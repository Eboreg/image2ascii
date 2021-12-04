#!/usr/bin/env python3

import argparse
import time

import colorama
from colorama import Fore

from image2ascii import (
    DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, __version__, utils,
)
from image2ascii.core import Image2ASCII
from image2ascii.output import ANSIFormatter


def main():
    colorama.init(autoreset=True)

    ansi = f"{Fore.BLUE}A{Fore.GREEN}N{Fore.YELLOW}S{Fore.RED}I{Fore.RESET}"

    parser = argparse.ArgumentParser()

    parser.add_argument("file", help="Image to process", nargs="?")
    parser.add_argument(
        "--width",
        "-w",
        type=int,
        default=DEFAULT_ASCII_WIDTH,
        help=f"Width (in number of characters) of output. Default: {DEFAULT_ASCII_WIDTH}."
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help=f"Outputs in glorious {ansi} colour."
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Fills characters that would have been empty, and vice versa. Note that this is not the same as " +
             "--negative."
    )
    parser.add_argument(
        "--crop",
        action="store_true",
        help="Crops empty areas at all edges."
    )
    parser.add_argument(
        "--quality",
        "-q",
        type=int,
        choices=range(1, 10),
        default=DEFAULT_QUALITY,
        help=f"The higher, the better (and slower). Default: {DEFAULT_QUALITY}."
    )
    parser.add_argument(
        "--ratio",
        "-r",
        type=float,
        default=DEFAULT_ASCII_RATIO,
        help="ASCII character height/width ratio. Increase this if the results look stretched out " +
             f"vertically, and vice versa. Default: {DEFAULT_ASCII_RATIO}."
    )
    parser.add_argument(
        "--fill-all",
        action="store_true",
        help="Fill all characters except transparent ones."
    )
    parser.add_argument(
        "--min-likeness",
        "-ml",
        type=float,
        default=DEFAULT_MIN_LIKENESS,
        help="For each image section, decide on an ASCII character as soon as we find one whose shape is " +
             "determined to be have at least this likeness (0.0 to 1.0) to the original. "
             "Default: {DEFAULT_MIN_LIKENESS}."
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=1.0,
        help="Adjusts contrast of source image before converting. 1.0 = original image, 0.0 = solid grey image."
    )
    parser.add_argument(
        "--brightness",
        type=float,
        default=1.0,
        help="Adjusts brightness of source image before converting. 1.0 = original image, 0.0 = black image."
    )
    parser.add_argument(
        "--color-balance",
        type=float,
        default=1.0,
        help="Adjusts colour balance of source image before converting. 1.0 = original image, 0.0 = B/W image."
    )
    parser.add_argument(
        "--negative",
        action="store_true",
        help="Inverts the colours of the image before processing."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Outputs some random debug info."
    )
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    if args.file is None:
        parser.print_help()
        return

    if args.debug:
        utils.timing_enabled = True
        start_time = time.monotonic()

    i2a = Image2ASCII(file=args.file)

    i2a.color_settings(
        color=args.color,
        invert=args.invert,
        negative=args.negative,
        fill_all=args.fill_all,
    )
    i2a.enhancement_settings(contrast=args.contrast, brightness=args.brightness, color_balance=args.color_balance)
    i2a.quality_settings(quality=args.quality, min_likeness=args.min_likeness)
    i2a.size_settings(ascii_width=args.width, ascii_ratio=args.ratio, crop=args.crop)
    if args.color:
        i2a.formatter_class = ANSIFormatter

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
