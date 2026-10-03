"""Evaluate document QA against the labeled questions in eval/dataset.json.

Run from the backend directory:

    .venv\\Scripts\\python.exe eval\\run_eval.py --config offline
    .venv\\Scripts\\python.exe eval\\run_eval.py --config deepseek --judge-model deepseek-v4-pro
    .venv\\Scripts\\python.exe eval\\run_eval.py --config openai --model gpt-5-mini --judge-model gpt-5
    .venv\\Scripts\\python.exe eval\\run_eval.py --summary

API keys are read from DEEPSEEK_API_KEY / OPENAI_API_KEY in the environment or
backend/.env, or from the key saved on the Settings page when its base URL
matches the provider.

Each run ingests the dataset documents into a fresh SQLite database under
storage/eval-run/<config>/ (gitignored), asks every question through
POST /api/chat/ask in private_only mode, and writes eval/results/<config>.json.
--summary rebuilds eval/results/summary.md from the result files.

The source PDFs are not in the repository. --docs-dir points at a folder that
contains them; files are matched by SHA-256, so their names do not matter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = BACKEND_DIR / "eval"
DATASET_PATH = EVAL_DIR / "dataset.json"
RESULTS_DIR = EVAL_DIR / "results"
RUN_ROOT = BACKEND_DIR / "storage" / "eval-run"
DEFAULT_DOCS_DIR = BACKEND_DIR / "storage" / "demo-run" / "live-backend-uploads"
APP_RUNTIME_SETTINGS = BACKEND_DIR / "storage" / "runtime_settings.json"

PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "wire_api": "responses",
        "key_name": "OPENAI_API_KEY",
        "default_model": "gpt-5-mini",
        "embedding_provider": "openai",
    },
    # DeepSeek has no embeddings API, so this config keeps the offline hash embeddings.
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "wire_api": "chat_completions",
        "key_name": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-flash",  # deepseek-chat and deepseek-reasoner now resolve to this model
        "embedding_provider": "deterministic",
    },
}
CONFIGS = ("offline", *PROVIDERS)
EMBEDDING_PROVIDERS = ("deterministic", "local", "openai")
# Column order in summary.md; other result files follow alphabetically.
SUMMARY_ORDER = ("offline", "offline-local", "deepseek-before-fix", "deepseek", "deepseek-local", "openai")
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
REFUSAL_MARKER = "do not have sufficient information"
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
LLM_STAGES = {
    "You rewrite user questions": "rewrite",
    "You are a retrieval reranker": "rerank",
    "You are the answer synthesis agent": "answer",
    "You are a routing agent": "router",
}
# App defaults, pinned so that a local .env cannot change what is evaluated.
PINNED_SETTINGS = {
    "VECTOR_STORE": "local",
    "QDRANT_URL": "",
    "SEARCH_ENABLED": "false",
    "CHUNK_SIZE_WORDS": "220",
    "CHUNK_OVERLAP_WORDS": "40",
    "RETRIEVAL_TOP_K": "5",
    "RETRIEVAL_SCORE_THRESHOLD": "0.3",
    "EMBEDDING_DIMENSIONS": "256",
    "LLM_TIMEOUT_SECONDS": "30",
}

JUDGE_INSTRUCTIONS = """You grade answers from a retrieval-augmented QA system that must answer only from the evidence it was given.

You receive the question, a reference answer written from the source documents (or a note that the documents do not answer the question), the exact evidence passages the system saw, and the system's answer.

Return JSON with:
- refusal: true if the answer says the available sources do not contain enough information to answer the question, even if it also mentions related facts; false if it attempts an answer.
- claims: every factual claim the answer makes about the subject matter. Mark supported = true only if the evidence states the claim or it follows directly from the evidence (rewording and simple arithmetic count). Correct background knowledge that is not in the evidence is NOT supported. Do not list statements about the sources themselves, hedges, or formatting. Use an empty list for a pure refusal.
- correctness: compare the answer with the reference answer. "correct" if it contains the essential points of the reference and nothing that contradicts it; "partial" if it is right but misses essential points, or mixes correct and incorrect content; "incorrect" if it is wrong, misses the point, or refuses a question the reference answers; "not_applicable" when the reference says the documents do not answer the question.
- rationale: one or two sentences explaining the grade.

Judge content, not language: the answer may be in a different language from the reference."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "refusal": {"type": "boolean"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "supported": {"type": "boolean"},
                },
                "required": ["claim", "supported"],
                "additionalProperties": False,
            },
        },
        "correctness": {"type": "string", "enum": ["correct", "partial", "incorrect", "not_applicable"]},
        "rationale": {"type": "string"},
    },
    "required": ["refusal", "claims", "correctness", "rationale"],
    "additionalProperties": False,
}
# Chat Completions providers get JSON mode instead of a strict schema, so spell out the shape.
JUDGE_FORMAT = (
    "\n\nRespond with a JSON object only, in this format:\n"
    '{"refusal": false, "claims": [{"claim": "...", "supported": true}], "correctness": "correct", "rationale": "..."}'
)


class Trace:
    """LLM calls, embedding calls and token usage recorded while one request runs."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.usage: list[dict] = []

    def reset(self) -> None:
        self.calls = []
        self.usage = []


class BufferedResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> BufferedResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    args = parse_args()
    if args.summary:
        print(f"Wrote {write_summary()}")
        return 0
    return run(args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        choices=CONFIGS,
        help="offline: hash embeddings, no LLM. deepseek: hash embeddings + DeepSeek LLM. openai: OpenAI embeddings + LLM.",
    )
    parser.add_argument("--model", help="Chat model for query rewrite, rerank and answers (default depends on --config).")
    parser.add_argument(
        "--embedding-provider",
        choices=EMBEDDING_PROVIDERS,
        help="Override the config's embedding provider, e.g. local for an on-device model.",
    )
    parser.add_argument("--embedding-model", help="Embedding model (default: the app default for the provider).")
    parser.add_argument("--judge-model", help="Grade answers with this model. Omit to skip grading.")
    parser.add_argument("--judge-provider", choices=list(PROVIDERS), help="Provider of the judge model (default: the run's provider).")
    parser.add_argument("--judge-workers", type=int, default=6)
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR))
    parser.add_argument("--name", help="Run name, used for the result file (default: config plus embedding provider if overridden).")
    parser.add_argument("--output", help="Result file path (default: eval/results/<name>.json).")
    parser.add_argument("--note", help="Free-text note shown in summary.md.")
    parser.add_argument("--ids", help="Comma-separated question ids for a partial run; results go to storage/eval-run.")
    parser.add_argument("--summary", action="store_true", help="Rebuild eval/results/summary.md and exit.")
    args = parser.parse_args()
    if args.summary:
        return args
    if not args.config:
        parser.error("--config is required unless --summary is given")
    if args.config in PROVIDERS:
        args.model = args.model or PROVIDERS[args.config]["default_model"]
    default_embedding = PROVIDERS[args.config]["embedding_provider"] if args.config in PROVIDERS else "deterministic"
    args.embedding_provider = args.embedding_provider or default_embedding
    if args.embedding_provider == "openai" and not args.embedding_model:
        args.embedding_model = "text-embedding-3-large"
    if args.embedding_provider == "openai" and args.config != "openai":
        parser.error("OpenAI embeddings need the openai config, which supplies the OpenAI key")
    args.name = args.name or (args.config if args.embedding_provider == default_embedding else f"{args.config}-{args.embedding_provider}")
    if args.judge_model:
        args.judge_provider = args.judge_provider or (args.config if args.config in PROVIDERS else None)
        if not args.judge_provider:
            parser.error("--judge-provider is required to grade the offline config")
    return args


def run(args: argparse.Namespace) -> int:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    questions = dataset["questions"]
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        questions = [question for question in questions if question["id"] in wanted]
    questions_by_id = {question["id"]: question for question in questions}
    documents = locate_documents(dataset, Path(args.docs_dir))
    # Resolve keys up front so a missing key fails before any work is done.
    runtime_settings = build_runtime_settings(args)
    judge_key = resolve_api_key(args.judge_provider) if args.judge_model else None

    run_dir = RUN_ROOT / (f"{args.name}-partial" if args.ids else args.name)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    runtime_settings_path = run_dir / "runtime_settings.json"
    runtime_settings_path.write_text(json.dumps(runtime_settings, indent=2), encoding="utf-8")

    # Settings and the database engine are created at import time, so configure first.
    os.environ.update(PINNED_SETTINGS)
    os.environ.update(
        {
            "DATABASE_URL": f"sqlite:///{(run_dir / 'app.db').as_posix()}",
            "FILE_STORAGE_PATH": (run_dir / "uploads").as_posix(),
            "RUNTIME_SETTINGS_PATH": runtime_settings_path.as_posix(),
        }
    )
    sys.path.insert(0, str(BACKEND_DIR))
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schemas.chat import RetrievedChunkRead
    from app.services.embeddings.embedding_service import EmbeddingService
    from app.services.qa.answer_service import AnswerService
    from app.services.settings.runtime_settings_service import RuntimeSettingsService

    trace = Trace()
    install_instrumentation(trace)
    answer_service = AnswerService()
    embedding_model = RuntimeSettingsService().get_effective_llm_settings().embedding_model
    embedding_dimensions = EmbeddingService().vector_size()

    def format_evidence(chunks: list[dict]) -> str:
        # Same formatting the answer agent uses, so the judge sees exactly what the model saw.
        return answer_service._format_internal_evidence([RetrievedChunkRead(**chunk) for chunk in chunks])

    started_at = datetime.now(timezone.utc)
    try:
        with TestClient(app) as client:
            project = client.post("/api/projects", json={"name": "Evaluation"})
            project.raise_for_status()
            project_id = project.json()["id"]
            ingestion = ingest_documents(client, project_id, dataset, documents, trace)
            records = ask_questions(client, project_id, questions, questions_by_id, trace, format_evidence)
    finally:
        runtime_settings_path.unlink(missing_ok=True)  # contains the API key

    judge_usage: list[dict] = []
    if args.judge_model:
        judge_usage = judge_records(records, questions_by_id, args, judge_key)

    provider = PROVIDERS.get(args.config)
    result = {
        "run": {
            "name": args.name,
            "note": args.note,
            "config": args.config,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": git_commit(),
            "dataset": dataset["name"],
            "dataset_sha256": sha256_file(DATASET_PATH)[:12],
            "questions": len(records),
            "mode": "private_only",
            "vector_store": "local",
            "embedding": "deterministic hashing" if args.embedding_provider == "deterministic" else f"{args.embedding_provider}: {embedding_model}",
            "embedding_dimensions": embedding_dimensions,
            "retrieval_top_k": int(PINNED_SETTINGS["RETRIEVAL_TOP_K"]),
            "llm_timeout_seconds": int(PINNED_SETTINGS["LLM_TIMEOUT_SECONDS"]),
            "answer_model": args.model if provider else None,
            "judge_model": args.judge_model,
            "judge_provider": args.judge_provider if args.judge_model else None,
            "model_snapshots": sorted(
                {item["model"] for item in collect_usage(records, ingestion, judge_usage) if item.get("model")}
            ),
        },
        "ingestion": ingestion,
        "metrics": compute_metrics(records, questions_by_id),
        "llm_calls": summarize_calls(records),
        "tokens": summarize_tokens(collect_usage(records, ingestion, judge_usage)),
        "records": [{key: value for key, value in record.items() if not key.startswith("_")} for record in records],
    }

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = run_dir / "results.json" if args.ids else RESULTS_DIR / f"{args.name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output_path}")
    if output_path.parent == RESULTS_DIR.resolve():
        print(f"Wrote {write_summary()}")
    return 0


def build_runtime_settings(args: argparse.Namespace) -> dict:
    settings: dict = {
        "provider_name": "openai",  # the app's OpenAI-compatible client
        "embedding_provider": args.embedding_provider,
        "vector_store": "local",
        "search_enabled": False,
    }
    if args.config == "offline":
        settings.update({"router_provider": "heuristic", "answer_provider": "extractive"})
    else:
        provider = PROVIDERS[args.config]
        settings.update(
            {
                "api_key": resolve_api_key(args.config),
                "base_url": provider["base_url"],
                "wire_api": provider["wire_api"],
                "chat_model": args.model,
                "router_model": args.model,
                "answer_model": args.model,
                "router_provider": "llm",
                "answer_provider": "llm",
            }
        )
    if args.embedding_model:
        settings["embedding_model"] = args.embedding_model
    return settings


def resolve_api_key(provider_name: str) -> str:
    provider = PROVIDERS[provider_name]
    key_name = provider["key_name"]
    key = os.environ.get(key_name, "").strip() or read_env_file(BACKEND_DIR / ".env").get(key_name, "")
    if key:
        return key
    if APP_RUNTIME_SETTINGS.exists():
        stored = json.loads(APP_RUNTIME_SETTINGS.read_text(encoding="utf-8"))
        same_host = urlparse(str(stored.get("base_url") or "")).hostname == urlparse(provider["base_url"]).hostname
        if same_host and str(stored.get("api_key") or "").strip():
            return str(stored["api_key"]).strip()
    raise SystemExit(f"No API key for {provider_name}. Add {key_name}=... to backend/.env (gitignored) or save the key on the Settings page.")


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip("\"'")
    return values


def locate_documents(dataset: dict, docs_dir: Path) -> dict[str, Path]:
    wanted = {document["sha256"]: document["filename"] for document in dataset["documents"]}
    found: dict[str, Path] = {}
    for path in sorted(docs_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".pdf", ".pptx", ".docx", ".txt", ".md"}:
            filename = wanted.get(sha256_file(path))
            if filename and filename not in found:
                found[filename] = path
    missing = [document["filename"] for document in dataset["documents"] if document["filename"] not in found]
    if missing:
        raise SystemExit(f"Not found in {docs_dir} (matched by SHA-256): {', '.join(missing)}")
    return found


def install_instrumentation(trace: Trace) -> None:
    """Record timing and token usage of the app's LLM and embedding calls.

    The wrappers only add bookkeeping: return values and exceptions pass through unchanged.
    """
    import app.services.embeddings.openai_embedding_client as embedding_module
    import app.services.llm.openai_compatible_client as chat_module
    from app.services.embeddings.embedding_service import EmbeddingService
    from app.services.llm.multi_provider_client import MultiProviderChatClient

    original_complete = MultiProviderChatClient.complete
    real_urlopen = chat_module.urlopen

    def timed_complete(self, *, system_prompt: str, user_prompt: str, model: str | None = None, temperature: float | None = None) -> str:
        stage = next((name for prefix, name in LLM_STAGES.items() if system_prompt.startswith(prefix)), "other")
        started = time.perf_counter()
        call = {"stage": stage, "error": None}
        try:
            output = original_complete(self, system_prompt=system_prompt, user_prompt=user_prompt, model=model, temperature=temperature)
            if stage == "rewrite":
                call["output"] = output[:300]
            return output
        except Exception as exc:
            call["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            raise
        finally:
            call["seconds"] = round(time.perf_counter() - started, 3)
            trace.calls.append(call)

    def timed_embedding(method):
        # Wraps embed_texts (chunks) and embed_query (one question) alike.
        def wrapper(self, value):
            started = time.perf_counter()
            error = None
            try:
                return method(self, value)
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:200]}"
                raise
            finally:
                trace.calls.append(
                    {
                        "stage": "embed",
                        "seconds": round(time.perf_counter() - started, 3),
                        "error": error,
                        "inputs": len(value) if isinstance(value, list) else 1,
                    }
                )

        return wrapper

    def recording_urlopen(request, timeout=None):
        with real_urlopen(request, timeout=timeout) as response:
            body = response.read()
        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
            trace.usage.append({"model": payload.get("model"), **normalize_usage(payload["usage"])})
        return BufferedResponse(body)

    MultiProviderChatClient.complete = timed_complete
    EmbeddingService.embed_texts = timed_embedding(EmbeddingService.embed_texts)
    EmbeddingService.embed_query = timed_embedding(EmbeddingService.embed_query)
    chat_module.urlopen = recording_urlopen
    embedding_module.urlopen = recording_urlopen


def ingest_documents(client, project_id: str, dataset: dict, documents: dict[str, Path], trace: Trace) -> list[dict]:
    results: list[dict] = []
    for document in dataset["documents"]:
        path = documents[document["filename"]]
        trace.reset()
        started = time.perf_counter()
        try:
            with path.open("rb") as handle:
                response = client.post(
                    "/api/documents/upload",
                    data={"project_id": project_id},
                    files={"file": (document["filename"], handle, CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"))},
                )
        except Exception as exc:
            raise SystemExit(f"Indexing {document['filename']} failed: {type(exc).__name__}: {str(exc)[:500]}") from None
        seconds = time.perf_counter() - started
        if response.status_code != 201:
            raise SystemExit(f"Upload of {document['filename']} failed: {response.status_code} {response.text[:300]}")
        detail = client.get(f"/api/documents/{response.json()['document_id']}").json()
        results.append(
            {
                "filename": document["filename"],
                "pages": detail.get("page_count"),
                "chunks": detail.get("chunk_count"),
                "seconds": round(seconds, 2),
                "usage": trace.usage,
            }
        )
        print(f"Indexed {document['filename']}: {detail.get('chunk_count')} chunks in {seconds:.1f}s", flush=True)
    return results


def ask_questions(client, project_id: str, questions: list[dict], questions_by_id: dict, trace: Trace, format_evidence) -> list[dict]:
    records: list[dict] = []
    consecutive_errors = 0
    for index, question in enumerate(questions, start=1):
        trace.reset()
        started = time.perf_counter()
        try:
            response = client.post(
                "/api/chat/ask",
                json={"project_id": project_id, "question": question["question"], "mode": "private_only"},
            )
            error = None if response.status_code == 200 else f"HTTP {response.status_code}: {response.text[:500]}"
        except Exception as exc:  # TestClient re-raises exceptions from inside the app
            response = None
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        latency = time.perf_counter() - started
        record = {
            "id": question["id"],
            "split": question["split"],
            "lang": question["lang"],
            "question": question["question"],
            "latency_s": round(latency, 3),
            "llm_calls": trace.calls,
            "usage": trace.usage,
        }
        if error is None:
            body = response.json()
            chunks = body["retrieved_chunks"]
            record.update(
                {
                    "retrieved": [
                        {"filename": chunk["filename"], "page": chunk["page_number"] or chunk["slide_number"], "score": chunk["score"]}
                        for chunk in chunks
                    ],
                    "citations": [
                        {"filename": citation["title"], "page": citation["page_number"] or citation["slide_number"]}
                        for citation in body["citations"]
                        if citation["source_kind"] == "document_chunk"
                    ],
                    "answer": body["answer"],
                    "answer_path": answer_path(trace.calls, chunks),
                    "_evidence": format_evidence(chunks) if chunks else "",
                }
            )
        else:
            record.update({"retrieved": [], "citations": [], "answer": None, "error": error})
        records.append(record)

        rank = first_gold_rank(record, gold_keys(questions_by_id[question["id"]]))
        print(
            f"[{index}/{len(questions)}] {question['id']} {latency:.1f}s "
            f"chunks={len(record['retrieved'])} gold_rank={rank or '-'} path={record.get('answer_path', 'error')}",
            flush=True,
        )
        consecutive_errors = consecutive_errors + 1 if error else 0
        if consecutive_errors >= 3:
            raise SystemExit(f"Stopping after 3 failed requests in a row. Last error: {error}")
    return records


def answer_path(calls: list[dict], chunks: list[dict]) -> str:
    if not chunks:
        return "no_evidence"
    if any(call["stage"] == "answer" and call["error"] is None for call in calls):
        return "llm"
    return "extractive"


def judge_records(records: list[dict], questions_by_id: dict, args: argparse.Namespace, api_key: str) -> list[dict]:
    provider = PROVIDERS[args.judge_provider]
    pending = [record for record in records if record.get("answer") is not None]
    usage: list[dict] = []

    def grade(record: dict) -> tuple[dict, dict | None, dict | None, str | None]:
        try:
            prompt = build_judge_prompt(questions_by_id[record["id"]], record)
            verdict, call_usage = call_judge(provider, api_key, args.judge_model, prompt)
            return record, verdict, call_usage, None
        except Exception as exc:
            return record, None, None, f"{type(exc).__name__}: {str(exc)[:300]}"

    with ThreadPoolExecutor(max_workers=args.judge_workers) as pool:
        futures = [pool.submit(grade, record) for record in pending]
        for done, future in enumerate(as_completed(futures), start=1):
            record, verdict, call_usage, error = future.result()
            if verdict is not None:
                record["judge"] = verdict
                usage.append(call_usage)
            else:
                record["judge_error"] = error
            print(f"Judged {done}/{len(pending)} {record['id']}{' ERROR ' + error if error else ''}", flush=True)
    return usage


def build_judge_prompt(question: dict, record: dict) -> str:
    reference = question.get("reference") or (
        "The source documents do not answer this question. "
        "The correct behaviour is to say that the available information is insufficient."
    )
    evidence = record.get("_evidence") or "(no evidence was retrieved)"
    return (
        f"Question:\n{question['question']}\n\n"
        f"Reference answer:\n{reference}\n\n"
        f"Evidence given to the system:\n{evidence}\n\n"
        f"System answer:\n{record['answer']}"
    )


def call_judge(provider: dict, api_key: str, model: str, prompt: str) -> tuple[dict, dict]:
    if provider["wire_api"] == "responses":
        url = f"{provider['base_url']}/responses"
        payload = {
            "model": model,
            "instructions": JUDGE_INSTRUCTIONS,
            "input": prompt,
            "text": {"format": {"type": "json_schema", "name": "rag_grade", "schema": JUDGE_SCHEMA, "strict": True}},
        }
    else:
        url = f"{provider['base_url']}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": JUDGE_INSTRUCTIONS + JUDGE_FORMAT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
    last_error = "unknown error"
    for attempt in range(5):
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
            usage = {"model": result.get("model"), **normalize_usage(result.get("usage") or {})}
            return parse_verdict(response_text(result)), usage
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')[:300]}"
            if exc.code == 400 and payload.pop("response_format", None):
                continue  # model rejects JSON mode; rely on the format given in the prompt
            if exc.code not in RETRYABLE_STATUS:
                break
        except (OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError(f"Judge request failed: {last_error}")


def response_text(result: dict) -> str:
    if "choices" in result:
        message = (result["choices"] or [{}])[0].get("message") or {}
        return str(message.get("content") or "")
    return "".join(
        part.get("text", "")
        for item in result.get("output") or []
        if isinstance(item, dict)
        for part in item.get("content") or []
        if isinstance(part, dict) and part.get("type") == "output_text"
    )


def parse_verdict(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    verdict = json.loads(text[start : end + 1]) if 0 <= start < end else None
    valid = (
        isinstance(verdict, dict)
        and isinstance(verdict.get("refusal"), bool)
        and isinstance(verdict.get("claims"), list)
        and all(
            isinstance(claim, dict) and isinstance(claim.get("claim"), str) and isinstance(claim.get("supported"), bool)
            for claim in verdict["claims"]
        )
        and verdict.get("correctness") in {"correct", "partial", "incorrect", "not_applicable"}
    )
    if not valid:
        raise ValueError(f"Judge returned an invalid verdict: {text[:200]!r}")
    verdict["rationale"] = str(verdict.get("rationale") or "")
    return verdict


def normalize_usage(usage: dict) -> dict:
    details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
    }


def gold_keys(question: dict) -> set[tuple[str, int]]:
    return {(gold["filename"].lower(), page) for gold in question["gold"] for page in gold["pages"]}


def first_gold_rank(record: dict, gold: set[tuple[str, int]]) -> int | None:
    for rank, chunk in enumerate(record["retrieved"], start=1):
        if (chunk["filename"].lower(), chunk["page"]) in gold:
            return rank
    return None


def is_refusal(record: dict) -> bool:
    if record.get("judge"):
        return bool(record["judge"]["refusal"])
    return record.get("answer") is None or REFUSAL_MARKER in record["answer"].lower()


def all_claims_supported(record: dict) -> bool:
    return all(claim["supported"] for claim in record["judge"]["claims"])


def compute_metrics(records: list[dict], questions_by_id: dict) -> dict:
    metrics: dict[str, dict] = {}
    for split in ("heldout", "dev"):
        subset = [record for record in records if record["split"] == split]
        if subset:
            metrics[split] = answerable_metrics(subset, questions_by_id)
    for lang in ("en", "zh"):
        subset = [record for record in records if record["split"] == "heldout" and record["lang"] == lang]
        if subset:
            metrics[f"heldout_{lang}"] = answerable_metrics(subset, questions_by_id)
    unanswerable = [record for record in records if record["split"] == "unanswerable"]
    if unanswerable:
        metrics["unanswerable"] = unanswerable_metrics(unanswerable)
    metrics["all"] = {
        "n": len(records),
        "failed_requests": sum(1 for record in records if record.get("error")),
        "latency_s": latency_stats(records),
    }
    return metrics


def answerable_metrics(records: list[dict], questions_by_id: dict) -> dict:
    total = len(records)
    gold_by_id = {record["id"]: gold_keys(questions_by_id[record["id"]]) for record in records}
    ranks = [first_gold_rank(record, gold_by_id[record["id"]]) for record in records]
    citations = [(record["id"], citation) for record in records for citation in record["citations"]]
    gold_citations = sum(1 for record_id, citation in citations if (citation["filename"].lower(), citation["page"]) in gold_by_id[record_id])
    metrics = {
        "n": total,
        "hit@1": proportion(sum(1 for rank in ranks if rank and rank <= 1), total),
        "hit@3": proportion(sum(1 for rank in ranks if rank and rank <= 3), total),
        "hit@5": proportion(sum(1 for rank in ranks if rank and rank <= 5), total),
        "mrr@5": round(sum(1 / rank for rank in ranks if rank and rank <= 5) / total, 4),
        "no_chunks_retrieved": proportion(sum(1 for record in records if not record["retrieved"]), total),
        "citation_hit": proportion(
            sum(
                1
                for record in records
                if any((citation["filename"].lower(), citation["page"]) in gold_by_id[record["id"]] for citation in record["citations"])
            ),
            total,
        ),
        "citation_precision": proportion(gold_citations, len(citations)),
        "refused": proportion(sum(1 for record in records if is_refusal(record)), total),
        "latency_s": latency_stats(records),
    }
    judged = [record for record in records if record.get("judge")]
    if judged:
        answered = [record for record in judged if not record["judge"]["refusal"]]
        claims = [claim for record in answered for claim in record["judge"]["claims"]]
        metrics.update(
            {
                "judged": len(judged),
                "correct": proportion(sum(1 for record in judged if record["judge"]["correctness"] == "correct"), len(judged)),
                "partially_correct": proportion(sum(1 for record in judged if record["judge"]["correctness"] == "partial"), len(judged)),
                "grounded_answers": proportion(sum(1 for record in answered if all_claims_supported(record)), len(answered)),
                "supported_claims": proportion(sum(1 for claim in claims if claim["supported"]), len(claims)),
            }
        )
    return metrics


def unanswerable_metrics(records: list[dict]) -> dict:
    total = len(records)
    metrics = {
        "n": total,
        "refused": proportion(sum(1 for record in records if is_refusal(record)), total),
        "no_chunks_retrieved": proportion(sum(1 for record in records if not record["retrieved"]), total),
        "latency_s": latency_stats(records),
    }
    judged = [record for record in records if record.get("judge")]
    if judged:
        metrics.update(
            {
                "judged": len(judged),
                "answered_with_unsupported_claims": proportion(
                    sum(1 for record in judged if not record["judge"]["refusal"] and not all_claims_supported(record)),
                    len(judged),
                ),
            }
        )
    return metrics


def proportion(count: int, total: int) -> dict:
    return {
        "count": count,
        "total": total,
        "rate": round(count / total, 4) if total else None,
        "ci95": wilson_interval(count, total),
    }


def wilson_interval(count: int, total: int, z: float = 1.96) -> list[float] | None:
    if not total:
        return None
    rate = count / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - half_width), 4), round(min(1.0, centre + half_width), 4)]


def latency_stats(records: list[dict]) -> dict:
    values = sorted(record["latency_s"] for record in records)
    if not values:
        return {}
    nearest_rank_p90 = values[max(0, math.ceil(0.9 * len(values)) - 1)]
    return {
        "median": round(statistics.median(values), 3),
        "p90": round(nearest_rank_p90, 3),
        "mean": round(statistics.mean(values), 3),
        "max": round(values[-1], 3),
    }


def summarize_calls(records: list[dict]) -> dict:
    stages: dict[str, dict] = {}
    for record in records:
        for call in record["llm_calls"]:
            entry = stages.setdefault(call["stage"], {"calls": 0, "errors": 0, "seconds": []})
            entry["calls"] += 1
            entry["errors"] += 1 if call["error"] else 0
            entry["seconds"].append(call["seconds"])
    return {
        stage: {
            "calls": entry["calls"],
            "errors": entry["errors"],
            "questions_with_call": sum(1 for record in records if any(call["stage"] == stage for call in record["llm_calls"])),
            "median_seconds": round(statistics.median(entry["seconds"]), 2),
            "mean_seconds": round(statistics.mean(entry["seconds"]), 2),
        }
        for stage, entry in sorted(stages.items())
    }


def collect_usage(records: list[dict], ingestion: list[dict], judge_usage: list[dict]) -> list[dict]:
    return [
        *(item for document in ingestion for item in document["usage"]),
        *(item for record in records for item in record["usage"]),
        *judge_usage,
    ]


def summarize_tokens(usage: list[dict]) -> dict:
    totals: dict[str, dict] = {}
    for item in usage:
        entry = totals.setdefault(item.get("model") or "unknown", {"requests": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0})
        entry["requests"] += 1
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            entry[key] += item[key]
    return totals


def write_summary() -> Path:
    paths = sorted(
        RESULTS_DIR.glob("*.json"),
        key=lambda path: (SUMMARY_ORDER.index(path.stem) if path.stem in SUMMARY_ORDER else len(SUMMARY_ORDER), path.stem),
    )
    runs = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in paths}
    if not runs:
        raise SystemExit(f"No result files in {RESULTS_DIR}")
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    names = list(runs)
    counts = {split: sum(1 for question in dataset["questions"] if question["split"] == split) for split in ("heldout", "dev", "unanswerable")}
    pages = sum(document["pages"] for document in dataset["documents"])

    def table(rows: list[tuple[str, str, object]]) -> list[str]:
        lines = [f"| Metric | {' | '.join(names)} |", f"|---|{'---|' * len(names)}"]
        for label, section, getter in rows:
            cells = []
            for name in names:
                metrics = runs[name]["metrics"].get(section)
                cells.append(getter(metrics) if metrics else "-")
            lines.append(f"| {label} | {' | '.join(cells)} |")
        return lines

    def rate(key: str):
        def getter(metrics: dict) -> str:
            value = metrics.get(key)
            if not value or value["rate"] is None:
                return "-"
            low, high = value["ci95"]
            return f"{value['rate']:.1%} ({value['count']}/{value['total']}) [{low:.0%}-{high:.0%}]"

        return getter

    def number(key: str):
        return lambda metrics: f"{metrics[key]:.3f}" if key in metrics else "-"

    def seconds(value: float) -> str:
        return f"{value * 1000:.0f} ms" if value < 1 else f"{value:.1f} s"

    def latency(metrics: dict) -> str:
        stats = metrics.get("latency_s") or {}
        return f"{seconds(stats['median'])} / {seconds(stats['p90'])}" if stats else "-"

    answerable_rows = [
        ("Retrieval hit@1", "{split}", rate("hit@1")),
        ("Retrieval hit@3", "{split}", rate("hit@3")),
        ("Retrieval hit@5", "{split}", rate("hit@5")),
        ("MRR@5", "{split}", number("mrr@5")),
        ("No chunks retrieved", "{split}", rate("no_chunks_retrieved")),
        ("A cited page is a gold page", "{split}", rate("citation_hit")),
        ("Citation precision", "{split}", rate("citation_precision")),
        ("Refused to answer", "{split}", rate("refused")),
        ("Answer correct (judge)", "{split}", rate("correct")),
        ("Answer partially correct (judge)", "{split}", rate("partially_correct")),
        ("Answers with every claim supported (judge)", "{split}", rate("grounded_answers")),
        ("Claims supported by evidence (judge)", "{split}", rate("supported_claims")),
        ("Latency median / p90", "{split}", latency),
    ]

    def rows_for(split: str) -> list[tuple[str, str, object]]:
        return [(label, section.format(split=split), getter) for label, section, getter in answerable_rows]

    lines = [
        "# Evaluation Summary",
        "",
        f"Dataset `{dataset['name']}`: {len(dataset['questions'])} questions over {len(dataset['documents'])} PDFs ({pages} pages). "
        "Generated by `eval/run_eval.py`; per-question results are in the JSON files next to this one.",
        "",
        "Rates show count/total and a 95% Wilson interval in brackets. Hit@k means a page that contains the answer "
        "is among the top k retrieved chunks. Judge metrics come from an LLM grader and are only present when a judge model was set.",
        "",
        f"## Held-out questions (n={counts['heldout']})",
        "",
        "Written for this evaluation; the retrieval code was not tuned on them.",
        "",
        *table(rows_for("heldout")),
        "",
        "### By question language",
        "",
        *table(
            [
                ("Hit@5, English", "heldout_en", rate("hit@5")),
                ("Hit@5, Chinese", "heldout_zh", rate("hit@5")),
                ("Correct, English (judge)", "heldout_en", rate("correct")),
                ("Correct, Chinese (judge)", "heldout_zh", rate("correct")),
            ]
        ),
        "",
        f"## Dev questions (n={counts['dev']})",
        "",
        "Asked during development. `retrieval_service.py` contains rules written for these questions, so they overstate quality.",
        "",
        *table(rows_for("dev")),
        "",
        f"## Unanswerable questions (n={counts['unanswerable']})",
        "",
        "Not covered by any document; the correct behaviour is to refuse.",
        "",
        *table(
            [
                ("Refused (correct)", "unanswerable", rate("refused")),
                ("Answered with unsupported claims (judge)", "unanswerable", rate("answered_with_unsupported_claims")),
                ("Latency median / p90", "unanswerable", latency),
            ]
        ),
        "",
        "## Runs",
        "",
        f"| | {' | '.join(names)} |",
        f"|---|{'---|' * len(names)}",
    ]
    run_rows = [
        ("Note", lambda result: result["run"].get("note") or "-"),
        ("Answer model", lambda result: result["run"]["answer_model"] or "none (extractive)"),
        ("Judge model", lambda result: result["run"]["judge_model"] or "none"),
        ("Model snapshots", lambda result: ", ".join(result["run"]["model_snapshots"]) or "-"),
        ("Embeddings", lambda result: f"{result['run']['embedding']} ({result['run']['embedding_dimensions']}-d)"),
        ("Vector store / mode", lambda result: f"{result['run']['vector_store']} / {result['run']['mode']}"),
        ("Failed requests", lambda result: str(result["metrics"]["all"].get("failed_requests", 0))),
        ("Chunks indexed", lambda result: str(sum(document["chunks"] for document in result["ingestion"]))),
        ("Indexing time", lambda result: f"{sum(document['seconds'] for document in result['ingestion']):.1f} s"),
        (
            "Model calls while answering, by stage (errors)",
            lambda result: ", ".join(f"{stage} {entry['calls']} ({entry['errors']})" for stage, entry in result["llm_calls"].items()) or "-",
        ),
        ("Git commit", lambda result: result["run"]["git_commit"] or "-"),
        ("Finished", lambda result: result["run"]["finished_at"]),
    ]
    for label, getter in run_rows:
        lines.append(f"| {label} | {' | '.join(getter(runs[name]) for name in names)} |")
    lines.append("")

    summary_path = RESULTS_DIR / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def git_commit() -> str | None:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND_DIR, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=BACKEND_DIR, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit} (uncommitted changes)" if dirty else commit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
