import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _looks_like_lock_contention(stderr: Optional[str]) -> bool:
    """True when a git write failed because another process held the
    repo lock (``.git/index.lock`` or a ref lock), not because of a
    genuine error. Git does not block on these — it fails fast with a
    fatal ``Unable to create '.../index.lock': File exists`` (exit 128)
    — so the remedy is a short backoff + retry, not surfacing the error.
    """
    s = (stderr or "").lower()
    return (
        "index.lock" in s
        or (".lock" in s and "file exists" in s)
        or "cannot lock ref" in s
    )


# Default timeouts in seconds for git subprocess invocations. Local
# read-only ops (status, log, show, diff) and small writes (add,
# commit) should complete in well under a second on a healthy repo;
# 30s is a generous cap that flags real problems (filesystem locks,
# antivirus interference, FSMonitor misbehavior) without false
# positives. Network ops (push/fetch) get a longer budget for slow
# remotes and slow auth handshakes.
_DEFAULT_LOCAL_TIMEOUT = 30.0
_DEFAULT_NETWORK_TIMEOUT = 60.0


def _resolve_local_timeout() -> float:
    raw = (os.getenv("ADMZ_GIT_LOCAL_TIMEOUT_SECONDS", "") or "").strip()
    if not raw:
        return _DEFAULT_LOCAL_TIMEOUT
    try:
        v = float(raw)
        return v if v > 0 else _DEFAULT_LOCAL_TIMEOUT
    except ValueError:
        return _DEFAULT_LOCAL_TIMEOUT


def _resolve_network_timeout() -> float:
    raw = (os.getenv("ADMZ_GIT_NETWORK_TIMEOUT_SECONDS", "") or "").strip()
    if not raw:
        return _DEFAULT_NETWORK_TIMEOUT
    try:
        v = float(raw)
        return v if v > 0 else _DEFAULT_NETWORK_TIMEOUT
    except ValueError:
        return _DEFAULT_NETWORK_TIMEOUT


# On Windows, CREATE_NO_WINDOW prevents the spawned process from
# attaching to / opening a console window. Without it, git.exe
# launched from a python.exe child of a console-less FastAPI server
# can hang trying to attach a console for credential prompts or
# other interactive output. The flag is Windows-only; on POSIX it's
# unused (None passed to creationflags).
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _auto_push_enabled() -> bool:
    """Read ADMZ_AUTO_PUSH env var. Default ON when an origin remote
    is configured (the GitRepo asks separately). Operators can flip
    this OFF via ``ADMZ_AUTO_PUSH=false`` for air-gapped deployments
    or to defer pushes.
    """
    raw = (os.getenv("ADMZ_AUTO_PUSH", "") or "").strip().lower()
    return raw not in ("false", "0", "no", "off")


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Force-kill a git subprocess AND its descendants.

    A ``subprocess`` timeout kills only the *direct* ``git`` child. But a
    network op (``push``/``fetch``) spawns ``git-remote-https`` / ``ssh`` as a
    grandchild that inherits the stdout pipe — so ``communicate()`` keeps
    blocking on that pipe even after the direct child dies, and the timeout
    never actually rescues the call. That is the hang that wedged the server
    (a hung push under a credential-less LocalSystem service). Kill the whole
    tree so the pipe closes and the call can be reaped.
    """
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            # /T = terminate the tree (git-remote-https, ssh, cred helpers).
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            )
        else:
            # git is launched with start_new_session=True, so it leads its own
            # process group — signal the whole group.
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:  # nosec - best-effort teardown; backstopped below
        pass
    finally:
        try:
            proc.kill()  # backstop the direct child regardless of the above
        except Exception:
            pass


def _askpass_helper_path() -> str:
    """Path to a tiny generated ``GIT_ASKPASS`` helper that echoes the token
    from the ``ADMZ_GH_TOKEN`` env var — so a GitHub App installation token can
    authenticate a push without ever landing in the command line or the
    persisted remote URL. Generated once under ADMZ_HOME."""
    from admz.paths import ensure_admz_home
    home = ensure_admz_home()
    if sys.platform == "win32":
        path = home / "git-askpass.cmd"
        content = "@echo %ADMZ_GH_TOKEN%\r\n"
    else:
        path = home / "git-askpass.sh"
        content = '#!/bin/sh\nprintf "%s" "$ADMZ_GH_TOKEN"\n'
    try:
        if not path.exists() or path.read_text() != content:
            path.write_text(content)
            if sys.platform != "win32":
                os.chmod(path, 0o700)
    except Exception:  # noqa: BLE001 - best-effort; a plain push still works
        pass
    return str(path)


class GitRepo:
    """Thin wrapper around a local git repository for config storage."""

    def __init__(self, repo_path: str, remote_url: Optional[str] = None):
        self.repo_path = Path(repo_path)
        self.remote_url = remote_url
        # Serializes the stage+commit critical section so two threads in
        # this process (e.g. a request handler and the health/audit
        # sweep) can't interleave ``git add -A`` / ``git commit`` on the
        # shared config-repo — which strands staged changes and can mix a
        # device's writes under another's commit message. GitRepo is a
        # process-wide singleton (see components.py), so an instance lock
        # covers every intra-process caller. Cross-process contention
        # (the chatbot MCP subprocess pool holds its own GitRepo) is
        # handled separately by the lock-retry in _run_git_write.
        self._commit_lock = threading.RLock()
        # Auto-push runs on a single background daemon thread so a slow/hung
        # push never blocks the caller (commits run on the asyncio event loop).
        # At most one push runs + one is queued: concurrent commits coalesce
        # into one eventual push, so pushes can't pile up. See _maybe_push.
        self._push_lock = threading.Lock()
        self._push_running = False
        self._push_pending = False
        self._push_thread: Optional[threading.Thread] = None
        self._ensure_repo()

    def _ensure_repo(self):
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            self._run_git("init")
            if self.remote_url:
                self._run_git("remote", "add", "origin", self.remote_url)
        self._ensure_identity()

    def _ensure_identity(self) -> None:
        """Guarantee a resolvable git author identity so commits succeed.

        ADMZ runs as a LocalSystem Windows service (ADR-0042 / Shawl), whose
        profile has no ``~/.gitconfig`` — so the interactive user's *global*
        git identity is invisible to it, and every commit dies with
        ``fatal: ... Author identity unknown`` (exit 128). Observed live: a
        full day of failed hourly audit commits + 34 stranded working-tree
        files on the deployed config-repo, all silently swallowed as
        best-effort audit-write warnings.

        Fix: if no identity is resolvable in *any* scope, write a repo-LOCAL
        one (``.git/config``, so it can't depend on ambient global config or
        which user starts the service). Set-if-missing — an operator or dev
        who configured their own identity (global or local) is respected.
        Overridable via ADMZ_GIT_AUTHOR_NAME / ADMZ_GIT_AUTHOR_EMAIL.
        """
        resolved = self._run_git("config", "--get", "user.email", check=False)
        if resolved.returncode == 0 and resolved.stdout.strip():
            return  # a name/email is already resolvable — leave it alone
        name = (os.getenv("ADMZ_GIT_AUTHOR_NAME") or "").strip() or "ADMZ"
        email = (os.getenv("ADMZ_GIT_AUTHOR_EMAIL") or "").strip() or "admz@localhost"
        self._run_git("config", "--local", "user.name", name)
        self._run_git("config", "--local", "user.email", email)
        logger.info(
            "configured repo-local git identity %s <%s> for %s "
            "(no ambient identity — likely running as a service)",
            name, email, self.repo_path,
        )

    def _run_git(
        self,
        *args: str,
        check: bool = True,
        timeout: Optional[float] = None,
        env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        """Invoke ``git`` as a subprocess with hardening for the
        chat-tool / FastAPI background-process context.

        ``env`` overrides the subprocess environment (default: inherit) — used
        by the authenticated push to hand git a GITHUB App token via
        ``GIT_ASKPASS`` without ever putting it in the command line.

        * ``stdin=DEVNULL`` — git inherits no stdin, so it can't
          accidentally block trying to read from one. This was the
          root cause of the homelab snapshot hang: when the MCP
          subprocess invoked ``git status --porcelain`` with default
          stdin handling on Windows, it occasionally blocked for
          minutes despite the operation being read-only and local.
        * ``creationflags=CREATE_NO_WINDOW`` on Windows — keeps git
          from trying to attach to / open a console window for any
          would-be interactive prompts (credential helper popups,
          etc.). Equivalent to running git "headless."
        * ``timeout`` — hard cap on subprocess wall time. Default
          30s for local ops, override via ``timeout=`` kwarg (push
          uses 60s by default — see _maybe_push). Operators can
          tune the global defaults via env vars
          ``ADMZ_GIT_LOCAL_TIMEOUT_SECONDS`` /
          ``ADMZ_GIT_NETWORK_TIMEOUT_SECONDS``.

        On timeout we kill the whole git process *tree* (see
        :func:`_kill_process_tree` — a plain ``subprocess.run`` timeout only
        kills the direct child and can hang forever on a pipe a grandchild
        holds) and re-raise ``TimeoutExpired``; callers that want best-effort
        behavior (auto-push) catch + log + continue.
        """
        if timeout is None:
            timeout = _resolve_local_timeout()
        popen_kwargs = dict(
            cwd=self.repo_path,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # git emits UTF-8; without an explicit encoding, Windows decodes
            # with the locale codepage (cp1252) and non-ASCII commit messages
            # mojibake on every history surface ("—" -> "â€”"). errors="replace"
            # so a stray invalid byte in a diff/file read degrades to U+FFFD
            # instead of crashing a history endpoint.
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
        )
        if env is not None:
            popen_kwargs["env"] = env
        if sys.platform != "win32":
            # Lead our own process group so a timeout can killpg the whole
            # tree (git + git-remote-https/ssh grandchildren) at once.
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(["git"] + list(args), **popen_kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                # Now that the tree (incl. any pipe-holding grandchild) is
                # dead, this drains + reaps without blocking.
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            logger.error(
                "git %s timed out after %.0fs (cwd=%s) — killed the git "
                "process tree (a network op can orphan git-remote-https/ssh "
                "grandchildren that keep the pipe open)",
                " ".join(args), timeout, self.repo_path,
            )
            raise
        result = subprocess.CompletedProcess(
            proc.args, proc.returncode, stdout, stderr,
        )
        if check and result.returncode != 0:
            logger.error("git %s failed: %s", " ".join(args), result.stderr)
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result

    def _run_git_write(
        self,
        *args: str,
        timeout: Optional[float] = None,
        attempts: int = 5,
    ) -> subprocess.CompletedProcess:
        """Run a mutating git command (``add``/``commit``) that can lose a
        race on ``.git/index.lock`` when another ADMZ *process* (the chatbot
        MCP subprocess pool holds its own GitRepo on the same config-repo)
        commits concurrently. Git fails such a race fast with a fatal
        ``Unable to create '.../index.lock': File exists`` (exit 128) rather
        than blocking, so we retry with a short exponential backoff. Genuine
        failures (a rejecting hook, a real error) don't match the lock
        signature and raise immediately, preserving the ``check=True``
        contract. Intra-process contention is already serialized by
        ``self._commit_lock``; this only backstops the cross-process case.
        """
        delay = 0.15
        last: Optional[subprocess.CompletedProcess] = None
        for attempt in range(1, attempts + 1):
            last = self._run_git(*args, check=False, timeout=timeout)
            if last.returncode == 0:
                return last
            if attempt < attempts and _looks_like_lock_contention(last.stderr):
                logger.warning(
                    "git %s lost a repo-lock race (attempt %d/%d): %s — "
                    "retrying in %.2fs",
                    args[0] if args else "", attempt, attempts,
                    (last.stderr or "").strip(), delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, 1.5)
                continue
            break
        logger.error(
            "git %s failed: %s", " ".join(args),
            (last.stderr if last else ""),
        )
        raise subprocess.CalledProcessError(
            last.returncode, last.args, last.stdout, last.stderr
        )

    def device_path(self, device_id: str) -> Path:
        # CR-5 defense-in-depth: even when the REST and MCP entry
        # points validate device_id, internal callers might forget.
        # Reject path-traversal-shaped values here before they reach
        # mkdir/open.
        from admz.validators import validate_identifier
        validate_identifier(device_id, "device_id")
        return self.repo_path / "fleet" / device_id

    def has_changes(self) -> bool:
        result = self._run_git("status", "--porcelain")
        return bool(result.stdout.strip())

    def commit_snapshot(
        self,
        device_id: str,
        message: Optional[str] = None,
        auto_push: bool = True,
    ) -> Optional[str]:
        """Commit working-tree changes for one device (commit-on-change).

        ``auto_push=False`` skips the best-effort origin push — used for
        audit *observation* commits (ADR-0031) so frequent audits don't
        churn the remote; baselines/snapshots keep the default push.
        """
        with self._commit_lock:
            if not self.has_changes():
                return None
            self._run_git_write("add", "-A")
            msg = message or f"Snapshot {device_id}"
            self._run_git_write("commit", "-m", msg)
            sha = self._run_git("rev-parse", "HEAD").stdout.strip()
        # Push outside the commit lock — it's a best-effort network op and
        # holding the lock across a slow/hung remote would stall every other
        # committer for no benefit (the local commit is already the SoT).
        if auto_push:
            self._maybe_push()
        return sha

    def commit_fleet_snapshot(
        self,
        device_ids: List[str],
        message: Optional[str] = None,
    ) -> Optional[str]:
        with self._commit_lock:
            if not self.has_changes():
                return None
            self._run_git_write("add", "-A")
            msg = message or f"Fleet snapshot: {', '.join(device_ids)}"
            self._run_git_write("commit", "-m", msg)
            sha = self._run_git("rev-parse", "HEAD").stdout.strip()
        self._maybe_push()
        return sha

    def _maybe_push(self) -> None:
        """Schedule a best-effort background push (returns immediately).

        The push runs git over the network, which — under a service account
        with no credentials — can hang up to the network timeout. Commits run
        on the asyncio event loop, so pushing inline would block the whole
        server (exactly what wedged it once). Hand the push to a single
        background daemon thread and return; the local commit is already the
        source of truth. Concurrent commits coalesce into one eventual push
        (at most one running + one queued), so pushes never pile up. Disable
        entirely with ``ADMZ_AUTO_PUSH=false``.
        """
        if not _auto_push_enabled():
            return
        with self._push_lock:
            if self._push_running:
                # A push is in flight — fold this commit into one follow-up.
                self._push_pending = True
                return
            self._push_running = True
            self._push_thread = threading.Thread(
                target=self._push_worker, name="admz-git-push", daemon=True,
            )
            self._push_thread.start()

    def _push_worker(self) -> None:
        """Drain the coalesced push queue on the single background thread."""
        while True:
            try:
                self._do_push()
            except Exception as exc:  # _do_push swallows; belt-and-suspenders
                logger.warning(
                    "auto-push worker error (local commit preserved): %s", exc
                )
            with self._push_lock:
                if self._push_pending:
                    self._push_pending = False
                    continue  # a commit landed mid-push — push once more
                self._push_running = False
                return

    def _wait_for_pushes(self, timeout: float = 30.0) -> None:
        """Block until the background push worker is idle.

        For tests and graceful shutdown; production callers never wait on a
        push. No-op when no push has been scheduled.
        """
        thread = self._push_thread
        if thread is not None:
            thread.join(timeout=timeout)

    def _do_push(self) -> None:
        """The actual ``git push origin <branch>``, run on the background
        worker thread.

        Enabled whenever an ``origin`` remote is configured. Failures/timeouts
        are logged at WARNING and swallowed — the local commit is the source of
        truth, the remote is a mirror that catches up on the next successful
        push. A transient network blip, expired token, or non-fast-forward must
        not break the snapshot path.
        """
        try:
            # Origin configured?
            remote_check = self._run_git(
                "remote", "get-url", "origin", check=False,
            )
            if remote_check.returncode != 0:
                return  # no origin → nothing to push to
            # Resolve current branch. Detached HEAD shouldn't happen in
            # normal ADMZ operation but degrade gracefully if it does.
            branch_check = self._run_git(
                "symbolic-ref", "--short", "HEAD", check=False,
            )
            if branch_check.returncode != 0:
                logger.warning(
                    "auto-push skipped: HEAD is detached or current branch "
                    "could not be resolved"
                )
                return
            branch = branch_check.stdout.strip()
            # If a GitHub App is connected, mint a fresh installation token and
            # hand it to git via GIT_ASKPASS (never on the command line);
            # `-c credential.helper=` disables any ambient helper (e.g. Windows
            # Credential Manager) so only our token is used. No App → plain push
            # (unchanged). Push gets the network timeout; the _run_git tree-kill
            # tears down a hung push at the timeout rather than lingering.
            env, extra = self._push_auth_env()
            push_result = self._run_git(
                *extra, "push", "origin", branch,
                check=False, timeout=_resolve_network_timeout(), env=env,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "auto-push timed out (local commit preserved). The "
                "remote may catch up on the next snapshot; if pushes "
                "keep timing out, check the service's push credentials or "
                "set ADMZ_AUTO_PUSH=false."
            )
            return
        if push_result.returncode != 0:
            logger.warning(
                "auto-push to origin/%s failed (local commit preserved): %s",
                branch, (push_result.stderr or "").strip(),
            )
        else:
            logger.info("auto-pushed snapshot to origin/%s", branch)

    def _push_auth_env(self):
        """(env, extra_git_args) that authenticate the push with a fresh GitHub
        App installation token when one is connected, else (None, []).

        The token is passed via GIT_ASKPASS + the ADMZ_GH_TOKEN env var so it
        never appears in the process command line or the persisted remote URL.
        Lazy-imports the github_app bridge to keep this git layer independent of
        it; any failure degrades to an unauthenticated push (best-effort).
        """
        try:
            from admz.github_app.push import installation_token_for_push
            token = installation_token_for_push()
        except Exception:  # noqa: BLE001 - never let backup wiring break push
            token = None
        if not token:
            return None, []
        env = dict(os.environ)
        env["ADMZ_GH_TOKEN"] = token
        env["GIT_ASKPASS"] = _askpass_helper_path()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return env, ["-c", "credential.helper="]

    def set_remote_url(self, url: Optional[str]) -> None:
        """Set (or, when ``url`` is None, remove) the config-repo ``origin``
        remote. Used by the GitHub App connect / disconnect flow."""
        existing = self._run_git("remote", "get-url", "origin", check=False)
        has_origin = existing.returncode == 0
        if url is None:
            if has_origin:
                self._run_git("remote", "remove", "origin")
            return
        if has_origin:
            self._run_git("remote", "set-url", "origin", url)
        else:
            self._run_git("remote", "add", "origin", url)

    def write_device_yaml(self, device_id: str, device_info: Dict) -> Path:
        device_dir = self.device_path(device_id)
        device_dir.mkdir(parents=True, exist_ok=True)
        path = device_dir / "device.yaml"
        with open(path, "w") as f:
            yaml.dump(device_info, f, default_flow_style=False, sort_keys=True)
        return path

    def write_facet(
        self,
        device_id: str,
        facet_name: str,
        normalized: Dict,
        raw: Optional[Dict] = None,
    ) -> Path:
        from admz.validators import validate_identifier
        validate_identifier(facet_name, "facet_name")
        device_dir = self.device_path(device_id)

        config_dir = device_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / f"{facet_name}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(normalized, f, default_flow_style=False, sort_keys=True)

        if raw is not None:
            raw_dir = device_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"{facet_name}.yaml"
            with open(raw_path, "w") as f:
                yaml.dump(raw, f, default_flow_style=False, sort_keys=True)

        return config_path

    def _safe_rel_path(self, rel_path: str) -> Path:
        """Resolve a repo-relative path and refuse anything that escapes the
        repo (traversal, absolute paths, drive letters)."""
        candidate = (self.repo_path / rel_path).resolve()
        root = self.repo_path.resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"path escapes the config repo: {rel_path!r}")
        return candidate

    def write_yaml(self, rel_path: str, data: Dict) -> Path:
        """Write a YAML document at an arbitrary repo-relative path.

        First generic writer — every other writer is device-scoped
        (``write_facet``/``write_device_yaml``). Callers own the path
        vocabulary (e.g. ``demos/<id>/roles/<role>.yaml``, ADR-0047); commit
        via the usual ``commit_snapshot``/``commit_fleet_snapshot``.
        """
        path = self._safe_rel_path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)
        return path

    def remove_path(self, rel_path: str) -> bool:
        """Delete a file or directory tree from the working tree (history is
        untouched — the next commit records the removal). Returns True if
        anything was removed."""
        path = self._safe_rel_path(rel_path)
        if path.is_dir():
            shutil.rmtree(path)
            return True
        if path.exists():
            path.unlink()
            return True
        return False

    def read_facet(
        self, device_id: str, facet_name: str, ref: str = "HEAD"
    ) -> Optional[Dict]:
        from admz.validators import validate_git_ref, validate_identifier
        validate_identifier(device_id, "device_id")
        validate_identifier(facet_name, "facet_name")
        validate_git_ref(ref)
        rel_path = f"fleet/{device_id}/config/{facet_name}.yaml"
        content = self.get_file(rel_path, ref)
        if content is None:
            return None
        return yaml.safe_load(content)

    def get_file(self, path: str, ref: str = "HEAD") -> Optional[str]:
        result = self._run_git("show", f"{ref}:{path}", check=False)
        if result.returncode == 0:
            return result.stdout
        return None

    def diff(
        self,
        ref_a: str,
        ref_b: str = "HEAD",
        path: Optional[str] = None,
    ) -> str:
        args = ["diff", ref_a, ref_b]
        if path:
            args += ["--", path]
        result = self._run_git(*args, check=False)
        return result.stdout

    def diff_working(self, path: Optional[str] = None) -> str:
        args = ["diff", "HEAD"]
        if path:
            args += ["--", path]
        result = self._run_git(*args, check=False)
        return result.stdout

    def diff_commit(self, sha: str, path: Optional[str] = None) -> str:
        """Unified diff a single commit introduced — vs its first parent, or
        the empty tree for a root commit (which has no parent). ``path``
        scopes it to e.g. one device's directory."""
        # Git's well-known empty-tree object id, so a ROOT commit still shows
        # everything it added rather than erroring on a missing parent.
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        parent = self._run_git(
            "rev-parse", "--verify", "--quiet", f"{sha}^", check=False
        )
        base = parent.stdout.strip() if parent.returncode == 0 else empty_tree
        return self.diff(base, sha, path=path)

    def list_tags(self) -> List[str]:
        result = self._run_git("tag", "-l", check=False)
        return result.stdout.strip().split("\n") if result.stdout.strip() else []

    def create_tag(self, name: str, message: Optional[str] = None):
        args = ["tag"]
        if message:
            args += ["-a", "-m", message]
        args.append(name)
        self._run_git(*args)

    def push(self, remote: str = "origin", ref: Optional[str] = None):
        args = ["push", remote]
        if ref:
            args.append(ref)
        self._run_git(*args)

    def log(self, path: Optional[str] = None, max_count: int = 20) -> List[Dict]:
        fmt = "%H%n%an%n%ae%n%aI%n%s%n---"
        args = ["log", f"--format={fmt}", f"-n{max_count}"]
        if path:
            args += ["--", path]
        result = self._run_git(*args, check=False)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        commits = []
        for block in result.stdout.strip().split("---\n"):
            lines = block.strip().split("\n")
            if len(lines) >= 5:
                commits.append(
                    {
                        "sha": lines[0],
                        "author": lines[1],
                        "email": lines[2],
                        "date": lines[3],
                        "message": lines[4],
                    }
                )
        return commits

    def list_devices(self) -> List[str]:
        fleet_dir = self.repo_path / "fleet"
        if not fleet_dir.exists():
            return []
        return sorted(
            d.name for d in fleet_dir.iterdir() if d.is_dir()
        )

    def list_facets_at(self, device_id: str, ref: str) -> List[str]:
        """Facet names committed for ``device_id`` at ``ref`` ([] if none).

        Used to validate accept/promote targets: a commit can only become a
        device's baseline if it actually holds config for that device.
        """
        from admz.validators import validate_git_ref, validate_identifier
        validate_identifier(device_id, "device_id")
        validate_git_ref(ref)
        result = self._run_git(
            "ls-tree", "--name-only",
            f"{ref}:fleet/{device_id}/config", check=False,
        )
        if result.returncode != 0:
            return []
        return sorted(
            name[:-5]
            for name in result.stdout.split()
            if name.endswith(".yaml")
        )

    def head_sha(self) -> Optional[str]:
        """Current repo HEAD commit SHA, or None on an empty repo.

        Used to pin a baseline/observation pointer even when a snapshot
        produced no new commit (commit-on-change) — HEAD still contains the
        device's current config at that ref.
        """
        result = self._run_git("rev-parse", "HEAD", check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def device_snapshot_status(self, device_id: str) -> Dict[str, Any]:
        """Baseline + last-snapshot summary for one device.

        Powers the Configuration roster. ``has_baseline`` is True when at
        least one config facet is stored; ``last_snapshot`` is the ISO date
        of the most recent commit touching the device's path (or None).
        Reads the working tree (== HEAD after every snapshot commit),
        matching :meth:`list_devices`.
        """
        cfg_dir = self.repo_path / "fleet" / device_id / "config"
        facets = (
            sorted(p.stem for p in cfg_dir.glob("*.yaml"))
            if cfg_dir.is_dir()
            else []
        )
        commits = self.log(path=f"fleet/{device_id}", max_count=1)
        return {
            "has_baseline": bool(facets),
            "facets": facets,
            "last_snapshot": commits[0]["date"] if commits else None,
        }
