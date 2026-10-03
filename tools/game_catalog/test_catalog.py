"""Run: py -3 tools/game_catalog/test_catalog.py --python-packages <isolated dependencies>"""
import argparse
import base64
import io
import json
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--python-packages")
options, remaining = parser.parse_known_args()
if options.python_packages:
    sys.path.insert(0, options.python_packages)

from addressables import decode, read_object
from bundles import Bundle, MemberStream
from catalog import Catalog, clean, source_key, rows
from snapshot import Snapshot, git
from refresh import steam_identity, input_paths, tool_digest, reusable_capture, inputs_stable, decompile
from processes import run_process
from schemas import normalize_generated
from game_version import capture as capture_version
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers.TypeTreeHelper import read_typetree
from UnityPy.streams import EndianBinaryReader


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hhmods-capture-process-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def alive(pid):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            status = Path(f"/proc/{pid}/stat")
            return not status.exists() or status.read_text().split(")", 1)[1].strip()[0] != "Z"
        except ProcessLookupError:
            return False

    def assert_dead(self, pid):
        deadline = time.monotonic() + 3
        while self.alive(pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(self.alive(pid), f"Capture left process {pid} running")

    def tree_child(self, pidfile, ending):
        return ("import os, subprocess, sys, time; from pathlib import Path; "
                "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                f"Path({str(pidfile)!r}).write_text(str(os.getpid())+' '+str(child.pid)); "
                "sys.stderr.write('discard-me'+'x'*5000+'reported stderr marker'); sys.stderr.flush(); " + ending)

    def test_deadline_kills_tree_and_reports_bounded_stderr(self):
        pidfile = self.root / "deadline-pids"
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "deadline exceeded .*deadline 3s.*") as caught:
            run_process([sys.executable, "-c", self.tree_child(pidfile, "time.sleep(60)")], timeout=3)
        self.assertLess(time.monotonic() - started, 8)
        self.assertIn(Path(sys.executable).name, str(caught.exception))
        tail = str(caught.exception).split("stderr tail:\n", 1)[1]
        self.assertTrue(tail.endswith("reported stderr marker"))
        self.assertLessEqual(len(tail.encode()), 4096)
        self.assertNotIn("discard-me", tail)
        for pid in map(int, pidfile.read_text().split()):
            self.assert_dead(pid)

    def test_failed_parent_kills_its_surviving_grandchild(self):
        pidfile = self.root / "failure-pids"
        with self.assertRaisesRegex(RuntimeError, "exit 9 .*deadline 5s.*"):
            run_process([sys.executable, "-c", self.tree_child(pidfile, "sys.exit(9)")], timeout=5)
        for pid in map(int, pidfile.read_text().split()):
            self.assert_dead(pid)

    def test_whole_capture_deadline_kills_nested_helper_groups(self):
        pidfile = self.root / "nested-pids"
        parentfile = self.root / "supervisor-pid"
        inner = ("import os,subprocess,sys,time; from pathlib import Path; "
                 "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                 f"Path({str(pidfile)!r}).write_text(str(os.getpid())+' '+str(child.pid)); time.sleep(60)")
        code = ("import os,sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(Path(__file__).parent)!r}); from processes import run_process; "
                f"Path({str(parentfile)!r}).write_text(str(os.getpid())); "
                f"run_process([sys.executable,'-c',{inner!r}],timeout=60)")
        with self.assertRaisesRegex(RuntimeError, "deadline exceeded"):
            run_process([sys.executable, "-c", code], timeout=3, forward=True)
        for path in (parentfile, pidfile):
            for pid in map(int, path.read_text().split()):
                self.assert_dead(pid)

    def test_concurrent_pipe_draining_preserves_binary_stdout(self):
        result = run_process([sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'a'*1048576); "
                              "sys.stderr.buffer.write(b'b'*1048576)"], timeout=5, text=False)
        self.assertEqual(result.stdout, b"a" * 1048576)
        self.assertEqual(result.stderr, b"b" * 4096)

    def test_assembly_failure_cancels_pending_and_running_siblings(self):
        managed = self.root / "Human Host_Data" / "Managed"
        managed.mkdir(parents=True)
        for name in ["a-fail", "b-sibling", *[f"z-pending-{i}" for i in range(12)]]:
            (managed / (name + ".dll")).write_bytes(b"synthetic assembly")
        stage = self.root / "stage"
        stage.mkdir()
        sibling = self.root / "b-sibling.pids"
        cancellations = []
        futures = []
        from concurrent.futures import ThreadPoolExecutor
        class RecordingExecutor(ThreadPoolExecutor):
            def submit(self, *args, **kwargs):
                future = super().submit(*args, **kwargs)
                futures.append(future)
                return future
        def standin(args, **kwargs):
            name = Path(args[-1]).stem
            cancellations.append(kwargs["cancel"])
            if name == "a-fail":
                code = ("import sys,time; from pathlib import Path\n"
                        f"while not Path({str(sibling)!r}).exists(): time.sleep(0.01)\n"
                        "sys.stderr.write('assembly stand-in failed'); sys.exit(7)")
            else:
                code = self.tree_child(self.root / (name + ".pids"), "time.sleep(60)")
            return run_process([sys.executable, "-c", code], timeout=5, cancel=kwargs["cancel"])
        started = time.monotonic()
        with patch("refresh.run_process", side_effect=standin), patch("refresh.concurrent.futures.ThreadPoolExecutor", RecordingExecutor):
            with self.assertRaisesRegex(RuntimeError, "assembly stand-in failed"):
                decompile(self.root, stage, None, 2)
        self.assertLess(time.monotonic() - started, 5)
        self.assertTrue(cancellations and all(event.is_set() for event in cancellations))
        self.assertTrue(any(future.cancelled() for future in futures))
        self.assertTrue(all(future.done() for future in futures))
        self.assertTrue(sibling.exists())
        for pidfile in self.root.glob("*.pids"):
            for pid in map(int, pidfile.read_text().split()):
                self.assert_dead(pid)


class BundleTests(unittest.TestCase):
    def test_lazy_uncompressed_member_skips_resource_payload(self):
        payload = b"metadata" + b"x" * 1000000
        info = b"\0" * 16 + struct.pack(">iIIHi", 1, len(payload), len(payload), 0, 2)
        info += struct.pack(">qqI", 0, 8, 0) + b"CAB-test\0"
        info += struct.pack(">qqI", 8, 1000000, 0) + b"CAB-test.resS\0"
        prefix = b"UnityFS\0" + struct.pack(">I", 7) + b"5.x.x\0" + b"2022.3.62f3\0"
        header_size = len(prefix) + 20
        header_size += (-header_size) % 16
        header = prefix + struct.pack(">qIII", header_size + len(info) + len(payload), len(info), len(info), 0)
        header += b"\0" * (header_size - len(header))
        stream = io.BytesIO(header + info + payload)
        bundle = Bundle(stream)
        member = MemberStream(bundle, 0, 8)
        self.assertEqual(member.read(), b"metadata")
        self.assertLess(stream.tell(), 1000)
        self.assertEqual(len(bundle.cache), 0)
        member.seek(-4, 2)
        self.assertEqual(member.read(), b"data")

    def test_hash_names_do_not_rename_catalog_source(self):
        self.assertEqual(source_key("scene_" + "a" * 32 + ".bundle"), "scene.bundle")


class DataTests(unittest.TestCase):
    def test_large_component_member_index_preserves_canonical_bytes_and_all_names(self):
        import hashlib
        value = {"id": "a#1", "script": {"class": "Fixture"},
                 "fields": {"日本語": 4, "geometry": [{"x": 1, "y": 2}] * 65000,
                            "future": {"value": 7}}, "references": []}
        expected = (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            locations = {}
            rows(path, [value], locations)
            data = path.read_bytes()
            self.assertEqual(expected, data)
            location = locations["a#1"]
            self.assertEqual(hashlib.sha256(data).hexdigest(), location["sha256"])
            members = location["members"]
            self.assertEqual(set(value), set(members))
            self.assertEqual(set(value["fields"]), set(members["fields"]))
            for key, size in members["fields"].items():
                self.assertEqual(len(json.dumps(value["fields"][key], ensure_ascii=False, sort_keys=True).encode()), size)

    def test_component_locations_are_byte_exact_without_duplicate_records(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            values = [{"id": "a#1", "name": "日本語", "script": {"class": "Fixture"}},
                      {"id": "a#2", "name": "engine object"},
                      {"id": "a#3", "script": {"class": "Other"}, "fields": {"x": 4}}]
            locations = {}
            rows(path, values, locations)
            self.assertEqual({"a#1", "a#3"}, set(locations))
            with path.open("rb") as stream:
                for value in [values[0], values[2]]:
                    location = locations[value["id"]]
                    stream.seek(location["offset"])
                    data = stream.read(location["bytes"])
                    self.assertEqual(value, json.loads(data))
                    self.assertEqual(location["sha256"], hashlib.sha256(data).hexdigest())
            self.assertNotIn(b"\r", path.read_bytes())

    def test_capture_reuse_requires_content_build_tool_and_full_scope_match(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            catalog = output / "Catalog"
            catalog.mkdir()
            steam, inputs, generator = {"build_id": "1"}, [{"path": "game.dll", "sha256": "a"}], {"tools": {"parser": "a"}}
            for name, data in [("steam-build.json", steam), ("generator.json", generator), ("coverage.json", {"decode_failures": []}),
                               ("game-version.json", {"schema": 1, "status": "unknown", "version": None, "evidence": []})]:
                (catalog / name).write_text(json.dumps(data))
            (catalog / "inputs.jsonl").write_text(json.dumps(inputs[0]) + "\n")
            (catalog / "assemblies.jsonl").write_text(json.dumps({"reason": "selected"}) + "\n")
            self.assertTrue(reusable_capture(output, steam, inputs, generator))
            self.assertFalse(reusable_capture(output, {"build_id": "2"}, inputs, generator))
            self.assertFalse(reusable_capture(output, steam, [{"path": "game.dll", "sha256": "b"}], generator))
            self.assertFalse(reusable_capture(output, steam, inputs, {"tools": {"parser": "b"}}))
            (catalog / "assemblies.jsonl").write_text(json.dumps({"reason": "explicit assembly subset"}) + "\n")
            self.assertFalse(reusable_capture(output, steam, inputs, generator))

    def test_application_version_selects_only_player_settings_with_input_evidence(self):
        records = [{"id": "globalgamemanagers#1", "type": "PlayerSettings", "fields": {"bundleVersion": "0.8.315"}},
                   {"id": "other#2", "type": "MonoBehaviour", "fields": {"bundleVersion": "wrong"}}]
        inputs = [{"path": "Human Host_Data/globalgamemanagers", "sha256": "a" * 64}]
        sources = {"globalgamemanagers": "globalgamemanagers"}
        result = capture_version(iter(records), sources, inputs)
        self.assertEqual(result["version"], "0.8.315")
        self.assertEqual(result["evidence"], [{"source_path": inputs[0]["path"], "source_sha256": "a" * 64,
                                             "object_id": "globalgamemanagers#1", "field": "/bundleVersion"}])
        self.assertEqual(result, capture_version(reversed(records), sources, inputs))
        self.assertEqual(capture_version([], sources, inputs)["reason"], "missing-player-settings")
        self.assertEqual(capture_version(records + [records[0]], sources, inputs)["reason"], "ambiguous-player-settings")
        for invalid in (None, "", 315, " version ", "line\nbreak", "x" * 129):
            records[0]["fields"]["bundleVersion"] = invalid
            self.assertIsNone(capture_version(records, sources, inputs)["version"])
        records[0]["fields"]["bundleVersion"] = "0.8.315"
        with self.assertRaisesRegex(ValueError, "inventory"):
            capture_version(records, sources, [])

    def test_reuse_stability_rejects_new_and_changed_installed_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            managed = game / "Human Host_Data" / "Managed"
            managed.mkdir(parents=True)
            path = managed / "Game.dll"
            path.write_bytes(b"fixture")
            paths = input_paths(game)
            stamps = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in paths}
            steam = steam_identity(game)
            inputs_stable(game, paths, stamps, steam)
            path.write_bytes(b"changed size")
            with self.assertRaisesRegex(RuntimeError, "changed during generation"):
                inputs_stable(game, paths, stamps, steam)
            (managed / "Added.dll").write_bytes(b"new")
            with self.assertRaisesRegex(RuntimeError, "input set changed"):
                inputs_stable(game, paths, stamps, steam)

    def test_steam_playtime_does_not_change_build_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            game = base / "common" / "Game"
            game.mkdir(parents=True)
            manifest = base / "appmanifest_2393970.acf"
            template = '"AppState" {{ "appid" "2393970" "buildid" "123" "LastPlayed" "{}" "InstalledDepots" {{ "7" {{ "manifest" "456" }} }} }}'
            manifest.write_text(template.format(1))
            first = steam_identity(game)
            manifest.write_text(template.format(999999))
            self.assertEqual(first, steam_identity(game))
            self.assertEqual(first["installed_depots"], {"7": {"manifest": "456"}})

    def test_inventory_excludes_saves_and_runtime_mod_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            for name in ("Managed/Player.dll", "Save/private.json", "ModBrowser/user.json", "StreamingAssets/settings.json",
                         "Plugins/Vuplex/log-chromium.txt", "Plugins/engine.log", "output_log.txt"):
                path = game / "Human Host_Data" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            self.assertEqual({p.name for p in input_paths(game)}, {"Player.dll", "settings.json"})

    def test_tool_hash_ignores_git_line_ending_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tool.ps1"
            path.write_bytes(b"one\ntwo\n")
            original = tool_digest(path)
            path.write_bytes(b"one\r\ntwo\r\n")
            self.assertEqual(tool_digest(path), original)

    def test_generated_header_keeps_script_pointer_aligned(self):
        def pointer(name):
            return TypeTreeNode(1, "PPtr<Object>", name, 12, 1, m_MetaFlag=0x4000, m_Children=[
                TypeTreeNode(2, "int", "m_FileID", 4, 1), TypeTreeNode(2, "SInt64", "m_PathID", 8, 1)])
        node = TypeTreeNode(0, "MonoBehaviour", "Base", -1, 1, m_Children=[
            pointer("m_GameObject"), TypeTreeNode(1, "UInt8", "m_Enabled", 1, 1),
            pointer("m_Script"), TypeTreeNode(1, "string", "m_Name", -1, 1, m_MetaFlag=0x4000)])
        data = struct.pack("<iqB3xiqi", 0, 23, 1, 1, 847, 0)
        tree = read_typetree(normalize_generated(node), EndianBinaryReader(data, endian="<"), byte_size=len(data))
        self.assertEqual(tree["m_Script"], {"m_FileID": 1, "m_PathID": 847})

    def test_generated_string_array_reads_elements_not_one_string(self):
        nodes = TypeTreeNode.from_list([
            TypeTreeNode(0, "Record", "Base", 0, 0),
            TypeTreeNode(1, "string", "names", 0, 0),
            TypeTreeNode(2, "Array", "Array", 0, 0, m_MetaFlag=0x4000),
            TypeTreeNode(3, "int", "size", 0, 0),
            TypeTreeNode(3, "string", "data", 0, 0),
            TypeTreeNode(4, "Array", "Array", 0, 0, m_MetaFlag=0x4000),
            TypeTreeNode(5, "int", "size", 0, 0),
            TypeTreeNode(5, "char", "data", 0, 0),
        ])
        data = struct.pack("<i", 2) + struct.pack("<i", 3) + b"one\0" + struct.pack("<i", 3) + b"two\0"
        tree = read_typetree(normalize_generated(nodes), EndianBinaryReader(data, endian="<"), byte_size=len(data))
        self.assertEqual(tree, {"names": ["one", "two"]})

    def test_compact_addressables_alias_and_dependency(self):
        def key(value):
            data = value.encode("ascii")
            return b"\0" + struct.pack("<i", len(data)) + data
        key_data = struct.pack("<i", 2) + key("item") + key("bundle")
        buckets = struct.pack("<i", 2) + struct.pack("<iii", 4, 1, 0) + struct.pack("<iii", 4 + len(key("item")), 1, 1)
        entries = struct.pack("<i14i", 2, 0, 0, 1, 5, -1, 0, 0, 1, 0, -1, 0, -1, 1, 0)
        result = decode({"m_BucketDataString": base64.b64encode(buckets), "m_KeyDataString": base64.b64encode(key_data),
                         "m_EntryDataString": base64.b64encode(entries), "m_ExtraDataString": "", "m_InternalIds": ["0#item.prefab", "bundle"],
                         "m_InternalIdPrefixes": ["assets/"], "m_ProviderIds": ["provider"], "m_resourceTypes": ["GameObject"]})
        self.assertEqual(result[0]["internal_id"], "assets/item.prefab")
        self.assertEqual(result[0]["dependency_entries"], [1])
        self.assertEqual(result[1]["keys"], ["bundle"])

    def test_binary_is_explicitly_omitted_and_large_ids_preserved(self):
        value = clean({"bytes": b"\xff\0", "id": 9223372036854775807})
        self.assertEqual(value["bytes"]["bytes"], 2)
        self.assertEqual(json.loads(json.dumps(value))["id"], 9223372036854775807)

    def test_external_reference_requires_unique_target(self):
        catalog = Catalog(Path("."), Path("."))
        catalog.files = {"a": {"assets": SimpleNamespace(externals=[SimpleNamespace(path="archive:/CAB-test/CAB-test")])}}
        catalog.aliases = {"cab-test": ["b"]}
        catalog.objects = {"b#123": None}
        pointer = {"m_FileID": 1, "m_PathID": 123}
        self.assertEqual(catalog.pointer("a", pointer)["target"], "b#123")
        catalog.aliases["cab-test"].append("c")
        catalog.objects["c#123"] = None
        self.assertEqual(catalog.pointer("a", pointer)["status"], "ambiguous")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hhmods-capture-snapshot-test-")
        self.output = Path(self.temp.name) / "code"
        self.output.mkdir()
        (self.output / "BUILD_INFO.md").write_text("old")
        git(self.output, "init", "--quiet")
        git(self.output, "config", "user.name", "Catalog Test")
        git(self.output, "config", "user.email", "catalog@example.invalid")
        git(self.output, "add", "-A")
        git(self.output, "commit", "--quiet", "-m", "old")
        self.head = git(self.output, "rev-parse", "HEAD").stdout

    def tearDown(self):
        # Windows marks loose Git objects read-only.
        import shutil
        def retry(function, path, exc):
            os.chmod(path, 0o700)
            function(path)
        shutil.rmtree(self.temp.name, onexc=retry)
        self.temp.cleanup()

    def test_generation_failure_preserves_previous_snapshot(self):
        with self.assertRaisesRegex(RuntimeError, "generation failed"):
            with Snapshot(self.output) as snapshot:
                (snapshot.stage / "partial.txt").write_text("partial")
                raise RuntimeError("generation failed")
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "old")
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
        self.assertFalse(snapshot.stage.exists())

    def test_interrupted_directory_swap_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            with Snapshot(self.output) as snapshot:
                (snapshot.stage / "BUILD_INFO.md").write_text("new")
                snapshot.prepare("new")
                snapshot.state["phase"] = "publishing"
                snapshot.write_journal(snapshot.state)
                os.replace(self.output, snapshot.backup)
                raise RuntimeError("simulated crash")
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "old")
        self.assertEqual(git(self.output, "status", "--porcelain").stdout, "")

    def test_repeat_publication_does_not_create_commit(self):
        for _ in range(2):
            with Snapshot(self.output) as snapshot:
                (snapshot.stage / "BUILD_INFO.md").write_text("old")
                snapshot.publish("same inputs")
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)

    def test_lock_rejects_second_writer(self):
        with Snapshot(self.output):
            with self.assertRaises((RuntimeError, OSError)):
                with Snapshot(self.output):
                    self.fail("Second writer acquired lock")

    @unittest.skipUnless(os.name == "nt", "Only Windows refuses to rename a directory with open handles inside")
    def test_held_output_fails_before_generation(self):
        # A process working directory inside .git holds a handle, like an editor's Git watcher.
        previous = os.getcwd()
        os.chdir(self.output / ".git")
        try:
            with self.assertRaisesRegex(RuntimeError, "Windows denied renaming .* another process holds"):
                with Snapshot(self.output) as snapshot:
                    self.fail("Generation started although publication cannot replace the output")
        finally:
            os.chdir(previous)
        snapshot = Snapshot(self.output)
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "old")
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
        self.assertFalse(snapshot.stage.exists() or snapshot.backup.exists() or snapshot.journal.exists())

    def interrupt_probe(self):
        # Simulate a crash after the probe's forward rename, before the rename back.
        snapshot = Snapshot(self.output)
        snapshot.write_journal({"output": str(self.output), "phase": "staging", "head": self.head.strip(), "existed": True})
        os.replace(self.output, snapshot.backup)
        return snapshot

    def test_interrupted_probe_restores_the_snapshot(self):
        snapshot = self.interrupt_probe()
        with Snapshot(self.output):
            pass
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "old")
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
        self.assertFalse(snapshot.backup.exists() or snapshot.journal.exists())

    def test_interrupted_probe_never_discards_a_recreated_output(self):
        snapshot = self.interrupt_probe()
        self.output.mkdir()
        (self.output / "BUILD_INFO.md").write_text("recreated")
        git(self.output, "init", "--quiet")
        git(self.output, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "add", "-A")
        git(self.output, "-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "--quiet", "-m", "other")
        with self.assertRaisesRegex(RuntimeError, "both exist"):
            with Snapshot(self.output):
                self.fail("Recovery accepted an ambiguous interrupted probe")
        self.assertEqual((snapshot.backup / "BUILD_INFO.md").read_text(), "old")
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "recreated")

    def test_dirty_snapshot_is_preserved(self):
        (self.output / "notes.txt").write_text("user work")
        with self.assertRaisesRegex(RuntimeError, "local changes"):
            with Snapshot(self.output):
                self.fail("Dirty snapshot accepted")
        self.assertEqual((self.output / "notes.txt").read_text(), "user work")

    def test_edits_during_generation_are_preserved(self):
        with self.assertRaisesRegex(RuntimeError, "changed during generation"):
            with Snapshot(self.output) as snapshot:
                (snapshot.stage / "BUILD_INFO.md").write_text("new")
                (self.output / "notes.txt").write_text("concurrent user work")
                snapshot.publish("new")
        self.assertEqual((self.output / "notes.txt").read_text(), "concurrent user work")
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)

    def test_crash_after_commit_retains_completed_snapshot(self):
        with self.assertRaisesRegex(RuntimeError, "after commit"):
            with Snapshot(self.output) as snapshot:
                (snapshot.stage / "BUILD_INFO.md").write_text("new")
                original = snapshot.write_journal
                def fail_after_commit(state):
                    if state["phase"] == "committed":
                        raise RuntimeError("after commit")
                    original(state)
                snapshot.write_journal = fail_after_commit
                snapshot.publish("new")
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "new")
        self.assertNotEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
        self.assertEqual(git(self.output, "status", "--porcelain").stdout, "")

    def test_same_size_and_timestamp_still_commits_changed_content(self):
        git(self.output, "config", "core.trustctime", "false")
        git(self.output, "config", "core.checkstat", "minimal")
        old_stat = (self.output / "BUILD_INFO.md").stat()
        with Snapshot(self.output) as snapshot:
            target = snapshot.stage / "BUILD_INFO.md"
            target.write_text("new")
            os.utime(target, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            snapshot.publish("same size and timestamp")
        self.assertEqual(git(self.output, "show", "HEAD:BUILD_INFO.md").stdout, "new")

    def interrupted_promotion(self):
        snapshot = Snapshot(self.output).__enter__()
        (snapshot.stage / "BUILD_INFO.md").write_text("prepared")
        snapshot.prepare("prepared")
        snapshot.state["phase"] = "publishing"
        snapshot.write_journal(snapshot.state)
        os.replace(self.output, snapshot.backup)
        os.replace(snapshot.stage, self.output)
        os.replace(snapshot.backup / ".git", self.output / ".git")
        git(self.output, "reset", "--mixed", snapshot.state["prepared_commit"])
        snapshot.lock.close()
        return snapshot

    def test_recovery_accepts_exact_journaled_result(self):
        snapshot = self.interrupted_promotion()
        state = json.loads(snapshot.journal.read_text())
        self.assertEqual(state["prepared_commit"], git(self.output, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual(state["prepared_tree"], git(self.output, "rev-parse", "HEAD^{tree}").stdout.strip())
        with Snapshot(self.output):
            pass
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "prepared")
        self.assertFalse(snapshot.backup.exists() or snapshot.journal.exists())

    def test_preparation_preserves_original_head_and_index(self):
        with Snapshot(self.output) as snapshot:
            (snapshot.stage / "BUILD_INFO.md").write_text("prepared")
            original_tree = git(self.output, "write-tree").stdout
            snapshot.prepare("prepared")
            self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
            self.assertEqual(git(self.output, "write-tree").stdout, original_tree)
            self.assertEqual(git(self.output, "status", "--porcelain").stdout, "")
            self.assertNotEqual(snapshot.state["prepared_commit"], self.head.strip())

    def test_recovery_accepts_original_before_promotion(self):
        snapshot = Snapshot(self.output).__enter__()
        (snapshot.stage / "BUILD_INFO.md").write_text("prepared")
        snapshot.prepare("prepared")
        snapshot.state["phase"] = "publishing"
        snapshot.write_journal(snapshot.state)
        snapshot.lock.close()
        with Snapshot(self.output):
            pass
        self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, self.head)
        self.assertEqual((self.output / "BUILD_INFO.md").read_text(), "old")
        self.assertFalse(snapshot.stage.exists() or snapshot.backup.exists() or snapshot.journal.exists())

    def test_no_git_publication_uses_exact_content_identity(self):
        output = Path(self.temp.name) / "no-git-code"
        with Snapshot(output, no_git=True) as snapshot:
            (snapshot.stage / "BUILD_INFO.md").write_text("diagnostic")
            snapshot.publish("diagnostic")
        self.assertEqual((output / "BUILD_INFO.md").read_text(), "diagnostic")
        self.assertFalse((output / ".git").exists())
        self.assertFalse(snapshot.journal.exists())

    def test_recovery_preserves_both_directories_for_foreign_clean_commit(self):
        for same_tree in (True, False):
            with self.subTest(same_tree=same_tree):
                snapshot = self.interrupted_promotion()
                if not same_tree:
                    (self.output / "BUILD_INFO.md").write_text("foreign")
                    git(self.output, "add", "-A")
                git(self.output, "commit", "--quiet", "--allow-empty", "-m", "foreign commit")
                foreign_head = git(self.output, "rev-parse", "HEAD").stdout
                with self.assertRaisesRegex(RuntimeError, "matches neither.*preserving"):
                    with Snapshot(self.output):
                        self.fail("Accepted a foreign clean commit")
                self.assertEqual(git(self.output, "rev-parse", "HEAD").stdout, foreign_head)
                self.assertEqual((snapshot.backup / "BUILD_INFO.md").read_text(), "old")
                self.assertTrue(snapshot.journal.exists())
                # Restore the fixture explicitly for the next independent case.
                os.replace(self.output / ".git", snapshot.backup / ".git")
                import shutil
                shutil.rmtree(self.output)
                os.replace(snapshot.backup, self.output)
                git(self.output, "reset", "--mixed", self.head.strip())
                snapshot.journal.unlink()

    def test_recovery_preserves_uncommitted_foreign_files(self):
        snapshot = self.interrupted_promotion()
        (self.output / "foreign.txt").write_text("preserve me")
        with self.assertRaisesRegex(RuntimeError, "Ambiguous snapshot recovery"):
            with Snapshot(self.output):
                self.fail("Accepted changed output")
        self.assertEqual((self.output / "foreign.txt").read_text(), "preserve me")
        self.assertEqual((snapshot.backup / "BUILD_INFO.md").read_text(), "old")
        self.assertTrue(snapshot.journal.exists())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
