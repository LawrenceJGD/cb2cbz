"""Tests for __main__ module."""

# ruff: noqa: S101

import sys
from contextlib import nullcontext
from itertools import chain, product
from pathlib import Path, PurePath
from subprocess import CalledProcessError
from types import NoneType

import pytest
from libarchive import file_reader, file_writer
from libarchive.entry import FileType

from cb2cbz import __main__, converters

EXTENSIONS = ("cbt", "cb7", "cbr", "cbz")
CONVERTERS = (
    converters.JpegConverter,
    converters.JpegliConverter,
    converters.JpegXLConverter,
    converters.PngConverter,
)


@pytest.mark.parametrize(
    "converter",
    [
        converters.JpegConverter,
        converters.JpegliConverter,
        converters.JpegXLConverter,
        converters.PngConverter,
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


class TestParseParams:
    """Test parse_params function."""

    format_converters = [
        (converters.ImageFormat.JPEG, converters.JpegConverter),
        (converters.ImageFormat.JPEGLI, converters.JpegliConverter),
        (converters.ImageFormat.JPEGXL, converters.JpegXLConverter),
        (converters.ImageFormat.PNG, converters.PngConverter),
        (converters.ImageFormat.NO_CHANGE, NoneType),
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

    @pytest.mark.parametrize("format_", ("jpeg", "jpegli", "jpegxl"))
    def test_default_quality(self, format_):
        """Test default quality for JPEG formats."""
        params = __main__.parse_params(("--format", format_, "test.cbr"))
        assert params.converter.quality == 90  # noqa: PLR2004

    def test_default_png_quality(self):
        """Test default quality for PNG."""
        params = __main__.parse_params(("--format", "png", "test.cbr"))
        assert params.converter.quality == 6  # noqa: PLR2004

    def test_default_no_change_quality(self):
        """Test default quality for no-change."""
        params = __main__.parse_params(("--format", "no-change", "test.cbr"))
        assert params.converter is None

    @pytest.mark.parametrize("format_", ("jpeg", "jpegli", "jpegxl"))
    def test_jpeg_quality(self, format_):
        """Test --quality for jpeg."""
        quality = 85
        params = __main__.parse_params(
            ("--format", format_, "--quality", str(quality), "test.cbr")
        )
        assert params.converter.quality == quality

    def test_png_quality(self):
        """Test --quality for png."""
        quality = 8
        params = __main__.parse_params(
            ("--format", "png", "--quality", str(quality), "test.cbr")
        )
        assert params.converter.quality == quality

    def test_invalid_format(self):
        """Test if it exits because of an invalid format."""
        with pytest.raises(SystemExit):
            __main__.parse_params(("--format", "failtest", "test.cbr"))

    def test_invalid_jpeg_quality(self):
        """Test if it exits because of an invalid quality for JPEG."""
        for format_, quality in product(
            ("jpeg", "jpegxl", "jpegli"), chain(range(-100, 0), range(101, 200))
        ):
            with pytest.raises(SystemExit):
                __main__.parse_params(
                    ("--format", format_, "--quality", str(quality), "test.cbr")
                )

    def test_invalid_quality(self):
        """Test if it exits because of an invalid PNG quality."""
        for i in chain(range(-10, 0), range(10, 20)):
            with pytest.raises(SystemExit):
                __main__.parse_params(
                    ("--format", "png", "--quality", str(i), "test.cbr")
                )


class MockArchiveWrite:
    """A mock of :cls:`libarchive.write.ArchiveWrite`."""
    def add_file_from_memory(*args, **kwargs):
        """Does nothing."""


class MockConverter(converters.BaseConverter):
    """A mock of a converter for doing a test."""

    format = ""
    pil_format = None
    extension = ""
    options = set()

    def __init__(self, quality):
        """Stores the quality."""
        self.quality = quality

    @classmethod
    def parse_options(cls, options):  # noqa: ARG003
        """It just returns an instance of the class."""
        return cls(-1)

    def convert(self, in_buffer):  # noqa: ARG002
        """Raises a CalledProcessError for testing."""
        msg = "Test"
        raise CalledProcessError(msg, "mytest", stderr=b"Test error")


class MockConverter2(MockConverter):
    """A mock of a converter that returns an empty bytes object."""
    def convert(self, in_buffer):  # noqa: ARG002
        """Returns an empty bytes object."""
        return converters.ImageData(nullcontext(), {}, new=False)


class MockEntry:
    """A mock of an entry for doing a test."""

    def __init__(self, pathname):
        """Initializes the class."""
        self.pathname = pathname
        self.filetype = FileType.REGULAR_FILE
        self.perm = self.uid = self.gid = self.size = self.atime = self.mtime = 0
        self.ctime = self.birthtime = self.rdev = self.rdevmajor = self.rdevminor = 0
        self.uname = self.gname = ""

    def get_blocks(self):
        """Returns an empty bytes object."""
        yield b""


def test_mock_converter_parse_options():
    """Test that :meth:`MockConverter.parse_options` returns an instance."""
    assert isinstance(MockConverter.parse_options(("1", "2", "3")), MockConverter)


class TestEntryStorer:
    """Tests for EntryStorer methods."""

    ext_and_converters = tuple(product((*CONVERTERS, None), EXTENSIONS))

    @pytest.mark.slow
    @pytest.mark.parametrize("conv,ext", ext_and_converters)
    def test_entrystorer_init(self, tmp_path, conv, ext):
        """Test EntryStorer.__init__ with multiple formats."""
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
    def test_entrystorer_save_entry(self, test_data, tmp_path, conv, ext):
        """Test EntryStorar.save_entry with multiple formats."""
        in_path = test_data / f"xkcd.{ext}"
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

    def test_called_process_error_message(self, capsys):
        """Test if an error message is printed when a subprocess fails."""
        converter = MockConverter(0)
        entry_storer = __main__.EntryStorer(MockArchiveWrite(), converter)
        with pytest.raises(SystemExit):
            entry_storer.save_entry(MockEntry("A test"), "test")

        captured = capsys.readouterr()
        print(captured)
        assert captured.err.strip() == (
            f"{PurePath(sys.argv[0]).name}: Error: An error happened while "
            'encoding "A test": Test error'
        )

    def test_error_when_pil_format_is_none(self):
        """Test if a ValueError exception is raised if pil_format is None."""
        converter = MockConverter2(0)
        entry_storer = __main__.EntryStorer(MockArchiveWrite(), converter)
        with pytest.raises(ValueError):
            entry_storer.save_entry(MockEntry("A test"), "test")


class TestMain:
    """Tests for main() function."""

    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_default(self, test_data, tmp_path, ext):
        """Test conversion from comic book to .cbz."""
        in_path = test_data / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main((str(in_path), out_path))
        assert in_path.exists()

    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_no_change(self, test_data, tmp_path, ext):
        """Test conversion from comic book to .cbz using no-change."""
        in_path = test_data / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main(("--format", "no-change", str(in_path), out_path))
        assert in_path.exists()

    @pytest.mark.slow
    @pytest.mark.parametrize("ext", EXTENSIONS)
    def test_cb_to_cbz_jpegxl(self, test_data, tmp_path, ext):
        """Test conversion from comic book to .cbz using jpegxl."""
        in_path = test_data / f"xkcd.{ext}"
        out_path = str(tmp_path / f"test_{ext}.cbz")
        __main__.main(("--format", "jpegxl", str(in_path), out_path))
        assert in_path.exists()

    def test_duplicated_files(self, test_data, tmp_path):
        """Test if main() gives error when there is duplicated files."""
        in_path = test_data / "duplicated_files.cbz"
        out_path = tmp_path / "test_duplicated.cbz"
        with pytest.raises(SystemExit) as exc_info:
            __main__.main(("--format", "jpeg", str(in_path), str(out_path)))

        assert exc_info.value.code == 1

    def test_duplicated_dir(self, test_data, tmp_path):
        """Test if main() gives error when there is duplicated folders."""
        in_path = test_data / "duplicated_dir.cbz"
        out_path = tmp_path / "test_duplicated.cbz"
        with pytest.raises(SystemExit) as exc_info:
            __main__.main(("--format", "jpeg", str(in_path), str(out_path)))

        assert exc_info.value.code == 1

    def test_duplicated_file_and_dir(self, test_data, tmp_path):
        """Test if main() gives error when there is duplicated folders."""
        in_path = test_data / "duplicated_file_dir.cbz"
        out_path = tmp_path / "test_duplicated.cbz"
        with pytest.raises(SystemExit) as exc_info:
            __main__.main(("--format", "jpeg", str(in_path), str(out_path)))

        assert exc_info.value.code == 1
