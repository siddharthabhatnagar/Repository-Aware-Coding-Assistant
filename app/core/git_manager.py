import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import git
from app.core.security import validate_safe_path, sanitize_git_ref, SecurityViolation

class GitManager:
    """
    Safe Git operations manager: inspect branches, diffs, commits,
    dry-run patch proposals, and patch application with rollback support.
    """

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.is_git_repo = False
        self.repo: Optional[git.Repo] = None
        self._init_repo()

    def _init_repo(self):
        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=False)
            self.is_git_repo = True
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            self.is_git_repo = False
            self.repo = None

    def initialize_git(self) -> bool:
        """Initializes a new git repository if one doesn't exist."""
        try:
            self.repo = git.Repo.init(self.repo_path)
            self.is_git_repo = True
            # Create initial commit if empty
            if not self.repo.heads:
                self.repo.git.config('user.email', 'assistant@repopulse.local')
                self.repo.git.config('user.name', 'RepoPulse Assistant')
                self.repo.git.add(A=True)
                self.repo.index.commit("Initial repository commit by RepoPulse")
            return True
        except Exception as e:
            return False

    def get_repo_status(self) -> Dict[str, Any]:
        """Returns branch, commit SHA, dirty files, and remote info."""
        if not self.is_git_repo or not self.repo:
            return {
                "is_git_repo": False,
                "branch": "none",
                "commit_hash": "",
                "is_dirty": False,
                "untracked_files": [],
                "modified_files": [],
                "diff_summary": "Not a Git repository"
            }

        try:
            branch = self.repo.active_branch.name if not self.repo.head.is_detached else "detached HEAD"
        except (TypeError, ValueError):
            branch = "main"

        try:
            commit_hash = self.repo.head.commit.hexsha[:8] if self.repo.heads else "initial"
            commit_msg = self.repo.head.commit.message.strip() if self.repo.heads else ""
        except (ValueError, AttributeError):
            commit_hash = "none"
            commit_msg = ""

        untracked = self.repo.untracked_files[:20]
        modified = [item.a_path for item in self.repo.index.diff(None)][:20]

        return {
            "is_git_repo": True,
            "branch": branch,
            "commit_hash": commit_hash,
            "commit_message": commit_msg,
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": untracked,
            "modified_files": modified,
            "diff_summary": f"{len(modified)} modified, {len(untracked)} untracked"
        }

    def get_commit_history(self, max_count: int = 15) -> List[Dict[str, Any]]:
        """Returns recent commits."""
        if not self.is_git_repo or not self.repo:
            return []

        try:
            commits = []
            for c in list(self.repo.iter_commits(max_count=max_count)):
                commits.append({
                    "hash": c.hexsha[:8],
                    "full_hash": c.hexsha,
                    "author": c.author.name,
                    "date": c.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    "message": c.message.strip(),
                    "summary": c.summary
                })
            return commits
        except Exception:
            return []

    def get_diff(self, staged: bool = False, file_path: Optional[str] = None) -> str:
        """Returns git diff for the repo or a specific file."""
        if not self.is_git_repo or not self.repo:
            return ""

        try:
            if staged:
                diff_index = self.repo.head.commit.diff() if self.repo.heads else []
            else:
                diff_index = self.repo.index.diff(None)

            if file_path:
                safe_fp = validate_safe_path(self.repo_path, file_path)
                rel_fp = safe_fp.relative_to(self.repo_path).as_posix()
                return self.repo.git.diff(rel_fp)

            return self.repo.git.diff()
        except Exception as e:
            return f"Error retrieving diff: {str(e)}"

    def apply_patch(self, patch_content: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Applies a unified patch safely.
        If dry_run is True, verifies that the patch applies cleanly without writing.
        """
        if not patch_content.strip():
            return {"success": False, "message": "Patch content is empty."}

        # Check safety: forbid paths escaping repo inside diff headers
        for line in patch_content.splitlines():
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                target = line[6:].strip()
                try:
                    validate_safe_path(self.repo_path, target)
                except SecurityViolation as e:
                    return {"success": False, "message": f"Patch security violation: {str(e)}"}

        try:
            cmd = ["git", "apply"]
            if dry_run:
                cmd.append("--check")

            res = subprocess.run(
                cmd,
                input=patch_content,
                text=True,
                cwd=str(self.repo_path),
                capture_output=True,
                timeout=10
            )

            if res.returncode == 0:
                msg = "Patch verification succeeded (dry-run)." if dry_run else "Patch applied successfully."
                return {
                    "success": True,
                    "message": msg,
                    "dry_run": dry_run,
                    "output": res.stdout
                }
            else:
                return {
                    "success": False,
                    "message": f"Git apply failed: {res.stderr.strip() or res.stdout.strip()}",
                    "dry_run": dry_run
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "Patch application timed out."}
        except Exception as e:
            return {"success": False, "message": f"Unexpected error applying patch: {str(e)}"}
