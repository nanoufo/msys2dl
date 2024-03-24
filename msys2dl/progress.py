from collections.abc import Iterable

from rich import table
from rich.console import ConsoleRenderable
from rich.progress import BarColumn, DownloadColumn, MofNCompleteColumn, Progress, TaskID, TextColumn

from msys2dl.download.download_callback import DownloadCallbacks
from msys2dl.download.download_request import DownloadRequest


class ProgressCounter(Progress):
    def __init__(self, total: int, description: str = "Downloading"):
        super().__init__()
        self._main_task_id = self.add_task(description, total=total)
        self.columns = (
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(table_column=table.Column(width=15)),
        )

    def __enter__(self) -> "ProgressCounter":
        # override __enter__ for type checking
        super().__enter__()
        return self

    def increment(self, n: int = 1) -> None:
        self.advance(self._main_task_id, n)


class DownloadProgress(Progress):
    def __init__(self, total: int, description: str = "Downloading"):
        super().__init__()
        self._total = total
        self._main_task_id = self.add_task(description, total=total)
        self._name_column_width = len(description)

    def __enter__(self) -> "DownloadProgress":
        # override __enter__ for type checking
        super().__enter__()
        return self

    def register_callbacks(self, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        self._name_column_width = max(self._name_column_width, len(request.name))
        DownloadProgressTracker(self, request).register_callbacks(callbacks)

    def get_renderables(self) -> Iterable[ConsoleRenderable]:
        if not self.tasks:
            return
        main_task = next(task for task in self.tasks if task.id == self._main_task_id)
        download_tasks = [task for task in self.tasks if task.id != self._main_task_id]

        # Render download progress bars
        self.columns = (
            TextColumn(
                "[progress.description]{task.description}",
                table_column=table.Column(width=self._name_column_width),
            ),
            BarColumn(bar_width=None),
            DownloadColumn(binary_units=True, table_column=table.Column(width=15)),
        )
        yield self.make_tasks_table(download_tasks)

        # Render main progress bar
        self.columns = (
            TextColumn(
                "[progress.description]{task.description}",
                table_column=table.Column(width=self._name_column_width),
            ),
            BarColumn(bar_width=None),
            MofNCompleteColumn(table_column=table.Column(width=15)),
        )
        yield self.make_tasks_table([main_task])

    def advance_n_downloaded(self, n: int = 1) -> None:
        self.advance(self._main_task_id, n)


class DownloadProgressTracker:
    def __init__(self, progress: DownloadProgress, request: DownloadRequest):
        self._task_id: TaskID | None = None
        self._progress = progress
        self._description = request.name
        self._task_removed = False

    def register_callbacks(self, callbacks: DownloadCallbacks) -> None:
        callbacks.success_handlers.register(self.on_success)
        callbacks.complete_handlers.register(self.on_complete)
        callbacks.progress_handlers.register(self.on_progress)

    def on_progress(self, bytes_downloaded: int, bytes_total: int) -> None:
        if self._task_removed:
            return
        if self._task_id is None:
            self._task_id = self._progress.add_task(self._description, total=bytes_total)
        self._progress.update(self._task_id, total=bytes_total, completed=bytes_downloaded)

    def on_success(self) -> None:
        self._progress.advance_n_downloaded(1)

    def on_complete(self) -> None:
        if not self._task_removed:
            self._task_removed = True
            if self._task_id is not None:
                self._progress.remove_task(self._task_id)
