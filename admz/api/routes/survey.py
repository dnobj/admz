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
    # #351 (#164 item 2): every branch below either writes a protected fleet
    # setting — two of them real credentials, `survey_github_pat` encrypted at
    # rest — or runs a survey that can submit fleet data to GitHub. The module
    # docstring above has claimed "all writes require an authenticated
    # principal" since it was written; this is the line that makes that true.
    from admz.audit import record_event
    from admz.authz import require_authenticated_principal

    require_authenticated_principal(principal)

    success: Optional[str] = None
    error: Optional[str] = None
    preview = None
    run_report = None
    #: Keys actually written, accumulated as each write commits. Each
    #: `fleet_settings.set` below commits independently, so a failure partway
    #: through `save_config` leaves earlier keys changed — the failure row has
    #: to name them or a partial application is an unattributed change.
    applied: list = []

    try:
        if action == "save_config":
            # #164: survey_mode_enabled is a declared capability; the write
            # goes through the audited setter. This route already had a
            # principal — what it lacked was a reason and an audit row.
            from admz import capabilities
            capabilities.set_enabled(
                "survey.contributor", bool(enabled), principal,
                reason="saved from the survey settings page")
            applied.append("survey.contributor")
            if repo:
                fleet_settings.set(secrets.KEY_REPO, repo.strip())
                applied.append(secrets.KEY_REPO)
            if redaction_profile in ("hash-serial", "keep-serial"):
                fleet_settings.set(secrets.KEY_REDACTION, redaction_profile)
                applied.append(secrets.KEY_REDACTION)
            if validation_tier in ("0", "1"):
                fleet_settings.set(secrets.KEY_VALIDATION_TIER, validation_tier)
                applied.append(secrets.KEY_VALIDATION_TIER)
            if contributor is not None:
                fleet_settings.set(secrets.KEY_CONTRIBUTOR, contributor.strip())
                applied.append(secrets.KEY_CONTRIBUTOR)
            if schedule_seconds is not None and schedule_seconds.strip():
                fleet_settings.set(secrets.KEY_SCHEDULE_SECONDS, schedule_seconds.strip())
                applied.append(secrets.KEY_SCHEDULE_SECONDS)
            _sync_survey_schedule(ctx, enabled=bool(enabled),
                                  schedule_seconds=schedule_seconds
                                  if schedule_seconds is not None
                                  else fleet_settings.get(secrets.KEY_SCHEDULE_SECONDS))
            # The repo target is recorded: pointing the survey at a different
            # repository is the step that turns a contribution into an
            # exfiltration, and it was the one write with no trace.
            record_event(principal, "fleet_setting.write",
                         resource="survey_settings:save_config",
                         details={"applied": list(applied),
                                  "repo": (repo or "").strip() or None,
                                  "redaction_profile": redaction_profile,
                                  "validation_tier": validation_tier})
            success = "Survey settings saved."

        elif action == "set_pat":
            if not github_pat or not github_pat.strip():
                error = "PAT cannot be empty. Use 'Clear PAT' to remove it."
            else:
                secrets.set_pat(github_pat.strip())
                applied.append(secrets.KEY_PAT)
                record_event(principal, "fleet_setting.write",
                             resource=f"survey_settings:{secrets.KEY_PAT}")
                success = "GitHub PAT saved (encrypted)."

        elif action == "clear_pat":
            secrets.set_pat("")
            applied.append(secrets.KEY_PAT)
            record_event(principal, "fleet_setting.write",
                         resource=f"survey_settings:{secrets.KEY_PAT}",
                         details={"cleared": True})
            success = "GitHub PAT cleared."

        elif action == "preview":
            import asyncio

            from admz.survey.runner import preview as _preview
            # The collector talks to every device synchronously — run it in a
            # worker thread so it stops blocking the event loop (#452).
            preview = await asyncio.to_thread(_preview)
            success = "Preview built (nothing was sent)."

        elif action == "run_now":
            import asyncio

            from admz.survey.runner import run_survey
            # respect_enabled False so a manual run works even before the
            # toggle — the RUN is always allowed; the PUSH is not. Submitting
            # requires the contributor capability AND a PAT (ADR-0030 as
            # amended by ADR-0063): "Run now" + a stored PAT + the toggle OFF
            # used to open a PR anyway, which was the one path around the
            # capability. Toggle off now yields an offline bundle.
            submitting = secrets.has_pat() and secrets.is_enabled()
            # Audited BEFORE the run: this can push fleet data to GitHub. A
            # run that dies mid-flight must still leave a record that someone
            # started it.
            record_event(principal, "survey.run_now",
                         resource="survey_settings:run_now",
                         details={"submit": submitting,
                                  "enabled": secrets.is_enabled(),
                                  "repo": fleet_settings.get(secrets.KEY_REPO)})
            report = await asyncio.to_thread(
                run_survey, submit=submitting, respect_enabled=False
            )
            run_report = report.to_dict()
            success = f"Survey run: {report.status}. {report.message}"

        else:
            error = f"Unknown action: {action!r}"
    except Exception as exc:  # noqa: BLE001 - surface to the page, never 500 the UI
        logger.exception("survey action failed")
        error = f"{type(exc).__name__}: {exc}"
        # `applied` is the point of this row. Each write above commits on its
        # own, so a failure partway through leaves real, effective changes —
        # a bare "action failed" would read as "nothing happened", which is
        # the wrong thing to believe about a repointed survey repo.
        record_event(principal, "survey.action", resource=f"survey_settings:{action}",
                     success=False, error_message=f"{type(exc).__name__}: {exc}",
                     details={"applied": list(applied),
                              "partial": bool(applied)})

    return templates.TemplateResponse(
        request,
        "survey_settings.html",
        _page_context(request, principal, success=success, error=error,
                      preview=preview, run_report=run_report))
