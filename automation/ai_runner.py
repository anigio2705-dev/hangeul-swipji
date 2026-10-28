"""Budget-gated, single-task AI code proposal runner. No code execution or writes."""
import json, os, pathlib, sys, urllib.request
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = {
 "d2-contract-fixture": {
  "input": "team14/phase3/test_team14_d2_catalog_http.py",
  "output": "automation/proposals/d2-contract-fixture.json",
  "instruction": "Propose the smallest fix for the duplicate booking_product_snapshots fixture insertion when Team13 already creates a trusted snapshot. Preserve all assertions and real HTTP SQLite coverage. Return entire corrected file.",
 }
}
def validate_payload(task, result):
    if not isinstance(result, dict) or set(result) != {"path","content"}:
        raise ValueError("Unexpected AI response shape")
    if result["path"] != task["input"] or not isinstance(result["content"],str):
        raise ValueError("AI attempted out-of-scope edit")
    if len(result["content"]) > 100000 or len(result["content"]) < 100:
        raise ValueError("Invalid output length")
    if "test_http_verified_completion_75_25_refund_replay_restart" not in result["content"]:
        raise ValueError("Critical regression test removed")
    return result

def run():
    task_id=os.environ.get("HQ_TASK_ID","d2-contract-fixture")
    if task_id not in TASKS: raise ValueError("Task not approved")
    task=TASKS[task_id]
    daily_limit=float(os.environ.get("HQ_DAILY_BUDGET_USD","0"))
    max_calls=int(os.environ.get("HQ_MAX_CALLS","0"))
    if daily_limit <= 0 or max_calls < 1: raise RuntimeError("AI execution disabled: configure explicit budget and calls")
    if max_calls > 2: raise RuntimeError("Pilot allows at most two calls per run")
    api_key=os.environ.get("OPENAI_API_KEY")
    if not api_key: raise RuntimeError("OPENAI_API_KEY missing; do not paste it into logs")
    input_file=ROOT/task["input"]
    original=input_file.read_text(encoding="utf-8")
    if len(original)>100000: raise ValueError("Input too large")
    model=os.environ.get("HQ_MODEL","gpt-4.1-mini")
    prompt=("You are a code reviewer. Return ONLY JSON with keys path and content. "
            "Do not remove tests, do not access secrets, and do not introduce payment or deployment. "
            +task["instruction"]+"\nPATH: "+task["input"]+"\nSOURCE:\n"+original)
    body=json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],
                     "response_format":{"type":"json_object"},"temperature":0}).encode()
    request=urllib.request.Request("https://api.openai.com/v1/chat/completions",data=body,
        headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"})
    # One bounded request, no automatic retry. Hard stop on HTTP errors.
    with urllib.request.urlopen(request,timeout=90) as response:
        raw=json.load(response)
    result=validate_payload(task,json.loads(raw["choices"][0]["message"]["content"]))
    out=ROOT/task["output"]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"task_id":task_id,"model":model,"date":date.today().isoformat(),
        "proposal":result},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Proposal created. No source code was modified; review and tests required.")

if __name__=="__main__":
    try: run()
    except Exception as exc:
        print("AI proposal run failed: "+type(exc).__name__+": "+str(exc).split("\n")[0][:180],file=sys.stderr)
        sys.exit(1)
