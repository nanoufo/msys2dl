import sys
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path

from msys2downloader.application import Application
from msys2downloader.deb_builder import DebBuilder
from msys2downloader.package import Environment
from msys2downloader.package_database import PackageNameResolver
from msys2downloader.progress import ProgressCounter
from msys2downloader.utilities import AppError


# Enum for mode
class Mode(Enum):
    EXTRACT = "extract"
    MAKE_DEB = "make-deb"


def _run_app(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = ArgumentParser()
    Application.configure_parser(parser)
    parser.add_argument("--extract", dest="mode", action="store_const", const=Mode.EXTRACT, default=False)
    parser.add_argument("--make-deb", dest="mode", action="store_const", const=Mode.MAKE_DEB, default=False)
    parser.add_argument("--output", "-o", metavar="OUTPUT_DIRECTORY", type=Path)
    parser.add_argument(
        "--env",
        default=None,
        choices=[n for e in Environment.all for n in [e.name, *e.alias]],
    )
    parser.add_argument("--no-deps", action="store_true", default=False)
    parser.add_argument("--exclude", metavar="PACKAGE", type=str, nargs="+", default=[])
    parser.add_argument("packages", metavar="PACKAGE", nargs="+")
    args = parser.parse_args(argv)

    # Setup
    mode = args.mode
    output = args.output
    if not args.mode:
        raise AppError("No --extract or --make-deb specified")
    with_dependencies = not args.no_deps

    # Initialize
    with Application(args) as app:
        # Resolve full package names
        default_env = Environment.by_name_or_raise(args.env) if args.env else None
        include = PackageNameResolver(default_env).resolve_full_names(args.packages)
        exclude = PackageNameResolver(default_env).resolve_full_names(args.exclude)
        environments = {Environment.by_package_name_or_raise(name) for name in (include + exclude)}
        # Update keys
        app.update_keys()
        # Download package databases
        app.download_databases(environments)
        # Download packages
        package_set = app.resolve_package_set(include, exclude, with_dependencies)
        package_files = app.download_packages(package_set)
        # Do something with downloaded packages
        if mode == Mode.EXTRACT:
            description = "Extracting packages"
        elif mode == Mode.MAKE_DEB:
            description = "Building deb packages"
        with ProgressCounter(len(package_files), description=description) as progress:
            for package_file in package_files:
                if mode == Mode.EXTRACT:
                    package_file.extract(output)
                    print("Extracted", str(package_file.metadata))
                elif mode == Mode.MAKE_DEB:
                    deb_file_blueprint = DebBuilder().build_for(package_file)
                    deb_file_blueprint.write_to_dir(output)
                    print(f"Generated {deb_file_blueprint.name}")
                progress.increment(1)


def main(argv: list[str] | None = None) -> None:
    try:
        _run_app(argv)
    except AppError as e:
        print(e.display())
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
