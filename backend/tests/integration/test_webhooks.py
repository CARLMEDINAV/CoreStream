"""Pruebas de integración de webhooks salientes (NEW-12).

Requieren PostgreSQL y Redis reales (ver conftest de integración). Ejercitan
el contrato HTTP completo: RBAC (sólo ADMIN), aislamiento por tenant y el
disparo real de una entrega al crear un ticket.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _create_webhook(client, headers, **overrides) -> dict:
    payload = {
        "name": "Integración de prueba",
        "url": "https://example.com/corestream-hook",
        "event_types": ["TICKET_CREATED"],
    }
    payload.update(overrides)
    res = await client.post("/api/webhooks/", json=payload, headers=headers)
    assert res.status_code == 201, res.text[:300]
    return res.json()


async def test_admin_crud_and_secret_shown_once(client, admin_headers):
    created = await _create_webhook(client, admin_headers)
    assert created["secret"]
    assert created["has_secret"] is True

    webhook_id = created["id"]

    listed = await client.get("/api/webhooks/", headers=admin_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert any(w["id"] == webhook_id for w in body)
    # El secreto nunca se devuelve en las lecturas
    assert all("secret" not in w for w in body)

    fetched = await client.get(f"/api/webhooks/{webhook_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert "secret" not in fetched.json()

    updated = await client.put(
        f"/api/webhooks/{webhook_id}",
        json={"is_active": False, "event_types": []},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["event_types"] == []

    rotated = await client.post(f"/api/webhooks/{webhook_id}/rotate-secret", headers=admin_headers)
    assert rotated.status_code == 200
    assert rotated.json()["secret"] and rotated.json()["secret"] != created["secret"]

    deleted = await client.delete(f"/api/webhooks/{webhook_id}", headers=admin_headers)
    assert deleted.status_code == 204


async def test_only_admin_can_manage(client, admin_headers, leader_headers, dev_headers):
    await _create_webhook(client, admin_headers)

    for headers in (leader_headers, dev_headers):
        assert (await client.get("/api/webhooks/", headers=headers)).status_code == 403
        assert (
            await client.post(
                "/api/webhooks/",
                json={"name": "x", "url": "https://example.com/x"},
                headers=headers,
            )
        ).status_code == 403


async def test_invalid_url_is_rejected(client, admin_headers):
    res = await client.post(
        "/api/webhooks/",
        json={"name": "malo", "url": "http://localhost:9000/hook"},
        headers=admin_headers,
    )
    assert res.status_code == 422


async def test_webhook_is_tenant_scoped(client, admin_headers, admin_b_headers):
    created = await _create_webhook(client, admin_headers)

    # El ADMIN del otro cliente no ve ni puede tocar este webhook
    listed = await client.get("/api/webhooks/", headers=admin_b_headers)
    assert all(w["id"] != created["id"] for w in listed.json())

    fetched = await client.get(f"/api/webhooks/{created['id']}", headers=admin_b_headers)
    assert fetched.status_code == 404


async def test_ticket_creation_dispatches_delivery(
    client, admin_headers, leader_headers, epic, dev_id
):
    created = await _create_webhook(
        client, admin_headers, name="Creados", event_types=["TICKET_CREATED"]
    )

    res = await client.post(
        "/api/tickets/",
        json={
            "epic_id": epic["id"],
            "title": "Ticket que dispara webhook",
            "priority": "HIGH",
            "assignee_id": dev_id,
        },
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]

    deliveries = await client.get(
        f"/api/webhooks/{created['id']}/deliveries", headers=admin_headers
    )
    assert deliveries.status_code == 200
    rows = deliveries.json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["event_type"] == "TICKET_CREATED"
    assert row["status"] in ("PENDING", "SUCCESS", "FAILED")
    payload = row["payload"]
    assert payload["event"] == "TICKET_CREATED"
    assert payload["ticket"]["title"] == "Ticket que dispara webhook"
