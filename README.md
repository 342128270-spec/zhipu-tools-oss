# zhipu-tools-oss · 智谱工具 API 的开源自建替代

把智谱开放平台的工具类 API 用开源组件重写一遍，接口路径保持兼容：客户端只要把 base_url 从
https://open.bigmodel.cn/api 换成 http://127.0.0.1:8088，其余不动。

无商业 SDK、无 API Key、无调用计费。

## 覆盖范围

| 原接口 | 本仓实现 | 开源后端 | 状态 |
|---|---|---|---|
| POST /paas/v4/web_search | tools/web_search.py | 必应 / 百度 HTML 解析 | 可用 |
| POST /paas/v4/reader | tools/reader.py | trafilatura (Apache-2.0) | 可用 |
| POST /paas/v4/files/parser/* | tools/parser.py | PyMuPDF + python-docx + trafilatura | 可用 |
| POST /paas/v4/files/ocr | tools/ocr.py | macOS Vision（离线）/ RapidOCR | 可用 |
| POST /paas/v4/moderations | tools/guard.py | 规则表（可自定义） | 可用 |
| POST /paas/v4/embeddings | tools/embeddings.py | hashing n-gram / sentence-transformers | 可用 |
| /llm-application/open/*（知识库） | tools/knowledge.py | SQLite + BM25Plus | 可用 |
| /paas/v4/batches | tools/batches.py | 转发到任意 OpenAI 兼容端点 | 可用 |
| /paas/v4/chat/completions | 不实现 | 用 Ollama / llama.cpp / vLLM | 建议外挂 |
| /agent/managed/v1/* | 不实现 | 应用层，非工具 | 不涉及 |

对话补全属于模型推理，自建没有意义。本机跑 Ollama 或 llama.cpp，再把批处理模块指过去。

## 安装

    cd zhipu-tools-oss
    ./install.sh          # 建 venv 到 ~/.zhipu-tools/venv
    ./start.sh            # 起服务，默认 127.0.0.1:8088

    ZT_PORT=9000 ZT_TOKEN=mysecret ./start.sh   # 换端口并开启 Bearer 校验
    ZT_DATA=/path/to/data ./start.sh            # 换数据目录（默认 ~/.zhipu-tools）

冒烟测试：8 项全过才算可用。

    ~/.zhipu-tools/venv/bin/python tests/smoke.py

## 调用示例

    # 联网搜索
    curl -s http://127.0.0.1:8088/paas/v4/web_search -H 'Content-Type: application/json' \
      -d '{"search_query":"智谱 GLM","count":5}'

    # 网页正文
    curl -s http://127.0.0.1:8088/paas/v4/reader -H 'Content-Type: application/json' \
      -d '{"url":"https://docs.bigmodel.cn/cn/guide/start/introduction"}'

    # 文件解析
    curl -s http://127.0.0.1:8088/paas/v4/files/parser/sync -F 'file=@报告.pdf' -F 'format=markdown'

    # OCR
    curl -s http://127.0.0.1:8088/paas/v4/files/ocr -F 'file=@截图.png'

    # 知识库：建库 → 传文档 → 检索
    curl -s http://127.0.0.1:8088/llm-application/open/knowledge \
      -H 'Content-Type: application/json' -d '{"name":"产品文档"}'
    curl -s http://127.0.0.1:8088/llm-application/open/document/upload_document/<kb_id> -F 'file=@手册.pdf'
    curl -s http://127.0.0.1:8088/llm-application/open/knowledge/retrieve \
      -H 'Content-Type: application/json' -d '{"knowledge_id":"<kb_id>","query":"怎么退款","top_k":3}'

    # 批处理（先 export ZT_LLM_BASE / ZT_LLM_MODEL 指向本机模型）
    curl -s http://127.0.0.1:8088/paas/v4/batches -H 'Content-Type: application/json' \
      -d '{"input_jsonl":"{\"custom_id\":\"1\",\"body\":{\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}]}}"}'

GET / 返回全部已注册端点，GET /openapi.json 是标准 OpenAPI 描述，可直接喂 Postman / LangChain。

## 设计取舍

- 搜索走 HTML 解析而非 API：无需 Key，代价是可能被反爬；命不中时返回空并在 errors 字段写明原因。
- 检索用 BM25 而非向量库：不下载模型、中文按字二元组切分。要语义检索就装 sentence-transformers 并设 ZT_USE_ST=1。
- OCR 走 macOS Vision：离线、中文准、零下载。非 macOS 自动退回 RapidOCR。
- 批处理是转发器：自己不产 token，把请求打到本地模型，负责排队、并发、结果落盘。

## 已知限制

1. 搜索受反爬影响，量大需加代理或自建 SearXNG。
2. BM25 是词面匹配，同义改写查不到。
3. 内容安全是规则表，只挡显式关键词，不是分类模型。
4. 无多租户、无配额（只有一个全局 ZT_TOKEN）。

## 许可

本仓代码 MIT。依赖各自遵循其许可证：trafilatura (Apache-2.0)、python-docx (MIT)、rank-bm25 (Apache-2.0)、
PyMuPDF (AGPL-3.0) —— 闭源分发需换 pdfminer.six 或购买商业授权。