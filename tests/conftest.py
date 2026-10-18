from sqlalchemy import NullPool
from requests import session
import os

from collections.abc import AsyncGenerator


os.environ["DATABASE_URL"] = "postgresql+psycopg://bloguser:blogpass@localhost:5432/test_blog"

os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["S3_REGION"] = "us-east-1"
os.environ["S3_ACCESS_KEY_ID"] = "testing"
os.environ["S3_SECRET_ACCESS_KEY"] = "testing"

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-at-least-32-bytes"

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


import boto3
import pytest
from httpx import ASGITransport, AsyncClient

from moto import mock_aws
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from database import get_db, Base, engine
from main import app

pytest_plugins = ["anyio"]

# pytest fixture for asynchronous event loop backend
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# pytest fixture for database connection sesssion
@pytest.fixture(scope="session")
def test_engine():
    return create_async_engine(
        os.environ["DATABASE_URL"],
        echo=True, # Log SQL queries
        poolclass=NullPool
    )

#Databse serup fixture
@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()

# Databse transaction rollback fixture for individual tests
@pytest.fixture(scope="function")
async def db_session(setup_database, test_engine) -> AsyncGenerator[AsyncSession]:
    async with test_engine.begin() as conn:
        #Manually create connection
        conn = await test_engine.connect()

        #create transaction
        trans = await conn.begin()

        test_async_session = async_sessionmaker(
            bind=conn, 
            class_=AsyncSession, 
            expire_on_commit=False,
            join_transaction_mode="create_savepoint"
        )

        async with test_async_session() as session:
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
                await conn.close()


#Test fixture for AWS mock
@pytest.fixture
def mocked_aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])
        yield s3


#Test client fixture for FastAPI application
@pytest.fixture
async def client(
    db_session: AsyncSession,
    mocked_aws,
) -> AsyncGenerator[AsyncClient]:
    """
    Override the dependency so that the test_client will use the test database session instead of the actual database
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db  #dependency_overrides is a dictionary that allows us to override the dependencies in FastAPI

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    
    app.dependency_overrides.clear() #Clears all the overrides


# Authentication helpers

## create user helper
async def create_user(
    client: AsyncClient,
    username:str ='test_user',
    email:str = 'test@example.com',
    password:str = 'testpassword123',
) -> dict:
    response = await client.post(
        "/api/users",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()

## Login user
async def login_user(
    client: AsyncClient,
    email: str = 'test@example.com',
    password: str = 'testpassword123',
) -> dict:
    """
    Login a user and return the access token.
    """
    response = await client.post(
        "api/users/token",
        data={
            "username": email,
            "password": password,
        }
    )
    assert response.status_code == 200, f"Failed to login user: {response.text}"
    return response.json()

#Auth header
def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
    
   
    