from functools import lru_cache
from typing import Any

from app.services.llm.base import LLMProviderConfig


def _import_boto3():
    import boto3

    return boto3


def _client_kwargs(config: LLMProviderConfig) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if config.aws_region:
        kwargs["region_name"] = config.aws_region
    if config.aws_access_key_id:
        kwargs["aws_access_key_id"] = config.aws_access_key_id
    if config.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = config.aws_secret_access_key
    if config.aws_session_token:
        kwargs["aws_session_token"] = config.aws_session_token
    return kwargs


@lru_cache(maxsize=8)
def _build_client(
    service_name: str,
    region_name: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_session_token: str | None,
):
    boto3 = _import_boto3()
    kwargs: dict[str, Any] = {}
    if region_name:
        kwargs["region_name"] = region_name
    if aws_access_key_id:
        kwargs["aws_access_key_id"] = aws_access_key_id
    if aws_secret_access_key:
        kwargs["aws_secret_access_key"] = aws_secret_access_key
    if aws_session_token:
        kwargs["aws_session_token"] = aws_session_token
    return boto3.client(service_name, **kwargs)


def get_bedrock_client(config: LLMProviderConfig, service_name: str):
    return _build_client(
        service_name,
        config.aws_region,
        config.aws_access_key_id,
        config.aws_secret_access_key,
        config.aws_session_token,
    )
