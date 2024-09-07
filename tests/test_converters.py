"""Tests for converters module."""

# ruff: noqa: S101

from io import BytesIO
from itertools import chain, product

import pytest
from cb2cbz import converters
from PIL import Image

BOOLS = (("true", True), ("1", True), ("false", False), ("0", False))


class TestJpegConverter:
    """Test JpegConverter methods."""

    img_modes = (
        ("2953_alien_theories.png", "L"),
        ("2953_alien_theories_2.jpg", "L"),
        ("2953_alien_theories_3.pfm", "RGB"),
        ("2952_routine_maintenance_1bit.png", "L"),
        ("2955_pole_vault_L_alpha.png", "L"),
        ("2955_pole_vault_rgba.png", "RGB"),
        ("2955_pole_vault_p.png", "RGB"),
        ("2955_pole_vault_p_alpha.png", "RGB"),
        ("2953_alien_theories_cmyk.jpg", "CMYK"),
    )

    def test_jpegconverter_init(self):
        """Test JpegConverter.__init__ with non-default values."""
        quality = 80
        subsampling = "4:2:2"
        optimize = True
        keep_rgb = True
        progressive = False

        converter = converters.JpegConverter(
            quality=quality,
            progressive=progressive,
            subsampling=subsampling,
            optimize=optimize,
            keep_rgb=keep_rgb,
        )

        assert isinstance(converter, converters.JpegConverter)
        assert converter.quality == quality
        assert converter.subsampling == subsampling
        assert converter.optimize == optimize
        assert keep_rgb == converter.keep_rgb
        assert progressive == converter.progressive

    def test_jpegconverter_init_invalid_quality(self):
        """Test JpegConverter.__init__ using invalid quality values."""
        for i in (-1, 101):
            with pytest.raises(
                ValueError, match="quality must be an int between 0 and 100"
            ):
                converters.JpegConverter(quality=i)

    def test_jpegconverter_init_invalid_subsampling(self):
        """Test JpegConverter.__init__ using a invalid subsampling value."""
        with pytest.raises(
            ValueError,
            match='subsampling must be "keep", "4:4:4", "4:2:2", "4:2:0" or None',
        ):
            converters.JpegConverter(subsampling="test")

    @pytest.mark.parametrize("value,bool_val", BOOLS)
    def test_jpegconverter_parse_options_optimize(self, value, bool_val):
        """Test JpegConverter.parse_options using optimize option."""
        converter = converters.JpegConverter.parse_options(f"optimize={value}")
        assert converter.optimize is bool_val

    @pytest.mark.parametrize("value,bool_val", BOOLS)
    def test_jpegconverter_parse_options_progressive(self, value, bool_val):
        """Test JpegConverter.parse_options using progressive option."""
        converter = converters.JpegConverter.parse_options(f"progressive={value}")
        assert converter.progressive == bool_val

    @pytest.mark.parametrize("value,bool_val", BOOLS)
    def test_jpegconverter_parse_options_keep_rgb(self, value, bool_val):
        """Test JpegConverter.parse_options using keep_rgb option."""
        converter = converters.JpegConverter.parse_options(f"keep_rgb={value}")
        assert converter.keep_rgb == bool_val

    @pytest.mark.parametrize("value", ("keep", "4:4:4", "4:2:2", "4:2:0"))
    def test_jpegconverter_parse_options_subsamping(self, value):
        """Test JpegConverter.parse_options using subsampling option."""
        converter = converters.JpegConverter.parse_options(f"subsampling={value}")
        assert converter.subsampling == value

    def test_jpegconverter_parse_options_subsamping_invalid(self):
        """Test JpegConverter.parse_options using an invalid subsampling."""
        with pytest.raises(ValueError, match='"test" is not a valid subsampling'):
            converters.JpegConverter.parse_options("subsampling=test")

    def test_jpegconverter_parse_options_all(self):
        """Test JpegConverter.parse_options using all possible options."""
        none_bools = (None, *BOOLS)
        subsampling = (None, "keep", "4:4:4", "4:2:2", "4:2:0")
        names = ("optimize", "progressive", "keep_rgb", "subsampling")
        combinations = product(none_bools, none_bools, none_bools, subsampling)

        for comb in combinations:
            converter = converters.JpegConverter.parse_options(
                ",".join(
                    f"{names[i]}={j if i == 3 else j[0]}"  # noqa: PLR2004
                    for i, j in enumerate(comb)
                    if j is not None
                )
            )
            if comb[0]:
                assert converter.optimize == comb[0][1]
            if comb[1]:
                assert converter.progressive == comb[1][1]
            if comb[2]:
                assert converter.keep_rgb == comb[2][1]
            if comb[3]:
                assert converter.subsampling == comb[3]

    @pytest.mark.parametrize("img_path,mode", img_modes)
    def test_jpegconverter_convert(self, test_data, img_path, mode):
        """Test convert function using a JPEG from a BytesIO object."""
        converter = converters.JpegConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
            assert isinstance(result, converters.ImageData)
            assert result.img.mode == mode, f"{result.img.mode} != {mode}"

    @pytest.mark.parametrize(
        "subsampling,optimize,keep_rgb,progressive",
        list(
            product(
                ("keep", "4:4:4", "4:2:2", "4:2:0", None),
                (True, False),
                (True, False),
                (True, False),
            )
        ),
    )
    def test_jpegconverter_convert_options(
        self,
        test_data,
        subsampling,
        optimize,
        keep_rgb,
        progressive,
    ):
        """Test JpegConverter.convert with all possible arguments."""
        converter = converters.JpegConverter(
            subsampling=subsampling,
            optimize=optimize,
            keep_rgb=keep_rgb,
            progressive=progressive,
        )

        with (
            (test_data / "2955_pole_vault_p.png").resolve().open(mode="rb") as img_file
        ):
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
            assert isinstance(result, converters.ImageData)

    @pytest.mark.parametrize(
        "progressive,dpi,icc_profile,exif,comment",
        list(
            product(
                (0, 1, 2),
                ((1000, 500), None),
                (b"hello", None),
                (b"world", None),
                ("how are you?", None),
            )
        ),
    )
    def test_jpegconverter_get_metadata(
        self, progressive, dpi, icc_profile, exif, comment
    ):
        """Test JpegConverter.get_metadata with all possible args."""
        keys = {"dpi", "icc_profile", "exif", "comment", "progressive"}
        info = {
            "test": "testing",
            "dpi": dpi,
            "icc_profile": icc_profile,
            "exif": exif,
            "comment": comment,
        }
        delete = {k for k, v in info.items() if v is None}
        for key in delete:
            del info[key]

        converter = converters.JpegConverter(progressive=progressive)
        meta = converter.get_metadata(info)

        assert keys >= meta.keys(), f"unexpected keys: {meta.keys() - keys}"
        if dpi:
            assert meta["dpi"] == dpi
        if icc_profile:
            assert meta["icc_profile"] == icc_profile
        if exif:
            assert meta["exif"] == exif
        if comment:
            assert meta["comment"] == comment


class TestJpegliConverter:
    """Test JpegliConverter methods."""

    img_modes = (
        ("2953_alien_theories.png", "L"),
        ("2953_alien_theories_2.jpg", "L"),
        ("2953_alien_theories_3.pfm", "RGB"),
        ("2952_routine_maintenance_1bit.png", "L"),
        ("2955_pole_vault_L_alpha.png", "L"),
        ("2955_pole_vault_rgba.png", "RGB"),
        ("2955_pole_vault_p.png", "RGB"),
        ("2955_pole_vault_p_alpha.png", "RGB"),
        ("2953_alien_theories_cmyk.jpg", "RGB"),
    )

    def test_jpegliconverter_init(self):
        """Test JpegliConverter.__init__ with valid values."""
        quality = 87
        progressive = 0
        subsampling = "440"
        xyb = True
        adaptive_quantization = True
        std_quant = True
        fixed_code = True

        converter = converters.JpegliConverter(
            quality=quality,
            progressive=progressive,
            subsampling=subsampling,
            xyb=xyb,
            adaptive_quantization=adaptive_quantization,
            std_quant=std_quant,
            fixed_code=fixed_code,
        )

        assert converter.quality == quality
        assert converter.progressive == progressive
        assert converter.subsampling == subsampling
        assert converter.xyb == xyb
        assert converter.adaptive_quantization == adaptive_quantization
        assert converter.std_quant == std_quant
        assert converter.fixed_code == fixed_code

    def test_jpegliconverter_init_valid_quality(self):
        """Test JpegliConverter.__init__ with quality arg."""
        for i in converters.JPEG_RANGE:
            converter = converters.JpegliConverter(quality=i)
            assert converter.quality == i

    def test_jpegliconverter_init_valid_progressive(self):
        """Test JpegliConverter.__init__ with progressive arg."""
        for i in converters.JPEGLI_PROGRESSIVE_RANGE:
            converter = converters.JpegliConverter(progressive=i)
            assert converter.progressive == i

    @pytest.mark.parametrize("value", ("444", "440", "422", "420"))
    def test_jpegliconverter_init_valid_subsampling(self, value):
        """Test JpegliConverter.__init__ with subsampling arg."""
        converter = converters.JpegliConverter(subsampling=value)
        assert converter.subsampling == value

    @pytest.mark.parametrize("value", (True, False))
    def test_jpegliconverter_init_valid_xyb(self, value):
        """Test JpegliConverter.__init__ with xyb arg."""
        converter = converters.JpegliConverter(xyb=value)
        assert converter.xyb == value

    @pytest.mark.parametrize("value", (True, False))
    def test_jpegliconverter_init_valid_adaptive_quantization(self, value):
        """Test JpegliConverter.__init__ with adaptive_quantization arg."""
        converter = converters.JpegliConverter(adaptive_quantization=value)
        assert converter.adaptive_quantization is value

    def test_jpegliconverter_init_valid_true_fixed_code_progressive(self):
        """Test JpegliConverter.__init__ with fixed_code as True."""
        converter = converters.JpegliConverter(progressive=0, fixed_code=True)
        assert converter.progressive == 0
        assert converter.fixed_code is True

    def test_jpegliconverter_init_valid_false_std_quant(self):
        """Test JpegliConverter.__init__ with fixed_code as False."""
        converter = converters.JpegliConverter(std_quant=False)
        assert converter.std_quant is False

    @pytest.mark.parametrize("value", (True, False))
    def test_jpegliconverter_init_valid_std_quant(self, value):
        """Test JpegliConverter.__init__ with std_quant."""
        converter = converters.JpegliConverter(std_quant=value)
        assert converter.std_quant is value

    @pytest.mark.parametrize("value", (-1, 101))
    def test_jpegliconverter_init_invalid_quality(self, value):
        """Test JpegliConverter.__init__ using invalid quality values."""
        with pytest.raises(
            ValueError, match="quality must be an int between 0 and 100"
        ):
            converters.JpegliConverter(quality=value)

    @pytest.mark.parametrize("value", (-1, 3))
    def test_jpegliconverter_init_invalid_progressive(self, value):
        """Test JpegliConverter.__init__ with invalid progressive values."""
        with pytest.raises(
            ValueError,
            match=(
                "progressive must be an int between "
                f"{converters.JPEGLI_PROGRESSIVE_RANGE.start} and "
                f"{converters.JPEGLI_PROGRESSIVE_RANGE.stop - 1}"
            ),
        ):
            converters.JpegliConverter(progressive=value)

    def test_jpegliconverter_init_invalid_subsampling(self):
        """Test JpegliConverter.__init__ with invalid an submsampling."""
        with pytest.raises(
            ValueError, match='subsampling must be "444", "440", "422" or "420"'
        ):
            converters.JpegliConverter(subsampling="test")

    def test_jpegliconverter_init_invalid_fixed_code_progressive(self):
        """Test JpegliConverter.__init__ with an invalid fixed_code."""
        with pytest.raises(
            ValueError, match="progressive must be 0 if fixed_code is True"
        ):
            converters.JpegliConverter(progressive=1, fixed_code=True)

    def test_jpegliconverter_parse_options_valid_progressive_numbers(self):
        """Test JpegliConverter.parse_options with numbers in progressive."""
        for i in converters.JPEGLI_PROGRESSIVE_RANGE:
            converter = converters.JpegliConverter.parse_options(f"progressive={i}")
            assert converter.progressive == i

    @pytest.mark.parametrize("value,num", (("true", 2), ("false", 0)))
    def test_jpegliconverter_parse_options_valid_progressive_bools(self, value, num):
        """Test JpegliConverter.parse_options with booleans in progressive."""
        converter = converters.JpegliConverter.parse_options(f"progressive={value}")
        assert converter.progressive == num

    @pytest.mark.parametrize("value", ("4:4:4", "4:4:0", "4:2:2", "4:2:0"))
    def test_jpegliconverter_parse_options_valid_subsampling(self, value):
        """Test JpegliConverter.parse_options with subsampling."""
        converter = converters.JpegliConverter.parse_options(f"subsampling={value}")
        assert converter.subsampling == value.replace(":", "")

    @pytest.mark.parametrize("value,boolean", BOOLS)
    def test_jpegliconverter_parse_options_valid_xyb(self, value, boolean):
        """Test JpegliConverter.parse_options with xyb."""
        converter = converters.JpegliConverter.parse_options(f"xyb={value}")
        assert converter.xyb is boolean

    @pytest.mark.parametrize("value,boolean", BOOLS)
    def test_jpegliconverter_parse_options_valid_adaptive_quantization(
        self, value, boolean
    ):
        """Test JpegliConverter.parse_options with adaptive_quantization."""
        converter = converters.JpegliConverter.parse_options(
            f"adaptive_quantization={value}"
        )
        assert converter.adaptive_quantization is boolean

    def test_jpegliconverter_parse_options_valid_true_fixed_code_progressive(self):
        """Test JpegliConverter.parse_options with fixed_code as true."""
        converter = converters.JpegliConverter.parse_options(
            "progressive=0,fixed_code=true"
        )
        assert converter.progressive == 0
        assert converter.fixed_code is True

    def test_jpegliconverter_parse_options_valid_false_fixed_code(self):
        """Test JpegliConverter.parse_options with fixed_code as false."""
        converter = converters.JpegliConverter.parse_options("std_quant=false")
        assert converter.std_quant is False

    @pytest.mark.parametrize("value,boolean", BOOLS)
    def test_jpegliconverter_parse_options_valid_std_quant(self, value, boolean):
        """Test JpegliConverter.parse_options with std_quant."""
        converter = converters.JpegliConverter.parse_options(f"std_quant={value}")
        assert converter.std_quant is boolean

    @pytest.mark.parametrize("value", (-1, 3))
    def test_jpegliconverter_parse_options_invalid_progressive_number(self, value):
        """Test parse_options with invalid numbers in progressive."""
        with pytest.raises(
            ValueError,
            match='progressive value must be "true", "false", "0", "1" or "2"',
        ):
            converters.JpegliConverter.parse_options(f"progressive={value}")

    def test_jpegliconverter_parse_options_invalid_subsampling(self):
        """Test JpegliConverter.parse_options with a invalid subsampling."""
        with pytest.raises(
            ValueError,
            match='subsampling value must be "4:4:4", "4:4:0", "4:2:2" or "4:2:0"',
        ):
            converters.JpegliConverter.parse_options("subsampling=test")

    def test_jpegliconverter_parse_options_invalid_fixed_code_progressive(self):
        """Test JpegliConverter.parse_options with an invalid fixed_code."""
        with pytest.raises(
            ValueError, match="progressive must be 0 if fixed_code is true"
        ):
            converters.JpegliConverter.parse_options("progressive=1,fixed_code=true")

    @pytest.mark.parametrize("img_path,mode", img_modes)
    def test_jpegliconverter_convert(self, test_data, img_path, mode):
        """Test convert function using a JPEG from a BytesIO object."""
        converter = converters.JpegliConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        assert isinstance(result, bytes)

        with BytesIO(result) as jpeg, Image.open(jpeg) as img:
            assert img.format == "JPEG"
            assert img.mode == mode, f"{img.mode} != {mode}"

    @pytest.mark.parametrize(
        "progressive,subsampling,xyb,adaptive_quantization,std_quant,fixed_code",
        list(
            filter(
                lambda x: not (x[5] and x[0] != 0),
                product(
                    (0, 1, 2),
                    ("444", "440", "422", "420", None),
                    (True, False),
                    (True, False),
                    (True, False),
                    (True, False),
                ),
            )
        ),
    )
    def test_jpegliconverter_convert_options(  # noqa: PLR0913
        self,
        test_data,
        progressive,
        subsampling,
        xyb,
        adaptive_quantization,
        std_quant,
        fixed_code,
    ):
        """Test JpegliConverter.convert with all possible arguments."""
        converter = converters.JpegliConverter(
            progressive=progressive,
            subsampling=subsampling,
            xyb=xyb,
            adaptive_quantization=adaptive_quantization,
            std_quant=std_quant,
            fixed_code=fixed_code,
        )

        with (
            (test_data / "2955_pole_vault_p.png").resolve().open(mode="rb") as img_file
        ):
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        assert isinstance(result, bytes)


class TestJpegXLConverter:
    """Test JpegXLConverter methods."""

    def test_jpegxlconverter_init(self):
        """Test __init__ method."""
        test_quality = 12
        test_effort = 3
        test_decoding_speed = 4

        converter = converters.JpegXLConverter(
            quality=test_quality, effort=test_effort, decoding_speed=test_decoding_speed
        )

        assert isinstance(converter, converters.JpegXLConverter)
        assert converter.quality == test_quality
        assert converter.effort == test_effort
        assert converter.decoding_speed == test_decoding_speed

    def test_jpegxlconverter_init_invalid_quality(self):
        """Test JpegXLConverter.__init__ using invalid quality values."""
        for i in (-1, 101):
            with pytest.raises(
                ValueError, match="quality must be an int between 0 and 100"
            ):
                converters.JpegXLConverter(quality=i)

    def test_jpegxlconverter_init_invalid_effort(self):
        """Test JpegXLConverter.__init__ using invalid effort values."""
        for i in (0, 11):
            with pytest.raises(
                ValueError, match="effort must be an int between 1 and 10"
            ):
                converters.JpegXLConverter(effort=i)

    def test_jpegxlconverter_init_invalid_decoding_speed(self):
        """Test JpegXLConverter.__init__ using an invalid decoding_speed."""
        for i in (-1, 5):
            with pytest.raises(
                ValueError, match="decoding_speed must be an int between 0 and 4"
            ):
                converters.JpegXLConverter(decoding_speed=i)

    def test_jpegxlconverter_parse_options_effort(self):
        """Test valid values for effort option."""
        for num in converters.EFFORT_RANGE:
            converter = converters.JpegXLConverter.parse_options(f"effort={num}")
            assert isinstance(converter, converters.JpegXLConverter)
            assert converter.effort == num

    def test_jpegxlconverter_parse_options_invalid_effort(self):
        """Test invalid values for effort option."""
        for num in chain(range(-10, 1), range(11, 21)):
            with pytest.raises(ValueError):
                converters.JpegXLConverter.parse_options(f"effort={num}")

    def test_jpegxlconverter_parse_options_decoding_speed(self):
        """Test valid values for decoding_speed option."""
        for num in converters.DECODING_SPEED_RANGE:
            converter = converters.JpegXLConverter.parse_options(
                f"decoding-speed={num}"
            )
            assert isinstance(converter, converters.JpegXLConverter)
            assert converter.decoding_speed == num

    def test_jpegxlconverter_parse_options_invalid_decoding_speed(self):
        """Test invalid values for decoding_speed option."""
        for num in chain(range(-10, 0), range(10, 20)):
            with pytest.raises(ValueError):
                converters.JpegXLConverter.parse_options(f"decoding-speed={num}")

    def test_jpegxlconverter_invalid_parse_options(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test option value is empty"):
            converters.JpegXLConverter.parse_options("test")

    def test_jpegxlconverter_parse_options_invalid_name(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test is not a valid option for jpegxl"):
            converters.JpegXLConverter.parse_options("test=abc")

    def test_jpegxlconverter_convert_png_l(self, test_data):
        """Test convert function using a PNG image in mode L."""
        converter = converters.JpegXLConverter()
        with (test_data / "2953_alien_theories.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "L"
            assert not result.new

    def test_jpegxlconverter_convert_png_1bit(self, test_data):
        """Test convert function using a PNG image in mode 1."""
        converter = converters.JpegXLConverter()
        with (test_data / "2952_routine_maintenance_1bit.png").open(
            mode="rb"
        ) as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "L"
            assert result.new

    def test_jpegxlconverter_convert_png_l_alpha(self, test_data):
        """Test convert function using a PNG image in mode LA."""
        converter = converters.JpegXLConverter()
        with (test_data / "2955_pole_vault_L_alpha.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            print(result.img.mode)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "LA"
            assert not result.new

    def test_jpegxlconverter_convert_png_rgba(self, test_data):
        """Test convert function using a PNG image in mode RGBA."""
        converter = converters.JpegXLConverter()
        with (test_data / "2955_pole_vault_rgba.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            print(result.img.mode)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGBA"
            assert not result.new

    def test_jpegxlconverter_convert_png_p(self, test_data):
        """Test convert function using a PNG image in mode P."""
        converter = converters.JpegXLConverter()
        with (test_data / "2955_pole_vault_p.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGB"
            assert result.new

    def test_jpegxlconverter_convert_png_p_alpha(self, test_data):
        """Test convert function using a PNG image in mode P with alpha."""
        converter = converters.JpegXLConverter()
        with (test_data / "2955_pole_vault_p_alpha.png").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, converters.ImageData)
            assert isinstance(result.img, Image.Image)
            assert result.img.mode == "RGBA"
            assert result.new

    def test_jpegxlconverter_convert_jpeg_file(self, test_data):
        """Test convert function using a JPEG."""
        converter = converters.JpegXLConverter()
        with (test_data / "2953_alien_theories_2.jpg").open(mode="rb") as img_file:
            result = converter.convert(img_file)
            assert isinstance(result, bytes)

    def test_jpegxlconverter_convert_jpeg_bytesio(self, test_data):
        """Test convert function using a JPEG from a BytesIO object."""
        converter = converters.JpegXLConverter()
        with (test_data / "2953_alien_theories_2.jpg").open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
            assert isinstance(result, bytes)


class TestParseStrBool:
    """Test parse_str_bool function."""

    @pytest.mark.parametrize("value", ("1", "true", "TRUE", "tRuE"))
    def test_parse_str_true(self, value):
        """Test true values."""
        assert converters.parse_str_bool(value, "test")

    @pytest.mark.parametrize("value", ("0", "false", "FALSE", "fAlSe"))
    def test_parse_str_false(self, value):
        """Test false values."""
        assert not converters.parse_str_bool(value, "test")

    def test_parse_str_invalid(self):
        """Test invalid values."""
        with pytest.raises(
            ValueError, match='test value must be "1", "0", "true" or "false"'
        ):
            converters.parse_str_bool("testing", "test")


class TestParseStrInt:
    """Tests for parse_str_int."""

    def test_valid_parse_str_int(self):
        """Test valid values for parse_str_int."""
        test_range = range(-5, 6)
        for i in test_range:
            assert converters.parse_str_int(str(i), test_range, "test") == i

    def test_invalid_parse_str_int(self):
        """Test invalid values for parse_str_int."""
        test_range = range(30)
        for i in ("a", "bC", "0x15", "0o15"):
            with pytest.raises(ValueError):
                converters.parse_str_int(i, test_range, "test")

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
                converters.parse_str_int(i, test_range, "test")
