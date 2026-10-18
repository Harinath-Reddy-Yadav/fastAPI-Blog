from fastapi import FastAPI
from fastapi.testclient import TestClient

demo_app = FastAPI()

client = TestClient(demo_app)

@demo_app.get('/')
def demo_root():
    return {"message": "Hello World"}



client = TestClient(demo_app)
def test_demo():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

