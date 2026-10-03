"""Reproducible text generation; Snapshot.publish is the publication boundary."""
import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import threading
import sys
from contextlib import contextmanager, nullcontext
from pathlib import Path
from processes import run_process, GIT_SECONDS, PROBE_SECONDS, ASSEMBLY_SECONDS, CAPTURE_SECONDS
from timing import Timing, short_error, supervise_capture, timing_parser, receipt_directory, cli_error

FRAMEWORK = re.compile(r"^(System(?:\.|$)|Mono(?:\.|$)|mscorlib$|netstandard$|Microsoft\.|UnityEngine)")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def tool_digest(path):
    # Git may convert PowerShell sources to CRLF on checkout. This is not a
    # generator behavior change and must not create a different snapshot.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def generator_tools(script_root):
    return sorted(p for p in script_root.glob("*.py") if not p.name.startswith("test_") and p.name != "timing.py") + [script_root.parent / "Decompile-GameCode.ps1", script_root.parent / "Read-GameBundle.ps1", script_root / "requirements.txt"]


def steam_identity(game):
    manifest = game.parent.parent / "appmanifest_2393970.acf"
    if not manifest.exists():
        return {"app_id": "2393970", "build_id": "unknown", "installed_depots": {}}
    tokens = iter(m.group(1) if m.group(1) is not None else m.group(2)
                  for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|([{}])', manifest.read_text(encoding="utf-8")))
    def read_object():
        values = {}
        for key in tokens:
            if key == "}":
                return values
            value = next(tokens)
            values[key] = read_object() if value == "{" else value
        return values
    state = read_object()["AppState"]
    return {"app_id": state["appid"], "build_id": state["buildid"],
            "installed_depots": state.get("InstalledDepots", {}),
            "branch": state.get("UserConfig", {}).get("BetaKey", "public")}


def input_paths(game):
    data = game / "Human Host_Data"
    paths = []
    for directory, subdirs, files in os.walk(data):
        if Path(directory) == data:
            subdirs[:] = sorted(d for d in subdirs if d.casefold() not in {"save", "modbrowser"})
        paths.extend(Path(directory) / name for name in files
                     if not name.lower().endswith(".log") and name.lower() != "output_log.txt"
                     and not (name.lower().startswith("log-") and name.lower().endswith(".txt")))
    paths += [p for p in game.iterdir() if p.is_file() and p.suffix.lower() in {".dll", ".exe"}]
    return sorted(paths)


def inventory(game, paths):
    result, stamps = [], {}
    for index, path in enumerate(paths, 1):
        relative = os.path.relpath(path, game).replace("\\", "/")
        before = path.stat()
        if index % 50 == 1 or path.suffix == ".bundle":
            print(f"[inventory {index}/{len(paths)}] {relative}", flush=True)
        sha = digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Input changed while hashing: {path}")
        stamps[path] = (after.st_size, after.st_mtime_ns)
        category = ("managed assembly" if path.parent.name == "Managed" and path.suffix == ".dll" else
                    "symbols" if path.suffix == ".pdb" else "asset bundle" if path.suffix == ".bundle" else
                    "resource payload" if path.suffix.lower() in {".ress", ".resource"} else
                    "native binary" if path.suffix.lower() in {".dll", ".exe"} else "data/configuration")
        result.append({"path": relative, "bytes": after.st_size, "sha256": sha, "category": category})
    return result, stamps


def decompile(game, stage, names, workers, timing=None):
    managed = game / "Human Host_Data" / "Managed"
    assemblies = sorted(managed.glob("*.dll"))
    selected = [p for p in assemblies if p.stem in names] if names else [p for p in assemblies if not FRAMEWORK.match(p.stem)]
    if names and set(names) != {p.stem for p in selected}:
        raise ValueError("An explicitly selected assembly is missing")
    manifest = [{"name": p.name, "sha256": digest(p), "decompiled": p in selected,
                 "reason": "selected" if p in selected else ("explicit assembly subset" if names else "runtime/framework module; API use remains in game source")}
                for p in assemblies]
    cancel = threading.Event()
    if timing:
        timing.update(assemblies=[{"name": p.name, "seconds": 0.0, "outcome": "skipped"} for p in assemblies])

    def run(path):
        with timing.measure(path.name, "assemblies") if timing else nullcontext():
            return run_assembly(path)

    def run_assembly(path):
        out = stage / path.stem
        out.mkdir()
        # Project mode extracts resources. Source-only mode emits C# and keeps payloads out.
        args = ["ilspycmd", "--disable-updatecheck", "-o", str(out), "-r", str(managed)]
        if path.with_suffix(".pdb").exists():
            args.append("-usepdb")
        core = game / "BepInEx" / "core"
        if core.exists():
            args += ["-r", str(core)]
        args.append(str(path))
        run_process(args, timeout=ASSEMBLY_SECONDS, cancel=cancel)
        resources = run_process(["ilspycmd", "--disable-updatecheck", "--list-resources", str(path)],
                                timeout=ASSEMBLY_SECONDS, cancel=cancel)
        return path.name, resources.stdout.splitlines()

    embedded = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(run, path): path for path in selected}
        try:
            for index, future in enumerate(concurrent.futures.as_completed(pending), 1):
                name, resources = future.result()
                print(f"[C# {index}/{len(selected)}] {name}", flush=True)
                embedded.append({"assembly": name, "resources": resources, "treatment": "names only; no resource extraction"})
        except BaseException:
            cancel.set()
            for future in pending:
                future.cancel()
            raise
    return manifest, sorted(embedded, key=lambda x: x["assembly"])


def inputs_stable(game, paths, stamps, steam):
    """Both a new capture and a reuse decision require the same stability gate."""
    if paths != input_paths(game):
        raise RuntimeError("Installed input set changed during generation; retry with stable inputs")
    for path, stamp in stamps.items():
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != stamp:
            raise RuntimeError(f"Installed input changed during generation: {path}")
    if steam != steam_identity(game):
        raise RuntimeError("Installed Steam build changed during generation")


def reusable_capture(output, steam, inputs, generator):
    """Called under Snapshot's lock after its clean/local-only source checks.

    Compare freshly hashed installed bytes and exact extraction implementation.
    Filesystem timestamps alone never establish unchanged game content.
    """
    catalog = output / "Catalog"
    required = ["steam-build.json", "inputs.jsonl", "generator.json", "coverage.json", "assemblies.jsonl", "game-version.json"]
    if not all((catalog / name).is_file() for name in required):
        return False
    old_steam = json.loads((catalog / "steam-build.json").read_text(encoding="utf-8"))
    old_generator = json.loads((catalog / "generator.json").read_text(encoding="utf-8"))
    if steam != old_steam or generator != old_generator:
        return False
    with (catalog / "inputs.jsonl").open(encoding="utf-8") as stream:
        old_inputs = [json.loads(line) for line in stream]
    if inputs != old_inputs:
        return False
    coverage = json.loads((catalog / "coverage.json").read_text(encoding="utf-8"))
    if coverage.get("decode_failures"):
        return False
    with (catalog / "assemblies.jsonl").open(encoding="utf-8") as stream:
        if any(row.get("reason") == "explicit assembly subset" for row in map(json.loads, stream)):
            return False
    return True


@contextmanager
def timed_snapshot(output, no_git, timing):
    from snapshot import Snapshot
    snapshot = Snapshot(output, no_git)
    snapshot.__enter__()
    try:
        yield snapshot
    finally:
        exception = sys.exc_info()
        with timing.measure("cleanup"):
            snapshot.__exit__(*exception)


def main(timing=None):
    owned = timing is None
    if owned:
        parser = timing_parser()
        parser.add_argument("--output", default="")
        options, _ = parser.parse_known_args()
        timing = Timing(options.output, options.timing_receipt)
    error = None
    try:
        capture(timing)
    except BaseException as exc:
        error = exc
        timing.update(outcome="failed", error=short_error(exc))
        raise
    finally:
        if owned:
            timing.finish(error)
        else:
            timing.drain()


def capture(timing):
    parser = argparse.ArgumentParser(description=__doc__, parents=[timing_parser()], allow_abbrev=False)
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--python-packages", type=Path)
    parser.add_argument("--assemblies", nargs="*")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--no-git", action="store_true")
    options = parser.parse_args()
    receipt_directory(options.timing_receipt, options.output)
    if options.python_packages:
        sys.path.insert(0, str(options.python_packages.resolve()))
    game, output = options.game.resolve(), options.output.resolve()
    timing.update(output_path=str(output))
    from catalog import Catalog, dump, rows
    workspace = Path(__file__).resolve().parents[2]
    if output == workspace or output.is_relative_to(game) or game.is_relative_to(output):
        raise ValueError("Output must be a separate generated snapshot directory outside the game")
    if output.is_relative_to(workspace):
        ignored = run_process(["git", "-C", str(workspace), "check-ignore", "-q", "--", output.relative_to(workspace).as_posix() + "/"], timeout=GIT_SECONDS, check=False)
        if ignored.returncode:
            raise ValueError("Output inside the workspace must be gitignored; use HumanHostCodebase or a path under .local")
    versions = {name: importlib.metadata.version(name) for name in ("UnityPy", "TypeTreeGeneratorAPI")}
    if versions != {"UnityPy": "1.25.3", "TypeTreeGeneratorAPI": "0.0.10"}:
        raise RuntimeError(f"Unsupported parser versions: {versions}; install tools/game_catalog/requirements.txt")
    for name in ("tpk_ar", "attrs", "lz4", "brotli", "fsspec"):
        versions[name] = importlib.metadata.version(name)
    if not shutil.which("ilspycmd"):
        raise RuntimeError("ilspycmd is not installed")
    if options.assemblies and output.exists():
        raise ValueError("Partial assembly exports require a new output path; they cannot replace a full snapshot")
    if options.workers < 1:
        raise ValueError("workers must be positive")
    decompiler = run_process(["ilspycmd", "--version"], timeout=PROBE_SECONDS).stdout.splitlines()[0]
    with timed_snapshot(output, options.no_git, timing) as snapshot:
        stage = snapshot.stage
        with timing.measure("input hashing/reuse check"):
            script_root = Path(__file__).resolve().parent
            tool_files = generator_tools(script_root)
            tool_hashes = {p.relative_to(script_root.parent).as_posix(): tool_digest(p) for p in tool_files}
            generator = {"schema": 1, "packages": versions, "python": sys.version.split()[0],
                         "decompiler": decompiler, "tool_hash_normalization": "CRLF to LF", "tools": tool_hashes}
            steam = steam_identity(game)
            paths = input_paths(game)
            inputs, stamps = inventory(game, paths)
            build = steam["build_id"]
            timing.update(game={"version": None, "build": build})
            if not options.no_git and not options.assemblies and reusable_capture(output, steam, inputs, generator):
                inputs_stable(game, paths, stamps, steam)
                if tool_hashes != {p.relative_to(script_root.parent).as_posix(): tool_digest(p) for p in tool_files}:
                    raise RuntimeError("Generator source changed during input verification")
                if snapshot.fingerprint() != snapshot.original_files:
                    raise RuntimeError("Source snapshot changed during input verification")
                from snapshot import git
                if git(output, "rev-parse", "HEAD").stdout.strip() != snapshot.state["head"] or git(output, "status", "--porcelain").stdout.strip():
                    raise RuntimeError("Source snapshot Git state changed during input verification")
                version = json.loads((output / "Catalog" / "game-version.json").read_text(encoding="utf-8"))
                timing.update(outcome="reused", output_commit=snapshot.state["head"], game={"version": version["version"], "build": build})
                print(f"Unchanged: verified installed hashes, Steam identity and generator; reusing {snapshot.state['head']}", flush=True)
                return
        with timing.measure("catalog decode"):
            dump(stage / "Catalog" / "steam-build.json", steam)
            rows(stage / "Catalog" / "inputs.jsonl", inputs)
            loose_text = []
            for path in paths:
                if path.name == "catalog.json" or path.suffix.lower() not in {".json", ".xml", ".txt", ".config", ".lua"} and path.name not in {"build_info", "Bundle_Info", "app.info"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8-sig")
                except UnicodeError:
                    continue
                if "\x00" not in text:
                    loose_text.append({"source": os.path.relpath(path, game).replace("\\", "/"), "text": text})
            rows(stage / "Catalog" / "loose-text.jsonl", loose_text)
            catalog = Catalog(game, stage / "Catalog")
            failures = catalog.export()
            if failures:
                raise RuntimeError(f"Catalog has {len(failures)} decoding failures; previous snapshot preserved.\n" + json.dumps(failures[:20], indent=2))
            from game_version import capture
            version = capture(catalog.records.values(), {key: info["source"] for key, info in catalog.files.items()}, inputs)
            dump(stage / "Catalog" / "game-version.json", version)
            timing.update(game={"version": version["version"], "build": build})
            print(f"[game version] {version['version'] or version['reason']}", flush=True)
        with timing.measure("decompile"):
            assembly_manifest, resources = decompile(game, stage, options.assemblies, options.workers, timing)
        rows(stage / "Catalog" / "assemblies.jsonl", assembly_manifest)
        rows(stage / "Catalog" / "embedded-resources.jsonl", resources)
        dump(stage / "Catalog" / "generator.json", generator)
        (stage / "BUILD_INFO.md").write_text(
            f"# Human Host text reference\n\nSteam build ID: {build}\n\n"
            f"Application version: {version['version'] or 'unknown'} (Catalog/game-version.json)\n\n"
            f"Decompiled assemblies: {sum(a['decompiled'] for a in assembly_manifest)}\n\n"
            f"Assembly scope: {'explicit subset' if options.assemblies else 'all non-framework managed assemblies'}\n\n"
            "Catalog/ contains serialized gameplay fields, object identities, source hashes, reference resolution, and generated views.\n"
            "Start with Catalog/views/LOOT.md, Catalog/views/object-index.jsonl, and Catalog/coverage.json.\n\n"
            "Media and bulk engine payloads are cataloged without exporting their bodies. Native engine modules are inventoried, not reconstructed as C#.\n"
            "See the owning workspace's docs/GAME_CODEBASE.md for coverage and reference semantics.\n\n"
            "Generated reference for local research. Do not edit or redistribute.\n", encoding="utf-8")
        (stage / ".gitignore").write_text("**/obj/\n**/bin/\n.vs/\n*.user\n*.dll\n*.pdb\n*.exe\n", encoding="utf-8")
        for path in stage.rglob("*"):
            if path.is_file() and path.name != ".gitignore" and path.suffix not in {".cs", ".json", ".jsonl", ".md", ".txt"}:
                raise RuntimeError(f"Unexpected non-text output: {path}")
        inputs_stable(game, paths, stamps, steam)
        if tool_hashes != {p.relative_to(script_root.parent).as_posix(): tool_digest(p) for p in tool_files}:
            raise RuntimeError("Generator source changed during generation; retry with stable tools")
        with timing.measure("Git promotion"):
            snapshot.publish(f"Human Host build {build}: source and text catalog")
            timing.update(output_commit=None if options.no_git else snapshot.state["prepared_commit"])
        print(f"Complete: {output}", flush=True)
    timing.update(outcome="succeeded")


if __name__ == "__main__":
    # Supervise even direct CLI use, including in-process decoder stalls.
    if os.environ.get("HUMANHOST_CAPTURE_CHILD") == "1":
        try:
            main(Timing.resume(os.environ["HUMANHOST_CAPTURE_TIMING"]))
        except Exception as exc:
            cli_error(exc)
        os._exit(0)
    else:
        try:
            supervise_capture([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], CAPTURE_SECONDS)
        except Exception as exc:
            cli_error(exc)
        os._exit(0)
