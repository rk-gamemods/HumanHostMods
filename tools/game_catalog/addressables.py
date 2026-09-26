"""Decode the compact JSON catalog layout used by the installed Addressables DLL."""
import base64
import json
import struct


def read_object(data, offset):
    kind = data[offset]
    offset += 1
    if kind in (0, 1):
        length, = struct.unpack_from("<i", data, offset)
        return data[offset + 4:offset + 4 + length].decode("ascii" if kind == 0 else "utf-16-le")
    if kind in (2, 3, 4):
        return struct.unpack_from({2: "<H", 3: "<I", 4: "<i"}[kind], data, offset)[0]
    if kind in (5, 6):
        length = data[offset]
        return data[offset + 1:offset + 1 + length].decode("ascii")
    if kind == 7:
        length = data[offset]
        assembly = data[offset + 1:offset + 1 + length].decode("ascii")
        offset += length + 1
        length = data[offset]
        cls = data[offset + 1:offset + 1 + length].decode("ascii")
        offset += length + 1
        length, = struct.unpack_from("<i", data, offset)
        return {"assembly": assembly, "class": cls,
                "value": json.loads(data[offset + 4:offset + 4 + length].decode("utf-16-le"))}
    raise ValueError(f"Unsupported Addressables object kind {kind}")


def decode(catalog):
    buckets = base64.b64decode(catalog["m_BucketDataString"], validate=True)
    key_data = base64.b64decode(catalog["m_KeyDataString"], validate=True)
    entries = base64.b64decode(catalog["m_EntryDataString"], validate=True)
    extra = base64.b64decode(catalog["m_ExtraDataString"], validate=True)
    count, = struct.unpack_from("<i", buckets)
    keys, bucket_entries, offset = [], [], 4
    for _ in range(count):
        key_offset, length = struct.unpack_from("<ii", buckets, offset)
        offset += 8
        keys.append(read_object(key_data, key_offset))
        bucket_entries.append(list(struct.unpack_from(f"<{length}i", buckets, offset)))
        offset += length * 4
    entry_count, = struct.unpack_from("<i", entries)
    if len(entries) != 4 + entry_count * 28:
        raise ValueError("Unexpected Addressables entry layout")
    aliases = [[] for _ in range(entry_count)]
    for key, indices in zip(keys, bucket_entries):
        for i in indices:
            aliases[i].append(key)
    result = []
    for i in range(entry_count):
        internal, provider, dependency, dependency_hash, extra_offset, primary, resource_type = struct.unpack_from("<7i", entries, 4 + i * 28)
        path = catalog["m_InternalIds"][internal]
        prefix, separator, suffix = path.rpartition("#")
        if separator and prefix.isdecimal():
            path = catalog["m_InternalIdPrefixes"][int(prefix)] + suffix
        result.append({"entry": i, "internal_id": path,
                       "primary_key": keys[primary], "keys": aliases[i],
                       "provider": catalog["m_ProviderIds"][provider],
                       "resource_type": catalog["m_resourceTypes"][resource_type],
                       "dependency_key": keys[dependency] if dependency >= 0 else None,
                       "dependency_entries": bucket_entries[dependency] if dependency >= 0 else [],
                       "dependency_hash": dependency_hash,
                       "extra": read_object(extra, extra_offset) if extra_offset >= 0 else None})
    return result
