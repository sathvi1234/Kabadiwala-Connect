from tests.conftest import _png, auth


def test_lot_idempotency_and_estimate(client, collector_token):
    headers = auth(collector_token)
    estimate = client.post(
        "/api/lots/estimate",
        json={"material_code": "PCB", "weight": 10, "unit": "kg", "city": "Hyderabad"},
        headers=headers,
    )
    assert estimate.status_code == 200, estimate.text
    body = estimate.json()
    assert body["price_per_kg"] > 0
    assert abs(body["value"] - body["price_per_kg"] * 10) < 0.2
    assert body["source"]
    assert body["date"]

    payload = {
        "material_code": "PCB",
        "weight": 2,
        "unit": "kg",
        "lat": 17.44,
        "lng": 78.49,
        "city": "Hyderabad",
        "idempotency_key": "idem-lot-001",
        "captured_at": "2020-01-01T00:00:00",
    }
    first = client.post("/api/lots", json=payload, headers=headers)
    second = client.post("/api/lots", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["replayed"] is True
    assert first.json()["public_id"].startswith("LOT-")
    assert first.json()["flags"]["gps_present"] is True
    assert first.json()["flags"]["time_ok"] is False
    assert first.json()["flags"]["photo_present"] is False

    missing_gps = client.post(
        "/api/lots",
        json={"material_code": "Cable", "weight": 500, "unit": "g", "city": "Hyderabad", "idempotency_key": "idem-lot-002"},
        headers=headers,
    )
    assert missing_gps.status_code == 200
    assert missing_gps.json()["weight_kg"] == 0.5
    assert missing_gps.json()["flags"]["gps_present"] is False

    photo = client.post(
        f"/api/lots/{first.json()['public_id']}/photos",
        files={"file": ("scrap.png", _png(), "image/png")},
        headers=headers,
    )
    assert photo.status_code == 200, photo.text
    assert photo.json()["flags"]["photo_present"] is True
    qr = client.get(f"/api/lots/{first.json()['public_id']}/qr", headers=headers)
    assert qr.status_code == 200
    assert qr.headers["content-type"].startswith("image/png")


def test_sync_idempotency(client, collector_token):
    headers = auth(collector_token)
    op = {
        "operations": [
            {
                "idempotency_key": "sync-key-7777",
                "type": "create_lot",
                "payload": {"material_code": "Plastic", "weight": 3, "unit": "kg", "lat": 17.4, "lng": 78.4, "city": "Hyderabad"},
            }
        ]
    }
    first = client.post("/api/sync/push", json=op, headers=headers)
    second = client.post("/api/sync/push", json=op, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "synced"
    assert second.json()["results"][0]["replayed"] is True
    assert second.json()["results"][0]["lot"]["id"] == first.json()["results"][0]["lot"]["id"]

    prices = client.post(
        "/api/sync/push",
        json={"operations": [{"idempotency_key": "price-push-1", "type": "price", "payload": {"price_per_kg": 1}}]},
        headers=headers,
    )
    assert prices.json()["results"][0]["conflict"] == "server_wins"


def test_handover_verification_payment_and_receipt(client, collector_token, recycler_token):
    headers = auth(collector_token)
    created = client.post(
        "/api/lots",
        json={
            "material_code": "Copper",
            "weight": 5,
            "unit": "kg",
            "lat": 17.44,
            "lng": 78.49,
            "city": "Hyderabad",
            "idempotency_key": "handover-lot-1",
        },
        headers=headers,
    ).json()
    recyclers = client.get("/api/recyclers/nearby", params={"lat": 17.44, "lng": 78.49, "material": "Copper", "weight": 5}, headers=headers)
    assert recyclers.status_code == 200
    assert recyclers.json()
    assert all(row["verified"] for row in recyclers.json())
    chosen = next(row for row in recyclers.json() if row["business_name"] == "GreenCycle Recycling")
    pickup = client.post(
        "/api/pickups",
        json={"lot_id": created["public_id"], "recycler_id": chosen["recycler_id"], "scheduled_at": "2026-09-29T16:30:00"},
        headers=headers,
    )
    assert pickup.status_code == 200, pickup.text
    accepted = client.patch(f"/api/pickups/{pickup.json()['id']}", json={"status": "accepted"}, headers=auth(recycler_token))
    assert accepted.status_code == 200
    far = client.post(
        f"/api/handovers/{created['public_id']}/collector",
        data={"lat": "28.61", "lng": "77.20", "captured_at": "2026-09-29T16:40:00"},
        files={"file": ("hand.png", _png((20, 20, 20)), "image/png")},
        headers=headers,
    )
    assert far.status_code == 200, far.text
    assert far.json()["flags"]["distance_suspicious"] is True
    done = client.post(
        f"/api/handovers/{created['public_id']}/recycler",
        data={"weight_kg": "4.2", "lat": "28.61", "lng": "77.20", "captured_at": "2026-09-29T16:42:00"},
        headers=auth(recycler_token),
    )
    assert done.status_code == 200, done.text
    assert done.json()["flags"]["weight_mismatch"] is True
    tx = done.json()["transaction_id"]
    partial = client.post(f"/api/transactions/{tx}/pay", json={"amount": 100, "mode": "cash"}, headers=auth(recycler_token))
    assert partial.status_code == 200
    assert partial.json()["status"] == "partial"
    rest = partial.json()["pending_amount"]
    paid = client.post(
        f"/api/transactions/{tx}/pay",
        json={"amount": rest, "mode": "upi", "reference": "UPI999"},
        headers=auth(recycler_token),
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    receipt = client.post(f"/api/transactions/{tx}/receipt", headers=headers)
    assert receipt.status_code == 200
    assert receipt.headers["content-type"] == "application/pdf"
    public = client.get(f"/api/public/verify/{created['public_id']}")
    assert public.json()["found"] is True
    assert "phone" not in public.json()
    assert public.json()["verification"]["distance_flag"] is True
