"""embeddings —— 自建向量化，替代 /paas/v4/embeddings
默认 hashing n-gram 向量（无模型依赖，纯词面）；装了 sentence-transformers 时自动升级为语义向量。
"""
import hashlib, math, os, re

DIM = 1024
_st = None
if os.environ.get("ZT_USE_ST", "") == "1":
    try:
        from sentence_transformers import SentenceTransformer
        _st = SentenceTransformer(os.environ.get("ZT_ST_MODEL", "BAAI/bge-small-zh-v1.5"))
    except Exception:
        _st = None


def _tok(s):
    s = (s or "").lower()
    words = re.findall(r"[a-z0-9_]+", s)
    cjk = re.sub(r"[^\u4e00-\u9fff]", "", s)
    grams = [cjk[i:i + 2] for i in range(len(cjk) - 1)] if len(cjk) > 1 else ([cjk] if cjk else [])
    return words + grams


def embed(text):
    if _st is not None:
        v = _st.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in v], "sentence-transformers"
    vec = [0.0] * DIM
    toks = _tok(text)
    for t in toks:
        h = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
        vec[h % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    vec = [x / norm for x in vec]
    return vec, "hashing-ngram"
