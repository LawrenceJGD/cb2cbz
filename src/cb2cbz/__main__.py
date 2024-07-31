#!/usr/bin/python

"""Script that converts comic book archives to CBZ files."""

from __future__ import annotations

import abc
import argparse
import datetime
import sys
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, assert_never

import pillow_jxl
from libarchive import (  # type: ignore[import-untyped]
    ArchiveEntry,
    file_reader,
    file_writer,
)
from libarchive.write import ArchiveWrite  # type: ignore[import-untyped]
from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from libarchive.read import (  # type: ignore[import-untyped]
        ArchiveRead,
        ArchiveWrite,
    )

_format = format
_input = input

JPEG_RANGE: Final[range] = range(101)
PNG_RANGE: Final[range] = range(10)
JPEG_DEFAULT: Final[int] = 90
PNG_DEFAULT: Final[int] = 6

EFFORT_RANGE = range(1, 11)
DECODING_SPEED_RANGE = range(10)


def errormsg(msg: str, code: int = 0) -> None:
    """Imprime un mensaje de error.

    Args:
        msg: mensaje a imprimir.
        code: código de salida. Si es `0` el mensaje será una
            advertencia, pero si es mayor a `0` será un mensaje de error
            y el programa cerrará con ese código.
    """
    if code not in range(256):
        exc_msg = "code no esta entre 0 y 255"
        raise ValueError(exc_msg)
    msg_type: str = "error" if code > 0 else "advertencia"
    print(f"{Path(sys.argv[0]).name}: {msg_type}: {msg}", file=sys.stderr)
    if code > 0:
        sys.exit(code)


class ImageFormat(StrEnum):
    """Enum for supported image formats."""

    JPEG = "jpeg"
    JPEGXL = "jpegxl"
    JPEGLI = "jpegli"
    PNG = "png"
    NO_CHANGE = "no-change"


@dataclass
class ImageData:
    """Dataclass for image data returned by converters.

    Attributes:
        img: Converted image.
        meta: A dictionary that contains the original Image.Image.info
            dict with all its metadata.
        new: True if the image is new and does not depend on the input
            BytesIO or viceversa.
    """

    img: Image.Image
    meta: dict[str, Any]
    new: bool


class BaseConverter(metaclass=abc.ABCMeta):
    """Base class for image converters."""

    format: ClassVar[ImageFormat]
    pil_format: ClassVar[str | None]
    extension: ClassVar[str]
    quality: int

    @abc.abstractmethod
    def __init__(self, quality: int) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
        """

    @classmethod
    @abc.abstractmethod
    def parse_options(cls, options: str) -> Self:
        """Parse format options.

        Raises:
            ValueError: If there are invalid options or invalid values.
        """

    @abc.abstractmethod
    def convert(self, in_buffer: BytesIO) -> ImageData | bytes:
        """Convert an image into another format and return it.

        Args:
            in_buffer: Image data in a BytesIO object.

        Returns:
            A bytes object that contains the entire image or a tuple
            with two elements:

                0. A PIL.Image.Image object that represents the image.
                1. A boolean indicating whether the image depends on the
                    BytesIO object remaining open.

        Raises:
            PIL.UnindentifiedImageError: If Pillow can't identify if
                in_buffer is an image.
        """


class JpegConverter(BaseConverter):
    """Converter to JPEG images."""

    format = ImageFormat.JPEG
    pil_format = "JPEG"
    extension = ".jpg"
    quality: int

    def __init__(self, quality: int = JPEG_DEFAULT) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
        """
        self.quality = quality

    def convert(self, in_buffer: BytesIO) -> ImageData:
        """Convert an image into JPEG and return it.

        Args:
            in_buffer: Image data in a BytesIO object.

        Returns:
            A bytes object that contains a JPEG image or a tuple that has
            two elements:

                0. A PIL.Image.Image object that represents the JPEG
                    image.
                1. A boolean indicating whether the image depends on the
                    BytesIO object remaining open.

        Raises:
            PIL.UnindentifiedImageError: If Pillow can't identify if
                in_buffer is an image.
        """
        img: Image.Image = Image.open(in_buffer)
        if img.mode in ("L", "RGB", "CMYK"):
            return ImageData(img, img.info, new=False)

        if img.info.get("transparency", None) is None:
            return ImageData(img.convert("RGB"), img.info, new=True)

        # Adds a white background to a transparent image before
        # deleting alpha channel.
        with img, Image.new("RGBA", img.size, "WHITE") as new_img:
            if img.mode in ("RGBA", "1", "LA", "RGBa"):
                new_img.paste(img, mask=img)
            else:
                with img.convert("RGBA") as mask:
                    new_img.paste(img, mask=mask)
            return ImageData(new_img.convert("RGB"), img.info, new=True)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the JPEG file."""
        return {
            i: meta[i] for i in {"dpi", "icc_profile", "exif", "comment"} & meta.keys()
        }


class JpegliConverter(BaseConverter):
    """Converter to JPEG images using cjpegli encoder."""

    format = ImageFormat.JPEGLI
    pil_format = None
    quality: int

    def __init__(self, quality: int = JPEG_DEFAULT) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
        """
        self.quality = quality


class JpegXLConverter(BaseConverter):
    """Converter to JPEG XL images."""

    format = ImageFormat.JPEGXL
    pil_format = "JXL"
    extension = ".jxl"
    quality: int = JPEG_DEFAULT
    effort: int
    decoding_speed: int

    def __init__(
        self,
        quality: int = JPEG_DEFAULT,
        effort: int = 7,
        decoding_speed: int = 0,
    ):
        """Initializes the object.

        Args:
            quality: Quality of the compressed image. It must be an int
                between 0 and 100.
            effort: How much processing will be done to do the
                compression. It must be an int between 1 and 100.
            decoding_speed: Improves image decoding speed at the expense
                of quality or density. It must be an int between 0 and
                .4.

        Raises:
            ValueError: If any of the args is invalid.
        """
        if quality not in JPEG_RANGE:
            raise ValueError
        if effort not in EFFORT_RANGE:
            raise ValueError
        if decoding_speed not in DECODING_SPEED_RANGE:
            raise ValueError

        self.quality = quality
        self.effort = effort
        self.decoding_speed = decoding_speed

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse JPEG XL format options.

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        effort: int = 7
        decoding_speed: int = 0
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

            lname: str = name.lower()

            if lname == "effort":
                effort = parse_str_int(value, EFFORT_RANGE, "effort")
            elif lname == "decoding_speed":
                decoding_speed = parse_str_int(
                    value, DECODING_SPEED_RANGE, "decoding_speed"
                )
            else:
                msg = f"{name} is not a valid option for jpegxl"
                raise ValueError(msg)

        return cls(effort=effort, decoding_speed=decoding_speed)

    def convert(self, in_buffer: BytesIO) -> ImageData | bytes:
        """Convert an image into JPEG XL and return it.

        Args:
            in_buffer: Image data in a BytesIO object.

        Returns:
            A bytes object that contains a JPEG XL image or a tuple that
            has two elements:

                0. A PIL.Image.Image object that represents the JPEG XL
                    image.
                1. A boolean indicating whether the image depends on the
                    BytesIO object remaining open.

        Raises:
            PIL.UnindentifiedImageError: If Pillow can't identify if
                in_buffer is an image.
        """
        enc: pillow_jxl.Encoder | None = None
        img: Image.Image = Image.open(in_buffer)
        if img.format == "JPEG":
            enc = pillow_jxl.Encoder(  # type: ignore[call-arg]
                mode=img.mode,
                parallel=True,
                lossless=False,
                quality=self.quality,
                decoding_speed=self.decoding_speed,
                effort=self.effort,
                use_container=True,
                use_original_profile=True,
            )

        else:
            if img.format == "PNG":
                # This is necessary for getting EXIF data if the PNG files has it.
                img.load()

            if img.mode == "1":
                return ImageData(img.convert("L"), img.info, new=True)

            if img.mode != "RGB" and "transparency" in img.info:
                return ImageData(
                    img.convert("L" if img.mode == "LA" else "RGB"), img.info, new=True
                )

            if img.mode not in ("RGB", "RGBA", "L", "LA"):
                return ImageData(img.convert("RGBA"), img.info, new=True)

            return ImageData(img, img.info, new=False)

        buf_data: bytes = in_buffer.getvalue()
        in_buffer.close()

        exif: bytes | None = img.info.get("exif", img.getexif().tobytes())
        if exif and exif.startswith(b"Exif\x00\x00"):
            exif = exif[6:]

        return enc(  # type: ignore[call-arg]
            buf_data,
            img.width,
            img.height,
            jpeg_encode=True,
            exif=exif,
            jumb=img.info.get("jumb"),
            xmp=img.info.get("xmp"),
        )


class PngConverter(BaseConverter):
    """Converter to PNG images."""

    format = ImageFormat.PNG
    pil_format = "PNG"
    extension = ".png"
    quality: int = PNG_DEFAULT

    def __init__(self, quality: int = PNG_DEFAULT):
        """Initializes the object.

        Args:
            quality: Quality of the compressed image. It must be an int
                between 0 and 9.

        Raises:
            ValueError: If any of the args is invalid.
        """
        self.quality = quality

    def convert(self, in_buffer: BytesIO) -> ImageData:
        """Convert an image into PNG and return it.

        Args:
            in_buffer: Image data in a BytesIO object.

        Returns:
            A bytes object that contains a PNG image or a tuple that has
            two elements:

                0. A PIL.Image.Image object that represents the PNG
                    image.
                1. A boolean indicating whether the image depends on the
                    BytesIO object remaining open.

        Raises:
            PIL.UnindentifiedImageError: If Pillow can't identify if
                in_buffer is an image.
        """
        img: Image.Image = Image.open(in_buffer)
        if img.mode in ("1", "L", "P"):
            return ImageData(img, img.info, new=False)

        if img.getcolors():
            return ImageData(img.convert("P"), img.info, new=True)

        if img.mode != "RGB" and not hasattr(img, "transparency"):
            return ImageData(img.convert("RGB"), img.info, new=True)

        if img.mode in ("LA", "I", "RGB", "RGBA"):
            return ImageData(img, img.info, new=False)

        return ImageData(img.convert("RGBA"), img.info, new=True)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the PNG file."""
        return {i: meta[i] for i in {"dpi", "icc_profile"} & meta.keys()}


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

    converter: BaseConverter | None
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
    value = value.lower()
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    msg: str = f'{name} value must be "1", "0", "true" or "false"'
    raise ValueError(msg)


def parse_str_int(value: str, limits: range, name: str) -> int:
    """Parse integer options, check and return them.

    Args:
        value: Value that must be parsed.
        limits: Lower and upper limits for the value.
        name: Name of the option to put in the exception if the value is
            invalid.

    Raises:
        ValueError: If the value is not an integer or is not in the
            limits.
    """
    num: int = int(value)
    if num not in limits:
        msg: str = (
            f"{name} value must be an integer between {limits.start} and "
            f"{limits.stop - 1}"
        )
        raise ValueError(msg)
    return num


def parse_params(argv: Sequence[str] | None = None) -> Parameters:
    """Parse CLI parameters and return them."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Converts comic book archives into .cbz files"
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
        default="",
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
    converter: BaseConverter
    output: Path = Path(
        params.input.with_suffix(".cbz") if params.output is None else params.output
    )

    match params.format:
        case ImageFormat.JPEG:
            converter = JpegConverter.parse_options(params.options)
        case ImageFormat.JPEGLI:
            converter = JpegliConverter.parse_options(params.options)
        case ImageFormat.JPEGXL:
            converter = JpegXLConverter.parse_options(params.options)
        case ImageFormat.PNG:
            converter = PngConverter.parse_options(params.options)
            if params.quality is not None:
                if params.quality not in PNG_RANGE:
                    parser.error("--quality for png only admits numbers from 0 to 9")
                converter.quality = params.quality

        case ImageFormat.NO_CHANGE:
            return Parameters(converter=None, input=params.input, output=output)
        case _:
            assert_never(params.format)

    if params.quality is not None and params.format in (
        ImageFormat.JPEG,
        ImageFormat.JPEGXL,
        ImageFormat.JPEGLI,
    ):
        if params.quality not in JPEG_RANGE:
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
    converter: BaseConverter | None

    def __init__(self, archive: ArchiveWrite, converter: BaseConverter | None) -> None:
        """Initializes the object.

        Args:
            archive: Output .cbz file
            converter: Converter that will be used to convert images. If
                None the no conversion will be done.
        """
        self.archive = archive
        self.converter = converter

    def _save_buf(
        self, out_name: str, entry: ArchiveEntry, img: Image.Image, meta: dict[str, Any]
    ) -> None:
        if self.converter is None:
            raise ValueError  # TODO @LawrenceJGD: Add an specific message.
        if self.converter.pil_format is None:
            raise ValueError

        entry_attrs: dict[str, Any] = get_entry_attrs(entry)
        entry_attrs["mtime"] = datetime.datetime.now().astimezone().timestamp()

        with BytesIO() as out_buffer:
            if hasattr(self.converter, "get_metadata"):
                img.save(
                    out_buffer,
                    format=self.converter.pil_format,
                    quality=self.converter.quality,
                    **self.converter.get_metadata(meta),
                )
            else:
                img.save(
                    out_buffer,
                    format=self.converter.pil_format,
                    quality=self.converter.quality,
                )
            data: bytes = out_buffer.getvalue()

        self.archive.add_file_from_memory(
            out_name,
            len(data),
            data,
            entry.filetype,
            entry.perm,
            **entry_attrs,
        )

    def save_entry(self, entry: ArchiveEntry) -> str:
        """Saves an entry from the input comic book to the .cbz file.

        Args:
            entry: Entry from the input comic book archive.
            archive: Output .cbz file.
            converter: If is not None then it'll try to convert the
                entry into another image format.

        Returns:
            Path to where the entry was saved in the .cbz file.
        """

        def simple_save():
            self.archive.add_file_from_memory(
                entry.pathname,
                entry.size,
                entry.get_blocks(),
                entry.filetype,
                entry.perm,
                **get_entry_attrs(entry),
            )

        if self.converter is None:
            simple_save()
            return entry.pathname

        out_name: str = str(
            PurePath(entry.pathname).with_suffix(self.converter.extension)
        )
        in_buffer: BytesIO
        with BytesIO() as in_buffer:
            for block in entry.get_blocks():
                in_buffer.write(block)

            try:
                img_data: ImageData | bytes = self.converter.convert(in_buffer)

            except UnidentifiedImageError:
                errormsg(
                    f'Cannot identify if "{entry.pathname}" is an image. '
                    "Skipping conversion..."
                )
                simple_save()
                return entry.pathname

            if isinstance(img_data, bytes):
                entry_attrs: dict[str, Any] = get_entry_attrs(entry)
                entry_attrs["mtime"] = datetime.datetime.now().astimezone().timestamp()

                self.archive.add_file_from_memory(
                    out_name,
                    len(img_data),
                    img_data,
                    entry.filetype,
                    entry.perm,
                    **entry_attrs,
                )
                return out_name

            if not img_data.new:
                with img_data.img:
                    self._save_buf(out_name, entry, img_data.img, img_data.meta)
                return out_name

        with img_data.img:
            self._save_buf(out_name, entry, img_data.img, img_data.meta)
        return out_name


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
        entry: ArchiveEntry
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
                new_name = entry_storer.save_entry(entry)
                print(f"{entry.pathname} → {new_name}")


if __name__ == "__main__":
    main()
