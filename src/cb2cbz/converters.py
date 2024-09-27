"""Module for image format converters."""

from __future__ import annotations

import abc
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from io import BytesIO
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self

import pillow_jxl
from PIL import Image

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Generator

JPEG_RANGE: Final = range(101)
PNG_RANGE: Final = range(10)
JPEG_DEFAULT: Final = 90
PNG_DEFAULT: Final = 6


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
    if value in {"true", "1"}:
        return True
    if value in {"false", "0"}:
        return False
    msg: str = f'{name} value must be "1", "0", "true" or "false"'
    raise ValueError(msg)


def remove_alpha(img: Image.Image) -> Image.Image:
    """Removes img alpha channel replacing it with a white background."""
    output_mode = "L" if img.mode in {"LA", "La"} else "RGB"
    with Image.new("RGBA", img.size, "WHITE") as background:
        if img.mode != "RGBA":
            with img:
                img = img.convert("RGBA")

        with img:
            background.alpha_composite(img)
            converted: Image.Image = background.convert(output_mode)
            return converted


@contextmanager
def view_manager(buffer: BytesIO) -> Generator[memoryview, None, None]:
    """Creates a context manager and yields BytesIO.getbuffer data."""
    view: memoryview | None = None
    try:
        view = buffer.getbuffer()
        yield view
    finally:
        if view is not None:
            view.release()


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


class JpegSubsamplingEnum(StrEnum):
    """Enumeration for JpegConverter subsampling option."""

    KEEP = "keep"
    S444 = "4:4:4"
    S422 = "4:2:2"
    S420 = "4:2:0"


class JpegConverter(BaseConverter):
    """Converter to JPEG images."""

    format = ImageFormat.JPEG
    pil_format = "JPEG"
    extension = ".jpg"
    options = {"optimize", "progressive", "keep_rgb", "subsampling"}
    quality: int
    subsampling: JpegSubsamplingEnum | None
    optimize: bool
    progressive: bool

    def __init__(
        self,
        quality: int = JPEG_DEFAULT,
        subsampling: JpegSubsamplingEnum | None = None,
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
            keep_rgb: If True use RGB instead of YCbCr.
            progressive: If True use progressive encoding.
            subsampling: Subsampling that will be used by the encoder.
                Available values:

                * "keep": Retains original image settings. Only works
                    with JPEG.
                * "4:4:4", "4:2:2", "4:2:0": Specific subsamplings.
                * None: Will be determined by the encoder.
        """
        if quality not in JPEG_RANGE:
            msg: str = (
                f"quality must be an int between {JPEG_RANGE.start} and "
                f"{JPEG_RANGE.stop - 1}"
            )
            raise ValueError(msg)

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
        subsampling: JpegSubsamplingEnum | None = None
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            match name:
                case "optimize":
                    optimize = parse_str_bool(value, name)
                case "progressive":
                    progressive = parse_str_bool(value, name)
                case "keep_rgb":
                    keep_rgb = parse_str_bool(value, name)
                case "subsampling":
                    try:
                        subsampling = JpegSubsamplingEnum(value)
                    except ValueError as err:
                        msg: str = f'"{value}" is not a valid subsampling'
                        raise ValueError(msg) from err

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
        if img.mode in {"L", "RGB", "CMYK"}:
            return ImageData(img, img.info, new=False)

        if img.mode == "1":
            return ImageData(img.convert("L"), img.info, new=True)

        if img.has_transparency_data:
            # Adds a white background to a transparent image before
            # deleting alpha channel.
            return ImageData(remove_alpha(img), img.info, new=True)

        return ImageData(img.convert("RGB"), img.info, new=True)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the JPEG file."""
        metadata: dict[str, Any] = {"progressive": self.progressive}
        metadata.update(
            filter(
                lambda x: x[0] in {"dpi", "icc_profile", "exif", "comment"},
                meta.items(),
            )
        )
        return metadata


class JpegliProgressiveEnum(IntEnum):
    """Enumeration for JpegliConverter progressive option."""

    ZERO = 0
    ONE = 1
    TWO = 2


class JpegliSubsamplingEnum(StrEnum):
    """Enumeration for JpegliConverter subsampling option."""

    S444 = "444"
    S440 = "440"
    S422 = "422"
    S420 = "420"


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
    progressive: JpegliProgressiveEnum
    subsampling: JpegliSubsamplingEnum | None
    xyb: bool
    adaptive_quantization: bool
    std_quant: bool
    fixed_code: bool

    def __init__(  # noqa: PLR0913
        self,
        quality: int = JPEG_DEFAULT,
        progressive: JpegliProgressiveEnum = JpegliProgressiveEnum.TWO,
        subsampling: JpegliSubsamplingEnum | None = None,
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
                444, 440, 422, 420 or None. If None the default encoder
                setting will be used.
            xyb: If True then will convert using XYB colorspace.
            adaptive_quantization: If True then will use adaptive
                quantization.
            std_quant: If True then will use standard quantization
                tables.
            fixed_code: If True then will disable Huffman code
                optimization. progressive must be 0 if fixed_code is
                True.
        """
        if quality not in JPEG_RANGE:
            msg: str = (
                f"quality must be an int between {JPEG_RANGE.start} and "
                f"{JPEG_RANGE.stop - 1}"
            )
            raise ValueError(msg)
        if fixed_code and progressive != JpegliProgressiveEnum.ZERO:
            msg = "progressive must be 0 if fixed_code is True"
            raise ValueError(msg)

        self.quality = quality
        self.progressive = progressive
        self.subsampling = subsampling
        self.xyb = xyb
        self.adaptive_quantization = adaptive_quantization
        self.std_quant = std_quant
        self.fixed_code = fixed_code

    @classmethod
    def parse_options(cls, options: str) -> Self:  # noqa: C901
        """Parse jpegli format options.

        Available options are: "optimize", "progressive", "keep_rgb" and
        "subsamping"

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        progressive: JpegliProgressiveEnum = JpegliProgressiveEnum.TWO
        subsampling: JpegliSubsamplingEnum | None = None
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
                        progressive = JpegliProgressiveEnum(int(value))
                    except ValueError as err1:
                        try:
                            progressive = JpegliProgressiveEnum(
                                2 if parse_str_bool(value, name) else 0
                            )
                        except ValueError as err2:
                            msg: str = (
                                'progressive value must be "true", "false", '
                                '"0", "1" or "2"'
                            )
                            err2.__cause__ = err1
                            raise ValueError(msg) from err2

                case "subsampling":
                    if value not in {"4:4:4", "4:4:0", "4:2:2", "4:2:0"}:
                        msg = (
                            'subsampling value must be "4:4:4", "4:4:0", '
                            '"4:2:2" or "4:2:0"'
                        )
                        raise ValueError(msg)
                    subsampling = JpegliSubsamplingEnum(value.replace(":", ""))

                case "xyb":
                    xyb = parse_str_bool(value, name)
                case "adaptive_quantization":
                    adaptive_quantization = parse_str_bool(value, name)
                case "std_quant":
                    std_quant = parse_str_bool(value, name)
                case "fixed_code":
                    fixed_code = parse_str_bool(value, name)

        if fixed_code and progressive != JpegliProgressiveEnum.ZERO:
            msg = "progressive must be 0 if fixed_code is true"
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
            params.append("--noadaptive_quantization")
        if self.fixed_code:
            params.append("--fixed_code")
        if self.std_quant:
            params.append("--std_quant")
        params.extend(("-", "-"))
        return params

    def convert(self, in_buffer: BytesIO) -> bytes:
        """Convert an image into JPEG using jpegli encoder and return it."""

        def run(img: Image.Image, info: dict[str, Any]) -> bytes:
            if img.has_transparency_data:
                new_img: Image.Image = remove_alpha(img)
                img.close()
                img = new_img

            elif img.mode not in {"RGB", "L", "P"}:
                new_img = img.convert("RGB")
                img.close()
                img = new_img

            buffer: BytesIO
            with BytesIO() as buffer:
                img.save(
                    buffer,
                    format="PNG",
                    compress_level=0,
                    icc_profile=info.get("icc_profile"),
                    exif=info.get("exif"),
                    dpi=info.get("dpi"),
                )
                img.close()

                view: memoryview
                with view_manager(buffer) as view:
                    return subprocess.run(  # noqa: S603
                        self._get_params(), input=view, capture_output=True, check=True
                    ).stdout

        img: Image.Image
        with Image.open(in_buffer) as img:
            # Workaround for a failure that happens when converting 1-bit images
            if img.mode == "1":
                limg: Image.Image = img.convert("L")
                img.close()
                return run(limg, img.info)

            if (
                img.has_transparency_data
                or img.format not in {"JPEG", "PNG", "PPM"}
                or img.mode not in {"RGB", "L", "P"}
            ):
                return run(img, img.info)

        in_view: memoryview
        with view_manager(in_buffer) as in_view:
            return subprocess.run(  # noqa: S603
                self._get_params(), input=in_view, capture_output=True, check=True
            ).stdout


class JpegXLEffortEnum(IntEnum):
    """Enumeration for JpegXLConverter effort option."""

    LIGHTNING = 1
    THUNDER = 2
    FALCON = 3
    CHEETAH = 4
    HARE = 5
    WOMBAT = 6
    SQIRREL = 7
    KITTEN = 8
    TORTOISE = 9


class JpegXLDecodingSpeedEnum(IntEnum):
    """Enumeration for JpegXLConverter decoding_speed option."""

    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4


class JpegXLConverter(BaseConverter):
    """Converter to JPEG XL images."""

    format = ImageFormat.JPEGXL
    pil_format = "JXL"
    extension = ".jxl"
    options = {"effort", "decoding_speed", "jpegtran"}
    quality: int
    effort: JpegXLEffortEnum
    decoding_speed: JpegXLDecodingSpeedEnum
    jpegtran: bool

    def __init__(
        self,
        quality: int = JPEG_DEFAULT,
        effort: JpegXLEffortEnum = JpegXLEffortEnum.SQIRREL,
        decoding_speed: JpegXLDecodingSpeedEnum = JpegXLDecodingSpeedEnum.ZERO,
        *,
        jpegtran: bool = False,
    ):
        """Initializes the object.

        Args:
            quality: Quality of the compressed image. It must be an int
                between 0 and 100.
            effort: How much processing will be done to do the
                compression. It must be an int between 1 and 10.
            decoding_speed: Improves image decoding speed at the expense
                of quality or density. It must be an int between 0 and
                4.
            jpegtran: If True passes JPEG files to jpegtran program
                before converting JPEG XL. It helps to recover JPEG
                images that have an invalid bitstream that can't be
                decoded by the JPEG XL encoder.

        Raises:
            ValueError: If any of the args is invalid.
        """
        if quality not in JPEG_RANGE:
            msg: str = "quality must be an int between 0 and 100"
            raise ValueError(msg)

        self.quality = quality
        self.effort = effort
        self.decoding_speed = decoding_speed
        self.jpegtran = jpegtran

    @classmethod
    def parse_options(cls, options: str) -> Self:
        """Parse JPEG XL format options.

        Raises:
            ValueError: If there are invalid options or invalid values.
        """
        effort: JpegXLEffortEnum = JpegXLEffortEnum.SQIRREL
        decoding_speed: JpegXLDecodingSpeedEnum = JpegXLDecodingSpeedEnum.ZERO
        jpegtran: bool = False
        name: str
        value: str
        for name, value in cls._parse_opt(options):
            if name == "effort":
                try:
                    effort = JpegXLEffortEnum(int(value))
                except ValueError as err:
                    msg: str = "effort value must be an integer between 1 and 10"
                    raise ValueError(msg) from err

            elif name == "decoding_speed":
                try:
                    decoding_speed = JpegXLDecodingSpeedEnum(int(value))
                except ValueError as err:
                    msg = "decoding_speed value must be an integer between 0 and 4"
                    raise ValueError(msg) from err

            elif name == "jpegtran":
                jpegtran = parse_str_bool(value, "jpegtran")

        return cls(effort=effort, decoding_speed=decoding_speed, jpegtran=jpegtran)

    def _jpg_to_jxl(self, in_buffer: BytesIO, img: Image.Image) -> bytes:

        enc: pillow_jxl.Encoder = pillow_jxl.Encoder(  # type: ignore[call-arg]
            mode=img.mode,
            parallel=True,
            lossless=False,
            quality=self.quality,
            decoding_speed=int(self.decoding_speed),
            effort=int(self.effort),
            use_container=True,
            use_original_profile=True,
        )

        exif: bytes | None = img.info.get("exif", img.getexif().tobytes())
        if exif and exif.startswith(b"Exif\x00\x00"):
            exif = exif[6:]

        if self.jpegtran:
            with view_manager(in_buffer) as view:
                buf_data = subprocess.run(  # noqa: S603
                    ("jpegtran", "-copy", "all"),
                    input=view,
                    capture_output=True,
                    check=True,
                ).stdout
        else:
            buf_data = in_buffer.getvalue()
        in_buffer.close()

        jxl: bytes = enc(  # type: ignore[call-arg]
            buf_data,
            img.width,
            img.height,
            jpeg_encode=True,
            exif=exif,
            jumb=img.info.get("jumb"),
            xmp=img.info.get("xmp"),
        )
        return jxl

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
        img: Image.Image = Image.open(in_buffer)

        if img.format == "JPEG" and img.mode in {"RGB", "L"}:
            with img:
                return self._jpg_to_jxl(in_buffer, img)

        if img.format == "PNG":
            # This is necessary for getting EXIF data if the PNG files has it.
            img.load()

        if img.mode == "1":
            with img:
                return ImageData(img.convert("L"), img.info, new=True)

        if img.mode not in {"RGB", "L"} and not img.has_transparency_data:
            with img:
                return ImageData(
                    img.convert("L" if img.mode == "LA" else "RGB"), img.info, new=True
                )

        if img.mode not in {"RGB", "RGBA", "L", "LA"}:
            with img:
                return ImageData(
                    img.convert("RGBA" if img.has_transparency_data else "RGB"),
                    img.info,
                    new=True,
                )

        return ImageData(img, img.info, new=False)


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
        optimize: bool = False
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
        if img.mode in {"1", "L", "P"}:
            return ImageData(img, img.info, new=False)

        if img.getcolors():
            return ImageData(img.convert("P"), img.info, new=True)

        if img.mode != "RGB" and not img.has_transparency_data:
            return ImageData(img.convert("RGB"), img.info, new=True)

        if img.mode in {"LA", "I", "RGB", "RGBA"}:
            return ImageData(img, img.info, new=False)

        return ImageData(img.convert("RGBA"), img.info, new=True)

    def get_metadata(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Returns metadata that must be saved to the PNG file."""
        metadata: dict[str, Any] = {"optimize": self.optimize}
        metadata.update(
            filter(lambda x: x[0] in {"dpi", "icc_profile", "exif"}, meta.items())
        )
        return metadata
