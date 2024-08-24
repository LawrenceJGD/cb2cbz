#!/usr/bin/python

"""Script that converts comic book archives to CBZ files."""

from __future__ import annotations

import abc
import argparse
import contextlib
import datetime
import subprocess
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

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Generator, Iterable, Sequence

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

DEFAULT_JPEGLI_PROGRESSIVE: Final[int] = 2
JPEGLI_PROGRESSIVE_RANGE: Final[range] = range(3)

DEFAULT_EFFORT: Final[int] = 7
DEFAULT_DECODING_SPEED: Final[int] = 0

EFFORT_RANGE: Final[range] = range(1, 11)
DECODING_SPEED_RANGE: Final[range] = range(5)


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
    options: ClassVar[set[str]]
    quality: int

    @abc.abstractmethod
    def __init__(self, quality: int) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
        """

    @classmethod
    def _parse_opt(cls, options: str) -> Generator[tuple[str, str], None, None]:
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
            if name not in cls.options:
                msg = f"{name} is not a valid option for {cls.format}"
                raise ValueError(msg)

            yield (name.lower(), value)

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
    options = {"optimize", "progressive", "keep_rgb", "subsampling"}
    progressive: bool
    quality: int

    def __init__(
        self,
        quality: int = JPEG_DEFAULT,
        subsampling: str | None = None,
        *,
        optimize: bool = False,
        keep_rgb: bool = False,
        progressive: bool = True,
    ) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
            optimize: If True does an extra step when encoding the image
                to optimize the compression.
            keep_rgb: Use RGB instead of YCbCr.
            progressive: Use progressive encoding.
            subsampling: Subsampling that will be used by the encoder.
                Available values:

                * "keep": Retains original image settings. Only works
                    with JPEG.
                * "4:4:4", "4:2:2", "4:2:0": Specific subsamplings.
                * None: Will be determined by the encoder.
        """
        self.quality = quality
        self.optimize = optimize
        self.keep_rgb = keep_rgb
        self.progressive = progressive
        self.subsampling = subsampling

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse JPEG format options.

        Available options are: "optimize", "progressive", "keep_rgb" and
        "subsamping"

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        optimize: bool = False
        progressive: bool = True
        keep_rgb: bool = False
        subsampling: str | None = None
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            if name == "optimize":
                optimize = parse_str_bool(value, name)
            elif name == "progressive":
                progressive = parse_str_bool(value, name)
            elif name == "keep_rgb":
                keep_rgb = parse_str_bool(value, name)
            elif name == "subsampling":
                if value not in ("keep", "4:4:4", "4:2:2", "4:2:0"):
                    msg: str = f'"{value}" is not a valid subsampling'
                    raise ValueError(msg)
                subsampling = value
        return cls(
            optimize=optimize,
            progressive=progressive,
            keep_rgb=keep_rgb,
            subsampling=subsampling,
        )

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

        if not img.has_transparency_data:
            return ImageData(img.convert("RGB"), img.info, new=True)

        # Adds a white background to a transparent image before
        # deleting alpha channel.
        return ImageData(remove_alpha(img), img.info, new=True)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the JPEG file."""
        metadata: dict[str, Any] = {
            i: meta[i] for i in {"dpi", "icc_profile", "exif", "comment"} & meta.keys()
        }
        metadata["progressive"] = self.progressive
        return metadata


class JpegliConverter(BaseConverter):
    """Converter to JPEG images using cjpegli encoder."""

    format = ImageFormat.JPEGLI
    pil_format = None
    extension = ".jpg"
    options = {
        "progressive",
        "subsampling",
        "xyb",
        "adaptive_quantization",
        "std_quant",
        "fixed_code",
    }
    quality: int
    progressive: int
    subsampling: str | None
    xyb: bool
    adaptive_quantization: bool
    std_quant: bool
    fixed_code: bool

    def __init__(  # noqa: PLR0913
        self,
        quality: int = JPEG_DEFAULT,
        progressive: int = DEFAULT_JPEGLI_PROGRESSIVE,
        subsampling: str | None = None,
        *,
        xyb: bool = False,
        adaptive_quantization: bool = True,
        std_quant: bool = False,
        fixed_code: bool = False,
    ) -> None:
        """Initializes the object.

        Args:
            quality: Quality of the compressed image.
            progressive: Number of passes for progressive encoding. 0
                means no progressive encoding. Must be a int between 0
                and 2.
            subsampling: Chroma subsampling setting. Valid values are:
                "444", "440", "422", "420" or None. If None the default
                encoder setting will be used.
            xyb: If True then will convert using XYB colorspace.
            adaptive_quantization: If True then will use adaptive
                quantization.
            std_quant: If True then will use standard quantization
                tables.
            fixed_code: If True then will disable Huffman code
                optimization. progressive must be 0 if fixed_code is
                True.
        """
        self.quality = quality
        self.progressive: int = progressive
        self.subsampling: str | None = subsampling
        self.xyb: bool = xyb
        self.adaptive_quantization: bool = adaptive_quantization
        self.std_quant: bool = std_quant
        self.fixed_code: bool = fixed_code

    @classmethod
    def parse_options(cls, options: str) -> Self:  # noqa: C901, PLR0912
        """Parse JPEG format options.

        Available options are: "optimize", "progressive", "keep_rgb" and
        "subsamping"

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        progressive: int = 2
        subsampling: str | None = None
        xyb: bool = False
        adaptive_quantization: bool = True
        std_quant: bool = False
        fixed_code: bool = False
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            match name:
                case "progressive":
                    try:
                        prog: int | bool = parse_str_int(value, range(3), name)
                    except ValueError:
                        try:
                            prog = parse_str_bool(value, name)
                        except ValueError:
                            msg: str = (
                                'progressive value must be "true", "false", '
                                '"0", "1" or "2"'
                            )
                            raise ValueError(msg) from None

                    if prog is True:
                        progressive = 2
                    elif prog is False:
                        progressive = 0
                    else:
                        progressive = prog

                case "subsampling":
                    if value not in ("4:4:4", "4:4:0", "4:2:2", "4:2:0"):
                        msg = (
                            'subsampling value must be "4:4:4", "4:4:0", "4:2:2" '
                            'and "4:2:0"'
                        )
                        raise ValueError(msg)
                    subsampling = value.replace(":", "")

                case "xyb":
                    xyb = parse_str_bool(value, name)
                case "adaptive-quantization":
                    adaptive_quantization = parse_str_bool(value, name)
                case "std-quant":
                    std_quant = parse_str_bool(value, name)
                case "fixed-code":
                    fixed_code = parse_str_bool(value, name)

        if fixed_code and progressive != 0:
            msg = "progressive must be 0 if fixed-code is true"
            raise ValueError(msg)

        return cls(
            progressive=progressive,
            subsampling=subsampling,
            xyb=xyb,
            adaptive_quantization=adaptive_quantization,
            std_quant=std_quant,
            fixed_code=fixed_code,
        )

    def _get_params(self) -> list[str]:
        params: list[str] = [
            "cjpegli",
            "--quiet",
            f"--quality={self.quality}",
            f"--progressive_level={self.progressive}",
        ]
        if self.subsampling:
            params.append(f"--chroma_subsampling={self.subsampling}")
        if self.xyb:
            params.append("--xyb")
        if not self.adaptive_quantization:
            params.append("--noadaptive-quantization")
        if self.fixed_code:
            params.append("--fixed_code")
        if self.std_quant:
            params.append("--std_quant")
        params.extend(("-", "-"))
        return params

    def convert(self, in_buffer: BytesIO) -> bytes:
        """Convert an image into JPEG using jpegli encoder and return it."""

        @contextlib.contextmanager
        def view_manager(buffer: BytesIO) -> Generator[memoryview, None, None]:
            view: memoryview | None = None
            try:
                view = buffer.getbuffer()
                yield view
            finally:
                if view is not None:
                    view.release()

        def run(img: Image.Image, info: dict[str, Any]) -> bytes:
            buffer: BytesIO
            with BytesIO() as buffer:
                with img:
                    img.save(
                        buffer,
                        format="PNG",
                        compress_level=0,
                        icc_profile=info.get("icc_profile"),
                        exif=info.get("exif"),
                        dpi=info.get("dpi"),
                    )

                view: memoryview
                with view_manager(buffer) as view:
                    return subprocess.run(  # noqa: S603
                        self._get_params(), input=view, capture_output=True, check=True
                    ).stdout

        img: Image.Image
        with Image.open(in_buffer) as img:
            if img.format == "PNG" and img.mode == "1":
                limg: Image.Image = img.convert("L")
                img.close()
                return run(limg, img.info)

            if (
                img.format == "PNG"
                and img.has_transparency_data
                or img.format not in ("JPEG", "PNG", "APNG", "GIF", "PPM", "PFM")
            ):
                return run(remove_alpha(img), img.info)

        in_view: memoryview
        with view_manager(in_buffer) as in_view:
            return subprocess.run(  # noqa: S603
                self._get_params(), input=in_view, capture_output=True, check=True
            ).stdout


class JpegXLConverter(BaseConverter):
    """Converter to JPEG XL images."""

    format = ImageFormat.JPEGXL
    pil_format = "JXL"
    extension = ".jxl"
    options = {"effort", "decoding-speed"}
    quality: int
    effort: int
    decoding_speed: int

    def __init__(
        self,
        quality: int = JPEG_DEFAULT,
        effort: int = DEFAULT_EFFORT,
        decoding_speed: int = DEFAULT_DECODING_SPEED,
    ):
        """Initializes the object.

        Args:
            quality: Quality of the compressed image. It must be an int
                between 0 and 100.
            effort: How much processing will be done to do the
                compression. It must be an int between 1 and 100.
            decoding_speed: Improves image decoding speed at the expense
                of quality or density. It must be an int between 0 and
                4.

        Raises:
            ValueError: If any of the args is invalid.
        """
        if quality not in JPEG_RANGE:
            msg: str = "quality must be an int between 0 and 100"
            raise ValueError(msg)
        if effort not in EFFORT_RANGE:
            msg = "effort must be an int between 1 and 10"
            raise ValueError(msg)
        if decoding_speed not in DECODING_SPEED_RANGE:
            msg = "decoding_speed must be an int between 0 and 4"
            raise ValueError(msg)

        self.quality = quality
        self.effort = effort
        self.decoding_speed = decoding_speed

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse JPEG XL format options.

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        effort: int = DEFAULT_EFFORT
        decoding_speed: int = DEFAULT_DECODING_SPEED
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            if name == "effort":
                effort = parse_str_int(value, EFFORT_RANGE, "effort")
            elif name == "decoding-speed":
                decoding_speed = parse_str_int(
                    value, DECODING_SPEED_RANGE, "decoding-speed"
                )

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

        if img.format == "JPEG" and img.mode in ("RGB", "L"):
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

            buf_data: bytes
            if isinstance(in_buffer, BytesIO):
                buf_data = in_buffer.getvalue()
            else:
                in_buffer.seek(0)
                buf_data = in_buffer.read()
            in_buffer.close()

            exif: bytes | None = img.info.get("exif", img.getexif().tobytes())
            if exif and exif.startswith(b"Exif\x00\x00"):
                exif = exif[6:]

            with img:
                return enc(  # type: ignore[call-arg]
                    buf_data,
                    img.width,
                    img.height,
                    jpeg_encode=True,
                    exif=exif,
                    jumb=img.info.get("jumb"),
                    xmp=img.info.get("xmp"),
                )

        if img.format == "PNG":
            # This is necessary for getting EXIF data if the PNG files has it.
            img.load()

        if img.mode == "1":
            with img:
                return ImageData(img.convert("L"), img.info, new=True)

        if img.mode not in ("RGB", "L") and not img.has_transparency_data:
            with img:
                return ImageData(
                    img.convert("L" if img.mode == "LA" else "RGB"), img.info, new=True
                )

        if img.mode not in ("RGB", "RGBA", "L", "LA"):
            with img:
                return ImageData(
                    img.convert("RGBA" if img.has_transparency_data else "RGB"),
                    img.info,
                    new=True,
                )

        return ImageData(img, img.info, new=False)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the JPEG XL file."""
        metadata: dict[str, Any] = {
            i: meta[i] for i in {"exif", "jumb", "xmp", "icc_profile"} & meta.keys()
        }
        metadata["effort"] = self.effort
        metadata["decoding_speed"] = self.decoding_speed
        return metadata


class PngConverter(BaseConverter):
    """Converter to PNG images."""

    format = ImageFormat.PNG
    pil_format = "PNG"
    extension = ".png"
    options = {"optimize"}
    quality: int = PNG_DEFAULT
    optimize: bool

    def __init__(self, quality: int = PNG_DEFAULT, *, optimize: bool = False):
        """Initializes the object.

        Args:
            quality: Quality of the compressed image. It must be an int
                between 0 and 9.
            optimize: Tells the encoded to search the best encoding
                options, but it will take a lot of time. Ignores quality
                and always uses `quality=9`.

        Raises:
            ValueError: If any of the args is invalid.
        """
        self.quality = quality
        self.optimize = optimize

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse PNG format options.

        The only option available is "optimize".

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        optimize = False
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            if name == "optimize":
                optimize = parse_str_bool(value, name)
        return cls(optimize=optimize)

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
        metadata: dict[str, Any] = {
            i: meta[i] for i in {"dpi", "icc_profile"} & meta.keys()
        }
        metadata["optimize"] = self.optimize
        return metadata


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


def remove_alpha(img: Image.Image) -> Image.Image:
    """Removes img alpha channel replacing it with a white background."""
    output_mode = "L" if img.mode in ("LA", "La") else "RGB"
    with Image.new("RGBA", img.size, "WHITE") as background:
        if img.mode != "RGBA":
            with img:
                img = img.convert("RGBA")

        with img:
            background.alpha_composite(img)
            converted: Image.Image = background.convert(output_mode)
            return converted


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
        case _:  # pragma: no cover
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

    def save_entry(self, entry: ArchiveEntry, name: str) -> None:
        """Saves an entry from the input comic book to the .cbz file.

        Args:
            entry: Entry from the input comic book archive.
            name: Path to the file in the archive that will saved.

        Returns:
            Path to where the entry was saved in the .cbz file.
        """

        def simple_save(data: bytes | Iterable[bytes]) -> None:
            self.archive.add_file_from_memory(
                name,
                entry.size,
                data,
                entry.filetype,
                entry.perm,
                **get_entry_attrs(entry),
            )

        if self.converter is None:
            simple_save(entry.get_blocks())
            return

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
                simple_save(in_buffer)
                return

            except subprocess.CalledProcessError as err:
                errormsg(
                    (
                        f'An error happened while encoding "{entry.pathname}": '
                        f"{err.stderr.decode()}"
                    ),
                    1,
                )

            if isinstance(img_data, bytes):
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

            if not img_data.new:
                with img_data.img:
                    self._save_buf(name, entry, img_data.img, img_data.meta)
                return

        with img_data.img:
            self._save_buf(name, entry, img_data.img, img_data.meta)


def create_new_name(old_name: str, converter: BaseConverter | None) -> str:
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
                        f'At least two entries got the same name "{entry.pathname}"', 1
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
                    errormsg(f'At least two entries got the same name "{new_name}"', 1)
                names.add(stripped)

                entry_storer.save_entry(entry, new_name)
                print(f"{entry.pathname} → {new_name}")


if __name__ == "__main__":
    main()
