from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ExternalIdMappingRecord,
    ImportCursorRecord,
    ImportCutoverDecisionRecord,
    ImportReconciliationRecord,
    ImportRunRecord,
)
from app.models.domain import utc_now


_REQUIRED_ENTITIES: dict[str, tuple[str, ...]] = {
    "freshdesk": ("contact", "ticket", "conversation"),
    "freshchat": ("user", "conversation", "message"),
}
_FINAL_DELTA_MAX_AGE = timedelta(hours=24)
_SOURCE_MANIFEST_MAX_AGE = timedelta(days=7)
_ROLLBACK_WINDOW = timedelta(hours=72)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _run_payload(record: ImportRunRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "market_id": record.market_id,
        "provider": record.provider,
        "mode": record.mode,
        "status": record.status,
        "dry_run": record.dry_run,
        "started_by": record.started_by,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "source_cursor": record.source_cursor or {},
        "next_cursor": record.next_cursor or {},
        "statistics": record.statistics or {},
        "error_summary": record.error_summary,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _cursor_payload(record: ImportCursorRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "market_id": record.market_id,
        "provider": record.provider,
        "resource": record.resource,
        "cursor": record.cursor or {},
        "checkpoint_at": record.checkpoint_at,
    }


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _readiness_hash(readiness: Mapping[str, Any]) -> str:
    encoded = json.dumps(readiness, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, default=str))


def _run_time(record: ImportRunRecord) -> datetime:
    return _aware(record.finished_at) or _aware(record.started_at) or utc_now()


class ImportRepository:
    def begin_run(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        mode: str,
        dry_run: bool,
        started_by: str,
        source_cursor: Mapping[str, Any] | None = None,
    ) -> ImportRunRecord:
        record = ImportRunRecord(
            id=_new_id("import"),
            market_id=market_id,
            provider=provider,
            mode=mode,
            status="running",
            dry_run=dry_run,
            started_by=started_by,
            source_cursor=dict(source_cursor or {}),
            next_cursor={},
            statistics={},
        )
        db.add(record)
        db.flush()
        return record

    def finish_run(
        self,
        record: ImportRunRecord,
        *,
        status: str,
        statistics: Mapping[str, Any],
        next_cursor: Mapping[str, Any] | None = None,
        error_summary: str = "",
    ) -> None:
        record.status = status
        record.statistics = dict(statistics)
        record.next_cursor = dict(next_cursor or {})
        record.error_summary = error_summary[:8000]
        record.finished_at = utc_now()
        record.updated_at = utc_now()

    def list_runs(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = select(ImportRunRecord).where(ImportRunRecord.market_id == market_id)
        if provider:
            query = query.where(ImportRunRecord.provider == provider)
        records = db.scalars(
            query.order_by(ImportRunRecord.started_at.desc()).limit(limit)
        ).all()
        return [_run_payload(record) for record in records]

    def read_run(
        self,
        db: Session,
        *,
        market_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        record = db.get(ImportRunRecord, run_id)
        if record is None or record.market_id != market_id:
            return None
        return _run_payload(record)

    def list_cursors(self, db: Session, *, market_id: str) -> list[dict[str, Any]]:
        records = db.scalars(
            select(ImportCursorRecord)
            .where(ImportCursorRecord.market_id == market_id)
            .order_by(ImportCursorRecord.provider, ImportCursorRecord.resource)
        ).all()
        return [_cursor_payload(record) for record in records]

    def get_cursor(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        resource: str,
    ) -> dict[str, Any]:
        record = db.scalar(
            select(ImportCursorRecord).where(
                ImportCursorRecord.market_id == market_id,
                ImportCursorRecord.provider == provider,
                ImportCursorRecord.resource == resource,
            )
        )
        return dict(record.cursor or {}) if record else {}

    def set_cursor(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        resource: str,
        cursor: Mapping[str, Any],
    ) -> ImportCursorRecord:
        record = db.scalar(
            select(ImportCursorRecord).where(
                ImportCursorRecord.market_id == market_id,
                ImportCursorRecord.provider == provider,
                ImportCursorRecord.resource == resource,
            )
        )
        now = utc_now()
        if record is None:
            record = ImportCursorRecord(
                id=_new_id("cursor"),
                market_id=market_id,
                provider=provider,
                resource=resource,
                cursor=dict(cursor),
                checkpoint_at=now,
            )
            db.add(record)
        else:
            record.cursor = dict(cursor)
            record.checkpoint_at = now
            record.updated_at = now
        db.flush()
        return record

    def get_mapping(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        entity_type: str,
        external_id: object,
    ) -> ExternalIdMappingRecord | None:
        return db.scalar(
            select(ExternalIdMappingRecord).where(
                ExternalIdMappingRecord.market_id == market_id,
                ExternalIdMappingRecord.provider == provider,
                ExternalIdMappingRecord.entity_type == entity_type,
                ExternalIdMappingRecord.external_id == str(external_id),
            )
        )

    def set_mapping(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        entity_type: str,
        external_id: object,
        internal_id: str,
        source_updated_at: datetime | None,
        payload_hash: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExternalIdMappingRecord:
        record = self.get_mapping(
            db,
            market_id=market_id,
            provider=provider,
            entity_type=entity_type,
            external_id=external_id,
        )
        now = utc_now()
        if record is None:
            record = ExternalIdMappingRecord(
                id=_new_id("mapping"),
                market_id=market_id,
                provider=provider,
                entity_type=entity_type,
                external_id=str(external_id),
                internal_id=internal_id,
                source_updated_at=source_updated_at,
                payload_hash=payload_hash,
                mapping_metadata=dict(metadata or {}),
            )
            db.add(record)
        else:
            record.internal_id = internal_id
            record.source_updated_at = source_updated_at
            record.payload_hash = payload_hash
            record.mapping_metadata = dict(metadata or {})
            record.updated_at = now
        db.flush()
        return record

    def set_reconciliation_manifest(
        self,
        db: Session,
        *,
        market_id: str,
        provider: str,
        entity_type: str,
        source_count: int,
        source_checksum: str,
        sample_size: int,
        sample_failures: int,
        missing_attachments: int,
        source_snapshot_at: datetime,
        recorded_by: str,
        notes: str,
    ) -> ImportReconciliationRecord:
        record = ImportReconciliationRecord(
            id=_new_id("reconciliation"),
            market_id=market_id,
            provider=provider,
            entity_type=entity_type,
            source_count=source_count,
            source_checksum=source_checksum,
            sample_size=sample_size,
            sample_failures=sample_failures,
            missing_attachments=missing_attachments,
            source_snapshot_at=source_snapshot_at,
            recorded_by=recorded_by,
            notes=notes,
        )
        db.add(record)
        db.flush()
        return record

    def _latest_cutover(
        self,
        db: Session,
        *,
        market_id: str,
    ) -> ImportCutoverDecisionRecord | None:
        return db.scalar(
            select(ImportCutoverDecisionRecord)
            .where(ImportCutoverDecisionRecord.market_id == market_id)
            .order_by(ImportCutoverDecisionRecord.decided_at.desc())
            .limit(1)
        )

    def _cutover_payload(
        self,
        record: ImportCutoverDecisionRecord | None,
        *,
        current_hash: str,
    ) -> dict[str, Any] | None:
        if record is None:
            return None
        rollback_until = _aware(record.rollback_until)
        return {
            "id": record.id,
            "status": record.status,
            "decided_by": record.decided_by,
            "decided_at": record.decided_at,
            "rollback_until": record.rollback_until,
            "reason": record.reason,
            "readiness_hash": record.readiness_hash,
            "snapshot_current": record.readiness_hash == current_hash,
            "rollback_active": bool(rollback_until and rollback_until > utc_now()),
        }

    def reconciliation(self, db: Session, *, market_id: str) -> dict[str, Any]:
        rows = db.execute(
            select(
                ExternalIdMappingRecord.provider,
                ExternalIdMappingRecord.entity_type,
                func.count(ExternalIdMappingRecord.id),
            )
            .where(ExternalIdMappingRecord.market_id == market_id)
            .group_by(ExternalIdMappingRecord.provider, ExternalIdMappingRecord.entity_type)
            .order_by(ExternalIdMappingRecord.provider, ExternalIdMappingRecord.entity_type)
        ).all()
        providers: dict[str, dict[str, int]] = {}
        for provider, entity_type, count in rows:
            providers.setdefault(str(provider), {})[str(entity_type)] = int(count)

        manifest_records = list(
            db.scalars(
                select(ImportReconciliationRecord)
                .where(ImportReconciliationRecord.market_id == market_id)
                .order_by(
                    ImportReconciliationRecord.provider,
                    ImportReconciliationRecord.entity_type,
                    ImportReconciliationRecord.source_snapshot_at.desc(),
                    ImportReconciliationRecord.created_at.desc(),
                )
            )
        )
        manifest_by_key: dict[tuple[str, str], ImportReconciliationRecord] = {}
        for record in manifest_records:
            manifest_by_key.setdefault((record.provider, record.entity_type), record)
        source_manifests: dict[str, dict[str, dict[str, Any]]] = {}
        for record in manifest_by_key.values():
            source_manifests.setdefault(record.provider, {})[record.entity_type] = {
                "source_count": record.source_count,
                "source_checksum": record.source_checksum,
                "sample_size": record.sample_size,
                "sample_failures": record.sample_failures,
                "missing_attachments": record.missing_attachments,
                "source_snapshot_at": record.source_snapshot_at,
                "recorded_by": record.recorded_by,
                "notes": record.notes,
            }

        runs = list(
            db.scalars(
                select(ImportRunRecord)
                .where(ImportRunRecord.market_id == market_id)
                .order_by(ImportRunRecord.started_at.desc())
            )
        )
        now = utc_now()
        provider_results: dict[str, dict[str, Any]] = {}
        global_checks: list[dict[str, Any]] = []
        for provider, required_entities in _REQUIRED_ENTITIES.items():
            provider_runs = [run for run in runs if run.provider == provider]
            latest_run = provider_runs[0] if provider_runs else None
            completed_full = next(
                (
                    run
                    for run in provider_runs
                    if run.mode == "full_export"
                    and run.status == "completed"
                    and not run.dry_run
                ),
                None,
            )
            completed_delta = next(
                (
                    run
                    for run in provider_runs
                    if run.mode in {"incremental", "final_delta"}
                    and run.status == "completed"
                    and not run.dry_run
                    and (
                        completed_full is None
                        or _run_time(run) >= _run_time(completed_full)
                    )
                ),
                None,
            )
            missing_entities: list[str] = []
            differences: dict[str, int] = {}
            sample_failures = 0
            missing_attachments = 0
            stale_entities: list[str] = []
            checksum_missing_entities: list[str] = []
            unsampled_entities: list[str] = []
            for entity_type in required_entities:
                manifest = manifest_by_key.get((provider, entity_type))
                if manifest is None:
                    missing_entities.append(entity_type)
                    continue
                differences[entity_type] = (
                    providers.get(provider, {}).get(entity_type, 0) - manifest.source_count
                )
                sample_failures += manifest.sample_failures
                missing_attachments += manifest.missing_attachments
                if not manifest.source_checksum.strip():
                    checksum_missing_entities.append(entity_type)
                if manifest.sample_size == 0:
                    unsampled_entities.append(entity_type)
                snapshot_at = _aware(manifest.source_snapshot_at)
                if snapshot_at is None or now - snapshot_at > _SOURCE_MANIFEST_MAX_AGE:
                    stale_entities.append(entity_type)
            delta_finished_at = _run_time(completed_delta) if completed_delta else None
            checks = [
                {
                    "key": "source_manifest",
                    "label": "Source manifest complete",
                    "passed": (
                        not missing_entities
                        and not stale_entities
                        and not checksum_missing_entities
                    ),
                    "detail": (
                        "All required source totals and checksums are current."
                        if not missing_entities
                        and not stale_entities
                        and not checksum_missing_entities
                        else (
                            f"Missing: {', '.join(missing_entities) or 'none'}; "
                            f"stale: {', '.join(stale_entities) or 'none'}; "
                            f"checksum missing: {', '.join(checksum_missing_entities) or 'none'}."
                        )
                    ),
                },
                {
                    "key": "full_import",
                    "label": "Full export imported",
                    "passed": completed_full is not None,
                    "detail": (
                        f"Completed {completed_full.finished_at.isoformat()}."
                        if completed_full and completed_full.finished_at
                        else "No completed production full export."
                    ),
                },
                {
                    "key": "final_delta",
                    "label": "Final delta current",
                    "passed": bool(
                        delta_finished_at and now - delta_finished_at <= _FINAL_DELTA_MAX_AGE
                    ),
                    "detail": (
                        f"Completed {delta_finished_at.isoformat()}."
                        if delta_finished_at
                        else "No completed delta after the full export."
                    ),
                },
                {
                    "key": "record_counts",
                    "label": "Record counts match",
                    "passed": bool(differences) and all(value == 0 for value in differences.values()),
                    "detail": (
                        "Every required entity count matches the source."
                        if differences and all(value == 0 for value in differences.values())
                        else "One or more source and mapped counts differ."
                    ),
                },
                {
                    "key": "sample_validation",
                    "label": "Samples and attachments pass",
                    "passed": (
                        not unsampled_entities
                        and sample_failures == 0
                        and missing_attachments == 0
                    ),
                    "detail": (
                        f"{sample_failures} sample failure(s), "
                        f"{missing_attachments} missing attachment(s), "
                        f"unsampled: {', '.join(unsampled_entities) or 'none'}."
                    ),
                },
                {
                    "key": "run_health",
                    "label": "Latest run healthy",
                    "passed": bool(latest_run and latest_run.status == "completed"),
                    "detail": (
                        f"Latest run is {latest_run.status}."
                        if latest_run
                        else "No import run recorded."
                    ),
                },
            ]
            verified = all(check["passed"] for check in checks)
            provider_results[provider] = {
                "verified": verified,
                "required_entities": list(required_entities),
                "missing_entities": missing_entities,
                "stale_entities": stale_entities,
                "checksum_missing_entities": checksum_missing_entities,
                "unsampled_entities": unsampled_entities,
                "differences": differences,
                "sample_failures": sample_failures,
                "missing_attachments": missing_attachments,
                "latest_run_id": latest_run.id if latest_run else None,
                "full_import_run_id": completed_full.id if completed_full else None,
                "final_delta_run_id": completed_delta.id if completed_delta else None,
                "checks": checks,
            }
            global_checks.extend(
                {**check, "key": f"{provider}.{check['key']}", "provider": provider}
                for check in checks
            )

        readiness = {
            "ready": all(result["verified"] for result in provider_results.values()),
            "checks": global_checks,
            "evaluated_at": now,
        }
        current_hash = _readiness_hash(
            {
                "providers": provider_results,
                "source_manifests": source_manifests,
                "ready": readiness["ready"],
            }
        )
        readiness["hash"] = current_hash
        return {
            "market_id": market_id,
            "providers": providers,
            "source_manifests": source_manifests,
            "provider_results": provider_results,
            "readiness": readiness,
            "cutover": self._cutover_payload(
                self._latest_cutover(db, market_id=market_id),
                current_hash=current_hash,
            ),
        }

    def approve_cutover(
        self,
        db: Session,
        *,
        market_id: str,
        decided_by: str,
        reason: str,
    ) -> tuple[ImportCutoverDecisionRecord, dict[str, Any]]:
        reconciliation = self.reconciliation(db, market_id=market_id)
        readiness = reconciliation["readiness"]
        if not readiness["ready"]:
            raise ValueError("Cutover cannot be approved until every reconciliation check passes.")
        now = utc_now()
        record = ImportCutoverDecisionRecord(
            id=_new_id("cutover"),
            market_id=market_id,
            status="approved",
            decided_by=decided_by,
            decided_at=now,
            rollback_until=now + _ROLLBACK_WINDOW,
            readiness_hash=readiness["hash"],
            readiness_snapshot=_json_snapshot(
                {
                    "providers": reconciliation["provider_results"],
                    "source_manifests": reconciliation["source_manifests"],
                    "ready": readiness["ready"],
                }
            ),
            reason=reason,
        )
        db.add(record)
        db.flush()
        return record, reconciliation

    def revoke_cutover(
        self,
        db: Session,
        *,
        market_id: str,
        decided_by: str,
        reason: str,
    ) -> ImportCutoverDecisionRecord:
        current = self._latest_cutover(db, market_id=market_id)
        if current is None or current.status != "approved":
            raise ValueError("No approved cutover exists for this market.")
        now = utc_now()
        record = ImportCutoverDecisionRecord(
            id=_new_id("cutover"),
            market_id=market_id,
            status="revoked",
            decided_by=decided_by,
            decided_at=now,
            rollback_until=current.rollback_until,
            readiness_hash=current.readiness_hash,
            readiness_snapshot=current.readiness_snapshot,
            reason=reason,
        )
        db.add(record)
        db.flush()
        return record


import_repository = ImportRepository()
