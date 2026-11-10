import pytest

async def test_oauth_form_login_and_logout(api):
    response = await api.client.post("/v1/auth/token", data={"username": "OWNER@example.com", "password": "Validpass1!"})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await api.client.get("/v1/orders", headers=headers)).status_code == 200
    assert (await api.client.post("/v1/auth/logout", headers=headers)).status_code == 204
    assert (await api.client.get("/v1/orders", headers=headers)).status_code == 401
    assert (await api.client.post("/v1/auth/token", data={"username": "owner@example.com", "password": "wrong"})).status_code == 401

async def test_username_unique_and_phone_normalization(api):
    body = {"username": "Student_1", "name": "학생", "phone": "010-1234-5678", "email": "student@example.com", "password": "Validpass1!"}
    created = await api.client.post("/v1/users", json=body)
    assert created.status_code == 201, created.text
    user = created.json()["data"]
    assert user["username"] == "student_1" and user["phone"] == "01012345678"
    duplicate = await api.client.post("/v1/users", json={**body, "username": "STUDENT_1", "email": "another@example.com"})
    assert duplicate.status_code == 409
    assert "password_hash" not in created.text and body["password"] not in created.text

@pytest.mark.parametrize("change", [{"username": "ab"}, {"username": "space here"}, {"phone": "not-a-number"}, {"phone": "123"}])
async def test_invalid_member_fields(api, change):
    body = {"username": "student_1", "name": "학생", "phone": "010-1234-5678", "email": "student@example.com", "password": "Validpass1!", **change}
    assert (await api.client.post("/v1/users", json=body)).status_code == 422

async def test_cors_and_timing_header(api):
    response = await api.client.options("/v1/orders", headers={"Origin": "http://localhost:8000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    denied = await api.client.options("/v1/orders", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in denied.headers
    assert float((await api.client.get("/health")).headers["x-process-time-ms"]) >= 0

async def test_public_board_uses_username_not_real_name(api):
    body = {"username": "a" * 30, "name": "가상 실명", "phone": "01012345678", "email": "private@example.com", "password": "Validpass1!"}
    assert (await api.client.post("/v1/users", json=body)).status_code == 201
    token = (await api.client.post("/v1/auth/token", data={"username": body["email"], "password": body["password"]})).json()["access_token"]
    response = await api.client.post("/v1/boards/free/posts", headers={"Authorization": f"Bearer {token}"}, json={"title": "Public username", "content": "No personal contact data"})
    assert response.status_code == 201, response.text
    assert response.json()["author"]["author_name"] == body["username"]
    assert body["name"] not in response.text and body["phone"] not in response.text and body["email"] not in response.text

async def test_unexpected_failure_has_safe_json_cors_and_timing(api, monkeypatch):
    from products.application.service import ProductService
    async def fail(*args, **kwargs):
        raise RuntimeError("simulated private detail must not appear")
    monkeypatch.setattr(ProductService, "list_products", fail)
    response = await api.client.get("/v1/products", headers={"Origin": "http://localhost:8000"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert "x-process-time-ms" in response.headers
    assert "private detail" not in response.text
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"
