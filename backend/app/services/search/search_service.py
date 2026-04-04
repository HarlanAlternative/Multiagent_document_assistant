import json
import logging
import re
from html import unescape
from typing import Protocol
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.schemas.chat import WebSearchResultRead
from app.services.settings.runtime_settings_service import EffectiveSearchSettings, RuntimeSettingsService

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    def search(self, query: str, top_k: int) -> list[WebSearchResultRead]:
        ...


class TavilySearchProvider:
    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, top_k: int) -> list[WebSearchResultRead]:
        payload = {
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": top_k,
            "include_answer": False,
            "include_raw_content": False,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Tavily search failed with status {exc.code}: {body or exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"Tavily search request failed: {exc.reason}") from exc

        normalized_results: list[WebSearchResultRead] = []
        for index, item in enumerate(raw_payload.get("results", []), start=1):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("content") or "").strip()
            if not title or not url:
                continue
            normalized_results.append(
                WebSearchResultRead(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="tavily",
                    rank=index,
                )
            )
        return normalized_results


class DuckDuckGoSearchProvider:
    endpoint = "https://html.duckduckgo.com/html/"

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, top_k: int) -> list[WebSearchResultRead]:
        request = Request(
            f"{self.endpoint}?q={quote_plus(query)}",
            headers={
                "User-Agent": "Mozilla/5.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"DuckDuckGo search failed with status {exc.code}: {body or exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"DuckDuckGo search request failed: {exc.reason}") from exc

        return self._parse_results(html=html, top_k=top_k)

    def _parse_results(self, html: str, top_k: int) -> list[WebSearchResultRead]:
        results: list[WebSearchResultRead] = []
        block_pattern = re.compile(
            r'<div class="result results_links.*?<div class="clear"></div>\s*</div>\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )
        title_pattern = re.compile(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet_a>.*?)</a>|'
            r'<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet_div>.*?)</div>',
            re.IGNORECASE | re.DOTALL,
        )
        for index, block in enumerate(block_pattern.findall(html), start=1):
            title_match = title_pattern.search(block)
            if not title_match:
                continue
            snippet_match = snippet_pattern.search(block)
            raw_url = self._strip_tags(unescape(title_match.group("url")))
            url = self._normalize_duckduckgo_url(raw_url)
            title = self._strip_tags(unescape(title_match.group("title")))
            snippet_source = ""
            if snippet_match:
                snippet_source = snippet_match.group("snippet_a") or snippet_match.group("snippet_div") or ""
            snippet = self._strip_tags(unescape(snippet_source))
            if not title or not url:
                continue
            results.append(
                WebSearchResultRead(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="duckduckgo",
                    rank=index,
                )
            )
            if len(results) >= top_k:
                break
        return results

    def _normalize_duckduckgo_url(self, raw_url: str) -> str:
        if raw_url.startswith("//duckduckgo.com/l/"):
            parsed = urlparse(f"https:{raw_url}")
            actual = parse_qs(parsed.query).get("uddg", [None])[0]
            if actual:
                return actual
        if raw_url.startswith("/l/"):
            parsed = urlparse(f"https://duckduckgo.com{raw_url}")
            actual = parse_qs(parsed.query).get("uddg", [None])[0]
            if actual:
                return actual
        if raw_url.startswith("//"):
            return f"https:{raw_url}"
        return raw_url

    def _strip_tags(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", text).strip()


class SearchService:
    def __init__(self, provider: SearchProvider | None = None) -> None:
        settings = get_settings()
        self.top_k = settings.search_top_k
        self.runtime_settings_service = RuntimeSettingsService()
        self.search_settings = self.runtime_settings_service.get_effective_search_settings()
        self.enabled = self.search_settings.search_enabled
        self.provider_name = self.search_settings.search_provider
        self.provider = provider or self._build_provider(settings, self.search_settings)

    def search(self, query: str) -> tuple[list[WebSearchResultRead], str | None]:
        if not self.enabled:
            logger.info("Web search is disabled. Returning no web results for query=%r", query)
            return [], "Web search is disabled in settings."
        if self.provider is None:
            logger.warning("Web search provider %s is unavailable. Returning no web results.", self.provider_name)
            return [], f"Web search provider {self.provider_name} is unavailable."

        try:
            return self.provider.search(query=query, top_k=self.top_k), None
        except Exception as exc:
            logger.warning("Web search failed for query=%r using provider=%s: %s", query, self.provider_name, exc)
            return [], f"Web search failed using {self.provider_name}."

    def _build_provider(self, settings: Settings, search_settings: EffectiveSearchSettings) -> SearchProvider | None:
        provider_name = search_settings.search_provider.lower().strip()
        if provider_name == "duckduckgo":
            return DuckDuckGoSearchProvider(timeout_seconds=settings.search_timeout_seconds)
        if provider_name == "tavily":
            if not search_settings.search_api_key:
                logger.warning("Search provider tavily requires SEARCH_API_KEY or runtime search_api_key.")
                return None
            return TavilySearchProvider(
                api_key=search_settings.search_api_key,
                timeout_seconds=settings.search_timeout_seconds,
            )
        logger.warning("Unsupported search provider %s. Web search will be unavailable.", provider_name)
        return None
