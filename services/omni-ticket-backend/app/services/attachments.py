from pathlib import Path, PurePath
import re

from app.core.config import settings


SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class AttachmentStorage:
    """Local storage adapter; production can swap this boundary for object storage."""

    scheme = "local:"

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def safe_filename(self, filename: str) -> str:
        basename = PurePath(filename.strip()).name or "attachment"
        sanitized = SAFE_FILENAME_PATTERN.sub("_", basename).strip("._")
        return sanitized or "attachment"

    def storage_key(
        self,
        *,
        market_id: str,
        ticket_id: str,
        attachment_id: str,
        filename: str,
    ) -> str:
        safe = self.safe_filename(filename)
        return f"{self.scheme}{market_id}/{ticket_id}/{attachment_id}/{safe}"

    def write(
        self,
        *,
        market_id: str,
        ticket_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
    ) -> str:
        key = self.storage_key(
            market_id=market_id,
            ticket_id=ticket_id,
            attachment_id=attachment_id,
            filename=filename,
        )
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, storage_key: str) -> bytes:
        return self._path_for_key(storage_key).read_bytes()

    def _path_for_key(self, storage_key: str) -> Path:
        if not storage_key.startswith(self.scheme):
            raise ValueError("Unsupported attachment storage key")
        relative = Path(storage_key.removeprefix(self.scheme))
        path = (self.root / relative).resolve()
        root = self.root.resolve()
        if root not in path.parents:
            raise ValueError("Attachment storage key escapes storage root")
        return path


attachment_storage = AttachmentStorage(settings.attachment_storage_dir)
