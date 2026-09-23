# AI Short Maker

A local Windows desktop application for turning long videos into captioned, vertical shorts. Paste a YouTube link or select a video from your computer, choose your settings, and generate clips with automatic face following and zoom.

The application runs transcription and video processing on your own computer. No paid API or cloud processing account is required.

## Features

- **Desktop interface:** paste a link, select a local file, and manage export settings.
- **Automatic clip selection:** ranks speech windows using hooks, topic relevance, speech density, and sentence boundaries.
- **Vertical reframing:** creates 9:16 videos with smooth face following, scene-cut handling, and subtle automatic zoom.
- **Word captions:** burns outlined, highlighted captions into the video and saves editable ASS subtitle files.
- **CPU and GPU processing:** uses CUDA for transcription and NVIDIA NVENC for encoding when available, with CPU fallback.
- **Progress and cancellation:** tracks downloading, transcription, selection, and export separately.
- **Organized exports:** saves clips under `shorts/<main video title>/` with descriptive filenames.
- **Automatic cleanup:** deletes the downloaded full video after all clips have been exported and verified. Local input videos are kept.

## Quick start: use the Windows application

If you already have the built application, open:

```text
dist/AI Short Maker/AI Short Maker.exe
```

Keep the **entire `AI Short Maker` folder** together, including `_internal`. This is a portable folder build, not a standalone EXE that can be moved by itself.

The build includes Python, FFmpeg, Node.js, the default Whisper small model, and NVIDIA runtime libraries. You do not need to install those separately to use the packaged app. An NVIDIA graphics driver is still needed for GPU acceleration. The tested distribution is approximately **3.37 GiB**.

### Create your first shorts

1. Paste a YouTube URL or click **Choose file**.
2. Set the number of shorts, target duration, transcription model, and export quality.
3. Enable **Follow faces**, **Auto zoom**, **Word captions**, and **Use NVIDIA GPU** as needed.
4. Use **Save to...** to choose an export location.
5. Click **Generate shorts** and follow the progress bars.
6. Click **Play short** to review an export, or **Open output folder** to see all files.

Use videos you own or have permission to edit.

## Install and run from source

Run the following commands in **Windows PowerShell**, from the project directory.

### 1. Prepare the prerequisites

The project has been tested with **64-bit Python 3.14.5** on Windows and an **NVIDIA GeForce RTX 3050 Laptop GPU with 4 GB VRAM**. CPU processing is also supported.

For source execution, install Python and a supported JavaScript runtime for YouTube extraction. The downloader enables Node.js 22+ and Deno 2.3+ when available; the EXE build bundles Node.js when it is on PATH.

Install FFmpeg with:

```powershell
winget install --id=Gyan.FFmpeg -e
```

Close and reopen PowerShell after installation, then verify your tools:

```powershell
python --version
ffmpeg -version
ffprobe -version
node --version
```

If you use portable FFmpeg instead, place `ffmpeg.exe` and `ffprobe.exe` in `.tools/ffmpeg/bin/`. The application detects that location automatically.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

The examples below call the environment's Python directly, so PowerShell activation is optional.

### 3. Install dependencies

To reproduce the tested environment, including build tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Alternatively, install the unpinned runtime dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Windows dependencies include NVIDIA runtime packages, so installation can involve large downloads even if you later select CPU processing.

### 4. Start the desktop application

```powershell
.\.venv\Scripts\python.exe desktop.py
```

The source version downloads its speech model on first use and reuses the local cache afterward. The packaged application already includes the default small model.

## Settings

| Setting | Options and behavior |
| --- | --- |
| Number of shorts | 1–10 requested clips; fewer may be produced when usable speech is limited. |
| Target length | Approximately 30, 40, or 60 seconds; actual lengths follow speech boundaries. |
| Transcription model | Small for balanced processing, medium for potentially better accuracy with more time and memory, or base for a fast draft. |
| Export quality | 1080 × 1920 or 720 × 1280, at 30 FPS. |
| Follow faces | Moves the crop toward a detected face, with smoothing and scene-cut resets. |
| Auto zoom | Applies subtle face-aware zoom up to approximately 1.18× when face following is enabled. |
| Word captions | Adds highlighted captions to the exported video and saves an ASS subtitle file. |
| Use NVIDIA GPU | Attempts CUDA transcription and NVENC encoding; falls back to CPU if necessary. |

Downloads are capped at 1080p. Exporting a low-resolution video at a higher resolution does not restore missing detail.

## How processing works

```text
YouTube URL or local video
    -> Download / inspect video
    -> Transcribe speech with word timestamps
    -> Score and select non-overlapping clips
    -> Follow faces and reframe to 9:16
    -> Add captions and encode MP4 files
    -> Verify exports
    -> Remove the downloaded full video
```

The GPU handles Whisper inference through CUDA and H.264 encoding through NVENC. The CPU handles video decoding, face detection, camera movement, resizing, and caption composition. Model memory is released before rendering.

The hardware panel shows detected CUDA availability and the result of an actual NVENC encoder check. Activity messages report processing and fallback behavior. CPU and GPU utilization varies by stage; both do not need to be fully utilized at all times.

## Output folders and cleanup

The packaged app uses `Documents/AI Short Maker/` as its default data directory. The source version uses the project directory. **Save to...** changes where exports are stored.

```text
shorts/
└── Main Video Title/
    ├── 01 - First clip title.mp4
    ├── 01 - First clip title.ass
    ├── 01 - First clip title.jpg
    ├── 02 - Second clip title.mp4
    ├── 02 - Second clip title.ass
    ├── 02 - Second clip title.jpg
    └── project.json
```

The main video title comes from the download metadata, or from the filename for local inputs. Clip titles come from their opening transcript text. Characters that Windows cannot use in filenames are removed. Repeat runs create folders such as `Main Video Title (2)` instead of overwriting earlier results.

If the selected save location is not already named `shorts`, the application creates a `shorts` folder inside it. ASS files are created when captions are enabled. `project.json` records source information, selected timestamps, scoring reasons, face detection counts, encoding details, and download cleanup status.

**Downloaded originals are deleted only after all selected clips finish exporting and pass verification.** Failed or cancelled jobs retain the download for a retry. Videos selected from your computer are always kept. If deletion fails, the application keeps the finished shorts and displays a warning.

Transcripts remain in `transcripts/`. Matching cached word timings can be reused for the same unchanged source and transcription model.

## Offline use

Local videos can be processed offline once the chosen speech model is available. The EXE includes the small model; optional models require a first-time download. YouTube downloads require internet access.

**Stop** takes effect between processing operations. Model loading, a first-time model download, or another running operation may need time to return before cancellation takes effect. Completed shorts are retained.

## Build the Windows EXE

Complete the source setup first. If you installed only runtime requirements, add the build dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

The current build specification requires the FFmpeg binaries in `.tools/ffmpeg/bin/`. If you installed FFmpeg through WinGet, copy them from PATH:

```powershell
New-Item -ItemType Directory -Force .tools\ffmpeg\bin | Out-Null
Copy-Item -LiteralPath (Get-Command ffmpeg.exe).Source -Destination .tools\ffmpeg\bin\ffmpeg.exe
Copy-Item -LiteralPath (Get-Command ffprobe.exe).Source -Destination .tools\ffmpeg\bin\ffprobe.exe
```

Skip the copy step if those binaries are already in the project. Make sure Node.js is available on PATH and the face detection model is present in `assets/`.

Cache the default speech model, then build:

```powershell
.\.venv\Scripts\hf.exe download Systran/faster-whisper-small
.\build.ps1
```

The build creates:

```text
dist/
└── AI Short Maker/
    ├── AI Short Maker.exe
    ├── _internal/
    ├── README.md
    ├── THIRD-PARTY.md
    └── VALIDATION.md
```

Rebuild the EXE after changing application code or updating bundled dependencies.

## Transcript-only CLI

The original command-line workflow remains available for downloading and transcribing without creating shorts:

```powershell
# Prompt for a URL
.\.venv\Scripts\python.exe main.py

# Supply a URL directly
.\.venv\Scripts\python.exe main.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcribe a local recording
.\.venv\Scripts\python.exe main.py --file "C:\Videos\recording.mp4" --model small
```

This command saves a timestamped JSON transcript. Automatic full-video deletion applies to the desktop shorts workflow, not this transcript-only command.

## Project structure

| File or directory | Purpose |
| --- | --- |
| `desktop.py` | Desktop interface, background jobs, progress, and results. |
| `pipeline.py` | Coordinates processing, naming, verification, and cleanup. |
| `downloader.py` | Downloads videos and retrieves their titles. |
| `transcriber.py` | Whisper transcription, word timings, and GPU fallback. |
| `selector.py` | Scores transcript windows and selects clips. |
| `framing.py` | Face detection, camera smoothing, and zoom. |
| `captions.py` | Creates ASS captions. |
| `renderer.py` | Renders vertical clips with FFmpeg. |
| `runtime.py` | Resolves bundled tools, paths, and hardware capabilities. |
| `main.py` | Transcript-only CLI. |
| `assets/` | Face model, application icon, and third-party notices. |
| `tests/` | Automated behavior and rendering checks. |
| `ShortMaker.spec`, `build.ps1` | Windows application packaging. |

## Testing

Run the automated checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Check the desktop window:

```powershell
.\.venv\Scripts\python.exe desktop.py --ui-smoke
```

Run the GPU integration check with a local video longer than 215 seconds:

```powershell
.\.venv\Scripts\python.exe verify_desktop.py --source "C:\Videos\recording.mp4"
```

This checks a 75-second sample starting at 140 seconds. Use `--full` to process the entire source instead. The integration script expects working CUDA and NVENC; CPU rendering is covered by the automated tests. Without `--source`, it looks for the original development sample in `downloads/`, which may no longer exist after automatic cleanup.

Integration reports are written to `outputs/`. See [VALIDATION.md](VALIDATION.md) for the recorded build checks and sample performance results; processing time varies by hardware and video.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| FFmpeg or ffprobe is missing | Run `winget install --id=Gyan.FFmpeg -e`, reopen PowerShell, and check both commands. Alternatively, use `.tools/ffmpeg/bin/`. |
| YouTube download fails | Check the URL and network connection. Some videos require authentication or are unavailable. Update yt-dlp in the source environment and rebuild if using the EXE. |
| GPU processing falls back to CPU | Check the NVIDIA driver and the hardware panel. Open **Show activity** for the failure message. Try the small model if memory is limited. |
| First transcription takes longer | The source app or an optional model may be downloading weights. Subsequent runs reuse the model cache. |
| Fewer shorts than requested | The source may not contain enough usable, non-overlapping speech windows. Try a shorter target duration. |
| The app cannot delete a download | Close other programs using the file. The finished shorts are retained, and the app reports the cleanup problem. |
| The EXE fails after being moved | Move the complete application folder, including `_internal`, rather than the EXE alone. |

To update yt-dlp in the source environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"
```

The lock file records the nightly version used for the verified development run. Updating dependencies may change behavior; test and rebuild before distributing an updated app.

Detailed desktop errors are saved to `last-error.log` in the application data directory.

## Current limitations

- Clip selection uses local heuristics, not an LLM or a prediction of views or virality. English hook scoring is strongest.
- Face following favors a large face near the previous camera position. It does not identify the active speaker from audio.
- Fast cuts, occluded faces, group scenes, and speech-recognition errors can require manual editing.
- Clip durations are approximate, and subtitles should be reviewed before sharing.
- Windows is the tested desktop and packaging target.

## Third-party components

See [the third-party notices](assets/THIRD-PARTY.md) and [the YuNet license](assets/YUNET-LICENSE.txt) for component attribution and licensing references.

Core projects: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [OpenCV YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [PySide6](https://doc.qt.io/qtforpython-6/), and [FFmpeg](https://ffmpeg.org/).
