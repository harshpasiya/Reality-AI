"""Tests for authentication endpoints — POST /auth/register and POST /auth/login."""

import uuid
import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_broker, auth_header


class TestRegister:
    """POST /auth/register."""

    def test_register_broker_success(self, client: TestClient):
        unique_email = f"newbroker_{uuid.uuid4().hex[:8]}@test.com"
        resp = client.post("/auth/register", json={
            "email": unique_email,
            "password": "securepass1",
            "name": "New Broker",
            "role": "broker",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"] == {
            "id": data["user"]["id"],
            "email": unique_email,
            "name": "New Broker",
            "role": "broker",
        }
        assert isinstance(data["user"]["id"], int)

    def test_register_customer_success(self, client: TestClient):
        unique_email = f"newcustomer_{uuid.uuid4().hex[:8]}@test.com"
        resp = client.post("/auth/register", json={
            "email": unique_email,
            "password": "securepass1",
            "name": "New Customer",
            "role": "customer",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"] == {
            "id": data["user"]["id"],
            "email": unique_email,
            "name": "New Customer",
            "role": "customer",
        }
        assert isinstance(data["user"]["id"], int)

    def test_register_duplicate_email_409(self, client: TestClient):
        register_broker(client, email="dup@test.com")
        resp = client.post("/auth/register", json={
            "email": "dup@test.com",
            "password": "securepass1",
            "name": "Duplicate",
            "role": "broker",
        })
        assert resp.status_code == 409

    def test_register_invalid_role_422(self, client: TestClient):
        resp = client.post("/auth/register", json={
            "email": "bad@test.com",
            "password": "securepass1",
            "name": "Bad Role",
            "role": "admin",
        })
        assert resp.status_code == 422


class TestLogin:
    """POST /auth/login."""

    def test_login_success(self, client: TestClient):
        register_broker(client, email="login@test.com")
        resp = client.post("/auth/login", data={
            "username": "login@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"] == {
            "id": data["user"]["id"],
            "email": "login@test.com",
            "name": "Test Broker",
            "role": "broker",
        }
        assert isinstance(data["user"]["id"], int)

    def test_login_wrong_password_401(self, client: TestClient):
        register_broker(client, email="wrongpw@test.com")
        resp = client.post("/auth/login", data={
            "username": "wrongpw@test.com",
            "password": "wrongwrongwrong",
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect email or password"

    def test_login_nonexistent_user_401(self, client: TestClient):
        resp = client.post("/auth/login", data={
            "username": "noone@test.com",
            "password": "whatever123",
        })
        assert resp.status_code == 401


class TestMe:
    """GET /auth/me."""

    def test_me_success(self, client: TestClient):
        reg = register_broker(client, email="me@test.com")
        token = reg["access_token"]
        resp = client.get("/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["name"] == "Test Broker"
        assert data["role"] == "broker"
        assert "created_at" in data


class TestRegisterLimits:
    """Password length, email normalisation and broker phone."""

    def test_long_password_422_not_500(self, client: TestClient):
        resp = client.post("/auth/register", json={
            "email": f"longpw_{uuid.uuid4().hex[:8]}@test.com",
            "password": "p" * 100,
            "name": "Long",
            "role": "customer",
        })
        assert resp.status_code == 422

    def test_multibyte_password_over_72_bytes_422(self, client: TestClient):
        resp = client.post("/auth/register", json={
            "email": f"mbpw_{uuid.uuid4().hex[:8]}@test.com",
            "password": "अ" * 30,  # 30 chars, 90 UTF-8 bytes
            "name": "Hindi",
            "role": "customer",
        })
        assert resp.status_code == 422

    def test_email_case_insensitive_duplicate_409(self, client: TestClient):
        local = f"case_{uuid.uuid4().hex[:8]}"
        register_broker(client, email=f"{local}@test.com")
        resp = client.post("/auth/register", json={
            "email": f"  {local.upper()}@Test.com ",
            "password": "securepass1",
            "name": "Upper",
            "role": "customer",
        })
        assert resp.status_code == 409

    def test_login_with_different_case(self, client: TestClient):
        local = f"logincase_{uuid.uuid4().hex[:8]}"
        register_broker(client, email=f"{local}@test.com")
        resp = client.post("/auth/login", data={
            "username": f"{local.upper()}@TEST.COM",
            "password": "testpass123",
        })
        assert resp.status_code == 200

    def test_broker_phone_returned_by_me(self, client: TestClient):
        reg = register_broker(client, email=f"phone_{uuid.uuid4().hex[:8]}@test.com", phone="+919876543210")
        me = client.get("/auth/me", headers=auth_header(reg["access_token"])).json()
        assert me["phone"] == "+919876543210"

    def test_invalid_phone_422(self, client: TestClient):
        resp = client.post("/auth/register", json={
            "email": f"badphone_{uuid.uuid4().hex[:8]}@test.com",
            "password": "securepass1",
            "name": "Bad Phone",
            "role": "broker",
            "phone": "98765 43210",
        })
        assert resp.status_code == 422

    def test_customer_phone_422(self, client: TestClient):
        resp = client.post("/auth/register", json={
            "email": f"custphone_{uuid.uuid4().hex[:8]}@test.com",
            "password": "securepass1",
            "name": "Cust",
            "role": "customer",
            "phone": "+919876543210",
        })
        assert resp.status_code == 422
