import os
import signal
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable
from pathlib import Path
from threading import Event
from types import FrameType, TracebackType

import requests
from requests import RequestException

from msys2dl.download.download_callback import DownloadCallbacks
from msys2dl.download.download_request import DownloadRequest
from msys2dl.download.parallel_downloader import ParallelDownloader
from msys2dl.download.simple_downloader import SimpleDownloader
from msys2dl.gpg_keyring import GpgKeybox
from msys2dl.package import Environment, Package, PackageSet
from msys2dl.package_database import PackageDatabase
from msys2dl.package_store import PackageFile, PackageStore
from msys2dl.progress import DownloadProgress


class Application:
    def __init__(self, args: Namespace):
        home = Path(os.getenv("MSYS2DL_HOME") or Path("~/.local/share/msys2dl").expanduser())
        home.mkdir(parents=True, exist_ok=True)
        self._database = PackageDatabase(home / "db")
        self._package_store = PackageStore(home / "packages")
        self._keybox = GpgKeybox(home / "keybox.gpg")
        self._n_download_threads: int = args.download_threads
        self._base_url: str = args.base_url
        self._keys_url: str = args.keys_url
        self._interrupt_event: Event = Event()
        self._downloader = ParallelDownloader(
            downloader=SimpleDownloader(self._keybox), n_threads=args.download_threads
        )
        signal.signal(signal.SIGINT, self.handle_interrupt)
        signal.signal(signal.SIGTERM, self.handle_interrupt)

    def __enter__(self) -> "Application":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._downloader.close()
        if exc_val is not None:
            raise exc_val

    def handle_interrupt(self, _sig: int, _frame: FrameType | None) -> None:
        self._interrupt_event.set()

    def check_interrupted(self) -> None:
        if self._interrupt_event.is_set():
            raise InterruptedError()

    def update_keys(self) -> None:
        try:
            response = requests.get(self._keys_url, timeout=5)
            response.raise_for_status()
        except RequestException as exc:
            print(f"Warning: failed to update signature keys: {exc}")
            return
        self._keybox.update_keys(response.content)

    def download_databases(self, environments: Iterable[Environment], force: bool = False) -> None:
        reqs = self._database.make_download_requests(self._base_url, environments)
        self._download("Downloading package database", reqs, force)
        self._database.reload()

    def download_packages(self, packages: Iterable[Package], force: bool = False) -> list[PackageFile]:
        reqs = self._package_store.make_download_requests(self._base_url, packages)
        self._download("Downloading packages", reqs, force)
        return self.resolve_package_files(packages)

    def resolve_package_set(
        self,
        include: Iterable[str],
        exclude: Iterable[str],
        with_dependencies: bool,
        check_conflicts: bool = True,
    ) -> PackageSet:
        # Get excluded packages
        excluded_packages: list[Package] = []
        for excluded_name in exclude:
            package = self._database.get(excluded_name)
            if not package:
                print(f"Warning: unknown excluded package '{excluded_name}'")
                continue
            excluded_packages.append(package)
        # Create set from includes and excludes
        requested_packages = PackageSet(self._database.get_all_or_raise(include)) - excluded_packages
        # Add dependencies
        if with_dependencies:
            requested_packages.add_dependencies_recursively(exclude=excluded_packages)
        # Check for conflicts
        if check_conflicts:
            requested_packages.check_for_conflicts()
        return requested_packages

    def resolve_package_files(self, packages: Iterable[Package]) -> list[PackageFile]:
        return [self._package_store.get_package_file(package) for package in packages]

    def _download(self, description: str, reqs: list[DownloadRequest], force: bool = False) -> None:
        if not force:
            # Don't download if already downloaded
            reqs = [r for r in reqs if not r.dest.exists()]
        if not reqs:
            # Nothing to do
            return

        with DownloadProgress(len(reqs), description) as progress:

            def register_callbacks(request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
                progress.register_callbacks(request, callbacks)
                callbacks.is_interrupted_handlers.register(self._interrupt_event.is_set)
                callbacks.success_handlers.register(lambda: print(f"Downloaded {request.name}"))

            self._downloader.execute_requests(reqs, register_callbacks=register_callbacks)

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        parser.add_argument("--download-threads", type=int, default=5, help="Number of download threads")
        parser.add_argument("--base-url", type=str, default="https://mirror.msys2.org")
        parser.add_argument(
            "--keys-url",
            type=str,
            default="https://raw.githubusercontent.com/msys2/MSYS2-keyring/master/msys2.gpg",
        )
