"""Operator timing kept outside generated snapshot identities."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time

PHASES = ("input hashing/reuse check", "catalog decode", "decompile", "Git promotion", "cleanup")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def short_error(error):
    return (str(error).splitlines() or [type(error).__name__])[0][:300]


class Timing:
    def __init__(self, output="", receipt=None):
        root = Path(__file__).resolve().parents[2]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.receipt = Path(receipt) if receipt else root / ".local" / "runs" / f"capture-{stamp}-{os.getpid()}.json"
        self.pending = self.receipt.with_suffix(".pending")
        self.lock = threading.Lock()
        self.state = {"started": time.perf_counter(), "active": {}, "receipt": {
            "schema": "humanhost.capture-timing.v1", "started_at": utc_now(), "finished_at": None,
            "seconds": 0.0, "outcome": "failed", "error": None, "output_path": str(output),
            "output_commit": None, "game": None,
            "phases": [{"name": name, "seconds": 0.0, "outcome": "skipped"} for name in PHASES],
            "assemblies": []}}
        self.checkpoint()

    @classmethod
    def resume(cls, pending):
        result = cls.__new__(cls)
        result.pending = Path(pending)
        result.receipt = result.pending.with_suffix(".json")
        result.lock = threading.Lock()
        result.state = json.loads(result.pending.read_text(encoding="utf-8"))
        return result

    def atomic_write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def checkpoint(self):
        self.atomic_write(self.pending, self.state)

    def update(self, **fields):
        with self.lock:
            self.state["receipt"].update(fields)
            self.checkpoint()

    @contextmanager
    def measure(self, name, collection="phases"):
        key = collection + "/" + name
        with self.lock:
            entries = self.state["receipt"][collection]
            entry = next((row for row in entries if row["name"] == name), None)
            if entry is None:
                entry = {"name": name, "seconds": 0.0, "outcome": "skipped"}
                entries.append(entry)
            entry["outcome"] = "failed"
            self.state["active"][key] = time.perf_counter()
            self.checkpoint()
        outcome = "failed"
        try:
            yield
            outcome = "succeeded"
        finally:
            with self.lock:
                entry.update(seconds=time.perf_counter() - self.state["active"].pop(key), outcome=outcome)
                self.checkpoint()

    def finish(self, error=None):
        # A supervisor can finalize the last checkpoint after killing a stalled child.
        self.state = json.loads(self.pending.read_text(encoding="utf-8"))
        now = time.perf_counter()
        receipt = self.state["receipt"]
        for key, started in self.state["active"].items():
            collection, name = key.split("/", 1)
            entry = next(row for row in receipt[collection] if row["name"] == name)
            entry.update(seconds=now - started, outcome="failed")
        if error is not None:
            receipt.update(outcome="failed", error=receipt["error"] or short_error(error))
        receipt.update(finished_at=utc_now(), seconds=now - self.state["started"])
        receipt["assemblies"].sort(key=lambda row: row["name"])
        self.atomic_write(self.receipt, receipt)
        self.pending.unlink()
        self.pending.with_suffix(".pending.tmp").unlink(missing_ok=True)
        table = [f"{'phase':<26} {'seconds':>10}  outcome"]
        for row in receipt["phases"]:
            table.append(f"{row['name']:<26} {row['seconds']:>10.3f}  {row['outcome']}")
        table.append(f"{'total':<26} {receipt['seconds']:>10.3f}  {receipt['outcome']}")
        # Preserve the process runner's bounded reporting when a consumer stalls.
        from processes import ERROR_WRITE_SECONDS
        def report():
            try:
                print("\n".join(table), file=sys.stderr, flush=True)
            except OSError:
                pass
        reporter = threading.Thread(target=report, daemon=True)
        reporter.start()
        reporter.join(ERROR_WRITE_SECONDS)
        if reporter.is_alive():
            raise RuntimeError("Capture timing receipt saved; stderr table output blocked")


def supervise_capture(args, timeout):
    from processes import run_process
    def option(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    timing = Timing(option("--output", ""), option("--timing-receipt"))
    error = None
    try:
        environment = dict(os.environ, HUMANHOST_CAPTURE_CHILD="1", HUMANHOST_CAPTURE_TIMING=str(timing.pending))
        return run_process(args, timeout=timeout, env=environment, forward=True)
    except BaseException as exc:
        error = exc
        raise
    finally:
        timing.finish(error)


if __name__ == "__main__":
    from processes import ERROR_WRITE_SECONDS
    try:
        supervise_capture(sys.argv[2:], float(sys.argv[1]))
    except RuntimeError as exc:
        def report(message):
            try:
                print(message, file=sys.stderr, flush=True)
            except OSError:
                pass
        reporter = threading.Thread(target=report, args=(str(exc),), daemon=True)
        reporter.start()
        reporter.join(ERROR_WRITE_SECONDS)
        # Bypass stream finalization, which can wait for blocked daemon writers.
        os._exit(1)
