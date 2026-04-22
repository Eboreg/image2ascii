import argparse

from pydantic import Field, create_model
from pydantic_settings import CliApp, CliSettingsSource, CliSubCommand

from image2ascii.registry import Registry
from image2ascii_cli.config import Cli, CliFileConvertConfig


class ArgumentParser(argparse.ArgumentParser):
    def parse_args(self, *args, **kwargs):
        parsed_args = super().parse_args(*args, **kwargs)
        if "best" in parsed_args and parsed_args.best and "fastest" in parsed_args and parsed_args.fastest:
            self.error("'--best' and '--fastest' are mutually exclusive.")
        return parsed_args


def cli():
    parser = ArgumentParser()
    config_class = Registry.extend_config_class(CliFileConvertConfig)
    field = Cli.model_fields["conv"]
    field.annotation = config_class | None # pyright: ignore
    field.rebuild_annotation()

    subcommands: dict = {
        command: (CliSubCommand[command_class], Field(description=command_class.__doc__))
        for command, command_class in Registry.get_cli_subcommands().items()
    }

    NewCli = create_model(
        "Cli",
        __base__=Cli,
        __config__=Cli.model_config,
        **subcommands,
    )

    cli_settings = CliSettingsSource(
        NewCli,
        root_parser=parser,
        parse_args_method=ArgumentParser.parse_args,
        cli_avoid_json=True,
        cli_enforce_required=True,
        cli_hide_none_type=True,
        cli_ignore_unknown_args=True,
        cli_implicit_flags="dual",
        cli_kebab_case="all",
        cli_parse_args=True,
        cli_parse_none_str="none",
        cli_prog_name="i2a",
    )
    CliApp.run(NewCli, cli_settings_source=cli_settings)


if __name__ == "__main__":
    cli()
