"""Own teaching implementation of the five user-approved design references, not copied lessons."""
from pathlib import Path
import hashlib
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1]
REFERENCES=['EDUCATION_MASTER_STANDARD.md','TEACHER_METHOD_GUIDE.md','ASSESSMENT_STANDARD.md','ONLINE_KOREAN_PROGRAM_REFERENCE.md','SOURCE_REGISTER.md']
VERSION='education-standards-20261027-implementation-v1'
RUBRIC={
 'listening':['0: 실연 후 핵심 정보 파악 못함','1: 반복·선택지 도움으로 일부 파악','2: 도움으로 핵심 정보 파악','3: 도움 없이 주요 조건 파악','4: 조건 변화·함의까지 듣고 확인'],
 'speaking':['0: 시도했으나 과제 전달 못함','1: 제시 표현 반복으로 일부 전달','2: 도움으로 목적·조건 전달','3: 독립적으로 과제를 수행하고 수정','4: 예기치 않은 조건에도 조정하여 수행'],
 'reading':['0: 읽은 뒤 필요한 정보 파악 못함','1: 표시된 단어로 일부 찾음','2: 도움으로 문장 근거를 연결','3: 독립적으로 핵심·근거를 구별','4: 추론과 주장의 한계를 근거로 검토'],
 'writing':['0: 시도했으나 목적 전달 못함','1: 문장 틀로 일부 내용 전달','2: 도움으로 필요한 내용 구성','3: 목적·독자에 맞게 독립적으로 구성','4: 조건·근거·예외를 조정하고 스스로 수정']}

@lru_cache(maxsize=1)
def references():
 return [dict(path='docs/education/'+name,sha256=hashlib.sha256((ROOT/'docs/education'/name).read_bytes()).hexdigest()) for name in REFERENCES]

def apply(unit,stage):
 a=unit['assessment'];task=unit.get('performanceTask',{}).get('instruction') or unit['activities']['roleplay']
 if isinstance(task,dict):task=str(task)
 first=unit['dialogue'][0];answer=a[0]['answer'];focus=unit['vocabulary'][0]['ko']
 student={
  'listening':f'본문을 보지 않고 교사가 읽는 원문을 듣고 답하세요: {a[0]["question"]} 읽기나 반복 도움을 받았다면 교사에게 알려 주세요.',
  'speaking':task,
  'reading':f'{a[-1]["question"]} 답을 뒷받침하는 문장과 다른 선택이 맞지 않는 이유를 설명하세요.',
  'writing':str(unit['homework'])}
 criteria=[dict(area=k,prompt=v,rubric=RUBRIC[k],assessedBy='teacher-observation',autoApproved=False) for k,v in student.items()]
 methods=dict(version=VERSION,audience='성인 글로벌 학습자; 학교 자료의 교수 원리를 연령·목적에 맞게 재구성',stage=stage,durationMinutes=unit['durationMinutes'],observableGoals=[task,'필요한 정보를 근거와 함께 설명하고 상대의 이해를 확인한다.','도움을 받은 수행과 독립 수행을 구분하여 다음 보충 목표를 정한다.'],materials=['이 단원의 독자 대화·읽기','상황·조건 카드','교사 관찰 기록지','수정 전후 글쓰기 용지'],flow=[
 {'phase':'도입','minutes':'0~4','teacher':f'{unit["title"]}의 실제 필요와 선수 표현을 확인한다.','learner':'목적과 어려운 상황을 자기 말로 말한다.'},
 {'phase':'시범/이해','minutes':'4~10','teacher':f'원문을 직접 읽고 발문: {a[0]["question"]}','learner':'본문을 보지 않고 듣고 필요한 정보를 확인한다.'},
 {'phase':'안내된 연습','minutes':'10~17','teacher':f'핵심 표현을 시범 보인다: {unit["grammar"][0]}','learner':'단서와 문장 틀로 대답한 뒤 도움을 줄여 다시 말한다.'},
 {'phase':'실제 상황 활용','minutes':'17~25','teacher':'역할을 교환하고 시간·목적·상대 조건 하나를 바꾼다.','learner':task},
 {'phase':'피드백/복습','minutes':'25~30','teacher':'네 기능 관찰·오류 유형·다음 보충 활동을 구분해 기록한다.','learner':'수정 이유를 말하고 새 짧은 과제로 재시도한다.'}],
 prompts=[{'teacherQuestion':item['question'],'expectedResponse':item['answer'],'evidence':item['evidence']} for item in a],
 anticipatedErrors=[{'example':item.get('choices',[])[(item.get('answerIndex',0)+1)%3] if item.get('choices') else '근거 없이 답만 선택함','response':'먼저 선택 이유를 묻고 다음 원문 근거와 비교하여 자기 수정을 유도: '+' / '.join(item['evidence'])} for item in a],
 pronunciationCorrection=f'{focus}를 포함한 실제 발화를 듣는다. 이해를 막는 소리·받침·끊어 읽기를 기록→교사 시범→학습자 재시도→새 문장 확인 순으로 교정한다. 지역/개인 발음 차이를 무조건 오류로 보지 않는다.',
 differentiation={'support':f'대화 시작 틀 {first}와 핵심어 카드를 제공하고 과제의 조건 수를 줄인다.','extension':'같은 정답을 반복시키지 않고 목적·독자·시간 조건 하나를 바꿔 이유와 대안을 말하게 한다.','ageAdaptation':'아동에게 적용하려면 정서·연령·생활 한국어/학습 한국어의 차이를 따로 검토한다. 이 성인 플랫폼 계정 정책을 자동으로 아동용으로 바꾸지 않는다.'},
 fourSkillAssessments=criteria,homework=unit['homework'],feedbackRecord=['관찰 영역','도움/반복 여부','성공한 행동','오류 유형과 구체 발화','교사 피드백','다음 차시 보충 목표'],sourceReferences=references(),limits=['실제 듣기·말하기·발음은 교사가 직접 관찰하며 자동 채점으로 승인하지 않는다.','공공 원문·문제·음원·그림을 복제하지 않는다.','외부 온라인 프로그램의 전 화면 검증 또는 원본 자료의 전수 검토를 완료했다는 뜻이 아니다.'])
 return student,methods
