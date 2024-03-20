from pathlib import Path
from typing import Protocol, Set, Union, Optional
from urllib.parse import quote

import requests
from requests import RequestException

from msys2downloader.utilities import DisplayableError


class HasDownloadPath(Protocol):
    @property
    def download_path(self) -> str: ...


class DownloadError(DisplayableError):
    pass


def _get_download_path(inp: Union[HasDownloadPath, str]) -> str:
    return inp if isinstance(inp, str) else inp.download_path


class DownloadCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def store(self, url_path: Union[HasDownloadPath, str], content: bytes) -> Path:
        path = self._file_path(url_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def find(self, url_path: Union[HasDownloadPath, str]) -> Optional[Path]:
        path = self._file_path(url_path)
        if path.exists() and path.is_file():
            return path
        else:
            return None

    def find_or_raise(self, url_path: Union[HasDownloadPath, str]) -> Path:
        p = self.find(url_path)
        if p:
            return p
        raise DisplayableError(f"Not found in cache: {url_path}")

    def contains(self, url_path: Union[HasDownloadPath, str]) -> bool:
        return self._file_path(url_path).is_file()

    def _file_path(self, url_path: Union[HasDownloadPath, str]) -> Path:
        rel_file_path = "./" + quote(_get_download_path(url_path), safe="/")
        path = (self.root / rel_file_path).resolve()
        if not path.is_relative_to(self.root):
            # Not sure if this can happen
            raise RuntimeError(f"Bad url_path: {url_path}")
        return path


class Downloader:
    def __init__(self, base_url: str, cache: DownloadCache) -> None:
        self.base_url = base_url
        self.bad_mirrors: Set[str] = set()
        self.cache = cache

    def download(self, what: Union[str, HasDownloadPath]) -> Path:
        if isinstance(what, str):
            url_path = what
        else:
            url_path = what.download_path
        if not url_path.startswith("/"):
            url_path = "/" + url_path

        # Try to find in cache
        from_cache = self.cache.find(url_path)
        if from_cache:
            # print(f"{what} found in cache")
            return from_cache

        # Download
        url = self.base_url + url_path
        tries_left = 10
        last_error = None
        while tries_left > 0:
            # Try to download
            try:
                tries_left -= 1
                response = requests.get(url, timeout=(5, 5))
                if response.status_code != 200:
                    # Try again
                    last_error = "bad status code: " + str(response.status_code)
                    continue
            except RequestException as e:
                last_error = str(e)
            else:
                # Save to cache
                # print(f"Downloaded {what}")
                return self.cache.store(url_path, response.content)
        raise DownloadError(f"Failed to download {url}: {last_error}")
