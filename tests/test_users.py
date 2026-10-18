from jinja2.bccache import Bucket
from h11 import Data
import pytest

from httpx import AsyncClient
from tests.conftest import login_user, auth_header, create_user

from io import BytesIO
from unittest.mock import AsyncMock, patch
from pathlib import Path


#Testing validation error with missing required fields for creating user
@pytest.mark.anyio
async def test_create_user_missing_fields(client: AsyncClient):
    """
    Test that creating a user with missing required fields returns 422 Unprocessable Entity
    """
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser",
            "password": "testpassword",
        }
    )
    assert response.status_code == 422
    data = response.json()
    assert "email" in data["detail"][0]["loc"]
    assert "required" in data["detail"][0]["msg"]


#Test user creation with duplicate email
@pytest.mark.anyio
async def test_create_user_duplicate_email(client: AsyncClient, setup_database):
    """
    Test that creating a user with duplicate email returns 400 Bad Request
    """
    # Create first user
    await create_user(client=client)

    # Try to create user with same email
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser2",
            "email": "test@example.com",
            "password": "testpassword2",
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert "User with this email already exists" in data["detail"]

#Successfull user creation
@pytest.mark.anyio
async def test_create_user_successfull(client: AsyncClient):
    """
    Test that creating a user with valid data returns 201 Created
    """
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser33",
            "email": "test33@example.com",
            "password": "testpassword33",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser33"
    assert data["email"] == "test33@example.com"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


#Test upload image
@pytest.mark.anyio
async def test_upload_image(client: AsyncClient, mocked_aws):
    user = await create_user(client)
    token = await login_user(client)
    
    #use test_image
    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user["id"]}/profile_pic",
        files=[
            ("file", ("test_image.jpg", BytesIO(image_bytes), "image/jpeg")),
        ],
        headers=auth_header(token['access_token'])
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    assert data["image_file"].endswith(".jpg")
    assert "s3" in data["image_path"]

    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert "Contents" in s3_objects
    assert len(s3_objects["Contents"]) == 1
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])


#Test forget password email
@pytest.mark.anyio
async def test_forget_password_email(client: AsyncClient):
    """
    Test that the forget password email is requested successfully
    """
    await create_user(client)

    with patch("routers.users.send_password_reset_email") as mock_send_email:
        response = await client.post(
            "/api/users/forgot-password",
            json={
                "email": "test@example.com",
            }
        )
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "If an email exists with this email, you will receive an password reset email with instructions"
        mock_send_email.assert_called_once()
    