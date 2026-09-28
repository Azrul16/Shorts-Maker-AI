# Licensed music library

Kevin MacLeod (incompetech.com), Creative Commons Attribution 4.0.
License: https://creativecommons.org/licenses/by/4.0/
Artist terms: https://incompetech.com/music/royalty-free/licenses/
Artist FAQ: https://incompetech.com/music/royalty-free/faq.html

Each entry in ../catalog.json records the composition title, source download URL,
license, mood, duration and SHA-256. catalog-source.json preserves the artist metadata.
The library builder downloads distinct compositions directly from the artist and
encodes up to the first 90 seconds as 128 kbps AAC. Excerpts may be looped, trimmed,
faded and mixed beneath the video's original soundtrack.

Required credit is automatically appended to each .youtube.txt description,
including manually selected bundled tracks. Keep that credit when posting.
CC BY allows commercial use and adaptations with attribution; these compositions
are copyrighted and licensed, not public domain. A license cannot guarantee
that an automated platform will never issue a mistaken claim.

Rebuild with: .venv/Scripts/python.exe scripts/build_music_library.py
