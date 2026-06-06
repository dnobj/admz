"""
Survey run orchestration -- the entry point the web route and scheduler call.

``preview()`` collects (read-only) and returns the exact payload that *would* be
sent, without writing or submitting anything. ``run_survey()`` collects, assembles
a bundle, and either opens a PR (if a PAT is configured and ``submit=True``) or
writes an offline bundle for out-of-band transfer.

Everything is dependency-injected so this is testable without a registry, network,
or PAT.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from admz import __version__ as ADMZ_VERSION
from admz.survey import secrets
from admz.survey.bundle import assemble_bundle
from admz.survey.collector import SurveyCollector
from admz.survey.redact import build_preview

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bundle_id() -> str:
    return "survey-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _work_dir() -> Path:
    import os
    return Path(os.getenv("ADMZ_SURVEY_WORK", str(Path.home() / ".admz" / "survey-work")))


@dataclass
class SurveyRunReport:
    status: str                       # "submitted" | "offline" | "no-changes" | "disabled"
    bundle_id: Optional[str] = None
    pr_url: Optional[str] = None
    offline_path: Optional[str] = None
    models: List[str] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _collector(registry=None, **kwargs) -> SurveyCollector:
    if registry is None:
        from admz.factory import create_device_registry
        registry = create_device_registry()
    kwargs.setdefault("validate", True)
    kwargs.setdefault("validation_tier", secrets.get_validation_tier())
    return SurveyCollector(registry, **kwargs)


def preview(device_ids: Optional[List[str]] = None, *,
            collector: Optional[SurveyCollector] = None) -> Dict[str, Any]:
    """Read-only: return the redacted payload that would be submitted. Sends nothing."""
    collector = collector or _collector()
    result = collector.survey_fleet(device_ids)
    snapshots = [s.redacted_snapshot for s in result.surveys]
    specs: List[str] = []
    for s in result.surveys:
        specs.extend(f"{s.model}:{api}" for api in s.openapi_specs)
    preview_payload = build_preview(snapshots, profile=collector.profile,
                                    included_specs=specs)
    preview_payload["models"] = [s.model for s in result.surveys]
    preview_payload["skipped"] = result.skipped
    preview_payload["errors"] = result.errors
    return preview_payload


def run_survey(*, submit: bool = True, device_ids: Optional[List[str]] = None,
               collector: Optional[SurveyCollector] = None,
               submitter=None, respect_enabled: bool = True) -> SurveyRunReport:
    """Collect -> bundle -> submit/offline. Returns a report (never raises per-device)."""
    if respect_enabled and not secrets.is_enabled():
        return SurveyRunReport(status="disabled", message="survey mode is disabled")

    collector = collector or _collector()
    result = collector.survey_fleet(device_ids)
    if not result.surveys:
        return SurveyRunReport(status="no-changes", skipped=result.skipped,
                               errors=result.errors,
                               message="nothing new vs the installed atlas")

    bundle_id = _bundle_id()
    root = assemble_bundle(
        _work_dir(), result.surveys,
        profile=collector.profile,
        contributor=secrets.get_contributor() or "unknown",
        admz_version=ADMZ_VERSION,
        bundle_id=bundle_id,
        created_utc=_now_iso(),
    )
    models = [s.model for s in result.surveys]

    # submit via PR if possible, else offline
    if submit and secrets.has_pat():
        from admz.survey.github import GitHubSubmitter
        if submitter is None:
            submitter = GitHubSubmitter(secrets.get_pat(), secrets.get_repo())
        branch = f"contrib/{(secrets.get_contributor() or 'site')}/{bundle_id}"
        title = f"survey: {', '.join(models)}"
        body = _pr_body(models, result, collector.profile)
        res = submitter.submit(root, branch=branch, title=title, body=body)
        return SurveyRunReport(
            status="submitted", bundle_id=bundle_id, pr_url=res.pr_url,
            models=models, skipped=result.skipped, errors=result.errors,
            message=res.message)

    from admz.survey.github import write_offline
    zip_path = write_offline(root)
    return SurveyRunReport(
        status="offline", bundle_id=bundle_id, offline_path=str(zip_path),
        models=models, skipped=result.skipped, errors=result.errors,
        message="no PAT configured (or submit disabled); wrote offline bundle")


def _pr_body(models, result, profile) -> str:
    lines = [
        "Automated survey contribution from an ADMZ install.",
        "",
        f"- **Models:** {', '.join(models)}",
        f"- **Redaction profile:** {profile}",
        f"- **ADMZ version:** {ADMZ_VERSION}",
        "",
        "No credentials, network/site config, geolocation, overlay text, or user "
        "names are included. Seeded ops are deterministic drafts at safe-default "
        "risk, pending maintainer review/enrich.",
    ]
    if result.errors:
        lines += ["", f"_{len(result.errors)} device(s) errored during survey._"]
    return "\n".join(lines)
