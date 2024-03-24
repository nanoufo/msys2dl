from pathlib import Path

from requests import RequestException, Session

from msys2dl.download.download_callback import DownloadCallbacks, SigDownloadCallback
from msys2dl.download.download_request import DownloadRequest
from msys2dl.gpg_keyring import GpgKeybox
from msys2dl.utilities import AppError


class SimpleDownloader:
    def __init__(self, keybox: GpgKeybox):
        self._keybox = keybox

    def download(self, session: Session, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        try:
            self._do_download(session, request, callbacks)
        except Exception as exc:
            callbacks.on_failure(exc)
        else:
            callbacks.on_success()

    def _do_download(self, session: Session, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        # Download
        callbacks.check_interrupted()
        request.dest.parent.mkdir(parents=True, exist_ok=True)
        if request.expected_size is not None:
            callbacks.on_progress(0, request.expected_size)
        self._download_single_file(session, request.url, request.partial_dest, callbacks)
        self._download_single_file(session, request.sig_url, request.sig_dest, SigDownloadCallback(callbacks))
        # Check signature
        try:
            callbacks.check_interrupted()
            self._keybox.validate_signature(request.sig_dest, request.partial_dest)
        except AppError as err:
            raise AppError.wrap(f"failed to verify signature for {request.url}", err)
        # Move file to final path
        request.partial_dest.rename(request.dest)

    @staticmethod
    def _download_single_file(session: Session, url: str, dest: Path, callbacks: DownloadCallbacks) -> None:
        tries_left = 10
        last_error = None
        while tries_left > 0:
            callbacks.check_interrupted()
            tries_left -= 1
            try:
                # Start download
                with session.get(url, timeout=(5, 5), stream=True) as response:
                    if response.status_code != 200:
                        # Try again
                        last_error = "bad status code: " + str(response.status_code)
                        continue
                    # Download file
                    callbacks.check_interrupted()
                    total_size = int(response.headers.get("content-length", 0))
                    callbacks.on_progress(0, total_size)
                    bytes_downloaded = 0
                    block_size = 4 * 1024  # 4 KiB
                    with dest.open("wb") as f:
                        for data in response.iter_content(block_size):
                            callbacks.check_interrupted()
                            bytes_downloaded += len(data)
                            callbacks.on_progress(bytes_downloaded, total_size)
                            f.write(data)
                    return
            except RequestException as e:
                last_error = str(e)
        raise AppError(f"failed to download {url}: {last_error}")
