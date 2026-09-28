# AI Short Maker

A local Windows desktop application for turning long videos into captioned, vertical shorts. Paste a YouTube link or select a video from your computer, choose your settings, and generate clips with football ball tracking, full-screen cropping, and zoom.

The application runs transcription and video processing on your own computer. No paid API or cloud processing account is required.

## Features

The [competitive research](docs/COMPETITIVE_RESEARCH.md) compares the published features of 14 major products and explains this release's priorities. This app has not been benchmarked as superior to those products.

- **Review before export:** preview the source and vertical crop, trim clips, correct captions, choose a caption style, and add smooth crop points when automatic tracking needs correction. Uncheck review for automatic batch export.
- **Local edit drafts:** save your choices and resume with **Open draft**, without downloading, transcribing, or selecting moments again. Drafts reference the original video, which must still exist unchanged; completed downloads are deleted after verified export, so those drafts then require restoring the original.
- **Export checks:** each short includes a readable technical report checking dimensions, duration, codecs, frame rate, and audio. Tracking coverage and dark-frame warnings identify clips to review; they do not measure tracking accuracy.
- **Audio balancing and subtitle choices:** optional loudness normalization, three caption styles, and editable SRT plus ASS sidecars.
- **Desktop interface:** paste a link, select a local file, and manage export settings.
- **Automatic clip selection:** scores standalone speech with word-aligned boundaries, or finds audio activity peaks for sports/action footage. Exact start/end controls are available too.
- **Vertical reframing:** always fills the 9:16 frame in the desktop app. Football uses ball-aware tracking; other video types use face following.
- **Background music:** rotates 100+ local tracks by scene mood, or uses your own track, with adjustable volume, fades, and automatic reduction beneath the original audio.
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

The build includes Python, FFmpeg, Node.js, the default Whisper small model, and NVIDIA runtime libraries. You do not need to install those separately to use the packaged app. An NVIDIA graphics driver is still needed for GPU acceleration. The distribution includes several GB of runtime libraries and model files.

### Create your first shorts

1. Paste a YouTube URL or click **Choose file**.
2. Set the number of shorts and target length, then choose a **Video type** or leave **Auto detect**.
3. Click **Generate shorts** and follow the progress bars. Music, captions, full-screen cropping and GPU processing are enabled by default.
4. In review, check the clips you want, adjust their start/end times, and correct transcript text. Click the source preview to add a crop point at the current time; move to another time and add another point to animate the crop. Clear points to restore automatic tracking. The preview is silent; captions and music are applied during export.
5. Click **Export checked clips**, or **Save and close** to return later with **Open draft**. Review the finished video and its **Export checks** before uploading.
6. Click **Play short** to review an export, or **Open output folder** to see all files.

Open **More options** only when you want to change music, volume, framing, transcription, export quality, output folder, exact timestamps.

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
| Target length | Approximately 60, 90, or 120 seconds (default: 60); actual lengths follow speech boundaries. |
| Transcription model | Small for balanced processing, medium for potentially better accuracy with more time and memory, or base for a fast draft. |
| Export quality | 1080 × 1920 or 720 × 1280, at 30 FPS. |
| Follow ball / faces | Football follows confirmed ball positions. Other video types follow faces with smooth camera motion. |
| Auto zoom | Football uses a steady 1.06x zoom; other video types use subtle face-aware zoom up to 1.12x. |
| Word captions | Adds highlighted captions to the exported video and saves an ASS subtitle file. |
| Use NVIDIA GPU | Attempts CUDA transcription and NVENC encoding; falls back to CPU if necessary. |
| Framing | Fill screen: a 9:16 crop with no blurred full-scene fallback. Football always uses this mode. |
| Background music | Auto scene matching (default), 100+ bundled tracks, No added music, or a custom audio file. |
| Music volume | 0–50%, default 18%. Music fades at both ends and lowers when the original audio is active. |
| Video type | Football is the default. Auto recognizes sports-related words in the video title; Speech / stories scores transcript windows; Sports / action selects audio activity peaks; Football also checks for pitch views in the lead-up. |
| Choose exact moment | Produces one clip using your start/end timestamps in seconds. Overrides automatic selection and clip count. |

Downloads are capped at 1080p. Exporting a low-resolution video at a higher resolution does not restore missing detail.

## How processing works

```text
YouTube URL or local video
    -> Download / inspect video
    -> Transcribe speech with word timestamps
    -> Select speech windows or audio activity peaks (or your exact timestamps)
    -> Follow faces and reframe to 9:16
    -> Add captions, mix background music, and encode MP4 files
    -> Verify exports
    -> Remove the downloaded full video
```

The GPU handles Whisper inference through CUDA and H.264 encoding through NVENC. The CPU handles video decoding, face detection, camera movement, resizing, and caption composition. Model memory is released before rendering.

The hardware panel shows detected CUDA availability and the result of an actual NVENC encoder check. Activity messages report processing and fallback behavior. CPU and GPU utilization varies by stage; both do not need to be fully utilized at all times.

### Choosing a selection and framing mode

For interviews and explanations, use **Speech / stories**. The selector penalizes context-dependent openings, generic greetings, promotional text, and incomplete endings, while favoring hooks and reactions. It also reduces repetitive selections.

For football highlights, **Football** is selected by default. It selects candidate moments from audio activity and pitch checks, then renders a full-screen 9:16 crop following confirmed ball positions. The tracker looks for compact white/yellow moving objects on the pitch across multiple frames. It is a local visual heuristic, not goal recognition or a trained ball detector. Small, blurred, airborne or occluded balls can be missed, and false detections remain possible. When uncertain, the camera holds the last reliable crop instead of switching to a wide view. Clips with limited tracking observations show a review warning. Use **Sports / action** or another video type for non-football footage.

**Choose exact moment** provides precise control when an automatic candidate misses the moment you want. Enter times in seconds, for example start `90` and end `125` for 01:30–02:05.

### Background music

Added music is enabled by default for every exported short. Auto mode rotates through a library of 100+ tracks matched by mood; required credits are included in the upload description. **Choose music...** lets you use your own WAV, MP3, M4A, AAC, OGG, or FLAC file. Short tracks loop to cover the export.

The original audio remains present. Music fades in/out and is ducked beneath the original audio using FFmpeg's sidechain compression. Lower the volume or select **No added music** when the original video already has a strong soundtrack. Ducking responds to the whole foreground audio track rather than isolating speech.

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
| `activity.py` | Finds audio activity peaks for sports/action clips. |
| `music.py`, `make_music.py` | Selects/mixes music and generates the included instrumental tracks. |
| `framing.py` | Face detection, camera smoothing, and zoom. |
| `ball_tracking.py` | Football ball observations, temporal confirmation and full-screen camera movement. |
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
| Fewer shorts than requested | Turn off **Choose exact moment (one short)**. Automatic mode fills missing speech selections with distinct scenes. Very short sources are limited to one clip per 12 seconds (or the target duration if shorter); the results explain any reduction. |
| The app cannot delete a download | Close other programs using the file. The finished shorts are retained, and the app reports the cleanup problem. |
| The EXE fails after being moved | Move the complete application folder, including `_internal`, rather than the EXE alone. |

To update yt-dlp in the source environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"
```

The lock file records the nightly version used for the verified development run. Updating dependencies may change behavior; test and rebuild before distributing an updated app.

Detailed desktop errors are saved to `last-error.log` in the application data directory.

## Current limitations

- Clip selection uses local heuristics, not an LLM or a prediction of views or virality. English hook scoring is strongest; audio activity selection is language-independent but does not understand visual events.
- Face following favors a large face near the previous camera position. It does not identify the active speaker from audio.
- Fast cuts, occluded faces, group scenes, and speech-recognition errors can require manual editing.
- Clip durations are approximate, and subtitles should be reviewed before sharing.
- Windows is the tested desktop and packaging target.

## Third-party components

See [the third-party notices](assets/THIRD-PARTY.md) and [the YuNet license](assets/YUNET-LICENSE.txt) for component attribution and licensing references.

Core projects: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [OpenCV YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [PySide6](https://doc.qt.io/qtforpython-6/), and [FFmpeg](https://ffmpeg.org/).

Built-in music details: [assets/music/README.md](assets/music/README.md).


## Batch counts and YouTube upload copy

Choose **Shorts** for the desired number and turn off **Choose exact moment**.
Automatic selection fills missing slots with non-overlapping activity windows,
then distinct scene windows if needed. It may shorten clips or repartition the
source to achieve the count. Fallback scenes are marked in `project.json`;
meeting a count does not guarantee that every scene contains a complete story.

Use **Football** for football, **Sports / action** for other action clips,
**Movies** for movie dialogue, and **Animation** for animated content.
Movie and animation modes rank dialogue first and fill remaining slots with
activity or distinct scenes. Silent animation skips transcription and can still
export with background music. Full-screen cropping remains active when face tracking
cannot safely fill the portrait frame; animated character tracking is not guaranteed.

Every export includes a matching `.youtube.txt` file with a suggested title,
description, and relevant category hashtags. Click **YouTube caption** beside a
finished short to open it. Suggestions use the source title and actual transcript;
review names, speech recognition and context before publishing. They are local
templates, not predictions or guarantees of reach. For specific player, character,
or film hashtags, add the verified names rather than unrelated trending tags.

Exports use 9:16 H.264 MP4, AAC audio, and fast-start playback. Manual moments are
limited to 180 seconds. YouTube accepts square or vertical Shorts up to three
minutes: [YouTube Shorts requirements](https://support.google.com/youtube/answer/15424877?hl=en).

## Automatic background music

**Auto: match scene mood** is the default. It uses category, dialogue keywords
and visual activity to choose an energetic, playful, dramatic or calm track,
then starts near a detected music onset. This is a mood heuristic, not semantic
scene understanding or beat-by-beat video editing. Volume ducking and fades remain
active. You can still choose a track manually or turn added music off.

The bundle includes 100+ distinct tracks, including licensed Kevin MacLeod compositions
and original loops. Licensed tracks are up to 90-second excerpts from the artist,
under CC BY 4.0. Matching tracks rotate without repetition until that mood pool
has been used, including across app restarts. Both automatic and manual bundled
track selection add required attribution to the `.youtube.txt` description. Keep it
when posting. See `assets/music/licensed/README.md` for sources and terms.

The app does not scrape arbitrary "no copyright" YouTube uploads. YouTube's
official Audio Library is available through YouTube Studio; download a track
there, then use **Choose music** to import it. Add any required library credit
to your upload description. An upload from an unrelated channel is not proof
of reuse rights, and no library can rule out every mistaken automated claim.

## Automatic titles, descriptions and hashtags

Desktop exports automatically request a specific title, description and relevant
hashtags from Groq. There is no API-key field or enable switch in the interface.
The app reads `GROQ_API_KEY` from the process environment or the Windows user
environment, including when Explorer or the IDE has an older environment.
The key remains on your PC; it is never embedded in source, the EXE, or exports.
A copied application uses the destination PC's configuration.

Only the source title, content category and selected dialogue are sent to Groq.
Video and audio stay local. The default model is `openai/gpt-oss-120b`;
`GROQ_MODEL` can override it. Internet access and a valid account are required
for AI copy. If the service fails, the app saves local suggestions and shows a
warning. Music attribution is appended locally and must stay in your upload.
Titles and hashtags cannot guarantee reach. Review names, claims and scene
context before posting; text generation does not inspect the video itself.

## Full-screen football framing

The desktop app always crops to fill the Shorts frame. Football mode follows
confirmed ball locations with eased panning, a small amount of lead space and
a steady 1.06x zoom. It does not follow faces or switch to a blurred wide view.
Brief misses hold the camera target; uncertain detections cannot instantly
jump the camera. Tracking statistics and low-coverage warnings are saved in
`project.json` and shown beside completed clips.

Other video types retain smooth face-following fill crops. The underlying
Python API still supports explicit smart/fit modes for non-football workflows;
those modes are not offered by the desktop interface.

Cropping does not grant reuse rights or prevent copyright claims. Logos that
remain inside the crop are not specifically removed. Review the composition
and use footage you have permission to publish.

## Simple desktop workflow

Paste a link or choose a file, set the number and length of shorts, choose the video type (or Auto detect), and click **Generate shorts**. Automatic music, captions, full-screen cropping and GPU processing are enabled by default.

**More options** contains the complete music library, music volume/off switch, custom music import, framing, export quality, exact timestamps and output folder. Sports and challenge videos favor energetic music, animation favors playful music, movies favor dramatic music, and sad dialogue favors calm music. These are local heuristics; review the result before posting.
