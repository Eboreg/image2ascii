import argparse

from pydantic_settings import CliApp, CliSettingsSource

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
    convert_class = Registry.extend_config_class(CliFileConvertConfig)
    field = Cli.model_fields["conv"]
    field.annotation = convert_class | None # pyright: ignore
    field.rebuild_annotation()
    cli_settings = CliSettingsSource(
        Cli,
        root_parser=parser,
        parse_args_method=ArgumentParser.parse_args,
        cli_parse_args=True,
        cli_implicit_flags="dual",
        cli_kebab_case=True,
        cli_ignore_unknown_args=True,
        cli_avoid_json=True,
        cli_enforce_required=True,
        cli_prog_name="i2a",
        cli_parse_none_str="none",
    )
    CliApp.run(Cli, cli_settings_source=cli_settings)


if __name__ == "__main__":
    cli()
