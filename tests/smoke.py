#!/usr/bin/env python3
"""冒烟测试：逐个端点打卡，全部通过才算建成。"""
import base64, json, sys, time
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"
ok, fail = 0, 0


def check(name, fn):
    global ok, fail
    t0 = time.time()
    try:
        r = fn()
        dt = int((time.time() - t0) * 1000)
        if r:
            print("  PASS  %-22s %5dms" % (name, dt))
            ok += 1
        else:
            print("  FAIL  %-22s %5dms  empty result" % (name, dt))
            fail += 1
    except Exception as e:
        print("  FAIL  %-22s       %s" % (name, str(e)[:120]))
        fail += 1


print("== zhipu-tools-oss 冒烟测试 -> " + BASE)

check("health", lambda: httpx.get(BASE + "/health", timeout=10).json().get("status") == "ok")

check("web_search", lambda: httpx.post(BASE + "/paas/v4/web_search",
      json={"search_query": "Python 是什么", "count": 3}, timeout=60).json().get("search_result"))

check("reader", lambda: len(httpx.post(BASE + "/paas/v4/reader",
      json={"url": "https://example.com"}, timeout=30).json()["reader_result"]["content"]) > 20)

txt = "这是一段测试文本，用于验证解析链路是否畅通。\n\n第二段。"
b64 = base64.b64encode(txt.encode()).decode()

check("parser_sync", lambda: "解析" in httpx.post(BASE + "/paas/v4/files/parser/sync",
      data={"file_base64": b64, "filename": "t.txt"}, timeout=30).json().get("content", ""))

def ocr_test():
    from PIL import Image, ImageDraw
    import io
    img = Image.new("RGB", (420, 90), "white")
    ImageDraw.Draw(img).text((12, 30), "HELLO OCR 123", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = httpx.post(BASE + "/paas/v4/files/ocr",
                   files={"file": ("t.png", buf.getvalue(), "image/png")}, timeout=60).json()
    return r.get("text", "").strip()

check("ocr", ocr_test)

check("moderations", lambda: isinstance(httpx.post(BASE + "/paas/v4/moderations",
      json={"input": "正常内容"}, timeout=10).json().get("flagged"), bool))

check("embeddings", lambda: len(httpx.post(BASE + "/paas/v4/embeddings",
      json={"input": "你好"}, timeout=20).json()["data"][0]["embedding"]) > 100)

def kb_flow():
    c = httpx.Client(timeout=30)
    kid = c.post(BASE + "/llm-application/open/knowledge",
                 json={"name": "smoke-kb", "description": "test"}).json()["id"]
    c.post(BASE + "/llm-application/open/document",
           json={"knowledge_id": kid, "title": "d1",
                 "content": "智谱开放平台提供大模型 API 服务。联网搜索接口是 web_search。"})
    r = c.post(BASE + "/llm-application/open/knowledge/retrieve",
               json={"knowledge_id": kid, "query": "联网搜索", "top_k": 2}).json()
    hit = bool(r.get("results"))
    c.delete(BASE + "/llm-application/open/knowledge/" + kid)
    return hit

check("knowledge_rag", kb_flow)

print("\n通过 %d，失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
