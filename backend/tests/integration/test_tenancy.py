"""
Aislamiento multi-tenant (TRV-01, Fase 6).

Dos tenants: el cliente "por defecto" (bootstrap, donde viven ADMIN/LEADER/
DEV/DEV2 — ver conftest.py) y un segundo cliente ("cliente B", con
LEADER_B/DEV_B). El principio a verificar: un usuario de un cliente nunca
ve, edita, borra ni lista un recurso de otro cliente — 404, no 403, mismo
criterio que ya sigue RBAC.md para no confirmar ni la existencia del
recurso a un tenant ajeno.
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

async def test_cliente_b_no_ve_aplicacion_de_cliente_a(client, leader_b_headers, application):
    res = await client.get(f"/api/applications/{application['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_edita_aplicacion_de_cliente_a(client, leader_b_headers, application):
    res = await client.put(
        f"/api/applications/{application['id']}",
        json={"name": "Secuestrada"},
        headers=leader_b_headers,
    )
    assert res.status_code == 404


async def test_cliente_b_no_borra_aplicacion_de_cliente_a(client, leader_b_headers, application):
    res = await client.delete(f"/api/applications/{application['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_lista_aplicacion_de_cliente_a(client, leader_b_headers, application):
    res = await client.get("/api/applications/", headers=leader_b_headers)
    assert res.status_code == 200
    assert all(a["id"] != application["id"] for a in res.json())


# ---------------------------------------------------------------------------
# Epics
# ---------------------------------------------------------------------------

async def test_cliente_b_no_ve_epica_de_cliente_a(client, leader_b_headers, epic):
    res = await client.get(f"/api/epics/{epic['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_edita_epica_de_cliente_a(client, leader_b_headers, epic):
    res = await client.put(
        f"/api/epics/{epic['id']}", json={"title": "Secuestrada"}, headers=leader_b_headers
    )
    assert res.status_code == 404


async def test_cliente_b_no_borra_epica_de_cliente_a(client, leader_b_headers, epic):
    res = await client.delete(f"/api/epics/{epic['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_lista_epicas_de_cliente_a_por_app(client, leader_b_headers, application, epic):
    res = await client.get(f"/api/epics/by-app/{application['id']}", headers=leader_b_headers)
    assert res.status_code == 200
    assert all(e["id"] != epic["id"] for e in res.json())


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

async def test_cliente_b_no_ve_ticket_de_cliente_a(client, dev_b_headers, ticket):
    res = await client.get(f"/api/tickets/{ticket['id']}", headers=dev_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_edita_ticket_de_cliente_a(client, dev_b_headers, ticket):
    res = await client.put(
        f"/api/tickets/{ticket['id']}", json={"title": "Secuestrado"}, headers=dev_b_headers
    )
    assert res.status_code == 404


async def test_cliente_b_no_borra_ticket_de_cliente_a(client, leader_b_headers, ticket):
    res = await client.delete(f"/api/tickets/{ticket['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_inicia_ticket_de_cliente_a(client, dev_b_headers, ticket):
    res = await client.post(f"/api/tickets/{ticket['id']}/start", json={}, headers=dev_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_lista_ticket_de_cliente_a(client, dev_b_headers, ticket):
    res = await client.get("/api/tickets/", headers=dev_b_headers)
    assert res.status_code == 200
    assert all(t["id"] != ticket["id"] for t in res.json())


async def test_cliente_b_no_ve_eventos_de_ticket_de_cliente_a(client, dev_b_headers, ticket):
    res = await client.get(f"/api/tickets/{ticket['id']}/events", headers=dev_b_headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Subtareas
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def subtask(client, dev_headers, ticket):
    res = await client.post(
        f"/api/tickets/{ticket['id']}/subtasks/",
        json={"title": "Subtarea de A", "ticket_id": ticket["id"]},
        headers=dev_headers,
    )
    assert res.status_code == 201, res.text[:200]
    return res.json()


async def test_cliente_b_no_lista_subtareas_de_ticket_de_cliente_a(client, dev_b_headers, ticket, subtask):
    res = await client.get(f"/api/tickets/{ticket['id']}/subtasks/", headers=dev_b_headers)
    assert res.status_code == 200
    assert all(s["id"] != subtask["id"] for s in res.json())


async def test_cliente_b_no_edita_subtarea_de_cliente_a(client, dev_b_headers, ticket, subtask):
    res = await client.put(
        f"/api/tickets/{ticket['id']}/subtasks/{subtask['id']}",
        json={"title": "Secuestrada", "is_completed": True, "order_index": 0},
        headers=dev_b_headers,
    )
    assert res.status_code == 404


async def test_cliente_b_no_borra_subtarea_de_cliente_a(client, dev_b_headers, ticket, subtask):
    res = await client.delete(
        f"/api/tickets/{ticket['id']}/subtasks/{subtask['id']}", headers=dev_b_headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Incidentes
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def incident(client, dev_headers):
    res = await client.post(
        "/api/incidents/",
        json={"title": "Incidente de A", "description": "x", "severity": "P3"},
        headers=dev_headers,
    )
    assert res.status_code == 201, res.text[:200]
    return res.json()


async def test_cliente_b_no_ve_incidente_de_cliente_a(client, dev_b_headers, incident):
    res = await client.get(f"/api/incidents/{incident['id']}", headers=dev_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_edita_incidente_de_cliente_a(client, leader_b_headers, incident):
    res = await client.patch(
        f"/api/incidents/{incident['id']}", json={"title": "Secuestrado"}, headers=leader_b_headers
    )
    assert res.status_code == 404


async def test_cliente_b_no_lista_incidente_de_cliente_a(client, dev_b_headers, incident):
    res = await client.get("/api/incidents/", headers=dev_b_headers)
    assert res.status_code == 200
    assert all(i["id"] != incident["id"] for i in res.json())


# ---------------------------------------------------------------------------
# Reuniones
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def meeting(client, leader_headers):
    res = await client.post(
        "/api/meetings/",
        json={"title": "Reunión de A", "scheduled_at": "2030-01-01T10:00:00Z"},
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:200]
    return res.json()


async def test_cliente_b_no_ve_reunion_de_cliente_a(client, leader_b_headers, meeting):
    res = await client.get(f"/api/meetings/{meeting['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_edita_reunion_de_cliente_a(client, leader_b_headers, meeting):
    res = await client.patch(
        f"/api/meetings/{meeting['id']}", json={"title": "Secuestrada"}, headers=leader_b_headers
    )
    assert res.status_code == 404


async def test_cliente_b_no_lista_reunion_de_cliente_a(client, leader_b_headers, meeting):
    res = await client.get("/api/meetings/", headers=leader_b_headers)
    assert res.status_code == 200
    assert all(m["id"] != meeting["id"] for m in res.json())


# ---------------------------------------------------------------------------
# Usuarios (listado)
# ---------------------------------------------------------------------------

async def test_cliente_b_no_lista_usuarios_de_cliente_a(client, leader_b_headers, dev_id):
    res = await client.get("/api/users/", headers=leader_b_headers)
    assert res.status_code == 200
    assert all(u["id"] != dev_id for u in res.json())


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def document(client, dev_headers, epic):
    res = await client.post(
        "/api/documents/",
        files={"file": ("nota.md", b"# Documento de A", "text/markdown")},
        data={"epicId": epic["id"], "docType": "DOCUMENTATION"},
        headers=dev_headers,
    )
    assert res.status_code == 201, res.text[:200]
    return res.json()


async def test_cliente_b_no_descarga_documento_de_cliente_a(client, dev_b_headers, document):
    res = await client.get(f"/api/documents/{document['id']}/download", headers=dev_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_borra_documento_de_cliente_a(client, leader_b_headers, document):
    res = await client.delete(f"/api/documents/{document['id']}", headers=leader_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_traduce_documento_de_cliente_a(client, dev_b_headers, document):
    res = await client.post(
        f"/api/documents/{document['id']}/translate",
        json={"target_language": "en"},
        headers=dev_b_headers,
    )
    assert res.status_code == 404


async def test_cliente_b_no_lista_documentos_de_epica_de_cliente_a(client, dev_b_headers, epic, document):
    res = await client.get(
        "/api/documents/", params={"epicId": epic["id"]}, headers=dev_b_headers
    )
    assert res.status_code == 200
    assert all(d["id"] != document["id"] for d in res.json())


async def test_cliente_b_no_sube_documento_a_epica_de_cliente_a(client, dev_b_headers, epic):
    res = await client.post(
        "/api/documents/",
        files={"file": ("intruso.md", b"# No deberia poder", "text/markdown")},
        data={"epicId": epic["id"]},
        headers=dev_b_headers,
    )
    assert res.status_code == 404


    # ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(loop_scope="session")
async def notification(client, dev_headers, ticket):
    """
    No hay endpoint para crear una notificación directamente: se generan
    como efecto secundario. El fixture `ticket` ya asigna el ticket a `dev`
    al crearlo, lo que dispara notify_ticket_assigned() -> create_notification()
    para el destinatario (dev, cliente A).
    """
    res = await client.get("/api/notifications/", headers=dev_headers)
    assert res.status_code == 200
    assert res.json(), "se esperaba al menos una notificación tras asignar el ticket"
    return res.json()[0]


async def test_cliente_b_no_borra_notificacion_de_cliente_a(client, dev_b_headers, notification):
    res = await client.delete(f"/api/notifications/{notification['id']}", headers=dev_b_headers)
    assert res.status_code == 404


async def test_cliente_b_no_marca_como_leida_notificacion_de_cliente_a(client, dev_b_headers, notification):
    """
    Este endpoint no distingue "no encontrado" de "no es tuyo": simplemente
    filtra y cuenta. Si dev_b intenta marcar una notificación de dev (cliente
    A), el filtro por user_id ya la excluye — se espera 200 con 0 marcadas,
    no un 404.
    """
    res = await client.post(
        "/api/notifications/mark-read",
        json={"notification_ids": [notification["id"]]},
        headers=dev_b_headers,
    )
    assert res.status_code == 200
    assert res.json()["marked_as_read"] == 0


async def test_cliente_b_no_lista_notificacion_de_cliente_a(client, dev_b_headers, notification):
    res = await client.get("/api/notifications/", headers=dev_b_headers)
    assert res.status_code == 200
    assert all(n["id"] != notification["id"] for n in res.json())

# ---------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------

async def test_invitacion_es_consultable_sin_autenticar(client, admin_headers):
    """Confirma que el filtro de tenant no interfiere con las rutas públicas."""
    inv = await client.post(
        "/api/invitations/",
        json={"email": "prueba-publica@corestream-tests.com", "role": "DEVELOPER"},
        headers=admin_headers,
    )
    assert inv.status_code == 201
    res = await client.get(f"/api/invitations/{inv.json()['token']}")
    assert res.status_code == 200


async def test_invitacion_no_se_crea_para_email_ya_existente_en_otro_cliente(
    client, admin_headers, admin_b_headers
):
    """
    Sin el bypass (skip_tenant_scope)
    en create_invitation, un ADMIN de otro cliente no ve el email ya usado
    y la invitación se crea igual — fallando recién al aceptar, no al crear.
    """
    email = "compartido-entre-tenants@corestream-tests.com"

    inv_a = await client.post(
        "/api/invitations/", json={"email": email, "role": "DEVELOPER"}, headers=admin_headers
    )
    assert inv_a.status_code == 201
    accept_a = await client.post(
        f"/api/invitations/{inv_a.json()['token']}/accept",
        json={"full_name": "Usuario A", "password": "PasswordSegura123!"},
    )
    assert accept_a.status_code == 201

    inv_b = await client.post(
        "/api/invitations/", json={"email": email, "role": "DEVELOPER"}, headers=admin_b_headers
    )
    assert inv_b.status_code == 409, (
        "create_invitation debe rechazar el duplicado de inmediato, no dejar "
        "que la invitación se cree y falle recién en /accept."
    )


async def test_usuario_aceptado_hereda_el_cliente_del_admin_que_invito(client, admin_b_headers):
    """
    Lo confirmamos logueándolo y viendo que /auth/me responde con normalidad
    (si el client_id quedara mal seteado o nulo, el login/me fallaría).
    """
    inv = await client.post(
        "/api/invitations/",
        json={"email": "nuevo-en-b@corestream-tests.com", "role": "DEVELOPER"},
        headers=admin_b_headers,
    )
    assert inv.status_code == 201
    accept = await client.post(
        f"/api/invitations/{inv.json()['token']}/accept",
        json={"full_name": "Nuevo en B", "password": "PasswordSegura123!"},
    )
    assert accept.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": "nuevo-en-b@corestream-tests.com", "password": "PasswordSegura123!"},
    )
    assert login.status_code == 200
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert me.status_code == 200