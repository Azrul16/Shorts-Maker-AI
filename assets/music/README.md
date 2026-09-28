# Fixed energetic music library

50 distinct Kevin MacLeod instrumental tracks from incompetech.com, licensed under CC BY 4.0 with attribution. The application automatically rotates this pool for Football and challenge shorts. Metadata, source URLs, duration and SHA-256 hashes are recorded in catalog.json in the music directory.

These recordings are copyrighted and licensed for free reuse, not public domain. Keep the generated artist credit and license link in upload descriptions. The app trims to up to 90 seconds, loops, fades and mixes the excerpts under source audio; these edits are disclosed in the credit.

Artist licensing: https://incompetech.com/music/royalty-free/licenses/
License: https://creativecommons.org/licenses/by/4.0/

Rebuild with `.venv/Scripts/python.exe scripts/build_music_library.py`. The build uses only the fixed catalog. The selected artist metadata is retained in licensed/catalog-source.json.
