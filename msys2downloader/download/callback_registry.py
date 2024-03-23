import logging
from typing import ParamSpec, Generic, Callable, List

P = ParamSpec("P")


class CallbackRegistry(Generic[P]):
    def __init__(self) -> None:
        self._callbacks: List[Callable[P, None]] = []

    def register(self, handler: Callable[P, None]) -> None:
        self._callbacks.append(handler)

    def run_callbacks(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:
                logging.error("Unexpected exception in callback", exc_info=exc)


class InterruptFlagCallbackRegistry:
    def __init__(self) -> None:
        self._callbacks: List[Callable[[], bool]] = []

    def register(self, handler: Callable[[], bool]) -> None:
        self._callbacks.append(handler)

    def run_callbacks(self) -> bool:
        for callback in self._callbacks:
            try:
                if callback():
                    return True
            except Exception as exc:
                logging.error("Unexpected exception in callback", exc_info=exc)
        return False
