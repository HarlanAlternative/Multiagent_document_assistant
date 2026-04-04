from fastapi import APIRouter

from app.schemas.model_catalog import ModelCatalogRequest, ModelCatalogResponse
from app.schemas.settings import LLMSettingsRead, LLMSettingsUpdateRequest, SearchSettingsRead, SearchSettingsUpdateRequest
from app.services.llm.model_catalog_service import ModelCatalogService
from app.services.settings.runtime_settings_service import RuntimeLLMSettingsUpdate, RuntimeSearchSettingsUpdate, RuntimeSettingsService

router = APIRouter()
runtime_settings_service = RuntimeSettingsService()
model_catalog_service = ModelCatalogService()


@router.get("/llm", response_model=LLMSettingsRead)
def get_llm_settings() -> LLMSettingsRead:
    return LLMSettingsRead(**runtime_settings_service.get_snapshot().model_dump())


@router.put("/llm", response_model=LLMSettingsRead)
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsRead:
    snapshot = runtime_settings_service.update_llm_settings(RuntimeLLMSettingsUpdate(**payload.model_dump()))
    return LLMSettingsRead(**snapshot.model_dump())


@router.get("/search", response_model=SearchSettingsRead)
def get_search_settings() -> SearchSettingsRead:
    return SearchSettingsRead(**runtime_settings_service.get_search_snapshot().model_dump())


@router.put("/search", response_model=SearchSettingsRead)
def update_search_settings(payload: SearchSettingsUpdateRequest) -> SearchSettingsRead:
    snapshot = runtime_settings_service.update_search_settings(RuntimeSearchSettingsUpdate(**payload.model_dump()))
    return SearchSettingsRead(**snapshot.model_dump())


@router.post("/llm/models", response_model=ModelCatalogResponse)
def list_provider_models(payload: ModelCatalogRequest) -> ModelCatalogResponse:
    items = model_catalog_service.list_models(
        provider_name=payload.provider_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        aws_region=payload.aws_region,
        aws_access_key_id=payload.aws_access_key_id,
        aws_secret_access_key=payload.aws_secret_access_key,
        aws_session_token=payload.aws_session_token,
    )
    return ModelCatalogResponse(items=items)
