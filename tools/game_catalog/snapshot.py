"""Recoverable snapshot publication with an OS-held single-writer lock."""
import json
import os
import shutil
import subprocess
from pathlib import Path


def git(output, *args, check=True):
    return subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(output), *args], text=True, encoding="utf-8",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


class Snapshot:
    def __init__(self, output, no_git=False):
        self.output = Path(output).resolve()
        self.stage = self.output.with_name(self.output.name + ".catalog-stage")
        self.backup = self.output.with_name(self.output.name + ".catalog-backup")
        self.journal = self.output.with_name(self.output.name + ".catalog-journal.json")
        self.lock_path = self.output.with_name(self.output.name + ".catalog-lock")
        self.no_git = no_git
        self.lock = None

    def fingerprint(self):
        result = {}
        if self.output.exists():
            for directory, folders, names in os.walk(self.output):
                if Path(directory) == self.output:
                    folders[:] = [name for name in folders if name != ".git"]
                for name in names:
                    path = Path(directory) / name
                    stat = path.stat()
                    result[path.relative_to(self.output).as_posix()] = (stat.st_size, stat.st_mtime_ns)
        return result

    def remove_owned(self, path):
        if path not in (self.stage, self.backup) or path.parent != self.output.parent or path.is_symlink():
            raise ValueError(f"Refusing unexpected cleanup path: {path}")
        if path.exists():
            shutil.rmtree(path)

    def move_output_to_backup(self):
        # Windows refuses to rename a directory while any process holds a handle
        # inside it, such as an editor's Git integration watching .git.
        try:
            os.replace(self.output, self.backup)
        except PermissionError as exc:
            raise RuntimeError(
                f"Another process holds a file or directory open inside {self.output}, so it cannot be "
                "replaced. A common cause is an editor's Git integration watching its .git folder. "
                "Close that repository or program, then rerun.") from exc

    def write_journal(self, data):
        temporary = self.journal.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.journal)

    def recover(self):
        if not self.journal.exists():
            if self.stage.exists() or self.backup.exists():
                raise RuntimeError("Unowned staging/backup directory exists; inspect it before retrying.")
            return
        state = json.loads(self.journal.read_text(encoding="utf-8"))
        if state["output"] != str(self.output):
            raise RuntimeError("Snapshot journal belongs to a different output path")
        committed = state["phase"] == "committed"
        if not committed and (self.output / ".git").exists() and state.get("head"):
            head = git(self.output, "rev-parse", "HEAD", check=False).stdout.strip()
            committed = head != state["head"] and not git(self.output, "status", "--porcelain").stdout.strip()
        if self.backup.exists() and not committed:
            if self.output.exists():
                if (self.output / ".git").exists() and not (self.backup / ".git").exists():
                    os.replace(self.output / ".git", self.backup / ".git")
                self.remove_owned(self.stage)
                os.replace(self.output, self.stage)
            os.replace(self.backup, self.output)
            # A failed commit may have staged the new snapshot in the preserved repository.
            if (self.output / ".git").exists() and state.get("head"):
                git(self.output, "reset", "--mixed", state["head"])
        elif not committed and not state.get("existed", True) and state["phase"] == "publishing" and self.output.exists():
            self.remove_owned(self.stage)
            os.replace(self.output, self.stage)
        self.remove_owned(self.stage)
        self.remove_owned(self.backup)
        self.journal.unlink()

    def __enter__(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.lock_path.open("a+b")
        self.lock.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                self.lock.close()
                raise RuntimeError("Another refresh owns this output") from exc
        else:
            import fcntl
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            self.recover()
            if self.output.exists():
                if self.output.is_symlink() or not (self.output / "BUILD_INFO.md").is_file():
                    raise RuntimeError("Existing output is not a recognized generated game snapshot")
                if not (self.output / ".git").is_dir():
                    raise RuntimeError("Existing output has no local Git baseline; use a new output path to preserve its files")
                if (self.output / ".git").exists():
                    if git(self.output, "status", "--porcelain", "--untracked-files=all").stdout.strip():
                        raise RuntimeError("Snapshot contains local changes. Preserve them before refreshing.")
                    if git(self.output, "remote").stdout.strip():
                        raise RuntimeError("Game snapshots must have no Git remotes")
                    if git(self.output, "ls-files", "--others", "--ignored", "--exclude-standard").stdout.strip():
                        raise RuntimeError("Snapshot contains ignored local files. Preserve or remove them before refreshing.")
            self.state = {"output": str(self.output), "phase": "staging", "head": None, "existed": self.output.exists()}
            if (self.output / ".git").exists():
                self.state["head"] = git(self.output, "rev-parse", "HEAD").stdout.strip()
            self.original_files = self.fingerprint()
            self.write_journal(self.state)
            if self.state["existed"]:
                # Probe the publication swap now instead of failing after a long generation.
                # The journal lets recovery restore the output if the swap back is interrupted.
                try:
                    self.move_output_to_backup()
                except RuntimeError:
                    self.journal.unlink()
                    raise
                os.replace(self.backup, self.output)
            self.stage.mkdir()
            return self
        except BaseException:
            self.lock.close()
            raise

    def publish(self, message):
        if self.fingerprint() != self.original_files:
            raise RuntimeError("The existing snapshot changed during generation; preserving those changes")
        if self.state["head"]:
            if git(self.output, "rev-parse", "HEAD").stdout.strip() != self.state["head"] or git(self.output, "status", "--porcelain").stdout.strip():
                raise RuntimeError("The snapshot Git state changed during generation")
        self.state["phase"] = "publishing"
        self.write_journal(self.state)
        if self.output.exists():
            self.move_output_to_backup()
        os.replace(self.stage, self.output)
        if (self.backup / ".git").exists():
            os.replace(self.backup / ".git", self.output / ".git")
        if not self.no_git:
            if not (self.output / ".git").exists():
                git(self.output, "init", "--quiet")
            git(self.output, "add", "-A")
            # Directory replacement can preserve size and coarse file timestamps.
            # Force content hashing even if Git's cached stat data happens to match.
            git(self.output, "add", "--renormalize", ".")
            changed = git(self.output, "diff", "--cached", "--quiet", check=False)
            if changed.returncode == 1:
                git(self.output, "commit", "--quiet", "-m", message)
            elif changed.returncode:
                raise RuntimeError(changed.stderr)
        self.state["phase"] = "committed"
        self.write_journal(self.state)
        self.recover()

    def __exit__(self, kind, value, traceback):
        try:
            if self.journal.exists():
                self.recover()
        finally:
            self.lock.close()
