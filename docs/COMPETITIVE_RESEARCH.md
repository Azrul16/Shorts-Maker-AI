# Competitive research and implementation decisions

Reviewed 28 September 2026. This is a representative review of 14 major products,
not an exhaustive list of every application or a hands-on quality benchmark.
Sources are official product pages and documentation. Vendor performance,
accuracy, and virality claims are not treated as independently established facts.
No paid accounts, cloud video uploads, or subscriptions were purchased for this review.

| Product | Published strengths relevant to this project | What to learn from it |
| --- | --- | --- |
| [OpusClip](https://www.opus.pro/) | Multi-genre clipping, automatic reframing, manual tracking controls | Automation needs a correction workflow when tracking chooses the wrong subject. |
| [Klap](https://klap.app/tools/ai-clip-maker) | Clipping, reframing, transcript refinement and batch export | Review clip boundaries and transcript text before the expensive export. |
| [Captions](https://captions.ai/features/create-clips) | Clip generation, intelligent framing, editing and scoring | Deliver a complete editing workflow; do not confuse a score with demonstrated audience reach. |
| [CapCut Desktop](https://www.capcut.com/tools/desktop-ai-power) | Auto Reframe, captions, scene detection, keyframes and style controls | Offer precise framing and reusable caption styles without overloading the main screen. |
| [Descript](https://www.descript.com/) | Text-based editing, transcript correction, audio cleanup, clip creation | Correct dialogue in the app instead of forcing users to edit exported subtitle files. |
| [Vizard](https://vizard.ai/) | AI clipping, transcript and timeline editing, brand templates, team review | Make auto-selected clips editable and keep local draft state. |
| [Submagic](https://www.submagic.co/features/magic-clips) | Clip generation, caption styles, audio cleanup and metadata | Improve finishing: subtitles, audio balance and export sidecars. |
| [VEED](https://www.veed.io/tools/auto-video-editor/automatic-clip-maker) | Speech-driven clips, transcript editing and dynamic captions | Separate speech-driven editing from football, where important action may have no useful dialogue. |
| [Riverside](https://riverside.com/tools/ai-video-editor) | Text editing and social-ready Magic Clips | Keep a fast path for automatic export alongside optional human review. |
| [Adobe Premiere](https://helpx.adobe.com/premiere/desktop/add-video-effects/commonly-used-effects/add-auto-reframe-effect-to-a-sequence.html) | Auto Reframe motion presets and manual keyframe refinement | Fast sports motion needs correction points, not only a slower camera smoothing constant. |
| [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) | Professional editing, color, effects and audio tools | Provide measured export checks; do not claim parity with a full professional timeline editor. |
| [WSC Sports](https://wsc-sports.com/case/ligue-1-mcdonalds/) | Sports-specific automated highlights and multiple publishing formats | Combine football-specific evidence rather than treating loud audio as proof of a goal. |
| [Veo](https://www.veo.com/) | Sports recording and analysis ecosystem | Treat tracking as a sports-specific quality problem, not face detection with a new label. |
| [Pixellot](https://www.pixellot.tv/) | Automated sports production, streaming and analytics | Camera systems and sports infrastructure are a different category from editing arbitrary downloaded broadcasts. |

## Biggest gaps found in the previous build

1. A failed ball crop could only be accepted or the entire job rerun. There was no
   pre-export frame preview, editable crop path, or per-clip trim control.
2. Football selection primarily used audio peaks with two pitch samples. It did
   not include commentary evidence or broader scene coverage.
3. Caption text/style could not be corrected inside the app. There was no SRT export.
4. Export verification checked only height and approximate duration. It did not
   expose audio/video codec checks, aspect dimensions or a readable review report.
5. There was no resumable review draft. The stored transcript reference could
   point at a cache rather than an edited project transcript.
6. Missing-ball frames simply held the crop, even during very short occlusions.

## Changes selected for this release

- A local review workspace before export: scrubbing, silent source/crop preview,
  per-clip trim/title controls, checked clip selection and caption correction.
- Click-to-add crop keyframes, per-point zoom, point removal and smooth interpolation.
  Preview and final export share the same crop-path implementation.
- Versioned, atomic local drafts with source-change checks and no API credentials.
  Drafts can resume without repeating download, transcription or clip selection.
- Classic, Clean and Bold caption presets; editable ASS and SRT sidecars.
- Optional loudness balancing, targeting -16 LUFS and -1.5 dBTP with FFmpeg's
  dynamic [loudnorm filter](https://ffmpeg.org/ffmpeg-filters.html#loudnorm).
  Targets are processing settings, not a claim that every short attains exact measured loudness.
- Football ranking combines audio, six pitch samples and commentary cues. Cues
  remain evidence for review, not labels asserting that a goal or save occurred.
- Bounded prediction through brief ball occlusions, with observed and predicted
  frames kept separate. Correct time deltas are used when reacquiring a ball.
- Per-export quality reports, persistent edited transcripts, and atomic manifests.

## What is deliberately not claimed

This release is not proven better than every competitor. There was no controlled
comparison of their exported clips, tracking accuracy, editing time, or audience
retention. A local heuristic tracker is not equivalent to a trained sports vision
system. Manual correction improves control; it does not establish automatic
tracking superiority. A title or hashtag model cannot guarantee views.

The useful target is a focused local football workflow with understandable
failures, correctable crops, low friction, and verifiable exports. Generic video
generation, dubbing (previously removed at the user's request), cloud collaboration,
and automatic social posting are outside this release.

## Next evidence needed to claim superior quality

Use the same permission-cleared corpus across products: wide daylight matches,
night games, fast counterattacks, crowded penalty areas, replays, and close-ups.
Record ball visibility in the crop, incorrect-subject tracking, crop motion,
highlight relevance, caption accuracy, export time, memory usage, and human
correction time. Publish failures as well as wins. Do not substitute synthetic
unit-test success or observation counts for annotated real-football accuracy.
