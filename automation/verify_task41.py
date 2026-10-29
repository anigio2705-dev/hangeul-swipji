"""Trusted, read-only source inventory for backlog #41 (not a learner trial).

Run on the isolated candidate checkout. This verifier lives on the HQ
controller branch, outside the AI-writable team worktree.
"""
import json
import subprocess
import sys
from pathlib import Path

NODE_CHECK = r"""
const {courses,lessons,reading}=require('./scripts/curriculum-source.cjs');
let units=0,quizzes=0,passages=0,readingQuestions=0;
for(const course of courses){
  const items=lessons(course);
  if(items.length!==50)throw Error('Wrong lesson count '+course);
  for(const item of items){
    if(!Array.isArray(item.quiz)||!item.quiz.length)throw Error('Empty quiz '+course);
    for(const q of item.quiz){
      if(!Array.isArray(q)||q.length<4||!Array.isArray(q[2])
        ||!Number.isInteger(q[3])||q[3]<0||q[3]>=q[2].length
        ||new Set(q[2]).size!==q[2].length)throw Error('Invalid quiz '+course);
    }
    units++;quizzes+=item.quiz.length;
  }
}
const source=reading('ko');
for(let level=1;level<=15;level++)for(let book=1;book<=40;book++){
  const item=source.get(level,book);
  if(!item||!Array.isArray(item.paragraphs)||!item.paragraphs.length
     ||!Array.isArray(item.translations)||item.paragraphs.length!==item.translations.length
     ||!Array.isArray(item.q)||!item.q.length)throw Error('Missing reading '+level+'-'+book);
  for(const q of item.q){
    if(!Array.isArray(q.options)||q.options.length<2
       ||!Number.isInteger(q.correct)||q.correct<0||q.correct>=q.options.length
       ||new Set(q.options).size!==q.options.length)throw Error('Invalid reading quiz '+level+'-'+book);
  }
  passages++;readingQuestions+=item.q.length;
}
console.log(JSON.stringify({courses:courses.length,units,quizzes,passages,readingQuestions}));
"""

def verify(root):
    if not (root / "scripts" / "curriculum-source.cjs").is_file():
        raise ValueError("Candidate checkout is missing curriculum-source.cjs")
    run = subprocess.run(
        ["node", "-e", NODE_CHECK], cwd=root, capture_output=True,
        text=True, timeout=90, check=True)
    counts = json.loads(run.stdout)
    expected = {"courses": 7, "units": 350, "quizzes": 1758,
                "passages": 600, "readingQuestions": 1800}
    if counts != expected:
        raise AssertionError(f"Source inventory changed: {counts} != {expected}")
    return counts

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_task41.py <candidate_checkout>")
    print("PASS task #41 source-count and answer-index integrity: " +
          json.dumps(verify(Path(sys.argv[1]).resolve()), sort_keys=True))
