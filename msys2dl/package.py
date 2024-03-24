import re
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import ClassVar, Optional

from msys2dl.utilities import AppError


@dataclass
class Environment:
    name: str
    alias: list[str]
    path_prefix: str
    package_name_prefix: str

    all: ClassVar[list["Environment"]] = []

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


class PackageAlternatives:
    def __init__(self, provides: str, packages: Iterable["Package"]) -> None:
        self.provides = provides
        self.packages = tuple(packages)

    def __repr__(self) -> str:
        return f"Alternatives(provides='{self.provides}', packages={self.packages})"

    def __str__(self) -> str:
        return f"providers for {self.provides} (" + ", ".join(p.name for p in self.packages) + ")"


@dataclass
class Package:
    environment: Environment
    name: str
    description: str
    version: str
    filename: str
    compressed_size: int | None
    provides: list[str]
    dependencies_str: list[str]
    conflicts_str: list[str]
    conflicts: list["Package"] = field(default_factory=list, repr=False)
    dependencies: list["Package | PackageAlternatives"] = field(default_factory=list, repr=False)
    unknown_dependencies: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Package(name='{self.name}', version={self.version})"

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

    def resolve_package_links(
        self, name_dict: dict[str, "Package"], provides_dict: dict[str, list["Package"]]
    ) -> None:
        self.dependencies = []
        for dep in self.dependencies_str:
            if dep in provides_dict:
                provided_by = provides_dict[dep]
                self.dependencies.append(
                    provided_by[0] if len(provided_by) == 1 else PackageAlternatives(dep, provided_by)
                )
            else:
                self.unknown_dependencies.append(dep)
        for conflict_str in self.conflicts_str:
            if conflict_str in name_dict:
                self.conflicts.append(name_dict[conflict_str])

    @classmethod
    def from_desc(cls, desc: str, environment: Environment) -> "Package":
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
            conflicts_str=cls.parse_package_list(sections.get("CONFLICTS", "")),
            dependencies_str=cls.parse_package_list(sections.get("DEPENDS", "")),
            provides=cls.parse_package_list(sections.get("PROVIDES", "")),
            environment=environment,
        )

    @classmethod
    def parse_package_list(cls, text: str) -> list[str]:
        return [cls.strip_version_constraints(d) for d in text.split("\n") if d]

    @staticmethod
    def strip_version_constraints(name: str) -> str:
        return re.split(r"[<>=]", name)[0]


@dataclass
class PackageConflict:
    first: Package
    second: Package

    def __str__(self) -> str:
        return f"{self.first.name} and {self.second.name}"


class PackageSet:
    def __init__(self, packages: Iterable[Package] | None = None) -> None:
        self._set = set(packages) if packages is not None else set()

    def add(self, package: Package) -> bool:
        if package in self._set:
            return False
        self._set.add(package)
        return True

    def add_dependencies_recursively(self, exclude: Iterable[Package] | None) -> None:
        found_alternatives: set[PackageAlternatives] = set()
        q = deque(self._set)
        alternatives_q: deque[PackageAlternatives] = deque()
        while q or alternatives_q:
            if q:
                package = q.pop()
                for dep in package.dependencies:
                    if not isinstance(dep, PackageAlternatives):
                        # Normal dependency
                        if (exclude is None or dep not in exclude) and self.add(dep):
                            q.append(dep)
                    else:
                        # Alternatives present: postpone resolving them
                        # (maybe one of alternatives will be added as a normal dependency later)
                        if dep not in found_alternatives:
                            found_alternatives.add(dep)
                            alternatives_q.append(dep)
            else:
                # Need to choose from alternatives
                alternatives = alternatives_q.pop()
                chosen = next((alt for alt in alternatives.packages if alt in self._set), None)
                if chosen:
                    # already chosen
                    print(f"Alternatives: {chosen.name} is explicitly chosen from {alternatives}")
                else:
                    # select one
                    chosen = min(alternatives.packages, key=lambda p: p.name)
                    print(f"Alternatives: selecting {chosen.name} from {alternatives}")
                self.add(chosen)
                q.append(chosen)

    def find_conflicts(self) -> list[PackageConflict]:
        conflicts = []
        for p1 in self._set:
            for p2 in self._set:
                if p1 == p2 or p1.name > p2.name or (p2 not in p1.conflicts and p1 not in p2.conflicts):
                    continue

                conflicts.append(PackageConflict(p1, p2))
        return conflicts

    def check_for_conflicts(self) -> None:
        conflicts = self.find_conflicts()
        if conflicts:
            raise AppError(f"Package conflicts found: {', '.join(str(conflict) for conflict in conflicts)}")

    def __add__(self, other: Iterable[Package]) -> "PackageSet":
        return PackageSet(self._set.union(other))

    def __sub__(self, other: Iterable[Package]) -> "PackageSet":
        return PackageSet(self._set.difference(other))

    def __iter__(self) -> Iterator[Package]:
        return iter(self._set)

    def __len__(self) -> int:
        return len(self._set)
