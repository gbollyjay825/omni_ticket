from __future__ import annotations

from base64 import b64encode
import json
from pathlib import Path, PurePath
import re
from typing import Any, Protocol
import urllib.error
import urllib.request

from app.core.config import settings
from app.models.domain import AttachmentProviderConfig, AttachmentScanStatus


SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
DANGEROUS_ATTACHMENT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}


class AttachmentStorageBackend(Protocol):
    scheme: str

    def safe_filename(self, filename: str) -> str: ...

    def storage_key(
        self,
        *,
        market_id: str,
        ticket_id: str,
        attachment_id: str,
        filename: str,
    ) -> str: ...

    def write(
        self,
        *,
        market_id: str,
        ticket_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str: ...

    def read(self, storage_key: str) -> bytes: ...

    def delete(self, storage_key: str) -> bool: ...


class LocalAttachmentStorage:
    """Local storage adapter for development, demos, and VM operation before object storage."""

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
        content_type: str | None = None,
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

    def delete(self, storage_key: str) -> bool:
        try:
            path = self._path_for_key(storage_key)
        except ValueError:
            return False
        if not path.exists():
            return False
        path.unlink()
        return True

    def _path_for_key(self, storage_key: str) -> Path:
        if not storage_key.startswith(self.scheme):
            raise ValueError("Unsupported attachment storage key")
        relative = Path(storage_key.removeprefix(self.scheme))
        path = (self.root / relative).resolve()
        root = self.root.resolve()
        if root not in path.parents:
            raise ValueError("Attachment storage key escapes storage root")
        return path


class S3AttachmentStorage:
    """S3-compatible object storage adapter.

    The boto3 dependency is imported lazily so local/dev environments can keep using the
    local adapter until managed object storage credentials are configured.
    """

    scheme = "s3:"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        server_side_encryption: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.server_side_encryption = server_side_encryption

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
        object_key = "/".join(
            part
            for part in [self.prefix, market_id, ticket_id, attachment_id, safe]
            if part
        )
        return f"{self.scheme}{self.bucket}/{object_key}"

    def write(
        self,
        *,
        market_id: str,
        ticket_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        key = self.storage_key(
            market_id=market_id,
            ticket_id=ticket_id,
            attachment_id=attachment_id,
            filename=filename,
        )
        put_kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": self._object_key_for_storage_key(key),
            "Body": data,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type
        if self.server_side_encryption:
            put_kwargs["ServerSideEncryption"] = self.server_side_encryption
        self._client().put_object(**put_kwargs)
        return key

    def read(self, storage_key: str) -> bytes:
        response = self._client().get_object(
            Bucket=self.bucket,
            Key=self._object_key_for_storage_key(storage_key),
        )
        return response["Body"].read()

    def delete(self, storage_key: str) -> bool:
        if not storage_key.startswith(self.scheme):
            return False
        self._client().delete_object(
            Bucket=self.bucket,
            Key=self._object_key_for_storage_key(storage_key),
        )
        return True

    def _object_key_for_storage_key(self, storage_key: str) -> str:
        if not storage_key.startswith(self.scheme):
            raise ValueError("Unsupported attachment storage key")
        value = storage_key.removeprefix(self.scheme)
        bucket, _, object_key = value.partition("/")
        if bucket != self.bucket or not object_key:
            raise ValueError("Attachment storage key does not match the configured bucket")
        parts = PurePath(object_key).parts
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Attachment storage key escapes object prefix")
        return "/".join(parts)

    def _client(self):
        try:
            import boto3  # type: ignore[import-not-found,import-untyped]
        except ImportError as exc:
            raise RuntimeError("boto3 is required when OMNI_ATTACHMENT_STORAGE_BACKEND=s3") from exc

        kwargs: dict[str, Any] = {}
        if self.region:
            kwargs["region_name"] = self.region
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id:
            kwargs["aws_access_key_id"] = self.access_key_id
        if self.secret_access_key:
            kwargs["aws_secret_access_key"] = self.secret_access_key
        return boto3.client("s3", **kwargs)


def build_attachment_storage() -> AttachmentStorageBackend:
    if settings.attachment_storage_backend == "s3":
        return S3AttachmentStorage(
            bucket=settings.attachment_s3_bucket or "",
            prefix=settings.attachment_s3_prefix,
            region=settings.attachment_s3_region,
            endpoint_url=settings.attachment_s3_endpoint_url,
            access_key_id=settings.attachment_s3_access_key_id,
            secret_access_key=settings.attachment_s3_secret_access_key,
            server_side_encryption=settings.attachment_s3_server_side_encryption,
        )
    return LocalAttachmentStorage(settings.attachment_storage_dir)


def scan_attachment_metadata(filename: str, content_type: str) -> tuple[AttachmentScanStatus, str]:
    normalized = filename.strip().lower()
    suffix = f".{normalized.rsplit('.', 1)[-1]}" if "." in normalized else ""
    if suffix in DANGEROUS_ATTACHMENT_SUFFIXES:
        return (
            AttachmentScanStatus.blocked,
            f"Blocked because {suffix} files are not allowed in customer conversations.",
        )
    if content_type.strip().lower() in {"application/x-msdownload", "application/x-sh"}:
        return (
            AttachmentScanStatus.blocked,
            "Blocked because the content type is not allowed in customer conversations.",
        )
    return AttachmentScanStatus.clean, "Passed local metadata policy scan."


def scan_attachment_binary(
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> tuple[AttachmentScanStatus, str]:
    metadata_status, metadata_result = scan_attachment_metadata(filename, content_type)
    if metadata_status != AttachmentScanStatus.clean:
        return metadata_status, metadata_result
    if settings.attachment_scanner_adapter != "http":
        return metadata_status, metadata_result
    if not settings.attachment_scanner_http_endpoint:
        return (
            AttachmentScanStatus.failed,
            "External attachment scanner is selected but OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT is not configured.",
        )
    try:
        payload = _post_scanner_request(filename=filename, content_type=content_type, data=data)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return (
            AttachmentScanStatus.failed,
            f"External attachment scanner failed: {exc}",
        )
    return _scanner_payload_result(payload)


def blocked_storage_key(
    *,
    market_id: str,
    ticket_id: str,
    attachment_id: str,
    filename: str,
) -> str:
    safe = attachment_storage.safe_filename(filename)
    return f"blocked:{market_id}/{ticket_id}/{attachment_id}/{safe}"


def attachment_provider_config() -> AttachmentProviderConfig:
    storage_required: list[str] = []
    storage_missing: list[str] = []
    if settings.attachment_storage_backend == "s3":
        storage_required = [
            "OMNI_ATTACHMENT_S3_BUCKET",
            "OMNI_ATTACHMENT_S3_REGION or OMNI_ATTACHMENT_S3_ENDPOINT_URL",
        ]
        if not settings.attachment_s3_bucket:
            storage_missing.append("OMNI_ATTACHMENT_S3_BUCKET")
        if not settings.attachment_s3_region and not settings.attachment_s3_endpoint_url:
            storage_missing.append("OMNI_ATTACHMENT_S3_REGION or OMNI_ATTACHMENT_S3_ENDPOINT_URL")

    scanner_required: list[str] = []
    scanner_missing: list[str] = []
    if settings.attachment_scanner_adapter == "http":
        scanner_required = ["OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT"]
        if not settings.attachment_scanner_http_endpoint:
            scanner_missing.append("OMNI_ATTACHMENT_SCANNER_HTTP_ENDPOINT")

    storage_configured = settings.attachment_storage_backend == "local" or not storage_missing
    scanner_configured = settings.attachment_scanner_adapter == "local" or not scanner_missing
    notes = []
    if settings.attachment_storage_backend == "s3" and storage_configured:
        notes.append("S3-compatible attachment object storage is configured.")
    elif settings.attachment_storage_backend == "s3":
        notes.append("S3-compatible attachment object storage is selected but incomplete.")
    else:
        notes.append("Local attachment storage is active until managed object storage is configured.")
    if settings.attachment_scanner_adapter == "http" and scanner_configured:
        notes.append("External HTTP malware scanning is active for binary uploads.")
    elif settings.attachment_scanner_adapter == "http":
        notes.append("External HTTP malware scanning is selected but incomplete.")
    else:
        notes.append("Local metadata policy scanning is active.")

    return AttachmentProviderConfig(
        storage_backend=settings.attachment_storage_backend,
        storage_configured=storage_configured,
        storage_live=storage_configured,
        scanner_adapter=settings.attachment_scanner_adapter,
        scanner_configured=scanner_configured,
        live_scanning=settings.attachment_scanner_adapter == "http" and scanner_configured,
        required_settings=storage_required + scanner_required,
        missing_settings=storage_missing + scanner_missing,
        notes=" ".join(notes),
    )


def _post_scanner_request(*, filename: str, content_type: str, data: bytes) -> dict[str, Any]:
    body = json.dumps(
        {
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(data),
            "data_base64": b64encode(data).decode("ascii"),
        },
        separators=(",", ":"),
    ).encode()
    headers = {"Content-Type": "application/json"}
    if settings.attachment_scanner_http_auth_token:
        header = settings.attachment_scanner_http_auth_header
        scheme = settings.attachment_scanner_http_auth_scheme.strip()
        headers[header] = (
            f"{scheme} {settings.attachment_scanner_http_auth_token}"
            if scheme
            else settings.attachment_scanner_http_auth_token
        )
    request = urllib.request.Request(
        settings.attachment_scanner_http_endpoint or "",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(  # noqa: S310 - controlled by deployment config.
        request,
        timeout=settings.attachment_scanner_http_timeout_seconds,
    ) as response:
        response_body = response.read(4096).decode(errors="replace")
        if response.status >= 400:
            raise ValueError(f"scanner returned HTTP {response.status}")
        return json.loads(response_body or "{}")


def _scanner_payload_result(payload: dict[str, Any]) -> tuple[AttachmentScanStatus, str]:
    raw_status = str(payload.get("status") or payload.get("verdict") or "").strip().lower()
    result = str(payload.get("result") or payload.get("message") or "External scanner response received.")
    if raw_status in {"clean", "ok", "allowed", "safe"}:
        return AttachmentScanStatus.clean, result
    if raw_status in {"blocked", "infected", "malicious", "unsafe", "deny", "denied"}:
        return AttachmentScanStatus.blocked, result
    return AttachmentScanStatus.failed, result


AttachmentStorage = LocalAttachmentStorage
attachment_storage = build_attachment_storage()
