"""Best-effort operator diagnostics, outside generated snapshot identities."""
import argparse
from contextlib import contextmanager
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


def timing_options(args=None):
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--output", default="")
    return parser.parse_known_args(args)[0]


def capture_name():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"capture-{stamp}-{os.getpid()}-{os.urandom(8).hex()}"


class Timing:
    def __init__(self, output=""):
        self.receipt = self.pending = self.claim = None
        self.state = {"owner": os.urandom(16).hex(), "started": time.perf_counter(), "active": {}, "receipt": {
            "schema": "humanhost.capture-timing.v1", "started_at": utc_now(), "finished_at": None,
            "seconds": 0.0, "outcome": "failed", "error": None, "output_path": str(output),
            "output_commit": None, "game": None,
            "phases": [{"name": name, "seconds": 0.0, "outcome": "skipped"} for name in PHASES],
            "assemblies": []}}
        self.seed = json.dumps(self.state)
        self.start_worker()
        self.enqueue(self.reserve)

    @diagnostic
    def start_worker(self):
        self.tasks, self.reports, self.claim_owned, self.writable = queue.SimpleQueue(), [], False, False
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
        result = cls.__new__(cls)
        result.pending = Path(pending) if pending else None
        result.receipt = result.pending.with_suffix(".json") if pending else None
        result.claim = result.pending.with_suffix(".claim") if pending else None
        result.state = json.loads(os.environ["HUMANHOST_CAPTURE_TIMING_STATE"])
        result.start_worker()
        return result

    @diagnostic
    def enqueue(self, operation, *args):
        self.tasks.put((operation, args))

    def reserve(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        for _ in range(32):
            stem = capture_name()
            if any(RUNS.glob(stem + ".*")):
                continue
            self.receipt = RUNS / (stem + ".json")
            self.pending, self.claim = self.receipt.with_suffix(".pending"), self.receipt.with_suffix(".claim")
            try:
                stream = self.claim.open("x", encoding="utf-8")
            except FileExistsError:
                continue
            self.claim_owned = True
            with stream as claimed:
                claimed.write(self.state["owner"])
            if any(path != self.claim for path in RUNS.glob(stem + ".*")):
                self.claim.unlink()
                self.claim_owned = False
                continue
            self.writable = True
            self.checkpoint()
            return
        raise RuntimeError("could not reserve a unique capture name")

    @diagnostic
    def child_checkpoint(self):
        if self.drain() and self.writable:
            return str(self.pending)

    def atomic_write(self, path, value):
        if not self.claim_owned and self.claim.read_text(encoding="utf-8") != self.state["owner"]:
            raise ValueError("claim belongs to another run")
        if path == self.receipt and (not self.claim_owned or path.exists()):
            raise ValueError("refusing to overwrite an existing receipt")
        temporary = path.with_suffix(path.suffix + "." + uuid.uuid4().hex + ".tmp")
        created = False
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                created = True
                stream.write(json.dumps(value, indent=2) + "\n")
            os.replace(temporary, path)
            return True
        finally:
            if created:
                diagnostic(temporary.unlink)(missing_ok=True)

    @diagnostic
    def checkpoint(self):
        if self.pending is not None:
            self.atomic_write(self.pending, self.state)

    def change(self, fields):
        self.state["receipt"].update(fields)
        self.checkpoint()

    def phase(self, name, collection, stamp, outcome):
        entries = self.state["receipt"][collection]
        entry = next((row for row in entries if row["name"] == name), None)
        if entry is None:
            entry = {"name": name, "seconds": 0.0, "outcome": "skipped"}
            entries.append(entry)
        key = collection + "/" + name
        if outcome is None:
            entry["outcome"] = "failed"
            self.state["active"][key] = stamp
        else:
            entry.update(seconds=stamp - self.state["active"].pop(key), outcome=outcome)
        self.checkpoint()

    def update(self, **fields):
        self.enqueue(self.change, fields)

    @contextmanager
    def measure(self, name, collection="phases"):
        self.enqueue(self.phase, name, collection, time.perf_counter(), None)
        outcome = "failed"
        try:
            yield
            outcome = "succeeded"
        finally:
            self.enqueue(self.phase, name, collection, time.perf_counter(), outcome)

    def read_checkpoint(self):
        state = json.loads(self.pending.read_text(encoding="utf-8"))
        if state["owner"] != self.state["owner"]:
            raise ValueError("checkpoint belongs to another run")
        return state

    @diagnostic
    def cleanup(self):
        if self.claim_owned:
            for path in (self.claim, self.pending) if self.writable else (self.claim,):
                diagnostic(path.unlink)(missing_ok=True)
            if self.writable:
                for path in self.receipt.parent.glob(self.receipt.stem + ".*.tmp"):
                    diagnostic(path.unlink)(missing_ok=True)

    def finalize(self, error, outcome, announce):
        try:
            state = (diagnostic(self.read_checkpoint)() if self.writable else None) or self.state
            receipt, now = state["receipt"], time.perf_counter()
            if error is not None:
                receipt.update(outcome="failed", error=receipt["error"] or short_error(error))
            elif outcome is not None:
                receipt.update(outcome="reused" if receipt["outcome"] == "reused" else outcome, error=None)
            for key, started in state["active"].items():
                collection, name = key.split("/", 1)
                entry = next(row for row in receipt[collection] if row["name"] == name)
                entry.update(seconds=now - started,
                             outcome="succeeded" if receipt["outcome"] in {"succeeded", "reused"} else "failed")
            receipt.update(finished_at=utc_now(), seconds=now - state["started"])
            receipt["assemblies"].sort(key=lambda row: row["name"])
            saved = self.writable and diagnostic(self.atomic_write)(self.receipt, receipt)
            table = [f"{'phase':<26} {'seconds':>10}  outcome"]
            table += [f"{row['name']:<26} {row['seconds']:>10.3f}  {row['outcome']}" for row in receipt["phases"]]
            table += [f"{'total':<26} {receipt['seconds']:>10.3f}  {receipt['outcome']}"]
            self.reports.append(emit("\n".join(table)))
            if saved and announce:
                self.reports.append(emit(f"CAPTURE_TIMING_RECEIPT={self.receipt}", sys.stdout))
        finally:
            self.cleanup()

    @diagnostic
    def drain(self):
        flushed = threading.Event()
        self.enqueue(flushed.set)
        if flushed.wait(ERROR_WRITE_SECONDS):
            return True
        emit("Warning: capture timing diagnostic flush exceeded its reporting budget")

    @diagnostic
    def finish(self, error=None, outcome=None, announce=False):
        self.enqueue(self.finalize, error, outcome, announce)
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
    options = timing_options(args)
    timing = Timing(options.output)
    error, outcome = None, "failed"
    try:
        environment = dict(os.environ, HUMANHOST_CAPTURE_CHILD="1", HUMANHOST_CAPTURE_TIMING=timing.child_checkpoint() or "",
                           HUMANHOST_CAPTURE_TIMING_STATE=timing.seed)
        result = run_process(args, timeout=timeout, env=environment, forward=True)
        outcome = "succeeded"
        return result
    except BaseException as exc:
        error = exc
        raise
    finally:
        timing.finish(error, outcome, announce=True)


def cli_error(error):
    reporter = emit(str(error))
    if reporter:
        diagnostic(reporter.join)(ERROR_WRITE_SECONDS)
    os._exit(1)


if __name__ == "__main__":
    try:
        supervise_capture(sys.argv[2:], float(sys.argv[1]))
    except Exception as exc:
        cli_error(exc)
    os._exit(0)
