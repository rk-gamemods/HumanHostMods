"""Run: py -3 tools/game_catalog/test_catalog.py --python-packages <isolated dependencies>"""
import argparse
import base64
import io
import json
import os
import struct
import sys
import tempfile
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
from refresh import steam_identity, input_paths, tool_digest, reusable_capture, inputs_stable
from schemas import normalize_generated
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers.TypeTreeHelper import read_typetree
from UnityPy.streams import EndianBinaryReader


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
            for name, data in [("steam-build.json", steam), ("generator.json", generator), ("coverage.json", {"decode_failures": []})]:
                (catalog / name).write_text(json.dumps(data))
            (catalog / "inputs.jsonl").write_text(json.dumps(inputs[0]) + "\n")
            (catalog / "assemblies.jsonl").write_text(json.dumps({"reason": "selected"}) + "\n")
            self.assertTrue(reusable_capture(output, steam, inputs, generator))
            self.assertFalse(reusable_capture(output, {"build_id": "2"}, inputs, generator))
            self.assertFalse(reusable_capture(output, steam, [{"path": "game.dll", "sha256": "b"}], generator))
            self.assertFalse(reusable_capture(output, steam, inputs, {"tools": {"parser": "b"}}))
            (catalog / "assemblies.jsonl").write_text(json.dumps({"reason": "explicit assembly subset"}) + "\n")
            self.assertFalse(reusable_capture(output, steam, inputs, generator))

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
        self.temp = tempfile.TemporaryDirectory()
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
                snapshot.state["phase"] = "publishing"
                snapshot.write_journal(snapshot.state)
                os.replace(self.output, snapshot.backup)
                os.replace(snapshot.stage, self.output)
                os.replace(snapshot.backup / ".git", self.output / ".git")
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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
