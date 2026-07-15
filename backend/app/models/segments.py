from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.models.domain import Sentiment


class SegmentRules(BaseModel):
    include_all: bool = False
    tags_any: list[str] = Field(default_factory=list, max_length=50)
    tags_all: list[str] = Field(default_factory=list, max_length=50)
    preferred_channels_any: list[str] = Field(default_factory=list, max_length=20)
    sentiments: list[Sentiment] = Field(default_factory=list, max_length=4)
    company_ids: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def normalize_and_require_filter(self) -> "SegmentRules":
        self.tags_any = sorted({value.strip().lower() for value in self.tags_any if value.strip()})
        self.tags_all = sorted({value.strip().lower() for value in self.tags_all if value.strip()})
        self.preferred_channels_any = sorted(
            {value.strip().lower() for value in self.preferred_channels_any if value.strip()}
        )
        self.company_ids = sorted({value.strip() for value in self.company_ids if value.strip()})
        if not self.include_all and not any(
            (
                self.tags_any,
                self.tags_all,
                self.preferred_channels_any,
                self.sentiments,
                self.company_ids,
            )
        ):
            raise ValueError("Add at least one segment rule or explicitly include all contacts")
        return self


class CreateSegmentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=500)
    rules: SegmentRules


class UpdateSegmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    rules: SegmentRules | None = None
    active: bool | None = None


class SegmentResponse(BaseModel):
    id: str
    market_id: str
    name: str
    description: str
    rules: SegmentRules
    active: bool
    member_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime
