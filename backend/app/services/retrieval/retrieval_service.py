import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.chat import RetrievedChunkRead
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.llm.base import LLMClient
from app.services.llm.multi_provider_client import MultiProviderChatClient
from app.services.vectorstore.base import VectorSearchHit
from app.services.vectorstore.factory import get_vector_store
from app.utils.text import extract_keywords, split_sentences

logger = logging.getLogger(__name__)

RETRIEVAL_META_TERMS = {
    "uploaded",
    "upload",
    "document",
    "documents",
    "file",
    "files",
    "pdf",
    "pdfs",
    "ppt",
    "pptx",
    "slides",
    "slide",
    "web",
    "search",
    "compare",
    "comparison",
    "general",
    "current",
    "recent",
    "latest",
    "explain",
    "explanation",
}

USES_MARKERS = {
    "uses",
    "uses of",
    "uses for",
    "used for",
    "purpose",
    "purposes",
    "application",
    "applications",
    "main uses",
    "main use",
    "用途",
    "作用",
    "用于",
    "用来",
    "应用",
    "目的",
}

DEFINITION_MARKERS = {
    " is ",
    " are ",
    "refers to",
    "defined as",
    "means",
    "is called",
    "是",
    "指的是",
    "定义",
}

REFERENCE_PATTERN = re.compile(r"\b(?:it|those|them|that one|first point|second point)\b", re.IGNORECASE)

FORMULA_MARKERS = {
    "formula",
    "equation",
    "mathematical form",
    "model form",
    "matrix form",
    "formulation",
    "notation",
    "公式",
    "数学形式",
    "數學形式",
    "矩阵形式",
    "矩陣形式",
    "表达式",
    "寫成",
    "写成",
}


@dataclass(slots=True)
class QuestionIntentProfile:
    intent: str
    keywords: set[str]
    support_markers: tuple[str, ...]
    support_threshold: float


@dataclass(slots=True)
class ScoredHit:
    hit: object
    support_score: float
    marker_match: bool

class RetrievalService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        settings = get_settings()
        self.top_k = settings.retrieval_top_k
        self.score_threshold = settings.retrieval_score_threshold
        self.embedding_service = EmbeddingService(dimensions=settings.embedding_dimensions)
        self.llm_client = llm_client or MultiProviderChatClient()

    def retrieve(
        self,
        db: Session,
        question: str,
        conversation_context: str | None = None,
        project_id: str | None = None,
        selected_document_ids: list[str] | None = None,
        file_type: str | None = None,
    ) -> list[RetrievedChunkRead]:
        profile = self._build_question_profile(question)
        query_text = self._compose_query_text(
            question=question,
            conversation_context=conversation_context,
            profile=profile,
        )
        rewritten_query = self._rewrite_query(question=question, conversation_context=conversation_context)
        if rewritten_query:
            query_text = self._compose_query_text(
                question=rewritten_query,
                conversation_context=conversation_context,
                original_question=question,
                profile=profile,
            )
        query_embedding = self.embedding_service.embed_query(query_text)
        candidate_k = max(self.top_k * 4, 12)
        if profile.intent == "formula":
            candidate_k = max(candidate_k, 24)
        hits = get_vector_store().search(
            db=db,
            query_embedding=query_embedding,
            top_k=candidate_k,
            query_text=query_text,
            project_id=project_id,
            document_ids=selected_document_ids or [],
            file_type=file_type,
        )
        if profile.intent == "formula":
            hits = self._augment_formula_candidates(
                db=db,
                query_text=query_text,
                project_id=project_id,
                selected_document_ids=selected_document_ids or [],
                file_type=file_type,
                existing_hits=hits,
            )
        candidate_floor = max(self.score_threshold * 0.45, 0.12)
        candidate_hits = [hit for hit in hits if hit.score >= candidate_floor]
        reranked_hits = self._rerank_hits(question=question, hits=candidate_hits, rewritten_query=rewritten_query)
        if profile.intent != "formula":
            reranked_hits = self._rerank_with_llm(question=question, hits=reranked_hits)
        return [
            RetrievedChunkRead(
                chunk_id=hit.chunk.id,
                document_id=hit.chunk.document_id,
                filename=hit.chunk.document.filename,
                score=round(score, 4),
                content=hit.chunk.content,
                content_preview=hit.chunk.content_preview or hit.chunk.content,
                page_number=hit.chunk.page_number,
                slide_number=hit.chunk.slide_number,
            )
            for hit, score in reranked_hits
        ]

    def _augment_formula_candidates(
        self,
        db: Session,
        query_text: str,
        project_id: str | None,
        selected_document_ids: list[str],
        file_type: str | None,
        existing_hits: list[VectorSearchHit],
    ) -> list[VectorSearchHit]:
        query_keywords = extract_keywords(query_text)
        existing_by_chunk_id = {hit.chunk.id: hit for hit in existing_hits}

        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "indexed")
        )
        if project_id:
            statement = statement.where(Document.project_id == project_id)
        if selected_document_ids:
            statement = statement.where(Document.id.in_(selected_document_ids))
        if file_type:
            statement = statement.where(Document.file_type == file_type)

        supplemental_hits: list[VectorSearchHit] = []
        for chunk in db.scalars(statement).all():
            if chunk.id in existing_by_chunk_id:
                continue
            content = chunk.content
            lowered = content.lower()
            if not any(marker in lowered for marker in (" = ", "~", "∼", "normal(", "poisson(", "logit(", "xβ", "identity link", "appendix", "we can write")):
                continue

            content_keywords = extract_keywords(content)
            overlap = self._overlap_ratio(query_keywords, content_keywords)
            if overlap <= 0:
                continue

            lexical_score = 0.35 + (0.4 * overlap)
            if "xβ" in content or "Xβ" in content or "μ = Xβ" in content or "mu = x" in lowered:
                lexical_score += 0.25
            if "appendix" in lowered or "we can write" in lowered:
                lexical_score += 0.15
            if "normal regression" in lowered or "ordinary regression" in lowered:
                lexical_score += 0.12

            if lexical_score >= 0.55:
                supplemental_hits.append(VectorSearchHit(chunk=chunk, score=min(0.99, lexical_score)))

        if not supplemental_hits:
            return existing_hits

        merged = [*existing_hits, *supplemental_hits]
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[: max(len(existing_hits), self.top_k * 6)]

    def _compose_query_text(
        self,
        question: str,
        conversation_context: str | None,
        original_question: str | None = None,
        profile: QuestionIntentProfile | None = None,
    ) -> str:
        question_keywords = sorted(
            keyword for keyword in extract_keywords(question) if keyword not in RETRIEVAL_META_TERMS
        )
        parts = [f"Current question: {question}"]
        if original_question and original_question.strip() and original_question.strip() != question.strip():
            parts.append(f"Original user wording: {original_question}")
        if question_keywords:
            parts.append(f"Core retrieval terms: {' '.join(question_keywords[:12])}")
        if profile and profile.intent == "formula":
            parts.append("Formula-focused retrieval terms: equation formula mathematical form matrix form notation general representation")
            lowered = question.lower()
            if "glm" in lowered or "广义线性模型" in question or "廣義線性模型" in question:
                parts.append("Model family hint: generalized linear model glm")
            if "normal" in lowered or "gaussian" in lowered or "正态" in question or "正態" in question:
                parts.append("Model-specific hint: normal regression gaussian identity link")
            if "regression" in lowered or "回归" in question or "回歸" in question:
                parts.append("Equation hint: Y ~ Normal(mu, sigma^2 I_n), mu = X beta")

        if conversation_context:
            context_keywords = sorted(
                keyword for keyword in extract_keywords(conversation_context) if keyword not in RETRIEVAL_META_TERMS
            )
            if context_keywords:
                parts.append(f"Conversation context terms: {' '.join(context_keywords[:12])}")

        return "\n".join(parts)

    def _rewrite_query(self, question: str, conversation_context: str | None) -> str | None:
        if not self._needs_query_rewrite(question=question, conversation_context=conversation_context):
            return None
        if not self.llm_client.is_configured():
            return None

        system_prompt = (
            "You rewrite user questions into a standalone retrieval query for document search. "
            "Resolve references using the provided conversation context. "
            "When the user writes in Chinese or another language but the documents may be in English, produce a concise English retrieval query. "
            "If the user asks for a mathematical form or formula, include terms such as formula, equation, matrix form, or notation. "
            "Preserve exact technical terms. Return only the rewritten query."
        )
        user_prompt = (
            f"Current question:\n{question}\n\n"
            f"Conversation context:\n{conversation_context or 'None'}\n\n"
            "Rewrite this into a single standalone retrieval query."
        )
        try:
            rewritten = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            ).strip()
        except Exception:
            return None
        return rewritten or None

    def _needs_query_rewrite(self, question: str, conversation_context: str | None) -> bool:
        if re.search("[\u4e00-\u9fff]", question):
            return True
        if REFERENCE_PATTERN.search(question):
            return True
        if len(extract_keywords(question)) <= 2 and conversation_context:
            return True
        return False

    def _rerank_hits(self, question: str, hits, rewritten_query: str | None = None) -> list[tuple]:
        if not hits:
            return []

        profile = self._build_question_profile(question)
        if rewritten_query:
            # A Chinese question shares no words with English documents; also score against its English rewrite.
            profile.keywords |= {
                keyword for keyword in extract_keywords(rewritten_query) if keyword not in RETRIEVAL_META_TERMS
            }
        rescored_hits: list[ScoredHit] = []
        for hit in hits:
            support_score, marker_match = self._support_score(
                profile=profile,
                content=hit.chunk.content,
                base_score=hit.score,
            )
            if support_score >= profile.support_threshold:
                rescored_hits.append(
                    ScoredHit(
                        hit=hit,
                        support_score=support_score,
                        marker_match=marker_match,
                    )
                )

        if not rescored_hits:
            return []

        if profile.intent == "uses":
            rescored_hits = self._filter_uses_hits(rescored_hits)
            if not rescored_hits:
                return []
        elif profile.intent == "definition":
            rescored_hits = self._filter_definition_hits(rescored_hits, profile)
            if not rescored_hits:
                return []
        elif profile.intent == "formula":
            rescored_hits = self._filter_formula_hits(rescored_hits, profile)
            if not rescored_hits:
                return []

        rescored_hits.sort(key=lambda item: item.support_score, reverse=True)
        return [(item.hit, item.support_score) for item in rescored_hits[: self.top_k]]

    def _build_question_profile(self, question: str) -> QuestionIntentProfile:
        lowered = question.lower()
        keywords = {
            keyword
            for keyword in extract_keywords(question)
            if keyword not in RETRIEVAL_META_TERMS
        }
        if self._is_uses_question(question=question, lowered=lowered):
            return QuestionIntentProfile(
                intent="uses",
                keywords=keywords,
                support_markers=tuple(USES_MARKERS),
                support_threshold=max(self.score_threshold + 0.15, 0.55),
            )
        if self._is_definition_question(question=question, lowered=lowered):
            return QuestionIntentProfile(
                intent="definition",
                keywords=keywords,
                support_markers=tuple(DEFINITION_MARKERS),
                support_threshold=max(self.score_threshold + 0.05, 0.42),
            )
        if self._is_formula_question(question=question, lowered=lowered):
            return QuestionIntentProfile(
                intent="formula",
                keywords=keywords,
                support_markers=tuple(FORMULA_MARKERS),
                support_threshold=max(self.score_threshold + 0.08, 0.46),
            )
        return QuestionIntentProfile(
            intent="generic",
            keywords=keywords,
            support_markers=tuple(),
            support_threshold=max(self.score_threshold, 0.3),
        )

    def _support_score(self, profile: QuestionIntentProfile, content: str, base_score: float) -> tuple[float, bool]:
        content_keywords = extract_keywords(content)
        keyword_overlap = self._overlap_ratio(profile.keywords, content_keywords)
        sentence_overlap = max(
            (self._overlap_ratio(profile.keywords, extract_keywords(sentence)) for sentence in split_sentences(content)),
            default=0.0,
        )
        normalized_content = f" {content.lower()} "
        normalized_semantic_content = f" {re.sub(r'[-_/]+', ' ', content.lower())} "
        marker_boost = 0.0
        marker_match = False
        if profile.support_markers and any(marker in normalized_content for marker in profile.support_markers):
            marker_match = True
            marker_boost += 0.22
        if any((" " in keyword) and (f" {keyword} " in normalized_semantic_content) for keyword in profile.keywords):
            marker_boost += 0.12
        if profile.intent == "uses" and re.search(r"(?m)^\s*(?:\d+[\.\)]|[-•])\s+", content):
            marker_boost += 0.08

        if profile.intent == "formula":
            lowered = content.lower()
            formula_signals = 0
            for marker in (" = ", "~", "∼", "xβ", "x beta", "μ =", "mu =", "normal(", "poisson(", "logit(", "identity link"):
                if marker in lowered:
                    formula_signals += 1
            marker_boost += min(0.3, formula_signals * 0.06)
            if "xβ" in content or "Xβ" in content or "μ = Xβ" in content or "mu = x" in lowered:
                marker_boost += 0.18

        score = (0.45 * base_score) + (0.3 * sentence_overlap) + (0.15 * keyword_overlap) + marker_boost
        return score, marker_match

    def _filter_uses_hits(self, hits: list[ScoredHit]) -> list[ScoredHit]:
        anchor_hits = [item for item in hits if item.marker_match]
        if not anchor_hits:
            return hits

        filtered: list[ScoredHit] = []
        for item in hits:
            if item.marker_match:
                filtered.append(item)
                continue
            if self._is_adjacent_to_anchor(item=item, anchors=anchor_hits) and item.support_score >= 0.45:
                filtered.append(item)
        if not filtered:
            return []

        filtered.sort(key=lambda item: item.support_score, reverse=True)
        strongest_score = filtered[0].support_score
        relative_floor = max(strongest_score - 0.25, strongest_score * 0.72, 0.58)
        return [item for item in filtered if item.support_score >= relative_floor]

    def _is_adjacent_to_anchor(self, item: ScoredHit, anchors: list[ScoredHit]) -> bool:
        chunk = item.hit.chunk
        chunk_position = chunk.page_number or chunk.slide_number
        if chunk_position is None:
            return False

        for anchor in anchors:
            anchor_chunk = anchor.hit.chunk
            if anchor_chunk.document_id != chunk.document_id:
                continue
            anchor_position = anchor_chunk.page_number or anchor_chunk.slide_number
            if anchor_position is None:
                continue
            if abs(anchor_position - chunk_position) <= 1:
                return True
        return False

    def _filter_definition_hits(self, hits: list[ScoredHit], profile: QuestionIntentProfile) -> list[ScoredHit]:
        if not hits:
            return []
        hits.sort(key=lambda item: item.support_score, reverse=True)
        strongest_score = hits[0].support_score
        relative_floor = max(strongest_score - 0.22, strongest_score * 0.7, profile.support_threshold)
        return [item for item in hits if item.support_score >= relative_floor]

    def _filter_formula_hits(self, hits: list[ScoredHit], profile: QuestionIntentProfile) -> list[ScoredHit]:
        if not hits:
            return []
        adjusted_hits = [
            (item, item.support_score + self._formula_priority_bonus(profile=profile, content=item.hit.chunk.content))
            for item in hits
        ]
        strongest_score = max(score for _, score in adjusted_hits)
        relative_floor = max(strongest_score - 0.3, strongest_score * 0.78, profile.support_threshold)
        filtered = [item for item, score in adjusted_hits if score >= relative_floor]
        filtered.sort(key=lambda item: self._formula_priority(item=item, profile=profile), reverse=True)
        return filtered

    def _rerank_with_llm(self, question: str, hits: list[tuple]) -> list[tuple]:
        if len(hits) <= 1 or not self.llm_client.is_configured():
            return hits[: self.top_k]

        candidate_hits = hits[: min(len(hits), 8)]
        system_prompt = (
            "You are a retrieval reranker for a grounded RAG system. "
            "Given a user question and candidate chunks, keep only chunks that directly help answer the question. "
            "Prefer chunks that define the asked term, explicitly list requested items, or provide the exact statistic/formula asked for. "
            "Penalize tangential mentions, general background, repeated outline pages, and chunks that only share keywords without answering the question. "
            "Return strict JSON: {\"ranked\": [{\"chunk_id\": \"...\", \"score\": 0.0}]} with scores between 0 and 1."
        )
        candidate_lines = []
        for index, (hit, score) in enumerate(candidate_hits, start=1):
            chunk = hit.chunk
            location = f"page {chunk.page_number}" if chunk.page_number else f"slide {chunk.slide_number}" if chunk.slide_number else "unknown"
            excerpt = chunk.content.strip()
            if len(excerpt) > 1000:
                excerpt = f"{excerpt[:997].rstrip()}..."
            candidate_lines.append(
                f"[{index}] chunk_id={chunk.id} file={chunk.document.filename} location={location} heuristic_score={score:.3f}\n{excerpt}"
            )

        user_prompt = (
            f"Question:\n{question}\n\n"
            "Candidate chunks:\n"
            f"{'\n\n'.join(candidate_lines)}\n\n"
            "Return only JSON."
        )
        try:
            raw = self.llm_client.complete(system_prompt=system_prompt, user_prompt=user_prompt).strip()
            payload = self._extract_json_payload(raw)
            ranked = payload.get("ranked") if isinstance(payload, dict) else None
            if not isinstance(ranked, list):
                return candidate_hits[: self.top_k]

            rescored_by_id: dict[str, float] = {}
            for item in ranked:
                if not isinstance(item, dict):
                    continue
                chunk_id = str(item.get("chunk_id") or "").strip()
                score = item.get("score")
                if not chunk_id:
                    continue
                try:
                    numeric_score = float(score)
                except (TypeError, ValueError):
                    continue
                rescored_by_id[chunk_id] = max(0.0, min(1.0, numeric_score))

            if not rescored_by_id:
                return candidate_hits[: self.top_k]

            reranked: list[tuple] = []
            strongest_score = max(rescored_by_id.values())
            floor = max(strongest_score - 0.25, strongest_score * 0.72, 0.45)
            for hit, heuristic_score in candidate_hits:
                llm_score = rescored_by_id.get(hit.chunk.id)
                if llm_score is None or llm_score < floor:
                    continue
                combined_score = (0.65 * llm_score) + (0.35 * min(heuristic_score, 1.0))
                reranked.append((hit, combined_score))

            if not reranked:
                return []

            reranked.sort(key=lambda item: item[1], reverse=True)
            return reranked[: self.top_k]
        except Exception as exc:
            logger.warning("LLM reranking failed; falling back to heuristic reranking: %s", exc)
            return candidate_hits[: self.top_k]

    def _extract_json_payload(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}

    def _formula_priority_bonus(self, profile: QuestionIntentProfile, content: str) -> float:
        normalized = (
            content.lower()
            .replace("∼", "~")
            .replace("µ", "μ")
            .replace("σ²", "sigma^2")
            .replace("χ²", "chi^2")
        )
        asks_matrix_form = "matrix" in profile.keywords or "矩阵" in profile.keywords or "矩陣" in profile.keywords
        has_distribution = (
            "y ~ normal" in normalized
            or "y ~ n(" in normalized
            or "normal distribution" in normalized
            or "normal regression:" in normalized
        )
        has_general_mean = (
            "μ = xβ" in normalized
            or "mu = xβ" in normalized
            or "mu = x beta" in normalized
            or "μ = xb" in normalized
        )
        has_scalar_mean = "μ = β0" in normalized or "identity link" in normalized or "β0 + β1" in normalized
        has_glm_summary = "some generalized linear models" in normalized or "we can write slide 11 as" in normalized
        is_matrix_notation_page = "matrix notation" in normalized
        is_example_page = "catheter example" in normalized or "glm-examples" in normalized
        is_model_fitting_page = "model fitting" in normalized or "fitted model" in normalized

        bonus = 0.0
        if has_distribution and has_general_mean:
            bonus += 0.75
        elif has_distribution and has_scalar_mean:
            bonus += 0.18
        if has_glm_summary:
            bonus += 0.22
        if "glm" in profile.keywords and has_glm_summary:
            bonus += 0.12
        if "normal" in profile.keywords and "regression" in profile.keywords and "normal regression:" in normalized:
            bonus += 0.1
        if is_matrix_notation_page and not asks_matrix_form:
            bonus -= 0.22
        if is_example_page:
            bonus -= 0.18
        if is_model_fitting_page:
            bonus -= 0.22
        if "appendix" in normalized:
            bonus += 0.08
        if has_general_mean and not has_distribution and not asks_matrix_form:
            bonus -= 0.08
        return bonus

    def _formula_priority(self, item: ScoredHit, profile: QuestionIntentProfile) -> tuple[float, float]:
        bonus = self._formula_priority_bonus(profile=profile, content=item.hit.chunk.content)
        return (bonus + item.support_score, item.support_score)

    def _overlap_ratio(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / max(min(len(left), 6), 1)

    def _is_uses_question(self, question: str, lowered: str) -> bool:
        return any(
            marker in lowered
            for marker in {
                "use of",
                "uses of",
                "used for",
                "applications of",
                "purpose of",
                "purposes of",
                "用途",
                "作用",
                "用于什么",
                "用来做什么",
                "有什么用",
            }
        ) or "what are the uses" in lowered or question.startswith("用途")

    def _is_definition_question(self, question: str, lowered: str) -> bool:
        return (
            lowered.startswith("what is ")
            or lowered.startswith("what are ")
            or lowered.startswith("define ")
            or question.startswith("什么是")
            or question.startswith("何为")
        )

    def _is_formula_question(self, question: str, lowered: str) -> bool:
        return (
            "formula" in lowered
            or "equation" in lowered
            or "mathematical form" in lowered
            or "matrix form" in lowered
            or "formulation" in lowered
            or "notation" in lowered
            or "公式" in question
            or "数学形式" in question
            or "數學形式" in question
            or "矩阵形式" in question
            or "矩陣形式" in question
            or "表达式" in question
            or "寫成" in question
            or "写成" in question
        )
