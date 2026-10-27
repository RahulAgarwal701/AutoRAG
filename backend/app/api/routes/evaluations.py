import uuid

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.agent import Agent
from app.models.document import Document
from app.models.evaluation import EvaluationCase, EvaluationRun
from app.schemas.evaluation import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationRunRead,
    EvaluationRunRequest,
    SyntheticCaseRequest,
)
from app.services.evaluation import EvaluationService
from app.services.retrieval import create_retrieval_service
from app.services.tenancy import get_owned_agent

router = APIRouter(prefix="/agents/{agent_id}", tags=["evaluations"])


async def _owned_agent_or_404(
    session: DatabaseSession, user_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    agent = await get_owned_agent(session, user_id, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.post(
    "/evaluation-cases",
    response_model=EvaluationCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    agent_id: uuid.UUID,
    payload: EvaluationCaseCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> EvaluationCase:
    await _owned_agent_or_404(session, current_user.id, agent_id)
    if payload.reference_document_ids:
        owned_ids = set(
            await session.scalars(
                select(Document.id).where(
                    Document.user_id == current_user.id,
                    Document.agent_id == agent_id,
                    Document.id.in_(payload.reference_document_ids),
                )
            )
        )
        if owned_ids != set(payload.reference_document_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Every reference document must belong to this agent",
            )
    case = EvaluationCase(
        user_id=current_user.id,
        agent_id=agent_id,
        question=payload.question,
        reference_answer=payload.reference_answer,
        reference_document_ids=[str(item) for item in payload.reference_document_ids],
        source="manual",
    )
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


@router.get("/evaluation-cases", response_model=list[EvaluationCaseRead])
async def list_evaluation_cases(
    agent_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> list[EvaluationCase]:
    await _owned_agent_or_404(session, current_user.id, agent_id)
    cases = await session.scalars(
        select(EvaluationCase)
        .where(
            EvaluationCase.user_id == current_user.id,
            EvaluationCase.agent_id == agent_id,
        )
        .order_by(EvaluationCase.created_at.desc())
    )
    return list(cases)


@router.delete("/evaluation-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_case(
    agent_id: uuid.UUID,
    case_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    case = await session.scalar(
        select(EvaluationCase).where(
            EvaluationCase.id == case_id,
            EvaluationCase.user_id == current_user.id,
            EvaluationCase.agent_id == agent_id,
        )
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation case not found"
        )
    await session.delete(case)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/evaluation-cases/synthetic",
    response_model=list[EvaluationCaseRead],
    status_code=status.HTTP_201_CREATED,
)
async def generate_synthetic_cases(
    agent_id: uuid.UUID,
    payload: SyntheticCaseRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> list[EvaluationCase]:
    agent = await _owned_agent_or_404(session, current_user.id, agent_id)
    try:
        service = EvaluationService(session, create_retrieval_service(session))
        return await service.generate_synthetic_cases(
            tenant_id=current_user.id, agent=agent, count=payload.count
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/evaluations", response_model=EvaluationRunRead)
async def run_evaluation(
    agent_id: uuid.UUID,
    payload: EvaluationRunRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> EvaluationRun:
    agent = await _owned_agent_or_404(session, current_user.id, agent_id)
    try:
        service = EvaluationService(session, create_retrieval_service(session))
        return await service.run(
            tenant_id=current_user.id,
            agent=agent,
            name=payload.name,
            configurations=payload.configurations,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/evaluations", response_model=list[EvaluationRunRead])
async def list_evaluations(
    agent_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> list[EvaluationRun]:
    await _owned_agent_or_404(session, current_user.id, agent_id)
    runs = await session.scalars(
        select(EvaluationRun)
        .where(
            EvaluationRun.user_id == current_user.id,
            EvaluationRun.agent_id == agent_id,
        )
        .order_by(EvaluationRun.created_at.desc())
    )
    return list(runs)


@router.get("/evaluations/{run_id}", response_model=EvaluationRunRead)
async def read_evaluation(
    agent_id: uuid.UUID,
    run_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> EvaluationRun:
    run = await session.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.user_id == current_user.id,
            EvaluationRun.agent_id == agent_id,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found"
        )
    return run


@router.get("/evaluations/{run_id}/report", response_class=PlainTextResponse)
async def read_evaluation_report(
    agent_id: uuid.UUID,
    run_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> PlainTextResponse:
    run = await read_evaluation(agent_id, run_id, session, current_user)
    return PlainTextResponse(run.markdown_report, media_type="text/markdown")
