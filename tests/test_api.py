import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from auth.infrastructure.security import JwtTokenProvider
from board.infrastructure.models import BoardModel, PostModel
from shared.core.exceptions import UnauthorizedException, ValidationException
from user.infrastructure.models import UserModel
from user.infrastructure.security import BcryptPasswordHasher
from wiring.auth import token_provider


async def create_post(api, board="free", **values):
    body = {"title": "First post", "content": "Learning four layers", **values}
    headers = api.headers["owner"] if board == "free" else {}
    response = await api.client.post(f"/v1/boards/{board}/posts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def assert_error(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is False
    assert body["code"] and body["message"] and body["responded_at"]
    assert body["data"] is None


async def test_signup_login_and_no_password_leak(api):
    body = {"email": "new@example.com", "name": "newuser", "username": "newuser", "phone": "010-0000-0000", "password": "Validpass1!"}
    response = await api.client.post("/v1/users", json=body)
    assert response.status_code == 201
    assert response.json()["data"]["role"] == "USER"
    assert "password" not in response.text
    login = await api.client.post("/v1/auth/login", json={"email": body["email"], "password": body["password"]})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    async with api.sessions() as session:
        model = await session.scalar(select(UserModel).where(UserModel.email == body["email"]))
        assert model.password_hash != body["password"]
        assert BcryptPasswordHasher().verify(body["password"], model.password_hash)
    assert_error(await api.client.post("/v1/users", json=body), 409)


@pytest.mark.parametrize("changes", [
    {"email": "invalid"}, {"name": " "}, {"password": "short"},
    {"password": "abcdefgh"}, {"password": "A1!" + "a" * 70},
])
async def test_signup_validation(api, changes):
    body = {"email": "new@example.com", "name": "tester", "username": "tester", "phone": "010-0000-0000", "password": "Validpass1!", **changes}
    assert_error(await api.client.post("/v1/users", json=body), 422)


async def test_member_crud_and_owner_permission(api):
    post = await create_post(api)
    post_id = post["post_id"]
    assert post["author"]["author_id"] == str(api.users["owner"].id)
    assert "password" not in str(post)
    detail = await api.client.get(f"/v1/posts/{post_id}")
    assert detail.status_code == 200
    changes = {"title": "Changed", "content": "Updated content"}
    assert_error(await api.client.put(f"/v1/posts/{post_id}", json=changes, headers=api.headers["other"]), 403)
    assert_error(await api.client.delete(f"/v1/posts/{post_id}", headers=api.headers["other"]), 403)
    updated = await api.client.put(f"/v1/posts/{post_id}", json=changes, headers=api.headers["owner"])
    assert updated.status_code == 200 and updated.json()["title"] == "Changed"
    assert updated.json()["modified_at"] is not None
    deleted = await api.client.delete(f"/v1/posts/{post_id}", headers=api.headers["owner"])
    assert deleted.status_code == 204 and deleted.content == b""
    assert_error(await api.client.get(f"/v1/posts/{post_id}"), 404)
    async with api.sessions() as session:
        assert (await session.get(PostModel, post_id)).deleted_at is not None


async def test_writing_requires_login_in_default_board(api):
    assert_error(await api.client.post("/v1/boards/free/posts", json={
        "title": "Guest", "content": "No login", "guest_name": "guest", "guest_password": "guestpass",
    }), 403)


async def test_pagination_uses_board_size_and_search(api):
    for index in range(5):
        await create_post(api, title=f"lesson {index}")
    page = (await api.client.get("/v1/boards/free/posts")).json()
    assert page["page_size"] == 2 and page["total_count"] == 5 and page["total_pages"] == 3
    assert len(page["items"]) == 2
    last = (await api.client.get("/v1/boards/free/posts?page=3")).json()
    assert len(last["items"]) == 1
    explicit = (await api.client.get("/v1/boards/free/posts?page_size=3")).json()
    assert explicit["page_size"] == 3 and explicit["total_pages"] == 2
    found = (await api.client.get("/v1/boards/free/posts?search_type=TITLE&keyword=lesson%204")).json()
    assert found["total_count"] == 1 and found["items"][0]["title"] == "lesson 4"


async def test_created_at_is_evaluated_each_insert(api):
    first = await create_post(api)
    await asyncio.sleep(0.02)
    second = await create_post(api)
    assert datetime.fromisoformat(second["created_at"]) > datetime.fromisoformat(first["created_at"])


async def test_guest_post_password_and_no_hash_leak(api):
    post = await create_post(api, board="guest", guest_name="guest", guest_password="guestpass")
    post_id = post["post_id"]
    assert post["author"]["is_guest"] is True
    assert "password" not in str(post)
    changes = {"title": "Changed", "content": "Guest update", "guest_password": "wrongpass"}
    assert_error(await api.client.put(f"/v1/posts/{post_id}", json=changes), 403)
    changes["guest_password"] = "guestpass"
    assert (await api.client.put(f"/v1/posts/{post_id}", json=changes)).status_code == 200
    assert_error(await api.client.delete(f"/v1/posts/{post_id}"), 403)
    assert (await api.client.request("DELETE", f"/v1/posts/{post_id}", json={"guest_password": "guestpass"})).status_code == 204


async def test_guest_long_unicode_password_is_validation_error(api):
    assert_error(await api.client.post("/v1/boards/guest/posts", json={
        "title": "Guest", "content": "Test", "guest_name": "guest", "guest_password": "한" * 25,
    }), 422)


async def test_comment_crud_and_owner_permission(api):
    post = await create_post(api)
    route = f"/v1/posts/{post['post_id']}/comments"
    response = await api.client.post(route, json={"content": "Nice lesson"}, headers=api.headers["owner"])
    assert response.status_code == 201
    comment_id = response.json()["comment_id"]
    assert len((await api.client.get(route)).json()) == 1
    changes = {"content": "Changed comment"}
    assert_error(await api.client.put(f"/v1/comments/{comment_id}", json=changes, headers=api.headers["other"]), 403)
    assert_error(await api.client.delete(f"/v1/comments/{comment_id}", headers=api.headers["other"]), 403)
    updated = await api.client.put(f"/v1/comments/{comment_id}", json=changes, headers=api.headers["owner"])
    assert updated.status_code == 200 and updated.json()["modified_at"] is not None
    assert (await api.client.delete(f"/v1/comments/{comment_id}", headers=api.headers["owner"])).status_code == 204
    assert (await api.client.get(route)).json() == []


async def test_admin_can_moderate_post_and_comment(api):
    post = await create_post(api)
    comment = await api.client.post(f"/v1/posts/{post['post_id']}/comments", json={"content": "Comment"}, headers=api.headers["owner"])
    assert (await api.client.delete(f"/v1/comments/{comment.json()['comment_id']}", headers=api.headers["admin"])).status_code == 204
    assert (await api.client.delete(f"/v1/posts/{post['post_id']}", headers=api.headers["admin"])).status_code == 204


async def test_board_admin_duplicate_and_soft_delete(api):
    body = {"board_id": "notice", "board_name": "Notice"}
    assert_error(await api.client.post("/v1/boards", json=body, headers=api.headers["owner"]), 403)
    assert (await api.client.post("/v1/boards", json=body, headers=api.headers["admin"])).status_code == 201
    assert_error(await api.client.post("/v1/boards", json={**body, "board_id": "NOTICE"}, headers=api.headers["admin"]), 409)
    assert (await api.client.delete("/v1/boards/notice", headers=api.headers["admin"])).status_code == 204
    assert_error(await api.client.post("/v1/boards", json=body, headers=api.headers["admin"]), 409)
    assert_error(await api.client.get("/v1/boards/notice"), 404)
    assert_error(await api.client.get("/v1/boards?include_deleted=true"), 403)


async def test_deleted_board_hides_posts_and_comments(api):
    post = await create_post(api)
    assert (await api.client.delete("/v1/boards/free", headers=api.headers["admin"])).status_code == 204
    assert_error(await api.client.get(f"/v1/posts/{post['post_id']}"), 404)
    assert_error(await api.client.get(f"/v1/posts/{post['post_id']}/comments"), 404)


@pytest.mark.parametrize("authorization", ["Bearer invalid", "Basic invalid", "Bearer"])
async def test_invalid_authentication_not_treated_as_guest(api, authorization):
    assert_error(await api.client.get("/v1/boards/free/posts", headers={"Authorization": authorization}), 401)


async def test_login_logout_and_blacklist(api):
    assert_error(await api.client.post("/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}), 401)
    assert_error(await api.client.post("/v1/auth/login", json={"email": "owner@example.com", "password": "a" * 73}), 401)
    assert (await api.client.post("/v1/auth/logout", headers=api.headers["owner"])).status_code == 204
    assert_error(await api.client.get("/v1/boards/free/posts", headers=api.headers["owner"]), 401)
    assert_error(await api.client.post("/v1/auth/logout"), 401)


async def test_withdrawn_user_cannot_login(api):
    async with api.sessions.begin() as session:
        user = await session.get(UserModel, api.users["owner"].id)
        user.resign = True
    assert_error(await api.client.post("/v1/auth/login", json={"email": "owner@example.com", "password": "Validpass1!"}), 401)


async def test_password_change_requires_owner_token(api):
    user_id = api.users["owner"].id
    body = {"old_password": "Validpass1!", "new_password": "Newpassword2!"}
    assert_error(await api.client.patch(f"/v1/users/{user_id}/password", json=body), 401)
    assert_error(await api.client.patch(f"/v1/users/{user_id}/password", json=body, headers=api.headers["other"]), 403)
    assert (await api.client.patch(f"/v1/users/{user_id}/password", json=body, headers=api.headers["owner"])).status_code == 200
    assert (await api.client.post("/v1/auth/login", json={"email": "owner@example.com", "password": body["new_password"]})).status_code == 200


@pytest.mark.parametrize("path,status", [("/does-not-exist",404), ("/v1/posts/999999",404), ("/v1/boards/free/posts?page=0",422), ("/v1/boards/free/posts?page_size=101",422)])
async def test_consistent_error_envelope(api, path, status):
    assert_error(await api.client.get(path), status)


async def test_swagger_and_openapi(api):
    assert (await api.client.get("/docs")).status_code == 200
    schema = (await api.client.get("/openapi.json")).json()
    assert "/v1/boards/{board_id}/posts" in schema["paths"]
    assert "OAuth2PasswordBearer" in schema["components"]["securitySchemes"]


@pytest.mark.parametrize("overrides", [{"exp": 0}, {"sub": None}, {"jti": "invalid"}, {"exp": []}])
def test_invalid_signed_claims_return_unauthorized(overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": str(uuid.uuid4()), "jti": str(uuid.uuid4()), "iat": now, "exp": now+timedelta(minutes=1), **overrides}
    token = jwt.encode(claims, token_provider.secret_key, algorithm="HS512")
    with pytest.raises(UnauthorizedException):
        token_provider.decode_token(token)


def test_short_jwt_key_rejected():
    with pytest.raises(RuntimeError):
        JwtTokenProvider(secret_key="weak")


def test_bcrypt_byte_boundary():
    hasher = BcryptPasswordHasher()
    password = "한" * 24
    hashed = hasher.hash(password)
    assert hasher.verify(password, hashed)
    assert not hasher.verify(password + "a", hashed)
    with pytest.raises(ValidationException):
        hasher.hash(password + "a")


async def test_email_normalization_and_unknown_login(api):
    body = {"email": "NewUser@example.com", "name": "tester", "username": "tester", "phone": "010-0000-0000", "password": "Validpass1!"}
    assert (await api.client.post("/v1/users", json=body)).status_code == 201
    assert_error(await api.client.post("/v1/users", json={**body, "email": "newuser@example.com"}), 409)
    assert (await api.client.post("/v1/auth/login", json={"email": "NEWUSER@example.com", "password": body["password"]})).status_code == 200
    assert_error(await api.client.post("/v1/auth/login", json={"email": "missing@example.com", "password": body["password"]}), 401)


async def test_search_does_not_expose_email_or_expand_wildcards(api):
    await create_post(api)
    found = (await api.client.get("/v1/boards/free/posts?keyword=owner%40example.com")).json()
    assert found["total_count"] == 0
    found = (await api.client.get("/v1/boards/free/posts", params={"keyword": "%"})).json()
    assert found["total_count"] == 0
    assert_error(await api.client.get("/v1/boards/free/posts?search_type=AUTHOR_EMAIL&keyword=owner"), 422)


async def test_query_length_and_method_errors(api):
    assert_error(await api.client.get("/v1/boards/free/posts", params={"keyword": "x"*51}), 422)
    assert_error(await api.client.patch("/v1/auth/login"), 405)


@pytest.mark.parametrize("method,path", [
    ("GET", "/v1/posts/0"),
    ("GET", "/v1/posts/9223372036854775808"),
    ("GET", "/v1/posts/999999999999999999999/comments"),
    ("PUT", "/v1/comments/9223372036854775808"),
    ("DELETE", "/v1/comments/0"),
    ("GET", "/v1/boards/free/posts?page=1000001"),
])
async def test_database_integer_bounds(api, method, path):
    response = await api.client.request(method, path, json={"content": "Valid content"}, headers=api.headers["owner"])
    assert_error(response, 422)


async def test_email_plus_alias_is_valid(api):
    body = {"email": "student+board@example.com", "name": "student", "username": "student", "phone": "010-0000-0000", "password": "Validpass1!"}
    assert (await api.client.post("/v1/users", json=body)).status_code == 201
    assert (await api.client.post("/v1/auth/login", json={"email": body["email"], "password": body["password"]})).status_code == 200


async def test_board_put_requires_page_size(api):
    assert_error(await api.client.put("/v1/boards/free", json={"board_name": "Renamed"}, headers=api.headers["admin"]), 422)
    response = await api.client.get("/v1/boards/free")
    assert response.json()["page_size"] == 2
    response = await api.client.put("/v1/boards/free", json={"board_name": "Renamed", "page_size": 3}, headers=api.headers["admin"])
    assert response.status_code == 200 and response.json()["page_size"] == 3


async def test_board_paths_use_normalized_id(api):
    post = await create_post(api)
    assert (await api.client.get("/v1/boards/FREE")).json()["board_id"] == "free"
    response = await api.client.get("/v1/boards/FREE/posts")
    assert response.status_code == 200 and response.json()["items"][0]["post_id"] == post["post_id"]
