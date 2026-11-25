"""Lightweight Satori-compatible BDI bridge for HealthVerse.

This module intentionally avoids Satori's HoloLens/ptgctl/PyTorch runtime. It reuses
the upstream MIT task-plan parser and preserves Satori's structured step/checkpoint
contract while mapping HealthVerse evidence into Belief, Desire, and Intention.
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

from satori_parser import parse_xml_to_dict


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value, limit=400):
    return str(value or "").strip()[:limit]


def _list(value, limit=12):
    return [_text(item, 180) for item in (value or [])[:limit] if _text(item, 180)]


def _build_satori_xml(goal, observations, objects, action):
    observation_prompt = "；".join(observations[:3]) or "需要补充空间证据"
    object_nodes = "".join("<Object>%s</Object>" % escape(item) for item in objects)
    return """<TaskPlan>
  <DesiredTask>{goal}</DesiredTask>
  <Steps>
    <Step isStart="true">
      <StepContent>确认当前任务与空间证据</StepContent>
      <StepStatusCheckPrompts>
        <Prompt>{observation_prompt}</Prompt>
        <Prompt>用户是否处于自然停顿并愿意接收建议</Prompt>
      </StepStatusCheckPrompts>
      <Checkpoints>
        <Checkpoint>
          <Instruction>展示证据来源、置信度与不确定项</Instruction>
          <BlipPrompt>画面是否包含目标物体与相关人体关键点</BlipPrompt>
        </Checkpoint>
      </Checkpoints>
    </Step>
    <Step isStart="false">
      <StepContent>{action}</StepContent>
      <StepStatusCheckPrompts>
        <Prompt>用户是否确认了方案或要求修改</Prompt>
        <Prompt>执行后的空间关系是否与预览一致</Prompt>
      </StepStatusCheckPrompts>
      <Checkpoints>
        <Checkpoint>
          <Instruction>生成可撤销的轻量方案与原始布局对照</Instruction>
          <BlipPrompt>显示器、桌面与常用物体的位置是否发生预期变化</BlipPrompt>
        </Checkpoint>
      </Checkpoints>
    </Step>
  </Steps>
  <Objects>{objects}</Objects>
</TaskPlan>""".format(
        goal=escape(goal),
        observation_prompt=escape(observation_prompt),
        action=escape(action),
        objects=object_nodes,
    )


def build_plan(payload):
    """Map a HealthVerse context payload into a Satori-style BDI plan."""
    payload = payload or {}
    context = payload.get("context") or {}
    evidence = context.get("evidence") or payload.get("evidence") or []
    observations = _list(context.get("observations") or payload.get("observations"))
    constraints = _list(context.get("constraints") or payload.get("constraints"))
    objects = _list(context.get("objects") or payload.get("objects"))
    message = _text(payload.get("message"), 1000)
    task = _text(context.get("task") or payload.get("task") or "改善当前学习空间", 200)
    confidence = _number(context.get("confidence", payload.get("confidence", 0.6)), 0.6)
    interrupt_cost = _text(context.get("interrupt_cost") or "medium", 20).lower()
    correction = _text(context.get("correction") or "pending", 30).lower()

    belief = {
        "human": context.get("human") or {},
        "environment": context.get("environment") or {},
        "relations": context.get("relations") or [],
        "memory": context.get("memory") or [],
        "observations": observations,
        "evidence": evidence[:12],
        "confidence": round(max(0.0, min(confidence, 1.0)), 3),
    }
    desire = {
        "goal": message or task,
        "task": task,
        "constraints": constraints,
        "requires_user_confirmation": True,
    }

    if correction in ("rejected", "wrong", "mute"):
        policy = "suppress"
        action = "停止当前建议并等待新的用户输入"
        rationale = "用户已纠正或拒绝当前判断。"
    elif interrupt_cost == "high":
        policy = "stay_silent"
        action = "保持静默，在自然停顿时再询问"
        rationale = "当前打断成本高于建议的即时收益。"
    elif confidence < 0.75:
        policy = "ask_confirm"
        action = "请求补充侧面视角并让用户确认任务目标"
        rationale = "空间证据不足，先确认可以阻断错误传播。"
    else:
        policy = "offer_counterfactuals"
        action = "生成轻量方案与保持原布局的对照方案"
        rationale = "证据达到建议阈值，但执行权仍由用户保留。"

    intention = {
        "policy": policy,
        "next_action": action,
        "rationale": rationale,
        "reversible": True,
        "memory_write": "pending_user_confirmation",
    }
    xml_plan = _build_satori_xml(task, observations, objects, action)
    task_plan = parse_xml_to_dict(xml_plan)
    return {
        "schema": "healthverse.satori-bdi.v1",
        "belief": belief,
        "desire": desire,
        "intention": intention,
        "task_plan": task_plan,
        "provenance": {
            "upstream": "VIDA-NYU/satori-assistance",
            "upstream_commit": "dd09f303043cd90a9e486518bf9878f301f14677",
            "license": "MIT",
            "directly_reused": "Satori XML task-plan parser and step/checkpoint contract",
            "adapted": "HealthVerse BDI policy and evidence mapping",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HealthVerseSatoriBridge/1.0"

    def _json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "schema": "healthverse.satori-bdi.v1"})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/plan":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = max(0, min(int(self.headers.get("Content-Length", "0")), 64 * 1024))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            self._json(200, build_plan(payload))
        except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
            self._json(400, {"error": "invalid_request"})

    def log_message(self, fmt, *args):
        # The bridge handles local research context; avoid logging request bodies.
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="HealthVerse Satori BDI bridge")
    parser.add_argument("--serve", action="store_true", help="start an HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--input", type=Path, help="read one JSON request from a file")
    args = parser.parse_args()

    if args.serve:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        print("Satori bridge: http://%s:%d" % (args.host, args.port), flush=True)
        server.serve_forever()
        return

    if args.input:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        payload = json.load(sys.stdin)
    json.dump(build_plan(payload), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
