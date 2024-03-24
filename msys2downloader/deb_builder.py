import re
import shutil
import tempfile
import textwrap
from pathlib import Path
from typing import ClassVar

from msys2downloader.package import Package
from msys2downloader.package_store import PackageFile
from msys2downloader.utilities import AppError, FileBlueprint, run_subprocess


class DebBuilder:
    _dir_rewrites: ClassVar[dict[str, str]] = {
        "mingw64": "usr/x86_64-w64-mingw32",
        "mingw32": "usr/i686-w64-mingw32",
    }

    def build_for(self, msys2_package_file: PackageFile) -> FileBlueprint:
        package = msys2_package_file.metadata

        with tempfile.TemporaryDirectory(prefix=msys2_package_file.metadata.name, suffix="build") as tdir_str:
            tdir = Path(tdir_str)

            # Create build directory with the correct name for dpkg-deb
            deb_name = self._generate_package_name(package)
            build_dir = Path(tdir) / f"{deb_name}-${msys2_package_file.metadata.version}.name"

            # Extract package contents & perform directory renames
            msys2_package_file.extract(build_dir)

            # Perform directory renames
            for src, dst in self._dir_rewrites.items():
                src_path = build_dir / src
                dst_path = build_dir / dst
                if dst_path.exists():
                    raise AppError(f"unexpected directory /${dst} in MSYS2 package")
                if src_path.exists():
                    shutil.move(src_path, dst_path)

            # Perform directory renames in pkg-config files
            self._alter_paths_in_pkgconfig_files(build_dir)

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
               Recommends: {', '.join(self._generate_package_name(d) for d in package.dependencies)}

               """
            )
            (build_dir / "DEBIAN").mkdir(parents=True)
            (build_dir / "DEBIAN/control").write_text(control_file_content, encoding="utf-8")

            # Run dpkg-deb
            deb_file_name = f"{deb_name}_{version}_all.deb"
            deb_path = tdir / deb_file_name
            run_subprocess(["dpkg-deb", "--root-owner-group", "-b", str(build_dir), str(deb_path)])
            return FileBlueprint(name=deb_file_name, content=deb_path.read_bytes())

    @classmethod
    def _alter_paths_in_pkgconfig_files(cls, root: Path) -> None:
        for pc_file in root.rglob("**/*.pc"):
            content = pc_file.read_text("utf-8")
            for src, dst in cls._dir_rewrites.items():
                content = content.replace("/" + src, "/" + dst)
            pc_file.write_text(content, "utf-8")

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
