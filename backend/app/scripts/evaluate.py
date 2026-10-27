import argparse
import asyncio
import uuid
from pathlib import Path

from app.db.session import async_session_factory
from app.schemas.evaluation import EvaluationRunRequest
from app.services.evaluation import EvaluationService
from app.services.retrieval import create_retrieval_service
from app.services.tenancy import get_owned_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate and compare AutoRAG retrieval")
    parser.add_argument("--tenant-id", required=True, type=uuid.UUID)
    parser.add_argument("--agent-id", required=True, type=uuid.UUID)
    parser.add_argument("--name", default="RAG configuration comparison")
    parser.add_argument("--output", type=Path, default=Path("evaluation-report.md"))
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        agent = await get_owned_agent(session, args.tenant_id, args.agent_id)
        if agent is None:
            raise SystemExit("Agent not found for this tenant")
        request = EvaluationRunRequest(name=args.name)
        evaluation = await EvaluationService(session, create_retrieval_service(session)).run(
            tenant_id=args.tenant_id,
            agent=agent,
            name=request.name,
            configurations=request.configurations,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(evaluation.markdown_report, encoding="utf-8")
        print(f"Evaluation {evaluation.status}: {args.output.resolve()}")


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
