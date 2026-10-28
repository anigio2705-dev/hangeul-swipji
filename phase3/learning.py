"""Isolated educational records and published curriculum; no hosted DB or external calls."""
import json
import education_standards
from functools import lru_cache
from pathlib import Path
import time
import secrets
ROOT=Path(__file__).resolve().parent
SKILLS={'grammar','vocabulary','reading','interaction','pronunciation'}

@lru_cache(maxsize=2)
def _plan_version(stamp):
    return json.loads((ROOT/'curriculum-96.json').read_text())

def plan():
    return _plan_version((ROOT/'curriculum-96.json').stat().st_mtime_ns)

def decorate(unit):
    p=plan()
    meta=p['unitMapping'].get(unit['id'],{})
    student,methods=education_standards.apply(unit,meta.get('stage',1))
    return dict(unit,
                performanceAreas=student,
                teacherStandards=methods,
                _diagnostics={phase:diagnostic(unit['id'],phase) for phase in ('pre','post')},
                learningPath={k:v for k,v in meta.items() if k!='teacherNotes'},
                teacherNotes=meta.get('teacherNotes',{}),
                performanceRubric=dict(p['rubric'],**education_standards.RUBRIC))

def public_unit(unit,teacher=False):
    return {k:v for k,v in unit.items() if k!='_diagnostics' and (teacher or k not in ('teacherGuide','teacherNotes','teacherStandards'))}

def catalog():
    p=plan()
    return {k:p[k] for k in ('version','basis','scope','stages','limits')}

def diagnostic(uid,phase):
    p=plan()
    meta=p['unitMapping'].get(uid)
    if not meta:
        raise ValueError('\uc774 \ub2e8\uc6d0\uc5d0\ub294 \uc0c8 \uc9c4\ub2e8\uc774 \ub4f1\ub85d\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4')
    if phase=='pre':
        diag = p['preDiagnostics'].get(str(meta['stage']))
        if diag is None:
            raise ValueError('\uc9c4\ub2e8 \uad6c\ubd84\uc744 \ud655\uc778\ud558\uc138\uc694')
        return diag
    if phase=='post':
        diag = p['postDiagnostics'].get(uid)
        if diag is None:
            raise ValueError('\uc9c4\ub2e8 \uad6c\ubd84\uc744 \ud655\uc778\ud558\uc138\uc694')
        return diag
    raise ValueError('\uc9c4\ub2e8 \uad6c\ubd84\uc744 \ud655\uc778\ud558\uc138\uc694')

def safe_questions(qs):
    return [{k:v for k,v in q.items() if k!='answerIndex'} for q in qs]

def submit(db,uid,unit_id,phase,answers,booking_id=None,questions=None):
    qs=None
    try:
        qs=questions if questions is not None else diagnostic(unit_id,phase)
    except Exception as e:
        raise ValueError('\ubaa8\ub4e0 \uc9c4\ub2e8 \ubb38\ud56d\uc5d0 \uc751\ub2f5\ud558\uc138\uc694') from e
    if not isinstance(answers,list) or len(answers)!=len(qs):
        raise ValueError('\ubaa8\ub4e0 \uc9c4\ub2e8 \ubb38\ud56d\uc5d0 \uc751\ub2f5\ud558\uc138\uc694')
    if any(isinstance(a,bool) or not isinstance(a,int) or a<0 or a>=len(q.get('choices',[])) for a,q in zip(answers,qs)):
        raise ValueError('\uc120\ud0dd\uc9c0 \ubc88\ud638\ub97c \ud655\uc778\ud558\uc138\uc694')
    skills={}
    correct=0
    for a,q in zip(answers,qs):
        good=int(a==q.get('answerIndex'))
        correct+=good
        skill_key=q.get('skill')
        if skill_key not in SKILLS:
            skill_key='unknown'
        s=skills.setdefault(skill_key,{'earned':0,'possible':0})
        s['earned']+=good
        s['possible']+=1
    record=secrets.token_hex(16)
    db.execute('INSERT INTO learning_checks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (record,uid,unit_id,booking_id,phase,'text-check',correct,len(qs),json.dumps(skills),
                '\uc790\ub3d9 \ub0b4\uc6a9 \ud655\uc778 \u00b7 \uc2e4\uc81c \ubc1c\uc74c\u00b7\ub9d0\ud558\uae30 \ud3c9\uac00 \uc544\ub2d8',time.time(),uid))
    return dict(id=record,score=correct,maxScore=len(qs),skills=skills,answers=[q.get('answerIndex') for q in qs],kind='text-check',certified=False)

def save_placement(db,uid,groups):
    if not isinstance(groups,list) or len(groups)!=4 or any(isinstance(n,bool) or not isinstance(n,int) or not 0<=n<=5 for n in groups):
        raise ValueError('\ub124 \uc601\uc5ed\uc758 \uc815\ub2f5 \uc218\ub294 \uac01\uac01 0~5 \uc815\uc218\uc5ec\uc57c \ud569\ub2c8\ub2e4')
    score=sum(groups)
    stage=0 if score<=3 else 1 if score<=6 else 2 if score<=9 else 3 if score<=12 else 4 if score<=15 else 5 if score<=17 else 6
    db.execute('INSERT INTO learning_placements VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET stage=excluded.stage,groups_json=excluded.groups_json,source=excluded.source,created_at=excluded.created_at',
               (uid,stage,json.dumps(groups),'voluntary-browser-summary-unverified',time.time()))
    return dict(stage=stage,score=score,verified=False)

def teacher_rating(db,booking,actor,phase,ratings,note):
    if phase not in ('pre','post') or not isinstance(ratings,dict) or (not {'pronunciation','grammar','interaction'}.issubset(ratings) or set(ratings)-{'pronunciation','grammar','interaction','listening','speaking','reading','writing'}):
        raise ValueError('\uc218\ud589 \ud3c9\uac00 \uad6c\ubd84\uae30 \uc138 \uc601\uc5ed\uc774 \ud544\uc694\ud569\ub2c8\ub2e4')
    if any(isinstance(n,bool) or not isinstance(n,int) or not 0<=n<=4 for n in ratings.values()) or not isinstance(note,str) or not 10<=len(note.strip())<=5000:
        raise ValueError('\uac01 \uc601\uc5ed 0~4\uc810\uacfc 10\uc790 \uc774\uc0c1 \uad00\ucc30 \uadfc\uac70\uac00 \ud544\uc694\ud569\ub2c8\ub2e4')
    scores={k:dict(earned=v,possible=4) for k,v in ratings.items()}
    rid=secrets.token_hex(16)
    db.execute('INSERT INTO learning_checks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (rid,booking['learner_id'],booking['unit_id'],booking['id'],phase,'teacher-observation',sum(ratings.values()),4*len(ratings),json.dumps(scores),note.strip(),time.time(),actor))
    return dict(id=rid,score=sum(ratings.values()),maxScore=4*len(ratings),kind='teacher-observation',observedAreas=list(ratings),fourSkillsObserved={'listening','speaking','reading','writing'}.issubset(ratings),certified=False)

def summary(db,uid):
    p=plan()
    row=db.execute('SELECT * FROM learning_placements WHERE user_id=?',(uid,)).fetchone()
    placement=dict(row) if row else None
    if placement:
        try:
            placement['groups']=json.loads(placement.pop('groups_json'))
        except Exception:
            placement['groups']=[]
    records=[]
    for x in db.execute('SELECT * FROM learning_checks WHERE user_id=? ORDER BY created_at DESC,rowid DESC LIMIT 50',(uid,)):
        v=dict(x)
        try:
            v['skills']=json.loads(v.pop('skills_json'))
        except Exception:
            v['skills']={}
        records.append(v)
    latest={}
    observed={}
    text_checks={}
    for record in records:
        for skill,value in record['skills'].items():
            item=dict(value,kind=record['kind'],createdAt=record['created_at'])
            if skill not in latest:
                latest[skill]=item
            bucket=observed if record['kind']=='teacher-observation' else text_checks
            if skill not in bucket:
                bucket[skill]=item
    weak=sorted({s for bucket in (observed,text_checks) for s,v in bucket.items() if v['possible']>0 and v['earned']/v['possible']<.67})
    last=records[0]['unit_id'] if records else None
    stage=None
    if last:
        unit_meta=p['unitMapping'].get(last, {})
        stage=unit_meta.get('stage')
    if stage is None:
        if placement and placement.get('stage') is not None:
            fallback_stages=[1,1,2,3,3,4,4]
            index = placement['stage'] if isinstance(placement['stage'],int) and 0 <= placement['stage'] < len(fallback_stages) else 0
            stage=fallback_stages[index]
        else:
            stage=1
    candidates=[m for m in p['stages'] if m['id']==stage]
    if not candidates:
        candidates=[]
    else:
        candidates=candidates[0]['lessons']
    booked={r['unit_id'] for r in records if r.get('phase')=='post' and r.get('score')==r.get('max_score')}
    ready=[v for v in candidates if v.get('status')=='authored' and (v.get('unitId') not in booked or bool(weak))]
    if last and weak:
        ready.sort(key=lambda v:v.get('unitId')!=last)
    elif last:
        next_id=p['unitMapping'].get(last,{}).get('nextUnitId')
        ready.sort(key=lambda v:v.get('unitId')!=next_id)
    return dict(placement=placement,
                records=records,
                latestSkillChecks=latest,
                observedSkillChecks=observed,
                textCheckSkillChecks=text_checks,
                weakSkills=weak,
                recommendations=ready[:3],
                recommendationBasis='Internal advisory: latest task and available authored lessons; not certified placement.',
                productionDatabaseUsed=False)
