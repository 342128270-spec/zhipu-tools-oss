"""web_search —— 自建联网搜索，替代 /paas/v4/web_search
后端：cn.bing.com / baidu（HTML 解析），无需任何 API Key。
"""
import re, time, uuid, random
import httpx
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

SHORTCUTS = {
    "search_std": ["bing", "baidu"],
    "search_pro": ["bing", "baidu"],
    "search_pro_sogou": ["bing", "baidu"],
    "search_pro_quark": ["bing", "baidu"],
}


def _clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _bing(q, limit):
    out = []
    r = httpx.get("https://cn.bing.com/search",
                  params={"q": q, "count": max(limit, 10), "setlang": "zh-CN"},
                  headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                  timeout=15, follow_redirects=True)
    soup = BeautifulSoup(r.text, "lxml")
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        href = a.get("href", "")
        if not href.startswith("http"):
            continue
        cap = li.select_one(".b_caption p") or li.select_one("p")
        out.append({
            "title": _clean(a.get_text()),
            "link": href,
            "content": _clean(cap.get_text() if cap else ""),
            "media": "bing",
            "icon": "",
            "refer": "bing",
        })
        if len(out) >= limit:
            break
    return out


def _baidu(q, limit):
    out = []
    r = httpx.get("https://www.baidu.com/s",
                  params={"wd": q, "rn": max(limit, 10)},
                  headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                  timeout=15, follow_redirects=True)
    soup = BeautifulSoup(r.text, "lxml")
    for div in soup.select("div.result, div.c-container"):
        a = div.select_one("h3 a")
        if not a:
            continue
        href = a.get("href", "")
        if href.startswith("/link?"):
            href = "https://www.baidu.com" + href
        if not href.startswith("http"):
            continue
        cap = div.select_one(".c-abstract") or div.select_one("span.content-right_8Zs40")
        title = _clean(a.get_text())
        if not title:
            continue
        out.append({
            "title": title,
            "link": href,
            "content": _clean(cap.get_text() if cap else ""),
            "media": "baidu",
            "icon": "",
            "refer": "baidu",
        })
        if len(out) >= limit:
            break
    return out


ENGINES = {"bing": _bing, "baidu": _baidu}


def search(query, engine="search_std", limit=10):
    order = SHORTCUTS.get(engine) or [engine] if engine in ENGINES else SHORTCUTS["search_std"]
    results, errors = [], []
    for name in order:
        fn = ENGINES.get(name)
        if not fn:
            continue
        try:
            results.extend(fn(query, limit - len(results)))
        except Exception as e:
            errors.append(name + ": " + str(e)[:120])
        if len(results) >= limit:
            break
    # 去重
    seen, uniq = set(), []
    for it in results:
        k = it["link"].split("#")[0]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return {
        "id": "ws-" + uuid.uuid4().hex[:16],
        "created": int(time.time()),
        "search_result": uniq[:limit],
        "errors": errors,
    }
