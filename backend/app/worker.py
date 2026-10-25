import asyncio

from app.workflows.worker import run_worker

if __name__ == "__main__":
    asyncio.run(run_worker())

