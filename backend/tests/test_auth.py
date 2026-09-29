from tests.conftest import auth


def test_demo_login_and_public_stats(client):
    stats = client.get("/api/public/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["collectors"] >= 3
    assert "co2_kg" in body
    prices = client.get("/api/public/prices")
    assert prices.status_code == 200
    assert len(prices.json()["items"]) >= 10
    demo = client.post("/api/auth/demo-login", json={"role": "collector"})
    assert demo.status_code == 200
    assert demo.json()["user"]["is_demo"] is True
    assert demo.json()["user"]["role"] == "collector"
    locked = client.patch("/api/auth/me", headers=auth(demo.json()["token"]), json={"password": "Newpass123"})
    assert locked.status_code == 403


def test_roles_and_guards(client, collector_token, recycler_token, admin_token):
    assert client.get("/api/admin/summary").status_code == 401
    denied = client.get("/api/admin/summary", headers=auth(collector_token))
    assert denied.status_code == 403
    ok = client.get("/api/admin/summary", headers=auth(admin_token))
    assert ok.status_code == 200
    assert ok.json()["collectors"] >= 3
    me = client.get("/api/auth/me", headers=auth(recycler_token))
    assert me.json()["profile"]["status"] == "approved"


def test_register_collector_requires_otp(client):
    phone = "9000002222"
    otp = client.post("/api/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    bad = client.post(
        "/api/auth/register/collector",
        data={
            "name": "New Collector",
            "phone": phone,
            "password": "Demo@123",
            "otp": "000000",
            "preferred_language": "hi",
            "area": "Abids",
            "city": "Hyderabad",
            "materials": '["PCB"]',
        },
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/register/collector",
        data={
            "name": "New Collector",
            "phone": phone,
            "password": "Demo@123",
            "otp": otp,
            "preferred_language": "mr",
            "area": "Abids",
            "city": "Hyderabad",
            "materials": '["PCB","Cable"]',
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["user"]["preferred_language"] == "mr"
    pending = client.post(
        "/api/auth/otp/request",
        json={"phone": "9000003333"},
    )
    otp2 = pending.json()["dev_otp"]
    reg = client.post(
        "/api/auth/register/recycler",
        data={
            "name": "New Yard",
            "phone": "9000003333",
            "password": "Demo@123",
            "otp": otp2,
            "business_name": "New Yard",
            "licence_number": "LIC-1",
            "address": "Somewhere",
            "city": "Hyderabad",
            "lat": "17.4",
            "lng": "78.4",
            "materials": '["Plastic"]',
            "working_hours": '{"mon":"09:00-17:00"}',
        },
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["user"]["profile"]["status"] == "pending"
