# Aspect Sorter AX

A tiny, zero-configuration Python script that sorts your photos and videos into folders by **aspect ratio**:

| Folder        | Meaning                              | Example      |
|---------------|--------------------------------------|--------------|
| `horizontal/` | Wider than tall (landscape)          | 1920 × 1080  |
| `vertical/`   | Taller than wide (portrait)          | 1080 × 1920  |
| `square/`     | Equal (or nearly equal) sides        | 1080 × 1080  |

Drop the script into a folder, run it, and you're done. No menus, no prompts, no config files.

## Features

- **Runs immediately.** No questions are asked unless something goes wrong.
- **Photos and videos.** Supports the most common formats (see [Supported formats](#supported-formats)).
- **Rotation-aware.** Respects EXIF orientation for photos and rotation metadata for videos, so a portrait phone video is correctly detected as vertical.
- **Handles non-square pixels** in anamorphic videos.
- **Creates folders on demand.** Only the folders that are actually needed are created.
- **Safe conflict handling.** If a file with the same name already exists in the target folder, you choose to rename, enter a new name, overwrite, or skip, and can apply that choice to all remaining conflicts.
- **Dry-run mode** to preview the result before anything is moved.
- **Non-recursive and safe.** Only files located directly next to the script are processed, and the script never touches itself or hidden files.

## Requirements

- Python 3.8 or newer
- [Pillow](https://python-pillow.org/) for photos and GIFs
- [FFmpeg](https://ffmpeg.org/download.html) (specifically `ffprobe`) for videos. Without it, photos are still sorted and videos are skipped with a warning.
- *Optional:* [`pillow-heif`](https://pypi.org/project/pillow-heif/) for HEIC/HEIF photos

## Installation

```bash
git clone https://github.com/<your-username>/aspect-sorter.git
cd aspect-sorter
pip install -r requirements.txt
```

Make sure `ffprobe` is available in your `PATH`:

```bash
ffprobe -version
```

## Usage

1. Copy `aspect_sorter.py` into the folder with your media files.
2. Run it:

```bash
python aspect_sorter.py
```

That's it. Example output:

```
Processing 5 file(s) in: /home/user/Pictures/Trip

[+] IMG_0001.jpg -> horizontal/ [4032x3024]
[+] IMG_0002.jpg -> vertical/ [3024x4032]
[+] clip.mp4 -> vertical/ [1080x1920]
[+] avatar.png -> square/ [512x512]
[+] banner.webp -> horizontal/ [1600x400]

----------------------------------------
Done. 5 file(s) moved:
  horizontal  2
  vertical    2
  square      1
```

> **Windows tip:** run the script from a terminal (`cmd`, PowerShell, Windows Terminal). If you double-click it, the window will close as soon as the work is done.

### Optional arguments

| Argument              | Description                                                                         |
|-----------------------|-------------------------------------------------------------------------------------|
| `-d`, `--dir PATH`    | Process another directory instead of the script's own directory.                    |
| `-t`, `--tolerance X` | How far `width / height` may deviate from `1.0` to still count as square (default `0.02`, i.e. 2%). Use `0` for strictly equal sides. |
| `--dry-run`           | Show what would happen without creating folders or moving files.                    |

Examples:

```bash
python aspect_sorter.py --dry-run
python aspect_sorter.py --dir "D:\Downloads\Memes"
python aspect_sorter.py --tolerance 0
```

## Name conflicts

If the target folder already contains a file with the same name, the script asks what to do:

```
[!] 'horizontal/photo.jpg' already exists.
    What should be done with the new file?
      1 - Rename automatically (add a numeric suffix)
      2 - Enter a new name
      3 - Overwrite the existing file
      4 - Skip this file
    Your choice [1-4]:
```

For options 1, 3 and 4 you can also apply the choice to all remaining conflicts. If the script runs without an interactive terminal, conflicting files are skipped, never overwritten.

## Supported formats

**Photos:** `jpg`, `jpeg`, `jfif`, `png`, `webp`, `bmp`, `tif`, `tiff`, `gif`, `avif`, `heic`, `heif` (HEIC/HEIF require `pillow-heif`)

**Videos:** `mp4`, `mkv`, `webm`, `avi`, `mov`, `wmv`, `flv`, `m4v`, `mpg`, `mpeg`, `3gp`, `ts`, `m2ts`, `ogv`

GIFs are treated as images. To support more formats, add extensions to `IMAGE_EXTENSIONS` or `VIDEO_EXTENSIONS` at the top of the script.

## Error handling

- Files whose dimensions cannot be read (corrupted, unsupported codec, etc.) are left in place and listed in the final summary.
- If `ffprobe` is missing, videos are skipped with a clear message.
- The exit code is `0` on success and `1` if any file failed.

## Credits
The code was written using web version of Claude Sonnet 5.5 😁.

## License

[MIT](LICENSE)

