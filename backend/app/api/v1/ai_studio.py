from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.rbac import require_admin, require_operator
from app.api.v1.security import RequestContext, require_context
from app.db.session import get_db
from app.models.ai_studio import (
    AiAgentResponse,
    AiDecisionResponse,
    AiReadinessResponse,
    CreateAiAgentRequest,
    UpdateAiAgentRequest,
    UpdateAiPolicyRequest,
)
from app.services.ai_studio import ai_studio_service

router = APIRouter(prefix="/ai", tags=["ai-studio"])


@router.get("/readiness", response_model=AiReadinessResponse)
def read_ai_readiness(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AiReadinessResponse:
    require_operator(context)
    return ai_studio_service.readiness(db, market=context.market)


@router.patch("/policy", response_model=AiReadinessResponse)
def update_ai_policy(
    request: UpdateAiPolicyRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AiReadinessResponse:
    require_admin(context)
    return ai_studio_service.update_policy(
        db,
        market=context.market,
        actor=context.user.email,
        request=request,
    )


@router.get("/agents", response_model=list[AiAgentResponse])
def list_ai_agents(
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[AiAgentResponse]:
    require_operator(context)
    return ai_studio_service.list_agents(db, market_id=context.market_id)


@router.post("/agents", response_model=AiAgentResponse, status_code=201)
def create_ai_agent(
    request: CreateAiAgentRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AiAgentResponse:
    require_admin(context)
    return ai_studio_service.create_agent(
        db,
        market_id=context.market_id,
        actor=context.user.email,
        request=request,
    )


@router.patch("/agents/{agent_id}", response_model=AiAgentResponse)
def update_ai_agent(
    agent_id: str,
    request: UpdateAiAgentRequest,
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> AiAgentResponse:
    require_admin(context)
    return ai_studio_service.update_agent(
        db,
        market=context.market,
        actor=context.user.email,
        agent_id=agent_id,
        request=request,
    )


@router.get("/decisions", response_model=list[AiDecisionResponse])
def list_ai_decisions(
    limit: int = Query(50, ge=1, le=500),
    context: RequestContext = Depends(require_context),
    db: Session = Depends(get_db),
) -> list[AiDecisionResponse]:
    require_operator(context)
    return ai_studio_service.list_decisions(
        db,
        market_id=context.market_id,
        limit=limit,
    )
