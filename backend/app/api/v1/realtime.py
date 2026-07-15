from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from redis import asyncio as redis_async
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.api.v1.security import RequestContext, require_context
from app.core.config import settings
from app.db.models import (
    ChatConversationRecord,
    ChatMessageRecord,
    TicketRecord,
    TimelineEventRecord,
)
from app.db.realtime import realtime_event_repository, redis_channel
from app.db.session import SessionLocal, get_db
from app.models.domain import utc_now

router = APIRouter(tags=["realtime"])


def _durable_cursor(cursor: str | None) -> str | None:
    if cursor and cursor.startswith("ephemeral_"):
        return None
    return cursor


@router.get("/realtime/events")
def list_realtime_events(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        events = realtime_event_repository.list_after(
            db,
            market_id=context.market_id,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "events": events,
        "cursor": events[-1]["event_id"] if events else cursor,
        "has_more": len(events) == min(limit, settings.realtime_backlog_limit),
    }


def _websocket_token(websocket: WebSocket) -> str | None:
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    for protocol in (item.strip() for item in protocols.split(",")):
        if protocol.startswith("bearer."):
            return protocol.removeprefix("bearer.")
    return None


async def _send_if_new(
    websocket: WebSocket,
    envelope: dict[str, Any],
    sent_ids: set[str],
) -> bool:
    event_id = str(envelope.get("event_id", ""))
    if not event_id or event_id in sent_ids:
        return False
    sent_ids.add(event_id)
    await websocket.send_json(envelope)
    return True


async def _publish_ephemeral(
    redis_client: redis_async.Redis | None,
    *,
    context: RequestContext,
    message: dict[str, Any],
) -> dict[str, Any]:
    event_type = str(message.get("type", ""))
    aggregate_id = str(message.get("aggregate_id", ""))
    raw_payload = message.get("payload")
    payload: dict[str, Any] = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    now = utc_now()
    envelope = {
        "event_id": f"ephemeral_{uuid4().hex}",
        "type": event_type,
        "organization_id": "wakanow",
        "market_id": context.market_id,
        "aggregate_type": "conversation",
        "aggregate_id": aggregate_id,
        "version": int(now.timestamp() * 1_000_000),
        "timestamp": now.isoformat(),
        "payload": {
            **payload,
            "user_id": context.user.id,
            "user_name": context.user.name,
        },
    }
    if redis_client is not None:
        if event_type == "presence.updated":
            await redis_client.setex(
                f"{settings.realtime_channel_prefix}:presence:{context.market_id}:{context.user.id}",
                settings.realtime_presence_ttl_seconds,
                json.dumps(envelope, separators=(",", ":")),
            )
        await redis_client.publish(
            redis_channel(context.market_id),
            json.dumps(envelope, separators=(",", ":")),
        )
    return envelope


def _validate_client_event(
    db: Session,
    *,
    context: RequestContext,
    event_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> str | None:
    if event_type == "presence.updated":
        if aggregate_id != context.user.id:
            return "Presence can only be updated for the authenticated user"
        return None

    conversation = db.get(ChatConversationRecord, aggregate_id)
    ticket = db.get(TicketRecord, aggregate_id) if conversation is None else None
    if conversation is not None and conversation.market_id != context.market_id:
        return "Conversation was not found in the active market"
    if conversation is None and (ticket is None or ticket.market_id != context.market_id):
        return "Conversation was not found in the active market"

    message_id = str(payload.get("message_id", "")).strip()
    if message_id:
        if conversation is not None:
            message = db.get(ChatMessageRecord, message_id)
            valid_message = message is not None and message.conversation_id == conversation.id
        else:
            assert ticket is not None
            legacy_message = db.get(TimelineEventRecord, message_id)
            valid_message = legacy_message is not None and legacy_message.ticket_id == ticket.id
        if not valid_message:
            return "Message was not found in the conversation"
    return None


@router.websocket("/realtime")
async def realtime_socket(websocket: WebSocket) -> None:
    token = _websocket_token(websocket)
    session_cookie = websocket.cookies.get(settings.session_cookie_name)
    if token is None and session_cookie is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    market_id = websocket.query_params.get("market_id")
    cursor = _durable_cursor(websocket.query_params.get("cursor"))
    with SessionLocal() as auth_db:
        try:
            context = require_context(
                authorization=f"Bearer {token}" if token else None,
                market_header=market_id,
                session_cookie=session_cookie,
                db=auth_db,
            )
        except HTTPException as exc:
            close_code = 4403 if exc.status_code == status.HTTP_403_FORBIDDEN else 4401
            await websocket.close(code=close_code, reason=str(exc.detail))
            return

    await websocket.accept(subprotocol="omni.realtime.v1")
    redis_client: redis_async.Redis | None = None
    pubsub: Any = None
    if settings.redis_url:
        try:
            redis_client = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            await pubsub.subscribe(redis_channel(context.market_id))
        except RedisError:
            if pubsub is not None:
                await pubsub.aclose()
            if redis_client is not None:
                await redis_client.aclose()
            redis_client = None
            pubsub = None

    sent_ids: set[str] = set()
    last_cursor = cursor
    if last_cursor is None:
        with SessionLocal() as event_db:
            last_cursor = realtime_event_repository.latest_cursor(
                event_db,
                market_id=context.market_id,
            )
    await websocket.send_json(
        {
            "type": "realtime.ready",
            "market_id": context.market_id,
            "user_id": context.user.id,
            "cursor": last_cursor,
            "fanout": "redis" if redis_client is not None else "database-poll",
        }
    )
    durable_catchup_pending = True

    try:
        while True:
            durable_events: list[dict[str, Any]] = []
            if redis_client is None or durable_catchup_pending:
                with SessionLocal() as event_db:
                    try:
                        durable_events = realtime_event_repository.list_after(
                            event_db,
                            market_id=context.market_id,
                            cursor=last_cursor,
                            limit=settings.realtime_backlog_limit,
                        )
                    except ValueError:
                        last_cursor = None
                        durable_events = realtime_event_repository.list_after(
                            event_db,
                            market_id=context.market_id,
                            cursor=None,
                            limit=settings.realtime_backlog_limit,
                        )
                durable_catchup_pending = False
            for envelope in durable_events:
                await _send_if_new(websocket, envelope, sent_ids)
                last_cursor = str(envelope["event_id"])

            if pubsub is not None:
                try:
                    redis_message = await pubsub.get_message(timeout=0.01)
                except RedisError:
                    redis_message = None
                if redis_message and redis_message.get("type") == "message":
                    raw = redis_message.get("data")
                    if isinstance(raw, str):
                        await _send_if_new(websocket, json.loads(raw), sent_ids)

            try:
                client_message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=min(settings.realtime_poll_interval_seconds, 0.25)
                    if redis_client is not None
                    else settings.realtime_poll_interval_seconds,
                )
            except TimeoutError:
                continue
            if not isinstance(client_message, dict):
                continue
            message_type = str(client_message.get("type", ""))
            if message_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": utc_now().isoformat()})
                continue
            if message_type not in {"presence.updated", "typing.updated", "message.read"}:
                await websocket.send_json(
                    {"type": "realtime.error", "detail": "Unsupported realtime event type"}
                )
                continue
            aggregate_id = str(client_message.get("aggregate_id", "")).strip()
            if not aggregate_id:
                await websocket.send_json(
                    {"type": "realtime.error", "detail": "aggregate_id is required"}
                )
                continue
            raw_payload = client_message.get("payload")
            payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
            with SessionLocal() as validation_db:
                validation_error = _validate_client_event(
                    validation_db,
                    context=context,
                    event_type=message_type,
                    aggregate_id=aggregate_id,
                    payload=payload,
                )
            if validation_error:
                await websocket.send_json(
                    {"type": "realtime.error", "detail": validation_error}
                )
                continue
            if message_type == "message.read":
                with SessionLocal() as event_db:
                    envelope = realtime_event_repository.record(
                        event_db,
                        market_id=context.market_id,
                        event_type=message_type,
                        aggregate_type="conversation",
                        aggregate_id=aggregate_id,
                        payload={
                            **payload,
                            "user_id": context.user.id,
                            "user_name": context.user.name,
                        },
                    )
                await _send_if_new(websocket, envelope, sent_ids)
            else:
                envelope = await _publish_ephemeral(
                    redis_client,
                    context=context,
                    message=client_message,
                )
                if redis_client is None:
                    await _send_if_new(websocket, envelope, sent_ids)
    except WebSocketDisconnect:
        pass
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(redis_channel(context.market_id))
            await pubsub.aclose()
        if redis_client is not None:
            await redis_client.aclose()
