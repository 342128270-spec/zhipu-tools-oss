#!/usr/bin/env python3
"""zhipu-tools-oss —— 智谱工具 API 的开源自建替代。
一个进程提供：联网搜索 / 网页阅读 / 文件解析 / OCR / 内容安全 / 向量化 / 知识库 / 批处理。
用法：python3 serve.py [--port 8088]
"""
import argparse, base64, os, sys, tempfile
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from tools import web_search, reader, parser, ocr, knowledge, embeddings, batches, guard

TOKEN = os.environ.get("ZT_TOKEN", "")

app = FastAPI(title="zhipu-tools-oss", version="1.0.0",
              description="智谱开放平台工具 API 的开源自建实现")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def auth(request: Request):
    if not TOKEN:
        return True
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or h[7:] != TOKEN:
        raise HTTPException(401, "invalid token")
    return True


@app.get("/")
def root():
    return {
        "name": "zhipu-tools-oss",
        "version": "1.0.0",
        "auth_required": bool(TOKEN),
        "endpoints": [r.path for r in app.routes if getattr(r, "methods", None)],
    }


@app.get("/health")
def health():
    return {"status": "ok", "auth_required": bool(TOKEN)}


# ---------- 搜索 ----------
class SearchIn(BaseModel):
    search_query: str
    search_engine: str = "search_std"
    count: int = 10


@app.post("/paas/v4/web_search")
def api_web_search(body: SearchIn, _=Depends(auth)):
    return web_search.search(body.search_query, body.search_engine, body.count)


# ---------- 网页阅读 ----------
class ReaderIn(BaseModel):
    url: str
    return_format: str = "markdown"


@app.post("/paas/v4/reader")
def api_reader(body: ReaderIn, _=Depends(auth)):
    try:
        return reader.read(body.url, body.return_format)
    except Exception as e:
        raise HTTPException(502, "fetch failed: " + str(e)[:200])


# ---------- 文件解析 ----------
@app.post("/paas/v4/files/parser/create")
async def api_parser_create(file: UploadFile = File(None), file_base64: str = Form(None),
                            filename: str = Form(None), _=Depends(auth)):
    if file is not None:
        data = await file.read()
        name = file.filename or "upload"
    elif file_base64:
        data = base64.b64decode(file_base64.split(",")[-1])
        name = filename or "upload.pdf"
    else:
        raise HTTPException(400, "file or file_base64 required")
    p = parser.save_upload(data, name)
    return {"task_id": parser.create_task(p), "status": "succeeded"}


@app.post("/paas/v4/files/parser/sync")
async def api_parser_sync(file: UploadFile = File(None), file_base64: str = Form(None),
                          filename: str = Form(None), format: str = Form("markdown"),
                          _=Depends(auth)):
    if file is not None:
        data = await file.read()
        name = file.filename or "upload"
    elif file_base64:
        data = base64.b64decode(file_base64.split(",")[-1])
        name = filename or "upload.pdf"
    else:
        raise HTTPException(400, "file or file_base64 required")
    p = parser.save_upload(data, name)
    try:
        return parser.parse_file(p, format)
    except Exception as e:
        raise HTTPException(400, str(e)[:300])


@app.get("/paas/v4/files/parser/result/{task_id}/{format_type}")
def api_parser_result(task_id: str, format_type: str = "markdown", _=Depends(auth)):
    try:
        return parser.get_result(task_id, format_type)
    except KeyError:
        raise HTTPException(404, "task not found")


# ---------- OCR ----------
@app.post("/paas/v4/files/ocr")
async def api_ocr(file: UploadFile = File(None), file_base64: str = Form(None),
                  url: str = Form(None), _=Depends(auth)):
    try:
        if file is not None:
            data = await file.read()
            p = parser.save_upload(data, file.filename or "img.png")
            return ocr.ocr(file_path=str(p))
        if file_base64:
            return ocr.ocr(data=file_base64)
        if url:
            import httpx
            data = httpx.get(url, timeout=30, follow_redirects=True).content
            p = parser.save_upload(data, "img.png")
            return ocr.ocr(file_path=str(p))
    except Exception as e:
        raise HTTPException(400, "ocr failed: " + str(e)[:200])
    raise HTTPException(400, "file / file_base64 / url required")


# ---------- 内容安全 ----------
class ModIn(BaseModel):
    input: str


@app.post("/paas/v4/moderations")
def api_moderations(body: ModIn, _=Depends(auth)):
    return guard.moderate(body.input)


# ---------- 向量化 ----------
class EmbedIn(BaseModel):
    input: object
    model: str = "embedding-3"


@app.post("/paas/v4/embeddings")
def api_embeddings(body: EmbedIn, _=Depends(auth)):
    texts = body.input if isinstance(body.input, list) else [body.input]
    vecs, backend = [], ""
    for t in texts:
        v, backend = embeddings.embed(str(t))
        vecs.append({"object": "embedding", "index": len(vecs), "embedding": v})
    return {"object": "list", "data": vecs, "model": body.model, "backend": backend}


# ---------- 知识库 ----------
class KbIn(BaseModel):
    name: str
    description: str = ""


class KbPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RetrieveIn(BaseModel):
    knowledge_id: str
    query: str
    top_k: int = 5


class DocIn(BaseModel):
    knowledge_id: str
    title: str = ""
    content: str
    source: str = "text"


@app.get("/llm-application/open/knowledge/capacity")
def api_kb_capacity(_=Depends(auth)):
    return knowledge.capacity()


@app.post("/llm-application/open/knowledge")
def api_kb_create(body: KbIn, _=Depends(auth)):
    return knowledge.create_kb(body.name, body.description)


@app.get("/llm-application/open/knowledge")
def api_kb_list(_=Depends(auth)):
    return knowledge.list_kb()


@app.get("/llm-application/open/knowledge/{kid}")
def api_kb_get(kid: str, _=Depends(auth)):
    try:
        return knowledge.get_kb(kid)
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.put("/llm-application/open/knowledge/{kid}")
def api_kb_update(kid: str, body: KbPatch, _=Depends(auth)):
    try:
        return knowledge.update_kb(kid, body.name, body.description)
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.delete("/llm-application/open/knowledge/{kid}")
def api_kb_delete(kid: str, _=Depends(auth)):
    return knowledge.delete_kb(kid)


@app.post("/llm-application/open/knowledge/retrieve")
def api_kb_retrieve(body: RetrieveIn, _=Depends(auth)):
    try:
        return knowledge.retrieve(body.knowledge_id, body.query, body.top_k)
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.post("/llm-application/open/document")
def api_doc_add(body: DocIn, _=Depends(auth)):
    try:
        return knowledge.add_doc(body.knowledge_id, body.title or body.content[:30], body.content, body.source)
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.post("/llm-application/open/document/upload_document/{kid}")
async def api_doc_upload(kid: str, file: UploadFile = File(None), text: str = Form(None),
                         title: str = Form(None), _=Depends(auth)):
    try:
        if file is not None:
            data = await file.read()
            p = parser.save_upload(data, file.filename or "doc")
            parsed = parser.parse_file(p, "markdown")
            content = parsed["content"]
            name = title or (file.filename or "upload")
        elif text:
            content, name = text, (title or text[:30])
        else:
            raise HTTPException(400, "file or text required")
        return knowledge.add_doc(kid, name, content, "file")
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.post("/llm-application/open/document/upload_url/{kid}")
def api_doc_upload_url(kid: str, url: str = Query(...), title: str = Query(None), _=Depends(auth)):
    try:
        data = reader.read(url)["reader_result"]
        return knowledge.add_doc(kid, title or data.get("title") or url, data["content"], url)
    except KeyError:
        raise HTTPException(404, "knowledge base not found")


@app.get("/llm-application/open/document")
def api_doc_list(knowledge_id: str = Query(...), _=Depends(auth)):
    return knowledge.list_docs(knowledge_id)


@app.get("/llm-application/open/document/{did}")
def api_doc_get(did: str, _=Depends(auth)):
    try:
        return knowledge.get_doc(did)
    except KeyError:
        raise HTTPException(404, "document not found")


@app.delete("/llm-application/open/document/{did}")
def api_doc_delete(did: str, _=Depends(auth)):
    return knowledge.delete_doc(did)


# ---------- 批处理 ----------
class BatchIn(BaseModel):
    input_jsonl: Optional[str] = None
    input_file: Optional[str] = None


@app.post("/paas/v4/batches")
def api_batch_create(body: BatchIn, _=Depends(auth)):
    try:
        return batches.create(body.input_jsonl, body.input_file)
    except Exception as e:
        raise HTTPException(400, str(e)[:200])


@app.get("/paas/v4/batches")
def api_batch_list(_=Depends(auth)):
    return batches.list_all()


@app.get("/paas/v4/batches/{bid}")
def api_batch_get(bid: str, _=Depends(auth)):
    try:
        return batches.get(bid)
    except KeyError:
        raise HTTPException(404, "batch not found")


@app.post("/paas/v4/batches/{bid}/cancel")
def api_batch_cancel(bid: str, _=Depends(auth)):
    try:
        return batches.cancel(bid)
    except KeyError:
        raise HTTPException(404, "batch not found")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("ZT_PORT", "8088")))
    ap.add_argument("--host", default=os.environ.get("ZT_HOST", "127.0.0.1"))
    a = ap.parse_args()
    import uvicorn
    print("zhipu-tools-oss on http://" + a.host + ":" + str(a.port))
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
