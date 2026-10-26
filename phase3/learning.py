"""Isolated educational records and published curriculum; no hosted DB or external calls."""
import json
from functools import lru_cache
from pathlib import Path
import time
import secrets
ROOT=Path(__file__).resolve().parent
SKILLS={'grammar','vocabulary','reading','interaction','pronunciation'}

@lru_cache(maxsize=2)
def _plan_version(stamp):return json.loads((ROOT/'curriculum-96.json').read_text())
def plan():return _plan_version((ROOT/'curriculum-96.json').stat().st_mtime_ns)
def decorate(unit):
    p=plan();meta=p['unitMapping'].get(unit['id'],{})
    return dict(unit,_diagnostics={phase:diagnostic(unit['id'],phase) for phase in ('pre','post')},learningPath={k:v for k,v in meta.items() if k!='teacherNotes'},teacherNotes=meta.get('teacherNotes',{}),performanceRubric=p['rubric'])
def public_unit(unit,teacher=False):
    return {k:v for k,v in unit.items() if k!='_diagnostics' and (teacher or k not in ('teacherGuide','teacherNotes'))}
def catalog():
    p=plan();return {k:p[k] for k in ('version','basis','scope','stages','limits')}
def diagnostic(uid,phase):
    p=plan();meta=p['unitMapping'].get(uid)
    if not meta:raise ValueError('이 단원에는 새 진단이 등록되지 않았습니다')
    if phase=='pre':return p['preDiagnostics'][str(meta['stage'])]
    if phase=='post':return p['postDiagnostics'][uid]
    raise ValueError('진단 구분을 확인하세요')
def safe_questions(qs):return [{k:v for k,v in q.items() if k!='answerIndex'} for q in qs]
def submit(db,uid,unit_id,phase,answers,booking_id=None,questions=None):
    qs=questions if questions is not None else diagnostic(unit_id,phase)
    if not isinstance(answers,list) or len(answers)!=len(qs):raise ValueError('모든 진단 문항에 응답하세요')
    if any(isinstance(a,bool) or not isinstance(a,int) or a<0 or a>=len(q['choices']) for a,q in zip(answers,qs)):raise ValueError('선택지 번호를 확인하세요')
    skills={};correct=0
    for a,q in zip(answers,qs):
        good=int(a==q['answerIndex']);correct+=good
        s=skills.setdefault(q['skill'],{'earned':0,'possible':0});s['earned']+=good;s['possible']+=1
    record=secrets.token_hex(16)
    db.execute('INSERT INTO learning_checks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(record,uid,unit_id,booking_id,phase,'text-check',correct,len(qs),json.dumps(skills),'자동 내용 확인 · 실제 발음·말하기 평가 아님',time.time(),uid))
    return dict(id=record,score=correct,maxScore=len(qs),skills=skills,answers=[q['answerIndex'] for q in qs],kind='text-check',certified=False)
def save_placement(db,uid,groups):
    if not isinstance(groups,list) or len(groups)!=4 or any(isinstance(n,bool) or not isinstance(n,int) or not 0<=n<=5 for n in groups):raise ValueError('네 영역의 정답 수는 각각 0~5 정수여야 합니다')
    score=sum(groups);stage=0 if score<=3 else 1 if score<=6 else 2 if score<=9 else 3 if score<=12 else 4 if score<=15 else 5 if score<=17 else 6
    db.execute('INSERT INTO learning_placements VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET stage=excluded.stage,groups_json=excluded.groups_json,source=excluded.source,created_at=excluded.created_at',(uid,stage,json.dumps(groups),'voluntary-browser-summary-unverified',time.time()))
    return dict(stage=stage,score=score,verified=False)
def teacher_rating(db,booking,actor,phase,ratings,note):
    if phase not in ('pre','post') or not isinstance(ratings,dict) or set(ratings)!= {'pronunciation','grammar','interaction'}:raise ValueError('수행 평가 구분과 세 영역이 필요합니다')
    if any(isinstance(n,bool) or not isinstance(n,int) or not 0<=n<=4 for n in ratings.values()) or not isinstance(note,str) or not 10<=len(note.strip())<=5000:raise ValueError('각 영역 0~4점과 10자 이상 관찰 근거가 필요합니다')
    scores={k:dict(earned=v,possible=4) for k,v in ratings.items()};rid=secrets.token_hex(16)
    db.execute('INSERT INTO learning_checks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,booking['learner_id'],booking['unit_id'],booking['id'],phase,'teacher-observation',sum(ratings.values()),12,json.dumps(scores),note.strip(),time.time(),actor))
    return dict(id=rid,score=sum(ratings.values()),maxScore=12,kind='teacher-observation',certified=False)
def summary(db,uid):
    p=plan();row=db.execute('SELECT * FROM learning_placements WHERE user_id=?',(uid,)).fetchone()
    placement=dict(row) if row else None
    if placement:placement['groups']=json.loads(placement.pop('groups_json'))
    records=[]
    for x in db.execute('SELECT * FROM learning_checks WHERE user_id=? ORDER BY created_at DESC,rowid DESC LIMIT 50',(uid,)):
        v=dict(x);v['skills']=json.loads(v.pop('skills_json'));records.append(v)
    latest={}
    for record in records:
        for skill,value in record['skills'].items():
            if skill not in latest:latest[skill]=dict(value,kind=record['kind'],createdAt=record['created_at'])
    weak=[s for s,v in latest.items() if v['earned']/v['possible']<.67]
    last=records[0]['unit_id'] if records else None
    stage=p['unitMapping'].get(last,{}).get('stage') or ([1,1,2,3,3,4,4][placement['stage']] if placement else 1)
    candidates=[m for m in p['stages'] if m['id']==stage][0]['lessons']
    booked={r['unit_id'] for r in records if r['phase']=='post' and r['score']==r['max_score']}
    ready=[v for v in candidates if v['status']=='authored' and (v['unitId'] not in booked or weak)]
    if last and weak:ready.sort(key=lambda v:v['unitId']!=last)
    elif last:
        next_id=p['unitMapping'].get(last,{}).get('nextUnitId');ready.sort(key=lambda v:v['unitId']!=next_id)
    return dict(placement=placement,records=records,latestSkillChecks=latest,weakSkills=weak,recommendations=ready[:3],recommendationBasis='Internal advisory: latest task and available authored lessons; not certified placement.',productionDatabaseUsed=False)
