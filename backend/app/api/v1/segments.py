from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_operator, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.db.session import get_db
from app.models.segments import CreateSegmentRequest, SegmentResponse, UpdateSegmentRequest
from app.services.segments import segment_service

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("", response_model=list[SegmentResponse])
def list_segments(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[SegmentResponse]:
    require_operator(context)
    return segment_service.list_segments(db, market_id=context.market_id)


@router.post("", response_model=SegmentResponse, status_code=201)
def create_segment(
    request: CreateSegmentRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> SegmentResponse:
    require_supervisor(context)
    return segment_service.create(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        request=request,
    )


@router.patch("/{segment_id}", response_model=SegmentResponse)
def update_segment(
    segment_id: str,
    request: UpdateSegmentRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> SegmentResponse:
    require_supervisor(context)
    return segment_service.update(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        segment_id=segment_id,
        request=request,
    )
