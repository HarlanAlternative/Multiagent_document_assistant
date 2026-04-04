from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.projects import ProjectCreateRequest, ProjectListResponse, ProjectRead, ProjectReindexResponse, ProjectUpdateRequest
from app.services.projects.project_service import ProjectService

router = APIRouter()
project_service = ProjectService()


def _to_project_read(project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        memory=project.memory,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db)) -> ProjectListResponse:
    project_service.ensure_default_project(db)
    return ProjectListResponse(items=[_to_project_read(project) for project in project_service.list_projects(db)])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, db: Session = Depends(get_db)) -> ProjectRead:
    project = project_service.create_project(
        db=db,
        name=payload.name,
        description=payload.description,
        memory=payload.memory,
    )
    return _to_project_read(project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectRead:
    project = project_service.get_project(db=db, project_id=project_id)
    return _to_project_read(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdateRequest, db: Session = Depends(get_db)) -> ProjectRead:
    project = project_service.get_project(db=db, project_id=project_id)
    project = project_service.update_project(
        db=db,
        project=project,
        name=payload.name,
        description=payload.description,
        memory=payload.memory,
    )
    return _to_project_read(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = project_service.get_project(db=db, project_id=project_id)
    project_service.delete_project(db=db, project=project)


@router.post("/{project_id}/reindex", response_model=ProjectReindexResponse)
def reindex_project(project_id: str, db: Session = Depends(get_db)) -> ProjectReindexResponse:
    project = project_service.get_project(db=db, project_id=project_id)
    reindexed_document_ids, failed_documents = project_service.reindex_project(db=db, project=project)
    return ProjectReindexResponse(
        project_id=project.id,
        reindexed_document_ids=reindexed_document_ids,
        failed_documents=failed_documents,
    )
