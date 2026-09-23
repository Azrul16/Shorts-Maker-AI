# Verified desktop build

Tested on this Windows computer with its NVIDIA GeForce RTX 3050 Laptop GPU
(4 GB VRAM), on 23 September 2026.

- 17 distinct automated checks cover download filename handling, invalid
  inputs, non-overlapping clip selection, captions, timestamp rounding,
  portrait/landscape crop bounds, moving-face tracking, zoom limits, CPU
  export with audio, and cancellation cleanup.
- The title-based output update adds checks for `shorts/<video title>/`,
  Windows-safe names, repeat-run collisions, deletion after verified exports,
  and preservation of originals after errors, cancellation, invalid exports,
  or local-file input.
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

Local evidence:

- `outputs/desktop-verification.json`
- `outputs/desktop-verification/20260923-160159-357c33/`
- `outputs/packaged-check/verification.json`
- `outputs/packaged-check/desktop-preview.png`

The app folder is approximately 3.37 GiB because it includes Python/Qt,
NVIDIA runtime libraries, FFmpeg, Node.js, and the default speech model.
Keep `_internal` alongside `AI Short Maker.exe`. Optional transcription models
still require a first-time download. Clip ranking is heuristic and face tracking
does not perform audio-based active-speaker identification.
