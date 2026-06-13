#!/usr/bin/env python3
"""Re-encode plugin MP3 audio to a lower bitrate with ffmpeg."""
# python3 scripts/compress-audio.py --jobs 4
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).parent.parent
DEFAULT_AUDIO_DIR = ROOT / "audio"
DEFAULT_BITRATE = "32k"
DEFAULT_SKIP_BITRATE = 33000
DEFAULT_JOBS = 4


class BatchResult(NamedTuple):
    total: int
    compressed: int
    skipped: int
    failed: int


def iter_audio_files(audio_dir: Path) -> list[Path]:
    files: list[Path] = []
    for ext in ("*.mp3", "*.ogg", "*.wav"):
        for path in audio_dir.rglob(ext):
            if ".compress-tmp." in path.name:
                continue
            files.append(path)
    return sorted(files)


def probe_bitrate(path: Path) -> int | None:
    try:
        output = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        ).strip()
        if not output:
            return None
        return int(output)
    except (subprocess.CalledProcessError, ValueError):
        return None


def compress_file(
    path: Path,
    bitrate: str,
    skip_bitrate: int,
    mono: bool,
) -> str:
    if path.stat().st_size == 0:
        return "failed"

    current_bitrate = probe_bitrate(path)
    if current_bitrate is not None and current_bitrate <= skip_bitrate:
        return "skipped"

    tmp_path = path.with_name(f"{path.stem}.compress-tmp{path.suffix}")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
    ]
    if mono:
        command.extend(["-ac", "1"])
    command.append(str(tmp_path))

    try:
        subprocess.run(command, check=True)
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            tmp_path.unlink(missing_ok=True)
            return "failed"
        tmp_path.replace(path)
        return "compressed"
    except subprocess.CalledProcessError:
        tmp_path.unlink(missing_ok=True)
        return "failed"


def compress_audio(
    audio_dir: Path,
    bitrate: str = DEFAULT_BITRATE,
    skip_bitrate: int = DEFAULT_SKIP_BITRATE,
    jobs: int = DEFAULT_JOBS,
    mono: bool = True,
) -> BatchResult:
    files = iter_audio_files(audio_dir)
    compressed = skipped = failed = 0
    worker_count = max(1, jobs)

    if worker_count == 1:
        for path in files:
            status = compress_file(path, bitrate, skip_bitrate, mono)
            if status == "compressed":
                compressed += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(compress_file, path, bitrate, skip_bitrate, mono): path
                for path in files
            }
            for future in as_completed(futures):
                status = future.result()
                if status == "compressed":
                    compressed += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    failed += 1

    return BatchResult(
        total=len(files),
        compressed=compressed,
        skipped=skipped,
        failed=failed,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compress plugin audio with ffmpeg")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--bitrate", default=DEFAULT_BITRATE, help="Audio bitrate (default: 32k)")
    parser.add_argument(
        "--skip-bitrate",
        type=int,
        default=DEFAULT_SKIP_BITRATE,
        help="Skip files already at or below this bitrate (default: 33000)",
    )
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    parser.add_argument(
        "--stereo",
        action="store_true",
        help="Keep stereo instead of forcing mono",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not shutil_which("ffmpeg") or not shutil_which("ffprobe"):
        print("ffmpeg and ffprobe are required", file=sys.stderr)
        return 1

    print(
        f"Compressing audio in {args.audio_dir} to {args.bitrate}, "
        f"jobs={args.jobs}, skip<={args.skip_bitrate}"
    )
    result = compress_audio(
        audio_dir=args.audio_dir,
        bitrate=args.bitrate,
        skip_bitrate=args.skip_bitrate,
        jobs=args.jobs,
        mono=not args.stereo,
    )
    print(
        "Done: "
        f"total {result.total}, "
        f"compressed {result.compressed}, "
        f"skipped {result.skipped}, "
        f"failed {result.failed}"
    )
    return 1 if result.failed else 0


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


if __name__ == "__main__":
    raise SystemExit(main())
