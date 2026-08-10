"""
Submit a contribution bundle -- as a GitHub PR (fork -> branch -> PR) or offline.

Two paths:

* :func:`write_offline` -- copy the bundle to ``~/.admz/survey-out/`` (+ a zip)
  for out-of-band transfer. Used when there's no PAT or the site is air-gapped.
  This is the Phase-1 default and needs no network.

* :class:`GitHubSubmitter` -- fork-and-PR via the GitHub REST API using a
  fine-grained PAT scoped to the contributor's fork. Uses the Contents API
  (one PUT per file) for simplicity/robustness. HTTP is injectable so the flow
  is unit-testable without a live token.

Design choices (per the approved plan):
  - **fork-and-PR**, never push to upstream (least privilege);
  - **idempotent**: a branch name derived from the bundle id; if an open PR for
    that head already exists, reuse it;
  - the PAT is supplied by the caller (decrypted via :mod:`admz.survey.secrets`);
    it is never logged.
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# offline path
# ---------------------------------------------------------------------------


def _offline_root() -> Path:
    from admz.paths import survey_out_dir
    return survey_out_dir()


def write_offline(bundle_root: Path, *, out_dir: Optional[Path] = None) -> Path:
    """Copy the bundle dir + a .zip into the offline out dir. Returns the zip path."""
    bundle_root = Path(bundle_root)
    out = Path(out_dir) if out_dir else _offline_root()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / bundle_root.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(bundle_root, dest)
    zip_path = out / f"{bundle_root.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(bundle_root.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(bundle_root.parent))
    return zip_path


# ---------------------------------------------------------------------------
# GitHub PR path
# ---------------------------------------------------------------------------


class HttpSession(Protocol):
    def request(self, method: str, url: str, **kwargs) -> Any: ...


@dataclass
class SubmitResult:
    pr_url: Optional[str]
    branch: str
    created: bool
    reused: bool = False
    message: str = ""


class GitHubError(RuntimeError):
    pass


class GitHubSubmitter:
    def __init__(self, token: str, upstream_repo: str, *,
                 session: Optional[HttpSession] = None, base_branch: str = "main"):
        if "/" not in upstream_repo:
            raise ValueError("upstream_repo must be 'owner/name'")
        self.token = token
        self.upstream_owner, self.upstream_name = upstream_repo.split("/", 1)
        self.base_branch = base_branch
        self._session = session  # lazy httpx.Client if None

    # -- low-level ----------------------------------------------------------
    def _sess(self) -> HttpSession:
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=30)
        return self._session

    def _req(self, method: str, path: str, *, json: Optional[Dict] = None,
             ok=(200, 201)) -> Dict:
        # Every request here carries the survey PAT as a bearer token, so the
        # target must never be caller-influenced. This used to be
        # `path if path.startswith("http") else ...`, which would send the token
        # to any absolute URL handed in. No caller does that today — but GitHub
        # responses are full of absolute URLs (`url`, `html_url`, and pagination
        # `Link` headers most of all), and threading one back in is the natural
        # next change. Found by the outbound-target sweep #355 asked for; same
        # class as #160, where an SPN derived from a caller-supplied host leaked
        # the service account's NTLM response.
        if not path.startswith("/"):
            raise GitHubError(
                f"refusing to send the survey token to a non-relative target: "
                f"{path!r}. Pass an api.github.com path beginning with '/'."
            )
        url = f"{GITHUB_API}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = self._sess().request(method, url, headers=headers, json=json)
        status = getattr(resp, "status_code", None)
        if status not in ok:
            body = getattr(resp, "text", "")
            raise GitHubError(f"{method} {url} -> {status}: {body[:300]}")
        try:
            return resp.json()
        except Exception:  # noqa: BLE001
            return {}

    # -- high-level steps ---------------------------------------------------
    def whoami(self) -> str:
        return self._req("GET", "/user").get("login", "")

    def ensure_fork(self) -> str:
        """Return the fork owner (the PAT user); create the fork if missing."""
        login = self.whoami()
        try:
            self._req("GET", f"/repos/{login}/{self.upstream_name}", ok=(200,))
        except GitHubError:
            self._req("POST", f"/repos/{self.upstream_owner}/{self.upstream_name}/forks",
                      ok=(202, 200))
        return login

    def base_sha(self) -> str:
        ref = self._req(
            "GET", f"/repos/{self.upstream_owner}/{self.upstream_name}/git/ref/heads/{self.base_branch}",
            ok=(200,))
        return ref["object"]["sha"]

    def create_branch(self, fork_owner: str, branch: str, sha: str) -> None:
        self._req("POST", f"/repos/{fork_owner}/{self.upstream_name}/git/refs",
                  json={"ref": f"refs/heads/{branch}", "sha": sha}, ok=(201,))

    def put_file(self, fork_owner: str, branch: str, repo_path: str,
                 content: bytes, message: str) -> None:
        b64 = base64.b64encode(content).decode()
        self._req("PUT", f"/repos/{fork_owner}/{self.upstream_name}/contents/{repo_path}",
                  json={"message": message, "content": b64, "branch": branch},
                  ok=(200, 201))

    def find_open_pr(self, fork_owner: str, branch: str) -> Optional[str]:
        prs = self._req(
            "GET",
            f"/repos/{self.upstream_owner}/{self.upstream_name}/pulls?state=open&head={fork_owner}:{branch}",
            ok=(200,))
        if isinstance(prs, list) and prs:
            return prs[0].get("html_url")
        return None

    def open_pr(self, fork_owner: str, branch: str, title: str, body: str) -> str:
        pr = self._req("POST", f"/repos/{self.upstream_owner}/{self.upstream_name}/pulls",
                       json={"title": title, "body": body,
                             "head": f"{fork_owner}:{branch}", "base": self.base_branch},
                       ok=(201,))
        return pr.get("html_url", "")

    # -- orchestration ------------------------------------------------------
    def submit(self, bundle_root: Path, *, branch: str, title: str, body: str,
               repo_prefix: str = "contrib/incoming") -> SubmitResult:
        bundle_root = Path(bundle_root)
        fork_owner = self.ensure_fork()

        existing = self.find_open_pr(fork_owner, branch)
        if existing:
            return SubmitResult(pr_url=existing, branch=branch, created=False,
                                reused=True, message="open PR already exists for this branch")

        sha = self.base_sha()
        self.create_branch(fork_owner, branch, sha)

        files: List[Path] = sorted(p for p in bundle_root.rglob("*") if p.is_file())
        for p in files:
            rel = p.relative_to(bundle_root).as_posix()
            repo_path = f"{repo_prefix}/{bundle_root.name}/{rel}"
            self.put_file(fork_owner, branch, repo_path, p.read_bytes(),
                          f"survey: add {bundle_root.name}/{rel}")

        pr_url = self.open_pr(fork_owner, branch, title, body)
        return SubmitResult(pr_url=pr_url, branch=branch, created=True,
                            message=f"opened PR with {len(files)} files")
