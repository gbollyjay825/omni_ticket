from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_operator, require_supervisor
from app.api.v1.security import RequestContext, require_context
from app.db.session import get_db
from app.models.campaigns import (
    CampaignConsentResponse,
    CampaignDeliveryResponse,
    CampaignLaunchResponse,
    CampaignProviderReadiness,
    CampaignResponse,
    CreateCampaignRequest,
    SetCampaignConsentRequest,
    UpdateCampaignRequest,
)
from app.services.campaigns import campaign_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[CampaignResponse]:
    require_operator(context)
    return campaign_service.list_campaigns(db, market_id=context.market_id)


@router.get("/readiness", response_model=list[CampaignProviderReadiness])
def campaign_readiness(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[CampaignProviderReadiness]:
    require_operator(context)
    return campaign_service.readiness(db, market_id=context.market_id)


@router.get("/consents", response_model=list[CampaignConsentResponse])
def list_campaign_consents(
    customer_id: str | None = Query(None),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[CampaignConsentResponse]:
    require_operator(context)
    return campaign_service.list_consents(
        db,
        market_id=context.market_id,
        customer_id=customer_id,
    )


@router.put("/consents", response_model=CampaignConsentResponse)
def set_campaign_consent(
    request: SetCampaignConsentRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> CampaignConsentResponse:
    require_supervisor(context)
    return campaign_service.set_consent(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        request=request,
    )


@router.post("", response_model=CampaignResponse, status_code=201)
def create_campaign(
    request: CreateCampaignRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    require_supervisor(context)
    return campaign_service.create(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        request=request,
    )


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    request: UpdateCampaignRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    require_supervisor(context)
    return campaign_service.update(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        campaign_id=campaign_id,
        request=request,
    )


@router.post("/{campaign_id}/launch", response_model=CampaignLaunchResponse)
def launch_campaign(
    campaign_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> CampaignLaunchResponse:
    require_supervisor(context)
    return campaign_service.launch(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        campaign_id=campaign_id,
    )


@router.get("/{campaign_id}/deliveries", response_model=list[CampaignDeliveryResponse])
def list_campaign_deliveries(
    campaign_id: str,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[CampaignDeliveryResponse]:
    require_operator(context)
    return campaign_service.list_deliveries(
        db,
        market_id=context.market_id,
        campaign_id=campaign_id,
    )
