# Comic Book to CBZ Converter (cb2cbz)

This is a script that can convert comic book files like ".cbr" (RAR), ".cb7" (7z), ".cbt" (Tar), or any compressed file to ".cbz" (Zip) and convert the image formats to PNG, JPEG, and JPEG-XL.

## Why Would I Use It?

One reason to use it is that CBR and CB7 don't provide better compression because comic book files contain images in PNG or JPEG formats, which means that they are currently compressed using algorithms that are better for compressing pictures. If you try to compress them again with RAR or 7z, you get very little or no compression, but at the expense of a slower decoding process when you open them in a comic book viewer, which uses more CPU and battery than if you just used a Zip file without compression.

Another reason is the compatibility: CBZ has a better support from comic viewers than CBR, CB7 and CBT because it just uses Zip, a format that is open and that has been used since a lot of time, while RAR is a propietary format, making it harder to use for some apps, while CB7 is rarer to find and CBT even more.

However, there is something that will make your comic book files take up less space, and that is converting the format of the images that they contain. I've achieved size reductions of about one-third when converting from JPEG to JPEG-XL.

That's a lot more than what you'll get using only CBR or CB7.

## How to use it?

(WIP)...

## License

This program is under the [GNU General Public License, version 3.0](LICENSE.txt).

# Credits

* [Pillow](https://python-pillow.github.io/): used for converting between different image formats, made by Jeffrey A. Clark and contributors and is under the [MIT-CDU license](https://github.com/python-pillow/Pillow/blob/main/LICENSE).

* [libarchive-c](https://github.com/Changaco/python-libarchive-c): used for doing the conversion from CBR, CB7 and CBT to CBZ, made by Charly Coste and under the [Creative Commons Zero License](https://github.com/Changaco/python-libarchive-c/blob/master/LICENSE.md).

* [pillow-jpegxl-plugin](https://github.com/Isotr0py/pillow-jpegxl-plugin): used for converting images to JPEG-XL, made by Isotr0py and under the [GNU General Public License, version 3.0](https://github.com/Isotr0py/pillow-jpegxl-plugin/blob/main/LICENSE).

* [Xkcd](https://xkcd.com): Images in `test/data` directory are from Xkcd and are under the [Creative Commons Attribution-NonCommercial 2.5 license](https://creativecommons.org/licenses/by-nc/2.5/).