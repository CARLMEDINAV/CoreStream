"""prueba el control comercial con postgres y redis."""
import psycopg2

from tests.integration.conftest import DEFAULT_CLIENT_SLUG, TEST_DATABASE_URL


def set_plan(plan):
    with psycopg2.connect(TEST_DATABASE_URL.replace("+asyncpg", "")) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE clients SET commercial_plan = %s WHERE slug = %s",
                           (plan, DEFAULT_CLIENT_SLUG))


async def test_live_plan_change_and_tenant_isolation(client, admin_headers, admin_b_headers):
    import asyncio

    await asyncio.to_thread(set_plan, "Basico")
    profile = await client.get("/api/auth/commercial-profile", headers=admin_headers)
    assert profile.status_code == 200
    assert profile.json()["plan"] == "Basico"
    url = "/api/analytics/support-summary"
    assert (await client.get(url, headers=admin_headers)).status_code == 403
    assert (await client.get(url, headers=admin_b_headers)).status_code == 200
    await asyncio.to_thread(set_plan, "Pro")
    assert (await client.get(url, headers=admin_headers)).status_code == 200


async def test_pro_preserves_role_restriction(client, dev_headers, application):
    response = await client.get(
        f"/api/analytics/export/csv/{application['id']}", headers=dev_headers
    )
    assert response.status_code == 403
    assert isinstance(response.json()["detail"], str)  # rechazo por rol
