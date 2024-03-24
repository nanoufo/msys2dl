import sys
from argparse import ArgumentParser

from msys2dl.application import Application
from msys2dl.commands.command import CommandType
from msys2dl.commands.command_extract import CommandExtract
from msys2dl.commands.command_make_deb import CommandMakeDeb
from msys2dl.utilities import AppError


def _run_app(argv: list[str] | None = None) -> None:
    # Configure parser
    parser = ArgumentParser()
    Application.configure_parser(parser)
    command_types: list[CommandType] = [CommandMakeDeb, CommandExtract]
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    for command_type in command_types:
        subparser = subparsers.add_parser(command_type.command_name)
        command_type.configure_parser(subparser)

    # Parse command
    args = parser.parse_args(argv)

    # RUn application
    with Application(args) as app:
        command_type = next(
            command_type for command_type in command_types if command_type.command_name == args.command_name
        )
        command = command_type(app, args)
        command.run()


def main(argv: list[str] | None = None) -> None:
    try:
        _run_app(argv)
    except InterruptedError:
        print("Interrupted")
        sys.exit(2)
    except AppError as e:
        print(e.display())
        sys.exit(1)


if __name__ == "__main__":
    main()
