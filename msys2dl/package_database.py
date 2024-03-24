import io
import tarfile
from collections.abc import Iterable
from pathlib import Path

from msys2dl.download.download_request import DownloadRequest
from msys2dl.package import Environment, Package
from msys2dl.utilities import AppError, decompress_zst


class PackageDatabase:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._packages_name_dict: dict[str, "Package"] = {}
        self._packages_provides_dict: dict[str, list["Package"]] = {}
        self.reload()

    def make_download_requests(
        self, base_url: str, environments: Iterable[Environment]
    ) -> list[DownloadRequest]:
        return [
            DownloadRequest(name=e.name, url=base_url + e.database_download_path, dest=self._database_file(e))
            for e in environments
        ]

    def get(self, full_name: str) -> Package | None:
        return self._packages_name_dict.get(full_name)

    def get_or_raise(self, full_name: str) -> Package:
        package = self.get(full_name)
        if package is None:
            raise AppError(f"Package {full_name} not found")
        return package

    def get_all_or_raise(self, full_names: Iterable[str]) -> list[Package]:
        return [self.get_or_raise(name) for name in full_names]

    def reload(self) -> None:
        self._packages_name_dict = {}
        self._packages_provides_dict = {}
        # Load packages
        all_packages = []
        for env in Environment.all:
            db_file = self._database_file(env)
            if db_file.exists():
                all_packages.extend(self._load_from_file(env, db_file))
        # Populate lookup dictionaries
        for p in all_packages:
            # Add package to name lookup
            self._packages_name_dict[p.name] = p
            # Add package to provides lookup
            p_provides = {p.name, *p.provides}
            for p_name in p_provides:
                self._packages_provides_dict.setdefault(p_name, []).append(p)
        # Populate dependencies
        for p in all_packages:
            p.resolve_package_links(self._packages_name_dict, self._packages_provides_dict)

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
    def __init__(self, default_env: Environment | None = None):
        self.default_env = default_env

    def resolve_full_name(self, name: str) -> str:
        if Environment.by_package_name(name):
            # It is full package name
            return name
        if self.default_env:
            return self.default_env.package_name_prefix + name
        raise AppError(
            f"package '{name}' does not contain environment prefix, and no default environment set"
        )

    def resolve_full_names(self, names: Iterable[str]) -> list[str]:
        return [self.resolve_full_name(name) for name in names]
