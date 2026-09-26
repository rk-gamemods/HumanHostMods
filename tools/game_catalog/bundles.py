"""Read UnityFS members on demand. Never materialize resource streams on disk."""
import bisect
import collections
import io
import struct

from UnityPy.helpers.CompressionHelper import decompress_lz4, decompress_lzma


def unpack(stream, fmt):
    size = struct.calcsize(fmt)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated UnityFS data")
    return struct.unpack(fmt, data)


def cstring(stream):
    result = bytearray()
    while True:
        char = stream.read(1)
        if not char:
            raise ValueError("Unterminated UnityFS string")
        if char == b"\0":
            return result.decode("utf-8")
        result.extend(char)


def decompress(data, size, flags):
    mode = flags & 63
    if mode == 0:
        result = data
    elif mode == 1:
        result = decompress_lzma(data)
    elif mode in (2, 3):
        result = decompress_lz4(data, size)
    else:
        raise ValueError(f"Unsupported UnityFS compression: {mode}")
    if len(result) != size:
        raise ValueError(f"UnityFS block size mismatch: {len(result)} != {size}")
    return result


class Bundle:
    def __init__(self, stream):
        self.stream = stream
        stream.seek(0)
        if cstring(stream) != "UnityFS":
            raise ValueError("Expected UnityFS signature")
        version, = unpack(stream, ">I")
        self.player_version = cstring(stream)
        self.engine_version = cstring(stream)
        size, compressed, uncompressed, flags = unpack(stream, ">qIII")
        stream.seek(0, 2)
        if stream.tell() != size:
            raise ValueError("UnityFS file size mismatch")
        # The installed game uses format 6/7/8 with Unity 2022 alignment rules.
        stream.seek(8 + 4 + len(self.player_version) + 1 + len(self.engine_version) + 1 + 20)
        if version >= 7:
            stream.seek((-stream.tell()) % 16, 1)
        if flags & ~0x3FF:
            raise ValueError(f"Unsupported UnityFS flags {flags:#x}")
        position = stream.tell()
        if flags & 0x80:
            stream.seek(size - compressed)
        info = io.BytesIO(decompress(stream.read(compressed), uncompressed, flags))
        data_start = position if flags & 0x80 else stream.tell()
        if flags & 0x200:
            data_start += (-data_start) % 16
        info.seek(16)
        block_count, = unpack(info, ">i")
        self.blocks, self.starts = [], []
        raw_start, packed_start = 0, data_start
        for _ in range(block_count):
            raw, packed, block_flags = unpack(info, ">IIH")
            self.starts.append(raw_start)
            self.blocks.append((packed_start, packed, raw, block_flags))
            packed_start += packed
            raw_start += raw
        self.length = raw_start
        member_count, = unpack(info, ">i")
        self.members = []
        for _ in range(member_count):
            offset, member_size, member_flags = unpack(info, ">qqI")
            name = cstring(info)
            if offset < 0 or member_size < 0 or offset + member_size > self.length:
                raise ValueError(f"Invalid bundle member bounds: {name}")
            self.members.append((name, offset, member_size, member_flags))
        self.cache = collections.OrderedDict()

    def read(self, position, size):
        result = bytearray()
        while size:
            index = bisect.bisect_right(self.starts, position) - 1
            if index < 0 or position >= self.length:
                raise ValueError("Read outside UnityFS data")
            start, packed, raw, flags = self.blocks[index]
            local = position - self.starts[index]
            take = min(size, raw - local)
            if flags & 63 == 0:
                # Uncompressed blocks can contain gigabytes. Read only the field requested.
                self.stream.seek(start + local)
                chunk = self.stream.read(take)
            else:
                if index not in self.cache:
                    self.stream.seek(start)
                    self.cache[index] = decompress(self.stream.read(packed), raw, flags)
                    while len(self.cache) > 8:
                        self.cache.popitem(last=False)
                self.cache.move_to_end(index)
                chunk = self.cache[index][local:local + take]
            if len(chunk) != take:
                raise ValueError("Truncated UnityFS block")
            result.extend(chunk)
            position += take
            size -= take
        return bytes(result)


class MemberStream(io.RawIOBase):
    def __init__(self, bundle, offset, size):
        self.bundle, self.offset, self.size, self.position = bundle, offset, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else (self.position if whence == 1 else self.size) + offset
        if position < 0 or position > self.size:
            raise ValueError("Seek outside bundle member")
        self.position = position
        return position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        data = self.bundle.read(self.offset + self.position, size)
        self.position += len(data)
        return data
