import argparse
import asyncio
import json
import uuid

from app.db.session import async_session_factory
from app.services.retrieval import create_retrieval_service
from app.services.tenancy import get_owned_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test hybrid retrieval for an agent")
    parser.add_argument("--tenant-id", required=True, type=uuid.UUID)
    parser.add_argument("--agent-id", required=True, type=uuid.UUID)
    parser.add_argument("--query", required=True)
    return parser.parse_args()


async def run(tenant_id: uuid.UUID, agent_id: uuid.UUID, query: str) -> None:
    async with async_session_factory() as session:
        agent = await get_owned_agent(session, tenant_id, agent_id)
        if agent is None:
            raise SystemExit("Agent not found for this tenant")
        results = await create_retrieval_service(session).retrieve(
            tenant_id=tenant_id,
            agent=agent,
            question=query,
        )
        print(
            json.dumps(
                [result.model_dump(mode="json") for result in results],
                indent=2,
            )
        )


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.tenant_id, args.agent_id, args.query))


if __name__ == "__main__":
    main()
