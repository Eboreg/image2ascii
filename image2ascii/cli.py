#!/usr/bin/env python3

import argparse
import time
from typing import TYPE_CHECKING

import colorama
from colorama import Fore

from image2ascii import __version__, utils

if TYPE_CHECKING:
    from image2ascii.config import Config


def add_boolean_argument(parser: argparse._ActionsContainer, config: "Config", name: str, help_text: str):
    var_name = name.replace("-", "_")
    default = getattr(config, var_name)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        f"--{name}",
        action="store_true",
        default=default,
        help=help_text
    )
    group.add_argument(
        f"--no-{name}",
        action="store_false",
        dest=var_name,
        default=default,
        help=f"Negates --{name}. Only relevant if config file contains '{var_name} = true'."
    )


def init_parser(config: "Config") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    ansi = f"{Fore.BLUE}A{Fore.GREEN}N{Fore.YELLOW}S{Fore.RED}I{Fore.RESET}"

    parser.add_argument("file", help="Image to process", nargs="?")

    # Non-boolean optional arguments
    parser.add_argument(
        "--width",
        "-w",
        type=int,
        default=config.width,
        help=f"Width (in number of characters) of output. Default: {config.width}."
    )
    parser.add_argument(
        "--quality",
        "-q",
        type=int,
        choices=range(1, 10),
        default=config.quality,
        help=f"The higher, the better (and slower). Default: {config.quality}."
    )
    parser.add_argument(
        "--ratio",
        "-r",
        type=float,
        default=config.ratio,
        help="ASCII character height/width ratio. Increase this if the results look stretched out " +
             f"vertically, and vice versa. Default: {config.ratio}."
    )
    parser.add_argument(
        "--min-likeness",
        "-ml",
        type=float,
        default=config.min_likeness,
        help="For each image section, decide on an ASCII character as soon as we find one whose shape is " +
             "determined to be have at least this likeness (0.0 to 1.0) to the original. " +
             f"Default: {config.min_likeness}."
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=config.contrast,
        help="Adjusts contrast of source image before converting. 1.0 = original image, 0.0 = solid grey " +
             f"image. Default: {config.contrast}."
    )
    parser.add_argument(
        "--brightness",
        type=float,
        default=config.brightness,
        help="Adjusts brightness of source image before converting. 1.0 = original image, 0.0 = black image. " +
             f"Default: {config.brightness}."
    )
    parser.add_argument(
        "--color-balance",
        type=float,
        default=config.color_balance,
        help="Adjusts colour balance of source image before converting. 1.0 = original image, 0.0 = B/W image. " +
             f"Default: {config.color_balance}."
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file. If set, it will take precedence over the default ones, which are "
             "`~/.image2ascii` and `[application path]/defaults.conf`."
    )

    # Boolean optional arguments
    bool_group = parser.add_argument_group("Boolean arguments")
    add_boolean_argument(bool_group, config, "color", f"Outputs in glorious {ansi} colour.")
    add_boolean_argument(
        bool_group, config, "invert",
        "Fills characters that would have been empty, and vice versa. Note that this is not the same as "
        "--negative."
    )
    add_boolean_argument(bool_group, config, "crop", "Crops empty areas at all edges.")
    add_boolean_argument(bool_group, config, "fill-all", "Fill all characters except transparent ones.")
    add_boolean_argument(
        bool_group, config, "negative", "Inverts the colours of the image before processing."
    )
    add_boolean_argument(bool_group, config, "debug", "Outputs some random debug info.")

    # Other arguments
    parser.add_argument("--version", action="version", version=__version__)

    return parser


def main():
    from image2ascii.config import Config
    from image2ascii.core import Image2ASCII

    colorama.init(autoreset=True)

    config = Config.from_default_files()
    parser = init_parser(config)
    args = parser.parse_args()

    if args.config:
        # If issued a config file, we need to re-init the parser because
        # the default values may have changed.
        config = Config.from_file(args.config)
        parser = init_parser(config)
        args = parser.parse_args()

    if args.file is None:
        parser.print_help()
        return

    config.update(**args.__dict__)

    if args.debug:
        utils.timing_enabled = True
        start_time = time.monotonic()

    i2a = Image2ASCII(file=args.file, config=config)

    output = i2a.render()

    if args.debug:
        elapsed_time = time.monotonic() - start_time

    print(output)

    if args.debug:
        for funcname, executions, timing in utils.summarize_timing():
            print("{:40} {:20} {:30} {}".format(
                funcname,
                f"{executions} executions",
                f"average={round(timing / executions, 10)} s",
                f"total={round(timing, 10)} s",
            ))
        print()
        print(f"Total time: {round(elapsed_time, 10)} s")


if __name__ == "__main__":
    main()
