"""Tests for __main__ module."""

# ruff: noqa: S101

import sys
from io import BytesIO
from itertools import chain, product
from pathlib import Path, PurePath
from types import NoneType

import pytest
from cb2cbz import __main__
from libarchive import file_reader, file_writer
from PIL import Image

EXTENSIONS = ("cbt", "cb7", "cbr", "cbz")
CONVERTERS = (
    __main__.JpegConverter,
    # __main__.JpegliConverter,
    __main__.JpegXLConverter,
    # __main__.PngConverter,
)


class TestErrormsg:
    """Test errormsg function."""

    def test_errormsg_default(self, capsys):
        """Test default args for errormsg."""
        __main__.errormsg("test")
        captured = capsys.readouterr()
        assert captured.err.strip() == f"{PurePath(sys.argv[0]).name}: Warning: test"

    def test_errormsg_warning(self, capsys):
        """Test errormsg warnings."""
        __main__.errormsg("test", 0)
        captured = capsys.readouterr()
        assert captured.err.strip() == f"{PurePath(sys.argv[0]).name}: Warning: test"

    def test_errormsg_error(self, capsys):
        """Test errormsg errors."""
        for i in range(1, 256):
            with pytest.raises(SystemExit):
                __main__.errormsg("test", i)

            captured = capsys.readouterr()
            assert captured.err.strip() == f"{PurePath(sys.argv[0]).name}: Error: test"

    def test_errormsg_invalid_code(self):
        """Test errormsg using invalid numbers for code arg."""
        for i in chain(range(-256, 0), range(256, 512)):
            with pytest.raises(ValueError, match="code is not between 0 and 255"):
                __main__.errormsg("test", i)


class TestJpegXLConverter:
    """Test JpegXLConverter methods."""

    def test_jpegxlconverter_init(self):
        """Test __init__ method."""
        test_quality = 12
        test_effort = 3
        test_decoding_speed = 4

        converter = __main__.JpegXLConverter(
            quality=test_quality, effort=test_effort, decoding_speed=test_decoding_speed
        )

        assert isinstance(converter, __main__.JpegXLConverter)
        assert converter.quality == test_quality
        assert converter.effort == test_effort
        assert converter.decoding_speed == test_decoding_speed

    def test_jpegxlconverter_init_invalid_quality(self):
        """Test JpegXLConverter.__init__ using invalid quality values."""
        for i in (-1, 101):
            with pytest.raises(
                ValueError, match="quality must be an int between 0 and 100"
            ):
                __main__.JpegXLConverter(quality=i)

    def test_jpegxlconverter_init_invalid_effort(self):
        """Test JpegXLConverter.__init__ using invalid effort values."""
        for i in (0, 11):
            with pytest.raises(
                ValueError, match="effort must be an int between 1 and 10"
            ):
                __main__.JpegXLConverter(effort=i)

    def test_jpegxlconverter_init_invalid_decoding_speed(self):
        """Test JpegXLConverter.__init__ using an invalid decoding_speed."""
        for i in (-1, 5):
            with pytest.raises(
                ValueError, match="decoding_speed must be an int between 0 and 4"
            ):
                __main__.JpegXLConverter(decoding_speed=i)

    def test_jpegxlconverter_parse_options_effort(self):
        """Test valid values for effort option."""
        for num in __main__.EFFORT_RANGE:
            converter = __main__.JpegXLConverter.parse_options(f"effort={num}")
            assert isinstance(converter, __main__.JpegXLConverter)
            assert converter.effort == num

    def test_jpegxlconverter_parse_options_invalid_effort(self):
        """Test invalid values for effort option."""
        for num in chain(range(-10, 1), range(11, 21)):
            with pytest.raises(ValueError):
                __main__.JpegXLConverter.parse_options(f"effort={num}")

    def test_jpegxlconverter_parse_options_decoding_speed(self):
        """Test valid values for decoding_speed option."""
        for num in __main__.DECODING_SPEED_RANGE:
            converter = __main__.JpegXLConverter.parse_options(f"decoding-speed={num}")
            assert isinstance(converter, __main__.JpegXLConverter)
            assert converter.decoding_speed == num

    def test_jpegxlconverter_parse_options_invalid_decoding_speed(self):
        """Test invalid values for decoding_speed option."""
        for num in chain(range(-10, 0), range(10, 20)):
            with pytest.raises(ValueError):
                __main__.JpegXLConverter.parse_options(f"decoding-speed={num}")

    def test_jpegxlconverter_invalid_parse_options(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test option value is empty"):
            __main__.JpegXLConverter.parse_options("test")

    def test_jpegxlconverter_parse_options_invalid_name(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test is not a valid option for jpegxl"):
            __main__.JpegXLConverter.parse_options("test=abc")

    def test_jpegxlconverter_convert_png_l(self, shared_datadir):
        """Test convert function using a PNG image in mode L."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2953_alien_theories.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "L"
            assert not result.new

    def test_jpegxlconverter_convert_png_1bit(self, shared_datadir):
        """Test convert function using a PNG image in mode 1."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2952_routine_maintenance_1bit.png").open(
            mode="rb"
        ) as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "L"
            assert result.new

    def test_jpegxlconverter_convert_png_l_alpha(self, shared_datadir):
        """Test convert function using a PNG image in mode LA."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2955_pole_vault_L_alpha.png").open(
            mode="rb"
        ) as img_file:
            result = converter.convert(img_file)
            print(result.img.mode)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "LA"
            assert not result.new

    def test_jpegxlconverter_convert_png_rgba(self, shared_datadir):
        """Test convert function using a PNG image in mode RGBA."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2955_pole_vault_rgba.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            print(result.img.mode)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGBA"
            assert not result.new

    def test_jpegxlconverter_convert_png_p(self, shared_datadir):
        """Test convert function using a PNG image in mode P."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2955_pole_vault_p.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGB"
            assert result.new

    def test_jpegxlconverter_convert_png_p_alpha(self, shared_datadir):
        """Test convert function using a PNG image in mode P with alpha."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2955_pole_vault_p_alpha.png").open(
            mode="rb"
        ) as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, __main__.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGBA"
            assert result.new

    def test_jpegxlconverter_convert_jpeg_file(self, shared_datadir):
        """Test convert function using a JPEG."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2953_alien_theories_2.jpg").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, bytes)

    def test_jpegxlconverter_convert_jpeg_bytesio(self, shared_datadir):
        """Test convert function using a JPEG from a BytesIO object."""
        converter = __main__.JpegXLConverter()
        with (shared_datadir / "2953_alien_theories_2.jpg").open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
            assert isinstance(result, bytes)


@pytest.mark.parametrize(
    "converter",
    [
        __main__.JpegConverter,
        __main__.JpegliConverter,
        __main__.JpegXLConverter,
        __main__.PngConverter,
    ],
)
def test_parameter_init(converter):
    """Test Parameter.__init__."""
    params = __main__.Parameters(
        converter=converter, input=Path("test.cbr"), output=Path("tested.cbz")
    )
    assert params.converter == converter
    assert params.input == Path("test.cbr")
    assert params.output == Path("tested.cbz")


class TestParseStrBool:
    """Test parse_str_bool function."""

    @pytest.mark.parametrize("value", ("1", "true", "TRUE", "tRuE"))
    def test_parse_str_true(self, value):
        """Test true values."""
        assert __main__.parse_str_bool(value, "test")

    @pytest.mark.parametrize("value", ("0", "false", "FALSE", "fAlSe"))
    def test_parse_str_false(self, value):
        """Test false values."""
        assert not __main__.parse_str_bool(value, "test")

    def test_parse_str_invalid(self):
        """Test invalid values."""
        with pytest.raises(
            ValueError, match='test value must be "1", "0", "true" or "false"'
        ):
            __main__.parse_str_bool("testing", "test")


class TestParseStrInt:
    """Tests for parse_str_int."""

    def test_valid_parse_str_int(self):
        """Test valid values for parse_str_int."""
        test_range = range(-5, 6)
        for i in test_range:
            assert __main__.parse_str_int(str(i), test_range, "test") == i

    def test_invalid_parse_str_int(self):
        """Test invalid values for parse_str_int."""
        test_range = range(30)
        for i in ("a", "bC", "0x15", "0o15"):
            with pytest.raises(ValueError):
                __main__.parse_str_int(i, test_range, "test")

    def test_parse_str_int_not_in_limits(self):
        """Test numbers that are out of limits."""
        out_of_limits = chain(range(-5, 0), range(6, 11))
        test_range = range(6)
        for i in out_of_limits:
            with pytest.raises(
                ValueError,
                match=(
                    "test value must be an integer between "
                    f"{test_range.start} and {test_range.stop - 1}"
                ),
            ):
                __main__.parse_str_int(i, test_range, "test")


class TestParseParams:
    """Test parse_params function."""

    format_converters = [
        (__main__.ImageFormat.JPEG, __main__.JpegConverter),
        # (__main__.ImageFormat.JPEGLI, __main__.JpegliConverter),
        (__main__.ImageFormat.JPEGXL, __main__.JpegXLConverter),
        # (__main__.ImageFormat.PNG, __main__.PngConverter),
        (__main__.ImageFormat.NO_CHANGE, NoneType),
    ]

    def test_input_only(self):
        """Test only with input argument."""
        params = __main__.parse_params(("test.cbr",))
        assert isinstance(params, __main__.Parameters)
        assert isinstance(params.input, Path)
        assert isinstance(params.output, Path)
        assert params.input == Path("test.cbr")
        assert params.output == Path("test.cbz")
        assert params.converter is None

    def test_output(self):
        """Test output argument."""
        params = __main__.parse_params(("test.cbr", "tested.cbz"))
        assert isinstance(params, __main__.Parameters)
        assert isinstance(params.input, Path)
        assert isinstance(params.output, Path)
        assert params.input == Path("test.cbr")
        assert params.output == Path("tested.cbz")

    @pytest.mark.parametrize("format_,converter", format_converters)
    def test_short_format(self, format_, converter):
        """Test -f argument."""
        params = __main__.parse_params(("-f", str(format_), "test.cbr"))
        assert isinstance(params, __main__.Parameters)
        print(type(params.converter))
        assert isinstance(params.converter, converter)

    @pytest.mark.parametrize("format_,converter", format_converters)
    def test_long_format(self, format_, converter):
        """Test --format argument."""
        params1 = __main__.parse_params(("--format", str(format_), "test.cbr"))
        params2 = __main__.parse_params((f"--format={format_}", "test.cbr"))
        assert isinstance(params1, __main__.Parameters)
        assert isinstance(params2, __main__.Parameters)
        assert isinstance(params1.converter, converter)
        assert isinstance(params2.converter, converter)

    @pytest.mark.parametrize(
        "format_", ("jpeg", "jpegxl")
    )  # TODO @LawrenceJGD: add "jpegli"
    def test_default_quality(self, format_):
        """Test default quality for JPEG formats."""
        params = __main__.parse_params(("--format", format_, "test.cbr"))
        assert params.converter.quality == 90  # noqa: PLR2004

    # TODO @LawrenceJGD: Add when PNG conversion is ready
    # def test_default_png_quality(self):
    #     """Test default quality for PNG."""
    #     params = __main__.parse_params(("--format", "png", "test.cbr"))
    #     assert params.converter.quality == 6  # noqa: PLR2004

    def test_default_no_change_quality(self):
        """Test default quality for no-change."""
        params = __main__.parse_params(("--format", "no-change", "test.cbr"))
        assert params.converter is None

    def test_invalid_format(self):
        """Test if it exits because of an invalid format."""
        with pytest.raises(SystemExit):
            __main__.parse_params(("--format", "failtest", "test.cbr"))

    def test_invalid_jpeg_quality(self):
        """Test if it exits because of an invalid quality for JPEG."""
        for i in ("jpeg", "jpegxl", "jpegli"):
            for j in range(-100, 0):
                with pytest.raises(SystemExit):
                    __main__.parse_params(
                        ("--format", str(i), "--quality", str(j), "test.cbr")
                    )

            for j in range(101, 200):
                with pytest.raises(SystemExit):
                    __main__.parse_params(
                        ("--format", str(i), "--quality", str(j), "test.cbr")
                    )

    def test_invalid_quality(self):
        """Test if it exits because of an invalid PNG quality."""
        for i in chain(range(-10, 0), range(10, 20)):
            with pytest.raises(SystemExit):
                __main__.parse_params(
                    ("--format", "png", "--quality", str(i), "test.cbr")
                )


class TestEntryStorer:
    """Tests for EntryStorer methods."""

    ext_and_converters = tuple(product((*CONVERTERS, None), EXTENSIONS))

    @pytest.mark.slow
    @pytest.mark.parametrize("conv,ext", ext_and_converters)
    def test_entrystorer_init(self, tmp_path, conv, ext):
        out_path = tmp_path / f"test_{ext}.cbz"
        converter = None if conv is None else conv()

        with file_writer(
            str(out_path), "zip", options="compression=store"
        ) as output_arc:
            entry_storer = __main__.EntryStorer(output_arc, converter)
            assert entry_storer.archive == output_arc
            assert converter is None or isinstance(entry_storer.converter, conv)

    @pytest.mark.slow
    @pytest.mark.parametrize("conv,ext", ext_and_converters)
    def test_entrystorer_save_entry(self, shared_datadir, tmp_path, conv, ext):
        in_path = shared_datadir / f"xkcd.{ext}"
        out_path = tmp_path / f"test_{ext}.cbz"
        converter = None if conv is None else conv()
        files = set()

        with (
            file_reader(str(in_path)) as input_arc,
            file_writer(
                str(out_path), "zip", options="compression=store"
            ) as output_arc,
        ):
            entry_storer = __main__.EntryStorer(output_arc, converter)
            for entry in input_arc:
                print(entry)
                if entry.isreg:
                    new_name = __main__.create_new_name(entry.pathname, converter)
                    files.add(new_name.strip("/"))
                    entry_storer.save_entry(entry, new_name)

                elif entry.isdir:
                    output_arc.add_file_from_memory(
                        entry.pathname,
                        0,
                        b"",
                        entry.filetype,
                        entry.perm,
                        **__main__.get_entry_attrs(entry),
                    )
                    files.add(entry.pathname.strip("/"))

        found = set()
        with file_reader(str(out_path)) as created_arc:
            for entry in created_arc:
                found.add(entry.pathname.strip("/"))

        assert files == found, f"the difference between files an found {files ^ found}"


class TestMain:
    """Tests for main() function."""

    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_default(self, shared_datadir, tmp_path, ext):
        """Test conversion from comic book to .cbz."""
        in_path = shared_datadir / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main((str(in_path), out_path))
        assert in_path.exists()

    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_no_change(self, shared_datadir, tmp_path, ext):
        """Test conversion from comic book to .cbz using no-change."""
        in_path = shared_datadir / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main(("--format", "no-change", str(in_path), out_path))
        assert in_path.exists()

    @pytest.mark.slow
    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_jpegxl(self, shared_datadir, tmp_path, ext):
        """Test conversion from comic book to .cbz using jpegxl."""
        in_path = shared_datadir / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main(("--format", "jpegxl", str(in_path), out_path))
        assert in_path.exists()

    def test_duplicated_files(self, shared_datadir, tmp_path):
        """Test if main() gives error when there is duplicated files."""
        in_path = shared_datadir / "duplicated_files.cbz"
        out_path = tmp_path / "test_duplicated.cbz"
        with pytest.raises(SystemExit) as exc_info:
            __main__.main(("--format", "jpeg", str(in_path), str(out_path)))

        assert exc_info.value.code == 1

    def test_duplicated_dir(self, shared_datadir, tmp_path):
        """Test if main() gives error when there is duplicated folders."""
        in_path = shared_datadir / "duplicated_dir.cbz"
        out_path = tmp_path / "test_duplicated.cbz"
        with pytest.raises(SystemExit) as exc_info:
            __main__.main(("--format", "jpeg", str(in_path), str(out_path)))

        assert exc_info.value.code == 1
