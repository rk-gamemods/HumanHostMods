"""Dependency-free checks: py -3 tools/game_catalog/test_timing.py"""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import refresh
from timing import Timing, RUNS, PHASES, supervise_capture


class TimingTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="timing-test-", dir=RUNS)
        self.directory = Path(self.temp.name)
        self.root = patch("timing.RUNS", self.directory)
        self.root.start()
        self.messages = []
        self.reporting = patch("timing.emit", side_effect=lambda message, stream=None: self.messages.append(message))
        self.reporting.start()

    def tearDown(self):
        self.reporting.stop()
        self.root.stop()
        self.temp.cleanup()

    def timer(self):
        return Timing("synthetic snapshot")

    def test_unwritable_directory_preserves_original_process_failure_and_timeout(self):
        for original in (RuntimeError("original process failed"), RuntimeError("original deadline exceeded")):
            with self.subTest(error=original), patch("timing.Path.mkdir", side_effect=PermissionError("unwritable receipt directory")), \
                    patch("processes.run_process", side_effect=original):
                with self.assertRaises(RuntimeError) as caught:
                    supervise_capture(["python", "synthetic.py"], 2)
                self.assertIs(caught.exception, original)
        self.assertTrue(any(message.startswith("Warning:") and "unwritable" in message for message in self.messages))
        self.assertTrue(all("\n" not in message for message in self.messages if message.startswith("Warning:")))

    def test_cleanup_checkpoint_failure_still_recovers_and_releases_snapshot(self):
        timer = self.timer()
        snapshot = Mock()
        snapshot.__enter__ = Mock(return_value=snapshot)
        snapshot.__exit__ = Mock()
        original = RuntimeError("original capture failure")
        with patch("snapshot.Snapshot", return_value=snapshot), patch.object(timer, "checkpoint", side_effect=OSError("cleanup checkpoint failed")):
            with self.assertRaises(RuntimeError) as caught:
                with refresh.timed_snapshot(Path("synthetic"), False, timer):
                    raise original
            timer.drain()
        self.assertIs(caught.exception, original)
        snapshot.__exit__.assert_called_once()
        self.assertIs(snapshot.__exit__.call_args.args[1], original)
        timer.finish(original)
        self.assertTrue(any("cleanup checkpoint failed" in message for message in self.messages))

    def test_failed_claim_write_is_cleaned_and_capture_continues_without_checkpoint(self):
        opened = Path.open
        @contextmanager
        def broken_claim(stream):
            with stream:
                yield SimpleNamespace(write=Mock(side_effect=FileExistsError("claim write failed")))
        def open_claim(path, *args, **kwargs):
            stream = opened(path, *args, **kwargs)
            return broken_claim(stream) if path.suffix == ".claim" else stream
        def child(args, *, env, **kwargs):
            self.assertEqual(env["HUMANHOST_CAPTURE_TIMING"], "")
            with patch.dict(os.environ, env):
                timer = Timing.resume(env["HUMANHOST_CAPTURE_TIMING"])
            timer.update(outcome="succeeded")
            with timer.measure("cleanup"):
                pass
            timer.finish()
            return 0
        with patch("timing.Path.open", autospec=True, side_effect=open_claim), patch("processes.run_process", side_effect=child):
            self.assertEqual(supervise_capture(["python", "synthetic.py"], 2), 0)
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertTrue(any("claim write failed" in message for message in self.messages))

    def test_output_metadata_cannot_choose_receipt_directory(self):
        output = self.directory / "snapshot"
        expected = SimpleNamespace(returncode=0)
        with patch("processes.run_process", return_value=expected):
            result = supervise_capture(["python", "synthetic.py", "--output", str(output)], 2)
        self.assertIs(result, expected)
        receipt, = self.directory.glob("capture-*.json")
        self.assertEqual(json.loads(receipt.read_text())["output_path"], str(output))
        self.assertFalse(output.exists())

    def test_timing_source_changes_do_not_change_provenance_hashes(self):
        script_root = self.directory / "tools" / "game_catalog"
        script_root.mkdir(parents=True)
        for path in (script_root / "refresh.py", script_root / "timing.py", script_root / "requirements.txt",
                     script_root.parent / "Decompile-GameCode.ps1", script_root.parent / "Read-GameBundle.ps1"):
            path.write_text("synthetic tool")
        def hashes():
            return {path.name: refresh.tool_digest(path) for path in refresh.generator_tools(script_root)}
        before = hashes()
        self.assertNotIn("timing.py", before)
        (script_root / "timing.py").write_text("different diagnostic code")
        self.assertEqual(hashes(), before)
        (script_root / "refresh.py").write_text("different generator code")
        self.assertNotEqual(hashes(), before)

    def test_two_runs_in_same_second_have_exclusive_random_names(self):
        fixed = datetime(2026, 10, 3, tzinfo=timezone.utc)
        with patch("timing.datetime") as clock:
            clock.now.return_value = fixed
            first, second = self.timer(), self.timer()
            first.drain()
            second.drain()
        self.assertNotEqual(first.receipt, second.receipt)
        for timer in (first, second):
            self.assertRegex(timer.receipt.name, r"^capture-20261003T000000Z-\d+-[0-9a-f]{16}\.json$")
            timer.update(outcome="succeeded")
            timer.finish()
            self.assertEqual(json.loads(timer.receipt.read_text())["outcome"], "succeeded")

    def test_existing_receipt_is_never_overwritten_even_on_id_collision(self):
        stem = "capture-20261003T000000Z-123-" + "a" * 16
        with patch("timing.capture_name", side_effect=[stem, stem, stem[:-16] + "b" * 16]):
            first = self.timer()
            first.update(outcome="succeeded")
            first.finish()
            original = first.receipt.read_bytes()
            second = self.timer()
            second.finish(RuntimeError("second failed"))
        self.assertNotEqual(first.receipt, second.receipt)
        self.assertEqual(first.receipt.read_bytes(), original)
        self.assertEqual(json.loads(second.receipt.read_text())["outcome"], "failed")

    def test_any_existing_stem_is_preserved_and_child_gets_only_reserved_checkpoint(self):
        for suffix in (".claim", ".pending", ".json", ".pending.orphan.tmp"):
            with self.subTest(suffix=suffix):
                stem = "capture-20261003T000000Z-123-" + "c" * 16
                orphan = self.directory / (stem + suffix)
                orphan.write_text("unowned original")
                fresh = stem[:-16] + os.urandom(8).hex()
                def child(args, *, env, **kwargs):
                    pending = Path(env["HUMANHOST_CAPTURE_TIMING"])
                    self.assertEqual(pending, self.directory / (fresh + ".pending"))
                    state = json.loads(env["HUMANHOST_CAPTURE_TIMING_STATE"])
                    self.assertEqual(pending.with_suffix(".claim").read_text(), state["owner"])
                    self.assertEqual(json.loads(pending.read_text())["owner"], state["owner"])
                    with patch.dict(os.environ, env):
                        timer = Timing.resume(str(pending))
                    timer.update(outcome="reused")
                    timer.drain()
                    timer.finish()
                    return 0
                with patch("timing.capture_name", side_effect=[stem, fresh]), patch("processes.run_process", side_effect=child):
                    self.assertEqual(supervise_capture(["python", "synthetic.py"], 2), 0)
                self.assertEqual(orphan.read_text(), "unowned original")
                self.assertEqual(json.loads((self.directory / (fresh + ".json")).read_text())["outcome"], "reused")
                orphan.unlink()

    def test_checkpoint_read_and_replace_failures_do_not_change_success(self):
        for operation in ("timing.Path.read_text", "timing.os.replace"):
            with self.subTest(operation=operation), patch(operation, side_effect=OSError("diagnostic I/O failed")), \
                    patch("processes.run_process", return_value=0):
                self.assertEqual(supervise_capture(["python", "synthetic.py"], 2), 0)
            if operation == "timing.Path.read_text":
                receipt = next(self.directory.glob("capture-*.json"))
                value = json.loads(receipt.read_text())
                self.assertEqual(value["outcome"], "succeeded")
                self.assertIsNone(value["error"])
        self.assertEqual(list(self.directory.glob("*.claim")), [])

    def test_claim_reservation_does_not_expose_json_and_is_cleaned_on_failure(self):
        timer = self.timer()
        timer.drain()
        self.assertTrue(timer.claim.exists())
        self.assertFalse(timer.receipt.exists())
        with patch("timing.os.replace", side_effect=OSError("publication failed")):
            timer.finish(outcome="succeeded")
        self.assertFalse(timer.receipt.exists())
        self.assertFalse(timer.claim.exists())
        self.assertFalse(timer.pending.exists())

    def test_receipt_is_invisible_until_atomic_publication(self):
        entered, release = threading.Event(), threading.Event()
        timer = self.timer()
        timer.update(outcome="succeeded")
        timer.drain()
        replace = os.replace
        def delayed(source, destination):
            if destination == timer.receipt:
                entered.set()
                release.wait()
            return replace(source, destination)
        try:
            with patch("timing.os.replace", side_effect=delayed):
                timer.finish(outcome="succeeded")
                self.assertTrue(entered.wait(2))
                self.assertFalse(timer.receipt.exists())
                release.set()
                timer.worker.join(2)
        finally:
            release.set()
            timer.worker.join(2)
        self.assertEqual(json.loads(timer.receipt.read_text())["outcome"], "succeeded")
        self.assertFalse(timer.claim.exists())

    def test_concurrent_assembly_updates_are_serialized_without_drops(self):
        timer = self.timer()
        timer.drain()
        names = [f"assembly-{index}.dll" for index in range(64)]
        timer.update(assemblies=[{"name": name, "seconds": 0.0, "outcome": "skipped"} for name in names])
        def assembly(name):
            with timer.measure(name, "assemblies"):
                pass
        with patch.object(timer, "checkpoint", side_effect=lambda: time.sleep(0.001)):
            with ThreadPoolExecutor(max_workers=16) as executor:
                list(executor.map(assembly, names))
            timer.drain()
        timer.enqueue(timer.checkpoint)
        timer.finish(outcome="succeeded")
        value = json.loads(timer.receipt.read_text())
        self.assertEqual({row["name"] for row in value["assemblies"]}, set(names))
        self.assertTrue(all(row["outcome"] == "succeeded" for row in value["assemblies"]))
        self.assertEqual(timer.state["active"], {})

    def test_blocked_storage_cannot_block_capture_or_change_error(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(*args):
            entered.set()
            release.wait()
        timer = None
        try:
            with patch.object(Timing, "atomic_write", side_effect=blocked):
                timer = self.timer()
                self.assertTrue(entered.wait(2))
                started = time.perf_counter()
                with timer.measure("cleanup"):
                    timer.update(outcome="succeeded")
                self.assertLess(time.perf_counter() - started, 0.2)
                timer.finish()
                self.assertLess(time.perf_counter() - started, 1.5)
        finally:
            release.set()
            if timer:
                timer.worker.join(2)
        self.assertFalse(timer.worker.is_alive())

    def test_supervisor_success_reuse_failure_and_timeout(self):
        module = Path(__file__).with_name("timing.py")
        setup = ("import os,sys,time; "
                 f"sys.path.insert(0, {str(module.parent)!r}); "
                 "from timing import Timing; t=Timing.resume(os.environ['HUMANHOST_CAPTURE_TIMING']); ")
        for outcome in ("succeeded", "reused", "failed", "timeout"):
            with self.subTest(outcome=outcome):
                if outcome == "timeout":
                    action = "phase=t.measure('catalog decode'); phase.__enter__(); time.sleep(60)"
                elif outcome == "failed":
                    action = "t.update(outcome='failed', error='synthetic failure'); t.drain(); sys.exit(7)"
                else:
                    action = f"t.update(outcome={outcome!r}); t.drain()"
                # Redirect only the module constant, keeping receipt paths out of CLI arguments.
                harness = (f"import sys,os; from pathlib import Path; sys.path.insert(0, {str(module.parent)!r}); "
                           f"import timing; timing.RUNS=Path({str(self.directory)!r})\n"
                           "try:\n"
                           f" timing.supervise_capture({[sys.executable, '-c', setup + action, '--output', 'synthetic snapshot']!r}, 2)\n"
                           "except Exception as exc:\n timing.cli_error(exc)\n"
                           "os._exit(0)\n")
                result = subprocess.run([sys.executable, "-c", harness],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1 if outcome in {"failed", "timeout"} else 0, result.stderr)
                marker = next(line for line in result.stdout.splitlines() if line.startswith("CAPTURE_TIMING_RECEIPT="))
                receipt = Path(marker.split("=", 1)[1])
                value = json.loads(receipt.read_text())
                self.assertEqual(value["outcome"], "failed" if outcome == "timeout" else outcome)
                self.assertEqual([row["name"] for row in value["phases"]], list(PHASES))
                self.assertIn("total", result.stderr)
                self.assertFalse(receipt.with_suffix(".pending").exists())
                if outcome == "timeout":
                    self.assertIn("deadline exceeded", value["error"])
                    self.assertEqual(value["phases"][1]["outcome"], "failed")
                    self.assertGreater(value["phases"][1]["seconds"], 0)
                    self.assertEqual([row["outcome"] for row in value["phases"]],
                                     ["skipped", "failed", "skipped", "skipped", "skipped"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
