import re
from collections import deque
from dataclasses import dataclass, field
from typing import ClassVar, List, Optional, Iterable, Iterator


@dataclass
class Environment:
    name: str
    alias: list[str]
    path_prefix: str
    package_name_prefix: str

    all: ClassVar[List["Environment"]] = []

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Environment):
            return False
        return self.name == other.name

    @property
    def database_download_path(self) -> str:
        return f"{self.path_prefix}/{self.name}/{self.name}.db"

    def package_download_path(self, filename: str) -> str:
        return f"{self.path_prefix}/{self.name}/{filename}"

    @staticmethod
    def by_name_or_raise(name: str) -> "Environment":
        env = Environment.by_name(name)
        if env:
            return env
        raise ValueError(f"Invalid environment name: {name}")

    @staticmethod
    def by_name(name: str) -> Optional["Environment"]:
        return next(
            (env for env in Environment.all if (env.name == name) or (name in env.alias)),
            None,
        )

    @staticmethod
    def by_package_name(pname: str) -> Optional["Environment"]:
        return next(
            (env for env in Environment.all if pname.startswith(env.package_name_prefix)),
            None,
        )

    @staticmethod
    def by_package_name_or_raise(pname: str) -> "Environment":
        env = Environment.by_package_name(pname)
        if env:
            return env
        raise ValueError(f"No environment in package name: {pname}")


Environment.all = [
    Environment("clangarm64", [], "/mingw", "mingw-w64-clang-aarch64-"),
    Environment("clang32", [], "/mingw", "mingw-w64-clang-i686-"),
    Environment("clang64", [], "/mingw", "mingw-w64-clang-x86_64-"),
    Environment("mingw32", [], "/mingw", "mingw-w64-i686-"),
    Environment("mingw64", [], "/mingw", "mingw-w64-x86_64-"),
    Environment("ucrt64", [], "/mingw", "mingw-w64-ucrt-x86_64-"),
]


@dataclass
class Package:
    environment: Environment
    name: str
    description: str
    version: str
    filename: str
    compressed_size: Optional[int]
    dependencies_str: list[str]
    dependencies: list["Package"] = field(default_factory=lambda: [], repr=False)
    unknown_dependencies: list[str] = field(default_factory=lambda: [])

    def __str__(self) -> str:
        return f"{self.name}-{self.version}"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, rhs: object) -> bool:
        if not isinstance(rhs, Package):
            return False
        return self.name == rhs.name

    @property
    def download_path(self) -> str:
        return self.environment.package_download_path(self.filename)

    @property
    def short_name(self) -> str:
        return self.name.removeprefix(self.environment.package_name_prefix)

    def populate_dependencies(self, packages_dict: dict[str, "Package"]) -> None:
        self.dependencies = []
        for dep in self.dependencies_str:
            dep_name = re.split(r"[<>=]", dep)[0]
            if dep_name in packages_dict:
                self.dependencies.append(packages_dict[dep_name])
            else:
                self.unknown_dependencies.append(dep_name)

    @staticmethod
    def from_desc(desc: str, environment: Environment) -> "Package":
        sections = {}
        lines = desc.strip().split("\n")
        current_section_name = None
        current_section_lines = []
        for line in lines:
            if not line:
                continue
            if line.startswith("%") and line.endswith("%"):
                if current_section_name:
                    sections[current_section_name] = "\n".join(current_section_lines)
                    current_section_lines = []
                current_section_name = line[1:-1]
            else:
                current_section_lines.append(line)
        if current_section_name:
            sections[current_section_name] = "\n".join(current_section_lines)

        return Package(
            name=sections["NAME"],
            version=sections["VERSION"],
            filename=sections["FILENAME"],
            compressed_size=int(sections["CSIZE"]) if "CSIZE" in sections else None,
            description=sections.get("DESC", ""),
            dependencies_str=[d for d in sections.get("DEPENDS", "").split("\n") if d],
            environment=environment,
        )


class PackageSet:
    def __init__(self, packages: Optional[Iterable[Package]] = None) -> None:
        self._set = set(packages) if packages is not None else set()

    def add(self, package: Package) -> bool:
        if package in self._set:
            return False
        self._set.add(package)
        return True

    def add_dependencies_recursively(self, exclude: Optional[Iterable[Package]]) -> None:
        q = deque(self._set)
        while q:
            package = q.pop()
            for dep in package.dependencies:
                if (exclude is None or dep not in exclude) and self.add(dep):
                    q.append(dep)

    def __add__(self, other: Iterable[Package]) -> "PackageSet":
        return PackageSet(self._set.union(other))

    def __sub__(self, other: Iterable[Package]) -> "PackageSet":
        return PackageSet(self._set.difference(other))

    def __iter__(self) -> Iterator[Package]:
        return iter(self._set)

    def __len__(self) -> int:
        return len(self._set)
