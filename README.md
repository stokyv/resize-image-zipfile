# resize-image-zipfile

A small Windows-friendly Python utility that optimizes images stored inside
ZIP, CBZ, and RAR archives. It recursively finds images, applies EXIF rotation,
limits their width to 1280 pixels without upscaling, converts them to WebP at
quality 80, and creates a new ZIP archive.

## Features

- Processes ZIP, CBZ, and RAR files, including nested archives.
- Supports JPEG, PNG, BMP, GIF, TIFF, and WebP input images.
- Preserves aspect ratios and images already narrower than 1280 pixels.
- Handles Unicode filenames and repairs common legacy CP932 Japanese ZIP names.
- Processes up to eight top-level archives concurrently by default.
- Protects against unsafe archive paths during ZIP extraction.
- Records run details and errors in `resize.log`.

## Requirements

- Windows with Python 3.13 or another Pillow-compatible Python version.
- [`uv`](https://docs.astral.sh/uv/) for environment and package management.
- 7-Zip (`7z.exe` or `7zz`) on `PATH` when processing RAR files. ZIP and CBZ
  files use Python's standard library and do not require 7-Zip.

## Setup

```powershell
uv venv
uv pip install -r requirements.txt
```

## Usage

Double-click `run_script.bat` to process all supported archives beside the
script, or drag one or more archives onto `drag_and_drop_zip.bat`.

From a terminal, archives can be selected explicitly and worker concurrency can
be changed:

```powershell
.venv\Scripts\python.exe script.py --workers 4 book.zip comic.cbz
```

With no archive arguments, the script processes supported archives in the
current directory, excluding output files whose names end in `-1280x.zip`.

## Output and file handling

For an input named `book.zip`, the generated archive is `book-1280x.zip` in the
same directory. After processing:

- Successful inputs move to `processed-success/`.
- Failed inputs move to `processed-failed/`.
- Generated output archives remain beside those folders.
- Temporary extraction data under `.resize-temp/` is removed automatically.

Nested ZIP and CBZ archives are rebuilt as ZIP files. Because the RAR format is
read-only in 7-Zip, a nested `name.rar` is rebuilt as `name.rar.zip`.

## Project files

- `script.py` contains archive extraction, image conversion, concurrency, and
  result-handling logic.
- `run_script.bat` processes archives from the project directory.
- `drag_and_drop_zip.bat` accepts archives dropped onto it in Windows Explorer.
- `requirements.txt` pins the Python dependency.
- `examples/` contains sample archives; archive files elsewhere are ignored by
  Git so local input and generated output data are not committed accidentally.
