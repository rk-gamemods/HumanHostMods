"""Text catalogs and cross-file references for installed Unity player data."""
import collections
import hashlib
import gzip
import io
import json
import math
import re
from pathlib import Path

import UnityPy
from UnityPy.files.SerializedFile import SerializedFile
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.streams import EndianBinaryReader

from addressables import decode as decode_addressables
from bundles import Bundle, MemberStream
from schemas import normalize_generated, read_with_managed_references
from processes import run_process, DECODER_SECONDS


# These objects remain cataloged by name, type, ID, source, and byte size.
# Their bodies contain rendering/media data rather than gameplay definitions.
PAYLOAD_TYPES = {
    "Texture2D", "Texture3D", "Texture2DArray", "Cubemap", "CubemapArray", "RenderTexture",
    "Mesh", "AudioClip", "VideoClip", "Shader", "ComputeShader", "Font", "AnimationClip",
    "TerrainData", "NavMeshData", "LightingDataAsset", "LightProbes", "OcclusionCullingData",
    "PreloadData", "PackedAssets", "SpriteAtlas", "SpeedTreeWindAsset",
    "ParticleSystem",
}
PAYLOAD_SCRIPTS = {"PampelGames.GoreSimulator.SO_Storage": "baked gore meshes and mesh-cut vertex/index data"}
HASH_SUFFIX = re.compile(r"_[0-9a-f]{32}(?=\.bundle$)", re.I)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8", errors="backslashreplace")


def rows(path, values, locations=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for value in values:
            if locations is not None and value.get("script"):
                locations[value["id"]] = indexed_row(handle, value)
            else:
                handle.write(encoded(value) + b"\n")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8", errors="backslashreplace")


def indexed_row(handle, value):
    """Write canonical JSON once; index large records by named member sizes.

    The index describes every member, including unknown future fields. It carries
    no wiki selection policy and creates no second raw record or field-value copy.
    """
    start, sha = handle.tell(), hashlib.sha256()

    def emit(data):
        handle.write(data)
        sha.update(data)

    def members(obj, split_fields=False):
        sizes = {}
        emit(b"{")
        for index, key in enumerate(sorted(obj)):
            if index:
                emit(b", ")
            emit(encoded(key) + b": ")
            if split_fields and key == "fields" and isinstance(obj[key], dict):
                sizes[key] = members(obj[key])
            else:
                data = encoded(obj[key])
                emit(data)
                sizes[key] = len(data)
        emit(b"}")
        return sizes

    sizes = members(value, split_fields=True)
    emit(b"\n")
    location = {"offset": start, "bytes": handle.tell() - start, "sha256": sha.hexdigest()}
    if location["bytes"] >= 1024 * 1024:
        location["members"] = sizes
    return location


def clean(value):
    """Keep scalar/structured text. Binary values get explicit descriptors, never base64."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, bytes):
        return {"omitted": "binary payload", "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"float": str(value)}
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    raise TypeError(f"Unrecognized serialized value: {type(value).__name__}")


def source_key(relative):
    normalized = relative.replace("\\", "/")
    normalized = normalized.replace("StreamingAssets/aa/StandaloneWindows64/", "bundles/", 1)
    return HASH_SUFFIX.sub("", normalized)


def walk(value, path=""):
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from walk(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}/{index}")


class Catalog:
    def __init__(self, game, destination):
        self.game, self.data, self.destination = game, game / "Human Host_Data", destination
        self.environment = UnityPy.Environment()
        self.files, self.aliases, self.objects, self.scripts = {}, {}, {}, {}
        self.containers, self.addressables, self.guid_targets = {}, [], {}
        self.streams, self.bundles, self.inputs = [], [], []
        self.text_assets = []
        self.failures, self.references, self.records = [], collections.Counter(), {}
        self.generator = None
        self.schemas = collections.defaultdict(list)
        self.gaps = []

    def add_file(self, stream, source, name, member_index=0):
        logical = source_key(source)
        # CAB names are build hashes. A member ordinal scoped to its bundle avoids
        # turning a changed CAB hash into a rename of every catalog record.
        key = logical + (f"::serialized-{member_index}" if source.endswith(".bundle") else "")
        if key in self.files:
            raise ValueError(f"Duplicate serialized file identity: {key}")
        assets = SerializedFile(EndianBinaryReader(stream), parent=self.environment, name=name)
        self.files[key] = {"assets": assets, "source": source, "member": name, "key": key}
        alias = Path(name).name.lower()
        self.aliases.setdefault(alias, []).append(key)
        for obj in assets.objects.values():
            identity = f"{key}#{obj.path_id}"
            self.objects[identity] = (key, obj)
        return assets

    def load(self):
        paths = sorted(self.data.glob("*"))
        candidates = [p for p in paths if p.is_file() and
                      (p.suffix == ".assets" or re.fullmatch(r"level\d+", p.name) or p.name == "globalgamemanagers")]
        candidates += sorted(p for p in (self.data / "Resources").glob("*") if p.is_file() and p.suffix.lower() not in {".ress", ".resource"})
        candidates += sorted((self.data / "StreamingAssets").rglob("*.bundle"))
        for index, path in enumerate(candidates, 1):
            relative = path.relative_to(self.data).as_posix()
            print(f"[catalog headers {index}/{len(candidates)}] {path.name}", flush=True)
            stream = path.open("rb")
            self.streams.append(stream)
            if path.suffix != ".bundle":
                self.add_file(stream, relative, path.name)
                continue
            signature = stream.read(7)
            if signature.startswith(b"\x1f\x8b"):
                stream.seek(0)
                with gzip.GzipFile(fileobj=stream) as compressed:
                    text = compressed.read().decode("utf-8-sig")
                self.text_assets.append({"source": relative, "encoding": "gzip UTF-8", "text": text})
                self.inputs.append({"source": relative, "bytes": path.stat().st_size,
                                    "treatment": "compressed text companion; not a UnityFS asset bundle"})
                continue
            if signature != b"UnityFS":
                helper = Path(__file__).resolve().parents[1] / "Read-GameBundle.ps1"
                result = run_process(["pwsh", "-NoProfile", "-File", str(helper),
                                         "-GameData", str(self.data), "-BundlePath", str(path)],
                                     timeout=DECODER_SECONDS, text=False)
                stream = io.BytesIO(result.stdout)
                self.streams.append(stream)
            bundle = Bundle(stream)
            self.bundles.append(bundle)
            member_index = 0
            for name, offset, size, flags in bundle.members:
                if name.lower().endswith((".ress", ".resource")):
                    self.inputs.append({"source": relative, "member": name, "bytes": size,
                                        "treatment": "resource payload cataloged only"})
                    continue
                self.add_file(MemberStream(bundle, offset, size), relative, name, member_index)
                self.inputs.append({"source": relative, "member": name, "bytes": size,
                                    "treatment": "serialized object metadata"})
                member_index += 1
        versions = sorted({str(f["assets"].unity_version) for f in self.files.values()})
        # unity_version is a string on the pinned UnityPy version.
        version = self.files[next(iter(self.files))]["assets"].unity_version
        self.generator = TypeTreeGenerator(version)
        for dll in sorted((self.data / "Managed").glob("*.dll")):
            if dll.name in {"System.Memory.dll", "System.Runtime.CompilerServices.Unsafe.dll"}:
                continue  # Already registered by TypeTreeGeneratorAPI itself.
            self.generator.load_dll(dll.read_bytes())
        self.versions = versions

    def pointer(self, file_key, pointer):
        path_id, file_id = pointer["m_PathID"], pointer["m_FileID"]
        if path_id == 0:
            return {"status": "null"}
        candidates = [file_key]
        external = None
        if file_id:
            externals = self.files[file_key]["assets"].externals
            if file_id < 0 or file_id > len(externals):
                return {"status": "invalid_file_id", "file_id": file_id}
            external = externals[file_id - 1].path.replace("\\", "/")
            candidates = self.aliases.get(external.rsplit("/", 1)[-1].lower(), [])
        matches = [f"{key}#{path_id}" for key in candidates if f"{key}#{path_id}" in self.objects]
        if len(matches) == 1:
            return {"status": "resolved", "target": matches[0]}
        if len(matches) > 1:
            return {"status": "ambiguous", "candidates": sorted(matches), "external": external}
        builtin = external and any(n in external.lower() for n in ("unity default resources", "unity_builtin_extra"))
        return {"status": "engine_builtin" if builtin else "unresolved", "external": external,
                "path_id": path_id}

    def prepare(self):
        for identity, (key, obj) in self.objects.items():
            if obj.type.name == "MonoScript":
                self.scripts[identity] = obj.read_typetree()
        seen_nodes = set()
        for identity, (key, obj) in self.objects.items():
            if obj.type.name != "MonoBehaviour" or not obj.serialized_type or not obj.serialized_type.node:
                continue
            node = obj.serialized_type.node
            if id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            head = obj.parse_monobehaviour_head()
            ref = self.pointer(key, {"m_FileID": head.m_Script.m_FileID, "m_PathID": head.m_Script.m_PathID})
            script = self.scripts.get(ref.get("target"))
            if script:
                cls = ((script["m_Namespace"] + ".") if script["m_Namespace"] else "") + script["m_ClassName"]
                self.schemas[(script["m_AssemblyName"], cls)].append((identity, node))
        reference_schemas = {t.old_type_hash: t for info in self.files.values()
                             for t in info["assets"].ref_types if t.node is not None and t.old_type_hash}
        for info in self.files.values():
            for ref_type in info["assets"].ref_types:
                donor = reference_schemas.get(ref_type.old_type_hash)
                if ref_type.node is None and donor:
                    ref_type.node = donor.node
                    ref_type.m_ClassName = donor.m_ClassName
                    ref_type.m_NameSpace = donor.m_NameSpace
                    ref_type.m_AssemblyName = donor.m_AssemblyName
                if ref_type.node is None and ref_type.m_ClassName:
                    cls = ((ref_type.m_NameSpace + ".") if ref_type.m_NameSpace else "") + ref_type.m_ClassName
                    try:
                        ref_type.node = normalize_generated(self.generator.get_nodes_up(ref_type.m_AssemblyName, cls))
                    except Exception:
                        pass  # A consumer will report the exact missing managed-reference schema.
        for identity, (key, obj) in self.objects.items():
            if obj.type.name != "AssetBundle":
                continue
            tree = obj.read_typetree()
            container = tree.get("m_Container", [])
            if isinstance(container, dict):
                container = list(container.items())
            for path, info in container:
                resolved = self.pointer(key, info["asset"])
                if resolved["status"] == "resolved":
                    self.containers.setdefault(path.lower().replace("\\", "/"), set()).add(resolved["target"])
        catalog_paths = sorted((self.data / "StreamingAssets").rglob("catalog*.json"))
        for path in catalog_paths:
            catalog = json.loads(path.read_text(encoding="utf-8-sig"))
            if "m_BucketDataString" not in catalog:
                continue
            entries = decode_addressables(catalog)
            for entry in entries:
                entry["catalog"] = path.relative_to(self.data).as_posix()
                path_key = entry["internal_id"].lower().replace("\\", "/")
                targets = sorted(self.containers.get(path_key, []))
                entry["targets"] = targets
                for alias in entry["keys"]:
                    if isinstance(alias, str) and re.fullmatch(r"[0-9a-fA-F]{32}", alias):
                        self.guid_targets.setdefault(alias.lower(), set()).update(targets)
            self.addressables.extend(entries)

    def export_object(self, identity, key, obj):
        record = {"id": identity, "path_id": obj.path_id, "type": obj.type.name,
                  "class_id": obj.class_id, "serialized_bytes": obj.byte_size}
        try:
            if obj.type.name in PAYLOAD_TYPES:
                record["name"] = obj.peek_name()
                record["body_omitted"] = "rendering, media, navigation or bulk engine payload"
                return record
            nodes = None
            if obj.type.name == "MonoBehaviour":
                head = obj.parse_monobehaviour_head()
                script_ref = self.pointer(key, {"m_FileID": head.m_Script.m_FileID, "m_PathID": head.m_Script.m_PathID})
                script = self.scripts.get(script_ref.get("target"))
                if not script:
                    raise ValueError(f"Missing MonoScript: {script_ref}")
                cls = ((script["m_Namespace"] + ".") if script["m_Namespace"] else "") + script["m_ClassName"]
                record["script"] = {"assembly": script["m_AssemblyName"], "class": cls,
                                    "target": script_ref["target"]}
                if cls in PAYLOAD_SCRIPTS:
                    record["name"] = obj.peek_name()
                    record["body_omitted"] = PAYLOAD_SCRIPTS[cls]
                    return record
                assembly = script["m_AssemblyName"].removesuffix(".dll")
                if (assembly.endswith("-Editor") or ".Editor" in assembly) and not (self.data / "Managed" / (assembly + ".dll")).exists():
                    record["name"] = head.m_Name
                    record["decode_gap"] = "Editor-only declaring assembly is absent from the shipped player; no reconstructable field layout"
                    record["raw_sha256"] = hashlib.sha256(obj.get_raw_data()).hexdigest()
                    self.gaps.append({"id": identity, "script": record["script"], "reason": record["decode_gap"]})
                    return record
                # Embedded field layouts are authoritative for this serialized object.
                # DLL reconstruction is a fallback only for stripped player files.
                nodes = obj.serialized_type.node if obj.serialized_type else None
                if nodes is None and self.schemas.get((script["m_AssemblyName"], cls)):
                    candidates = self.schemas[(script["m_AssemblyName"], cls)]
                    signatures = {tuple((n.m_Level, n.m_Type, n.m_Name, (n.m_MetaFlag or 0) & 0x4000)
                                        for n in candidate.traverse()) for _, candidate in candidates}
                    if len(signatures) != 1:
                        raise ValueError(f"Conflicting embedded layouts for {cls}; explicit schema selection is required")
                    origin, nodes = candidates[0]
                    record["schema_origin"] = origin
                if nodes is None:
                    nodes = normalize_generated(self.generator.get_nodes_up(script["m_AssemblyName"], cls))
                record["schema_source"] = "embedded" if obj.serialized_type and obj.serialized_type.node else ("matching embedded class" if "schema_origin" in record else "managed assembly")
            try:
                tree = obj.read_typetree(nodes=nodes)
            except ValueError as exc:
                if "ref type" not in str(exc):
                    raise
                tree = read_with_managed_references(obj, nodes, self.generator)
                record["managed_reference_schema"] = "reconstructed from serialized type names and installed DLLs"
            record["name"] = tree.get("m_Name")
            if obj.type.name == "MonoBehaviour":
                expected_script = {"m_FileID": head.m_Script.m_FileID, "m_PathID": head.m_Script.m_PathID}
                if tree.get("m_Script") != expected_script or tree.get("m_Name") != head.m_Name:
                    raise ValueError("Decoded fields disagree with the independently parsed MonoBehaviour header")
            if record.get("script", {}).get("class") == "GPUInstancer.CrowdAnimations.GPUICrowdAnimationData":
                for field in ("rootMotions", "bindPoses"):
                    if field in tree:
                        tree[field] = {"omitted": "baked animation matrices", "entries": len(tree[field])}
            if obj.type.name == "AssetBundle":
                for field in ("m_PreloadTable", "m_Container"):
                    if field in tree:
                        tree[field] = {"omitted": "bundle loading index; named asset paths exported in containers.jsonl",
                                       "entries": len(tree[field])}
            if obj.type.name == "TextAsset" and isinstance(tree.get("m_Script"), (str, bytes)):
                payload = tree["m_Script"]
                if isinstance(payload, bytes):
                    try:
                        tree["m_Script"] = payload.decode("utf-8")
                    except UnicodeError:
                        pass
                if isinstance(tree["m_Script"], str) and "\x00" in tree["m_Script"]:
                    tree["m_Script"] = {"omitted": "binary TextAsset", "characters": len(tree["m_Script"])}
            record["fields"] = clean(tree)
            refs = []
            for field, value in walk(record["fields"]):
                if "m_FileID" in value and "m_PathID" in value:
                    resolution = self.pointer(key, value)
                    self.references[resolution["status"]] += 1
                    if resolution["status"] != "null":
                        refs.append({"field": field, **resolution})
                if "m_AssetGUID" in value and value["m_AssetGUID"]:
                    guid = value["m_AssetGUID"]
                    targets = sorted(self.guid_targets.get(guid.lower(), []))
                    status = "resolved" if targets else "unresolved_guid"
                    refs.append({"field": field, "status": status, "guid": guid, "targets": targets,
                                 "sub_object": value.get("m_SubObjectName")})
                    self.references[status] += 1
            if refs:
                record["references"] = refs
        except Exception as exc:
            record["decode_error"] = f"{type(exc).__name__}: {exc}"
            self.failures.append({"id": identity, "type": obj.type.name, "script": record.get("script"), "error": record["decode_error"]})
        return record

    def export(self):
        self.load()
        print(f"[catalog] {len(self.files)} serialized files; {len(self.objects)} objects", flush=True)
        self.prepare()
        object_types, script_types = collections.Counter(), collections.Counter()
        locations = {}
        for index, (key, info) in enumerate(sorted(self.files.items()), 1):
            print(f"[catalog metadata {index}/{len(self.files)}] {key}", flush=True)
            output = []
            for obj in sorted(info["assets"].objects.values(), key=lambda obj: obj.path_id):
                identity = f"{key}#{obj.path_id}"
                record = self.export_object(identity, key, obj)
                self.records[identity] = record
                output.append(record)
                object_types[record["type"]] += 1
                if "script" in record:
                    script_types[record["script"]["class"]] += 1
            # The readable source name is retained, rather than a hash-only output filename.
            relative = key.replace("::", "/") + ".jsonl"
            rows(self.destination / "objects" / relative, output, locations)
        rows(self.destination / "addressables.jsonl", self.addressables)
        rows(self.destination / "references.jsonl", ({"source": identity, **ref}
             for identity, record in sorted(self.records.items()) for ref in record.get("references", [])))
        rows(self.destination / "containers.jsonl", ({"path": p, "targets": sorted(ids)} for p, ids in sorted(self.containers.items())))
        rows(self.destination / "bundle-members.jsonl", self.inputs)
        rows(self.destination / "compressed-text.jsonl", self.text_assets)
        rows(self.destination / "serialized-files.jsonl", ({"id": k, "source": f["source"], "member": f["member"],
             "unity_version": f["assets"].unity_version, "objects": len(f["assets"].objects),
             "externals": [{"path": e.path, "guid": e.guid.hex() if e.guid else None} for e in f["assets"].externals]}
             for k, f in sorted(self.files.items())))
        dump(self.destination / "coverage.json", {
            "schema": 1, "serialized_files": len(self.files), "objects": len(self.objects),
            "object_types": dict(object_types), "script_types": dict(script_types),
            "references": dict(self.references), "decode_failures": self.failures,
            "decode_gaps": self.gaps,
            "payload_types_cataloged_without_body": sorted(PAYLOAD_TYPES),
            "payload_scripts_cataloged_without_body": PAYLOAD_SCRIPTS,
            "unity_versions": self.versions,
            "input_scope": "Installed player data, resources, streaming assets and managed/native modules. Save, ModBrowser and runtime log files are excluded. Steam build/depot identities are recorded separately.",
            "identity_note": "Bundle name without content hash + serialized member ordinal + path ID. Path IDs can change across builds; Addressables GUIDs and container paths provide additional identity.",
        })
        from views import generate
        generate(self.destination, self.records, self.addressables, self.containers, locations)
        for stream in self.streams:
            stream.close()
        return self.failures
