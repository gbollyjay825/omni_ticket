# Omni completion kit (workflow-generated reference)

> Auto-generated code-level implementation kits for the remaining Omni parity work
> (B-112 remaining modules, B-113, B-114, stubs, credentials, UX). Reference only —
> apply each module as a sequential, individually-verified slice, then commit.

Continuing the verbatim b112-data kit at the cut point (C6 payload helper).

```python
def _custom_object_payload(
    request: CreateCustomObjectRequest | UpdateCustomObjectRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Custom object name is required",
            )
    if "description" in payload and payload["description"] is not None:
        payload["description"] = payload["description"].strip()
    if "fields" in payload and payload["fields"] is not None:
        seen: set[str] = set()
        fields: list[dict] = []
        for field in payload["fields"]:
            key = str(field.get("key", "")).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            field["key"] = key
            field["label"] = str(field.get("label", "")).strip()
            field["options"] = _normalized_options(field.get("options") or [])
            if field.get("field_type") not in _OPTION_FIELD_TYPES:
                field["options"] = []
            fields.append(field)
        payload["fields"] = fields
    return payload
```

**Repo methods** — after `update_company_field`:

```python
    def list_custom_objects(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[CustomObject]:
        records = db.scalars(
            select(CustomObjectRecord).where(CustomObjectRecord.market_id == market_id)
        ).all()
        objects = [custom_object_from_record(record) for record in records]
        objects.sort(key=lambda obj: (not obj.active, obj.name.lower()))
        state.custom_objects = {
            **{
                key: value
                for key, value in state.custom_objects.items()
                if value.market_id != market_id
            },
            **{obj.id: obj for obj in objects},
        }
        return objects

    def create_custom_object(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateCustomObjectRequest,
        market_id: str,
        actor: str,
    ) -> CustomObject:
        payload = _custom_object_payload(request)
        payload["key"] = payload["key"].strip().lower()
        duplicate = db.scalar(
            select(CustomObjectRecord).where(
                CustomObjectRecord.market_id == market_id,
                CustomObjectRecord.key == payload["key"],
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Custom object key already exists")
        record = CustomObjectRecord(id=_new_id("object"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="custom_object.create",
            entity_type="custom_object",
            entity_id=record.id,
            market_id=market_id,
            details={"key": record.key, "name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        custom_object = custom_object_from_record(record)
        state.custom_objects[custom_object.id] = custom_object
        return custom_object

    def update_custom_object(
        self,
        db: Session,
        state: InMemoryStore,
        object_id: str,
        request: UpdateCustomObjectRequest,
        market_id: str,
        actor: str,
    ) -> CustomObject:
        record = db.get(CustomObjectRecord, object_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Custom object not found")
        patch = _custom_object_payload(request)
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="custom_object.update",
            entity_type="custom_object",
            entity_id=object_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        custom_object = custom_object_from_record(record)
        state.custom_objects[custom_object.id] = custom_object
        return custom_object
```

### C7. `app/core/store.py` — import `CustomObject,` and `CustomObjectField,`; field `self.custom_objects: dict[str, CustomObject] = {}` (after `company_fields`); seed after `self.company_fields = {...}`:

```python
            self.custom_objects = {
                "object-loyalty-account": CustomObject(
                    id="object-loyalty-account",
                    market_id="market-ng",
                    key="loyalty_account",
                    name="Loyalty account",
                    description="Frequent-flyer account linked to a traveller.",
                    fields=[
                        CustomObjectField(
                            key="membership_id",
                            label="Membership ID",
                            field_type=TicketFieldType.text,
                            required=True,
                        ),
                        CustomObjectField(
                            key="tier",
                            label="Tier",
                            field_type=TicketFieldType.select,
                            options=["Blue", "Silver", "Gold", "Platinum"],
                        ),
                        CustomObjectField(
                            key="points_balance",
                            label="Points balance",
                            field_type=TicketFieldType.number,
                        ),
                    ],
                ),
                "object-asset": CustomObject(
                    id="object-asset",
                    market_id="market-ng",
                    key="travel_asset",
                    name="Travel asset",
                    description="Physical or digital asset tied to a booking (device, voucher, baggage tag).",
                    fields=[
                        CustomObjectField(
                            key="asset_tag",
                            label="Asset tag",
                            field_type=TicketFieldType.text,
                            required=True,
                        ),
                        CustomObjectField(
                            key="asset_type",
                            label="Asset type",
                            field_type=TicketFieldType.select,
                            options=["Voucher", "Baggage tag", "Device", "SIM"],
                        ),
                    ],
                ),
            }
```

### C8. `app/db/bootstrap.py` — import `CustomObjectRecord,`; add `seed_custom_objects`; call after `seed_company_fields` (early-return), and `add_all` after the `CompanyFieldRecord` block:

```python
def seed_custom_objects(session: Session, source: InMemoryStore = store) -> None:
    for custom_object in source.custom_objects.values():
        existing = session.get(CustomObjectRecord, custom_object.id) or session.scalar(
            select(CustomObjectRecord).where(
                CustomObjectRecord.market_id == custom_object.market_id,
                CustomObjectRecord.key == custom_object.key,
            )
        )
        if existing is not None:
            continue
        session.add(CustomObjectRecord(**_payload(custom_object)))
    session.commit()
```
```python
    session.add_all(
        [
            CustomObjectRecord(**_payload(custom_object))
            for custom_object in source.custom_objects.values()
        ]
    )
```

### C9. `app/db/store_sync.py` — import `custom_object_from_record,` / `CustomObjectRecord,`; persist after `company_fields`:

```python
    for custom_object in state.custom_objects.values():
        payload = custom_object.model_dump(mode="json")
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        _merge_record(db, CustomObjectRecord, payload)
```
hydrate after `state.company_fields`:
```python
    state.custom_objects = {
        custom_object.id: custom_object_from_record(custom_object)
        for custom_object in db.scalars(select(CustomObjectRecord)).all()
    }
```

### C10. `app/api/v1/resources.py` — import `CustomObject`, `CreateCustomObjectRequest`, `UpdateCustomObjectRequest`; add 3 routes after `update_company_field`; snapshot key after `"company_fields"`:

```python
@router.get("/custom-objects", response_model=list[CustomObject])
def list_custom_objects(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[CustomObject]:
    return management_repository.list_custom_objects(db, state, context.market_id)


@router.post("/custom-objects", response_model=CustomObject, status_code=status.HTTP_201_CREATED)
def create_custom_object(
    request: CreateCustomObjectRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomObject:
    require_admin(context)
    return management_repository.create_custom_object(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/custom-objects/{object_id}", response_model=CustomObject)
def update_custom_object(
    object_id: str,
    request: UpdateCustomObjectRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> CustomObject:
    require_admin(context)
    return management_repository.update_custom_object(
        db,
        state,
        object_id,
        request,
        context.market_id,
        context.user.email,
    )
```
```python
        "custom_objects": management_repository.list_custom_objects(db, state, context.market_id),
```

---

## PART D — PORTAL BRANDING (extends `workspace_settings`, no new table) — **migration `0035`, `down_revision = "20260606_0034"`**

### D1. `app/models/domain.py`

**Anchor:** `class WorkspaceSettings` (line 322). Add the branding fields (append after `public_brand_name`):

```python
class WorkspaceSettings(BaseModel):
    market_id: str = "market-ng"
    ai_work_queue_automation_enabled: bool = True
    ai_can_send_customer_messages: bool = False
    default_timezone: str = "Africa/Lagos"
    business_hours: str = "Mon-Fri 08:00-18:00"
    public_brand_name: str = "Omni Ticket"
    portal_logo_url: str = ""
    portal_primary_color: str = "#2563eb"
    portal_accent_color: str = "#9333ea"
    portal_support_email: str = ""
    portal_headline: str = "How can we help you today?"
```

### D2. `app/db/models.py`

**Anchor:** `class WorkspaceSettingsRecord` (line 84). Append after `public_brand_name`:

```python
    public_brand_name: Mapped[str] = mapped_column(String(160), default="Omni Ticket")
    portal_logo_url: Mapped[str] = mapped_column(String(500), default="")
    portal_primary_color: Mapped[str] = mapped_column(String(16), default="#2563eb")
    portal_accent_color: Mapped[str] = mapped_column(String(16), default="#9333ea")
    portal_support_email: Mapped[str] = mapped_column(String(255), default="")
    portal_headline: Mapped[str] = mapped_column(String(255), default="How can we help you today?")
```

### D3. Migration `migrations/versions/20260606_0031_portal_branding.py` (full file) — **rename to `0035`, `revision = "20260606_0035"`, `down_revision = "20260606_0034"`**

```python
"""add portal branding columns to workspace settings

Revision ID: 20260606_0031
Revises: 20260606_0030
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0031"
down_revision: str | None = "20260606_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_settings",
        sa.Column("portal_logo_url", sa.String(length=500), nullable=False, server_default=""),
    )
    op.add_column(
        "workspace_settings",
        sa.Column("portal_primary_color", sa.String(length=16), nullable=False, server_default="#2563eb"),
    )
    op.add_column(
        "workspace_settings",
        sa.Column("portal_accent_color", sa.String(length=16), nullable=False, server_default="#9333ea"),
    )
    op.add_column(
        "workspace_settings",
        sa.Column("portal_support_email", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "workspace_settings",
        sa.Column(
            "portal_headline",
            sa.String(length=255),
            nullable=False,
            server_default="How can we help you today?",
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace_settings", "portal_headline")
    op.drop_column("workspace_settings", "portal_support_email")
    op.drop_column("workspace_settings", "portal_accent_color")
    op.drop_column("workspace_settings", "portal_primary_color")
    op.drop_column("workspace_settings", "portal_logo_url")
```

### D4. `app/db/mappers.py` — extend `workspace_settings_from_record` (line 126):

```python
def workspace_settings_from_record(record: WorkspaceSettingsRecord) -> WorkspaceSettings:
    return WorkspaceSettings(
        market_id=record.market_id,
        ai_work_queue_automation_enabled=record.ai_work_queue_automation_enabled,
        ai_can_send_customer_messages=record.ai_can_send_customer_messages,
        default_timezone=record.default_timezone,
        business_hours=record.business_hours,
        public_brand_name=record.public_brand_name,
        portal_logo_url=record.portal_logo_url,
        portal_primary_color=record.portal_primary_color,
        portal_accent_color=record.portal_accent_color,
        portal_support_email=record.portal_support_email,
        portal_headline=record.portal_headline,
    )
```

### D5. `app/db/settings.py` — extend the duplicate mapper here (line 7) identically:

```python
def workspace_settings_from_record(record: WorkspaceSettingsRecord) -> WorkspaceSettings:
    return WorkspaceSettings(
        market_id=record.market_id,
        ai_work_queue_automation_enabled=record.ai_work_queue_automation_enabled,
        ai_can_send_customer_messages=record.ai_can_send_customer_messages,
        default_timezone=record.default_timezone,
        business_hours=record.business_hours,
        public_brand_name=record.public_brand_name,
        portal_logo_url=record.portal_logo_url,
        portal_primary_color=record.portal_primary_color,
        portal_accent_color=record.portal_accent_color,
        portal_support_email=record.portal_support_email,
        portal_headline=record.portal_headline,
    )
```

> **Route reuse — no change needed:** `PATCH /settings` in `app/api/v1/settings.py` iterates `WorkspaceSettings.model_fields.keys()` and setattr-s any allowed field except `market_id`. The 5 new branding fields are now automatically writable and audited under `settings.update`. `_repair_legacy_schema` is not needed because `_stamp_schema_head` + `Base.metadata.create_all` create the columns on fresh DBs; the migration handles existing DBs.

### D6. `bootstrap.py` / `store_sync.py` — **no change.** Workspace settings are seeded/persisted via `_payload(settings)` / `settings.model_dump()`, which already include all model fields.

---

## PART E — BACKEND TESTS

### E1. `tests/test_operations.py`

Add after `test_admin_manages_ticket_templates` (line 1523). These mirror `test_admin_manages_business_hours`:

```python
def test_admin_manages_contact_fields(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/contact-fields",
        json={
            "key": f"loyalty_{suffix}",
            "label": "Loyalty tier",
            "field_type": "select",
            "options": ["Gold", "Gold", "Silver"],
            "position": 15,
        },
    )
    assert created.status_code == 201
    field = created.json()
    assert field["options"] == ["Gold", "Silver"]  # de-duplicated

    listing = client.get("/api/v1/contact-fields")
    assert listing.status_code == 200
    assert any(item["id"] == field["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/contact-fields/{field['id']}",
        json={"active": False, "label": "Loyalty level"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["label"] == "Loyalty level"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == field["id"] for item in snapshot.json()["contact_fields"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "contact_field.create" for event in audit)
    assert any(event["action"] == "contact_field.update" for event in audit)


def test_admin_manages_company_fields(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/company-fields",
        json={
            "key": f"contract_{suffix}",
            "label": "Contract type",
            "field_type": "select",
            "options": ["Annual", "Trial"],
            "position": 12,
        },
    )
    assert created.status_code == 201
    field = created.json()
    assert field["field_type"] == "select"

    updated = client.patch(
        f"/api/v1/company-fields/{field['id']}",
        json={"required": True},
    )
    assert updated.status_code == 200
    assert updated.json()["required"] is True

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == field["id"] for item in snapshot.json()["company_fields"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "company_field.create" for event in audit)
    assert any(event["action"] == "company_field.update" for event in audit)


def test_admin_manages_custom_objects(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/custom-objects",
        json={
            "key": f"asset_{suffix}",
            "name": "Travel asset",
            "description": "Asset tied to a booking.",
            "fields": [
                {"key": "asset_tag", "label": "Asset tag", "field_type": "text", "required": True},
                {"key": "asset_type", "label": "Asset type", "field_type": "select", "options": ["Voucher", "SIM"]},
            ],
        },
    )
    assert created.status_code == 201
    custom_object = created.json()
    assert len(custom_object["fields"]) == 2
    assert custom_object["fields"][0]["key"] == "asset_tag"

    updated = client.patch(
        f"/api/v1/custom-objects/{custom_object['id']}",
        json={"active": False, "description": "Retired asset schema."},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == custom_object["id"] for item in snapshot.json()["custom_objects"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "custom_object.create" for event in audit)
    assert any(event["action"] == "custom_object.update" for event in audit)


def test_admin_updates_portal_branding(client: TestClient) -> None:
    updated = client.patch(
        "/api/v1/settings",
        json={
            "portal_logo_url": "https://cdn.example.com/logo.png",
            "portal_primary_color": "#0f766e",
            "portal_support_email": "help@omniticket.example.com",
            "portal_headline": "We are here to help",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["portal_logo_url"] == "https://cdn.example.com/logo.png"
    assert body["portal_primary_color"] == "#0f766e"
    assert body["portal_headline"] == "We are here to help"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["settings"]["portal_support_email"] == "help@omniticket.example.com"
```

### E2. `tests/test_database.py`

- Bump head: `ALEMBIC_HEAD = "20260606_0031"` **[SUPERSEDED — use `0045`]**.
- Add table assertions in `test_database_schema_and_seed_are_postgres_ready_with_local_sqlite` (after line 37 `assert "ticket_templates" in tables`):
```python
    assert "contact_fields" in tables
    assert "company_fields" in tables
    assert "custom_objects" in tables
```
- In `test_create_schema_repairs_legacy_user_auth_columns_and_stamps_head` (after line 152 `assert "ticket_templates"`):
```python
    assert "contact_fields" in inspector.get_table_names()
    assert "company_fields" in inspector.get_table_names()
    assert "custom_objects" in inspector.get_table_names()
```

> The head-stamp test compares the stamped revision against `ALEMBIC_HEAD`; `_alembic_head_revision()` derives the head by sorting filenames, so `20260606_0031` sorts last — consistent.

---

## PART F — FRONTEND

### F1. `src/domain.ts`

**Interfaces** — after `TicketField` (line 162), add (channel-agnostic mirror):

```typescript
export interface ContactField {
  id: string
  key: string
  label: string
  fieldType: TicketFieldType
  required: boolean
  active: boolean
  system: boolean
  options: string[]
  placeholder: string
  helpText: string
  position: number
  updatedAt: string
}

export interface CompanyField {
  id: string
  key: string
  label: string
  fieldType: TicketFieldType
  required: boolean
  active: boolean
  system: boolean
  options: string[]
  placeholder: string
  helpText: string
  position: number
  updatedAt: string
}

export interface CustomObjectFieldDef {
  key: string
  label: string
  fieldType: TicketFieldType
  required: boolean
  options: string[]
}

export interface CustomObject {
  id: string
  key: string
  name: string
  description: string
  active: boolean
  fields: CustomObjectFieldDef[]
  updatedAt: string
}
```

**WorkspaceSettings** — replace (line 342):

```typescript
export interface WorkspaceSettings {
  aiWorkQueueAutomationEnabled: boolean
  publicBrandName: string
  portalLogoUrl: string
  portalPrimaryColor: string
  portalAccentColor: string
  portalSupportEmail: string
  portalHeadline: string
}
```

**OmniState** — after `ticketFields: TicketField[]` (line 376):
```typescript
  contactFields: ContactField[]
  companyFields: CompanyField[]
  customObjects: CustomObject[]
```

### F2. `src/backend.ts`

**BackendSettings** (line 5) — append branding fields:
```typescript
export interface BackendSettings {
  market_id: string
  ai_work_queue_automation_enabled: boolean
  ai_can_send_customer_messages: boolean
  default_timezone: string
  business_hours: string
  public_brand_name: string
  portal_logo_url: string
  portal_primary_color: string
  portal_accent_color: string
  portal_support_email: string
  portal_headline: string
}
```

**Backend types** — after `BackendUpdateTicketFieldInput` (line 1260), add:

```typescript
export interface BackendContactField {
  id: string
  market_id: string
  key: string
  label: string
  field_type: BackendTicketFieldType
  required: boolean
  active: boolean
  system: boolean
  options: string[]
  placeholder: string
  help_text: string
  position: number
  updated_at: string
}

export interface BackendCreateContactFieldInput {
  key: string
  label: string
  field_type: BackendTicketFieldType
  required?: boolean
  active?: boolean
  options?: string[]
  placeholder?: string
  help_text?: string
  position?: number
}

export type BackendUpdateContactFieldInput = Partial<Omit<BackendCreateContactFieldInput, 'key'>>

export type BackendCompanyField = Omit<BackendContactField, never>
export type BackendCreateCompanyFieldInput = BackendCreateContactFieldInput
export type BackendUpdateCompanyFieldInput = BackendUpdateContactFieldInput

export interface BackendCustomObjectField {
  key: string
  label: string
  field_type: BackendTicketFieldType
  required: boolean
  options: string[]
}

export interface BackendCustomObject {
  id: string
  market_id: string
  key: string
  name: string
  description: string
  active: boolean
  fields: BackendCustomObjectField[]
  created_at: string
  updated_at: string
}

export interface BackendCreateCustomObjectInput {
  key: string
  name: string
  description?: string
  active?: boolean
  fields?: BackendCustomObjectField[]
}

export interface BackendUpdateCustomObjectInput {
  name?: string
  description?: string
  active?: boolean
  fields?: BackendCustomObjectField[]
}
```

**BackendSnapshot** — add camel keys after `ticketFields:` (line 518):
```typescript
  contactFields: BackendContactField[]
  companyFields: BackendCompanyField[]
  customObjects: BackendCustomObject[]
```
and snake keys after `ticket_fields:` (line 541):
```typescript
  contact_fields: BackendContactField[]
  company_fields: BackendCompanyField[]
  custom_objects: BackendCustomObject[]
```

**BackendFrontendSnapshot** — after `ticket_fields:` (line 1346):
```typescript
  contact_fields: BackendContactField[]
  company_fields: BackendCompanyField[]
  custom_objects: BackendCustomObject[]
```

**Snapshot normalization** — in `fetchBackendSnapshot` return object, after `ticketFields: frontendSnapshot.ticket_fields ?? [],` (line 1509):
```typescript
    contactFields: frontendSnapshot.contact_fields ?? [],
    companyFields: frontendSnapshot.company_fields ?? [],
    customObjects: frontendSnapshot.custom_objects ?? [],
```

**Client fns** — after `patchBackendTicketField` (find near line 2041; the existing pair is `createBackendTicketField`/`patchBackendTicketField`). Add:

```typescript
export async function createBackendContactField(
  input: BackendCreateContactFieldInput,
  session: BackendSession,
): Promise<BackendContactField> {
  return fetchJson<BackendContactField>('/contact-fields', {
    method: 'POST',
    body: JSON.stringify(input),
  }, session)
}

export async function patchBackendContactField(
  fieldId: string,
  patch: BackendUpdateContactFieldInput,
  session: BackendSession,
): Promise<BackendContactField> {
  return fetchJson<BackendContactField>(`/contact-fields/${fieldId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function createBackendCompanyField(
  input: BackendCreateCompanyFieldInput,
  session: BackendSession,
): Promise<BackendCompanyField> {
  return fetchJson<BackendCompanyField>('/company-fields', {
    method: 'POST',
    body: JSON.stringify(input),
  }, session)
}

export async function patchBackendCompanyField(
  fieldId: string,
  patch: BackendUpdateCompanyFieldInput,
  session: BackendSession,
): Promise<BackendCompanyField> {
  return fetchJson<BackendCompanyField>(`/company-fields/${fieldId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}

export async function createBackendCustomObject(
  input: BackendCreateCustomObjectInput,
  session: BackendSession,
): Promise<BackendCustomObject> {
  return fetchJson<BackendCustomObject>('/custom-objects', {
    method: 'POST',
    body: JSON.stringify(input),
  }, session)
}

export async function patchBackendCustomObject(
  objectId: string,
  patch: BackendUpdateCustomObjectInput,
  session: BackendSession,
): Promise<BackendCustomObject> {
  return fetchJson<BackendCustomObject>(`/custom-objects/${objectId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }, session)
}
```

### F3. `src/store.ts`

**Imports (top of file):**
- Domain (lines ~24-31): add `ContactField,`, `CompanyField,`, `CustomObject,`, `CustomObjectFieldDef,`.
- Client fns (`createBackend*`): add `createBackendContactField,`, `createBackendCompanyField,`, `createBackendCustomObject,`.
- `patchBackend*`: add `patchBackendContactField,`, `patchBackendCompanyField,`, `patchBackendCustomObject,`.
- Create input types: add `type BackendCreateContactFieldInput,`, `type BackendCreateCompanyFieldInput,`, `type BackendCreateCustomObjectInput,`.
- Update input types: add `type BackendUpdateContactFieldInput,`, `type BackendUpdateCompanyFieldInput,`, `type BackendUpdateCustomObjectInput,`.
- Backend record types: add `type BackendContactField,`, `type BackendCompanyField,`, `type BackendCustomObject,`.

**Mappers** — after `mapTicketField` (line 430):

```typescript
function mapContactField(field: BackendContactField): ContactField {
  return {
    id: field.id,
    key: field.key,
    label: field.label,
    fieldType: field.field_type,
    required: field.required,
    active: field.active,
    system: field.system,
    options: field.options,
    placeholder: field.placeholder,
    helpText: field.help_text,
    position: field.position,
    updatedAt: field.updated_at,
  }
}

function mapCompanyField(field: BackendCompanyField): CompanyField {
  return {
    id: field.id,
    key: field.key,
    label: field.label,
    fieldType: field.field_type,
    required: field.required,
    active: field.active,
    system: field.system,
    options: field.options,
    placeholder: field.placeholder,
    helpText: field.help_text,
    position: field.position,
    updatedAt: field.updated_at,
  }
}

function mapCustomObject(custom: BackendCustomObject): CustomObject {
  return {
    id: custom.id,
    key: custom.key,
    name: custom.name,
    description: custom.description,
    active: custom.active,
    fields: (custom.fields ?? []).map(
      (field): CustomObjectFieldDef => ({
        key: field.key,
        label: field.label,
        fieldType: field.field_type,
        required: field.required,
        options: field.options ?? [],
      }),
    ),
    updatedAt: custom.updated_at,
  }
}
```

**Settings mapper** — replace the `const settings = {...}` block in `mergeBackendSnapshot` (line 772):
```typescript
  const settings = {
    ...current.settings,
    aiWorkQueueAutomationEnabled: snapshot.settings.ai_work_queue_automation_enabled,
    publicBrandName: snapshot.settings.public_brand_name,
    portalLogoUrl: snapshot.settings.portal_logo_url,
    portalPrimaryColor: snapshot.settings.portal_primary_color,
    portalAccentColor: snapshot.settings.portal_accent_color,
    portalSupportEmail: snapshot.settings.portal_support_email,
    portalHeadline: snapshot.settings.portal_headline,
  }
```

**Hydration** — in the `routeStateFromUrl({ ... })` return, after `ticketFields: (snapshot.ticket_fields ?? snapshot.ticketFields ?? []).map(mapTicketField),` (line 825):
```typescript
    contactFields: (snapshot.contact_fields ?? snapshot.contactFields ?? []).map(mapContactField),
    companyFields: (snapshot.company_fields ?? snapshot.companyFields ?? []).map(mapCompanyField),
    customObjects: (snapshot.custom_objects ?? snapshot.customObjects ?? []).map(mapCustomObject),
```

**Rehydration merge** — in `mergeReferenceData` after `ticketFields:` (line 250):
```typescript
    contactFields: state.contactFields ?? initialOmniState.contactFields,
    companyFields: state.companyFields ?? initialOmniState.companyFields,
    customObjects: state.customObjects ?? initialOmniState.customObjects,
```

**Actions** — after `updateTicketField` (line 1979):
```typescript
  function createContactField(input: BackendCreateContactFieldInput) {
    return syncBackendMutation((session) => createBackendContactField(input, session))
  }

  function updateContactField(fieldId: string, patch: BackendUpdateContactFieldInput) {
    return syncBackendMutation((session) => patchBackendContactField(fieldId, patch, session))
  }

  function createCompanyField(input: BackendCreateCompanyFieldInput) {
    return syncBackendMutation((session) => createBackendCompanyField(input, session))
  }

  function updateCompanyField(fieldId: string, patch: BackendUpdateCompanyFieldInput) {
    return syncBackendMutation((session) => patchBackendCompanyField(fieldId, patch, session))
  }

  function createCustomObject(input: BackendCreateCustomObjectInput) {
    return syncBackendMutation((session) => createBackendCustomObject(input, session))
  }

  function updateCustomObject(objectId: string, patch: BackendUpdateCustomObjectInput) {
    return syncBackendMutation((session) => patchBackendCustomObject(objectId, patch, session))
  }
```

**Expose** — in the actions return object, after `updateTicketField,` (line 2234):
```typescript
    createContactField,
    updateContactField,
    createCompanyField,
    updateCompanyField,
    createCustomObject,
    updateCustomObject,
```

> **Portal branding write:** `patchBackendSettings(patch: Partial<BackendSettings>, …)` already exists. If a generic `updateSettings(patch: Partial<BackendSettings>)` action does not already exist, add:
> ```typescript
>   function updateWorkspaceSettings(patch: Partial<BackendSettings>) {
>     return syncBackendMutation((session) => patchBackendSettings(patch, session))
>   }
> ```
> import `patchBackendSettings` if not already imported, and expose `updateWorkspaceSettings,` in the return object.

### F4. `src/seed.ts`

**Defaults** — after `ticketFields: seedTicketFields,` (line 1777):
```typescript
  contactFields: [],
  companyFields: [],
  customObjects: [],
```

**settings** — replace the `settings: { aiWorkQueueAutomationEnabled: true }` block (line 1785):
```typescript
  settings: {
    aiWorkQueueAutomationEnabled: true,
    publicBrandName: 'Omni Ticket',
    portalLogoUrl: '',
    portalPrimaryColor: '#2563eb',
    portalAccentColor: '#9333ea',
    portalSupportEmail: '',
    portalHeadline: 'How can we help you today?',
  },
```

### F5. `src/OmniApp.tsx`

**Imports:** Domain (lines 55-73): add `ContactField,`, `CompanyField,`, `CustomObject,`, `CustomObjectFieldDef,`.

**setupBuiltModules** (line 422) — add the 4 module names:
```typescript
  'Contact fields',
  'Company fields',
  'Custom objects',
  'Portal branding',
```

**Pull actions from store** — in the destructure near line 863-870:
```typescript
    createContactField,
    updateContactField,
    createCompanyField,
    updateCompanyField,
    createCustomObject,
    updateCustomObject,
    updateWorkspaceSettings,
```

**State** — near the `ticketFieldDraft` state (line 1035), add drafts:

```typescript
  const [contactFieldDraft, setContactFieldDraft] = useState({
    label: '',
    key: '',
    fieldType: 'text' as TicketFieldType,
    options: '',
    required: false,
    active: true,
    position: 100,
  })
  const [companyFieldDraft, setCompanyFieldDraft] = useState({
    label: '',
    key: '',
    fieldType: 'text' as TicketFieldType,
    options: '',
    required: false,
    active: true,
    position: 100,
  })
  const [contactFieldBusy, setContactFieldBusy] = useState(false)
  const [companyFieldBusy, setCompanyFieldBusy] = useState(false)
  const [customObjectDraft, setCustomObjectDraft] = useState({
    key: '',
    name: '',
    description: '',
  })
  const [customObjectFieldRows, setCustomObjectFieldRows] = useState<CustomObjectFieldDef[]>([])
  const [customObjectBusy, setCustomObjectBusy] = useState(false)
  const [brandingDraft, setBrandingDraft] = useState({
    portalLogoUrl: state.settings.portalLogoUrl,
    portalPrimaryColor: state.settings.portalPrimaryColor,
    portalAccentColor: state.settings.portalAccentColor,
    portalSupportEmail: state.settings.portalSupportEmail,
    portalHeadline: state.settings.portalHeadline,
  })
  const [brandingBusy, setBrandingBusy] = useState(false)
```

**Handlers** — place near `handleCreateTicketField` (line 2091). These reuse `normalizeTicketFieldKey` and `ticketFieldOptions` helpers already in the file:

```typescript
  async function handleCreateContactField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const label = contactFieldDraft.label.trim()
    const key = normalizeTicketFieldKey(contactFieldDraft.key || label)
    if (label.length < 1 || key.length < 2 || contactFieldBusy) return
    const options = ticketFieldOptions(contactFieldDraft.options)
    if (
      (contactFieldDraft.fieldType === 'select' || contactFieldDraft.fieldType === 'multiselect') &&
      options.length === 0
    ) {
      announcePrototype('Select fields need at least one option.')
      return
    }
    setContactFieldBusy(true)
    try {
      const saved = await createContactField({
        key,
        label,
        field_type: contactFieldDraft.fieldType,
        required: contactFieldDraft.required,
        active: contactFieldDraft.active,
        options,
        position: contactFieldDraft.position,
      })
      if (saved) {
        setContactFieldDraft({
          label: '',
          key: '',
          fieldType: 'text',
          options: '',
          required: false,
          active: true,
          position: 100,
        })
      }
    } finally {
      setContactFieldBusy(false)
    }
  }

  async function toggleContactField(field: ContactField) {
    if (contactFieldBusy) return
    setContactFieldBusy(true)
    try {
      await updateContactField(field.id, { active: !field.active })
    } finally {
      setContactFieldBusy(false)
    }
  }

  async function handleCreateCompanyField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const label = companyFieldDraft.label.trim()
    const key = normalizeTicketFieldKey(companyFieldDraft.key || label)
    if (label.length < 1 || key.length < 2 || companyFieldBusy) return
    const options = ticketFieldOptions(companyFieldDraft.options)
    if (
      (companyFieldDraft.fieldType === 'select' || companyFieldDraft.fieldType === 'multiselect') &&
      options.length === 0
    ) {
      announcePrototype('Select fields need at least one option.')
      return
    }
    setCompanyFieldBusy(true)
    try {
      const saved = await createCompanyField({
        key,
        label,
        field_type: companyFieldDraft.fieldType,
        required: companyFieldDraft.required,
        active: companyFieldDraft.active,
        options,
        position: companyFieldDraft.position,
      })
      if (saved) {
        setCompanyFieldDraft({
          label: '',
          key: '',
          fieldType: 'text',
          options: '',
          required: false,
          active: true,
          position: 100,
        })
      }
    } finally {
      setCompanyFieldBusy(false)
    }
  }

  async function toggleCompanyField(field: CompanyField) {
    if (companyFieldBusy) return
    setCompanyFieldBusy(true)
    try {
      await updateCompanyField(field.id, { active: !field.active })
    } finally {
      setCompanyFieldBusy(false)
    }
  }

  function addCustomObjectFieldRow() {
    setCustomObjectFieldRows((rows) => [
      ...rows,
      { key: '', label: '', fieldType: 'text', required: false, options: [] },
    ])
  }

  function updateCustomObjectFieldRow(index: number, patch: Partial<CustomObjectFieldDef>) {
    setCustomObjectFieldRows((rows) =>
      rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    )
  }

  function removeCustomObjectFieldRow(index: number) {
    setCustomObjectFieldRows((rows) => rows.filter((_, rowIndex) => rowIndex !== index))
  }

  async function handleCreateCustomObject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const key = normalizeTicketFieldKey(customObjectDraft.key || customObjectDraft.name)
    const name = customObjectDraft.name.trim()
    if (name.length < 2 || key.length < 2 || customObjectBusy) return
    const fields = customObjectFieldRows
      .map((row) => ({
        key: normalizeTicketFieldKey(row.key || row.label),
        label: row.label.trim(),
        field_type: row.fieldType,
        required: row.required,
        options: row.options,
      }))
      .filter((row) => row.key.length >= 2 && row.label.length >= 1)
    setCustomObjectBusy(true)
    try {
      const saved = await createCustomObject({
        key,
        name,
        description: customObjectDraft.description.trim(),
        fields,
      })
      if (saved) {
        setCustomObjectDraft({ key: '', name: '', description: '' })
        setCustomObjectFieldRows([])
      }
    } finally {
      setCustomObjectBusy(false)
    }
  }

  async function toggleCustomObject(custom: CustomObject) {
    if (customObjectBusy) return
    setCustomObjectBusy(true)
    try {
      await updateCustomObject(custom.id, { active: !custom.active })
    } finally {
      setCustomObjectBusy(false)
    }
  }

  async function handleSaveBranding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (brandingBusy) return
    setBrandingBusy(true)
    try {
      await updateWorkspaceSettings({
        portal_logo_url: brandingDraft.portalLogoUrl.trim(),
        portal_primary_color: brandingDraft.portalPrimaryColor.trim() || '#2563eb',
        portal_accent_color: brandingDraft.portalAccentColor.trim() || '#9333ea',
        portal_support_email: brandingDraft.portalSupportEmail.trim(),
        portal_headline: brandingDraft.portalHeadline.trim() || 'How can we help you today?',
      })
    } finally {
      setBrandingBusy(false)
    }
  }
```

**Setup panels** — add inside the `setupSection === 'forms'` block (it spans from line 6813). Place after the existing Ticket-fields panel content, before the closing of the `forms` conditional. Contact-fields panel:

```tsx
          <div className="automation-settings-panel contact-fields-panel">
            <div className="panel-head compact">
              <div>
                <span>Contact fields</span>
                <h2>Attributes captured on every contact</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="ticket-field-form" onSubmit={handleCreateContactField}>
              <label>
                <span>Label</span>
                <input
                  required
                  value={contactFieldDraft.label}
                  onChange={(event) =>
                    setContactFieldDraft((current) => ({
                      ...current,
                      label: event.target.value,
                      key: current.key || normalizeTicketFieldKey(event.target.value),
                    }))
                  }
                  placeholder="Loyalty tier"
                  disabled={!canManageUsers || contactFieldBusy}
                />
              </label>
              <label>
                <span>Key</span>
                <input
                  required
                  value={contactFieldDraft.key}
                  onChange={(event) =>
                    setContactFieldDraft((current) => ({
                      ...current,
                      key: normalizeTicketFieldKey(event.target.value),
                    }))
                  }
                  placeholder="loyalty_tier"
                  disabled={!canManageUsers || contactFieldBusy}
                />
              </label>
              <label>
                <span>Type</span>
                <select
                  value={contactFieldDraft.fieldType}
                  onChange={(event) =>
                    setContactFieldDraft((current) => ({
                      ...current,
                      fieldType: event.target.value as TicketFieldType,
                    }))
                  }
                  disabled={!canManageUsers || contactFieldBusy}
                >
                  {ticketFieldTypeOptions.map((type) => (
                    <option key={type} value={type}>{titleCase(type)}</option>
                  ))}
                </select>
              </label>
              {(contactFieldDraft.fieldType === 'select' ||
                contactFieldDraft.fieldType === 'multiselect') ? (
                <label className="span-all">
                  <span>Options (comma separated)</span>
                  <input
                    value={contactFieldDraft.options}
                    onChange={(event) =>
                      setContactFieldDraft((current) => ({ ...current, options: event.target.value }))
                    }
                    placeholder="Blue, Silver, Gold"
                    disabled={!canManageUsers || contactFieldBusy}
                  />
                </label>
              ) : null}
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || contactFieldBusy || contactFieldDraft.label.trim().length < 1}
              >
                <Plus size={16} />
                Add contact field
              </button>
            </form>
            <div className="canned-response-list">
              {state.contactFields.length === 0 ? (
                <p className="setup-module-hint">No contact fields yet.</p>
              ) : (
                state.contactFields.map((field) => (
                  <article className={`canned-response-card ${field.active ? '' : 'inactive'}`} key={field.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{field.label}</strong>
                        <code>{field.key}</code>
                      </div>
                      <span>{titleCase(field.fieldType)}</span>
                    </div>
                    {field.options.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {field.options.slice(0, 6).map((option) => (
                          <span key={option}>{option}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || contactFieldBusy}
                        onClick={() => void toggleContactField(field)}
                      >
                        {field.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
```

Add a **Company fields panel** identical to the above with `company`/`Company` substitutions (`handleCreateCompanyField`, `companyFieldDraft`/`setCompanyFieldDraft`, `companyFieldBusy`, `state.companyFields`, `toggleCompanyField`, copy "Account manager"/"account_manager" placeholders, heading "Company fields" / "Attributes captured on every company").

Add a **Custom objects panel**:

```tsx
          <div className="automation-settings-panel custom-objects-panel">
            <div className="panel-head compact">
              <div>
                <span>Custom objects</span>
                <h2>Named record schemas agents can attach</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateCustomObject}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={customObjectDraft.name}
                    onChange={(event) =>
                      setCustomObjectDraft((current) => ({
                        ...current,
                        name: event.target.value,
                        key: current.key || normalizeTicketFieldKey(event.target.value),
                      }))
                    }
                    placeholder="Loyalty account"
                    disabled={!canManageUsers || customObjectBusy}
                  />
                </label>
                <label>
                  <span>Key</span>
                  <input
                    required
                    value={customObjectDraft.key}
                    onChange={(event) =>
                      setCustomObjectDraft((current) => ({
                        ...current,
                        key: normalizeTicketFieldKey(event.target.value),
                      }))
                    }
                    placeholder="loyalty_account"
                    disabled={!canManageUsers || customObjectBusy}
                  />
                </label>
              </div>
              <label>
                <span>Description</span>
                <textarea
                  rows={2}
                  value={customObjectDraft.description}
                  onChange={(event) =>
                    setCustomObjectDraft((current) => ({ ...current, description: event.target.value }))
                  }
                  placeholder="What this object represents…"
                  disabled={!canManageUsers || customObjectBusy}
                />
              </label>
              <div className="custom-object-field-rows">
                {customObjectFieldRows.map((row, index) => (
                  <div className="custom-object-field-row" key={index}>
                    <input
                      value={row.label}
                      onChange={(event) =>
                        updateCustomObjectFieldRow(index, {
                          label: event.target.value,
                          key: row.key || normalizeTicketFieldKey(event.target.value),
                        })
                      }
                      placeholder="Field label"
                      disabled={!canManageUsers || customObjectBusy}
                    />
                    <select
                      value={row.fieldType}
                      onChange={(event) =>
                        updateCustomObjectFieldRow(index, {
                          fieldType: event.target.value as TicketFieldType,
                        })
                      }
                      disabled={!canManageUsers || customObjectBusy}
                    >
                      {ticketFieldTypeOptions.map((type) => (
                        <option key={type} value={type}>{titleCase(type)}</option>
                      ))}
                    </select>
                    {(row.fieldType === 'select' || row.fieldType === 'multiselect') ? (
                      <input
                        value={row.options.join(', ')}
                        onChange={(event) =>
                          updateCustomObjectFieldRow(index, {
                            options: ticketFieldOptions(event.target.value),
                          })
                        }
                        placeholder="Option A, Option B"
                        disabled={!canManageUsers || customObjectBusy}
                      />
                    ) : null}
                    <button
                      type="button"
                      className="secondary-action"
                      onClick={() => removeCustomObjectFieldRow(index)}
                      disabled={!canManageUsers || customObjectBusy}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="secondary-action"
                  onClick={addCustomObjectFieldRow}
                  disabled={!canManageUsers || customObjectBusy}
                >
                  <Plus size={14} />
                  Add field
                </button>
              </div>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || customObjectBusy || customObjectDraft.name.trim().length < 2}
              >
                <Plus size={16} />
                Add custom object
              </button>
            </form>
            <div className="canned-response-list">
              {state.customObjects.length === 0 ? (
                <p className="setup-module-hint">No custom objects yet.</p>
              ) : (
                state.customObjects.map((custom) => (
                  <article className={`canned-response-card ${custom.active ? '' : 'inactive'}`} key={custom.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{custom.name}</strong>
                        <code>{custom.key}</code>
                      </div>
                      <span>{custom.fields.length} fields</span>
                    </div>
                    {custom.description ? <p className="canned-card-body">{custom.description}</p> : null}
                    {custom.fields.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {custom.fields.slice(0, 6).map((field) => (
                          <span key={field.key}>{field.label}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || customObjectBusy}
                        onClick={() => void toggleCustomObject(custom)}
                      >
                        {custom.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
```

Add a **Portal branding panel**:

```tsx
          <div className="automation-settings-panel portal-branding-panel">
            <div className="panel-head compact">
              <div>
                <span>Portal branding</span>
                <h2>Logo, colors, and support details on the customer portal</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleSaveBranding}>
              <label>
                <span>Logo URL</span>
                <input
                  value={brandingDraft.portalLogoUrl}
                  onChange={(event) => setBrandingDraft((current) => ({ ...current, portalLogoUrl: event.target.value }))}
                  placeholder="https://cdn.example.com/logo.png"
                  disabled={!canManageUsers || brandingBusy}
                />
              </label>
              <div className="canned-form-row">
                <label>
                  <span>Primary color</span>
                  <input
                    type="color"
                    value={brandingDraft.portalPrimaryColor || '#2563eb'}
                    onChange={(event) =>
                      setBrandingDraft((current) => ({ ...current, portalPrimaryColor: event.target.value }))
                    }
                    disabled={!canManageUsers || brandingBusy}
                  />
                </label>
                <label>
                  <span>Accent color</span>
                  <input
                    type="color"
                    value={brandingDraft.portalAccentColor || '#9333ea'}
                    onChange={(event) =>
                      setBrandingDraft((current) => ({ ...current, portalAccentColor: event.target.value }))
                    }
                    disabled={!canManageUsers || brandingBusy}
                  />
                </label>
              </div>
              <label>
                <span>Support email</span>
                <input
                  type="email"
                  value={brandingDraft.portalSupportEmail}
                  onChange={(event) =>
                    setBrandingDraft((current) => ({ ...current, portalSupportEmail: event.target.value }))
                  }
                  placeholder="help@yourbrand.com"
                  disabled={!canManageUsers || brandingBusy}
                />
              </label>
              <label>
                <span>Headline</span>
                <input
                  value={brandingDraft.portalHeadline}
                  onChange={(event) =>
                    setBrandingDraft((current) => ({ ...current, portalHeadline: event.target.value }))
                  }
                  placeholder="How can we help you today?"
                  disabled={!canManageUsers || brandingBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || brandingBusy}
              >
                <Plus size={16} />
                Save branding
              </button>
            </form>
            <div
              className="portal-branding-preview"
              style={{
                borderColor: brandingDraft.portalPrimaryColor || '#2563eb',
              }}
            >
              <strong style={{ color: brandingDraft.portalPrimaryColor || '#2563eb' }}>
                {state.settings.publicBrandName}
              </strong>
              <p>{brandingDraft.portalHeadline || 'How can we help you today?'}</p>
              {brandingDraft.portalSupportEmail ? <small>{brandingDraft.portalSupportEmail}</small> : null}
            </div>
          </div>
```

> If `openSetupModule` should give branding/contact/company/objects a section route, no `peopleRoutes` entry is needed (they live in `forms`). The hint message already fires for any module name.

### F6. `src/App.css`

The new panels reuse existing classes. Add only additive styling for the custom-object rows and the branding preview. **Anchor:** append at end of the `.ticket-fields-panel { … }` cluster (near line 5089) or end of file:

```css
.custom-object-field-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.custom-object-field-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1.4fr auto;
  gap: 8px;
  align-items: center;
}

.custom-object-field-row input,
.custom-object-field-row select {
  width: 100%;
}

.portal-branding-preview {
  margin-top: 16px;
  padding: 16px;
  border: 2px solid #2563eb;
  border-radius: 12px;
  background: var(--surface, #fff);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.portal-branding-preview strong {
  font-size: 18px;
}

.portal-branding-preview small {
  color: var(--muted, #64748b);
}

@media (max-width: 760px) {
  .custom-object-field-row {
    grid-template-columns: 1fr;
  }
}
```

---

## APPLICATION ORDER SUMMARY (b112-data)

1. Domain models (A1, B1, C1, D1) → models.py records (A2, B2, C2, D2) → `models/__init__` (A4, B4, C4).
2. Migrations 0032→0035 (A3, B3, C3, D3).
3. Mappers (A5, B5, C5, D4, D5) → management.py (A6, B6, C6) → store.py seed (A7, B7, C7).
4. bootstrap.py (A8, B8, C8) → store_sync.py (A9, B9, C9).
5. resources.py routes + snapshot (A10, B10, C10); `/settings` route unchanged for branding.
6. Backend tests (E1, E2).
7. Frontend: domain.ts (F1) → backend.ts (F2) → store.ts (F3) → seed.ts (F4) → OmniApp.tsx (F5) → App.css (F6).

**Key file paths:** Backend: `/Users/gbolahan.salami/Documents/Ticket Desk/backend/app/models/domain.py`, `app/models/__init__.py`, `app/db/models.py`, `app/db/mappers.py`, `app/db/management.py`, `app/db/bootstrap.py`, `app/db/store_sync.py`, `app/db/settings.py`, `app/core/store.py`, `app/api/v1/resources.py`, 4 new migrations, tests `tests/test_operations.py`, `tests/test_database.py`. Frontend: `frontend/src/domain.ts`, `frontend/src/backend.ts`, `frontend/src/store.ts`, `frontend/src/seed.ts`, `frontend/src/OmniApp.tsx`, `frontend/src/App.css`.

---

The remaining four kits (b112-channels, b113, b114, stubs-creds) are reproduced verbatim below in subsequent sections. Due to length, I'll continue them in order.

---

### HEADING C — b112-channels: Phone (reuse) + Widgets + Feedback form
**Revision remap: kit says 0028 (channel_widgets) / 0029 (feedback_forms) → use 0036 (channel_widgets, `down_revision = "20260606_0035"`) / 0037 (feedback_forms, `down_revision = "20260606_0036"`). Phone is reuse-only (no migration). Ignore the kit's head bump.**

I now have complete understanding of all the pieces. The voice/Phone config is fully wired in `integrationCredentialDraft` (voiceHttp* fields) and the SMS+voice details section already renders in the connectors panel — Phone is pure frontend reveal work. I have everything needed to produce the kit.

Here is the complete implementation kit.

---

# B-112 Connector Channel Configs — Implementation Kit

## Architecture decision (read first)

I traced all three configs against the existing `connectors.py` / `integration_credentials.py` backend. The mapping is:

| Config | Backend strategy | Why |
|---|---|---|
| **(2) Phone (voice line)** | **100% reuse.** No new table, no new migration, no new domain model. | `IntegrationCredentialSettingsRecord` already stores `voice_http_endpoint / voice_http_from / voice_http_auth_token / voice_http_auth_header / voice_http_auth_scheme / voice_http_status_callback_url`, and `_sync_connector_accounts` already pushes the `voice` `ConnectorAccountRecord` live/pending. The frontend `integrationCredentialDraft` already carries every `voiceHttp*` field and the SMS+voice `<details>` already renders. Phone is purely a **frontend reveal**: add `'Phone'` to `setupBuiltModules`, route it in `openSetupModule`, and open the SMS/voice section. |
| **(1) Widgets (embeddable web widget)** | **New table** `channel_widgets` (revision **0028**→**0036**), full vertical slice mirroring `BusinessHours`. | A widget is per-market config that does not fit the single-row credential settings shape. It is a list of named widgets like business hours / templates. |
| **(3) Feedback form** | **New table** `feedback_forms` (revision **0029**→**0037**, applied after widgets), full vertical slice mirroring `TicketTemplate`. | A feedback form is per-market config. List-shaped like templates. |

Revisions: **Widgets = `20260606_0036`** (`down_revision = "20260606_0035"`), **Feedback forms = `20260606_0037`** (`down_revision = "20260606_0036"`).

`_repair_legacy_schema` in `bootstrap.py` does **not** need entries (same as business_hours/ticket_templates which are also absent there).

---

## PART A — Phone (reuse only, frontend)

### A1. `src/OmniApp.tsx` — add to `setupBuiltModules`

Find (line ~444):
```tsx
  'Canned responses',
  'Ticket templates',
])
```
Replace with:
```tsx
  'Canned responses',
  'Ticket templates',
  'Phone',
  'Widgets',
  'Feedback form',
])
```
(Widgets/Feedback form also belong to later parts — adding all three here once.)

### A2. `src/OmniApp.tsx` — route Phone in `openSetupModule`

Find in `openSetupModule` (line ~3170), the block after the `peopleRoutes` if:
```tsx
    if (peopleRoutes[moduleName]) {
      setPeopleView(peopleRoutes[moduleName])
    }
    setSetupModuleHint(`Showing ${moduleName} settings below.`)
```
Insert **before** `setSetupModuleHint`:
```tsx
    if (peopleRoutes[moduleName]) {
      setPeopleView(peopleRoutes[moduleName])
    }
    if (moduleName === 'Phone' && typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById('connector-voice-section')?.setAttribute('open', 'true')
      })
    }
    setSetupModuleHint(`Showing ${moduleName} settings below.`)
```

> **NOTE (reconcile):** E5 below supersedes this A2 edit with a combined version that also handles Widgets/Feedback form. Apply E5's combined block, not A2 alone.

### A3. `src/OmniApp.tsx` — give the SMS/voice `<details>` an id

Find (line ~8366):
```tsx
              <details className="credential-settings-section">
                <summary>
                  <span className="credential-section-title">
                    <Phone size={16} />
                    <span>
                      <strong>SMS and voice</strong>
```
Replace the opening tag:
```tsx
              <details className="credential-settings-section" id="connector-voice-section">
                <summary>
                  <span className="credential-section-title">
                    <Phone size={16} />
                    <span>
                      <strong>SMS and voice</strong>
```

Phone needs nothing else — backend, draft state, save handler, and connector-account sync already exist.

---

## PART B — Widgets (new table, revision 0028→0036)

### B1. Backend — `app/models/domain.py`

**Domain model + requests.** Insert immediately after the `TicketTemplate` class (after line 571, before `class Tag`):
```python
class ChannelWidget(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    allowed_domain: str = ""
    theme_color: str = "#2f6fed"
    greeting: str = "Hi there! How can we help?"
    launcher_position: str = "bottom-right"
    prefill_fields: list[str] = Field(default_factory=list)
    business_hours_id: str | None = None
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

Insert the requests after `UpdateTicketTemplateRequest` (after line 1354):
```python
class CreateChannelWidgetRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    allowed_domain: str = Field(default="", max_length=255)
    theme_color: str = Field(default="#2f6fed", max_length=16)
    greeting: str = Field(default="Hi there! How can we help?", max_length=300)
    launcher_position: str = Field(default="bottom-right", max_length=32)
    prefill_fields: list[str] = Field(default_factory=list)
    business_hours_id: str | None = Field(default=None, max_length=64)
    active: bool = True


class UpdateChannelWidgetRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    allowed_domain: str | None = Field(default=None, max_length=255)
    theme_color: str | None = Field(default=None, max_length=16)
    greeting: str | None = Field(default=None, max_length=300)
    launcher_position: str | None = Field(default=None, max_length=32)
    prefill_fields: list[str] | None = None
    business_hours_id: str | None = Field(default=None, max_length=64)
    active: bool | None = None
```

### B2. Backend — `app/models/__init__.py`

Add to the import block: `ChannelWidget,`. Add to `__all__`: `"ChannelWidget",`.

### B3. Backend — `app/db/models.py`

Insert after `TicketTemplateRecord` (after line 247, before `class ChannelRecord`):
```python
class ChannelWidgetRecord(TimestampMixin, Base):
    __tablename__ = "channel_widgets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    allowed_domain: Mapped[str] = mapped_column(String(255), default="")
    theme_color: Mapped[str] = mapped_column(String(16), default="#2f6fed")
    greeting: Mapped[str] = mapped_column(String(300), default="Hi there! How can we help?")
    launcher_position: Mapped[str] = mapped_column(String(32), default="bottom-right")
    prefill_fields: Mapped[list] = mapped_column(JSON, default=list)
    business_hours_id: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_channel_widget_market_name"),
    )
```

### B4. Backend — migration `migrations/versions/20260606_0028_channel_widgets.py` (full file) — **rename to `0036`, `revision = "20260606_0036"`, `down_revision = "20260606_0035"`**

```python
"""add market-scoped channel widgets

Revision ID: 20260606_0028
Revises: 20260606_0027
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0028"
down_revision: str | None = "20260606_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_widgets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("allowed_domain", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("theme_color", sa.String(length=16), nullable=False, server_default="#2f6fed"),
        sa.Column(
            "greeting",
            sa.String(length=300),
            nullable=False,
            server_default="Hi there! How can we help?",
        ),
        sa.Column(
            "launcher_position",
            sa.String(length=32),
            nullable=False,
            server_default="bottom-right",
        ),
        sa.Column("prefill_fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("business_hours_id", sa.String(length=64)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_channel_widget_market_name"),
    )
    op.create_index("ix_channel_widgets_market_id", "channel_widgets", ["market_id"])
    op.create_index("ix_channel_widgets_active", "channel_widgets", ["active"])


def downgrade() -> None:
    op.drop_index("ix_channel_widgets_active", table_name="channel_widgets")
    op.drop_index("ix_channel_widgets_market_id", table_name="channel_widgets")
    op.drop_table("channel_widgets")
```

### B5. Backend — `app/db/mappers.py`

Add `ChannelWidgetRecord` to record imports and `ChannelWidget` to domain imports, then insert after `ticket_template_from_record` (after line 243):
```python
def channel_widget_from_record(record: ChannelWidgetRecord) -> ChannelWidget:
    return ChannelWidget.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "allowed_domain": record.allowed_domain,
            "theme_color": record.theme_color,
            "greeting": record.greeting,
            "launcher_position": record.launcher_position,
            "prefill_fields": record.prefill_fields or [],
            "business_hours_id": record.business_hours_id,
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )
```

### B6. Backend — `app/db/management.py`

Add to mapper import: `channel_widget_from_record,`. Add to models import: `ChannelWidgetRecord,`. Add to domain import: `ChannelWidget,`, `CreateChannelWidgetRequest,`, `UpdateChannelWidgetRequest,`.

Insert the payload helper after `_business_hours_payload` (after line 424):
```python
def _channel_widget_payload(
    request: CreateChannelWidgetRequest | UpdateChannelWidgetRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Widget name is required",
            )
    if "allowed_domain" in payload and payload["allowed_domain"] is not None:
        payload["allowed_domain"] = payload["allowed_domain"].strip().lower()
    if "theme_color" in payload and payload["theme_color"] is not None:
        payload["theme_color"] = payload["theme_color"].strip() or "#2f6fed"
    if "greeting" in payload and payload["greeting"] is not None:
        payload["greeting"] = payload["greeting"].strip()
    if "prefill_fields" in payload and payload["prefill_fields"] is not None:
        seen: set[str] = set()
        fields: list[str] = []
        for field in payload["prefill_fields"]:
            cleaned = str(field).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                fields.append(cleaned)
        payload["prefill_fields"] = fields
    return payload
```

Insert the repo methods inside `class ManagementRepository`, after `update_ticket_template` (after line 1047, before `list_knowledge`):
```python
    def list_channel_widgets(
        self,
        db: Session,
        state: InMemoryStore,
        market_id: str,
    ) -> list[ChannelWidget]:
        records = db.scalars(
            select(ChannelWidgetRecord).where(ChannelWidgetRecord.market_id == market_id)
        ).all()
        widgets = [channel_widget_from_record(record) for record in records]
        widgets.sort(key=lambda widget: (not widget.active, widget.name.lower()))
        state.channel_widgets = {
            **{
                key: value
                for key, value in state.channel_widgets.items()
                if value.market_id != market_id
            },
            **{widget.id: widget for widget in widgets},
        }
        return widgets

    def create_channel_widget(
        self,
        db: Session,
        state: InMemoryStore,
        request: CreateChannelWidgetRequest,
        market_id: str,
        actor: str,
    ) -> ChannelWidget:
        payload = _channel_widget_payload(request)
        name = payload["name"]
        duplicate = db.scalar(
            select(ChannelWidgetRecord).where(
                ChannelWidgetRecord.market_id == market_id,
                ChannelWidgetRecord.name == name,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Widget already exists")
        record = ChannelWidgetRecord(id=_new_id("widget"), market_id=market_id, **payload)
        db.add(record)
        db.flush()
        _audit(
            db,
            state,
            actor=actor,
            action="channel_widget.create",
            entity_type="channel_widget",
            entity_id=record.id,
            market_id=market_id,
            details={"name": record.name, "active": record.active},
        )
        db.commit()
        db.refresh(record)
        widget = channel_widget_from_record(record)
        state.channel_widgets[widget.id] = widget
        return widget

    def update_channel_widget(
        self,
        db: Session,
        state: InMemoryStore,
        widget_id: str,
        request: UpdateChannelWidgetRequest,
        market_id: str,
        actor: str,
    ) -> ChannelWidget:
        record = db.get(ChannelWidgetRecord, widget_id)
        if record is None or record.market_id != market_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Widget not found")
        patch = _channel_widget_payload(request)
        if "name" in patch and patch["name"] != record.name:
            duplicate = db.scalar(
                select(ChannelWidgetRecord).where(
                    ChannelWidgetRecord.market_id == market_id,
                    ChannelWidgetRecord.name == patch["name"],
                    ChannelWidgetRecord.id != widget_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail="Widget already exists")
        for key, value in patch.items():
            setattr(record, key, value)
        _audit(
            db,
            state,
            actor=actor,
            action="channel_widget.update",
            entity_type="channel_widget",
            entity_id=widget_id,
            market_id=market_id,
            details=patch,
        )
        db.commit()
        db.refresh(record)
        widget = channel_widget_from_record(record)
        state.channel_widgets[widget.id] = widget
        return widget
```

### B7. Backend — `app/core/store.py`

Add `ChannelWidget,` to domain import. Add field after line 79:
```python
        self.ticket_templates: dict[str, TicketTemplate] = {}
        self.channel_widgets: dict[str, ChannelWidget] = {}
```
Add seed data inside `seed()` — insert after the `self.ticket_templates = {...}` block (after line 519):
```python
            self.channel_widgets = {
                "widget-ng-help": ChannelWidget(
                    id="widget-ng-help",
                    market_id="market-ng",
                    name="Nigeria help centre widget",
                    allowed_domain="help.example.ng",
                    theme_color="#1f7a4d",
                    greeting="Hi! Ask us about bookings, refunds, or changes.",
                    launcher_position="bottom-right",
                    prefill_fields=["name", "email", "booking_reference"],
                    business_hours_id="bh-ng-standard",
                ),
                "widget-uk-support": ChannelWidget(
                    id="widget-uk-support",
                    market_id="market-uk",
                    name="UK support widget",
                    allowed_domain="support.example.co.uk",
                    theme_color="#2f6fed",
                    greeting="Welcome — how can we help today?",
                    launcher_position="bottom-left",
                    prefill_fields=["name", "email"],
                    business_hours_id="bh-uk-standard",
                ),
            }
```

### B8. Backend — `app/db/bootstrap.py`

Add `ChannelWidgetRecord,` to models import. Insert the seed fn after `seed_ticket_templates` (after line 487):
```python
def seed_channel_widgets(session: Session, source: InMemoryStore = store) -> None:
    for widget in source.channel_widgets.values():
        existing = session.get(ChannelWidgetRecord, widget.id) or session.scalar(
            select(ChannelWidgetRecord).where(
                ChannelWidgetRecord.market_id == widget.market_id,
                ChannelWidgetRecord.name == widget.name,
            )
        )
        if existing is not None:
            continue
        session.add(ChannelWidgetRecord(**_payload(widget)))
    session.commit()
```
In `seed_reference_data`, add the call in the early-return branch after `seed_ticket_templates(session, source)`:
```python
        seed_ticket_templates(session, source)
        seed_channel_widgets(session, source)
```
In the fresh-seed (`add_all`) branch, add after the `TicketTemplateRecord` block:
```python
    session.add_all(
        [
            ChannelWidgetRecord(**_payload(widget))
            for widget in source.channel_widgets.values()
        ]
    )
```

### B9. Backend — `app/db/store_sync.py`

Add `channel_widget_from_record,` to mappers import and `ChannelWidgetRecord,` to models import. Add hydration after the `state.ticket_templates = {...}` block (after line 208):
```python
    state.channel_widgets = {
        widget.id: channel_widget_from_record(widget)
        for widget in db.scalars(select(ChannelWidgetRecord)).all()
    }
```

### B10. Backend — `app/api/v1/resources.py`

Add to domain imports: `ChannelWidget`, `CreateChannelWidgetRequest`, `UpdateChannelWidgetRequest`. Insert routes after the `update_ticket_template` route (after line 1262, before `list_customers`):
```python
@router.get("/channel-widgets", response_model=list[ChannelWidget])
def list_channel_widgets(
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> list[ChannelWidget]:
    return management_repository.list_channel_widgets(db, state, context.market_id)


@router.post("/channel-widgets", response_model=ChannelWidget, status_code=status.HTTP_201_CREATED)
def create_channel_widget(
    request: CreateChannelWidgetRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ChannelWidget:
    require_admin(context)
    return management_repository.create_channel_widget(
        db,
        state,
        request,
        context.market_id,
        context.user.email,
    )


@router.patch("/channel-widgets/{widget_id}", response_model=ChannelWidget)
def update_channel_widget(
    widget_id: str,
    request: UpdateChannelWidgetRequest,
    context: RequestContext = Depends(require_context),
    state: InMemoryStore = Depends(get_store),
    db: Session = Depends(get_db),
) -> ChannelWidget:
    require_admin(context)
    return management_repository.update_channel_widget(
        db,
        state,
        widget_id,
        request,
        context.market_id,
        context.user.email,
    )
```
Add the snapshot key (after line 3058):
```python
        "ticket_templates": management_repository.list_ticket_templates(db, state, context.market_id),
        "channel_widgets": management_repository.list_channel_widgets(db, state, context.market_id),
```

---

## PART C — Feedback form (new table, revision 0029→0037)

Mirror of TicketTemplate. Apply Part B first (0036 must precede 0037).

### C1. `app/models/domain.py`

After the `ChannelWidget` class (Part B1):
```python
class FeedbackForm(BaseModel):
    id: str
    market_id: str = "market-ng"
    name: str
    title: str
    intro: str = ""
    channel: ChannelType = ChannelType.portal
    fields: list[str] = Field(default_factory=list)
    success_message: str = "Thank you for your feedback!"
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```
After `UpdateChannelWidgetRequest` (Part B1):
```python
class CreateFeedbackFormRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    title: str = Field(min_length=1, max_length=300)
    intro: str = Field(default="", max_length=2000)
    channel: ChannelType = ChannelType.portal
    fields: list[str] = Field(default_factory=list)
    success_message: str = Field(default="Thank you for your feedback!", max_length=500)
    active: bool = True


class UpdateFeedbackFormRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    intro: str | None = Field(default=None, max_length=2000)
    channel: ChannelType | None = None
    fields: list[str] | None = None
    success_message: str | None = Field(default=None, max_length=500)
    active: bool | None = None
```

### C2. `app/models/__init__.py`
Add `FeedbackForm,` to import block. Add `"FeedbackForm",` to `__all__`.

### C3. `app/db/models.py`
After `ChannelWidgetRecord` (Part B3):
```python
class FeedbackFormRecord(TimestampMixin, Base):
    __tablename__ = "feedback_forms"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    intro: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(String(32), default="portal")
    fields: Mapped[list] = mapped_column(JSON, default=list)
    success_message: Mapped[str] = mapped_column(String(500), default="Thank you for your feedback!")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("market_id", "name", name="uq_feedback_form_market_name"),
    )
```

### C4. Migration `migrations/versions/20260606_0029_feedback_forms.py` (full file) — **rename to `0037`, `revision = "20260606_0037"`, `down_revision = "20260606_0036"`**
```python
"""add market-scoped feedback forms

Revision ID: 20260606_0029
Revises: 20260606_0028
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0029"
down_revision: str | None = "20260606_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_forms",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False, server_default=""),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="portal"),
        sa.Column("fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "success_message",
            sa.String(length=500),
            nullable=False,
            server_default="Thank you for your feedback!",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_id", "name", name="uq_feedback_form_market_name"),
    )
    op.create_index("ix_feedback_forms_market_id", "feedback_forms", ["market_id"])
    op.create_index("ix_feedback_forms_active", "feedback_forms", ["active"])


def downgrade() -> None:
    op.drop_index("ix_feedback_forms_active", table_name="feedback_forms")
    op.drop_index("ix_feedback_forms_market_id", table_name="feedback_forms")
    op.drop_table("feedback_forms")
```

### C5. `app/db/mappers.py`
Add `FeedbackFormRecord` (records) and `FeedbackForm` (domain) imports. After `channel_widget_from_record`:
```python
def feedback_form_from_record(record: FeedbackFormRecord) -> FeedbackForm:
    return FeedbackForm.model_validate(
        {
            "id": record.id,
            "market_id": record.market_id,
            "name": record.name,
            "title": record.title,
            "intro": record.intro,
            "channel": record.channel,
            "fields": record.fields or [],
            "success_message": record.success_message,
            "active": record.active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )
```

### C6. `app/db/management.py`
Add imports: `feedback_form_from_record,` (mappers), `FeedbackFormRecord,` (models), and `FeedbackForm, CreateFeedbackFormRequest, UpdateFeedbackFormRequest` (domain).
Payload helper after `_channel_widget_payload`:
```python
def _feedback_form_payload(
    request: CreateFeedbackFormRequest | UpdateFeedbackFormRequest,
) -> dict:
    payload = request.model_dump(exclude_unset=True, mode="json")
    if "name" in payload and payload["name"] is not None:
        payload["name"] = _clean_group_name(payload["name"])
        if not payload["name"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Feedback form name is required",
            )
    if "title" in payload and payload["title"] is not None:
        payload["title"] = payload["title"].strip()
        if not payload["title"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Feedback form title is required",
            )
    if "intro" in payload and payload["intro"] is not None:
        payload["intro"] = payload["intro"].strip()
    if "success_message" in payload and payload["success_message"] is not None:
        payload["success_message"] = (
            payload["success_message"].strip() or "Thank you for your feedback!"
        )
    if "fields" in payload and payload["fields"] is not None:
        seen: set[str] = set()
        fields: list[str] = []
        for field in payload["fields"]:
            cleaned = str(field).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                fields.append(cleaned)
        payload["fields"] = fields
    return payload
```
Repo methods after `update_channel_widget` (mirror exactly, swapping symbols): `list_feedback_forms`, `create_feedback_form`, `update_feedback_form` — same body shape as the widget methods, with `FeedbackFormRecord`, `feedback_form_from_record`, `_feedback_form_payload`, id prefix `_new_id("feedback")`, `state.feedback_forms`, audit actions `feedback_form.create` / `feedback_form.update`, entity_type `feedback_form`, conflict detail `"Feedback form already exists"`, 404 detail `"Feedback form not found"`, and create-audit details `{"name": record.name, "channel": record.channel, "active": record.active}`.

### C7. `app/core/store.py`
Import `FeedbackForm,`. Field: `self.feedback_forms: dict[str, FeedbackForm] = {}` after `channel_widgets`. Seed after the `channel_widgets` block:
```python
            self.feedback_forms = {
                "feedback-ng-csat": FeedbackForm(
                    id="feedback-ng-csat",
                    market_id="market-ng",
                    name="Post-resolution CSAT",
                    title="How did we do?",
                    intro="Tell us about your recent support experience.",
                    channel=ChannelType.portal,
                    fields=["rating", "comment"],
                    success_message="Thanks — your feedback helps us improve.",
                ),
                "feedback-ng-product": FeedbackForm(
                    id="feedback-ng-product",
                    market_id="market-ng",
                    name="Product feedback",
                    title="Share a product idea",
                    intro="Suggest improvements to the booking experience.",
                    channel=ChannelType.email,
                    fields=["category", "comment", "email"],
                    success_message="We have logged your idea for the product team.",
                ),
            }
```

### C8. `app/db/bootstrap.py`
Import `FeedbackFormRecord,`. Add `seed_feedback_forms` (mirror of `seed_channel_widgets`, swapping symbols, iterating `source.feedback_forms.values()`). Call it after `seed_channel_widgets(session, source)` in the early-return branch (before `return`), and add the `FeedbackFormRecord` `add_all` block after the `ChannelWidgetRecord` block in the fresh-seed branch.

### C9. `app/db/store_sync.py`
Import `feedback_form_from_record,` and `FeedbackFormRecord,`. Hydration after `channel_widgets`:
```python
    state.feedback_forms = {
        form.id: feedback_form_from_record(form)
        for form in db.scalars(select(FeedbackFormRecord)).all()
    }
```

### C10. `app/api/v1/resources.py`
Domain imports: add `FeedbackForm`, `CreateFeedbackFormRequest`, `UpdateFeedbackFormRequest`. Routes after the channel-widget routes — `GET/POST /feedback-forms` and `PATCH /feedback-forms/{form_id}`, mirror of channel-widget routes (path param `form_id`, calls `management_repository.list_feedback_forms / create_feedback_form / update_feedback_form`). Snapshot key after `channel_widgets`:
```python
        "channel_widgets": management_repository.list_channel_widgets(db, state, context.market_id),
        "feedback_forms": management_repository.list_feedback_forms(db, state, context.market_id),
```

---

## PART D — Backend tests

### D1. `tests/test_database.py`
Update head and add table asserts:
```python
ALEMBIC_HEAD = "20260606_0029"
```
**[SUPERSEDED — use `0045`]**
After `assert "ticket_templates" in tables` (line 37):
```python
    assert "ticket_templates" in tables
    assert "channel_widgets" in tables
    assert "feedback_forms" in tables
```
After line 152 (`assert "ticket_templates" in inspector.get_table_names()`):
```python
    assert "ticket_templates" in inspector.get_table_names()
    assert "channel_widgets" in inspector.get_table_names()
    assert "feedback_forms" in inspector.get_table_names()
```

### D2. `tests/test_operations.py` — add after `test_admin_manages_ticket_templates` (after line 1522)
```python
def test_admin_manages_channel_widgets(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/channel-widgets",
        json={
            "name": f"Help widget {suffix}",
            "allowed_domain": "Help.Example.NG",
            "theme_color": "#1f7a4d",
            "greeting": "Hi there!",
            "launcher_position": "bottom-right",
            "prefill_fields": ["email", "email", "name"],
            "business_hours_id": "bh-ng-standard",
        },
    )
    assert created.status_code == 201
    widget = created.json()
    assert widget["allowed_domain"] == "help.example.ng"  # normalized lower-case
    assert widget["prefill_fields"] == ["email", "name"]  # de-duplicated

    listing = client.get("/api/v1/channel-widgets")
    assert listing.status_code == 200
    assert any(item["id"] == widget["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/channel-widgets/{widget['id']}",
        json={"active": False, "theme_color": "#000000"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["theme_color"] == "#000000"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == widget["id"] for item in snapshot.json()["channel_widgets"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "channel_widget.create" for event in audit)
    assert any(event["action"] == "channel_widget.update" for event in audit)


def test_admin_manages_feedback_forms(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/v1/feedback-forms",
        json={
            "name": f"CSAT form {suffix}",
            "title": "How did we do?",
            "intro": "Tell us about your experience.",
            "channel": "portal",
            "fields": ["rating", "rating", "comment"],
            "success_message": "Thanks!",
        },
    )
    assert created.status_code == 201
    form = created.json()
    assert form["channel"] == "portal"
    assert form["fields"] == ["rating", "comment"]  # de-duplicated

    listing = client.get("/api/v1/feedback-forms")
    assert listing.status_code == 200
    assert any(item["id"] == form["id"] for item in listing.json())

    updated = client.patch(
        f"/api/v1/feedback-forms/{form['id']}",
        json={"active": False, "title": "Updated title"},
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["title"] == "Updated title"

    snapshot = client.get("/api/v1/frontend/snapshot")
    assert snapshot.status_code == 200
    assert any(item["id"] == form["id"] for item in snapshot.json()["feedback_forms"])

    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "feedback_form.create" for event in audit)
    assert any(event["action"] == "feedback_form.update" for event in audit)
```
(`uuid4` and `TestClient` are already imported in this test module.)

---

## PART E — Frontend (Widgets + Feedback form full slice)

### E1. `src/domain.ts`
After the `TicketTemplate` interface (after line 283):
```typescript
export interface ChannelWidget {
  id: string
  name: string
  allowedDomain: string
  themeColor: string
  greeting: string
  launcherPosition: string
  prefillFields: string[]
  businessHoursId: string | null
  active: boolean
  updatedAt: string
}

export interface FeedbackForm {
  id: string
  name: string
  title: string
  intro: string
  channelId: ChannelId
  fields: string[]
  successMessage: string
  active: boolean
  updatedAt: string
}
```
In `OmniState` after `ticketTemplates: TicketTemplate[]` (line 381):
```typescript
  ticketTemplates: TicketTemplate[]
  channelWidgets: ChannelWidget[]
  feedbackForms: FeedbackForm[]
```

### E2. `src/backend.ts`
After `BackendUpdateTicketTemplateInput` (after line 966):
```typescript
export interface BackendChannelWidget {
  id: string
  market_id: string
  name: string
  allowed_domain: string
  theme_color: string
  greeting: string
  launcher_position: string
  prefill_fields: string[]
  business_hours_id: string | null
  active: boolean
  created_at: string
  updated_at: string
}

export interface BackendCreateChannelWidgetInput {
  name: string
  allowed_domain?: string
  theme_color?: string
  greeting?: string
  launcher_position?: string
  prefill_fields?: string[]
  business_hours_id?: string | null
  active?: boolean
}

export interface BackendUpdateChannelWidgetInput {
  name?: string
  allowed_domain?: string
  theme_color?: string
  greeting?: string
  launcher_position?: string
  prefill_fields?: string[]
  business_hours_id?: string | null
  active?: boolean
}

export interface BackendFeedbackForm {
  id: string
  market_id: string
  name: string
  title: string
  intro: string
  channel: string
  fields: string[]
  success_message: string
  active: boolean
  created_at: string
  updated_at: string
}

export interface BackendCreateFeedbackFormInput {
  name: string
  title: string
  intro?: string
  channel?: string
  fields?: string[]
  success_message?: string
  active?: boolean
}

export interface BackendUpdateFeedbackFormInput {
  name?: string
  title?: string
  intro?: string
  channel?: string
  fields?: string[]
  success_message?: string
  active?: boolean
}
```

**Snapshot fields.** In `BackendSnapshot` (around line 522) — add camelCase after `ticketTemplates: BackendTicketTemplate[]` (line 523):
```typescript
  ticketTemplates: BackendTicketTemplate[]
  channelWidgets: BackendChannelWidget[]
  feedbackForms: BackendFeedbackForm[]
```
and snake_case after `ticket_templates: BackendTicketTemplate[]` (line 545):
```typescript
  ticket_templates: BackendTicketTemplate[]
  channel_widgets: BackendChannelWidget[]
  feedback_forms: BackendFeedbackForm[]
```
In `BackendFrontendSnapshot` (line ~1351), after `ticket_templates: BackendTicketTemplate[]`:
```typescript
  ticket_templates: BackendTicketTemplate[]
  channel_widgets: BackendChannelWidget[]
  feedback_forms: BackendFeedbackForm[]
```
**Normalization** in `fetchBackendSnapshot` after `ticketTemplates: frontendSnapshot.ticket_templates ?? [],` (line 1513):
```typescript
    ticketTemplates: frontendSnapshot.ticket_templates ?? [],
    channelWidgets: frontendSnapshot.channel_widgets ?? [],
    feedbackForms: frontendSnapshot.feedback_forms ?? [],
```
**Client fns** after `patchBackendTicketTemplate` (after line 1829):
```typescript
export async function createBackendChannelWidget(
  input: BackendCreateChannelWidgetInput,
  session: BackendSession,
): Promise<BackendChannelWidget> {
  return fetchJson<BackendChannelWidget>(
    '/channel-widgets',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendChannelWidget(
  widgetId: string,
  patch: BackendUpdateChannelWidgetInput,
  session: BackendSession,
): Promise<BackendChannelWidget> {
  return fetchJson<BackendChannelWidget>(
    `/channel-widgets/${widgetId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}

export async function createBackendFeedbackForm(
  input: BackendCreateFeedbackFormInput,
  session: BackendSession,
): Promise<BackendFeedbackForm> {
  return fetchJson<BackendFeedbackForm>(
    '/feedback-forms',
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
    session,
  )
}

export async function patchBackendFeedbackForm(
  formId: string,
  patch: BackendUpdateFeedbackFormInput,
  session: BackendSession,
): Promise<BackendFeedbackForm> {
  return fetchJson<BackendFeedbackForm>(
    `/feedback-forms/${formId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(patch),
    },
    session,
  )
}
```

### E3. `src/store.ts`
**Domain imports** (after `TicketTemplate,` line 25): add `ChannelWidget,`, `FeedbackForm,`.
**Backend value imports** (near line 40-41): add `createBackendChannelWidget,`, `createBackendFeedbackForm,`. Near line 73-74: add `patchBackendChannelWidget,`, `patchBackendFeedbackForm,`.
**Backend type imports** (near line 89-90): add `type BackendChannelWidget,`, `type BackendFeedbackForm,`. Near line 93-94: add `type BackendCreateChannelWidgetInput,`, `type BackendUpdateChannelWidgetInput,`, `type BackendCreateFeedbackFormInput,`, `type BackendUpdateFeedbackFormInput,`.
**Rehydration merge** in `mergeReferenceData` after `ticketTemplates:` (line 254):
```typescript
    ticketTemplates: state.ticketTemplates ?? initialOmniState.ticketTemplates,
    channelWidgets: state.channelWidgets ?? initialOmniState.channelWidgets,
    feedbackForms: state.feedbackForms ?? initialOmniState.feedbackForms,
```
**Mappers** after `mapTicketTemplate` (after line 492):
```typescript
function mapChannelWidget(widget: BackendChannelWidget): ChannelWidget {
  return {
    id: widget.id,
    name: widget.name,
    allowedDomain: widget.allowed_domain,
    themeColor: widget.theme_color,
    greeting: widget.greeting,
    launcherPosition: widget.launcher_position,
    prefillFields: widget.prefill_fields ?? [],
    businessHoursId: widget.business_hours_id,
    active: widget.active,
    updatedAt: widget.updated_at,
  }
}

function mapFeedbackForm(form: BackendFeedbackForm): FeedbackForm {
  return {
    id: form.id,
    name: form.name,
    title: form.title,
    intro: form.intro,
    channelId: normalizeChannelId(form.channel),
    fields: form.fields ?? [],
    successMessage: form.success_message,
    active: form.active,
    updatedAt: form.updated_at,
  }
}
```
**Hydration** after the `ticketTemplates` build (line 786-787):
```typescript
  const channelWidgets = (snapshot.channel_widgets ?? snapshot.channelWidgets ?? []).map(
    mapChannelWidget,
  )
  const feedbackForms = (snapshot.feedback_forms ?? snapshot.feedbackForms ?? []).map(
    mapFeedbackForm,
  )
```
In the returned hydrated state object after `ticketTemplates,` (line 823):
```typescript
    ticketTemplates,
    channelWidgets,
    feedbackForms,
```
**Actions** after `updateTicketTemplate` (after line 1970):
```typescript
  function createChannelWidget(input: BackendCreateChannelWidgetInput) {
    return syncBackendMutation((session) => createBackendChannelWidget(input, session))
  }

  function updateChannelWidget(widgetId: string, patch: BackendUpdateChannelWidgetInput) {
    return syncBackendMutation((session) => patchBackendChannelWidget(widgetId, patch, session))
  }

  function createFeedbackForm(input: BackendCreateFeedbackFormInput) {
    return syncBackendMutation((session) => createBackendFeedbackForm(input, session))
  }

  function updateFeedbackForm(formId: string, patch: BackendUpdateFeedbackFormInput) {
    return syncBackendMutation((session) => patchBackendFeedbackForm(formId, patch, session))
  }
```
**Export** in the returned object after `updateTicketTemplate,` (line 2232):
```typescript
    createTicketTemplate,
    updateTicketTemplate,
    createChannelWidget,
    updateChannelWidget,
    createFeedbackForm,
    updateFeedbackForm,
```

### E4. `src/seed.ts`
After `ticketTemplates: [],` (line 1782):
```typescript
  ticketTemplates: [],
  channelWidgets: [],
  feedbackForms: [],
```

### E5. `src/OmniApp.tsx`

**Type imports** (after `TicketTemplate,` line 73): add `ChannelWidget,`, `FeedbackForm,`.

**Store destructuring** after `updateTicketTemplate,` (line 868):
```tsx
    createTicketTemplate,
    updateTicketTemplate,
    createChannelWidget,
    updateChannelWidget,
    createFeedbackForm,
    updateFeedbackForm,
```

**Local draft state** — add near the other Setup drafts (after the template draft / `setupSection` state around line 985):
```tsx
  const [widgetDraft, setWidgetDraft] = useState({
    name: '',
    allowedDomain: '',
    themeColor: '#2f6fed',
    greeting: 'Hi there! How can we help?',
    launcherPosition: 'bottom-right',
    prefillFields: '',
    businessHoursId: '',
  })
  const [widgetBusy, setWidgetBusy] = useState(false)
  const [feedbackDraft, setFeedbackDraft] = useState({
    name: '',
    title: '',
    intro: '',
    channel: 'portal' as ChannelId,
    fields: '',
    successMessage: 'Thank you for your feedback!',
  })
  const [feedbackBusy, setFeedbackBusy] = useState(false)
```

**Handlers** — add near `handleCreateTicketTemplate` / `toggleTicketTemplate` (after line ~3150):
```tsx
  async function handleCreateChannelWidget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = widgetDraft.name.trim()
    if (name.length < 2 || widgetBusy) return
    setWidgetBusy(true)
    try {
      const saved = await createChannelWidget({
        name,
        allowed_domain: widgetDraft.allowedDomain.trim(),
        theme_color: widgetDraft.themeColor.trim() || '#2f6fed',
        greeting: widgetDraft.greeting.trim(),
        launcher_position: widgetDraft.launcherPosition,
        prefill_fields: widgetDraft.prefillFields
          .split(',')
          .map((field) => field.trim())
          .filter(Boolean),
        business_hours_id: widgetDraft.businessHoursId || null,
      })
      if (saved) {
        setWidgetDraft((current) => ({ ...current, name: '', allowedDomain: '', prefillFields: '' }))
      }
    } finally {
      setWidgetBusy(false)
    }
  }

  async function toggleChannelWidget(widget: ChannelWidget) {
    if (widgetBusy) return
    setWidgetBusy(true)
    try {
      await updateChannelWidget(widget.id, { active: !widget.active })
    } finally {
      setWidgetBusy(false)
    }
  }

  async function handleCreateFeedbackForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = feedbackDraft.name.trim()
    const title = feedbackDraft.title.trim()
    if (name.length < 2 || title.length < 1 || feedbackBusy) return
    setFeedbackBusy(true)
    try {
      const saved = await createFeedbackForm({
        name,
        title,
        intro: feedbackDraft.intro.trim(),
        channel: feedbackDraft.channel,
        fields: feedbackDraft.fields
          .split(',')
          .map((field) => field.trim())
          .filter(Boolean),
        success_message: feedbackDraft.successMessage.trim() || 'Thank you for your feedback!',
      })
      if (saved) {
        setFeedbackDraft((current) => ({ ...current, name: '', title: '', intro: '', fields: '' }))
      }
    } finally {
      setFeedbackBusy(false)
    }
  }

  async function toggleFeedbackForm(form: FeedbackForm) {
    if (feedbackBusy) return
    setFeedbackBusy(true)
    try {
      await updateFeedbackForm(form.id, { active: !form.active })
    } finally {
      setFeedbackBusy(false)
    }
  }
```

**Setup panels** — insert inside the `setupSection === 'connectors'` block, immediately before its closing `</>` at line 9643:
```tsx
          <div className="automation-settings-panel widget-config-panel" id="connector-widgets-panel">
            <div className="panel-head compact">
              <div>
                <span>Web widget</span>
                <h2>Embeddable chat widgets</h2>
              </div>
              <MessageCircle size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateChannelWidget}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={widgetDraft.name}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Help centre widget"
                    disabled={!canManageUsers || widgetBusy}
                  />
                </label>
                <label>
                  <span>Allowed domain</span>
                  <input
                    value={widgetDraft.allowedDomain}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, allowedDomain: event.target.value }))}
                    placeholder="help.example.com"
                    disabled={!canManageUsers || widgetBusy}
                  />
                </label>
              </div>
              <div className="canned-form-row">
                <label>
                  <span>Theme color</span>
                  <input
                    type="color"
                    value={widgetDraft.themeColor}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, themeColor: event.target.value }))}
                    disabled={!canManageUsers || widgetBusy}
                  />
                </label>
                <label>
                  <span>Launcher position</span>
                  <select
                    value={widgetDraft.launcherPosition}
                    onChange={(event) => setWidgetDraft((current) => ({ ...current, launcherPosition: event.target.value }))}
                    disabled={!canManageUsers || widgetBusy}
                  >
                    <option value="bottom-right">Bottom right</option>
                    <option value="bottom-left">Bottom left</option>
                  </select>
                </label>
              </div>
              <label>
                <span>Business hours</span>
                <select
                  value={widgetDraft.businessHoursId}
                  onChange={(event) => setWidgetDraft((current) => ({ ...current, businessHoursId: event.target.value }))}
                  disabled={!canManageUsers || widgetBusy}
                >
                  <option value="">Always on</option>
                  {state.businessHours.map((calendar) => (
                    <option key={calendar.id} value={calendar.id}>{calendar.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Greeting</span>
                <input
                  value={widgetDraft.greeting}
                  onChange={(event) => setWidgetDraft((current) => ({ ...current, greeting: event.target.value }))}
                  placeholder="Hi there! How can we help?"
                  disabled={!canManageUsers || widgetBusy}
                />
              </label>
              <label>
                <span>Prefill fields (comma separated)</span>
                <input
                  value={widgetDraft.prefillFields}
                  onChange={(event) => setWidgetDraft((current) => ({ ...current, prefillFields: event.target.value }))}
                  placeholder="name, email, booking_reference"
                  disabled={!canManageUsers || widgetBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || widgetBusy || widgetDraft.name.trim().length < 2}
              >
                <Plus size={16} />
                Add widget
              </button>
            </form>
            <div className="canned-response-list">
              {state.channelWidgets.length === 0 ? (
                <p className="setup-module-hint">No web widgets yet. Add one to embed live chat.</p>
              ) : (
                state.channelWidgets.map((widget) => (
                  <article className={`canned-response-card ${widget.active ? '' : 'inactive'}`} key={widget.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{widget.name}</strong>
                        <span className="widget-theme-chip" style={{ backgroundColor: widget.themeColor }} />
                      </div>
                      <span>{widget.allowedDomain || 'Any domain'}</span>
                    </div>
                    <p className="canned-card-body">{widget.greeting}</p>
                    {widget.prefillFields.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {widget.prefillFields.slice(0, 6).map((field) => (
                          <span key={field}>{field}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || widgetBusy}
                        onClick={() => void toggleChannelWidget(widget)}
                      >
                        {widget.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
          <div className="automation-settings-panel feedback-form-panel" id="connector-feedback-panel">
            <div className="panel-head compact">
              <div>
                <span>Feedback</span>
                <h2>Customer feedback forms</h2>
              </div>
              <ClipboardList size={18} />
            </div>
            <form className="user-create-form canned-response-form" onSubmit={handleCreateFeedbackForm}>
              <div className="canned-form-row">
                <label>
                  <span>Name</span>
                  <input
                    required
                    value={feedbackDraft.name}
                    onChange={(event) => setFeedbackDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Post-resolution CSAT"
                    disabled={!canManageUsers || feedbackBusy}
                  />
                </label>
                <label>
                  <span>Channel</span>
                  <select
                    value={feedbackDraft.channel}
                    onChange={(event) => setFeedbackDraft((current) => ({ ...current, channel: event.target.value as ChannelId }))}
                    disabled={!canManageUsers || feedbackBusy}
                  >
                    <option value="portal">Portal</option>
                    <option value="email">Email</option>
                  </select>
                </label>
              </div>
              <label>
                <span>Title</span>
                <input
                  required
                  value={feedbackDraft.title}
                  onChange={(event) => setFeedbackDraft((current) => ({ ...current, title: event.target.value }))}
                  placeholder="How did we do?"
                  disabled={!canManageUsers || feedbackBusy}
                />
              </label>
              <label>
                <span>Fields (comma separated)</span>
                <input
                  value={feedbackDraft.fields}
                  onChange={(event) => setFeedbackDraft((current) => ({ ...current, fields: event.target.value }))}
                  placeholder="rating, comment"
                  disabled={!canManageUsers || feedbackBusy}
                />
              </label>
              <label>
                <span>Intro</span>
                <textarea
                  rows={2}
                  value={feedbackDraft.intro}
                  onChange={(event) => setFeedbackDraft((current) => ({ ...current, intro: event.target.value }))}
                  placeholder="Tell us about your recent experience…"
                  disabled={!canManageUsers || feedbackBusy}
                />
              </label>
              <label>
                <span>Success message</span>
                <input
                  value={feedbackDraft.successMessage}
                  onChange={(event) => setFeedbackDraft((current) => ({ ...current, successMessage: event.target.value }))}
                  placeholder="Thank you for your feedback!"
                  disabled={!canManageUsers || feedbackBusy}
                />
              </label>
              <button
                type="submit"
                className="primary-action"
                disabled={!canManageUsers || feedbackBusy || feedbackDraft.name.trim().length < 2 || feedbackDraft.title.trim().length < 1}
              >
                <Plus size={16} />
                Add feedback form
              </button>
            </form>
            <div className="canned-response-list">
              {state.feedbackForms.length === 0 ? (
                <p className="setup-module-hint">No feedback forms yet. Add one to collect CSAT.</p>
              ) : (
                state.feedbackForms.map((form) => (
                  <article className={`canned-response-card ${form.active ? '' : 'inactive'}`} key={form.id}>
                    <div className="canned-card-head">
                      <div>
                        <strong>{form.name}</strong>
                        <span className="template-priority">{titleCase(form.channelId)}</span>
                      </div>
                      <span>{form.fields.length} field(s)</span>
                    </div>
                    <p className="canned-card-body">
                      <b>{form.title}</b>
                      {form.intro ? ` — ${form.intro}` : ''}
                    </p>
                    {form.fields.length > 0 ? (
                      <div className="tag-list compact-tags">
                        {form.fields.slice(0, 6).map((field) => (
                          <span key={field}>{field}</span>
                        ))}
                      </div>
                    ) : null}
                    <div className="canned-card-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!canManageUsers || feedbackBusy}
                        onClick={() => void toggleFeedbackForm(form)}
                      >
                        {form.active ? 'Pause' : 'Activate'}
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
```
Anchor: this lands between the existing outbound-message panel `</div>` (line 9642) and the connectors `</>` (line 9643). `MessageCircle`, `ClipboardList`, `Plus`, `titleCase`, `canManageUsers`, `ChannelId` are already imported/in-scope.

**`openSetupModule` routing** for Widgets/Feedback form. Replace the Phone insert from A2 with the combined version:
```tsx
    if (peopleRoutes[moduleName]) {
      setPeopleView(peopleRoutes[moduleName])
    }
    if (moduleName === 'Phone' && typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById('connector-voice-section')?.setAttribute('open', 'true')
      })
    }
    if (moduleName === 'Widgets' && typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById('connector-widgets-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
    if (moduleName === 'Feedback form' && typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.getElementById('connector-feedback-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
    setSetupModuleHint(`Showing ${moduleName} settings below.`)
```

**setupBuiltModules** entries — already added in A1 (`'Phone'`, `'Widgets'`, `'Feedback form'`). These three are members of `setupModuleCatalog.connectors[0].modules` (line 411), so they become clickable cards.

### E6. `src/App.css`
Append:
```css
.widget-config-panel .canned-form-row,
.feedback-form-panel .canned-form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.widget-theme-chip {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid var(--border, #d8dee9);
  vertical-align: middle;
  margin-left: 8px;
}

.widget-config-panel input[type='color'] {
  width: 100%;
  height: 40px;
  padding: 2px;
  cursor: pointer;
}

@media (max-width: 720px) {
  .widget-config-panel .canned-form-row,
  .feedback-form-panel .canned-form-row {
    grid-template-columns: 1fr;
  }
}
```

---

## Apply order (b112-channels)
1. Backend Part B (Widgets, rev 0036) → Part C (Feedback forms, rev 0037) → run migrations `alembic upgrade head`.
2. Part D tests.
3. Part A (Phone reveal) + Part E (frontend) — A1 adds all three to `setupBuiltModules`; E5 supersedes A2's `openSetupModule` edit with the combined version.

## Reuse summary
- **Phone**: zero backend changes — `voice_http_*` on `IntegrationCredentialSettingsRecord`, `_sync_connector_accounts` voice sync, and the `integrationCredentialDraft.voiceHttp*` fields + SMS/voice `<details>` already exist. Only `setupBuiltModules` + `openSetupModule` + a `<details id>` change.
- **Widgets / Feedback form**: new tables; `business_hours_id` on widgets is stored as plain `String(64)`, matching how `SlaPolicy.business_hours` references hours by name without a hard FK.

**Files touched (b112-channels):** Backend: `app/models/domain.py`, `app/models/__init__.py`, `app/db/models.py`, 2 new migrations, `app/db/mappers.py`, `app/db/management.py`, `app/core/store.py`, `app/db/bootstrap.py`, `app/db/store_sync.py`, `app/api/v1/resources.py`, `tests/test_database.py`, `tests/test_operations.py`. Frontend: `src/domain.ts`, `src/backend.ts`, `src/store.ts`, `src/seed.ts`, `src/OmniApp.tsx`, `src/App.css`.

---

The b113 and stubs-creds kits remain. I'll continue with b113 next, then b114, then stubs-creds.
