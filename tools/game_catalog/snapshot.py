"""Recoverable snapshot publication with an OS-held single-writer lock."""
import json
import hashlib
import os
import shutil
import stat
from pathlib import Path
from processes import run_process, GIT_SECONDS


def git(output, *args, check=True, env=None):
    return run_process(["git", "-c", "core.fsmonitor=false", "-C", str(output), *args],
                       timeout=GIT_SECONDS, check=check, env=env)


def index_signature(output, env=None):
    entries = git(output, "ls-files", "--stage", "-z", env=env).stdout
    return hashlib.sha256(entries.encode("utf-8")).hexdigest()


def file_tree(root):
    """Content identity for recovery, including no-Git diagnostic captures."""
    result = hashlib.sha256()
    for directory, folders, names in os.walk(root):
        if Path(directory) == root:
            folders[:] = [name for name in folders if name != ".git"]
        for name in sorted(names):
            path = Path(directory) / name
            content = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    content.update(block)
            result.update(json.dumps([path.relative_to(root).as_posix(), content.hexdigest()]).encode("utf-8"))
        folders.sort()
    return result.hexdigest()


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
            def retry(function, target, exc):
                mode = os.stat(target).st_mode
                if os.name != "nt" or not isinstance(exc, PermissionError) or mode & stat.S_IWRITE:
                    raise exc
                # Git's owned loose objects are read-only on Windows.
                os.chmod(target, mode | stat.S_IWRITE)
                function(target)
            shutil.rmtree(path, onexc=retry)

    def move_output_to_backup(self):
        # Windows refuses to rename a directory while any process holds a handle
        # inside it, such as an editor's Git integration watching .git.
        try:
            os.replace(self.output, self.backup)
        except PermissionError as exc:
            raise RuntimeError(
                f"Windows denied renaming {self.output}. Usually another process holds a file or directory "
                "open inside it, such as an editor's Git integration watching its .git folder; close that "
                "repository or program, then rerun. Otherwise check that this account may rename it.") from exc

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
        if state["phase"] not in ("staging", "publishing", "committed"):
            raise RuntimeError("Unknown snapshot journal phase; preserving all directories")
        if state["phase"] == "staging" and self.backup.exists():
            # Only the publication probe moves the output before publishing, so this
            # backup is the original snapshot. Never infer a commit from it.
            if self.output.exists():
                raise RuntimeError(f"{self.output} and {self.backup} both exist after an interrupted probe; "
                                   "inspect both before retrying.")
            os.replace(self.backup, self.output)
        committed = False
        if state["phase"] in ("publishing", "committed"):
            def ambiguous():
                raise RuntimeError(f"Ambiguous snapshot recovery: {self.output} matches neither the original "
                                   "nor a journaled publication state; preserving output, staging and backup directories.")
            def identity(root):
                if not (root / ".git").is_dir():
                    return None, None, None
                return (git(root, "rev-parse", "HEAD", check=False).stdout.strip(),
                        git(root, "rev-parse", "HEAD^{tree}", check=False).stdout.strip(), index_signature(root))
            original_git = (state.get("head"), state.get("original_git_tree"), state.get("original_index"))
            prepared_git = (state.get("prepared_commit"), state.get("prepared_tree"), state.get("prepared_index"))
            backup_git = (self.backup / ".git").is_dir()
            output_git = (self.output / ".git").is_dir()
            if self.stage.exists() and file_tree(self.stage) != state.get("prepared_files"):
                ambiguous()
            if self.backup.exists():
                if (file_tree(self.backup) != state.get("original_tree") or
                        (backup_git and (output_git or identity(self.backup) != original_git))):
                    ambiguous()
            if self.output.exists():
                observed = identity(self.output)
                files = file_tree(self.output)
                clean = not output_git or not (
                    git(self.output, "status", "--porcelain=v2", "--untracked-files=all").stdout.strip() or
                    git(self.output, "ls-files", "--others", "--ignored", "--exclude-standard").stdout.strip())
                committed = (files == state.get("prepared_files") and observed == prepared_git and
                             (clean or state.get("no_git", False)))
                original = (state["phase"] == "publishing" and files == state.get("original_tree") and
                            observed == original_git and clean)
                # Promotion leaves the original Git directory in backup; transfer
                # then leaves the original HEAD/index beside the prepared files.
                # A reset may have installed only its index or only its HEAD.
                intermediate = (state["phase"] == "publishing" and self.backup.exists() and not self.stage.exists() and
                                files == state.get("prepared_files") and state.get("head") and (
                                    (not output_git and backup_git) or
                                    (output_git and not backup_git and observed in (
                                        original_git,
                                        (original_git[0], original_git[1], prepared_git[2]),
                                        (prepared_git[0], prepared_git[1], original_git[2])))))
                if not committed and not original and not intermediate:
                    ambiguous()
            elif state["phase"] == "committed" or (state.get("existed") and (not self.backup.exists() or not backup_git)):
                ambiguous()
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
            self.state = {"output": str(self.output), "phase": "staging", "head": None,
                          "existed": self.output.exists(), "no_git": self.no_git,
                          "original_tree": file_tree(self.output), "original_git_tree": None, "original_index": None}
            if (self.output / ".git").exists():
                self.state["head"] = git(self.output, "rev-parse", "HEAD").stdout.strip()
                self.state["original_git_tree"] = git(self.output, "rev-parse", "HEAD^{tree}").stdout.strip()
                self.state["original_index"] = index_signature(self.output)
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
        self.prepare(message)
        if file_tree(self.output) != self.state["original_tree"] or (
                self.state["head"] and (
                    git(self.output, "rev-parse", "HEAD").stdout.strip() != self.state["head"] or
                    index_signature(self.output) != self.state["original_index"] or
                    git(self.output, "status", "--porcelain=v2", "--untracked-files=all").stdout.strip())):
            raise RuntimeError("The existing snapshot changed during preparation; preserving those changes")
        self.state["phase"] = "publishing"
        self.write_journal(self.state)
        if self.output.exists():
            self.move_output_to_backup()
        os.replace(self.stage, self.output)
        if (self.backup / ".git").exists():
            os.replace(self.backup / ".git", self.output / ".git")
        if not self.no_git:
            git(self.output, "reset", "--mixed", self.state["prepared_commit"])
        self.state["phase"] = "committed"
        self.write_journal(self.state)
        self.recover()

    def prepare(self, message):
        """Create the exact commit without changing the original HEAD or index."""
        self.state["prepared_files"] = file_tree(self.stage)
        self.state["prepared_commit"] = self.state["head"]
        self.state["prepared_tree"] = None
        self.state["prepared_index"] = self.state["original_index"]
        if self.no_git:
            if self.state["head"]:
                self.state["prepared_tree"] = git(self.output, "rev-parse", "HEAD^{tree}").stdout.strip()
            return
        if self.state["head"]:
            index_dir = self.stage / ".git"
            index_dir.mkdir()
            index = index_dir / "index"
            environment = dict(os.environ, GIT_INDEX_FILE=str(index))
            try:
                git(self.output, "read-tree", self.state["head"], env=environment)
                git(self.output, "--work-tree", str(self.stage), "add", "-A", env=environment)
                # Hash content even when size and coarse timestamps match.
                git(self.output, "--work-tree", str(self.stage), "add", "--renormalize", ".", env=environment)
                tree = git(self.output, "write-tree", env=environment).stdout.strip()
                self.state["prepared_index"] = index_signature(self.output, env=environment)
                if tree == git(self.output, "rev-parse", "HEAD^{tree}").stdout.strip():
                    commit = self.state["head"]
                else:
                    commit = git(self.output, "commit-tree", tree, "-p", self.state["head"], "-m", message).stdout.strip()
            finally:
                for path in index_dir.iterdir():
                    path.unlink()
                index_dir.rmdir()
        else:
            git(self.stage, "init", "--quiet")
            git(self.stage, "add", "-A")
            git(self.stage, "commit", "--quiet", "-m", message)
            tree = git(self.stage, "rev-parse", "HEAD^{tree}").stdout.strip()
            commit = git(self.stage, "rev-parse", "HEAD").stdout.strip()
            self.state["prepared_index"] = index_signature(self.stage)
        self.state.update(prepared_tree=tree, prepared_commit=commit)

    def __exit__(self, kind, value, traceback):
        try:
            if self.journal.exists():
                self.recover()
        finally:
            self.lock.close()
