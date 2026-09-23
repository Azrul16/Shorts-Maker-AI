"""Phase one: video URL -> download -> timestamped JSON transcript."""

import argparse
import json
from pathlib import Path
import sys

from downloader import download_video
from transcriber import transcribe

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("url", nargs="?", help="Video URL; prompted for when omitted")
    source.add_argument("--file", type=Path, help="Transcribe an existing local video or audio file")
    parser.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"], help="Whisper model (default: small)")
    args = parser.parse_args()
    try:
        if args.file:
            video_path = str(args.file.resolve())
        else:
            url = args.url or input("Paste YouTube URL: ").strip()
            print("\nDownloading video...", flush=True)
            video_path = download_video(url)
            print(f"\nDownloaded: {video_path}")
        print("\nGenerating transcript...", flush=True)
        transcript = transcribe(video_path, model_size=args.model)
        transcript_dir = ROOT / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)
        destination = transcript_dir / f"{Path(video_path).stem}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)
        print(f"\nDone! Transcript segments: {len(transcript)}")
        print(f"Saved: {destination}")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
