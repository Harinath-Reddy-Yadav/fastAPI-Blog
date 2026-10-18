import pytest
from httpx import AsyncClient


from tests.conftest import login_user, auth_header, create_user


#Get posts tests when its empty
@pytest.mark.anyio
async def test_empty_posts(client: AsyncClient):
    response = await client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["total"] == 0
    assert data["has_more"] == False


#Post doesn't exist test
@pytest.mark.anyio
async def test_post_not_found(client: AsyncClient):
    response = await client.get("/api/posts/999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Post not found"


#creating a post when user authenticated
@pytest.mark.anyio
async def test_create_post(client: AsyncClient,db_session):
    user = await create_user(client)
    token = await login_user(client)
    header = auth_header(token['access_token'])


    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "This is a test post."},
        headers=header
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Post"
    assert data["content"] == "This is a test post."
    assert data["user_id"] == user["id"]
    assert data["author"]["username"] == "test_user"

#Creating post without authentication
@pytest.mark.anyio
async def test_create_post_unauthenticated(client: AsyncClient):
    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "This is a test post."}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated"

#To create a post with authorization
@pytest.mark.anyio
async def test_create_post_authorized(client: AsyncClient):
    await create_user(client)
    token = await login_user(client)
    header = auth_header(token['access_token'])

    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "This is a test post."},
        headers=header
    )

    post_id = response.json()["id"]
    
    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Updated Post", "content": "This is an updated post."},
        headers=header
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Post"
    assert data["content"] == "This is an updated post."
    assert data["author"]["username"] == "test_user"

# Test creating a post unautorized
@pytest.mark.anyio
async def test_create_post_unautorized(client: AsyncClient):
    await create_user(client)
    token = await login_user(client)
    header = auth_header(token['access_token'])

    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "This is a test post."},
        headers=header
    )

    post_id = response.json()["id"]

    await create_user(client,username='test_user2',email='test2@example.com',password='testpassword123')

    token2 = await login_user(client,email='test2@example.com',password='testpassword123')
    header2 = auth_header(token2['access_token'])

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Updated Post", "content": "This is an updated post."},
        headers=header2
    )

    assert response.status_code == 403
    data = response.json()
    assert data["detail"] == "You are not authorized to update this post"

# Test pagination
@pytest.mark.anyio
async def test_get_posts_with_pagination(client: AsyncClient):
    await create_user(client)
    token_data = await login_user(client)
    headers = auth_header(token_data['access_token'])

    #Create 50 posts
    for i in range(5):
        response = await client.post(
            "api/posts",
            json={"title": f"Test Post {i}", "content": f"This is a test post {i}."},
            headers=headers
        )
        assert response.status_code == 200

    response = await client.get("api/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 5
    assert data["has_more"] == False

    response = await client.get("api/posts?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["has_more"] == True

    response = await client.get("api/posts?limit=2&skip=4")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 1
    assert data["has_more"] == False