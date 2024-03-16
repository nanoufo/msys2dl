import io
import sys
import tarfile
from argparse import ArgumentParser
from pathlib import Path
from tarfile import TarInfo, data_filter
from typing import List, Optional, Set

import zstandard as zstd

from msys2downloader.downloader import Cache, Downloader
from msys2downloader.package import Environment, Package


def decompress_zst(inp: bytes) -> bytes:
    decompressor = zstd.ZstdDecompressor()
    stream_reader = decompressor.stream_reader(inp)
    return stream_reader.read()


def load_package_database(downloader: Downloader, env: Environment) -> dict[str, Package]:
    # Download database file
    content = downloader.download(env.database_download_path)
    # Read database file
    content = decompress_zst(content)
    tar = tarfile.open(fileobj=io.BytesIO(content), mode="r")
    packages = []
    for member in tar.getmembers():
        file = tar.extractfile(member)
        if file and member.name.endswith("/desc"):
            packages.append(Package.from_desc(file.read().decode("utf-8"), environment=env))
    packages_dict = {p.name: p for p in packages}
    # Populate dependency links
    for package in packages:
        package.populate_dependencies(packages_dict)
    return packages_dict


def unpack(package_archive: bytes, target_root: Path) -> None:
    def need_to_extract(member: TarInfo, dest_path: str) -> Optional[TarInfo]:
        if not data_filter(member, dest_path):
            return None
        if member.name.startswith("."):
            # No .MTREE and other pacman files
            return None
        return member

    tar_bytes = decompress_zst(package_archive)
    tar = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r")
    tar.extractall(filter=need_to_extract, path=target_root)


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = ArgumentParser()
    parser.add_argument("--extract-root", type=Path, required=False)
    parser.add_argument("--cache", type=Path)
    parser.add_argument(
        "--env",
        default=None,
        choices=[n for e in Environment.all for n in [e.name, *e.alias]],
    )
    parser.add_argument("--no-deps", action="store_true", default=False)
    parser.add_argument("--base-url", type=str, default="https://mirror.msys2.org")
    parser.add_argument("packages", metavar="PACKAGE", nargs="+")
    args = parser.parse_args(argv)

    if not args.extract_root:
        print("No --extract-root provided, packages will be downloaded to cache")

    no_deps = args.no_deps
    cache_root = args.cache if args.cache else Path("~/.cache/msys2-downloader").expanduser()
    cache = Cache(cache_root)
    downloader = Downloader(args.base_url, cache)

    envs: list[Environment]
    if args.env:
        default_env = Environment.by_name_or_raise(args.env)
        envs = [default_env]
    else:
        default_env = None
        envs = [env for p in args.packages if (env := Environment.by_package_name(p))]

    if not envs:
        raise SystemExit("MSYS2 environment is not set. Provide one with --env or use prefixed package names")

    # Download package databases
    env2database: dict[Environment, dict[str, Package]] = {}
    for env in envs:
        env2database[env] = load_package_database(downloader, env)

    # Find requested packages in the database
    packages_to_download: Set[Package] = set()
    for package_name in args.packages:
        # Find package in the databases
        candidate_names = [package_name]
        if default_env:
            candidate_names.append(default_env.package_name_prefix + package_name)
        candidates = []
        for env in envs:
            for candidate_name in candidate_names:
                candidate = env2database[env].get(candidate_name)
                if candidate:
                    candidates.append(candidate)
        if len(candidates) == 0:
            raise SystemExit(f"Unknown package {package_name}, tried {candidate_names}")
        elif len(candidates) >= 2:
            raise SystemExit(f"Ambiguous package name {package_name}")
        # Mark for download
        package = candidates[0]
        if no_deps:
            packages_to_download.add(package)
        else:
            packages_to_download.update(package.with_recursive_dependencies())

    # Download packages
    n_failed = 0
    for package in packages_to_download:
        if cache.contains(package.download_path):
            continue
        try:
            downloader.download(package)
        except Exception as e:
            print(f"Failed to download {package.name}: {e}")
            n_failed += 1
    if n_failed > 0:
        raise SystemExit("Failed to download some packages")

    # Unpack
    if args.extract_root:
        for package in packages_to_download:
            print(f"Extracting {package.name} to {args.extract_root}")
            package_bytes = cache.load(package.download_path)
            if not package_bytes:
                raise RuntimeError(f"{package.name} not found in cache (probably a bug)")
            unpack(package_bytes, args.extract_root)


if __name__ == "__main__":
    main(sys.argv[1:])
