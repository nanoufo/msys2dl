import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from subprocess import CompletedProcess

from msys2downloader.package import PackageFile, Package
from msys2downloader.utilities import FileBlueprint, DisplayableError


class DebBuildError(DisplayableError):
    pass


class DpkgDebSubprocessError(DebBuildError):
    def __init__(self, process: CompletedProcess[str]) -> None:
        super().__init__("")
        self.message = "dpkg-deb failed with exit code {}".format(process.returncode)
        self.process = process

    def display(self):
        print(self.message)
        if self.process.stdout:
            print("stdout: " + self.process.stdout.strip())
        if self.process.stderr:
            print("stderr: " + self.process.stderr.strip())


class DebBuilder:
    _dir_rewrites = {
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
                    raise DebBuildError(f"unexpected ${dst} in MSYS2 package")
                if src_path.exists():
                    shutil.move(src_path, dst_path)

            # Perform directory renames in pkg-config files
            self._alter_paths_in_pkgconfig_files(self, build_dir)

            # Generate control file
            single_line_description = package.description.replace("\n", " ")
            control_file_content = textwrap.dedent(
                f"""
               Package: {deb_name}
               Version: 1.0.0
               Architecture: all
               Maintainer: unknown
               Description: {single_line_description}
               Recommends: {', '.join(self._generate_package_name(d) for d in package.dependencies)}
               
               """
            )
            (build_dir / "DEBIAN").mkdir(parents=True)
            (build_dir / "DEBIAN/control").write_text(control_file_content, encoding="utf-8")

            # Run dpkg-deb
            deb_file_name = f"{deb_name}_{package.version}_all.deb"
            deb_path = tdir / deb_file_name
            try:
                result = subprocess.run(
                    ["dpkg-deb", "--root-owner-group", "-b", build_dir, deb_path],
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except FileNotFoundError:
                raise DebBuildError("dpkg-deb not found in PATH")
            if result.returncode != 0:
                raise DpkgDebSubprocessError(result)
            return FileBlueprint(name=deb_file_name, content=deb_path.read_bytes())

    @staticmethod
    def _alter_paths_in_pkgconfig_files(self, root: Path):
        for pc_file in root.rglob('**/*.pc'):
            content = pc_file.read_text('utf-8')
            for src, dst in self._dir_rewrites.items():
                content = content.replace("/" + src, "/" + dst)
            pc_file.write_text(content, 'utf-8')

    @staticmethod
    def _generate_package_name(package: Package):
        return f"{package.short_name}-msys2-{package.environment.name}"
