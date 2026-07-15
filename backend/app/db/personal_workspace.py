from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.audit import write_audit_event
from app.db.models import (
    PersonalTaskRecord,
    TicketRecord,
    TicketTimeEntryRecord,
    TicketWatcherRecord,
    UserRecord,
)
from app.models.domain import (
    CreateTicketTimeEntryRequest,
    PersonalTask,
    PersonalWorkspace,
    TicketTimeEntry,
    UpdatePersonalTaskRequest,
    utc_now,
)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _task(record: PersonalTaskRecord) -> PersonalTask:
    return PersonalTask(
        id=record.id,
        market_id=record.market_id,
        user_id=record.user_id,
        label=record.label,
        completed=record.completed,
        position=record.position,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _time_entry(record: TicketTimeEntryRecord, agent: str) -> TicketTimeEntry:
    return TicketTimeEntry(
        id=record.id,
        market_id=record.market_id,
        ticket_id=record.ticket_id,
        user_id=record.user_id,
        agent=agent,
        minutes=record.minutes,
        note=record.note,
        billable=record.billable,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _ticket_or_404(db: Session, *, market_id: str, ticket_id: str) -> TicketRecord:
    record = db.get(TicketRecord, ticket_id)
    if record is None or record.market_id != market_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return record


class PersonalWorkspaceRepository:
    def get_workspace(self, db: Session, *, market_id: str, user_id: str) -> PersonalWorkspace:
        tasks = db.scalars(
            select(PersonalTaskRecord)
            .where(
                PersonalTaskRecord.market_id == market_id,
                PersonalTaskRecord.user_id == user_id,
            )
            .order_by(
                PersonalTaskRecord.completed.asc(),
                PersonalTaskRecord.position.asc(),
                PersonalTaskRecord.created_at.asc(),
            )
        ).all()
        watched_ticket_ids = list(
            db.scalars(
                select(TicketWatcherRecord.ticket_id)
                .where(
                    TicketWatcherRecord.market_id == market_id,
                    TicketWatcherRecord.user_id == user_id,
                )
                .order_by(TicketWatcherRecord.created_at.asc())
            ).all()
        )
        return PersonalWorkspace(
            tasks=[_task(record) for record in tasks],
            watched_ticket_ids=watched_ticket_ids,
        )

    def create_task(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        label: str,
        actor: str,
    ) -> PersonalTask:
        max_position = db.scalars(
            select(PersonalTaskRecord.position).where(
                PersonalTaskRecord.market_id == market_id,
                PersonalTaskRecord.user_id == user_id,
            )
        ).all()
        record = PersonalTaskRecord(
            id=_id("task"),
            market_id=market_id,
            user_id=user_id,
            label=label.strip(),
            position=max(max_position, default=-1) + 1,
        )
        db.add(record)
        write_audit_event(
            db,
            actor=actor,
            action="personal_task.create",
            entity_type="personal_task",
            entity_id=record.id,
            market_id=market_id,
            details={"user_id": user_id},
        )
        db.commit()
        db.refresh(record)
        return _task(record)

    def update_task(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        task_id: str,
        payload: UpdatePersonalTaskRequest,
        actor: str,
    ) -> PersonalTask:
        record = db.get(PersonalTaskRecord, task_id)
        if record is None or record.market_id != market_id or record.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
        patch = payload.model_dump(exclude_unset=True)
        if "label" in patch:
            record.label = str(patch["label"]).strip()
        if "completed" in patch:
            record.completed = bool(patch["completed"])
        if "position" in patch:
            record.position = int(patch["position"])
        record.updated_at = utc_now()
        write_audit_event(
            db,
            actor=actor,
            action="personal_task.update",
            entity_type="personal_task",
            entity_id=record.id,
            market_id=market_id,
            details={"changes": patch},
        )
        db.commit()
        return _task(record)

    def delete_task(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        task_id: str,
        actor: str,
    ) -> None:
        record = db.get(PersonalTaskRecord, task_id)
        if record is None or record.market_id != market_id or record.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
        db.delete(record)
        write_audit_event(
            db,
            actor=actor,
            action="personal_task.delete",
            entity_type="personal_task",
            entity_id=record.id,
            market_id=market_id,
            details={"user_id": user_id},
        )
        db.commit()

    def watch_ticket(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        ticket_id: str,
        actor: str,
    ) -> None:
        _ticket_or_404(db, market_id=market_id, ticket_id=ticket_id)
        existing = db.scalar(
            select(TicketWatcherRecord).where(
                TicketWatcherRecord.ticket_id == ticket_id,
                TicketWatcherRecord.user_id == user_id,
            )
        )
        if existing is None:
            db.add(
                TicketWatcherRecord(
                    id=_id("watcher"),
                    market_id=market_id,
                    ticket_id=ticket_id,
                    user_id=user_id,
                )
            )
            write_audit_event(
                db,
                actor=actor,
                action="ticket.watch",
                entity_type="ticket",
                entity_id=ticket_id,
                market_id=market_id,
                details={"user_id": user_id},
            )
            db.commit()

    def unwatch_ticket(
        self,
        db: Session,
        *,
        market_id: str,
        user_id: str,
        ticket_id: str,
        actor: str,
    ) -> None:
        record = db.scalar(
            select(TicketWatcherRecord).where(
                TicketWatcherRecord.market_id == market_id,
                TicketWatcherRecord.ticket_id == ticket_id,
                TicketWatcherRecord.user_id == user_id,
            )
        )
        if record is None:
            return
        db.delete(record)
        write_audit_event(
            db,
            actor=actor,
            action="ticket.unwatch",
            entity_type="ticket",
            entity_id=ticket_id,
            market_id=market_id,
            details={"user_id": user_id},
        )
        db.commit()

    def list_time_entries(
        self,
        db: Session,
        *,
        market_id: str,
        ticket_id: str,
    ) -> list[TicketTimeEntry]:
        _ticket_or_404(db, market_id=market_id, ticket_id=ticket_id)
        rows = db.execute(
            select(TicketTimeEntryRecord, UserRecord.name)
            .join(UserRecord, UserRecord.id == TicketTimeEntryRecord.user_id)
            .where(
                TicketTimeEntryRecord.market_id == market_id,
                TicketTimeEntryRecord.ticket_id == ticket_id,
            )
            .order_by(TicketTimeEntryRecord.created_at.asc())
        ).all()
        return [_time_entry(record, agent) for record, agent in rows]

    def create_time_entry(
        self,
        db: Session,
        *,
        market_id: str,
        ticket_id: str,
        user_id: str,
        payload: CreateTicketTimeEntryRequest,
        actor: str,
    ) -> TicketTimeEntry:
        _ticket_or_404(db, market_id=market_id, ticket_id=ticket_id)
        user = db.get(UserRecord, user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
        record = TicketTimeEntryRecord(
            id=_id("time"),
            market_id=market_id,
            ticket_id=ticket_id,
            user_id=user_id,
            minutes=payload.minutes,
            note=payload.note.strip(),
            billable=payload.billable,
        )
        db.add(record)
        write_audit_event(
            db,
            actor=actor,
            action="ticket.time_entry.create",
            entity_type="ticket_time_entry",
            entity_id=record.id,
            market_id=market_id,
            details={"ticket_id": ticket_id, "minutes": payload.minutes},
        )
        db.commit()
        db.refresh(record)
        return _time_entry(record, user.name)

    def delete_time_entry(
        self,
        db: Session,
        *,
        market_id: str,
        ticket_id: str,
        entry_id: str,
        user_id: str,
        actor: str,
    ) -> None:
        record = db.get(TicketTimeEntryRecord, entry_id)
        if (
            record is None
            or record.market_id != market_id
            or record.ticket_id != ticket_id
            or record.user_id != user_id
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Time entry not found")
        db.delete(record)
        write_audit_event(
            db,
            actor=actor,
            action="ticket.time_entry.delete",
            entity_type="ticket_time_entry",
            entity_id=record.id,
            market_id=market_id,
            details={"ticket_id": ticket_id, "minutes": record.minutes},
        )
        db.commit()


personal_workspace_repository = PersonalWorkspaceRepository()
