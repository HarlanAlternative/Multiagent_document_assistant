# Multi-Agent Personal Knowledge Copilot

[English](README.md) | 简体中文

一个针对个人文档的知识问答助手。你上传 PDF、PPTX、DOCX、TXT 或 Markdown 文件后，系统会为它们建立索引，每个回答都会注明出自哪一页或哪张幻灯片。路由、检索、联网搜索、答案撰写和引用整理分别由不同的 agent 负责。你可以用中文提问英文文档，向量也可以在本机计算。外部服务不可用时，系统会自动改用本地组件。

## 功能

- **多智能体 RAG 流程。** 路由 agent 判断问题该查文档、查网络，还是两者都查；检索、联网搜索、答案和引用 agent 负责其余环节。
- **有依据、带引用的回答。** 答案只依据检索到的内容，并注明出自哪一页或哪张幻灯片。文档里没有答案时，会直接说明。
- **中英文提问。** 中文问题会被改写成英文检索查询，默认的向量模型也支持多语言。
- **本机计算向量。** 默认使用在 CPU 上运行的本地 [fastembed](https://github.com/qdrant/fastembed) 模型（`Qwen3-Embedding-0.6B`，int8），建索引不需要任何向量 API。
- **可替换的组件。**
  - LLM：任意 OpenAI 兼容接口（OpenAI、DeepSeek 等）、Claude、Gemini 或 AWS Bedrock。
  - 向量：本地模型、OpenAI、Bedrock 或离线哈希。
  - 向量库：Qdrant 或本地存储。
  - 联网搜索：Tavily 或 DuckDuckGo。
- **项目与对话。** 文档和聊天记录按项目归类。长对话会自动生成摘要，所以追问时能沿用上下文。
- **内置评测。** 包含一套带标注的题目，以及一个通过真实 API 测量检索和回答质量的脚本。
- **完整的前后端。** 包括 FastAPI 后端、React 前端和 Docker Compose 部署。应用运行时，可以在设置页切换各个组件。

## 技术栈

- **后端：** FastAPI、SQLAlchemy、SQLite 或 PostgreSQL、Qdrant、PyMuPDF、python-pptx、python-docx、fastembed
- **前端：** React 18、TypeScript、Vite、Tailwind CSS、TanStack Query、KaTeX

## 效果

以下结果来自 72 道测试题（其中 22 道中文），题目针对 5 份共 226 页的 PDF 课件。回答由 DeepSeek（`deepseek-flash`）生成，向量来自本地 Qwen3 模型。

| 指标 | 结果 |
|---|---|
| 检索命中率 hit@5（检索结果中包含答案所在页） | 94.4% |
| 中文题检索命中率 hit@5 | 90.9% |
| 答案正确率 | 87.5% |
| 每条陈述都有检索原文依据的回答 | 97.1% |
| 文档范围外的问题正确拒答 | 10/10 |
| 响应时间 | 中位数 5.1 秒，p90 9.7 秒 |
| 在 CPU 上为 226 页建索引的耗时 | 62 秒 |

正确率和有据率由另一个 LLM（`deepseek-v4-pro`）评分。评测方法和对比基线见[评测](#评测)。

## 工作原理

**建索引。** 每个文件按页（PDF）、按幻灯片（PPTX）或作为纯文本解析。文本被切成最多 220 词的块，块不会跨页。每个块计算向量后，和页码一起存储。

**回答问题：**

1. **路由。** 在 `auto` 模式下，由 LLM 判断查文档、查网络，还是两者都查。没有 LLM 时，按规则判断。
2. **改写。** 中文问题和追问会被改写成独立的英文检索查询。
3. **检索。** 系统找出 20 个候选块，按向量相似度结合关键词重叠为每个块打分。
4. **重排。** 先按问题类型（定义、用途、公式或一般）重新打分，再由 LLM 重排，通常保留一到两个块。
5. **回答。** LLM 只依据这些块作答，找不到答案就拒答。没有 LLM 时，直接返回最相关的原文句子。
6. **引用。** 每个答案都列出证据来自哪个文件的哪一页或哪张幻灯片；网页结果则列出 URL。

检索方式是按块的向量检索加重排，没有使用知识图谱。

## 评测

`backend/eval/dataset.json` 中共有 91 道题，都针对这 5 份 PDF：

- 72 道测试题，其中 22 道是中文。每道题都标注了答案所在的页。
- 10 道文档无法回答的题，正确做法是拒答。
- 9 道来自早期开发的题，单独统计。

`backend/eval/run_eval.py` 以 `private_only` 模式把每道题发送到 `POST /api/chat/ask`，记录检索结果、引用、响应时间和 token 用量。另一个模型 `deepseek-v4-pro` 对照参考答案和检索到的证据，为每个答案评分。

72 道测试题的结果（测于 2026-10-02）：

| 指标 | 无 LLM，哈希向量 | DeepSeek，哈希向量 | DeepSeek，本地向量（默认） |
|---|---|---|---|
| 检索命中率 hit@5 | 70.8% | 88.9% | **94.4%** |
| MRR@5 | 0.588 | 0.889 | **0.944** |
| 中文题检索命中率 hit@5 | 13.6% | 72.7% | **90.9%** |
| 答案正确率 | 未评分 | 87.5% | 87.5% |
| 每条陈述都有依据的回答 | 未评分 | 96.9% | 97.1% |
| 引用精确率 | 45.5% | 79.8% | 85.2% |
| 无答案题正确拒答 | 5/10 | 10/10 | 10/10 |
| 响应时间，中位数 / p90 | 33 ms / 35 ms | 4.0 s / 8.6 s | 5.1 s / 9.7 s |

不接 LLM 时，各本地向量模型的对比如下：

| 向量模型 | 下载大小 | Hit@5 | MRR@5 | 中文 hit@5 | 单题耗时 | 226 页建索引 |
|---|---|---|---|---|---|---|
| 哈希（无模型） | - | 70.8% | 0.588 | 3/22 | 33 ms | 0.2 s |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.22 GB | 75.0% | 0.650 | 6/22 | 66 ms | 2.9 s |
| `jina-embeddings-v2-base-zh` | 0.64 GB | 75.0% | 0.657 | 6/22 | 115 ms | 13.2 s |
| `Qwen3-Embedding-0.6B-Q`（默认） | 1.12 GB | 80.6% | 0.693 | 10/22 | 546 ms | 62.0 s |

逐题结果在 `backend/eval/results/` 中。复现方法：

```powershell
cd backend
.venv\Scripts\python.exe eval\run_eval.py --config offline
.venv\Scripts\python.exe eval\run_eval.py --config deepseek --embedding-provider local --judge-model deepseek-v4-pro
```

使用 LLM 的运行会从环境变量或 `backend/.env` 中读取 `DEEPSEEK_API_KEY`。PDF 文件不在仓库中，脚本会在 `backend/storage/demo-run/live-backend-uploads` 中查找，并按 SHA-256 匹配。可以用 `--docs-dir` 指定其他目录。

## 快速开始

### Docker Compose（完整环境）

```bash
cd infra
docker compose up --build
```

会启动以下服务：

- PostgreSQL：`localhost:5433`。没有用 `5432`，是为了避免和本机已有的 PostgreSQL 冲突。
- Qdrant：`localhost:6333`
- FastAPI 后端：`http://127.0.0.1:8000`
- React 前端：`http://127.0.0.1:5173`

后端容器会读取 `backend/.env`。

### 只启动后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

在 macOS 或 Linux 上，用 `. .venv/bin/activate` 激活虚拟环境，用 `cp .env.example .env` 复制配置文件。

`.env.example` 指向 Docker 中端口为 `5433` 的 PostgreSQL。如果不想启动任何服务，就删掉 `DATABASE_URL` 并设置 `VECTOR_STORE=local`，后端会改用 `backend/storage/app.db` 中的 SQLite。

### 只启动前端

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

前端默认请求 `http://127.0.0.1:8000/api`。如需修改，设置 `VITE_API_BASE_URL`。

## 配置

大部分设置都可以在设置页（**Settings**）修改。这些设置保存在 `backend/storage/runtime_settings.json` 中，并覆盖 `.env` 里的同名配置。LLM、向量和向量库的修改从下一次请求开始生效；联网搜索的修改需要重启后端。

### LLM

在设置页或通过 `PUT /api/settings/llm` 配置 API key、提供方和模型。key 只从这里读取，OpenAI 向量也用同一个 key。系统不会读取 `backend/.env` 中的 `OPENAI_API_KEY`。

**DeepSeek：** 选择 DeepSeek 预设后，它会：

- 把 base URL 设为 `https://api.deepseek.com/v1`，把 wire API 设为 `chat_completions`；
- 提供 `deepseek-flash` 和 `deepseek-v4-pro` 两个模型；
- 把向量切换为本地模型，因为 DeepSeek 没有向量接口。

模型名和模式也可以写在 `.env` 中：

```powershell
CHAT_MODEL=gpt-5-mini
ROUTER_MODEL=gpt-5-mini
ANSWER_MODEL=gpt-5-mini
ROUTER_PROVIDER=llm
ANSWER_PROVIDER=llm
OPENAI_WIRE_API=responses   # 或 chat_completions
LLM_TIMEOUT_SECONDS=30
```

没有可用的 LLM 时，后端会改用规则路由、启发式重排和抽取式答案。

### 向量与向量库

| 方案 | 配置 |
|---|---|
| 本地模型（推荐，不需要 API key） | `EMBEDDING_PROVIDER=local`，可选 `LOCAL_EMBEDDING_MODEL` 和 `LOCAL_EMBEDDING_CACHE_DIR` |
| 离线哈希（不需要模型） | `EMBEDDING_PROVIDER=deterministic` |
| OpenAI | `EMBEDDING_PROVIDER=openai`，`OPENAI_EMBEDDING_MODEL=text-embedding-3-large` |
| Bedrock | `EMBEDDING_PROVIDER=bedrock`，`BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0`，`AWS_REGION`，`AWS_ACCESS_KEY_ID`，`AWS_SECRET_ACCESS_KEY` |

- **本地模型：** 默认是 `Qwen/Qwen3-Embedding-0.6B-Q`，首次使用时下载（约 1.1 GB），缓存在 `backend/storage/models/`。也可以换成 fastembed 的 `TextEmbedding.list_supported_models()` 中的任意模型。
- **离线哈希：** 只能匹配相同的词，所以只有在 LLM 改写了查询之后，中文问题才能匹配英文文档。
- **更换来源：** 更换向量来源后，请在文档页点击 **Reindex all documents**。
- **向量库：** 把 `VECTOR_STORE` 设为 `qdrant` 或 `local`。Qdrant 不可用时，检索会回退到本地存储。维度不等于 `EMBEDDING_DIMENSIONS`（256）的向量会使用单独的 Qdrant 集合，例如 `document_chunks_1024d`。

### 联网搜索

```powershell
SEARCH_ENABLED=true
SEARCH_PROVIDER=duckduckgo   # 不需要 API key
# 或者
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=tvly-your-key
SEARCH_TOP_K=5
SEARCH_TIMEOUT_SECONDS=8
```

联网搜索不可用时，`private_plus_web` 仍会依据你的文档作答，`web_only` 则会拒答。

### 环境变量

| 分组 | 变量 |
|---|---|
| 存储 | `DATABASE_URL`、`FILE_STORAGE_PATH`、`MAX_UPLOAD_SIZE_MB` |
| Qdrant | `VECTOR_STORE`、`QDRANT_URL`、`QDRANT_COLLECTION_NAME`、`QDRANT_API_KEY`、`QDRANT_TIMEOUT_SECONDS` |
| LLM | `CHAT_MODEL`、`ROUTER_MODEL`、`ANSWER_MODEL`、`ROUTER_PROVIDER`、`ANSWER_PROVIDER`、`OPENAI_BASE_URL`、`OPENAI_WIRE_API`、`LLM_TIMEOUT_SECONDS` |
| 向量 | `EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`OPENAI_EMBEDDING_MODEL`、`BEDROCK_EMBEDDING_MODEL`、`LOCAL_EMBEDDING_MODEL`、`LOCAL_EMBEDDING_CACHE_DIR` |
| AWS | `AWS_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_SESSION_TOKEN` |
| 检索 | `CHUNK_SIZE_WORDS`、`CHUNK_OVERLAP_WORDS`、`RETRIEVAL_TOP_K`、`RETRIEVAL_SCORE_THRESHOLD` |
| 联网搜索 | `SEARCH_ENABLED`、`SEARCH_PROVIDER`、`SEARCH_API_KEY`、`SEARCH_TOP_K`、`SEARCH_TIMEOUT_SECONDS` |

## API

| 分类 | 接口 |
|---|---|
| 健康检查 | `GET /api/health` |
| 设置 | `GET/PUT /api/settings/llm`、`POST /api/settings/llm/models`、`GET/PUT /api/settings/search` |
| 项目 | `GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{project_id}`、`POST /api/projects/{project_id}/reindex` |
| 文档 | `POST /api/documents/upload`、`GET /api/documents`、`GET/PATCH/DELETE /api/documents/{document_id}`、`POST /api/documents/{document_id}/reindex` |
| 问答 | `POST /api/chat/ask` |
| 对话记录 | `GET /api/conversations`、`GET/DELETE /api/conversations/{conversation_id}` |

## 目录结构

```text
backend/
  app/
    api/routes/      # 健康检查、设置、项目、文档、问答、对话记录
    services/
      agents/        # 路由、检索、联网搜索、答案、引用、编排
      retrieval/     # 查询改写、意图重排、LLM 重排
      llm/           # OpenAI 兼容、Claude、Gemini、Bedrock 客户端
      embeddings/    # 本地（fastembed）、OpenAI、Bedrock、哈希
      vectorstore/   # Qdrant + 本地存储
      parsing/       # PDF、PPTX、DOCX、TXT/MD
      ...
  eval/
    dataset.json     # 91 道带标注的题目
    run_eval.py      # 通过 API 逐题运行并打分
    results/         # 逐题结果和 summary.md
  scripts/
    smoke_test_qdrant.py
  requirements.txt

frontend/
  src/               # 页面：对话、文档、设置

infra/
  docker/
  docker-compose.yml
```

## 局限

- 没有 OCR，没有文字层的扫描版 PDF 无法建立索引。
- 需要多页内容才能回答的问题，答案可能不完整，因为重排通常只保留一到两个块。
- 本地向量库会用 Python 把查询和每个块逐一比较，文档量大时请使用 Qdrant。
- 上传时会同步建立索引。使用本地模型时，在 CPU 上每页约需 0.27 秒。
- 使用外部 LLM 时，你的问题和检索到的段落会被发送给对应的服务商。
- 没有身份认证，请只在自己的电脑上运行。

## 测试

`backend/scripts/smoke_test_qdrant.py` 会连接 PostgreSQL 和 Qdrant（例如由 Docker Compose 启动的实例）做一次端到端检查，依次：

1. 上传一个示例 PDF 和一个示例 PPTX。
2. 检查 SQL 中的记录和 Qdrant 中的向量是否一致。
3. 提两个带过滤条件的问题，并检查它们的引用。
4. 删除 PDF，并检查它没有留下任何内容。

> **警告：** 脚本会先删除所配置数据库中的全部文档。请把 `DATABASE_URL` 指向一个可以随时丢弃的数据库。

```powershell
cd backend
.venv\Scripts\python.exe scripts\smoke_test_qdrant.py
```

评测脚本的说明见[评测](#评测)。
