"""Look for exact Commons file labels, never manufacture a recording or approve listening.
No downloads or manifest changes; candidates require provenance and licensing review.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
audio=json.loads((ROOT/'hangul-audio-audit.json').read_text())
missing=[t['text'] for t in audio['targets'] if not t['recordingAvailable'] and any(g in t['groups'] for g in ['자음 이름','모음','글자판 음절'])]
titles=[f'File:Ko-{word}.{ext}' for word in missing for ext in ['ogg','oga']]
batches=[titles[i:i+50] for i in range(0,len(titles),50)]
def query(batch):
    url='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json','prop':'imageinfo','iiprop':'url|extmetadata','titles':'|'.join(batch)})
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'HangeulSwipjiAudioAudit/1.0 (source inventory)'})
        with urllib.request.urlopen(req,timeout=25) as response:data=json.load(response)
        if 'error' in data:return {'error':data['error'],'titles':batch}
        return {'pages':list(data['query']['pages'].values())}
    except Exception as error:return {'error':str(error),'titles':batch}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(query,batches))
pages=[p for r in results for p in r.get('pages',[])]
report={'queriedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Exact Ko-<target>.ogg/.oga filename inventory only; absence is not proof that no other recording exists','missingTargets':len(missing),'titlesQueried':len(titles),'responses':len(pages),'failedBatches':[r for r in results if 'error' in r],'candidates':[p for p in pages if p.get('imageinfo')],'notFoundTitles':sum('missing' in p for p in pages),'listeningApproved':False}
(ROOT/'audit/audio-source-search.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'targets':len(missing),'queries':len(titles),'failedBatches':len(report['failedBatches']),'candidates':[p['title'] for p in report['candidates']]},ensure_ascii=False))
