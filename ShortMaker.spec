# PyInstaller folder build: launch the EXE and keep _internal beside it.
from pathlib import Path
import sys
import shutil
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / 'assets'), 'assets'), (str(root / '.tools/ffmpeg/bin'), '.tools/ffmpeg/bin')]
binaries = []
hiddenimports = []
for package in ('faster_whisper', 'ctranslate2', 'tokenizers', 'onnxruntime', 'yt_dlp_ejs'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files('yt_dlp')
from huggingface_hub import snapshot_download
small = snapshot_download('Systran/faster-whisper-small', local_files_only=True, allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt'])
for name in ('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt'):
    path = Path(small) / name
    if path.exists():
        datas.append((str(path), 'models/small'))
for name in ('yt-dlp', 'yt-dlp-ejs', 'faster-whisper', 'huggingface-hub'):
    datas += copy_metadata(name)
for name in ('nvidia-cublas-cu12', 'nvidia-cudnn-cu12', 'nvidia-cuda-nvrtc-cu12', 'PySide6', 'opencv-python-headless'):
    datas += copy_metadata(name)
nvidia = Path(sys.prefix) / 'Lib/site-packages/nvidia'
for dll in nvidia.glob('*/bin/*.dll'):
    binaries.append((str(dll), str(Path('nvidia') / dll.parent.parent.name / 'bin')))
node = shutil.which('node')
if node:
    binaries.append((node, 'tools'))
a = Analysis(['desktop.py'], pathex=[str(root)], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['matplotlib', 'IPython', 'pytest', 'torch', 'tensorflow'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AI Short Maker', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(root / 'assets/app.ico') if (root / 'assets/app.ico').exists() else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AI Short Maker')
