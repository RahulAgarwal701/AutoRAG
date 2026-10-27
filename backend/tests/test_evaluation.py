import uuid
from typing import cast

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.main import app
from app.models.agent import Agent
from app.models.evaluation import EvaluationCase
from app.schemas.evaluation import (
    EvaluationConfiguration,
    EvaluationResult,
    EvaluationRunRequest,
)
from app.services.evaluation import (
    EvaluationSample,
    EvaluationService,
    render_markdown_report,
    retrieval_scores,
)
from app.services.retrieval import RetrievalService, RetrievedChunk


def test_retrieval_scores_compute_hit_rate_and_reciprocal_rank() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()

    hit_rate, mrr, count = retrieval_scores(
        [{first}, {second}, set()],
        [[uuid.uuid4(), first], [uuid.uuid4()], [second]],
    )

    assert count == 2
    assert hit_rate == pytest.approx(0.5)
    assert mrr == pytest.approx(0.25)


def test_default_evaluation_request_compares_four_configurations() -> None:
    request = EvaluationRunRequest()

    assert [item.name for item in request.configurations] == [
        "hybrid",
        "dense",
        "hybrid + reranker",
        "dense + reranker",
    ]


@pytest.mark.asyncio
async def test_configuration_run_combines_ragas_and_retrieval_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    expected_document = uuid.uuid4()

    class FakeRetrieval:
        async def retrieve_standalone(self, **_: object) -> list[RetrievedChunk]:
            return [
                RetrievedChunk(
                    text="Refunds are available for 30 days.",
                    score=0.9,
                    document_id=expected_document,
                    document_name="policy.pdf",
                    chunk_index=0,
                    source_url="https://storage.test/policy.pdf",
                )
            ]

    class FakeRagas:
        async def score(self, samples: list[EvaluationSample]) -> dict[str, float]:
            assert samples[0].contexts == ["Refunds are available for 30 days."]
            return {
                "faithfulness": 0.9,
                "answer_relevancy": 0.8,
                "context_precision": 0.7,
                "context_recall": 0.6,
            }

    async def fake_answer(*_: object) -> str:
        return "Refunds are available for 30 days."

    monkeypatch.setattr(EvaluationService, "_answer", staticmethod(fake_answer))
    service = EvaluationService(
        cast(AsyncSession, object()),
        cast(RetrievalService, FakeRetrieval()),
        FakeRagas(),
    )
    agent = Agent(
        id=agent_id,
        user_id=user_id,
        name="Policy",
        system_prompt="Stay grounded",
        model="grok-4.7",
        llm_provider="grok",
        top_k=5,
        use_reranker=False,
    )
    case = EvaluationCase(
        user_id=user_id,
        agent_id=agent_id,
        question="What is the refund period?",
        reference_answer="Refunds are available for 30 days.",
        reference_document_ids=[str(expected_document)],
        source="manual",
    )

    result = await service._run_configuration(
        tenant_id=user_id,
        agent=agent,
        cases=[case],
        configuration=EvaluationConfiguration(name="hybrid"),
    )

    assert result.faithfulness == pytest.approx(0.9)
    assert result.answer_relevancy == pytest.approx(0.8)
    assert result.hit_rate_at_k == pytest.approx(1.0)
    assert result.mrr == pytest.approx(1.0)
    assert result.retrieval_labeled_count == 1


def test_markdown_report_contains_real_metric_values() -> None:
    agent_id = uuid.uuid4()
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    agent = Agent(
        id=agent_id,
        user_id=user_id,
        name="Invoices",
        system_prompt="Stay grounded",
        model="grok-4.7",
        llm_provider="grok",
    )
    case = EvaluationCase(
        user_id=user_id,
        agent_id=agent_id,
        question="What is the total?",
        reference_answer="The total is INR 42,750.",
        reference_document_ids=[str(document_id)],
        source="manual",
    )
    result = EvaluationResult(
        configuration=EvaluationConfiguration(name="hybrid"),
        sample_count=1,
        retrieval_labeled_count=1,
        faithfulness=0.91,
        answer_relevancy=0.82,
        context_precision=0.73,
        context_recall=0.64,
        hit_rate_at_k=1.0,
        mrr=0.5,
    )

    report = render_markdown_report(agent, "Evaluation", [case], [result])

    assert (
        "| hybrid | hybrid | no | 5 | 0.910 | 0.820 | 0.730 | 0.640 | 1.000 | 0.500 |"
    ) in report
    assert "Golden questions: **1**" in report


def test_metrics_endpoint_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class TestSettings:
        metrics_token = SecretStr("metrics-secret")

    monkeypatch.setattr("app.api.routes.metrics.get_settings", lambda: TestSettings())
    with TestClient(app) as client:
        unauthorized = client.get("/metrics")
        response = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert "autorag_http_requests_total" in response.text
    assert "autorag_http_request_duration_seconds" in response.text
