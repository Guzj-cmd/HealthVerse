import json
from pathlib import Path

from bridge import build_plan


root = Path(__file__).resolve().parent
payload = json.loads((root / "sample_request.json").read_text(encoding="utf-8"))
plan = build_plan(payload)

assert plan["schema"] == "healthverse.satori-bdi.v1"
assert plan["intention"]["policy"] == "ask_confirm"
assert plan["task_plan"]["steps"]
assert plan["task_plan"]["objects"] == ["显示器", "键盘", "手写区域", "水杯"]
assert plan["provenance"]["license"] == "MIT"
print(json.dumps({"ok": True, "policy": plan["intention"]["policy"]}, ensure_ascii=False))
