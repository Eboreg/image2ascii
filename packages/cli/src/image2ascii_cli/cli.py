import argparse

from pydantic_settings import CliApp, CliSettingsSource

from image2ascii.color import ANSI_COLORS, ANSI_RESET_FG
from image2ascii.registry import Registry
from image2ascii_cli.config import Config


class ArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        _help = super().format_help() + "\n"
        _help += (
            "ANSI colour shorthands available for use with '--background' and '--border-color' (you can also use "
            "the format 'R,G,B', or CSS RGB colour strings):\n"
        )
        standard_ansi = [c for c in ANSI_COLORS if c.code < 90]
        bright_ansi = [c for c in ANSI_COLORS if c.code >= 90]

        for standard, bright in zip(standard_ansi, bright_ansi, strict=False):
            _help += f"  {standard.ansi}██{ANSI_RESET_FG} {standard.name:20s}"
            _help += f"{bright.ansi}██{ANSI_RESET_FG} {bright.name}\n"

        return _help

    def parse_args(self, *args, **kwargs):
        parsed_args = super().parse_args(*args, **kwargs)
        if "best" in parsed_args and parsed_args.best and "fastest" in parsed_args and parsed_args.fastest:
            self.error("'--best' and '--fastest' are mutually exclusive.")
        return parsed_args


def cli():
    parser = ArgumentParser()
    config_class = Registry.extend_config_class(Config)
    cli_settings = CliSettingsSource(
        config_class,
        root_parser=parser,
        parse_args_method=ArgumentParser.parse_args,
        format_help_method=ArgumentParser.format_help,
        cli_parse_args=True,
        cli_implicit_flags="dual",
        cli_kebab_case=True,
        cli_ignore_unknown_args=True,
        cli_avoid_json=True,
        cli_enforce_required=True,
        cli_prog_name="i2a",
        cli_parse_none_str="none",
    )
    CliApp.run(config_class, cli_settings_source=cli_settings)


if __name__ == "__main__":
    cli()
