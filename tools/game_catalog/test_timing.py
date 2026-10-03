"""Dependency-free checks: py -3 tools/game_catalog/test_timing.py"""
from datetime import datetime, timezone
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
from timing import Timing, RUNS, PHASES, supervise_capture, timing_parser


class TimingTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="timing-test-", dir=RUNS)
        self.directory = Path(self.temp.name)
        self.hint = self.directory / "requested.json"
        self.messages = []
        self.reporting = patch("timing.emit", side_effect=lambda message, stream=None: self.messages.append(message))
        self.reporting.start()

    def tearDown(self):
        self.reporting.stop()
        self.temp.cleanup()

    def timer(self):
        return Timing("synthetic snapshot", self.hint)

    def test_unwritable_directory_preserves_original_process_failure_and_timeout(self):
        for original in (RuntimeError("original process failed"), RuntimeError("original deadline exceeded")):
            with self.subTest(error=original), patch("timing.Path.mkdir", side_effect=PermissionError("unwritable receipt directory")), \
                    patch("processes.run_process", side_effect=original):
                with self.assertRaises(RuntimeError) as caught:
                    supervise_capture(["python", "synthetic.py", "--timing-receipt", str(self.hint)], 2)
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
        self.assertIs(caught.exception, original)
        snapshot.__exit__.assert_called_once()
        self.assertIs(snapshot.__exit__.call_args.args[1], original)
        timer.finish(original)
        self.assertTrue(any("cleanup checkpoint failed" in message for message in self.messages))

    def test_snapshot_output_receipt_is_rejected_before_writes(self):
        output = RUNS.parent / "synthetic snapshot"
        with patch("timing.Path.open") as opened, self.assertRaisesRegex(ValueError, "must resolve inside"):
            Timing(output, output / "capture.json")
        opened.assert_not_called()

    def test_snapshot_output_under_runs_still_cannot_contain_receipts(self):
        output = self.directory / "snapshot"
        with patch("timing.Path.open") as opened, self.assertRaisesRegex(ValueError, "inside snapshot output"):
            Timing(output, output / "capture.json")
        opened.assert_not_called()

    def test_direct_main_rejects_snapshot_receipt_before_any_write(self):
        output = self.directory / "snapshot"
        args = ["refresh.py", "--game", "synthetic game", "--output", str(output),
                f"--timing-receipt={output / 'capture.json'}"]
        with patch("refresh.sys.argv", args), patch("timing.Path.open") as opened, \
                self.assertRaisesRegex(ValueError, "inside snapshot output"):
            refresh.main()
        opened.assert_not_called()

    def test_shared_parser_accepts_equals_and_separate_receipt_arguments(self):
        for args in (["--timing-receipt", str(self.hint)], [f"--timing-receipt={self.hint}"]):
            self.assertEqual(timing_parser().parse_args(args).timing_receipt, self.hint)
        expected = SimpleNamespace(returncode=0)
        with patch("processes.run_process", return_value=expected):
            result = supervise_capture(["python", "synthetic.py", f"--timing-receipt={self.hint}"], 2)
        self.assertIs(result, expected)
        self.assertEqual(len(list(self.directory.glob("capture-*.json"))), 1)

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
        self.assertNotEqual(first.receipt, second.receipt)
        for timer in (first, second):
            self.assertRegex(timer.receipt.name, r"^capture-20261003T000000Z-\d+-[0-9a-f]{8}\.json$")
            timer.update(outcome="succeeded")
            timer.finish()
            self.assertEqual(json.loads(timer.receipt.read_text())["outcome"], "succeeded")

    def test_existing_receipt_is_never_overwritten_even_on_id_collision(self):
        fixed = datetime(2026, 10, 3, tzinfo=timezone.utc)
        with patch("timing.datetime") as clock, patch("timing.uuid.uuid4", return_value=SimpleNamespace(hex="a" * 32)):
            clock.now.return_value = fixed
            first = self.timer()
            first.update(outcome="succeeded")
            first.finish()
            original = first.receipt.read_bytes()
            second = self.timer()
            second.finish(RuntimeError("second failed"))
        self.assertEqual(second.receipt.read_bytes(), original)

    def test_colliding_child_cannot_adopt_another_runs_checkpoint(self):
        fixed = datetime(2026, 10, 3, tzinfo=timezone.utc)
        with patch("timing.datetime") as clock, patch("timing.uuid.uuid4", return_value=SimpleNamespace(hex="b" * 32)):
            clock.now.return_value = fixed
            first = self.timer()
            first.drain()
            original = first.pending.read_bytes()
            second = self.timer()
            second.drain()
            with patch.dict(os.environ, HUMANHOST_CAPTURE_TIMING_STATE=json.dumps(second.state)):
                child = Timing.resume(second.pending)
            child.update(outcome="reused")
            child.drain()
            self.assertEqual(first.pending.read_bytes(), original)
            child.finish()
            second.finish()
            self.assertEqual(first.pending.read_bytes(), original)
            first.finish()

    def test_checkpoint_read_and_replace_failures_do_not_change_success(self):
        for operation in ("timing.Path.read_text", "timing.os.replace"):
            with self.subTest(operation=operation), patch(operation, side_effect=OSError("diagnostic I/O failed")), \
                    patch("processes.run_process", return_value=0):
                self.assertEqual(supervise_capture(["python", "synthetic.py", "--timing-receipt", str(self.hint)], 2), 0)

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

    def test_explicit_cli_success_reuse_failure_and_timeout(self):
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
                result = subprocess.run([sys.executable, str(module), "2", sys.executable, "-c", setup + action,
                                         "--output", "synthetic snapshot", f"--timing-receipt={self.hint}"],
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
