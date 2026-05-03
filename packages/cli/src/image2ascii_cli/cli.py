# PYTHON_ARGCOMPLETE_OK
import argparse
from typing import Self

import argcomplete
from pydantic import Field, create_model
from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, CliSubCommand, SettingsConfigDict, get_subcommand

from image2ascii.plugin import BaseCliSubCommand
from image2ascii.registry import Registry


class ArgParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self.completers = Registry().get_completers()
        super().__init__(*args, **kwargs)

    def add_argument(self, *args, **kwargs) -> argparse.Action:
        action = argparse.ArgumentParser.add_argument(self, *args, **kwargs)
        if hasattr(self, "completers") and action.dest in self.completers:
            setattr(action, "completer", self.completers[action.dest])  # noqa: B010
        return action

    def parse_args(self, *args, **kwargs):
        parsed_args = super().parse_args(*args, **kwargs)
        if "best" in parsed_args and parsed_args.best and "fastest" in parsed_args and parsed_args.fastest:
            self.error("'--best' and '--fastest' are mutually exclusive.")
        return parsed_args


class Cli(
    BaseSettings,
    cli_avoid_json=True,
    cli_enforce_required=True,
    cli_hide_none_type=True,
    cli_ignore_unknown_args=True,
    cli_implicit_flags="dual",
    cli_kebab_case="all",
    cli_parse_args=True,
    cli_parse_none_str="none",
    cli_prog_name="i2a",
):
    # conv: CliSubCommand[CliFileConvertSettings] = Field(description="Convert a file")
    # colors: CliSubCommand[ColorGuide] = Field(description="A little colour guide")
    # colours: CliSubCommand[ColorGuide] = Field(description="Same as above, but spelled more Britishly")
    # list_settings: CliSubCommand[ListSettings]

    model_config = SettingsConfigDict(
        cli_shortcuts={
            "color.background": ["background", "bg"],
            "effect.brightness": "brightness",
            "effect.color-balance": "color-balance",
            "effect.contrast": "contrast",
            "effect.invert": "invert",
            "effect.mirror": "mirror",
            "effect.rotate": "rotate",
            "effect.sharpness": "sharpness",
            "viewport.columns": ["cols", "c"],
            "viewport.rows": ["rows", "r"],
            "zoom.factor": "z",
        },
    )

    def cli_cmd(self):
        if cmd := self.get_subcommand():
            cmd.run()
        else:
            CliApp.print_help(self)

    def get_subcommand(self) -> BaseCliSubCommand | None:
        if cmd := get_subcommand(self, is_required=False):
            if isinstance(cmd, BaseCliSubCommand):
                return cmd

    @classmethod
    def extend(cls) -> type[Self]:
        subcommands = cls.get_subcommands()

        return create_model(
            "Cli",
            __base__=cls,
            __config__=cls.model_config,
            **subcommands,
        )

    @classmethod
    def get_subcommands(cls) -> dict:
        subcommands: dict = {}

        for name, command in Registry().get_cli_subcommands().items():
            if isinstance(command, tuple):
                command = (CliSubCommand[command[0]], command[1])
            else:
                command = (CliSubCommand[command], Field(description=command.__doc__))
            subcommands[name] = command

        return subcommands


def cli():
    parser = ArgParser()
    NewCli = Cli.extend()

    cli_settings = CliSettingsSource(
        NewCli,
        cli_avoid_json=True,
        cli_enforce_required=True,
        cli_hide_none_type=True,
        cli_ignore_unknown_args=True,
        cli_implicit_flags="dual",
        cli_kebab_case="all",
        cli_parse_args=True,
        cli_parse_none_str="none",
        cli_prog_name="i2a",
        parse_args_method=ArgParser.parse_args,
        root_parser=parser,
        add_argument_method=ArgParser.add_argument,
    )
    argcomplete.autocomplete(parser)
    CliApp.run(NewCli, cli_settings_source=cli_settings)


if __name__ == "__main__":
    cli()
