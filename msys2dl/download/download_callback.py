from msys2dl.download.callback_registry import CallbackRegistry, InterruptFlagCallbackRegistry


class DownloadCallbacks:
    def __init__(self) -> None:
        self.complete_handlers: CallbackRegistry[[]] = CallbackRegistry()
        self.success_handlers: CallbackRegistry[[]] = CallbackRegistry()
        self.failure_handlers: CallbackRegistry[[Exception]] = CallbackRegistry()
        self.progress_handlers: CallbackRegistry[[int, int]] = CallbackRegistry()
        self.is_interrupted_handlers = InterruptFlagCallbackRegistry()

    def on_success(self) -> None:
        self.success_handlers.run_callbacks()
        self.complete_handlers.run_callbacks()

    def on_failure(self, exc: Exception) -> None:
        self.failure_handlers.run_callbacks(exc)
        self.complete_handlers.run_callbacks()

    def on_progress(self, current: int, total: int) -> None:
        self.progress_handlers.run_callbacks(current, total)

    def is_interrupted(self) -> bool:
        return self.is_interrupted_handlers.run_callbacks()

    def check_interrupted(self) -> None:
        if self.is_interrupted():
            raise InterruptedError()


class SigDownloadCallback(DownloadCallbacks):
    def __init__(self, base: DownloadCallbacks):
        super().__init__()
        self.is_interrupted_handlers.register(base.is_interrupted)
