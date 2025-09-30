#!/usr/bin/python

# cb2cbz, a script that converts from comic book archives to CBZ files.
# Copyright (C) 2025  Lawrence González
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Script that converts comic book archives to CBZ files."""

from __future__ import annotations

import argparse
import datetime
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Final, assert_never

from libarchive import (  # type: ignore[import-untyped]
    ArchiveEntry,
    file_reader,
    file_writer,
)
from libarchive.write import ArchiveWrite  # type: ignore[import-untyped]
from PIL import Image, UnidentifiedImageError

from . import converters

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from libarchive.read import (  # type: ignore[import-untyped]
        ArchiveRead,
        ArchiveWrite,
    )


@dataclass
class Parameters:
    """Parsed CLI parameters.

    Attributes:
        converter: Converter that will be used for converting images.
            None if no conversion should be done.
        input: Path to input comic book file.
        output: Path to output CBZ file.
    """

    converter: converters.BaseConverter | None
    input: Path
    output: Path


def errormsg(msg: str, code: int = 0) -> None:
    """Prints an error message.

    Args:
        msg: Message that must be printed.
        code: Exit code. If it's 0 then the message will be a warning,
            else will be an error message and the program will closen
            with that code.

    Raises:
        ValueError: If the code is not between 0 and 255.
    """
    if code not in range(256):
        errmsg: str = "code is not between 0 and 255"
        raise ValueError(errmsg)

    msg_type: str = "Error" if code > 0 else "Warning"
    print(f"{Path(sys.argv[0]).name}: {msg_type}: {msg}", file=sys.stderr)
    if code > 0:
        raise SystemExit(code) from None


def wrap_bulleted_text(text: str, width: int) -> str:
    """Devuelve el texto ajustado al tamaño en width.

    Si las líneas tienen espacios iniciales entonces el texto en los
    párrafos también será indentado, y si el texto está en viñetas
    (deben ser hechas con "*" y "-") también es indentado para ajustarlo
    a estas.

    Args:
        text: string a ajustar.
        width: tamaño máximo que debe tener cada línea.
    """
    indent_pattern: Final[re.Pattern[str]] = re.compile(r"^ *(?:[*+-] +)?")
    new_lines: list[str] = []

    for line in text.split("\n"):
        if line.isspace():
            new_lines.append(line)
        elif not line:
            new_lines.extend(textwrap.wrap(line, width))
        else:
            indent_match: re.Match[str] | None = indent_pattern.search(line)
            indent: str = " " * indent_match.end() if indent_match else ""
            new_lines.extend(textwrap.wrap(line, width, subsequent_indent=indent))

    return "\n".join(new_lines)


def parse_params(argv: Sequence[str] | None = None) -> Parameters:
    """Parse CLI parameters and return them."""
    terminal_width: int = shutil.get_terminal_size().columns - 26
    wrap = partial(wrap_bulleted_text, width=terminal_width)

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Converts comic book archives into .cbz files",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=converters.ImageFormat,
        type=converters.ImageFormat,
        default=converters.ImageFormat.NO_CHANGE,
        help=wrap(
            "Image format to which the images in the comic book will be "
            'converted. "jxl" uses lossless compression while "jxl-lossy" does '
            'not, "jpegli" encodes JPEG files using cjpegli and "no-change" '
            "does not change the image's format."
        ),
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        help=wrap(
            "Compression quality. Its meaning depends on the format. For "
            '"jpeg", "jpegli" and "jpegxl" it goes from 0 to 100, the default '
            'for them is 90. For "jpegxl" 100 means mathematically lossless '
            'and 90 visually lossless. For "png" it goes from 0 to 9 and the '
            'default is 6. For "no-change" is ignored.'
        ),
    )
    parser.add_argument(
        "-o",
        "--options",
        default="",
        metavar="FORMAT-OPTIONS",
        help=wrap(
            "Options that will modify compression of each format. The options "
            "and values depend on the selected format. Commas can be used for "
            'separating options like this: "option1=value1,option2=value2". '
            "The available options are:\n "
            "\n"
            "* jpeg:\n"
            '  - optimize: If "true" then does an extra step for optimizing '
            'JPEG encoding. "false" by default\n'
            '  - progressive: If "true" uses progressive encoding. "false" by '
            "default.\n"
            '  - keep_rgb: If "true" uses RGB instead of YCbCr. "false" by default.\n'
            "  - subsampling: Chroma subsampling setting. Valid values are "
            '"4:4:4", "4:2:2", and "4:2:0". If is not specified the encoder '
            "will decide it.\n"
            "* jpegli:\n"
            "  - progressive: Uses progressive encoding. Valid values are:\n"
            '    + "0" or "false": Does not use progressive encoding.\n'
            '    + "1": Does one step of progressive encoding.\n'
            '    + "2" or "true": Does two steps of progressive encoding (default).\n'
            "  - subsampling: Chroma subsampling setting. Valid values are "
            '"4:4:4", "4:4:0", "4:2:2", and "4:2:0".\n'
            '  - xyb: If "true" uses XYB colorspace. Improves compression but '
            'it may be incompatible with several image viewers. "false" by '
            "default.\n"
            '  - adaptive_quantization: If "false" will not use adaptive '
            'quantization. "true" by default.\n'
            '  - std_quant: If "true" will use standard quantization tables. '
            '"false" by default\n'
            '  - fixed_code: If "true" will use fixed encoding. "false" by '
            "default.\n"
            "* jpegxl:\n"
            "  - effort: A number from 1 to 9 that indicates how much "
            "processing will be used for encoding, a bigger number improves "
            'the compression ratio, but will increase CPU and RAM usage. "7" '
            "by default\n"
            "  - decoding_speed: A number from 0 to 4, higher values improve "
            "decode speed at the expense of quality or density.\n"
            "* png:\n"
            '  - optimize: If "true" tells the encoder to search the best '
            'encoding settings. Quality will be adjusted to "9" and it will '
            "increase CPU usage a lot.\n"
        ),
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
    converter: converters.BaseConverter
    output: Path = Path(
        params.input.with_suffix(".cbz") if params.output is None else params.output
    )

    match params.format:
        case converters.ImageFormat.JPEG:
            converter = converters.JpegConverter.parse_options(params.options)
        case converters.ImageFormat.JPEGLI:
            converter = converters.JpegliConverter.parse_options(params.options)
        case converters.ImageFormat.JPEGXL:
            converter = converters.JpegXLConverter.parse_options(params.options)
        case converters.ImageFormat.PNG:
            converter = converters.PngConverter.parse_options(params.options)
            if params.quality is not None:
                if params.quality not in converters.PNG_RANGE:
                    parser.error("--quality for png only admits numbers from 0 to 9")
                converter.quality = params.quality

        case converters.ImageFormat.NO_CHANGE:
            return Parameters(converter=None, input=params.input, output=output)
        case _:  # pragma: no cover
            assert_never(params.format)

    if params.quality is not None and params.format in (
        converters.ImageFormat.JPEG,
        converters.ImageFormat.JPEGXL,
        converters.ImageFormat.JPEGLI,
    ):
        if params.quality not in converters.JPEG_RANGE:
            parser.error(
                f"--quality for {params.format} only admits numbers from 0 to 100"
            )
        converter.quality = params.quality

    parsed: Parameters = Parameters(
        converter=converter, input=params.input, output=output
    )
    return parsed


def get_entry_attrs(entry: ArchiveEntry) -> dict[str, Any]:
    """Get metadata from the entry and return it if they're not None."""
    attr_names: tuple[str, ...] = (
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
    return {i: attr for i in attr_names if (attr := getattr(entry, i)) is not None}


class EntryStorer:
    """Class for storing files into the .cbz file."""

    archive: ArchiveEntry
    converter: converters.BaseConverter | None

    def __init__(
        self, archive: ArchiveWrite, converter: converters.BaseConverter | None
    ) -> None:
        """Initializes the object.

        Args:
            archive: Output .cbz file
            converter: Converter that will be used to convert images. If
                None the no conversion will be done.
        """
        self.archive = archive
        self.converter = converter

    def save_entry(self, entry: ArchiveEntry, name: str) -> None:
        """Saves an entry from the input comic book to the .cbz file.

        Args:
            entry: Entry from the input comic book archive.
            name: Path to the file in the archive that will saved.
        """
        simple_save = partial(
            self.archive.add_file_from_memory,
            entry_path=name,
            entry_size=entry.size,
            filetype=entry.filetype,
            permission=entry.perm,
            **get_entry_attrs(entry),
        )

        if self.converter is None:
            simple_save(entry_data=entry.get_blocks())
            return

        in_buffer: BytesIO
        with BytesIO() as in_buffer:
            for block in entry.get_blocks():
                in_buffer.write(block)

            try:
                img_data: bytes = self.converter.convert(in_buffer)

            except UnidentifiedImageError:
                errormsg(
                    f'Cannot identify if "{entry.pathname}" is an image. '
                    "Skipping its conversion..."
                )
                simple_save(entry_data=in_buffer)
                return

            except subprocess.CalledProcessError as err:
                errormsg(
                    (
                        f'An error happened while encoding "{entry.pathname}": '
                        f"{err.stderr.decode()}"
                    ),
                    1,
                )

            entry_attrs: dict[str, Any] = get_entry_attrs(entry)
            entry_attrs["mtime"] = datetime.datetime.now().astimezone().timestamp()

            self.archive.add_file_from_memory(
                name,
                len(img_data),
                img_data,
                entry.filetype,
                entry.perm,
                **entry_attrs,
            )
            return


def create_new_name(old_name: str, converter: converters.BaseConverter | None) -> str:
    """Returns a new name where a file must be saved in the CBZ file."""
    return (
        old_name
        if converter is None
        else str(PurePath(old_name).with_suffix(converter.extension))
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Main function that executes the script.

    Args:
        argv: Parameters from the command line. If it's None then it'll
            use sys.argv.
    """
    params: Parameters = parse_params(argv)
    input_arc: ArchiveRead
    output_arc: ArchiveWrite
    with (
        file_reader(str(params.input)) as input_arc,
        file_writer(
            str(params.output), "zip", options="compression=store"
        ) as output_arc,
    ):
        entry_storer: EntryStorer = EntryStorer(output_arc, params.converter)
        names: set[str] = set()
        entry: ArchiveEntry
        for entry in input_arc:
            if entry.isdir:
                stripped: str = entry.pathname.strip("/")
                if stripped in names:
                    errormsg(
                        (
                            "Two files in the output CBZ file got the same "
                            f"name due to the conversion: {entry.pathname}"
                        ),
                        1,
                    )
                names.add(stripped)
                output_arc.add_file_from_memory(
                    entry.pathname,
                    0,
                    b"",
                    entry.filetype,
                    entry.perm,
                    **get_entry_attrs(entry),
                )

            elif entry.isreg:
                new_name: str = create_new_name(entry.pathname, params.converter)
                stripped = new_name.strip("/")
                if stripped in names:
                    errormsg(
                        (
                            "Two files in the output CBZ file got the same "
                            f"name due to the conversion: {entry.pathname}"
                        ),
                        1,
                    )
                names.add(stripped)

                entry_storer.save_entry(entry, new_name)
                print(f"{entry.pathname} → {new_name}")


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)
