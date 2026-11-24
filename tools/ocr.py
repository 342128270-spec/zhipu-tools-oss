"""ocr —— 自建 OCR，替代 /paas/v4/files/ocr
后端优先 macOS Vision（系统内置，离线、中文准），其次 rapidocr（若已装）。
"""
import base64, os, tempfile
from pathlib import Path

_vision = None
try:
    import Vision, Quartz
    from Foundation import NSURL
    _vision = True
except Exception:
    _vision = False

_rapid = None
try:
    from rapidocr_onnxruntime import RapidOCR
    _rapid = RapidOCR()
except Exception:
    _rapid = None


def _vision_ocr(path):
    url = NSURL.fileURLWithPath_(str(path))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if src is None:
        raise ValueError("cannot open image")
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(1)          # accurate
    req.setUsesLanguageCorrection_(True)
    req.setRecognitionLanguages_(["zh-Hans", "en-US"])
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(str(err))
    lines = []
    for obs in (req.results() or []):
        cand = obs.topCandidates_(1)
        if cand and len(cand):
            lines.append(cand[0].string())
    return "\n".join(lines)


def _decode(data, file_path):
    if file_path:
        return Path(file_path)
    if isinstance(data, str):
        raw = base64.b64decode(data.split(",")[-1])
    else:
        raw = data
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(raw)
    f.close()
    return Path(f.name)


def ocr(data=None, file_path=None):
    p = _decode(data, file_path)
    text = ""
    engine = ""
    if _vision:
        try:
            text = _vision_ocr(p)
            engine = "macos-vision"
        except Exception:
            text = ""
    if not text and _rapid is not None:
        res, _ = _rapid(str(p))
        text = "\n".join(x[1] for x in res) if res else ""
        engine = "rapidocr"
    if not engine:
        raise RuntimeError("no OCR backend available")
    words = [w for w in text.replace("\n", " ").split(" ") if w]
    return {
        "words_result_num": len(words),
        "words_result": [{"words": w} for w in words],
        "text": text,
        "engine": engine,
    }
