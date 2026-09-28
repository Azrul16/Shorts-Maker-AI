# Challenge Video Studio

A Windows desktop production workflow for **MrBeast-style challenge videos**: download, transcribe, select stories, frame people, add animated captions and licensed music, and prepare upload copy. Independent software; not affiliated with MrBeast.

## Run

Open `dist/challenge-studio/AI Short Maker/AI Short Maker.exe`. Keep its entire folder together, including `_internal`.

1. Paste a video link or choose a local file.
2. Choose what to make:
   - **Reel:** automatic story length, never more than 120 seconds; vertical 9:16 framing; music volume defaults to 50% and ducks during speech.
   - **Summary video:** automatic 4-6 minute story; original picture format/composition; music defaults to 18% and captions adapt to the frame.
3. Set the maximum number of outputs. The app exports fewer if there is insufficient distinct material.
4. Click **Generate reels** or **Generate summary video**. Selection, captions, music and export run automatically.
5. Click **Open publishing desk** to watch your videos and copy titles/descriptions.

There is no fixed-length dropdown: the selected story determines the duration within the format limit. A source shorter than four minutes stays at its actual length with an explanatory notice. Longer sources without enough supported material for a four-minute summary are kept, and the app suggests making a reel. More options contains resolution, adjustable music volume, caption style, animation, exact reel timestamps and optional review. Review is off by default. Summary review shows source timestamps, story roles and retained dialogue, with checkboxes and draft saving. Individual clips retain the trim/crop preview. Summary review is a storyboard, not a live assembled-video preview.

## What the studio does

- **Story summaries:** analyse the full transcript, identify setup and outcome evidence, then join several sentence-aligned source sections in chronological order. Topic coverage, temporal diversity, repetition penalties and sponsor exclusions guide local scoring. Additional outputs require unused story evidence; the app never pads the count with arbitrary windows. Short sources that already fit the target retain their context.
- **Timeline assembly:** seek directly to retained video sections, join only their audio with tiny fades at cut edges, retime word captions and effects, and reset the camera at each cut. Music runs continuously across the assembled short. No intermediate full-resolution video is needed.
- **Reel framing:** full-screen 9:16 crop with persistent primary-person selection, nearby group composition, face detection and a bounded full-body fallback. Partial bystanders are downweighted. Shot changes can immediately reacquire the subject; motion within a shot stays smooth.
- **Summary framing:** preserves the original landscape, square or portrait composition and aspect ratio. It skips unnecessary face tracking for lower CPU use.
- **Editing:** bold reel captions use up to four words per group. Landscape/square captions use a proportional canvas with longer readable groups. An opening title uses the generated upload title. Eased punch-ins are timed to dialogue cues instead of a fixed repeating interval; no matching cue means no forced punch-in. Manual crop paths remain exact.
- **Music:** 50 licensed energetic instrumentals, selected using scene dialogue and artist tags for suspense, celebration, playful moments or driving action. Rotation avoids immediate repetition; indexed onsets avoid repeated analysis. Music ducks beneath speech and fades at clip boundaries.
- **Publishing:** automatic title, substantial description, exactly seven relevant hashtags for the selected format (#Reels or #FacebookVideo), required music credit, subtitles, thumbnail, technical checks, story-cue JSON, a batch CSV and an offline publishing page.

Selection is an English-dialogue heuristic, not a visual-language model or a guarantee of the best moments. It can miss silent actions, misunderstand story relationships, or select an incomplete explanation. Review summaries before posting. It preserves chronology but omits time between sections; `.edit.json` records source timestamps and evidence. If no supported setup/outcome is found, it keeps the source and suggests Reel or exact timestamps instead of inventing a story. Summary videos require 240-360 seconds when the source is at least four minutes long; reels use up to 120 seconds. Neither mode stretches footage or repeats it to pad duration. Fewer than the requested number may qualify.

Framing does not identify the actual speaker or guarantee the right subject in crowded scenes. This is an editing and delivery workflow, not an upload bot or a guarantee of audience reach.

## Local processing and online copy

Video/audio processing stays local. Whisper small uses CUDA when available; NVENC handles H.264 export with CPU fallback. Preview decoding runs on a worker and coalesces seeks. Processing is tuned for the i7-11800H, 8 GB RAM and RTX 3050 laptop; outputs are 30 fps. Reels are 1080x1920 or 720x1280; landscape summaries are up to 1920x1080 or 1280x720, with proportional dimensions for other source formats.

Groq receives only the source title and selected dialogue to write upload copy. The app reads `GROQ_API_KEY` from the process or Windows user environment; no API-key field or embedded key is included. The default model is `openai/gpt-oss-120b`, overridable with `GROQ_MODEL`. Offline copy is saved if the service is unavailable. MrBeast hashtags are only added when the supplied source identifies him.

## Output and music license

Exports are saved in `shorts/<video title>/`. Open `START-HERE.html` or `upload-index.csv` for the batch; each new video also has `.post.txt` (older exports used `.youtube.txt`), subtitles, a thumbnail, `.edit.json`, and quality reports. `project.json` records the job.

Downloaded originals are deleted only after all exports and the delivery package finish successfully. Local source files are kept. A saved draft needs its unchanged original to reopen.

The music pool uses Kevin MacLeod tracks under **CC BY 4.0 with attribution**. Keep the generated credits when posting. Sources, hashes and onset offsets are in `assets/music/catalog.json`. See [artist licensing](https://incompetech.com/music/royalty-free/licenses/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and [third-party notices](assets/THIRD-PARTY.md). No library can guarantee freedom from mistaken copyright claims.

## Install from source

Use 64-bit Python 3.14 on Windows. Install FFmpeg:

```powershell
winget install --id=Gyan.FFmpeg -e
```

Reopen PowerShell, install Node.js for supported YouTube extraction, then:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe desktop.py
```

OpenCV is pinned to 4.13.0.92 for the local person detector. First-use transcription may download the speech model. The portable build includes that model, FFmpeg and Node when available.

## Build and check

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
powershell -ExecutionPolicy Bypass -File .\build.ps1 -OutputDirectory dist/challenge-studio
```

The build expects FFmpeg in `.tools/ffmpeg/bin`, cached Whisper small and installed build requirements. It refuses to overwrite a running app. Use `requirements-build.txt` if build tools were not installed from the lock file.

Only rebuild the music library when needed: `.\.venv\Scripts\python.exe scripts/build_music_library.py`.

See [research and editorial decisions](docs/MRBEAST_RESEARCH.md) and [validation](VALIDATION.md).
