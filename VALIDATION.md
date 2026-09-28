# Verified desktop build

Tested on this Windows computer with its NVIDIA GeForce RTX 3050 Laptop GPU
(4 GB VRAM), on 23 September 2026.

- 43 distinct automated checks cover download filename handling, invalid
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
- Optional Groq checks cover offline mode, response validation, secret-free fallback and preserved music credits. No live Groq request was made.

Local evidence:

- `outputs/desktop-verification.json`
- `outputs/desktop-verification/20260923-160159-357c33/`
- `outputs/packaged-check/verification.json`
- `outputs/packaged-check/desktop-preview.png`
- `outputs/football-preview.json`

The app folder is approximately 3.56 GiB because it includes Python/Qt,
NVIDIA runtime libraries, FFmpeg, Node.js, and the default speech model.
Keep `_internal` alongside `AI Short Maker.exe`. Optional transcription models
still require a first-time download. Clip ranking is heuristic and face tracking
does not perform audio-based active-speaker identification.

## Simplified interface and expanded music library

- 122 distinct audio assets: 120 licensed excerpts plus two original loops.
- Every asset decoded completely with FFmpeg without errors; hashes and metadata checked.
- Four mood groups have at least 30 tracks each; rotation avoids repeats within a mood cycle and across restarts.
- Tests cover rotation, cycle boundaries, corrupt history recovery, category matching and manual artist credit.
- Collapsed advanced settings, visible Generate button and advanced toggle checked in Qt.
- Dubbing controls, pipeline integration, renderer inputs and installers removed. The build explicitly includes only current assets and excludes the legacy voice resources.
- Bulk deletion of old development voice/model folders was blocked by automatic policy review. They remain unused on disk and are not packaged.
- Updated source engine passed CUDA transcription and a 1080x1920 NVENC export.
- Music mood matching is heuristic, not semantic scene understanding or beat-by-beat editing.

- Final rebuilt EXE passed the UI launch and offline CUDA/NVENC checks from outside the workspace. Evidence: `outputs/packaged-simple-check/verification.json` and `outputs/packaged-simple-ui/desktop-preview.png`.
- All 122 packaged track hashes verified; no dubbing assets or installer found in the distribution.
- A real automatic-music pipeline export selected Half Mystery, rendered with NVENC and preserved its required artist credit in the upload description. Evidence: `outputs/automatic-music-check/shorts/install-check-source/project.json`.

## Smooth camera and automatic publishing copy ? 25 September 2026

- 51 automated tests pass, including short face-detection dropouts, continuous fit/crop geometry, black-frame prevention, exposure flashes, small detector noise and 24/30/60 fps camera consistency.
- Camera motion uses a deadband, layout hysteresis, a one-second missed-detection hold, bounded pan/zoom acceleration, and subpixel affine rendering. No instantaneous fit/crop switch or face-box override remains.
- Offscreen UI check confirms no Groq key field or enable switch and automatic copy enabled for desktop jobs.
- Local environment and Windows user registry key lookup tested without copying credentials into project files.
- Live Groq check succeeded using the locally configured key and `openai/gpt-oss-120b`; the previous model returned HTTP 404 and was absent from the account's available models. Evidence: `outputs/groq-automatic-check.json`.
- Synthetic 20-second camera preview and motion trace: `outputs/smooth-camera/`. Includes pan, brief missed detections, sustained face loss and reacquisition.
- No generation system can guarantee editorial accuracy or audience reach. API failures retain offline copy with a visible warning.

- Final packaged EXE passed UI launch, CUDA transcription, 1080x1920 NVENC export and live Groq copy generation from outside the workspace. The child process had no GROQ_API_KEY environment variable, proving Windows user-key lookup works without a UI key field. Evidence: `outputs/packaged-smooth-check/verification.json`.

## Football crop and ball tracking ? 28 September 2026

- Desktop defaults to Football and exposes only Fill screen framing. Football always forces full-screen 9:16 cropping, even when an older configuration requested fit/smart mode.
- Local CPU ball tracking uses compact white/yellow pitch objects, motion compensation and multiple-frame confirmation; it is a heuristic, not a trained ball detector. The camera uses smooth pan with a steady 1.06x zoom, with no blurred full-scene fallback.
- 58 automated tests pass, including moving white/yellow balls, rejection of static pitch markings and isolated observations, non-pitch scenes, hold-on-loss, aspect ratios, and football pipeline routing.
- UI checks confirm Football default, Fill-only mode and disabled face controls while following the ball.
- A real 10-second match excerpt exported at 1080x1920 through NVENC with ball tracking and zero preserved/wide frames. Some visible-ball frames were tracked; the crowded shooting sequence was not continuously tracked. This is not an accuracy benchmark. Low-coverage warnings are shown for fewer than 65% confirmed frames.
- Preview: `outputs/ball-check/football-fullscreen.mp4`. Tracking snapshots: `outputs/ball-check/tracking-refined.jpg`.
- Source logos inside the crop remain; cropping does not establish reuse rights or prevent copyright claims.

- Final packaged EXE passed its UI launch check and exported a real match sample with ball tracking, fill framing, zero wide frames, 1080x1920 dimensions and NVENC encoding. CUDA transcription also ran. Evidence: `outputs/packaged-football-check/verification.json`.

## Competitive research and editing upgrade - 28 September 2026

- Reviewed published features from 14 representative products using official sources; see `docs/COMPETITIVE_RESEARCH.md`. No hands-on competitor benchmark or superiority claim.
- 67 automated tests pass, including deterministic manual crop paths, invalid keyframes, atomic drafts, source fingerprint validation, credential exclusion, caption corrections/SRT timing, technical export failures, commentary evidence, and resume without reanalysis.
- Real football review UI exercised caption edits, style selection, adding/removing crop points, save/load and accepting edits. Screenshot: `outputs/review-upgrade-preview.png`. Preview is silent and does not render captions/music.
- Saved draft exported through the real pipeline with manual crop points, bold captions, SRT, loudness normalization and NVIDIA NVENC at 720x1280. All technical checks passed; local original preserved. Evidence: `outputs/editing-check/shorts/Edited football/project.json`.
- Football ranking samples six pitch locations and uses commentary cues; these are ranking hints, not verified goal detection. Brief missing-ball predictions are bounded to 0.25 seconds, then framing holds. Tracking remains heuristic and needs visual review.
- Loudness uses FFmpeg dynamic loudnorm targets; no claim of independently measured exact integrated loudness.

- Rebuilt portable EXE passed UI launch and a real 1080x1920, 30 fps H.264/AAC export using CUDA transcription and NVENC encoding, manual crop keyframes, bold captions and normalization. All technical checks passed. Evidence: `outputs/packaged-editing-check/verification.json`.
