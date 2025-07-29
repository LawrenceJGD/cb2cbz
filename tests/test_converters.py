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

"""Tests for converters module."""

# ruff: noqa: S101

from io import BytesIO
from itertools import chain, product

import pytest
from PIL import Image

from cb2cbz import converters

BOOLS = (("true", True), ("1", True), ("false", False), ("0", False))


class TestJpegSubsamplingEnum:
    """Test that JpegSubsamplingEnum has the right values."""

    @pytest.mark.parametrize("value", ("keep", "4:4:4", "4:2:2", "4:2:0"))
    def test_jpegsubsamplingenum_valid_values(self, value):
        """Test valid values for JpegSubsamplingEnum."""
        subsampling = converters.JpegSubsamplingEnum(value)
        assert subsampling == value

    @pytest.mark.parametrize("value", ("test", "4:4:0"))
    def test_jpegsubsamplingenum_invalid_values(self, value):
        """Test invalid values for JpegSubsamplingEnum."""
        with pytest.raises(ValueError):
            converters.JpegSubsamplingEnum(value)


class TestJpegliProgressiveEnum:
    """Test that JpegliProgressiveEnum has the right values."""

    @pytest.mark.parametrize("value", (0, 1, 2))
    def test_jpegliprogressiveenum_valid_values(self, value):
        """Test valid values for JpegliProgressiveEnum."""
        progressive = converters.JpegliProgressiveEnum(value)
        assert progressive == value

    @pytest.mark.parametrize("value", (-1, 3))
    def test_jpegliprogressiveenum_invalid_values(self, value):
        """Test invalid values for JpegliProgressiveEnum."""
        with pytest.raises(ValueError):
            converters.JpegliProgressiveEnum(value)


class TestJpegliSubsamplingEnum:
    """Test that JpegliSubsamplingEnum has the right values."""

    @pytest.mark.parametrize("value", ("444", "440", "422", "420"))
    def test_jpeglisubsamplingenum_valid_values(self, value):
        """Test invalid values for JpegliSubsamplingEnum."""
        subsampling = converters.JpegliSubsamplingEnum(value)
        assert subsampling == value

    @pytest.mark.parametrize("value", ("test", "4:4:4", "4:4:2"))
    def test_jpeglisubsamplingenum_invalid_values(self, value):
        """Test invalid values for JpegliSubsamplingEnum."""
        with pytest.raises(ValueError):
            converters.JpegliSubsamplingEnum(value)


class TestJpegXLEffortEnum:
    """Test that JpegXLEffortEnum has the right values."""

    @pytest.mark.parametrize("value", tuple(range(1, 10)))
    def test_jpegxleffortenum_valid_values(self, value):
        """Test valid values for JpegXLEffortEnum."""
        effort = converters.JpegXLEffortEnum(value)
        assert effort == value

    @pytest.mark.parametrize("value", (0, 11))
    def test_jpegxleffortenum_invalid_values(self, value):
        """Test invalid values for JpegXLEffortEnum."""
        with pytest.raises(ValueError):
            converters.JpegXLEffortEnum(value)


class TestJpegXLDecodingSpeedEnum:
    """Test that JpegXLDecodingEnum has the right values."""

    @pytest.mark.parametrize("value", tuple(range(5)))
    def test_jpegxldecodingspeedenum_valid_values(self, value):
        """Test valid values for JpegXLDecodingSpeedEnum."""
        effort = converters.JpegXLDecodingSpeedEnum(value)
        assert effort == value

    @pytest.mark.parametrize("value", (-1, 5))
    def test_jpegxldecodingspeedenum_invalid_values(self, value):
        """Test invalid values for JpegXLDecodingSpeedEnum."""
        with pytest.raises(ValueError):
            converters.JpegXLDecodingSpeedEnum(value)


class TestJpegConverter:
    """Test JpegConverter methods."""

    def test_jpegconverter_init(self):
        """Test JpegConverter.__init__ with non-default values."""
        quality = 80
        subsampling = converters.JpegSubsamplingEnum.S422
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
        subsampling = (None, *converters.JpegSubsamplingEnum)
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

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img_path,mode,new",
        (
            ("2953_alien_theories.png", "L", False),
            ("2953_alien_theories_2.jpg", "L", False),
            ("2953_alien_theories_3.pfm", "RGB", True),
            ("2952_routine_maintenance_1bit.png", "L", True),
            ("2955_pole_vault_L_alpha.png", "L", True),
            ("2955_pole_vault_p.png", "RGB", True),
            ("2955_pole_vault_p_alpha.png", "RGB", True),
            ("2864_compact_graphs.png", "RGB", False),
            ("2864_compact_graphs_rgba.png", "RGB", True),
            ("2864_compact_graphs_cmyk.jpg", "CMYK", False),
            ("cursed_p_alpha.tif", "RGB", True),
        ),
    )
    def test_jpegconverter_convert(self, test_data, img_path, mode, new):
        """Test convert function using a JPEG from a BytesIO object."""
        converter = converters.JpegConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
            assert isinstance(result, converters.ImageData)
            assert result.img.mode == mode, f"{result.img.mode} != {mode}"
            assert result.new is new, f"expected {new}, got {result.new}"

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "subsampling,optimize,keep_rgb,progressive",
        list(
            product(
                (*converters.JpegSubsamplingEnum, None),
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
        for key in tuple(k for k, v in info.items() if v is None):
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
        for i in (0, 1, 2):
            converter = converters.JpegliConverter(progressive=i)
            assert converter.progressive == i

    @pytest.mark.parametrize("value", tuple(converters.JpegliSubsamplingEnum))
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

    def test_jpegliconverter_init_invalid_fixed_code_progressive(self):
        """Test JpegliConverter.__init__ with an invalid fixed_code."""
        with pytest.raises(
            ValueError, match="progressive must be 0 if fixed_code is True"
        ):
            converters.JpegliConverter(
                progressive=converters.JpegliProgressiveEnum.TWO, fixed_code=True
            )

    def test_jpegliconverter_parse_options_valid_progressive_numbers(self):
        """Test JpegliConverter.parse_options with numbers in progressive."""
        for i in (0, 1, 2):
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
        assert converter.progressive == converters.JpegliProgressiveEnum.ZERO
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

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img_path,mode",
        (
            ("2953_alien_theories.png", "L"),
            ("2953_alien_theories_2.jpg", "L"),
            ("2953_alien_theories_3.pfm", "RGB"),
            ("2952_routine_maintenance_1bit.png", "L"),
            ("2955_pole_vault_L_alpha.png", "L"),
            ("2955_pole_vault_rgba.png", "RGB"),
            ("2955_pole_vault_p.png", "RGB"),
            ("2955_pole_vault_p_alpha.png", "RGB"),
            ("2864_compact_graphs.png", "RGB"),
            ("2864_compact_graphs_rgba.png", "RGB"),
            ("2864_compact_graphs_cmyk.jpg", "RGB"),
            ("cursed_p_alpha.tif", "RGB"),
        ),
    )
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

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "progressive,subsampling,xyb,adaptive_quantization,std_quant,fixed_code",
        list(
            filter(
                lambda x: not (x[5] and x[0] != converters.JpegliProgressiveEnum.ZERO),
                product(
                    tuple(converters.JpegliProgressiveEnum),
                    (*converters.JpegliSubsamplingEnum, None),
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

    def test_jpegxlconverter_init_default(self):
        """Test __init__ method with default args."""
        quality = 90
        effort = converters.JpegXLEffortEnum.SQIRREL
        decoding_speed = converters.JpegXLDecodingSpeedEnum.ZERO

        converter = converters.JpegXLConverter()

        assert isinstance(converter, converters.JpegXLConverter)
        assert converter.quality == quality
        assert converter.effort == effort
        assert converter.decoding_speed == decoding_speed

    def test_jpegxlconverter_init_invalid_quality(self):
        """Test JpegXLConverter.__init__ using invalid quality values."""
        for i in (-1, 101):
            with pytest.raises(
                ValueError, match="quality must be an int between 0 and 100"
            ):
                converters.JpegXLConverter(quality=i)

    def test_jpegxlconverter_parse_options_effort(self):
        """Test valid values for effort option."""
        for num in converters.JpegXLEffortEnum:
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
        for num in converters.JpegXLDecodingSpeedEnum:
            converter = converters.JpegXLConverter.parse_options(
                f"decoding_speed={num}"
            )
            assert isinstance(converter, converters.JpegXLConverter)
            assert converter.decoding_speed == num

    @pytest.mark.parametrize("value,boolean", BOOLS)
    def test_jpegxlconverter_parse_options_jpegtran(self, value, boolean):
        """Test valid values for jpegtran option."""
        converter = converters.JpegXLConverter.parse_options(f"jpegtran={value}")
        assert converter.jpegtran is boolean

    def test_jpegxlconverter_parse_options_invalid_decoding_speed(self):
        """Test invalid values for decoding_speed option."""
        for num in (-1, 5):
            with pytest.raises(ValueError):
                converters.JpegXLConverter.parse_options(f"decoding_speed={num}")

    def test_jpegxlconverter_invalid_parse_options(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test option value is empty"):
            converters.JpegXLConverter.parse_options("test")

    def test_jpegxlconverter_parse_options_invalid_name(self):
        """Test parse_options methods using invalid options."""
        with pytest.raises(ValueError, match="test is not a valid option for jpegxl"):
            converters.JpegXLConverter.parse_options("test=abc")

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img_path,mode,new",
        (
            ("2953_alien_theories.png", "L", False),
            ("2953_alien_theories_3.pfm", "RGB", True),
            ("2952_routine_maintenance_1bit.png", "L", True),
            ("2955_pole_vault_L_alpha.png", "LA", False),
            ("2955_pole_vault_p.png", "RGB", True),
            ("2955_pole_vault_p_alpha.png", "RGBA", True),
            ("2864_compact_graphs.png", "RGB", False),
            ("2864_compact_graphs_rgba.png", "RGBA", False),
            ("2953_alien_theories_cmyk.jpg", "RGB", True),
            ("2864_compact_graphs_cmyk.jpg", "RGB", True),
            ("cursed_p_alpha.tif", "RGBA", True),
        ),
    )
    def test_jpegxlconverter_convert(self, test_data, img_path, mode, new):
        """Test convert function using images from BytesIO objects."""
        converter = converters.JpegXLConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        assert isinstance(result, converters.ImageData)
        assert result.img.mode == mode, f"{result.img.mode} != {mode}"
        assert result.new is new, f"expected {new}, got {result.new}"

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img_path,mode",
        (
            ("2953_alien_theories_2.jpg", "L"),
            ("2864_compact_graphs_rgb.jpg", "RGB"),
        ),
    )
    def test_jpegxlconverter_convert_jpeg(self, test_data, img_path, mode):
        """Test convert function using JPEG files."""
        converter = converters.JpegXLConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        assert isinstance(result, bytes)

        with BytesIO(result) as jpegxl, Image.open(jpegxl) as img:
            assert img.format == "JXL"
            assert img.mode == mode, f"{img.mode} != {mode}"

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img,effort,decoding_speed,jpegtran",
        list(
            product(
                (
                    ("2864_compact_graphs_rgb.jpg", "JPEG"),
                    ("2955_pole_vault_p.png", "PNG"),
                ),
                converters.JpegXLEffortEnum,
                converters.JpegXLDecodingSpeedEnum,
                (True, False),
            )
        ),
    )
    def test_jpegxlconverter_convert_options(
        self, test_data, img, effort, decoding_speed, jpegtran
    ):
        """Test JpegliConverter.convert with all possible arguments."""
        converter = converters.JpegXLConverter(
            effort=effort, decoding_speed=decoding_speed, jpegtran=jpegtran
        )

        with (test_data / img[0]).resolve().open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        if img[1] == "JPEG":
            assert isinstance(
                result, bytes
            ), f"result should be a bytes object, it is {type(result)}"
        else:
            assert isinstance(
                result, converters.ImageData
            ), f"result should be a ImageData object, it is {type(result)}"


class TestPngConverter:
    """Test PngConverter methods."""

    def test_pngconverter_init(self):
        """Test PngConverter.__init__ with default values."""
        quality = 6
        optimize = False
        converter = converters.PngConverter()
        assert converter.quality == quality
        assert converter.optimize is optimize

    @pytest.mark.parametrize("value", (True, False))
    def test_pngconverter_init_optimize(self, value):
        """Test valid values for optimize argument."""
        converter = converters.PngConverter(optimize=value)
        assert converter.optimize is value

    def test_pngconverter_init_quality(self):
        """Test valid values for quality argument."""
        for i in converters.PNG_RANGE:
            converter = converters.PngConverter(quality=i)
            assert converter.quality == i

    @pytest.mark.parametrize("value,bool_val", BOOLS)
    def test_pngconverter_parse_options_optimize(self, value, bool_val):
        """Test parse_options with optimize option."""
        converter = converters.PngConverter.parse_options(f"optimize={value}")
        assert converter.optimize is bool_val

    def test_pngconverter_parse_options_invalid_optimize(self):
        """Test parse_options with invalid values for optimize option."""
        with pytest.raises(
            ValueError, match='optimize value must be "1", "0", "true" or "false"'
        ):
            converters.PngConverter.parse_options("optimize=test")

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "img_path,mode,new",
        (
            ("2953_alien_theories.png", "L", False),
            ("2953_alien_theories_2.jpg", "L", False),
            ("2953_alien_theories_3.pfm", "P", True),
            ("2952_routine_maintenance_1bit.png", "1", False),
            ("2955_pole_vault_L_alpha.png", "LA", False),
            ("2955_pole_vault_p.png", "P", False),
            ("2955_pole_vault_p_alpha.png", "P", False),
            ("2864_compact_graphs.png", "RGB", False),
            ("2864_compact_graphs_rgba.png", "RGBA", False),
            ("2864_compact_graphs_cmyk.jpg", "RGB", True),
            ("cursed_p_alpha.tif", "RGBA", True),
        ),
    )
    def test_pngconverter_convert(self, test_data, img_path, mode, new):
        """Test convert function using image from BytesIO objects."""
        converter = converters.PngConverter()
        with (test_data / img_path).open(mode="rb") as img_file:
            data = BytesIO(img_file.read())

        with data:
            result = converter.convert(data)
        assert isinstance(result, converters.ImageData)
        assert result.img.mode == mode, f"{result.img.mode} != {mode}"
        assert result.new is new, f"expected {new}, got {result.new}"


class TestParseStrBool:
    """Test parse_str_bool function."""

    @pytest.mark.parametrize(
        "value", ("1", *map("".join, product(*zip("true", "TRUE", strict=True))))
    )
    def test_parse_str_true(self, value):
        """Test "true" with all combinations of upper and lower case."""
        assert converters.parse_str_bool(value, "test")

    @pytest.mark.parametrize(
        "value", ("0", *map("".join, product(*zip("false", "FALSE", strict=True))))
    )
    def test_parse_str_false(self, value):
        """Test "false" with all combinations of upper and lower case."""
        assert not converters.parse_str_bool(value, "test")

    def test_parse_str_invalid(self):
        """Test invalid values."""
        with pytest.raises(
            ValueError, match='test value must be "1", "0", "true" or "false"'
        ):
            converters.parse_str_bool("testing", "test")

    @pytest.mark.parametrize(
        "optimize,dpi,icc_profile,exif",
        list(
            product(
                (True, False),
                ((1000, 500), None),
                (b"hello", None),
                (b"world", None),
            )
        ),
    )
    def test_pngconverter_get_metadata(self, optimize, dpi, icc_profile, exif):
        """Test PngConverter.get_metadata with all possible args."""
        keys = {"dpi", "icc_profile", "exif", "optimize"}
        info = {
            "test": "testing",
            "dpi": dpi,
            "icc_profile": icc_profile,
            "exif": exif,
        }
        for key in tuple(k for k, v in info.items() if v is None):
            del info[key]

        converter = converters.PngConverter(optimize=optimize)
        meta = converter.get_metadata(info)

        assert keys >= meta.keys(), f"unexpected keys: {meta.keys() - keys}"
        if dpi:
            assert meta["dpi"] == dpi
        if icc_profile:
            assert meta["icc_profile"] == icc_profile
        if exif:
            assert meta["exif"] == exif
        if optimize is not None:
            assert meta["optimize"] == optimize
