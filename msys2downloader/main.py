import sys
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path
from typing import List, Optional

from alive_progress import alive_bar

from msys2downloader.deb_builder import DebBuilder
from msys2downloader.downloader import Downloader, DownloadCache
from msys2downloader.package import Environment, PackageSet
from msys2downloader.package_database import PackageNameResolver, PackageDatabase
from msys2downloader.utilities import DisplayableError


# Enum for mode
class Mode(Enum):
    EXTRACT = "extract"
    MAKE_DEB = "make-deb"


def _run_app(argv: Optional[List[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = ArgumentParser()
    parser.add_argument("--extract", dest="mode", action="store_const", const=Mode.EXTRACT, default=False)
    parser.add_argument("--make-deb", dest="mode", action="store_const", const=Mode.MAKE_DEB, default=False)
    parser.add_argument("--output", "-o", metavar="OUTPUT_DIRECTORY", type=Path, default=Path("."))
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--env",
        default=None,
        choices=[n for e in Environment.all for n in [e.name, *e.alias]],
    )
    parser.add_argument("--no-deps", action="store_true", default=False)
    parser.add_argument("--base-url", type=str, default="https://mirror.msys2.org")
    parser.add_argument("--exclude", metavar="PACKAGE", type=str, nargs="+", default=[])
    parser.add_argument("packages", metavar="PACKAGE", nargs="+")
    args = parser.parse_args(argv)

    # Setup
    mode = args.mode
    output = args.output
    if not args.mode:
        raise DisplayableError("No --extract or --make-deb specified")
    no_deps = args.no_deps
    cache_root = args.cache if args.cache_dir else Path("~/.cache/msys2-downloader").expanduser()
    cache = DownloadCache(cache_root)
    downloader = Downloader(args.base_url, cache)

    # Create output directory
    output.mkdir(parents=True, exist_ok=True)

    # Resolve full package names
    default_env = Environment.by_name_or_raise(args.env) if args.env else None
    name_resolver = PackageNameResolver(default_env)
    package_names = name_resolver.resolve_full_names(args.packages)
    excluded_package_names = name_resolver.resolve_full_names(args.exclude)
    package_environments = set(
        env for name in (package_names + excluded_package_names) if (env := Environment.by_package_name(name))
    )

    # Download package databases & find requested packages
    database = PackageDatabase(downloader)
    database.download_for_environments(package_environments)

    # Show warnings about unknown excluded packages
    excluded_packages = []
    for excluded_name in excluded_package_names:
        package = database.get(excluded_name)
        if package:
            excluded_packages.append(package)
        else:
            print(f"Warning: unknown excluded package '{excluded_name}'")

    requested_packages = PackageSet(database.get_all_or_raise(package_names)) - excluded_packages
    if not no_deps:
        requested_packages.add_dependencies_recursively(exclude=excluded_packages)

    # Download packages
    print("Downloading packages...")
    package_files = []
    with alive_bar(len(requested_packages), enrich_print=False) as bar:
        for p in requested_packages:
            bar.title = str(p)
            package_file = p.get_from_cache(cache)
            if package_file:
                print(f"{p} is cached")
                bar(1, skipped=True)
            else:
                package_file = p.download(downloader)
                bar(1)
                print(f"{p} downloaded")
            package_files.append(package_file)
        bar.title = "Done!"

    # Do something with downloaded packages
    if mode == Mode.EXTRACT:
        print("Extracting packages...")
    elif mode == Mode.MAKE_DEB:
        print("Building deb packages...")
    with alive_bar(len(requested_packages), enrich_print=False) as bar:
        for package_file in package_files:
            bar.title = str(package_file.metadata)
            if mode == Mode.EXTRACT:
                package_file.extract(output)
            elif mode == Mode.MAKE_DEB:
                DebBuilder().build_for(package_file).write_to_dir(output)
            bar(1)
        bar.title = "Done!"


def main(argv: Optional[List[str]] = None) -> None:
    try:
        _run_app(argv)
    except DisplayableError as e:
        e.display()
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
