# Validation

Story-summary release, 29 September 2026. Target hardware: i7-11800H, 8 GB RAM, RTX 3050 Laptop 4 GB.

## Automated checks

92 tests passed. `outputs/summary-tests.log` contains the local results (ignored by Git). Checks include:

- A generated red/green/blue source proves non-adjacent sections are joined in order, with the omitted middle scene absent. Frequency analysis verifies the corresponding 440 Hz / 880 Hz audio sections, and SRT timestamps verify caption retiming.
- End-to-end summary export verifies source-span provenance, output duration, selected-only publishing copy, local source preservation, and delivery files.
- Summary selection checks chronology, duration budget, setup/outcome coverage, sponsor filtering and refusal to pad counts. Draft validation checks reversed/overlapping/non-finite spans and accepts long source envelopes with short edited durations.
- Summary review saves and exports its timeline. Existing cancellation, CPU rendering, camera smoothing, preview responsiveness, music, caption, credential and publishing checks remain covered.

A saved 1,137-second transcript produced three summary plans (86.74, 88.80 and 85.02 seconds, using 6, 7 and 7 sections) in about 0.06 seconds. This measures selection on an existing transcript, not transcription or rendering speed. It is not a measured editorial-accuracy benchmark or a full export of that source.

## Limits

The story planner uses English dialogue cues and recurring vocabulary. It does not understand every visual event or reliably resolve all participants and narrative relationships. Summary review presents selected source dialogue and timestamps; it is not an assembled-video preview. Watch finished exports before posting. Technical checks verify media properties, not virality or editorial perfection.

The fixed library retains 50 licensed tracks and required attribution. Previously retired football code, obsolete music, build caches and historical documents remain outside the active project. API keys remain in the local environment and are excluded from project files and Git.

## Packaged verification

See `outputs/summary-package/` for the current frozen-build checks. The active build is `dist/challenge-studio/AI Short Maker/AI Short Maker.exe`; keep the entire folder together.

The frozen application passed launch, review-preview responsiveness, CUDA transcription and a two-section 3.4-second NVENC 1080x1920 H.264/AAC export with captions, animated text, licensed music and loudness normalization. Live Groq returned seven hashtags. Archive inspection confirmed the summary module is bundled and the retired ball tracker is absent. Source/output timestamps are checked separately so story events retain correct provenance after cuts.
