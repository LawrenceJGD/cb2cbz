#!/usr/bin/python

"""Script that converts comic book files to CBZ files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Sequence

_format = format
_input = input

JPEG_RANGE = range(101)
PNG_RANGE = range(10)


class ImageFormat(StrEnum):
    """Enum for supported image formats."""

    JPEG = "jpeg"
    JPEGXL = "jpegxl"
    JPEGLI = "jpegli"
    PNG = "png"
    NO_CHANGE = "no-change"


@dataclass
class JpegXLOptions:
    """Options for encoding JPEG-XL images."""

    lossless: bool

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse JPEG XL format options.

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        lossless: bool = True
        opt: str
        for opt in options.split(","):
            if not opt:
                continue

            name: str
            value: str
            name, _, value = opt.partition("=")

            msg: str
            if not value:
                msg = f"{name} option value is empty"
            if name.lower() == "lossless":
                lossless = parse_str_bool(value, "lossless")
            else:
                msg = f"{name} is not a valid option for jpegxl"
                raise ValueError(msg)

        return cls(lossless=lossless)


@dataclass
class Parameters:
    """Parsed CLI parameters.

    Attributes:
        format: Output image format.
        quality: Compression quality.
        options: Output image format options.
        input: Path to input comic book file.
        output: Path to output CBZ file.
    """

    format: ImageFormat
    quality: int | None
    options: JpegXLOptions | None
    input: Path
    output: Path


def parse_quality(value: str) -> int:
    """Parses --quality CLI parameter and return it as an int."""
    try:
        num: int = int(value)
    except ValueError:
        msg: str = "--quality must be a valid integer number"
        raise argparse.ArgumentTypeError(msg) from None
    if num < 0:
        msg = "--quality must be greater or equal than 0"
        raise argparse.ArgumentTypeError(msg)
    return num


def parse_str_bool(value: str, name: str) -> bool:
    """Parse boolean options and return them.

    Args:
        value: Value that must be parsed.
        name: Name of the option to put in the exception if the value is
            invalid.

    Raises:
        ValueError: If the value is not "1", "0", "true" or "false".
    """
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    msg: str = f'{name} value must be "1", "0", "true" or "false"'
    raise ValueError(msg)


def parse_params(argv: Sequence[str] | None = None) -> Parameters:
    """Parse CLI parameters and return them."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Converts comic book files into .cbz files"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=ImageFormat,
        type=ImageFormat,
        default=ImageFormat.NO_CHANGE,
        help=(
            "Image format to which the images in the comic book will be "
            'converted. "jxl" uses lossless compression while '
            '"jxl-lossy" does not, "jpegli" encodes JPEG files using '
            'cjpegli and "no-change" does not change the image\'s format.'
        ),
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=parse_quality,
        help=(
            "Compression quality. Its meaning depends on the format. For "
            '"jpeg", "jpegli" and "jpegxl" it goes from 0 to 100, the default '
            'for them is 90. For "jpegxl" 100 means lossless. For "png" it '
            "goes from 0 to 9 and the default is 6."
        ),
    )
    parser.add_argument(
        "-o",
        "--options",
        metavar="FORMAT-OPTIONS",
        help="Selected format options. TBD",
    )
    parser.add_argument(
        "input",
        metavar="INPUT-FILE",
        type=Path,
        help="Path to the input comic book file.",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT-FILE",
        type=Path,
        nargs="?",
        help="Path to the output CBZ file.",
    )
    params: argparse.Namespace = parser.parse_args(argv)

    quality: int | None = None
    options: JpegXLOptions | None = None

    if params.options == "":
        parser.error("--option value shall not be empty")

    if params.format in (ImageFormat.JPEG, ImageFormat.JPEGXL, ImageFormat.JPEGLI):
        if params.quality is None:
            quality = 90
        elif params.quality in JPEG_RANGE:
            quality = params.quality
        else:
            parser.error(
                f"--quality for {params.format} only admits values from 0 to 100"
            )
        if params.format == ImageFormat.JPEGXL and params.options is not None:
            options = JpegXLOptions.parse_options(params.options)

    elif params.format == ImageFormat.PNG:
        if params.quality is None:
            quality = 6
        elif params.quality in PNG_RANGE:
            quality = params.quality
        else:
            parser.error("--quality for png only admits values from 0 to 9")

    output: Path = (
        params.input.with_suffix(".cbz") if params.output is None else params.output
    )

    parsed: Parameters = Parameters(
        format=params.format,
        quality=quality,
        options=options,
        input=params.input,
        output=output,
    )
    return parsed


def main(argv: Sequence[str] | None = None) -> None:
    """Main function that executes the script."""
    parse_params(argv)


if __name__ == "__main__":
    main()
