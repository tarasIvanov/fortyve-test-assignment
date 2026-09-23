import asyncio
import os
import subprocess
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import get_session
from app.main import app

TEST_DATABASE_NAME = "fields_test"


def build_test_database_url() -> str:
    base_url, _, _ = settings.database_url.rpartition("/")
    return f"{base_url}/{TEST_DATABASE_NAME}"


async def create_test_database() -> None:
    """CREATE DATABASE не можна виконати в транзакції, тому потрібен AUTOCOMMIT."""
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)

    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE_NAME}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))

    await engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Окрема база під тести зі схемою, накоченою тією самою міграцією, що й у проді."""
    url = build_test_database_url()
    asyncio.run(create_test_database())

    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "DATABASE_URL": url},
    )
    return url


@pytest_asyncio.fixture
async def session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """Сесія всередині транзакції, яка відкочується після тесту.

    join_transaction_mode="create_savepoint" робить так, що commit усередині
    репозиторію закриває лише savepoint, а зовнішня транзакція все одно
    відкочується — база лишається чистою без TRUNCATE між тестами.
    """
    engine = create_async_engine(test_database_url, poolclass=NullPool)

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with session_factory() as session:
            yield session

        await transaction.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
