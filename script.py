import argparse
import concurrent.futures
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps


if os.name == "nt":
    # Do not let Windows' legacy console code page crash on Japanese filenames.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


TARGET_WIDTH = 1280
WEBP_QUALITY = 80
DEFAULT_WORKERS = 8
LOG_FILENAME = "resize.log"
SUCCESS_DIRECTORY_NAME = "processed-success"
FAILED_DIRECTORY_NAME = "processed-failed"
ARCHIVE_EXTENSIONS = {".zip", ".cbz", ".rar"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


def display_name(info):
    """Repair legacy Japanese ZIP names that were stored as CP932."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        raw = info.filename.encode("cp437")
        candidate = decode_legacy_cp932(raw)
        if any(ord(char) > 127 for char in candidate):
            return candidate
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return info.filename


def decode_legacy_cp932(raw):
    """Decode CP932, undoing ZIP tools that changed a 0x5c trail byte to '/'."""
    repaired = bytearray()
    index = 0
    while index < len(raw):
        value = raw[index]
        is_lead_byte = 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC
        if is_lead_byte and index + 1 < len(raw) and raw[index + 1] == 0x2F:
            # In CP932, e.g. 0x97 0x5c is "予". Some old ZIP tools mistake
            # that 0x5c trail byte for a path slash and rewrite it as 0x2f.
            repaired.extend((value, 0x5C))
            index += 2
            continue
        repaired.append(value)
        index += 1
    return repaired.decode("cp932")


def safe_destination(root, member_name):
    parts = [part for part in PurePosixPath(member_name.replace("\\", "/")).parts
             if part not in ("", ".", "..")]
    destination = root.joinpath(*parts)
    if not destination.is_relative_to(root):
        raise ValueError(f"Unsafe archive path: {member_name}")
    return destination


def extract_zip(archive, output_dir):
    with zipfile.ZipFile(archive, "r") as source:
        for info in source.infolist():
            destination = safe_destination(output_dir, display_name(info))
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def find_7zip():
    return shutil.which("7z") or shutil.which("7zz")


def extract_archive(archive, output_dir):
    if archive.suffix.lower() in {".zip", ".cbz"}:
        extract_zip(archive, output_dir)
        return
    seven_zip = find_7zip()
    if not seven_zip:
        raise RuntimeError("RAR support requires 7-Zip (7z.exe) to be installed and on PATH.")
    result = subprocess.run(
        [seven_zip, "x", "-y", f"-o{output_dir}", str(archive)],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"7-Zip could not extract {archive.name}:\n{result.stderr or result.stdout}")


def write_zip(directory, output_path):
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                target.write(file_path, file_path.relative_to(directory).as_posix())


def convert_image(file_path):
    output_path = file_path.with_suffix(".webp")
    temporary_output = output_path.with_name(output_path.name + ".tmp")
    with Image.open(file_path) as source:
        image = ImageOps.exif_transpose(source)
        if image.width > TARGET_WIDTH:
            height = round(image.height * TARGET_WIDTH / image.width)
            image = image.resize((TARGET_WIDTH, height), Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        image.save(temporary_output, format="WEBP", quality=WEBP_QUALITY, method=6)
    os.replace(temporary_output, output_path)
    if output_path != file_path:
        file_path.unlink()


def process_contents(directory, temporary_root):
    image_count = 0
    nested_archive_count = 0
    # Innermost archives first. Newly extracted content is processed recursively.
    archives = [path for path in directory.rglob("*")
                if path.is_file() and path.suffix.lower() in ARCHIVE_EXTENSIONS]
    for archive in archives:
        nested_archive_count += 1
        with tempfile.TemporaryDirectory(prefix="nested_", dir=temporary_root) as temp:
            extracted = Path(temp)
            extract_archive(archive, extracted)
            nested_images, nested_archives = process_contents(extracted, temporary_root)
            image_count += nested_images
            nested_archive_count += nested_archives
            # RAR is read-only in 7-Zip; keep its original suffix in the new
            # name so a sibling foo.zip can never be overwritten by foo.rar.
            replacement = (archive.with_name(archive.name + ".zip")
                           if archive.suffix.lower() == ".rar"
                           else archive.with_suffix(".zip"))
            temporary_zip = replacement.with_name(replacement.name + ".tmp")
            write_zip(extracted, temporary_zip)
            archive.unlink()
            os.replace(temporary_zip, replacement)

    for image_path in list(directory.rglob("*")):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
            convert_image(image_path)
            image_count += 1

    return image_count, nested_archive_count


def process_archive(archive_path, temporary_root):
    started = time.perf_counter()
    archive = Path(archive_path).resolve()
    if not archive.is_file() or archive.suffix.lower() not in ARCHIVE_EXTENSIONS:
        raise ValueError(f"Not a supported archive: {archive}")
    output_path = archive.with_name(f"{archive.stem}-1280x.zip")
    with tempfile.TemporaryDirectory(prefix="archive_", dir=temporary_root) as temp:
        extracted = Path(temp)
        extract_archive(archive, extracted)
        image_count, nested_archive_count = process_contents(extracted, temporary_root)
        temporary_zip = output_path.with_name(output_path.name + ".tmp")
        write_zip(extracted, temporary_zip)
        os.replace(temporary_zip, output_path)
    return {
        "output": str(output_path),
        "images": image_count,
        "nested_archives": nested_archive_count,
        "seconds": time.perf_counter() - started,
    }


def positive_worker_count(value):
    try:
        workers = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("worker count must be an integer") from error
    if workers < 1:
        raise argparse.ArgumentTypeError("worker count must be at least 1")
    return workers


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Resize images inside ZIP, CBZ, and RAR archives."
    )
    parser.add_argument(
        "--workers",
        type=positive_worker_count,
        default=DEFAULT_WORKERS,
        help=f"maximum archives to process concurrently (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument("archives", nargs="*", help="archives to process")
    return parser.parse_args()


def find_archives(arguments):
    if arguments:
        candidates = [Path(argument) for argument in arguments]
    else:
        candidates = sorted(
            (path for path in Path.cwd().iterdir()
             if path.is_file()
             and path.suffix.lower() in ARCHIVE_EXTENSIONS
             and not path.name.lower().endswith("-1280x.zip")),
            key=lambda path: path.name.casefold(),
        )

    archives = []
    seen_inputs = set()
    output_owners = {}
    for candidate in candidates:
        archive = candidate.resolve()
        if not archive.is_file() or archive.suffix.lower() not in ARCHIVE_EXTENSIONS:
            raise ValueError(f"Not a supported archive: {archive}")

        input_key = os.path.normcase(str(archive))
        if input_key in seen_inputs:
            continue
        seen_inputs.add(input_key)

        output_path = archive.with_name(f"{archive.stem}-1280x.zip")
        output_key = os.path.normcase(str(output_path))
        if output_key in output_owners:
            raise ValueError(
                f"Output collision: {output_owners[output_key]} and {archive} "
                f"would both create {output_path}"
            )
        output_owners[output_key] = archive
        archives.append(archive)
    return archives


def configure_logger(log_path):
    logger = logging.getLogger("resize-image-zipfile")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def unique_processed_destination(archive, directory_name):
    processed_directory = archive.parent / directory_name
    processed_directory.mkdir(exist_ok=True)
    destination = processed_directory / archive.name
    number = 2
    while destination.exists():
        destination = processed_directory / f"{archive.stem} ({number}){archive.suffix}"
        number += 1
    return destination


def move_processed_archive(archive, directory_name):
    if archive.parent.name.casefold() == directory_name.casefold():
        return archive
    destination = unique_processed_destination(archive, directory_name)
    return Path(shutil.move(str(archive), str(destination)))


def run_archives(archives, maximum_workers, temporary_root, logger):
    worker_count = min(maximum_workers, len(archives))
    print(
        f"Processing {len(archives)} archive(s) with {worker_count} worker(s).",
        flush=True,
    )
    print(f"Temporary files: {temporary_root}", flush=True)
    logger.info(
        "Starting run: archives=%d workers=%d temporary_directory=%s",
        len(archives),
        worker_count,
        temporary_root,
    )

    failures = 0
    completed = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        future_archives = {
            executor.submit(process_archive, str(archive), str(temporary_root)): archive
            for archive in archives
        }
        for future in concurrent.futures.as_completed(future_archives):
            archive = future_archives[future]
            completed += 1
            try:
                result = future.result()
            except Exception as error:
                failures += 1
                logger.error(
                    "Archive failed: %s | %s",
                    archive,
                    error,
                    exc_info=(type(error), error, error.__traceback__),
                )
                print(
                    f"[{completed}/{len(archives)}] ERROR: {archive}: {error}",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    failed_path = move_processed_archive(archive, FAILED_DIRECTORY_NAME)
                except Exception as move_error:
                    logger.error(
                        "Could not move failed archive: %s | %s",
                        archive,
                        move_error,
                        exc_info=(type(move_error), move_error, move_error.__traceback__),
                    )
                    print(
                        f"  Could not move to {FAILED_DIRECTORY_NAME}: {move_error}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    logger.info("Moved failed archive: %s -> %s", archive, failed_path)
                    print(f"  Moved to: {failed_path}", flush=True)
                continue

            try:
                success_path = move_processed_archive(archive, SUCCESS_DIRECTORY_NAME)
            except Exception as move_error:
                failures += 1
                success_path = None
                logger.error(
                    "Could not move successfully processed archive: %s | %s",
                    archive,
                    move_error,
                    exc_info=(type(move_error), move_error, move_error.__traceback__),
                )
                print(
                    f"  Could not move to {SUCCESS_DIRECTORY_NAME}: {move_error}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                logger.info("Moved successful archive: %s -> %s", archive, success_path)

            logger.info(
                "Archive completed: %s | output=%s images=%d nested_archives=%d "
                "seconds=%.1f input_moved_to=%s",
                archive,
                result["output"],
                result["images"],
                result["nested_archives"],
                result["seconds"],
                success_path or "MOVE FAILED",
            )
            print(
                f"[{completed}/{len(archives)}] Created: {result['output']} "
                f"({result['images']} image(s), "
                f"{result['nested_archives']} nested archive(s), "
                f"{result['seconds']:.1f}s)",
                flush=True,
            )
            if success_path:
                print(f"  Input moved to: {success_path}", flush=True)
    logger.info(
        "Finished run: completed=%d succeeded=%d failed=%d",
        completed,
        completed - failures,
        failures,
    )
    return failures


def main():
    args = parse_arguments()
    log_path = Path(__file__).resolve().parent / LOG_FILENAME
    logger = configure_logger(log_path)
    try:
        archives = find_archives(args.archives)
    except ValueError as error:
        logger.error("Input validation failed: %s", error)
        print(f"ERROR: {error}", file=sys.stderr)
        print(f"Log: {log_path}")
        return 1
    if not archives:
        logger.info("No supported archives found.")
        print("No ZIP, CBZ, or RAR files found.")
        print(f"Log: {log_path}")
        return 1

    # Keep extraction data on the same drive as this script instead of the
    # system temp directory. The run directory and every archive directory
    # beneath it are removed when processing finishes, including after errors.
    temporary_base = Path(__file__).resolve().parent / ".resize-temp"
    temporary_base.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="run_", dir=temporary_base) as temp:
            failures = run_archives(archives, args.workers, Path(temp), logger)
    finally:
        try:
            temporary_base.rmdir()
        except OSError:
            # Another run or remnants from an abruptly terminated run may exist.
            pass
    print(f"Log: {log_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
