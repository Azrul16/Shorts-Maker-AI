"""Rebuild the fixed 50-track energetic library from the artist's free license catalog."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import quote
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime import tool,NO_WINDOW
from projects import atomic_json
from music import first_beat
ROOT=Path(__file__).resolve().parents[1]
BASE='https://incompetech.com/music/royalty-free/'


def build():
    response=requests.get(BASE+'pieces.json',timeout=40)
    response.raise_for_status()
    pieces=response.json()
    folder=ROOT/'assets/music/licensed'
    folder.mkdir(parents=True,exist_ok=True)
    candidates=[]
    seen=set()
    for item in pieces:
        bpm=str(item.get('bpm',''))
        title=item['title'].strip()
        identity=re.sub(r'\s*\((?:faster|slower).*?\)','',title.lower())
        if identity in seen or not bpm.isdigit() or int(bpm)<100: continue
        if not re.search(r'aggressive|driving|intense|action',item.get('feel',''),re.I): continue
        if re.search(r'vocal',item.get('instruments',''),re.I) or 'waltz' in title.lower(): continue
        seen.add(identity)
        candidates.append(item)
        if len(candidates)==50: break
    if len(candidates)!=50: raise RuntimeError('Artist catalog does not contain 50 eligible tracks')

    def download(item):
        title=item['title'].strip()
        source=BASE+'mp3-royaltyfree/'+quote(item['filename'].strip())
        name=re.sub(r'[^a-zA-Z0-9_-]','_',title)+'-'+str(item.get('isrc') or item['uuid']).strip()+'.m4a'
        path=folder/name
        temporary=path.with_suffix('.download.m4a')
        try:
            if not path.exists():
                subprocess.run([tool('ffmpeg'),'-v','error','-y','-rw_timeout','20000000','-i',source,'-t','90','-vn','-c:a','aac','-b:a','128k',str(temporary)],capture_output=True,check=True,timeout=180,creationflags=NO_WINDOW)
                temporary.replace(path)
            result=subprocess.run([tool('ffprobe'),'-v','error','-show_entries','format=duration','-of','json',str(path)],capture_output=True,check=True,timeout=20,creationflags=NO_WINDOW)
            duration=float(json.loads(result.stdout)['format']['duration'])
            if duration<12: raise ValueError('Track is too short')
            return dict(file='licensed/'+name,title=title,artist='Kevin MacLeod',mood='energetic',bpm=item['bpm'],tags=item.get('feel',''),license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',source=source,duration=duration,onset=first_beat(str(path)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),editing='First 90 seconds (or full track when shorter), AAC encoded; excerpt mixed under original audio.')
        finally:
            temporary.unlink(missing_ok=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        tracks=[]
        for track in pool.map(download,candidates):
            tracks.append(track)
            print('Ready',len(tracks),track['title'].encode('ascii','replace').decode(),flush=True)
    atomic_json(folder/'catalog-source.json',candidates)
    atomic_json(ROOT/'assets/music/catalog.json',tracks)
    print('Fixed catalog saved: 50 tracks',flush=True)

if __name__=='__main__': build()
