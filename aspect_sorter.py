#!/usr/bin/env python3
"""
Aspect Sorter
=============

Sorts photos and videos located in the script's directory into three folders
according to their aspect ratio:

    horizontal/  - wider than tall   (e.g. 1920x1080)
    vertical/    - taller than wide  (e.g. 1080x1920)
    square/      - (almost) equal sides (e.g. 1080x1080)

The work starts immediately after launch. The script only asks questions when
something goes wrong, e.g. when a file with the same name already exists in the
destination folder.

Requirements:
    * Python 3.8+
    * Pillow            (images, GIFs)      ->  pip install Pillow
    * ffprobe (FFmpeg)  (videos, optional)  ->  https://ffmpeg.org/download.html
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:
    sys.exit("Error: Pillow is required. Install it with: pip install Pillow")

# Optional HEIC/HEIF support (iPhone photos).
try:
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except ImportError:
    pass

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp",
    ".tif", ".tiff", ".gif", ".heic", ".heif", ".avif",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".wmv", ".flv",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".m2ts", ".ogv",
}

FOLDER_HORIZONTAL = "horizontal"
FOLDER_VERTICAL = "vertical"
FOLDER_SQUARE = "square"

# Files whose width/height ratio differs from 1.0 by no more than this value
# are treated as square. 0.02 means "within 2%".
DEFAULT_SQUARE_TOLERANCE = 0.02

# EXIF orientation values that mean the image is rotated by 90/270 degrees.
EXIF_ORIENTATION_TAG = 0x0112
EXIF_SWAPPED_ORIENTATIONS = {5, 6, 7, 8}

Image.MAX_IMAGE_PIXELS = None  # We only read the size, never decode pixels.


# --------------------------------------------------------------------------- #
# Dimension detection
# --------------------------------------------------------------------------- #

class FFprobeMissing(RuntimeError):
    """Raised when ffprobe is not installed or not on PATH."""


def get_image_size(path: Path) -> Tuple[float, float]:
    """Return the displayed (width, height) of an image, honoring EXIF rotation."""
    with Image.open(path) as img:
        width, height = img.size
        try:
            orientation = img.getexif().get(EXIF_ORIENTATION_TAG)
        except Exception:
            orientation = None
    if orientation in EXIF_SWAPPED_ORIENTATIONS:
        width, height = height, width
    return float(width), float(height)


def get_video_size(path: Path) -> Tuple[float, float]:
    """Return the displayed (width, height) of a video using ffprobe.

    Takes rotation metadata (phone videos) and non-square pixels into account.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise FFprobeMissing("ffprobe not found")

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    streams = json.loads(result.stdout or "{}").get("streams") or []
    if not streams:
        raise RuntimeError("no video stream found")

    stream = streams[0]
    width = float(stream["width"])
    height = float(stream["height"])

    # Non-square pixels (anamorphic video).
    sar = str(stream.get("sample_aspect_ratio") or "")
    if ":" in sar:
        try:
            num, den = (int(x) for x in sar.split(":", 1))
            if num > 0 and den > 0:
                width = width * num / den
        except ValueError:
            pass

    # Rotation metadata.
    rotation = 0
    rotate_tag = (stream.get("tags") or {}).get("rotate")
    if rotate_tag is not None:
        rotation = int(float(rotate_tag))
    for side_data in stream.get("side_data_list") or []:
        if "rotation" in side_data:
            rotation = int(float(side_data["rotation"]))
    if abs(rotation) % 180 == 90:
        width, height = height, width

    return width, height


def classify(width: float, height: float, tolerance: float) -> str:
    """Return the destination folder name for the given dimensions."""
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid dimensions {width}x{height}")
    ratio = width / height
    if abs(ratio - 1.0) <= tolerance:
        return FOLDER_SQUARE
    return FOLDER_HORIZONTAL if ratio > 1.0 else FOLDER_VERTICAL


# --------------------------------------------------------------------------- #
# Name conflict handling
# --------------------------------------------------------------------------- #

def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending _1, _2, ... to the file name."""
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def ask(prompt: str) -> str:
    """Read a line from the user. Returns '' if input is unavailable."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


class ConflictResolver:
    """Asks the user what to do when the destination file already exists."""

    RENAME_AUTO, RENAME_MANUAL, OVERWRITE, SKIP = "1", "2", "3", "4"

    def __init__(self) -> None:
        self.remembered: Optional[str] = None

    def resolve(self, src: Path, dst: Path) -> Optional[Path]:
        """Return the final destination path, or None to skip the file."""
        if self.remembered is not None:
            return self._apply(self.remembered, dst)

        print(f"\n[!] '{dst.parent.name}/{dst.name}' already exists.")
        print("    What should be done with the new file?")
        print("      1 - Rename automatically (add a numeric suffix)")
        print("      2 - Enter a new name")
        print("      3 - Overwrite the existing file")
        print("      4 - Skip this file")

        while True:
            choice = ask("    Your choice [1-4]: ")
            if choice == "":
                # No input available (non-interactive run): be safe, skip.
                print("    No input - skipping.")
                return None
            if choice in {self.RENAME_AUTO, self.RENAME_MANUAL, self.OVERWRITE, self.SKIP}:
                break
            print("    Please enter 1, 2, 3 or 4.")

        if choice != self.RENAME_MANUAL:
            if ask("    Apply this choice to all remaining conflicts? [y/N]: ").lower() == "y":
                self.remembered = choice

        return self._apply(choice, dst)

    def _apply(self, choice: str, dst: Path) -> Optional[Path]:
        if choice == self.RENAME_AUTO:
            return unique_path(dst)
        if choice == self.OVERWRITE:
            return dst
        if choice == self.SKIP:
            return None
        return self._ask_new_name(dst)

    @staticmethod
    def _ask_new_name(dst: Path) -> Optional[Path]:
        while True:
            name = ask("    New file name (empty = skip file): ")
            if not name:
                return None
            if "/" in name or "\\" in name:
                print("    The name must not contain path separators.")
                continue
            candidate = dst.with_name(name if Path(name).suffix else name + dst.suffix)
            if candidate.exists():
                print(f"    '{candidate.name}' already exists, try another name.")
                continue
            return candidate


# --------------------------------------------------------------------------- #
# Main logic
# --------------------------------------------------------------------------- #

def get_base_dir() -> Path:
    """Directory where the script (or the frozen executable) lives."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def collect_media(base_dir: Path) -> List[Path]:
    """Return media files located directly in base_dir (not recursive)."""
    own_path = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    supported = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    files = []
    for entry in sorted(base_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        if entry.suffix.lower() not in supported:
            continue
        if own_path is not None and entry.resolve() == own_path:
            continue
        files.append(entry)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort photos and videos into horizontal/vertical/square folders "
                    "by aspect ratio. Runs immediately, no questions asked "
                    "unless an error occurs.",
    )
    parser.add_argument(
        "-d", "--dir", type=Path, default=None,
        help="Directory to process (default: the directory of this script).",
    )
    parser.add_argument(
        "-t", "--tolerance", type=float, default=DEFAULT_SQUARE_TOLERANCE,
        help="Max deviation of width/height from 1.0 to still count as square "
             f"(default: {DEFAULT_SQUARE_TOLERANCE}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without moving or creating anything.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = (args.dir or get_base_dir()).resolve()

    if not base_dir.is_dir():
        print(f"Error: '{base_dir}' is not a directory.")
        return 1

    files = collect_media(base_dir)
    if not files:
        print(f"No supported photos or videos found in: {base_dir}")
        return 0

    print(f"Processing {len(files)} file(s) in: {base_dir}")
    if args.dry_run:
        print("(dry run - nothing will be changed)")
    print()

    resolver = ConflictResolver()
    counts: Dict[str, int] = {FOLDER_HORIZONTAL: 0, FOLDER_VERTICAL: 0, FOLDER_SQUARE: 0}
    skipped: List[Tuple[Path, str]] = []
    failed: List[Tuple[Path, str]] = []
    ffprobe_available = True

    for src in files:
        ext = src.suffix.lower()
        is_video = ext in VIDEO_EXTENSIONS

        # 1) Detect dimensions.
        try:
            if is_video:
                if not ffprobe_available:
                    skipped.append((src, "ffprobe is not installed"))
                    continue
                width, height = get_video_size(src)
            else:
                width, height = get_image_size(src)
            folder = classify(width, height, args.tolerance)
        except FFprobeMissing:
            ffprobe_available = False
            print("[!] ffprobe (FFmpeg) was not found - videos will be skipped.")
            print("    Install FFmpeg and make sure 'ffprobe' is on your PATH.\n")
            skipped.append((src, "ffprobe is not installed"))
            continue
        except Exception as exc:
            failed.append((src, f"cannot read dimensions: {exc}"))
            print(f"[x] {src.name}: cannot read dimensions ({exc})")
            continue

        # 2) Move the file.
        dest_dir = base_dir / folder
        dst = dest_dir / src.name
        label = f"{int(round(width))}x{int(round(height))}"

        if args.dry_run:
            note = " (name conflict)" if dst.exists() else ""
            print(f"[dry] {src.name} -> {folder}/ [{label}]{note}")
            counts[folder] += 1
            continue

        try:
            dest_dir.mkdir(exist_ok=True)
            if dst.exists():
                resolved = resolver.resolve(src, dst)
                if resolved is None:
                    skipped.append((src, "name conflict"))
                    print(f"[-] {src.name}: skipped")
                    continue
                dst = resolved
                if dst.exists():  # overwrite chosen
                    dst.unlink()
            shutil.move(str(src), str(dst))
        except OSError as exc:
            failed.append((src, f"cannot move file: {exc}"))
            print(f"[x] {src.name}: cannot move file ({exc})")
            continue

        counts[folder] += 1
        renamed = f" (saved as {dst.name})" if dst.name != src.name else ""
        print(f"[+] {src.name} -> {folder}/ [{label}]{renamed}")

    # 3) Summary.
    verb = "would be moved" if args.dry_run else "moved"
    print("\n" + "-" * 40)
    print(f"Done. {sum(counts.values())} file(s) {verb}:")
    for name, count in counts.items():
        print(f"  {name:<11} {count}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for path, reason in skipped:
            print(f"  - {path.name}: {reason}")
    if failed:
        print(f"Failed: {len(failed)}")
        for path, reason in failed:
            print(f"  - {path.name}: {reason}")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
