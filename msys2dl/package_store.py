import io
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tarfile import TarFile, TarInfo, data_filter

from msys2dl.download.download_request import DownloadRequest
from msys2dl.package import Package
from msys2dl.utilities import decompress_zst, sanitize_file_path


@dataclass
class PackageFile:
    metadata: Package
    path: Path

    def extract(self, dst: Path) -> None:
        def need_to_extract(member: TarInfo, dest_path: str) -> TarInfo | None:
            if not data_filter(member, dest_path):
                return None
            if member.name.startswith("."):
                # No .MTREE and other pacman files
                return None
            return member

        self.as_tar_file().extractall(filter=need_to_extract, path=dst)

    def as_tar_file(self) -> TarFile:
        tar_bytes = decompress_zst(self.path.read_bytes())
        return tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r")


class PackageStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_package_file(self, package: Package) -> PackageFile:
        return PackageFile(package, self.path_for_package(package))

    def path_for_package(self, package: Package) -> Path:
        return self.root / package.environment.name / sanitize_file_path(package.filename)

    def make_download_request(self, base_url: str, package: Package) -> DownloadRequest:
        return DownloadRequest(
            name=str(package),
            url=base_url + package.download_path,
            dest=self.path_for_package(package),
            expected_size=package.compressed_size,
        )

    def make_download_requests(self, base_url: str, packages: Iterable[Package]) -> list[DownloadRequest]:
        return [self.make_download_request(base_url, package) for package in packages]
