import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class GitRepo:
    """Thin wrapper around a local git repository for config storage."""

    def __init__(self, repo_path: str, remote_url: Optional[str] = None):
        self.repo_path = Path(repo_path)
        self.remote_url = remote_url
        self._ensure_repo()

    def _ensure_repo(self):
        if not (self.repo_path / ".git").exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            self._run_git("init")
            if self.remote_url:
                self._run_git("remote", "add", "origin", self.remote_url)

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            logger.error("git %s failed: %s", " ".join(args), result.stderr)
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result

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
    ) -> Optional[str]:
        if not self.has_changes():
            return None
        self._run_git("add", "-A")
        msg = message or f"Snapshot {device_id}"
        self._run_git("commit", "-m", msg)
        result = self._run_git("rev-parse", "HEAD")
        return result.stdout.strip()

    def commit_fleet_snapshot(
        self,
        device_ids: List[str],
        message: Optional[str] = None,
    ) -> Optional[str]:
        if not self.has_changes():
            return None
        self._run_git("add", "-A")
        msg = message or f"Fleet snapshot: {', '.join(device_ids)}"
        self._run_git("commit", "-m", msg)
        result = self._run_git("rev-parse", "HEAD")
        return result.stdout.strip()

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
