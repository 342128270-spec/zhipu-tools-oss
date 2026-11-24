"""batches —— 自建批处理，替代 /paas/v4/batches
对任意 OpenAI 兼容端点（Ollama / llama.cpp / vLLM / 本机）批量跑 jsonl 请求。
环境变量：ZT_LLM_BASE（默认 http://127.0.0.1:11434/v1）、ZT_LLM_KEY、ZT_LLM_MODEL。
"""
import json, os, threading, time, uuid
from pathlib import Path

import httpx

DATA = Path(os.environ.get("ZT_DATA", Path.home() / ".zhipu-tools")).expanduser() / "batches"
DATA.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("ZT_LLM_BASE", "http://127.0.0.1:11434/v1")
KEY = os.environ.get("ZT_LLM_KEY", "")
MODEL = os.environ.get("ZT_LLM_MODEL", "")

_jobs = {}


def _state(bid):
    f = DATA / (bid + ".json")
    if not f.exists():
        raise KeyError(bid)
    return json.loads(f.read_text(encoding="utf-8"))


def _save(st):
    (DATA / (st["id"] + ".json")).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def _run(bid):
    st = _state(bid)
    st["status"] = "in_progress"
    _save(st)
    lines = (DATA / (bid + ".jsonl")).read_text(encoding="utf-8").splitlines()
    out = []
    ok = fail = 0
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = "Bearer " + KEY
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            req = json.loads(ln)
            body = req.get("body", req)
            body.setdefault("model", MODEL or body.get("model", ""))
            r = httpx.post(BASE.rstrip("/") + "/chat/completions", json=body, headers=headers, timeout=180)
            item = {"custom_id": req.get("custom_id", ""), "response": {"status_code": r.status_code,
                    "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}}
            if r.status_code == 200:
                ok += 1
            else:
                fail += 1
        except Exception as e:
            item = {"custom_id": "", "response": {"status_code": 0, "body": str(e)[:300]}}
            fail += 1
        out.append(item)
    (DATA / (bid + ".out.jsonl")).write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in out), encoding="utf-8")
    st.update({"status": "completed", "completed": int(time.time()),
               "request_counts": {"total": ok + fail, "completed": ok, "failed": fail}})
    _save(st)


def create(jsonl_text=None, file_path=None):
    if not jsonl_text and file_path:
        jsonl_text = Path(file_path).read_text(encoding="utf-8")
    if not jsonl_text:
        raise ValueError("need input file or inline jsonl")
    bid = "batch_" + uuid.uuid4().hex[:12]
    (DATA / (bid + ".jsonl")).write_text(jsonl_text, encoding="utf-8")
    st = {"id": bid, "status": "validating", "created": int(time.time()),
          "endpoint": "/v1/chat/completions", "input_file": bid + ".jsonl",
          "target_base": BASE, "request_counts": {"total": len(jsonl_text.splitlines()), "completed": 0, "failed": 0}}
    _save(st)
    threading.Thread(target=_run, args=(bid,), daemon=True).start()
    return st


def get(bid):
    st = _state(bid)
    out = DATA / (bid + ".out.jsonl")
    if out.exists() and st.get("status") == "completed":
        st["output_text"] = out.read_text(encoding="utf-8")[:20000]
    return st


def cancel(bid):
    st = _state(bid)
    st["status"] = "cancelled"
    _save(st)
    return st


def list_all():
    out = []
    for f in sorted(DATA.glob("batch_*.json")):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
            st.pop("output_text", None)
            out.append(st)
        except Exception:
            pass
    return out
