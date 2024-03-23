from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DownloadRequest:
    name: str
    url: str
    dest: Path
    expected_size: Optional[int] = None

    @property
    def sig_url(self) -> str:
        return self.url + ".sig"

    @property
    def sig_dest(self) -> Path:
        return self.dest.with_name(self.dest.name + ".sig")

    @property
    def partial_dest(self) -> Path:
        return self.dest.with_name(self.dest.name + ".part")
