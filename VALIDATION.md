# Verified desktop build

Tested on this Windows computer with its NVIDIA GeForce RTX 3050 Laptop GPU
(4 GB VRAM), on 23 September 2026.

- 35 distinct automated checks cover download filename handling, invalid
  inputs, non-overlapping clip selection, captions, timestamp rounding,
  portrait/landscape crop bounds, moving-face tracking, zoom limits, CPU
  export with audio, and cancellation cleanup.
- The title-based output update adds checks for `shorts/<video title>/`,
  Windows-safe names, repeat-run collisions, deletion after verified exports,
  and preservation of originals after errors, cancellation, invalid exports,
  or local-file input.
- The framing/music update adds checks for separated-face preservation,
  missing-face scene preservation, word-aligned sentence splitting, editorial
  scoring, activity peaks and their lead-in, bundled tracks, speech ducking,
  and Unicode/emoji filenames during FFprobe verification.
- Source desktop window and packaged EXE both passed the UI launch check.
  A visual inspection confirmed the form and progress layout render correctly.
- A 75-second sample produced two 1080 × 1920 captioned shorts in 66.1 seconds.
- The full 19-minute video `v9QtM6qnG50` produced three shorts in 295.7 seconds.
  CUDA transcription and NVENC encoding were confirmed in the result manifest.
  Each export was probed for dimensions, duration, and an audio track.
- The final packaged EXE passed an additional engine check with Hugging Face
  offline mode, an empty model-cache location, no development Python path,
  and a working directory outside the project. It loaded the bundled small
  model on CUDA and rendered a five-second 1080 × 1920 clip through NVENC.
- Captions and framing were visually inspected in exported frames. Automated
  checks validate operation, not editorial quality or transcription accuracy.
- The rebuilt music-enabled EXE passed the offline CUDA/NVENC engine check
  with its bundled ambient track, and passed the UI launch check again.
- Football mode exported a 30-second real match sample with the beat track.
  The selected window was 07:03.625–07:33.625; a reviewed frame preserved the
  goal and surrounding players using the full-scene layout.
- Batch-count regression checks cover sparse movie dialogue, fragmented
  selections, short-source limits, and a full three-export silent-animation
  pipeline with music and YouTube copy files. Upload-copy checks cover title
  length, category hashtags, and excluding dialogue outside the clip.
- A real source-video batch requested three shorts and exported all three
  through NVENC with music and individual `.youtube.txt` files. Evidence:
  `outputs/count-verification.json`.

Local evidence:

- `outputs/desktop-verification.json`
- `outputs/desktop-verification/20260923-160159-357c33/`
- `outputs/packaged-check/verification.json`
- `outputs/packaged-check/desktop-preview.png`
- `outputs/football-preview.json`

The app folder is approximately 3.37 GiB because it includes Python/Qt,
NVIDIA runtime libraries, FFmpeg, Node.js, and the default speech model.
Keep `_internal` alongside `AI Short Maker.exe`. Optional transcription models
still require a first-time download. Clip ranking is heuristic and face tracking
does not perform audio-based active-speaker identification.
