"""Best-effort operator diagnostics, outside generated snapshot identities."""
import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import uuid

from processes import ERROR_WRITE_SECONDS

PHASES = ("input hashing/reuse check", "catalog decode", "decompile", "Git promotion", "cleanup")
RUNS = Path(__file__).resolve().parents[2] / ".local" / "runs"


def emit(message, stream=None):
    """A stalled diagnostic consumer must never hold up the caller."""
    def write():
        try:
            print(message, file=stream or sys.stderr, flush=True)
        except Exception:
            pass
    try:
        worker = threading.Thread(target=write, daemon=True)
        worker.start()
        return worker
    except Exception:
        return None


def diagnostic(operation):
    @wraps(operation)
    def safe(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            emit(f"Warning: capture timing {operation.__name__}: {short_error(exc)}")
    return safe


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def short_error(error):
    return (str(error).splitlines() or [type(error).__name__])[0][:300]


def timing_parser():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--timing-receipt", type=Path)
    return parser


def receipt_directory(receipt, output=""):
    # Usage validation is deliberately outside the best-effort diagnostic guard.
    root = RUNS.absolute()
    if RUNS.resolve() != root:
        raise ValueError(f"Timing directory must resolve inside {root}")
    path = Path(receipt).resolve() if receipt is not None else root / "capture.json"
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Timing receipt must resolve inside {root}")
    if output:
        snapshot = Path(output).resolve()
        if path.parent == snapshot or path.parent.is_relative_to(snapshot):
            raise ValueError("Timing receipt cannot be inside snapshot output")
    return path.parent


class Timing:
    def __init__(self, output="", receipt=None):
        directory = receipt_directory(receipt, output)
        self.resumed = False
        self.announce = False
        self.run_id = uuid.uuid4().hex[:8]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.receipt = directory / f"capture-{stamp}-{os.getpid()}-{self.run_id}.json"
        self.pending = self.receipt.with_suffix(".pending")
        self.state = {"run_id": self.run_id, "owner": os.urandom(16).hex(), "started": time.perf_counter(), "active": {}, "receipt": {
            "schema": "humanhost.capture-timing.v1", "started_at": utc_now(), "finished_at": None,
            "seconds": 0.0, "outcome": "failed", "error": None, "output_path": str(output),
            "output_commit": None, "game": None,
            "phases": [{"name": name, "seconds": 0.0, "outcome": "skipped"} for name in PHASES],
            "assemblies": []}}
        self.start_worker()
        self.enqueue(self.reserve)
        self.checkpoint()

    @diagnostic
    def start_worker(self):
        self.lock = threading.Lock()
        self.tasks = queue.SimpleQueue()
        self.owned = {}
        self.reports = []
        def work():
            while True:
                operation, args = self.tasks.get()
                if operation is None:
                    return
                diagnostic(operation)(*args)
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    @classmethod
    def resume(cls, pending):
        # Validation happens before starting a worker or touching any file.
        receipt_directory(Path(pending).with_suffix(".json"))
        result = cls.__new__(cls)
        result.resumed = True
        result.announce = False
        result.pending = Path(pending)
        result.receipt = result.pending.with_suffix(".json")
        # The supervisor supplies a fallback even if storage is unavailable.
        result.run_id = result.pending.stem.rsplit("-", 1)[-1]
        result.state = diagnostic(json.loads)(os.environ.get("HUMANHOST_CAPTURE_TIMING_STATE", ""))
        if not result.state:
            result.state = {"run_id": result.run_id, "started": time.perf_counter(), "active": {}, "receipt": {
                "schema": "humanhost.capture-timing.v1", "started_at": utc_now(), "finished_at": None,
                "seconds": 0.0, "outcome": "failed", "error": None, "output_path": "", "output_commit": None,
                "game": None, "phases": [{"name": name, "seconds": 0.0, "outcome": "skipped"} for name in PHASES],
                "assemblies": []}}
        result.start_worker()
        result.enqueue(result.adopt_checkpoint)
        return result

    @diagnostic
    def enqueue(self, operation, *args):
        self.tasks.put((operation, args))

    @staticmethod
    def identity(path):
        stat = path.stat()
        return stat.st_dev, stat.st_ino

    @diagnostic
    def reserve(self):
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        # Reserve both names exclusively. A collision never clobbers another run.
        for path in (self.receipt, self.pending):
            with path.open("x", encoding="utf-8"):
                pass
            self.owned[path] = self.identity(path)

    @diagnostic
    def read_checkpoint(self):
        if not self.resumed and self.pending not in self.owned:
            raise ValueError("checkpoint name was not reserved by this run")
        state = json.loads(self.pending.read_text(encoding="utf-8"))
        if state["run_id"] != self.run_id or state.get("owner") != self.state.get("owner"):
            raise ValueError("checkpoint belongs to another run")
        return state

    @diagnostic
    def adopt_checkpoint(self):
        if self.read_checkpoint() is not None:
            self.owned[self.pending] = self.identity(self.pending)

    @diagnostic
    def atomic_write(self, path, value):
        if self.resumed and path == self.pending and path not in self.owned:
            # Retry adoption if the child's first update beat the initial checkpoint.
            self.adopt_checkpoint()
        if path not in self.owned or self.identity(path) != self.owned[path]:
            raise ValueError("refusing to replace a file not owned by this run")
        temporary = path.with_suffix(path.suffix + "." + uuid.uuid4().hex + ".tmp")
        created = False
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                created = True
                stream.write(json.dumps(value, indent=2) + "\n")
            if self.identity(path) != self.owned[path]:
                raise ValueError("refusing to replace a file whose ownership changed")
            os.replace(temporary, path)
            self.owned[path] = self.identity(path)
            return True
        finally:
            if created:
                diagnostic(temporary.unlink)(missing_ok=True)

    @diagnostic
    def checkpoint(self):
        self.enqueue(self.atomic_write, self.pending, copy.deepcopy(self.state))

    @diagnostic
    def update(self, **fields):
        if not self.lock.acquire(blocking=False):
            return
        try:
            self.state["receipt"].update(fields)
            self.checkpoint()
        finally:
            self.lock.release()

    @diagnostic
    def begin(self, name, collection):
        if not self.lock.acquire(blocking=False):
            return
        try:
            entries = self.state["receipt"][collection]
            entry = next((row for row in entries if row["name"] == name), None)
            if entry is None:
                entry = {"name": name, "seconds": 0.0, "outcome": "skipped"}
                entries.append(entry)
            entry["outcome"] = "failed"
            self.state["active"][collection + "/" + name] = time.perf_counter()
            self.checkpoint()
        finally:
            self.lock.release()

    @diagnostic
    def end(self, name, collection, outcome):
        if not self.lock.acquire(blocking=False):
            return
        try:
            started = self.state["active"].pop(collection + "/" + name, None)
            if started is not None:
                entry = next(row for row in self.state["receipt"][collection] if row["name"] == name)
                entry.update(seconds=time.perf_counter() - started, outcome=outcome)
                self.checkpoint()
        finally:
            self.lock.release()

    @contextmanager
    def measure(self, name, collection="phases"):
        self.begin(name, collection)
        outcome = "failed"
        try:
            yield
            outcome = "succeeded"
        finally:
            self.end(name, collection, outcome)

    @diagnostic
    def finalize(self, error):
        state = diagnostic(self.read_checkpoint)() or self.state
        now = time.perf_counter()
        receipt = state["receipt"]
        for key, started in state["active"].items():
            collection, name = key.split("/", 1)
            entry = next(row for row in receipt[collection] if row["name"] == name)
            entry.update(seconds=now - started, outcome="failed")
        if error is not None:
            receipt.update(outcome="failed", error=receipt["error"] or short_error(error))
        receipt.update(finished_at=utc_now(), seconds=now - state["started"])
        receipt["assemblies"].sort(key=lambda row: row["name"])
        saved = self.atomic_write(self.receipt, receipt)
        # The child may have replaced the owned checkpoint during capture.
        if diagnostic(self.read_checkpoint)() is not None:
            diagnostic(self.pending.unlink)()
        if self.pending in self.owned:
            for temporary in self.pending.parent.glob(self.pending.name + ".*.tmp"):
                diagnostic(temporary.unlink)(missing_ok=True)
        table = [f"{'phase':<26} {'seconds':>10}  outcome"]
        for row in receipt["phases"]:
            table.append(f"{row['name']:<26} {row['seconds']:>10.3f}  {row['outcome']}")
        table.append(f"{'total':<26} {receipt['seconds']:>10.3f}  {receipt['outcome']}")
        self.reports.append(emit("\n".join(table)))
        if saved and self.announce:
            self.reports.append(emit(f"CAPTURE_TIMING_RECEIPT={self.receipt}", sys.stdout))

    @diagnostic
    def drain(self):
        flushed = threading.Event()
        self.tasks.put((flushed.set, ()))
        # Only shutdown waits, with the same finite budget as CLI error reporting.
        if not flushed.wait(ERROR_WRITE_SECONDS):
            emit("Warning: capture timing diagnostic flush exceeded its reporting budget")

    @diagnostic
    def finish(self, error=None):
        self.enqueue(self.finalize, error)
        self.tasks.put((None, ()))
        deadline = time.perf_counter() + ERROR_WRITE_SECONDS
        self.worker.join(ERROR_WRITE_SECONDS)
        for reporter in self.reports:
            if reporter:
                reporter.join(max(0, deadline - time.perf_counter()))
        if self.worker.is_alive():
            emit("Warning: capture timing diagnostic flush exceeded its reporting budget")


def supervise_capture(args, timeout):
    from processes import run_process
    parser = timing_parser()
    parser.add_argument("--output", default="")
    options, _ = parser.parse_known_args(args)
    timing = Timing(options.output, options.timing_receipt)
    timing.announce = True
    error = None
    try:
        environment = dict(os.environ, HUMANHOST_CAPTURE_CHILD="1", HUMANHOST_CAPTURE_TIMING=str(timing.pending),
                           HUMANHOST_CAPTURE_TIMING_STATE=json.dumps(timing.state))
        return run_process(args, timeout=timeout, env=environment, forward=True)
    except BaseException as exc:
        error = exc
        raise
    finally:
        timing.finish(error)


def cli_error(error):
    reporter = emit(str(error))
    if reporter:
        diagnostic(reporter.join)(ERROR_WRITE_SECONDS)
    # Neither diagnostic workers nor blocked streams may delay CLI termination.
    os._exit(1)


if __name__ == "__main__":
    try:
        supervise_capture(sys.argv[2:], float(sys.argv[1]))
    except Exception as exc:
        cli_error(exc)
    os._exit(0)
