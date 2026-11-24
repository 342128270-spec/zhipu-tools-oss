"""reader —— 自建网页正文提取，替代 /paas/v4/reader
后端：trafilatura（Apache-2.0），可选 readability 兜底。
"""
import httpx, trafilatura

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def read(url, return_format="markdown", timeout=20):
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                  timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    html = r.text
    text = trafilatura.extract(
        html,
        output_format="markdown" if return_format == "markdown" else "txt",
        include_links=True, include_tables=True, include_images=False,
        favor_recall=True, url=url,
    ) or ""
    meta = trafilatura.extract_metadata(html, default_url=url)
    return {
        "reader_result": {
            "content": text,
            "title": (meta.title if meta else "") or "",
            "description": (meta.description if meta else "") or "",
            "url": str(r.url),
            "length": len(text),
        }
    }
