"""Reproducible source, duplication, internal difficulty and preservation gates."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,sys,itertools,statistics
R=Path(__file__).resolve().parents[1];P=R/'phase3'
base='7418e325f0833604249e5170c2531a103b31ff1c';errors=[]
def check(v,msg):
 if not v:errors.append(msg)
units=[]
for f in ('content.json','content-expansion.json','content-remaining72.json'):units+=json.loads((P/f).read_text())['units']
plan=json.loads((P/'curriculum-96.json').read_text());slots=[x for s in plan['stages'] for x in s['lessons']]
check(len(units)==96 and len(slots)==96,'96 count');check(len(set(x['id'] for x in units))==96,'unique IDs');check(all(x['status']=='authored' for x in slots),'unbuilt slot')
check(len(set(x['reading'] for x in units))==96,'duplicate reading');check(sum(len(x['assessment']) for x in units)==288,'288 checks')
check(set(x['unitId'] for x in slots)==set(u['id'] for u in units),'slot/unit mismatch')
questions=[]
for u in units:
 for key in ('objectives','vocabulary','grammar','reading','dialogue','teacherGuide','activities','performanceTask','homework','assessment'):
  check(bool(u.get(key)),u['id']+': missing '+key)
 for a in u['assessment']:
  source=u['reading']+' '+' '.join(u['dialogue']) if a.get('sourceType')=='reading_dialogue' else u.get(a.get('sourceType'),'')
  if isinstance(source,list):source=' '.join(source)
  if isinstance(source,dict):source=' '.join(map(str,source.values()))
  for quote in a['evidence']:check(quote in source,u['id']+': evidence missing')
  questions.append(a['question'])
  if a.get('choices'):
   check(len(set(a['choices']))==3,u['id']+': duplicate choices');check(a['choices'][a['answerIndex']]==a['answer'],u['id']+': wrong key')
 for phase in ('pre','post'):
  qs=plan['preDiagnostics'][str(plan['unitMapping'][u['id']]['stage'])] if phase=='pre' else plan['postDiagnostics'][u['id']]
  check(len(qs)==3,u['id']+': diagnostic size')
  for a in qs:check(0<=a['answerIndex']<len(a['choices']),u['id']+': diagnostic key')
original=['intro.html','beginner1.html','beginner2.html','intermediate1.html','intermediate2.html','advanced1.html','advanced2.html','reading.html','reading-curriculum.js','reading-alternates.js','hangul-audio-manifest.json','index.html','phase3/content.json','phase3/content-expansion.json']
preserved={}
for f in original:
 old=subprocess.check_output(['git','show',base+':'+f],cwd=R);actual=(R/f).read_bytes();preserved[f]=hashlib.sha256(actual).hexdigest();check(old==actual,'original modified: '+f)
def grams(text):
 w=text.split();return set(tuple(w[i:i+3]) for i in range(len(w)-2))
features={u['id']:grams(u['reading']) for u in units};pairs=[]
for a,b in itertools.combinations(units,2):
 x,y=features[a['id']],features[b['id']];score=len(x&y)/len(x|y) if x|y else 1
 pairs.append((score,a['id'],b['id']))
pairs.sort(reverse=True);check(pairs[0][0]<.65,'near-duplicate passage threshold')
stages=[]
for i in range(1,5):
 us=[u for u in units if plan['unitMapping'][u['id']]['stage']==i];counts=[len(u['reading'].split()) for u in us];words=[word for u in us for word in u['reading'].split()]
 stages.append(dict(stage=i,count=len(us),minEojeol=min(counts),meanEojeol=round(statistics.mean(counts),2),maxEojeol=max(counts),uniqueSurfaceForms=len(set(words)),longestSentenceEojeol=max(len(s.split()) for u in us for s in re.split(r'[.!?]',u['reading']))))
check([x['meanEojeol'] for x in stages]==sorted(x['meanEojeol'] for x in stages),'mean length progression')
check([x['uniqueSurfaceForms'] for x in stages]==sorted(x['uniqueSurfaceForms'] for x in stages),'vocabulary surface progression')
# Common courtesy phrases and intentionally shared prechecks are reported, not mislabelled unique.
repeatedQuestions=[{'question':q,'count':c} for q,c in Counter(questions).items() if c>1]
report=dict(baseCommit=base,units=len(units),newUnits=72,assessmentItems=288,stages=stages,passagePairs=len(pairs),exactPassageDuplicates=96-len(set(u['reading'] for u in units)),highestSimilarityPairs=[dict(score=round(s,4),a=a,b=b) for s,a,b in pairs[:12]],repeatedAssessmentStems=repeatedQuestions,preservedSHA256=preserved,errors=errors,limits=['Morphological difficulty, official CEFR/TOPIK calibration and educational effectiveness are not established by length or surface forms.','Shared stage prechecks and shared lesson-flow layouts are intentional.','Answer evidence/key tests do not establish every possible semantic interpretation; author review and teacher review are distinct.'])
(R/'audit/professional96-content.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('preservedSHA256','highestSimilarityPairs')},ensure_ascii=False,indent=2));sys.exit(bool(errors))
