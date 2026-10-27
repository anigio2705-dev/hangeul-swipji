"""Compile 72 authored scenes into the shared delivery format; preserve original 24 source files."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'phase3'
rows=runpy.run_path(str(P/'authoring/remaining72.py'))['ROWS']
plan=json.loads((P/'curriculum-96.json').read_text())
slots={v['slot']:v for stage in plan['stages'] for v in stage['lessons']}
new=[]
for i,row in enumerate(rows):
    stage=int(row['slot'][1]);uid='HS4-'+row['slot'];title=slots[row['slot']]['title'];qs=[]
    for j,item in enumerate(row['checks']):
        question,correct,w1,w2,*evidence=item
        assert correct not in (w1,w2) and w1!=w2
        for e in evidence:assert e in row['reading']+' '+' '.join(row['dialogue']),(uid,e)
        pos=(i+j)%3;choices=[w1,w2];choices.insert(pos,correct)
        qs.append(dict(question=question,answer=correct,choices=choices,answerIndex=pos,skill=['reading','interaction','grammar'][j],sourceType='reading_dialogue',evidence=evidence,explanation='근거: '+' / '.join(evidence),scoringNote='제시한 본문·대화 범위의 내용 확인. 실제 말하기·발음 수행을 이 점수로 인증하지 않습니다.'))
    writing=f'{title}의 목적과 상대를 정하고, '+(['세 문장','다섯 문장','여섯~여덟 문장','여덟~열두 문장'][stage-1])+f'으로 상황·선택·이유를 쓰세요. {row["task"]} 실제 개인 정보 대신 가상 정보를 사용하세요.'
    guide=[f'0~4분 도입/진단: {title}와 관련된 경험·목적을 묻고 학습자의 현재 표현을 기록합니다.',f'4~10분 시범/이해: 독자 대화문을 교사가 직접 읽고 {qs[0]["question"]}를 묻습니다.',f'10~17분 안내된 연습: {row["grammar"]} 핵심어를 바꾸어 말하고 읽기에서 근거를 찾게 합니다.',f'17~25분 실제 활용: {row["task"]} 역할을 바꾸고 조건 하나를 달리하여 다시 수행합니다.',f'25~30분 피드백/복습: {qs[2]["question"]}로 내용과 근거를 확인한 뒤 네 기능의 관찰과 다음 보충 목표를 기록합니다.',f'발문 예: {qs[0]["question"]} / 예상 응답: {qs[0]["answer"]}',f'오류 예: {qs[1]["choices"][(qs[1]["answerIndex"]+1)%3]}라고 답하면 정답을 즉시 주기보다 근거 {qs[1]["evidence"][0]}를 다시 확인하게 합니다.',f'발음: {row["words"][0][0]}를 포함한 문장을 실제로 듣고 음절·받침·끊어 읽기에서 이해를 방해한 부분만 교정합니다. 자동 청취 승인하지 않습니다.',f'개별화: 도움이 필요하면 {row["dialogue"][1]}를 문장 틀로 주고, 익숙하면 {title}의 조건을 하나 바꿔 이유를 다시 설명하게 합니다.']
    u=dict(id=uid,title=title,level=['A1','A2','B1-B2','C1'][stage-1],version='independent-72-v1',durationMinutes=30,objectives=[row['task'],row['grammar']],objectivesEn=['Complete the scenario task using the stated conditions.','Explain a choice with evidence and respond to a partner.'],vocabulary=[dict(ko=k,en=v) for k,v in row['words']],grammar=[row['grammar']],reading=row['reading'],dialogue=row['dialogue'],learnerGuide=['목표와 이미 아는 표현을 확인한 뒤 대화와 읽기를 공부하세요.','도움을 받은 연습 뒤에는 역할을 바꾸고 자기 말로 수행하세요.','내용 확인과 실제 네 기능의 수행 평가는 서로 다른 기록입니다.'],learnerGuideEn=['Check the goal and prior knowledge before the dialogue and reading.','After guided practice, swap roles and complete the task in your own words.','Text-check scores and observed language performance are separate records.'],teacherGuide=guide,activities=dict(listening='본문을 보지 않은 상태에서 교사가 읽는 대화를 듣고 핵심 정보와 조건을 메모하세요. 자료를 보았다면 교사에게 알려 읽기 도움 여부를 기록합니다.',speaking=row['task'],reading='읽기에서 각 평가 답을 뒷받침하는 근거를 찾고 사실·추정·미확인을 구분하세요.' if stage>=3 else '읽기에서 사람·시간·장소·선택의 근거를 찾으세요.',writing=writing,roleplay=row['task']),performanceTask=dict(instruction=row['task'],successCriteria=['조건을 본문과 맞게 전달한다.','목표 표현으로 필요한 질문과 응답을 한다.','상대의 이해를 확인하고 수정한다.']),homework=writing,assessment=qs)
    new.append(u)
    slots[row['slot']].update(unitId=uid,status='authored')
    plan['unitMapping'][uid]=dict(stage=stage,slot=row['slot'],skills=['vocabulary','reading','grammar','interaction'],nextUnitId=None,teacherNotes=dict(pronunciation=guide[-2],errorDiagnosis=guide[-3]))
    plan['postDiagnostics'][uid]=[{k:a[k] for k in ('question','choices','answerIndex','skill')} for a in qs]
# A complete ordered path, not a quota or a fixed business duration.
ordered=[x for stage in plan['stages'] for x in stage['lessons']]
assert len(ordered)==96 and all(v['status']=='authored' for v in ordered)
for i,v in enumerate(ordered):plan['unitMapping'][v['unitId']]['nextUnitId']=ordered[i+1]['unitId'] if i<95 else None
plan['version']='four-stage-96-authored-v2';plan['scope']='96 authored independent professional lessons / no planned placeholders; internal difficulty, not certified CEFR/TOPIK alignment.'
plan['limits']=[x for x in plan['limits'] if not x.startswith('Planned lessons')]
plan['limits'].append('96 source lessons are authored; teacher content review, learner trials and real audio approval remain separate.')
(P/'content-remaining72.json').write_text(json.dumps(dict(version='independent-72-v1',sourcePolicy='Original scenes; public standards inform teaching methods, not copied text/audio/questions.',units=new),ensure_ascii=False,indent=2)+'\n')
(P/'curriculum-96.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print('Compiled',len(new),'new lessons;',len(ordered),'ready slots')
