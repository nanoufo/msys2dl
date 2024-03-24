import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Optional
from urllib.parse import quote

import zstandard as zstd
from rich.console import ConsoleRenderable
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)


def sanitize_file_path(path_str: str) -> PurePath:
    path = PurePath("./" + quote(path_str, safe="/"))
    if path.is_absolute():
        raise ValueError(f"Path must be relative: {path_str}")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"Path must not contain ..: {path_str}")
    return path


class AppProgress(Progress):
    def get_renderables(self) -> Iterable[ConsoleRenderable]:
        for task in self.tasks:
            progress_type = task.fields.get("progress_type")
            if progress_type == "simple" or progress_type is None:
                self.columns = (
                    TextColumn("[progress.description]{task.description}"),
                    MofNCompleteColumn(),
                    BarColumn(),
                    TimeElapsedColumn(),
                )
            if progress_type == "download":
                self.columns = (
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=None),
                    "•",
                    DownloadColumn(),
                )
            yield self.make_tasks_table([task])


def decompress_zst(inp: bytes) -> bytes:
    decompressor = zstd.ZstdDecompressor()
    stream_reader = decompressor.stream_reader(inp)
    return stream_reader.read()


def run_subprocess(command: list[str]) -> str:
    try:
        p = subprocess.run(
            command,
            check=False,
            encoding="utf-8",
            errors="ignore",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if p.returncode != 0:
            raise AppError(
                f"{command[0]} exited with code {p.returncode}", additional_info=["output: " + p.stdout]
            )
    except FileNotFoundError:
        raise AppError(f"no {command[0]} found in PATH")
    else:
        return p.stdout


@dataclass
class FileBlueprint:
    name: str
    content: bytes

    def write_to_dir(self, path: Path) -> None:
        (path / self.name).write_bytes(self.content)


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        additional_info: list[str] | None = None,
        wrapped: Optional["AppError"] = None,
    ):
        super().__init__()
        self.wrapped = wrapped
        self.message = message
        self.additional_info = list(additional_info or [])

    def display(self) -> str:
        message = ""
        combined_info_lines = []
        ex: AppError | None = self
        while ex is not None:
            if message != "":
                message += ": "
            message += ex.message
            combined_info_lines.extend(ex.additional_info)
            ex = ex.wrapped
        return "\n".join([message, *combined_info_lines])

    @classmethod
    def wrap(cls, message: str, other: "AppError") -> "AppError":
        return cls(message=message, wrapped=other)
