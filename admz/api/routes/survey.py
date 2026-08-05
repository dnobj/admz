"""
Survey / contributor mode admin page + actions.

Default-OFF. Lets an operator: read the disclosure, opt in, store a GitHub PAT
(encrypted), pick a redaction profile, preview *exactly* what would be sent, and
run a survey now (offline bundle or PR). All writes require an authenticated
principal (the survey settings are PROTECTED fleet settings).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from admz.api.context import AppContext, get_context
from admz.auth import Principal, get_current_principal
from admz.fleet_settings import fleet_settings
from admz.survey import secrets

SURVEY_SCHEDULE_ID = "survey"


def _sync_survey_schedule(ctx, *, enabled: bool, schedule_seconds: Optional[str]) -> None:
    """Create / update / disable the recurring 'survey' schedule from the settings.

    Saved interval only takes effect as an actual scheduled job through here — the
    setting alone does nothing. Disabling survey mode (or clearing the interval)
    disables the schedule rather than deleting it, so the cadence is remembered.
    """
    scheduler = getattr(ctx, "scheduler", None)
    if scheduler is None:
        return
    try:
        seconds = int(schedule_seconds) if schedule_seconds and schedule_seconds.strip() else 0
    except (TypeError, ValueError):
        seconds = 0
    existing = scheduler.get_schedule(SURVEY_SCHEDULE_ID)
    if enabled and seconds > 0:
        if existing:
            scheduler.update_schedule(SURVEY_SCHEDULE_ID,
                                      interval_seconds=seconds, enabled=True)
        else:
            from admz.snapshot.scheduler import SnapshotSchedule
            scheduler.add_schedule(SnapshotSchedule(
                id=SURVEY_SCHEDULE_ID,
                description="Survey / contributor discovery run",
                interval_seconds=seconds, job_type="survey"))
    elif existing:
        scheduler.update_schedule(SURVEY_SCHEDULE_ID, enabled=False)

logger = logging.getLogger(__name__)

router = APIRouter()

_template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))
try:  # match the rest of the app's template config (filters, globals)
    from admz.api.templating import configure as _configure_templates
    _configure_templates(templates)
except Exception:  # noqa: BLE001
    pass


def _page_context(request: Request, principal: Principal, *,
                  success: Optional[str] = None, error: Optional[str] = None,
                  preview=None, run_report=None) -> dict:
    return {
        "request": request,
        "title": "Survey Mode",
        "principal": principal,
        "enabled": secrets.is_enabled(),
        "has_pat": secrets.has_pat(),
        "repo": secrets.get_repo(),
        "redaction_profile": secrets.get_redaction_profile(),
        "validation_tier": secrets.get_validation_tier(),
        "contributor": secrets.get_contributor(),
        "schedule_seconds": fleet_settings.get(secrets.KEY_SCHEDULE_SECONDS) or "",
        "preview": preview,
        "run_report": run_report,
        "success": success,
        "error": error,
    }


@router.get("/settings/survey", response_class=HTMLResponse)
async def survey_settings_page(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    return templates.TemplateResponse(request, "survey_settings.html",
                                      _page_context(request, principal))


@router.post("/settings/survey", response_class=HTMLResponse)
async def survey_settings_action(
    request: Request,
    action: str = Form(...),
    enabled: Optional[str] = Form(None),
    github_pat: Optional[str] = Form(None),
    repo: Optional[str] = Form(None),
    redaction_profile: Optional[str] = Form(None),
    validation_tier: Optional[str] = Form(None),
    contributor: Optional[str] = Form(None),
    schedule_seconds: Optional[str] = Form(None),
    principal: Principal = Depends(get_current_principal),
    ctx: AppContext = Depends(get_context),
):
    success: Optional[str] = None
    error: Optional[str] = None
    preview = None
    run_report = None

    try:
        if action == "save_config":
            # #164: survey_mode_enabled is a declared capability; the write
            # goes through the audited setter. This route already had a
            # principal — what it lacked was a reason and an audit row.
            from admz import capabilities
            capabilities.set_enabled(
                "survey.contributor", bool(enabled), principal,
                reason="saved from the survey settings page")
            if repo:
                fleet_settings.set(secrets.KEY_REPO, repo.strip())
            if redaction_profile in ("hash-serial", "keep-serial"):
                fleet_settings.set(secrets.KEY_REDACTION, redaction_profile)
            if validation_tier in ("0", "1"):
                fleet_settings.set(secrets.KEY_VALIDATION_TIER, validation_tier)
            if contributor is not None:
                fleet_settings.set(secrets.KEY_CONTRIBUTOR, contributor.strip())
            if schedule_seconds is not None and schedule_seconds.strip():
                fleet_settings.set(secrets.KEY_SCHEDULE_SECONDS, schedule_seconds.strip())
            _sync_survey_schedule(ctx, enabled=bool(enabled),
                                  schedule_seconds=schedule_seconds
                                  if schedule_seconds is not None
                                  else fleet_settings.get(secrets.KEY_SCHEDULE_SECONDS))
            success = "Survey settings saved."

        elif action == "set_pat":
            if not github_pat or not github_pat.strip():
                error = "PAT cannot be empty. Use 'Clear PAT' to remove it."
            else:
                secrets.set_pat(github_pat.strip())
                success = "GitHub PAT saved (encrypted)."

        elif action == "clear_pat":
            secrets.set_pat("")
            success = "GitHub PAT cleared."

        elif action == "preview":
            from admz.survey.runner import preview as _preview
            preview = _preview()
            success = "Preview built (nothing was sent)."

        elif action == "run_now":
            from admz.survey.runner import run_survey
            # respect_enabled False so a manual run works even before the toggle;
            # submit only if a PAT is present, else offline.
            report = run_survey(submit=secrets.has_pat(), respect_enabled=False)
            run_report = report.to_dict()
            success = f"Survey run: {report.status}. {report.message}"

        else:
            error = f"Unknown action: {action!r}"
    except Exception as exc:  # noqa: BLE001 - surface to the page, never 500 the UI
        logger.exception("survey action failed")
        error = f"{type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        request,
        "survey_settings.html",
        _page_context(request, principal, success=success, error=error,
                      preview=preview, run_report=run_report))
