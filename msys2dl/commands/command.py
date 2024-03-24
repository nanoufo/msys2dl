from argparse import ArgumentParser, Namespace
from typing import Protocol

from msys2dl.application import Application


class CommandType(Protocol):
    command_name: str

    def __call__(self, app: Application, args: Namespace) -> "Command": ...

    def configure_parser(self, parser: ArgumentParser) -> None: ...


class Command:
    def __init__(self, app: Application, _args: Namespace):
        self._app: Application = app

    def run(self) -> None:
        pass

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        pass
