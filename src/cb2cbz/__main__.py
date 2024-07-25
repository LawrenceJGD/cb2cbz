#!/usr/bin/python

"""Script that converts comic book files to CBZ files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Final, Self

import libarchive
import libarchive.entry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from libarchive.read import ArchiveRead, ArchiveWrite

_format = format
_input = input

JPEG_RANGE: Final[range] = range(101)
PNG_RANGE: Final[range] = range(10)
JPEG_DEFAULT: Final[int] = 90
PNG_DEFAULT: Final[int] = 6


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

    lossless: bool = True

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
                raise ValueError(msg)
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


def parse_str_bool(value: str, name: str) -> bool:
    """Parse boolean options and return them.

    Args:
        value: Value that must be parsed.
        name: Name of the option to put in the exception if the value is
            invalid.

    Raises:
        ValueError: If the value is not "1", "0", "true" or "false".
    """
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
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
        type=int,
        help=(
            "Compression quality. Its meaning depends on the format. For "
            '"jpeg", "jpegli" and "jpegxl" it goes from 0 to 100, the default '
            'for them is 90. For "jpegxl" 100 means lossless. For "png" it '
            'goes from 0 to 9 and the default is 6. For "no-change" is '
            "ignored."
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
            quality = JPEG_DEFAULT
        elif params.quality in JPEG_RANGE:
            quality = params.quality
        else:
            parser.error(
                f"--quality for {params.format} only admits numbers from 0 to 100"
            )
        if params.format == ImageFormat.JPEGXL and params.options is not None:
            options = JpegXLOptions.parse_options(params.options)

    elif params.format == ImageFormat.PNG:
        if params.quality is None:
            quality = PNG_DEFAULT
        elif params.quality in PNG_RANGE:
            quality = params.quality
        else:
            parser.error("--quality for png only admits numbers from 0 to 9")

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


def get_entry_attrs(entry: libarchive.ArchiveEntry) -> dict[str, Any]:
    """Get metadata from the entry and return it if they're not None."""
    attr_names: tuple[str] = (
        "uid",
        "gid",
        "uname",
        "gname",
        "atime",
        "mtime",
        "ctime",
        "birthtime",
        "rdev",
        "rdevmajor",
        "rdevminor",
    )
    attrs: dict[str, Any] = {}
    for name in attr_names:
        attr_data: Any = getattr(entry, name)
        if attr_data is not None:
            attrs[name] = attr_data
    return attrs


def save_file(
    entry: libarchive.ArchiveEntry,
    archive: ArchiveWrite,
    img_format: ImageFormat,
    options: JpegXLOptions | None,
) -> None:
    """Save files to the output .cbz file.

    Args:
        entry: Entry from the input file to save in the .cbz file.
        archive: File where the data must be saved.
        img_format: Format to which the image should be converted.
        options: Options for image convertion.
    """
    if img_format == ImageFormat.NO_CHANGE:
        archive.add_file_from_memory(
            entry.pathname,
            entry.size,
            entry.get_blocks(),
            entry.filetype,
            entry.perm,
            **get_entry_attrs(entry),
        )


def main(argv: Sequence[str] | None = None) -> None:
    """Main function that executes the script."""
    params: Parameters = parse_params(argv)
    input_arc: ArchiveRead
    output_arc: ArchiveWrite
    with (
        libarchive.file_reader(str(params.input)) as input_arc,
        libarchive.file_writer(
            str(params.output), "zip", options="compression=store"
        ) as output_arc,
    ):
        entry: libarchive.ArchiveEntry
        for entry in input_arc:
            if entry.isdir:
                output_arc.add_file_from_memory(
                    entry.pathname,
                    0,
                    b"",
                    entry.filetype,
                    entry.perm,
                    **get_entry_attrs(entry),
                )

            elif entry.isreg:
                save_file(entry, output_arc, params.format, params.options)


if __name__ == "__main__":
    main()
