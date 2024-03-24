from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from contextvars import ContextVar

from requests import Session
from requests.adapters import HTTPAdapter

from msys2dl.download.download_callback import DownloadCallbacks
from msys2dl.download.download_request import DownloadRequest
from msys2dl.download.simple_downloader import SimpleDownloader


class Job:
    def __init__(self) -> None:
        self._failed = False
        self._exception: Exception | None = None
        self._futures: list[Future[None]] = []

    def register_callbacks(self, callback: DownloadCallbacks) -> None:
        callback.failure_handlers.register(self.on_failure)
        callback.is_interrupted_handlers.register(self.is_failed)

    def add_future(self, future: Future[None]) -> None:
        self._futures.append(future)

    def on_failure(self, exc: Exception) -> None:
        if self._failed:
            # Already failed
            return
        self._exception = exc
        self._failed = True  # interrupt all downloads
        for future in self._futures:
            future.cancel()

    def is_failed(self) -> bool:
        return self._failed

    def join(self) -> None:
        for future in self._futures:
            try:
                if not future.cancelled():
                    future.result()
            except CancelledError:
                pass
        if self._exception:
            raise self._exception


class ParallelDownloader:
    def __init__(self, *, downloader: SimpleDownloader, n_threads: int = 5) -> None:
        self._downloader = downloader
        self._pool = ThreadPoolExecutor(n_threads, initializer=self._initialize_worker_thread)
        self._session: ContextVar[Session] = ContextVar("session")
        self._sessions: list[Session] = []

    def execute_requests(
        self,
        requests: list[DownloadRequest],
        register_callbacks: Callable[[DownloadRequest, DownloadCallbacks], None],
    ) -> None:
        job = Job()
        # Add tasks to thread pool
        for request in requests:
            callbacks = DownloadCallbacks()
            register_callbacks(request, callbacks)
            job.register_callbacks(callbacks)
            job.add_future(self._pool.submit(self._execute_request, request, callbacks))
        # Wait for completion & raise exceptions if any
        job.join()

    def close(self) -> None:
        for session in self._sessions:
            session.close()
        self._pool.shutdown(wait=True)

    def _initialize_worker_thread(self) -> None:
        self._session.set(self.create_session())

    def _execute_request(self, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        self._downloader.download(self._session.get(), request, callbacks)

    def create_session(self) -> Session:
        session = Session()
        session.mount("http://", HTTPAdapter(max_retries=0))
        session.mount("https://", HTTPAdapter(max_retries=0))
        self._sessions.append(session)
        return session
