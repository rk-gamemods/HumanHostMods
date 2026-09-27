"""Independently audit the current capture's version against catalog and input bytes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def contained(root, relative):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Version evidence escaped its source root")
    return path


def check(source, game):
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"]):
        raise ValueError("Capture has uncommitted changes")
    catalog = source / "Catalog"
    metadata = json.loads((catalog / "game-version.json").read_bytes())
    assert metadata["schema"] == 1 and metadata["status"] == "recorded"
    assert len(metadata["evidence"]) == 1
    evidence = metadata["evidence"][0]
    assert evidence["field"] == "/bundleVersion"
    key = evidence["object_id"].rsplit("#", 1)[0]
    path = contained(catalog / "objects", key.replace("::", "/") + ".jsonl")
    with path.open(encoding="utf-8") as stream:
        records = [record for record in map(json.loads, stream) if record["id"] == evidence["object_id"]]
    assert len(records) == 1 and records[0]["type"] == "PlayerSettings"
    assert records[0]["fields"]["bundleVersion"] == metadata["version"]
    with (catalog / "serialized-files.jsonl").open(encoding="utf-8") as stream:
        sources = [record for record in map(json.loads, stream) if record["id"] == key]
    assert len(sources) == 1 and "Human Host_Data/" + sources[0]["source"] == evidence["source_path"]
    with (catalog / "inputs.jsonl").open(encoding="utf-8") as stream:
        inputs = [record for record in map(json.loads, stream) if record["path"] == evidence["source_path"]]
    assert len(inputs) == 1 and inputs[0]["sha256"] == evidence["source_sha256"]
    installed = contained(game, evidence["source_path"])
    with installed.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == evidence["source_sha256"]
    return {"status": "passed", "version": metadata["version"], "evidence": evidence,
            "source_commit": subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"]).decode().strip(),
            "scope": "Captured PlayerSettings field, source mapping, input inventory and installed input hash; no gameplay verification"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--game", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.source.resolve(), args.game.resolve()), indent=2))
