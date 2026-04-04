import json
import logging
import time
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict,
    timeout_seconds: float,
) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_text = response.read().decode("utf-8")
            return json.loads(raw_text)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM request failed with status {exc.code}: {body or exc.reason}") from exc
        except (URLError, JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt == 2:
                if isinstance(exc, URLError):
                    raise RuntimeError(f"LLM request failed: {exc.reason}") from exc
                raise RuntimeError(str(exc)) from exc
            logger.warning("LLM request attempt %s failed, retrying once: %s", attempt, exc)
            time.sleep(0.5)
    raise RuntimeError(f"LLM request failed: {last_error}")
