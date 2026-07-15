from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_operator
from app.api.v1.security import RequestContext, require_context
from app.db.personal_workspace import personal_workspace_repository
from app.db.session import get_db
from app.models.domain import (
    CreatePersonalTaskRequest,
    CreateTicketTimeEntryRequest,
    PersonalTask,
    PersonalWorkspace,
    TicketTimeEntry,
    UpdatePersonalTaskRequest,
)

router = APIRouter(tags=["personal-workspace"])


@router.get("/me/workspace", response_model=PersonalWorkspace)
def get_personal_workspace(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> PersonalWorkspace:
    return personal_workspace_repository.get_workspace(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
    )


@router.post("/me/tasks", response_model=PersonalTask, status_code=status.HTTP_201_CREATED)
def create_personal_task(
    request: CreatePersonalTaskRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> PersonalTask:
    require_operator(context)
    return personal_workspace_repository.create_task(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        label=request.label,
        actor=str(context.user.email),
    )


@router.patch("/me/tasks/{task_id}", response_model=PersonalTask)
def update_personal_task(
    task_id: str,
    request: UpdatePersonalTaskRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> PersonalTask:
    require_operator(context)
    return personal_workspace_repository.update_task(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        task_id=task_id,
        payload=request,
        actor=str(context.user.email),
    )


@router.delete("/me/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personal_task(
    task_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_operator(context)
    personal_workspace_repository.delete_task(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        task_id=task_id,
        actor=str(context.user.email),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/tickets/{ticket_id}/watch", status_code=status.HTTP_204_NO_CONTENT)
def watch_ticket(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_operator(context)
    personal_workspace_repository.watch_ticket(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        ticket_id=ticket_id,
        actor=str(context.user.email),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/tickets/{ticket_id}/watch", status_code=status.HTTP_204_NO_CONTENT)
def unwatch_ticket(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_operator(context)
    personal_workspace_repository.unwatch_ticket(
        db,
        market_id=context.market_id,
        user_id=context.user.id,
        ticket_id=ticket_id,
        actor=str(context.user.email),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tickets/{ticket_id}/time-entries", response_model=list[TicketTimeEntry])
def list_ticket_time_entries(
    ticket_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[TicketTimeEntry]:
    return personal_workspace_repository.list_time_entries(
        db,
        market_id=context.market_id,
        ticket_id=ticket_id,
    )


@router.post(
    "/tickets/{ticket_id}/time-entries",
    response_model=TicketTimeEntry,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket_time_entry(
    ticket_id: str,
    request: CreateTicketTimeEntryRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> TicketTimeEntry:
    require_operator(context)
    return personal_workspace_repository.create_time_entry(
        db,
        market_id=context.market_id,
        ticket_id=ticket_id,
        user_id=context.user.id,
        payload=request,
        actor=str(context.user.email),
    )


@router.delete(
    "/tickets/{ticket_id}/time-entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ticket_time_entry(
    ticket_id: str,
    entry_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> Response:
    require_operator(context)
    personal_workspace_repository.delete_time_entry(
        db,
        market_id=context.market_id,
        ticket_id=ticket_id,
        entry_id=entry_id,
        user_id=context.user.id,
        actor=str(context.user.email),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
