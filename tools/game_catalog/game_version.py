"""Select the Unity application version and its evidence from captured metadata."""


def capture(records, sources, inputs):
    candidates = [record for record in records if record["type"] == "PlayerSettings"]
    result = {"schema": 1, "version": None, "status": "unknown", "evidence": []}
    if len(candidates) != 1:
        return {**result, "reason": "missing-player-settings" if not candidates else "ambiguous-player-settings"}
    record = candidates[0]
    version = record.get("fields", {}).get("bundleVersion")
    if not isinstance(version, str) or not version or len(version) > 128 or version.strip() != version or not version.isprintable():
        return {**result, "reason": "missing-or-invalid-bundle-version"}
    source = "Human Host_Data/" + sources[record["id"].rsplit("#", 1)[0]]
    matches = [item for item in inputs if item["path"] == source]
    if len(matches) != 1:
        raise ValueError("PlayerSettings source is missing or duplicated in the input inventory")
    return {**result, "status": "recorded", "version": version, "evidence": [{
        "source_path": source, "source_sha256": matches[0]["sha256"],
        "object_id": record["id"], "field": "/bundleVersion"}]}
