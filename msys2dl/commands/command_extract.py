from argparse import Namespace
from typing import ClassVar

from msys2dl.application import Application
from msys2dl.commands.command import Command
from msys2dl.commands.output_dir_mixin import OutputDirMixin
from msys2dl.commands.package_set_mixin import PackageSetMixin
from msys2dl.package_store import PackageFile


class CommandExtract(PackageSetMixin, OutputDirMixin, Command):
    command_name: ClassVar[str] = "extract"
    action_title = "Extracting files"

    def __init__(self, app: Application, args: Namespace):
        super().__init__(app, args)

    def do_package_action(self, package_file: PackageFile) -> None:
        package_file.extract(self.output_dir)
        print(f"Extracted {package_file.metadata}")
