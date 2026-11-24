"""parser —— 自建文件解析，替代 /paas/v4/files/parser/*
支持 pdf / docx / txt / md / html / 图片(OCR)。输出 markdown 或纯文本。
"""
import base64, json, os, tempfile, time, uuid, zipfile, re
from pathlib import Path

TASK_DIR = Path(os.environ.get("ZT_DATA", Path.home() / ".zhipu-tools")).expanduser() / "parser"
TASK_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm",
             ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def _md_table(rows):
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [[(c or "").replace("|", "/").replace("\n", " ").strip() for c in r] + [""] * (width - len(r))
            for r in rows]
    out = ["| " + " | ".join(norm[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for r in norm[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _pdf_tables(p, max_pages=50):
    """用 pdfplumber 抽表格；表格是 PDF 解析最容易丢的信息。"""
    try:
        import pdfplumber
    except Exception:
        return {}
    found = {}
    try:
        with pdfplumber.open(p) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages], 1):
                try:
                    tabs = page.extract_tables()
                except Exception:
                    continue
                good = [t for t in tabs if t and len(t) >= 2 and any(any(c for c in row) for row in t)]
                if good:
                    found[i] = good
    except Exception:
        return {}
    return found


def _from_pdf(p):
    import fitz
    doc = fitz.open(p)
    parts = []
    tables = _pdf_tables(p)
    for i, page in enumerate(doc, 1):
        t = page.get_text("text").strip()
        block = []
        if t:
            block.append("## 第 " + str(i) + " 页\n\n" + t)
        for k, tab in enumerate(tables.get(i, []), 1):
            md = _md_table(tab)
            if md:
                block.append("### 第 " + str(i) + " 页 表格 " + str(k) + "\n\n" + md)
        if block:
            parts.append("\n\n".join(block))
    doc.close()
    return "\n\n".join(parts)


def _from_docx(p):
    import docx
    d = docx.Document(p)
    out = []
    for para in d.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            lvl = "".join(ch for ch in style if ch.isdigit()) or "1"
            out.append("#" * min(int(lvl), 6) + " " + t)
        else:
            out.append(t)
    for ti, table in enumerate(d.tables, 1):
        out.append("")
        out.append("表格 " + str(ti) + ":")
        for row in table.rows:
            out.append("| " + " | ".join(c.text.strip().replace("|", "/") for c in row.cells) + " |")
    return "\n\n".join(out)


def _from_html(p):
    import trafilatura
    html = Path(p).read_text(encoding="utf-8", errors="replace")
    return trafilatura.extract(html, output_format="markdown",
                              include_links=True, include_tables=True) or ""


def _from_text(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def _from_image(p):
    from . import ocr as ocr_mod
    return ocr_mod.ocr(file_path=str(p))["text"]


HANDLERS = {".pdf": _from_pdf, ".docx": _from_docx, ".html": _from_html, ".htm": _from_html,
            ".txt": _from_text, ".md": _from_text, ".markdown": _from_text,
            ".png": _from_image, ".jpg": _from_image, ".jpeg": _from_image,
            ".webp": _from_image, ".bmp": _from_image, ".tiff": _from_image}


def parse_file(path, fmt="markdown"):
    p = Path(path)
    ext = p.suffix.lower()
    fn = HANDLERS.get(ext)
    if not fn:
        raise ValueError("unsupported type: " + ext + " (supported: " + ", ".join(sorted(SUPPORTED)) + ")")
    text = fn(p)
    if fmt == "text":
        text = re.sub(r"^#{1,6} ", "", text, flags=re.M)
    return {"content": text, "chars": len(text), "file": p.name, "type": ext.lstrip(".")}


def save_upload(data, filename):
    raw = data
    if isinstance(data, str):
        raw = base64.b64decode(data.split(",")[-1])
    d = TASK_DIR / (uuid.uuid4().hex[:12] + "_" + Path(filename).name)
    d.write_bytes(raw)
    return d


def create_task(path):
    tid = uuid.uuid4().hex
    (TASK_DIR / (tid + ".json")).write_text(json.dumps({
        "task_id": tid, "file": str(path), "status": "succeeded", "created": int(time.time())
    }), encoding="utf-8")
    return tid


def get_result(task_id, fmt="markdown"):
    meta = TASK_DIR / (task_id + ".json")
    if not meta.exists():
        raise KeyError(task_id)
    info = json.loads(meta.read_text(encoding="utf-8"))
    return parse_file(info["file"], fmt)
