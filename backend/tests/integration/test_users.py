"""
WEB-03 — Administración de usuarios y roles.

Criterios de aceptación verificados aquí:
  1. Un usuario inactivo no puede autenticarse ni ser asignado a nuevos tickets.
  2. El cambio de rol se refleja de inmediato en los permisos calculados.

Además: reactivación, protección del último ADMIN y aislamiento entre
clientes de las operaciones de administración.

Cada test parte de una base recién sembrada (_clean_database en conftest.py),
así que desactivar o cambiar el rol de un usuario aquí no afecta al siguiente.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

DEV2_LOGIN = {"email": "dev2@corestream-tests.com", "password": "TestDev223!@#"}


async def _desactivar(client, admin_headers, user_id):
    res = await client.delete(f"/api/users/{user_id}", headers=admin_headers)
    assert res.status_code == 204, res.text


# ---------------------------------------------------------------------------
# Criterio 1a: un usuario inactivo no puede autenticarse
# ---------------------------------------------------------------------------

async def test_token_de_usuario_desactivado_es_rechazado(
    client, admin_headers, dev2_headers, dev2_id
):
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.get("/api/auth/me", headers=dev2_headers)

    assert res.status_code == 401


async def test_usuario_desactivado_no_puede_hacer_login(client, admin_headers, dev2_id):
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.post("/api/auth/login", json=DEV2_LOGIN)

    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Criterio 1b: un usuario inactivo no puede ser asignado a nuevos tickets
# ---------------------------------------------------------------------------

async def test_no_se_crea_ticket_asignado_a_usuario_desactivado(
    client, admin_headers, leader_headers, dev2_id, epic
):
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.post(
        "/api/tickets/",
        json={"title": "T", "epic_id": epic["id"], "assignee_id": dev2_id},
        headers=leader_headers,
    )

    assert res.status_code == 400


async def test_no_se_reasigna_ticket_a_usuario_desactivado(
    client, admin_headers, leader_headers, dev2_id, ticket
):
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.put(
        f"/api/tickets/{ticket['id']}", json={"assignee_id": dev2_id}, headers=leader_headers
    )
    assert res.status_code == 400

    # Desasignar (assignee_id = null) debe seguir permitido.
    res = await client.put(
        f"/api/tickets/{ticket['id']}", json={"assignee_id": None}, headers=leader_headers
    )
    assert res.status_code == 200


async def test_no_se_redirige_ticket_a_usuario_desactivado(
    client, admin_headers, dev_headers, dev2_id, ticket
):
    await client.post(f"/api/tickets/{ticket['id']}/start", headers=dev_headers)
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.post(
        f"/api/tickets/{ticket['id']}/redirect",
        json={"to_user_id": dev2_id, "justification": "Necesito que lo tome otra persona"},
        headers=dev_headers,
    )

    assert res.status_code == 400


async def test_no_se_asigna_ticket_de_soporte_a_usuario_desactivado(
    client, admin_headers, leader_headers, dev_headers, dev2_id
):
    soporte = await client.post(
        "/api/support-tickets/", json={"title": "Bug en producción"}, headers=dev_headers
    )
    assert soporte.status_code == 201, soporte.text
    await _desactivar(client, admin_headers, dev2_id)

    res = await client.post(
        f"/api/support-tickets/{soporte.json()['id']}/assign",
        json={"assignee_id": dev2_id},
        headers=leader_headers,
    )

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Activar / desactivar
# ---------------------------------------------------------------------------

async def test_admin_reactiva_usuario_y_puede_volver_a_entrar(client, admin_headers, dev2_id):
    await _desactivar(client, admin_headers, dev2_id)

    lista = await client.get("/api/users/", headers=admin_headers)
    assert all(u["id"] != dev2_id for u in lista.json())

    lista = await client.get("/api/users/?include_inactive=true", headers=admin_headers)
    assert any(u["id"] == dev2_id for u in lista.json())

    res = await client.post(f"/api/users/{dev2_id}/activate", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is True

    res = await client.post("/api/auth/login", json=DEV2_LOGIN)
    assert res.status_code == 200


async def test_reactivar_usuario_ya_activo_es_error(client, admin_headers, dev2_id):
    res = await client.post(f"/api/users/{dev2_id}/activate", headers=admin_headers)

    assert res.status_code == 400


async def test_solo_admin_reactiva_y_lista_desactivados(client, leader_headers, dev2_id):
    res = await client.post(f"/api/users/{dev2_id}/activate", headers=leader_headers)
    assert res.status_code == 403

    res = await client.get("/api/users/?include_inactive=true", headers=leader_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Criterio 2: el cambio de rol se refleja de inmediato
# ---------------------------------------------------------------------------

async def test_cambio_de_rol_aplica_con_el_mismo_token(
    client, admin_headers, dev2_headers, dev2_id, application
):
    epica = {"title": "Épica", "application_id": application["id"]}

    res = await client.post("/api/epics/", json=epica, headers=dev2_headers)
    assert res.status_code == 403

    res = await client.post(
        f"/api/users/{dev2_id}/change-role", json={"role": "TEAM_LEADER"}, headers=admin_headers
    )
    assert res.status_code == 200

    # Mismo token de antes: el rol se lee de la BD en cada petición, no del JWT.
    res = await client.post("/api/epics/", json=epica, headers=dev2_headers)
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# Protección del último ADMIN
# ---------------------------------------------------------------------------

async def test_no_se_degrada_al_ultimo_admin(client, admin_headers):
    me = (await client.get("/api/auth/me", headers=admin_headers)).json()

    res = await client.post(
        f"/api/users/{me['id']}/change-role", json={"role": "DEVELOPER"}, headers=admin_headers
    )

    assert res.status_code == 400


async def test_se_puede_degradar_un_admin_si_queda_otro(client, admin_headers, leader_id):
    me = (await client.get("/api/auth/me", headers=admin_headers)).json()
    res = await client.post(
        f"/api/users/{leader_id}/change-role", json={"role": "ADMIN"}, headers=admin_headers
    )
    assert res.status_code == 200

    res = await client.post(
        f"/api/users/{me['id']}/change-role", json={"role": "DEVELOPER"}, headers=admin_headers
    )

    assert res.status_code == 200


async def test_admin_no_puede_desactivarse_a_si_mismo(client, admin_headers):
    me = (await client.get("/api/auth/me", headers=admin_headers)).json()

    res = await client.delete(f"/api/users/{me['id']}", headers=admin_headers)

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# "De su organización": un ADMIN no administra usuarios de otro cliente
# ---------------------------------------------------------------------------

async def test_admin_de_otro_cliente_no_administra_usuarios_ajenos(
    client, admin_b_headers, dev2_id
):
    res = await client.post(
        f"/api/users/{dev2_id}/change-role", json={"role": "ADMIN"}, headers=admin_b_headers
    )
    assert res.status_code == 404

    res = await client.delete(f"/api/users/{dev2_id}", headers=admin_b_headers)
    assert res.status_code == 404

    res = await client.post(f"/api/users/{dev2_id}/activate", headers=admin_b_headers)
    assert res.status_code == 404
