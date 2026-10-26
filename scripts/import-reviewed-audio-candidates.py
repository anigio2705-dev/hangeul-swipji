"""Import exact-label Commons sources from the reviewed acquisition inventory.
All imports remain HELD: attribution and decoding are not pronunciation approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
manifest_path=ROOT/'hangul-audio-manifest.json'
m=json.loads(manifest_path.read_text())
r=json.loads((ROOT/'audit/audio-source-search.json').read_text())
parser=argparse.ArgumentParser();parser.add_argument('--local-only',action='store_true');args=parser.parse_args()
imported=[];pending=[]
for page in r['candidates']:
    info=page['imageinfo'][0];meta=info['extmetadata'];word=page['title'].removeprefix('File:Ko-').rsplit('.',1)[0]
    if word in m['recordings']:continue
    plain=lambda key:re.sub('<[^>]+>','',meta.get(key,{}).get('value',''))
    assert plain('Artist')=='HappyMidnight' and plain('LicenseShortName')=='CC BY-SA 4.0'
    assert '한국어' in plain('ImageDescription')
    name='-'.join(format(ord(ch),'x') for ch in word)+'-20261027.mp3'
    file=ROOT/'assets/hangul-audio'/name
    if not file.exists():
        if args.local_only:
            pending.append({'text':word,'reason':'Download pending after HTTP 429; no network retry in local-only mode'})
            continue
        try:
            req=urllib.request.Request(info['url'],headers={'User-Agent':'HangeulSwipjiAudioAudit/1.0'})
            with tempfile.TemporaryDirectory() as tmp:
                source=Path(tmp)/'source.ogg'
                with urllib.request.urlopen(req,timeout=25) as response:source.write_bytes(response.read())
                subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-ac','1','-codec:a','libmp3lame','-q:a','3',str(file)],check=True)
        except Exception as error:
            pending.append({'text':word,'reason':str(error)})
            if getattr(error,'code',None)==429:break
            continue
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(file)],text=True))
    m['recordings'][word]={'kind':'human','src':'./assets/hangul-audio/'+name,'sourceTitle':page['title'],'sourceUrl':info['descriptionurl'],'author':plain('Artist'),'license':plain('LicenseShortName'),'licenseUrl':plain('LicenseUrl'),'duration':duration,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'change':'Converted complete source recording to mono MP3; no clipping, splicing, synthesis or listening approval.','labelStatus':'source-title-matched; listening-pending','review':'source metadata and decoding checked; teacher listening pending','disabled':True,'holdReason':'추가 확보한 사람 녹음 후보 · 교사 청취 검수 전','listeningReview':{'status':'pending'}}
    imported.append(word)
    checkpoint=manifest_path.with_suffix('.json.tmp');checkpoint.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');checkpoint.replace(manifest_path)
manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report={'imported':imported,'pending':pending,'allHeld':True,'listeningApproved':0};(ROOT/'audit/audio-acquisition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
