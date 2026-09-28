"""Local publishing desk: one index for the completed videos and their upload copy."""
import csv
import html
import io
from pathlib import Path
from urllib.parse import quote


def write_delivery(folder, manifest):
    folder = Path(folder)
    rows = []
    cards = []
    for item in manifest['clips']:
        video = Path(item['path']).name
        upload = item['youtube']
        rows.append([video,upload['title'],upload['description'],' '.join(upload['hashtags'])])
        escape = html.escape
        link = escape(quote(video))
        copy_link = escape(quote(Path(upload['file']).name))
        cards.append(f'<article><h2>{escape(upload["title"])}</h2>'
                     f'<video controls preload="none" src="{link}"></video>'
                     f'<p><a href="{link}" download>Video</a> &middot; <a href="{copy_link}">Upload text</a></p>'
                     f'<label>Title<textarea rows="2" readonly>{escape(upload["title"])}</textarea></label>'
                     f'<label>Description and credits<textarea rows="10" readonly>{escape(upload["description"])}</textarea></label></article>')
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['video','title','description','hashtags'])
    writer.writerows(rows)
    (folder/'upload-index.csv').write_text(stream.getvalue(),encoding='utf-8-sig',newline='')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Challenge Shorts - Publishing desk</title><style>'
            'body{font:16px system-ui;background:#101827;color:#eef3fa;margin:32px;max-width:1200px}'
            'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}'
            'article{background:#1b293d;padding:20px;border-radius:16px}h2{font-size:20px}'
            'video{width:100%;max-height:480px;background:#000}a{color:#72e1ce}'
            'textarea{box-sizing:border-box;width:100%;display:block;margin:8px 0 16px;background:#101827;color:#eef3fa;padding:12px;border:1px solid #526378}'
            '</style><h1>Your challenge shorts</h1><p>Watch each export, then copy its title and description. Keep the music credits.</p><main>'
            + ''.join(cards) + '</main></html>')
    (folder/'START-HERE.html').write_text(page,encoding='utf-8')
    return str(folder/'START-HERE.html')
