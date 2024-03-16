from pathlib import Path
from typing import Optional, Protocol, Set, Union
from urllib.parse import quote, urlparse

import requests


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def store(self, url_path: str, content: bytes) -> None:
        path = self._file_path(url_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def load(self, url_path: str) -> Optional[bytes]:
        path = self._file_path(url_path)
        if path.exists() and path.is_file():
            return path.read_bytes()
        else:
            return None

    def contains(self, url_path: str) -> bool:
        return self._file_path(url_path).is_file()

    def _file_path(self, url_path: str) -> Path:
        rel_file_path = "./" + quote(url_path, safe="/")
        path = (self.root / rel_file_path).resolve()
        if not path.is_relative_to(self.root):
            raise RuntimeError(f"Bad url_path: {url_path}")
        return path


class HasDownloadPath(Protocol):
    @property
    def download_path(self) -> str: ...


class Downloader:
    def __init__(self, base_url: str, cache: Cache) -> None:
        self.base_url = base_url
        self.bad_mirrors: Set[str] = set()
        self.cache = cache

    def download(self, what: Union[str, HasDownloadPath]) -> bytes:
        if isinstance(what, str):
            url_path = what
        else:
            url_path = what.download_path
        if not url_path.startswith("/"):
            url_path = "/" + url_path

        # Try to load from cache
        from_cache = self.cache.load(url_path)
        if from_cache:
            print(f"Loading cached {url_path}")
            return from_cache

        # Download
        url = self.base_url + url_path
        mirrors_left = 10
        tries_left = 30
        while tries_left > 0 and mirrors_left > 0:
            # Get mirror url
            redirect_url = self._get_redirect_to_mirror(url)
            host = urlparse(redirect_url).netloc
            if host in self.bad_mirrors:
                tries_left -= 1
                continue
            # Try to download
            try:
                response = requests.get(redirect_url, allow_redirects=False, timeout=(5, 5))
                if response.status_code != 200:
                    raise RuntimeError(f"unexpected status {response.status_code} for {redirect_url}")
            except:
                print(f"Failed to download using {host} mirror, adding to blacklist")
                self.bad_mirrors.add(host)
                mirrors_left -= 1
                tries_left -= 1
            else:
                # Save to cache
                print(f"Downloaded {redirect_url}")
                self.cache.store(url_path, response.content)
                return response.content
        raise RuntimeError(f"Failed to download {url}")

    @staticmethod
    def _get_redirect_to_mirror(url: str) -> str:
        response = requests.get(url, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 302:
            raise RuntimeError(f"unexpected status {response.status_code} for {url}")
        redirect_url = response.headers["Location"]
        return redirect_url


# def load_database(downloader: Downloader, path: str) -> dict[str, Package]:
#     content = downloader.download(path)
#     content = decompress_zst(content)
#     tar = tarfile.open(fileobj=io.BytesIO(content), mode="r")
#     packages = []
#     for member in tar.getmembers():
#         file = tar.extractfile(member)
#         if file and member.name.endswith('/desc'):
#             packages.append(Package.from_desc(file.read().decode('utf-8')))
#     packages_dict = {p.name: p for p in packages}
#
#     path_prefix = str(PurePath(path).parent)
#     for package in packages:
#         package.url_path_prefix = path_prefix
#         package.populate_dependencies(packages_dict)
#     return packages_dict
#
#
# downloader = Downloader('https://mirror.msys2.org')
# database = load_database(downloader, '/mingw/mingw64/mingw64.db')
# packages = sorted(database['mingw-w64-x86_64-curl-winssl'].with_recursive_dependencies(), key=lambda p: p.name)
#
# for p in packages:
