from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from typing import ClassVar

from msys2dl.application import Application
from msys2dl.commands.command import Command
from msys2dl.package import Environment
from msys2dl.package_database import PackageNameResolver
from msys2dl.package_store import PackageFile
from msys2dl.progress import ProgressCounter


class PackageSetMixin(Command):
    action_title: ClassVar[str] = "action_title unset"

    def __init__(self, app: Application, args: Namespace) -> None:
        super().__init__(app, args)
        self.with_dependencies: bool = not args.no_deps
        self.default_env = Environment.by_name(args.env) if args.env else None
        self.include: list[str] = PackageNameResolver(self.default_env).resolve_full_names(args.include)
        self.exclude: list[str] = PackageNameResolver(self.default_env).resolve_full_names(args.exclude)
        self.environments = {
            Environment.by_package_name_or_raise(name) for name in (self.include + self.exclude)
        }
        self.package_files: list[PackageFile] = []
        self.check_for_conflicts = not args.ignore_conflicts

    def run(self) -> None:
        super().run()
        self._app.update_keys()
        self._app.download_databases(self.environments)
        package_set = self._app.resolve_package_set(
            self.include,
            self.exclude,
            check_conflicts=self.check_for_conflicts,
            with_dependencies=self.with_dependencies,
        )
        self.package_files = self._app.download_packages(package_set)
        with ProgressCounter(len(self.package_files), description=self.action_title) as progress:
            for package_file in self.package_files:
                self._app.check_interrupted()
                self.do_package_action(package_file)
                progress.increment()

    @abstractmethod
    def do_package_action(self, package_file: PackageFile) -> None: ...

    @classmethod
    def configure_parser(cls, parser: ArgumentParser) -> None:
        super().configure_parser(parser)
        parser.add_argument("--no-deps", action="store_true", default=False)
        parser.add_argument("--ignore-conflicts", action="store_true", default=False)
        parser.add_argument("--exclude", metavar="PACKAGE", type=str, nargs="+", default=[])
        parser.add_argument(dest="include", metavar="PACKAGE", nargs="+")
        parser.add_argument(
            "--env",
            default=None,
            choices=[n for e in Environment.all for n in [e.name, *e.alias]],
        )
