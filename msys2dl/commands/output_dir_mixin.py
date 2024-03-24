from argparse import ArgumentParser, Namespace
from pathlib import Path

from msys2dl.application import Application
from msys2dl.commands.command import Command


class OutputDirMixin(Command):
    def __init__(self, _app: Application, args: Namespace) -> None:
        super().__init__(_app, args)
        self.output_dir: Path = args.output

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        super().configure_parser(parser)
        parser.add_argument("--output", "-o", metavar="OUTPUT_DIRECTORY", type=Path, default=Path())
