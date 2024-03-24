import re
import tempfile
import textwrap
from argparse import Namespace
from pathlib import Path
from typing import ClassVar

from msys2dl.application import Application
from msys2dl.commands.command import Command
from msys2dl.commands.output_dir_mixin import OutputDirMixin
from msys2dl.commands.package_set_mixin import PackageSetMixin
from msys2dl.package import Package
from msys2dl.package_store import PackageFile
from msys2dl.utilities import run_subprocess


class CommandMakeDeb(PackageSetMixin, OutputDirMixin, Command):
    command_name: ClassVar[str] = "make-deb"
    action_title = "Making debian packages"

    def __init__(self, app: Application, args: Namespace):
        super().__init__(app, args)

    def do_package_action(self, package_file: PackageFile) -> None:
        deb_path = DebBuilder().build(package_file, self.output_dir)
        print(f"Generated {deb_path.name}")


class DebBuilder:
    def build(self, msys2_package_file: PackageFile, output_dir: Path) -> Path:
        package = msys2_package_file.metadata

        with tempfile.TemporaryDirectory(prefix=msys2_package_file.metadata.name, suffix="build") as tdir_str:
            tdir = Path(tdir_str)

            # Create build directory with the correct name for dpkg-deb
            deb_name = self._generate_package_name(package)
            build_dir = Path(tdir) / f"{deb_name}-${msys2_package_file.metadata.version}.name"

            # Extract package contents & perform directory renames
            msys2_package_file.extract(build_dir)

            # Generate control file
            single_line_description = package.description.replace("\n", " ")
            version = self._convert_package_version(package.version)
            control_file_content = textwrap.dedent(
                f"""
               Package: {deb_name}
               Version: {version}
               Architecture: all
               Maintainer: unknown
               Description: {single_line_description}
               Recommends: {', '.join(self._generate_package_name(d) for d in package.dependencies if isinstance(d, Package))}

               """
            )
            (build_dir / "DEBIAN").mkdir(parents=True)
            (build_dir / "DEBIAN/control").write_text(control_file_content, encoding="utf-8")

            # Run dpkg-deb
            deb_file_name = f"{deb_name}_{version}_all.deb"
            deb_path = output_dir / deb_file_name
            run_subprocess(["dpkg-deb", "-Znone", "--root-owner-group", "-b", str(build_dir), str(deb_path)])
            return deb_path

    @staticmethod
    def _generate_package_name(package: Package) -> str:
        return f"{package.short_name}-msys2-{package.environment.name}"

    @staticmethod
    def _convert_package_version(version: str) -> str:
        # Change version to be compatible with Debian package system
        version = version.replace("-", ".")
        version = re.sub(r"[^a-zA-Z0-9.+~]", "", version)
        if not version[0].isdigit():
            version = "0." + version
        return version
