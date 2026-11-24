"""knowledge —— 自建知识库 / RAG，替代 /llm-application/open/*
存储 SQLite，检索 BM25（中文按字二元组切分，无需下载模型、无 API 依赖）。
"""
import json, os, re, sqlite3, time, uuid
from pathlib import Path

DATA = Path(os.environ.get("ZT_DATA", Path.home() / ".zhipu-tools")).expanduser()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "kb.db"

CHUNK = 500
OVERLAP = 60


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kb (
      id TEXT PRIMARY KEY, name TEXT, description TEXT, created INTEGER);
    CREATE TABLE IF NOT EXISTS doc (
      id TEXT PRIMARY KEY, kb_id TEXT, title TEXT, source TEXT,
      content TEXT, chunks INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS chunk (
      id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, kb_id TEXT,
      idx INTEGER, text TEXT);
    """)
    return c


def _tok(s):
    s = (s or "").lower()
    words = re.findall(r"[a-z0-9_]+", s)
    cjk = re.sub(r"[^\u4e00-\u9fff]", "", s)
    grams = [cjk[i:i + 2] for i in range(len(cjk) - 1)] if len(cjk) > 1 else ([cjk] if cjk else [])
    return words + grams


def _split(text):
    text = text.strip()
    if len(text) <= CHUNK:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK])
        i += CHUNK - OVERLAP
    return out


def create_kb(name, description=""):
    c = conn()
    kid = "kb_" + uuid.uuid4().hex[:12]
    c.execute("INSERT INTO kb VALUES (?,?,?,?)", (kid, name, description, int(time.time())))
    c.commit(); c.close()
    return {"id": kid, "name": name, "description": description}


def list_kb():
    c = conn()
    rows = c.execute("SELECT k.*, (SELECT COUNT(*) FROM doc d WHERE d.kb_id=k.id) AS docs FROM kb k ORDER BY created DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_kb(kid):
    c = conn()
    r = c.execute("SELECT * FROM kb WHERE id=?", (kid,)).fetchone()
    c.close()
    if not r:
        raise KeyError(kid)
    return dict(r)


def update_kb(kid, name=None, description=None):
    get_kb(kid)
    c = conn()
    if name is not None:
        c.execute("UPDATE kb SET name=? WHERE id=?", (name, kid))
    if description is not None:
        c.execute("UPDATE kb SET description=? WHERE id=?", (description, kid))
    c.commit(); c.close()
    return get_kb(kid)


def delete_kb(kid):
    c = conn()
    c.execute("DELETE FROM chunk WHERE kb_id=?", (kid,))
    c.execute("DELETE FROM doc WHERE kb_id=?", (kid,))
    c.execute("DELETE FROM kb WHERE id=?", (kid,))
    c.commit(); c.close()
    return {"deleted": kid}


def add_doc(kid, title, text, source="text"):
    get_kb(kid)
    c = conn()
    did = "doc_" + uuid.uuid4().hex[:12]
    chunks = _split(text)
    c.execute("INSERT INTO doc VALUES (?,?,?,?,?,?,?)",
              (did, kid, title, source, text[:200000], len(chunks), int(time.time())))
    for i, ch in enumerate(chunks):
        c.execute("INSERT INTO chunk (doc_id, kb_id, idx, text) VALUES (?,?,?,?)", (did, kid, i, ch))
    c.commit(); c.close()
    return {"id": did, "title": title, "chunks": len(chunks)}


def list_docs(kid):
    c = conn()
    rows = c.execute("SELECT id,title,source,chunks,created FROM doc WHERE kb_id=? ORDER BY created DESC", (kid,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_doc(did):
    c = conn()
    r = c.execute("SELECT * FROM doc WHERE id=?", (did,)).fetchone()
    c.close()
    if not r:
        raise KeyError(did)
    return dict(r)


def delete_doc(did):
    c = conn()
    c.execute("DELETE FROM chunk WHERE doc_id=?", (did,))
    c.execute("DELETE FROM doc WHERE id=?", (did,))
    c.commit(); c.close()
    return {"deleted": did}


def retrieve(kid, query, top_k=5):
    from rank_bm25 import BM25Plus
    c = conn()
    rows = c.execute("SELECT id,doc_id,idx,text FROM chunk WHERE kb_id=?", (kid,)).fetchall()
    c.close()
    if not rows:
        return {"results": [], "note": "knowledge base is empty"}
    corpus = [_tok(r["text"]) for r in rows]
    # BM25Plus：小语料下不会出现负分（Okapi 在单文档库会给出负值）
    bm25 = BM25Plus(corpus)
    scores = bm25.get_scores(_tok(query))
    order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)[:top_k]
    out = []
    for i in order:
        if scores[i] <= 0:
            continue
        out.append({
            "doc_id": rows[i]["doc_id"],
            "chunk": rows[i]["idx"],
            "score": round(float(scores[i]), 4),
            "text": rows[i]["text"],
        })
    return {"results": out, "total_chunks": len(rows)}


def capacity():
    c = conn()
    n_kb = c.execute("SELECT COUNT(*) c FROM kb").fetchone()["c"]
    n_doc = c.execute("SELECT COUNT(*) c FROM doc").fetchone()["c"]
    n_ch = c.execute("SELECT COUNT(*) c FROM chunk").fetchone()["c"]
    c.close()
    return {"knowledge_bases": n_kb, "documents": n_doc, "chunks": n_ch,
            "db_bytes": DB.stat().st_size if DB.exists() else 0}
