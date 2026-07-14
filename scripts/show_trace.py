"""Print turns_log from a JSONL result file for failure-mode analysis."""
import json, sys, re

path = sys.argv[1]
max_think = int(sys.argv[2]) if len(sys.argv) > 2 else 400

with open(path) as f:
    r = json.loads(f.read())

tl = r.get("turns_log", [])
print(f"Model:   {r.get('model')}")
print(f"Session: {r.get('session_id', '')[:8]}  failure={r.get('failure_reason')}  turns={len(tl)}")
print(f"Gate acc={r.get('gate_accuracy')}  steps_used={r.get('steps_to_exit')}")
print()

for t in tl:
    text     = (t.get("model_text") or "").strip()
    thinking = (t.get("model_reasoning") or "").strip()
    action   = t["action_parsed"]
    engine   = t["engine_text"][:140].strip()

    # For non-reasoning models: strip the JSON out of text to see any prose
    prose = re.sub(r"```[a-z]*\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()
    prose = re.sub(r"^\s*\{.*?\}\s*$", "", prose, flags=re.DOTALL).strip()

    display = thinking or prose

    print(f"=== Turn {t['turn']} ===")
    print(f"ACTION : {action}")
    print(f"ENGINE : {engine}")
    if display:
        print(f"THINK  :")
        for line in display[:max_think].splitlines():
            print(f"  {line}")
    else:
        print(f"THINK  : [none]")
    print()
