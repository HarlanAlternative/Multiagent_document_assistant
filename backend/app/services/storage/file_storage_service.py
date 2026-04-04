import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings


@dataclass(slots=True)
class StoredFile:
    original_filename: str
    file_type: str
    path: Path
    checksum: str
    file_size: int


class FileStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage_path = self.settings.file_storage_path

    def store_upload(self, upload: UploadFile) -> StoredFile:
        if not upload.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

        normalized_filename = Path(upload.filename).name
        if not normalized_filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

        suffix = Path(normalized_filename).suffix.lower().lstrip(".")
        if suffix not in self.settings.allowed_extensions:
            allowed = ", ".join(self.settings.allowed_extensions)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed extensions: {allowed}.",
            )

        target_name = f"{uuid4()}.{suffix}"
        target_path = self.storage_path / target_name
        upload.file.seek(0)

        hasher = hashlib.sha256()
        size = 0
        with target_path.open("wb") as output_file:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.settings.max_upload_size_mb * 1024 * 1024:
                    output_file.close()
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds the {self.settings.max_upload_size_mb} MB size limit.",
                    )
                hasher.update(chunk)
                output_file.write(chunk)

        return StoredFile(
            original_filename=normalized_filename,
            file_type=suffix,
            path=target_path,
            checksum=hasher.hexdigest(),
            file_size=size,
        )

    def delete_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)
