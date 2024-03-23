import io
import tarfile
from pathlib import Path
from typing import Iterable, Optional

from msys2downloader.download.download_request import DownloadRequest
from msys2downloader.package import Environment, Package
from msys2downloader.utilities import decompress_zst, AppError


class PackageDatabase:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._packages_dict: dict[str, Package] = {}
        self.reload()

    def make_download_requests(
        self, base_url: str, environments: Iterable[Environment]
    ) -> list[DownloadRequest]:
        return [
            DownloadRequest(name=e.name, url=base_url + e.database_download_path, dest=self._database_file(e))
            for e in environments
        ]

    def get(self, full_name: str) -> Optional[Package]:
        return self._packages_dict.get(full_name)

    def get_or_raise(self, full_name: str) -> Package:
        package = self.get(full_name)
        if package is None:
            raise AppError(f"Package {full_name} not found")
        return package

    def get_all_or_raise(self, full_names: Iterable[str]) -> list[Package]:
        return [self.get_or_raise(name) for name in full_names]

    def reload(self) -> None:
        self._packages_dict = {}
        for env in Environment.all:
            db_file = self._database_file(env)
            if db_file.exists():
                self._packages_dict.update({p.name: p for p in self._load_from_file(env, db_file)})
        for p in self._packages_dict.values():
            p.populate_dependencies(self._packages_dict)

    def _database_file(self, environment: Environment) -> Path:
        return self._root / (environment.name + ".db")

    @staticmethod
    def _load_from_file(env: Environment, path: Path) -> list[Package]:
        content = decompress_zst(path.read_bytes())
        tar = tarfile.open(fileobj=io.BytesIO(content), mode="r")
        packages = []
        for member in tar.getmembers():
            file = tar.extractfile(member)
            if file and member.name.endswith("/desc"):
                packages.append(Package.from_desc(file.read().decode("utf-8"), environment=env))
        return packages


class PackageNameResolver:
    def __init__(self, default_env: Optional[Environment] = None):
        self.default_env = default_env

    def resolve_full_name(self, name: str) -> str:
        if Environment.by_package_name(name):
            # It is full package name
            return name
        elif self.default_env:
            return self.default_env.package_name_prefix + name
        else:
            raise AppError(
                f"package '{name}' does not contain environment prefix, and no default environment set"
            )

    def resolve_full_names(self, names: Iterable[str]) -> list[str]:
        return [self.resolve_full_name(name) for name in names]
