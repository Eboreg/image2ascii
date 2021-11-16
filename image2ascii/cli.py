#!/usr/bin/env python3

import argparse
import time
from wsgiref.simple_server import make_server

import colorama
from colorama import Fore

from image2ascii import DEFAULT_ASCII_RATIO, DEFAULT_ASCII_WIDTH, DEFAULT_MIN_LIKENESS, DEFAULT_QUALITY, __version__
from image2ascii.color import ColorConverterInvertBW
from image2ascii.core import Image2ASCII
from image2ascii.wsgi import Application


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
             "--invert-colors."
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
             "determined to be have at least this likeness (0.0 to 1.0) to the original. Note that a value of " +
             f"1.0 may be insanely slow. Default: {DEFAULT_MIN_LIKENESS}."
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
        "--invert-colors",
        action="store_true",
        help="Inverts the colours (yes, I use British spelling in text and American in code; deal with it) " +
             "of the image before processing."
    )
    parser.add_argument(
        "--swap-bw",
        action="store_true",
        help="Makes black output characters white and vice versa; does not affect any other colours."
    )
    parser.add_argument("--test-server", action="store_true", help="Fires up a test server on port 8000.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Outputs some random debug info."
    )
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    if args.test_server:
        print("Listening on port 8000")
        httpd = make_server("localhost", 8000, Application())
        httpd.serve_forever()
        return

    if args.file is None:
        parser.print_help()
        return

    start_time = time.monotonic()

    i2a = Image2ASCII(
        args.file,
        ascii_width=args.width,
        quality=args.quality,
        ascii_ratio=args.ratio,
        invert=args.invert,
        fill_all=args.fill_all,
    )

    i2a.enhance(args.contrast, args.brightness, args.color_balance)

    if args.invert_colors:
        i2a.invert_colors()

    if args.crop:
        i2a.crop()

    if args.swap_bw:
        i2a.set_color_converter(ColorConverterInvertBW())

    output = i2a.render(color=args.color, min_likeness=args.min_likeness)

    elapsed_time = time.monotonic() - start_time

    print(output)

    if args.debug:
        print(f" *** source_width: {i2a.source_width}")
        print(f" *** source_height: {i2a.source_height}")
        print(f" *** section_width: {i2a.section_width}")
        print(f" *** section_height: {i2a.section_height}")
        print(f" *** Conversion time: {elapsed_time} seconds")


if __name__ == "__main__":
    main()
