"""Build 100 distinct licensed 90-second music excerpts from the artist catalog."""
from pathlib import Path
import concurrent.futures, hashlib, json, re, subprocess, sys
from urllib.parse import quote
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime import tool, NO_WINDOW
ROOT=Path(__file__).resolve().parents[1]
BASE='https://incompetech.com/music/royalty-free/'

def build():
    response=requests.get(BASE+'pieces.json',timeout=40);response.raise_for_status()
    pieces=response.json()
    (ROOT/'assets/music/licensed/catalog-source.json').write_text(json.dumps(pieces,indent=2),encoding='utf8')
    groups={'energetic':r'aggressive|driving|intense|action', 'playful':r'bouncy|humorous|bright|uplifting', 'dramatic':r'suspenseful|dark|eerie|epic', 'calm':r'calming|relaxed|somber|peaceful'}
    used=set(); jobs=[]
    for mood,pattern in groups.items():
        chosen=[]
        for p in pieces:
            name=(p.get('filename') or '').strip()
            if name in used or not name or not re.search(pattern,p.get('feel',''),re.I):continue
            if 'vocal' in p.get('instruments','').lower():continue
            used.add(name);chosen.append((p,mood))
            if len(chosen)==30:break
        jobs.extend(chosen)
    def download(job):
        p,mood=job;source=BASE+'mp3-royaltyfree/'+quote(p['filename'].strip())
        name=re.sub(r'[^a-zA-Z0-9_-]','_',p['title'].strip())+'-'+str(p['uuid']).strip()+'.m4a'
        dest=ROOT/'assets/music/licensed'/name
        try:
            if not dest.exists():
                subprocess.run([tool('ffmpeg'),'-hide_banner','-loglevel','error','-y','-rw_timeout','20000000','-i',source,'-t','90','-vn','-c:a','aac','-b:a','128k',str(dest)],capture_output=True,check=True,timeout=150,creationflags=NO_WINDOW)
            r=subprocess.run([tool('ffprobe'),'-v','error','-show_entries','format=duration','-of','json',str(dest)],capture_output=True,check=True,timeout=15,creationflags=NO_WINDOW)
            duration=float(json.loads(r.stdout)['format']['duration'])
            if duration<12:raise ValueError('too short')
            return dict(file='licensed/'+name,title=p['title'].strip(),artist='Kevin MacLeod',mood=mood,bpm=p.get('bpm'),tags=p.get('feel',''),license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',source=source,duration=duration,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),editing='First 90 seconds (or full track when shorter), AAC encoded; excerpt mixed under original audio.')
        except Exception as e:
            dest.unlink(missing_ok=True);print('FAILED',p['title'].strip().encode('ascii','replace').decode(),type(e).__name__,flush=True)
    tracks=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for track in pool.map(download,jobs):
            if track:tracks.append(track);print('Ready',len(tracks),track['title'].encode('ascii','replace').decode(),flush=True)
    if len(tracks)<100:raise RuntimeError(f'Only {len(tracks)} downloaded; catalog unchanged')
    originals=[t for t in json.loads((ROOT/'assets/music/catalog.json').read_text()) if t['artist']=='AI Short Maker']
    (ROOT/'assets/music/catalog.json').write_text(json.dumps(tracks+originals,indent=2,ensure_ascii=False),encoding='utf8')
    print('Catalog saved:',len(tracks+originals),flush=True)
if __name__=='__main__':build()
