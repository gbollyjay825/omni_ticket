from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from app.core.config import settings
from app.db.imports import import_repository
from app.db.session import SessionLocal
from app.importers.clients import FreshchatClient, FreshdeskClient
from app.importers.service import freshworks_import_service


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--market-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--started-by", default="migration-cli")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run repeatable Freshdesk and Freshchat migrations into Omni.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    freshdesk_api = commands.add_parser(
        "freshdesk-api",
        help="Import a Freshdesk incremental API window after the full export.",
    )
    _add_common(freshdesk_api)
    freshdesk_api.set_defaults(batch_size=100)
    freshdesk_api.add_argument("--updated-since")

    freshchat_api = commands.add_parser(
        "freshchat-api",
        help="Sync known Freshchat users and their conversations after the full export.",
    )
    _add_common(freshchat_api)
    freshchat_api.set_defaults(batch_size=25)
    freshchat_api.add_argument("--user-ids-file", type=Path, required=True)
    freshchat_api.add_argument("--from-time")

    freshdesk_export = commands.add_parser(
        "freshdesk-export",
        help="Import full Freshdesk contacts, tickets, and conversations export files.",
    )
    _add_common(freshdesk_export)
    freshdesk_export.add_argument("--contacts", type=Path, required=True)
    freshdesk_export.add_argument("--tickets", type=Path, required=True)
    freshdesk_export.add_argument("--conversations", type=Path, required=True)

    freshchat_export = commands.add_parser(
        "freshchat-export",
        help="Import full Freshchat users, conversations, and messages export files.",
    )
    _add_common(freshchat_export)
    freshchat_export.add_argument("--users", type=Path, required=True)
    freshchat_export.add_argument("--conversations", type=Path, required=True)
    freshchat_export.add_argument("--messages", type=Path, required=True)
    return parser


def _required_secret(value: str | None, variable: str) -> str:
    if not value or not value.strip():
        raise RuntimeError(f"{variable} is required in the protected runtime environment")
    return value.strip()


def _known_user_ids(path: Path) -> list[str]:
    if not path.is_file():
        raise RuntimeError(f"Freshchat user ID file does not exist: {path}")
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("user_ids") or payload.get("users")
        if not isinstance(payload, list):
            raise RuntimeError("Freshchat user ID JSON must contain a list")
        values = [item.get("id") if isinstance(item, dict) else item for item in payload]
    else:
        values = [line for line in text.splitlines() if line.strip()]
    user_ids = list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not user_ids:
        raise RuntimeError("Freshchat user ID file is empty")
    return user_ids


def _run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as db:
        if args.command == "freshdesk-export":
            return freshworks_import_service.run_freshdesk_export(
                db,
                market_id=args.market_id,
                contacts_path=args.contacts,
                tickets_path=args.tickets,
                conversations_path=args.conversations,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                started_by=args.started_by,
            )
        if args.command == "freshchat-export":
            return freshworks_import_service.run_freshchat_export(
                db,
                market_id=args.market_id,
                users_path=args.users,
                conversations_path=args.conversations,
                messages_path=args.messages,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                started_by=args.started_by,
            )
        if args.command == "freshdesk-api":
            cursor = import_repository.get_cursor(
                db,
                market_id=args.market_id,
                provider="freshdesk",
                resource="tickets",
            )
            updated_since = args.updated_since or cursor.get("updated_since")
            if not updated_since:
                raise RuntimeError(
                    "No Freshdesk cursor exists. Run the full export first or provide --updated-since."
                )
            freshdesk_client = FreshdeskClient(
                base_url=_required_secret(
                    settings.freshdesk_base_url,
                    "OMNI_FRESHDESK_BASE_URL",
                ),
                api_key=_required_secret(
                    settings.freshdesk_api_key,
                    "OMNI_FRESHDESK_API_KEY",
                ),
                timeout_seconds=settings.freshworks_import_timeout_seconds,
                max_retries=settings.freshworks_import_max_retries,
            )
            try:
                return freshworks_import_service.run_freshdesk_incremental(
                    db,
                    client=freshdesk_client,
                    market_id=args.market_id,
                    updated_since=str(updated_since),
                    dry_run=args.dry_run,
                    batch_size=args.batch_size,
                    started_by=args.started_by,
                )
            finally:
                freshdesk_client.close()
        if args.command == "freshchat-api":
            cursor = import_repository.get_cursor(
                db,
                market_id=args.market_id,
                provider="freshchat",
                resource="messages",
            )
            from_time = args.from_time or cursor.get("from_time")
            freshchat_client = FreshchatClient(
                base_url=_required_secret(
                    settings.freshchat_base_url,
                    "OMNI_FRESHCHAT_BASE_URL",
                ),
                api_token=_required_secret(
                    settings.freshchat_api_token,
                    "OMNI_FRESHCHAT_API_TOKEN",
                ),
                timeout_seconds=settings.freshworks_import_timeout_seconds,
                max_retries=settings.freshworks_import_max_retries,
            )
            try:
                return freshworks_import_service.run_freshchat_known_users(
                    db,
                    client=freshchat_client,
                    market_id=args.market_id,
                    user_ids=_known_user_ids(args.user_ids_file),
                    from_time=str(from_time) if from_time else None,
                    dry_run=args.dry_run,
                    batch_size=args.batch_size,
                    started_by=args.started_by,
                )
            finally:
                freshchat_client.close()
    raise RuntimeError(f"Unsupported import command: {args.command}")


def main() -> None:
    args = _parser().parse_args()
    try:
        result = _run(args)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, indent=2, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
