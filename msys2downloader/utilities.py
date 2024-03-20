from dataclasses import dataclass
from pathlib import Path

import zstandard as zstd


def decompress_zst(inp: bytes) -> bytes:
    decompressor = zstd.ZstdDecompressor()
    stream_reader = decompressor.stream_reader(inp)
    return stream_reader.read()


@dataclass
class FileBlueprint:
    name: str
    content: bytes

    def write_to_dir(self, path: Path):
        (path / self.name).write_bytes(self.content)


class DisplayableError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def display(self):
        print(self.message)
