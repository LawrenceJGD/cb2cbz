"""Tests for __main__ module."""

# ruff: noqa: S101

from pathlib import Path

import pytest
from cb2cbz import __main__


class TestJpegXLOptions:
    """Test JpegXLOptions methods."""

    @pytest.mark.parametrize("args", [{}, {"lossless": True}, {"lossless": False}])
    def test_init(self, args):
        """Test __init__ method."""
        options = __main__.JpegXLOptions(**args)
        for key, value in args.items():
            assert getattr(options, key) == value

    @pytest.mark.parametrize("value", ("=true", "=TRUE", "=1"))
    def test_parse_options_lossless_true(self, value):
        """Test parse_options with lossless."""
        for name in ("lossless", "LOSSLESS", "lOsSlEsS"):
            options = __main__.JpegXLOptions.parse_options(f"{name}{value}")
            assert isinstance(options, __main__.JpegXLOptions)
            assert options.lossless is True

    @pytest.mark.parametrize("value", ("=false", "=FALSE", "=0"))
    def test_parse_options_lossless_false(self, value):
        """Test parse_options with lossless with false value."""
        for name in ("lossless", "LOSSLESS", "lOsSlEsS"):
            options = __main__.JpegXLOptions.parse_options(f"{name}{value}")
            assert isinstance(options, __main__.JpegXLOptions)
            assert options.lossless is False

    def test_parse_options_invalid_lossless(self):
        """Test invalid value for lossless option."""
        with pytest.raises(ValueError):
            __main__.JpegXLOptions.parse_options("lossless=abc")

    @pytest.mark.parametrize("name", ("a", "de", "fg"))
    def test_invalid_parse_options(self, name):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match=f"{name} option value is empty"):
            __main__.JpegXLOptions.parse_options(name)


def test_parameter_init():
    """Test Parameter.__init__ method."""
    params1 = __main__.Parameters(
        format=__main__.ImageFormat.JPEG,
        quality=15,
        options=__main__.JpegXLOptions(lossless=True),
        input=Path("test.cbr"),
        output=Path("test.cbz"),
    )
    params2 = __main__.Parameters(
        format=__main__.ImageFormat.JPEG,
        quality=None,
        options=None,
        input=Path("test.cbr"),
        output=Path("test.cbz"),
    )

    assert params1.format == __main__.ImageFormat.JPEG
    assert params1.quality == 15  # noqa: PLR2004
    assert params1.options == __main__.JpegXLOptions(lossless=True)
    assert params1.input == Path("test.cbr")
    assert params1.output == Path("test.cbz")

    assert params2.format == __main__.ImageFormat.JPEG
    assert params2.quality is None
    assert params2.options is None
    assert params2.input == Path("test.cbr")
    assert params2.output == Path("test.cbz")


class TestParseStrBool:
    """Test parse_str_bool function."""

    @pytest.mark.parametrize("value", ("1", "true", "TRUE", "tRuE"))
    def test_true(self, value):
        """Test true values."""
        assert __main__.parse_str_bool(value, "test")

    @pytest.mark.parametrize("value", ("0", "false", "FALSE", "fAlSe"))
    def test_false(self, value):
        """Test false values."""
        assert not __main__.parse_str_bool(value, "test")

    def test_invalid(self):
        """Test invalid values."""
        with pytest.raises(
            ValueError, match='test value must be "1", "0", "true" or "false"'
        ):
            __main__.parse_str_bool("testing", "test")


class TestParseParams:
    """Test parse_params function."""

    def test_input_only(self):
        """Test only with input argument."""
        params = __main__.parse_params(("test.cbr",))
        assert isinstance(params, __main__.Parameters)
        assert isinstance(params.input, Path)
        assert isinstance(params.output, Path)
        assert params.input == Path("test.cbr")
        assert params.output == Path("test.cbz")
        assert params.format == __main__.ImageFormat.NO_CHANGE
        assert params.quality is None
        assert params.options is None

    def test_output(self):
        """Test output argument."""
        params = __main__.parse_params(("test.cbr", "tested.cbz"))
        assert isinstance(params, __main__.Parameters)
        assert isinstance(params.input, Path)
        assert isinstance(params.output, Path)
        assert params.input == Path("test.cbr")
        assert params.output == Path("tested.cbz")

    @pytest.mark.parametrize("format_", tuple(__main__.ImageFormat))
    def test_short_format(self, format_):
        """Test -f argument."""
        params = __main__.parse_params(("-f", str(format_), "test.cbr"))
        assert isinstance(params, __main__.Parameters)
        assert params.format == format_

    @pytest.mark.parametrize("format_", tuple(__main__.ImageFormat))
    def test_long_format(self, format_):
        """Test --format argument."""
        params1 = __main__.parse_params(("--format", str(format_), "test.cbr"))
        params2 = __main__.parse_params((f"--format={format_}", "test.cbr"))
        assert isinstance(params1, __main__.Parameters)
        assert isinstance(params2, __main__.Parameters)

    @pytest.mark.parametrize("format_", tuple(__main__.ImageFormat))
    def test_same_format(self, format_):
        """Test that -f, --format and --format= give the same object."""
        params1 = __main__.parse_params(("-f", str(format_), "test.cbr"))
        params2 = __main__.parse_params(("--format", str(format_), "test.cbr"))
        params3 = __main__.parse_params((f"--format={format_}", "test.cbr"))
        assert params1 == params2 and params1 == params3

    @pytest.mark.parametrize("format_", ("jpeg", "jpegxl", "jpegli"))
    def test_default_quality(self, format_):
        """Test default quality for JPEG formats."""
        params = __main__.parse_params(("--format", format_, "test.cbr"))
        assert params.quality == 90  # noqa: PLR2004

    def test_default_png_quality(self):
        """Test default quality for PNG."""
        params = __main__.parse_params(("--format", "png", "test.cbr"))
        assert params.quality == 6  # noqa: PLR2004

    def test_default_no_change_quality(self):
        """Test default quality for no-change."""
        params = __main__.parse_params(("--format", "no-change", "test.cbr"))
        assert params.quality is None

    def test_jpegxl_true_lossless_option(self):
        """Test JPEG XL lossless option when the value is true."""
        for i in ("true", "1"):
            params = __main__.parse_params(
                ("--format", "jpegxl", "--options", f"lossless={i}", "test.cbr")
            )
            assert isinstance(params.options, __main__.JpegXLOptions)
            assert params.options.lossless

    def test_jpegxl_false_lossless_option(self):
        """Test JPEG XL lossless option when the value is false."""
        for i in ("false", "0"):
            params = __main__.parse_params(
                ("--format", "jpegxl", "--options", f"lossless={i}", "test.cbr")
            )
            assert isinstance(params.options, __main__.JpegXLOptions)
            assert not params.options.lossless

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
        for i in range(-10, 0):
            with pytest.raises(SystemExit):
                __main__.parse_params(
                    ("--format", "png", "--quality", str(i), "test.cbr")
                )

        for i in range(10, 20):
            with pytest.raises(SystemExit):
                __main__.parse_params(
                    ("--format", "png", "--quality", str(i), "test.cbr")
                )
