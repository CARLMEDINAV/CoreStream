"""Pruebas unitarias de los webhooks salientes (NEW-12).

Cubren: validación de URL, firma HMAC, selección de webhooks por proyecto/tipo
de evento, aislamiento multi-tenant del payload y la tarea de entrega del
worker (éxito y fallo con reintento).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.context import current_client_id_ctx
from app.models import (
    Application,
    Client,
    TicketEventType,
    Webhook,
    WebhookDeliveryStatus,
)
from app.services import webhook_service
from app.services.webhook_service import compute_signature, validate_webhook_url

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.slack.com/services/T000/B000/XXXX",
        "http://jira.example.com/webhook",
        "https://8.8.8.8/hook",
    ],
)
def test_validate_webhook_url_accepts_public(url):
    assert validate_webhook_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/hook",
        "not-a-url",
        "http://localhost:8000/hook",
        "http://127.0.0.1/hook",
        "http://10.0.0.5/hook",
        "http://192.168.1.10/hook",
        "http://169.254.0.1/hook",
    ],
)
def test_validate_webhook_url_rejects_unsafe(url):
    with pytest.raises(ValueError):
        validate_webhook_url(url)


def test_compute_signature_is_stable_hmac():
    body = b'{"event":"TICKET_CREATED"}'
    first = compute_signature("s3cr3t", body)
    second = compute_signature("s3cr3t", body)
    assert first == second
    assert first.startswith("sha256=")
    assert first != compute_signature("otro", body)


async def _make_webhook(db, client, **kwargs) -> Webhook:
    webhook = Webhook(
        client_id=client.id,
        name=kwargs.pop("name", "hook"),
        url=kwargs.pop("url", "https://example.com/hook"),
        event_types=kwargs.pop("event_types", []),
        **kwargs,
    )
    db.add(webhook)
    await db.flush()
    return webhook


# ---------------------------------------------------------------------------
# Selección de webhooks
# ---------------------------------------------------------------------------

async def test_event_matches_project_and_event_type(
    db_session, sample_client, sample_ticket, sample_user, sample_app
):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        # Aplica a todos los proyectos, sólo TICKET_ASSIGNED
        hook_by_event = await _make_webhook(
            db_session, sample_client,
            name="solo asignaciones", event_types=["TICKET_ASSIGNED"],
        )
        # Aplica a este proyecto, todos los eventos
        hook_by_project = await _make_webhook(
            db_session, sample_client,
            name="proyecto", project_id=sample_app.id,
        )
        # Proyecto distinto → no debe aplicar
        other_app = Application(name="Otra app", client_id=sample_client.id)
        db_session.add(other_app)
        await db_session.flush()
        await _make_webhook(
            db_session, sample_client,
            name="otro proyecto", project_id=other_app.id,
        )

        deliveries = await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.TICKET_ASSIGNED,
            actor_id=sample_user.id,
            detail={"from_user_id": None, "to_user_id": str(sample_user.id)},
        )
        names = {d.webhook_id for d in deliveries}
        assert len(deliveries) == 2
        assert hook_by_event.id in names
        assert hook_by_project.id in names
        assert all(d.status is WebhookDeliveryStatus.PENDING for d in deliveries)
    finally:
        current_client_id_ctx.reset(token)


async def test_ignores_non_key_events(db_session, sample_client, sample_ticket):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        await _make_webhook(db_session, sample_client, name="todo", event_types=[])
        deliveries = await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.TIMER_SYNC,
            detail={},
        )
        assert deliveries == []
    finally:
        current_client_id_ctx.reset(token)


async def test_event_type_filter_excludes_unsubscribed(db_session, sample_client, sample_ticket):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        await _make_webhook(
            db_session, sample_client, name="solo completados", event_types=["TICKET_COMPLETED"]
        )
        deliveries = await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.STATUS_CHANGED,
            detail={"from_status": "TODO", "to_status": "IN_PROGRESS"},
        )
        assert deliveries == []
    finally:
        current_client_id_ctx.reset(token)


async def test_payload_does_not_leak_other_tenant(db_session, sample_client, sample_ticket):
    """Un webhook de otro cliente nunca recibe la entrega ni sus datos."""
    other_client = Client(name="Otro", slug="otro-cliente", is_active=True)
    db_session.add(other_client)
    await db_session.flush()

    own_hook = await _make_webhook(db_session, sample_client, name="propio", event_types=[])
    other_hook = await _make_webhook(db_session, other_client, name="ajeno", event_types=[])

    token = current_client_id_ctx.set(sample_client.id)
    try:
        deliveries = await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.CREATED,
            detail={"message": "creado"},
        )
    finally:
        current_client_id_ctx.reset(token)

    assert [d.webhook_id for d in deliveries] == [own_hook.id]
    assert other_hook.id not in {d.webhook_id for d in deliveries}

    payload = deliveries[0].payload
    assert payload["event"] == "TICKET_CREATED"
    assert payload["ticket"]["id"] == str(sample_ticket.id)
    # Ninguna referencia al otro tenant
    assert str(other_client.id) not in str(payload)
    assert str(other_hook.id) not in str(payload)


# ---------------------------------------------------------------------------
# Encolado post-commit
# ---------------------------------------------------------------------------

class _FakePool:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, **kwargs):
        self.jobs.append((name, kwargs))


async def test_flush_enqueues_deliveries(db_session, sample_client, sample_ticket, monkeypatch):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        await _make_webhook(
            db_session, sample_client, name="hook", secret="firma", event_types=[]
        )
        deliveries = await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.CREATED,
            detail={"message": "creado"},
        )
        assert len(deliveries) == 1

        # El job sólo puede encolarse tras el commit (ids válidos)
        await db_session.commit()

        pool = _FakePool()
        monkeypatch.setattr(webhook_service, "get_arq_pool", lambda: pool)
        await webhook_service.flush_pending_webhook_deliveries(db_session)

        assert len(pool.jobs) == 1
        name, kwargs = pool.jobs[0]
        assert name == "deliver_webhook"
        assert kwargs["delivery_id"] == str(deliveries[0].id)
        assert kwargs["secret"] == "firma"
        assert kwargs["url"] == "https://example.com/hook"
    finally:
        current_client_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# Tarea de entrega del worker
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _fake_client_factory(status_code, raise_exc=None):
    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, content=None, headers=None):
            if raise_exc is not None:
                raise raise_exc
            return _FakeResponse(status_code)

    return _FakeAsyncClient


async def _capture_updates(monkeypatch):
    calls = []

    async def _fake_update(delivery_id, *, status, attempt, response_status=None, error=None):
        calls.append(
            {
                "delivery_id": delivery_id,
                "status": status,
                "attempt": attempt,
                "response_status": response_status,
                "error": error,
            }
        )

    from app.worker import tasks as worker_tasks

    monkeypatch.setattr(worker_tasks, "_update_delivery", _fake_update)
    return worker_tasks, calls


async def test_deliver_webhook_success(monkeypatch):
    worker_tasks, calls = await _capture_updates(monkeypatch)
    monkeypatch.setattr(worker_tasks.httpx, "AsyncClient", _fake_client_factory(204))

    await worker_tasks.deliver_webhook(
        {"job_try": 1},
        delivery_id=str(uuid4()),
        url="https://example.com/hook",
        secret=None,
        payload={"event": "PING"},
        event_type="PING",
    )

    assert len(calls) == 1
    assert calls[0]["status"] == "SUCCESS"
    assert calls[0]["response_status"] == 204


async def test_deliver_webhook_failure_raises_for_retry(monkeypatch):
    worker_tasks, calls = await _capture_updates(monkeypatch)
    monkeypatch.setattr(worker_tasks.httpx, "AsyncClient", _fake_client_factory(503))

    with pytest.raises(RuntimeError):
        await worker_tasks.deliver_webhook(
            {"job_try": 1},
            delivery_id=str(uuid4()),
            url="https://example.com/hook",
            secret="s",
            payload={"event": "PING"},
            event_type="PING",
        )

    assert calls and calls[0]["status"] == "FAILED"
    assert calls[0]["response_status"] == 503


# ---------------------------------------------------------------------------
# Formato Slack (NEW-12+)
# ---------------------------------------------------------------------------

def test_build_slack_payload_includes_ticket_details():
    payload = {
        "event": "STATUS_CHANGED",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "project": {"id": "p1", "name": "Web"},
        "ticket": {
            "id": "t1",
            "title": "Arreglar login",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
        },
        "actor": {"id": "u1", "name": "Ana"},
        "data": {"from_status": "TODO", "to_status": "IN_PROGRESS"},
    }
    message = webhook_service.build_slack_payload(payload)
    assert set(message) == {"text"}
    text = message["text"]
    assert "Cambio de estado" in text
    assert "Arreglar login" in text
    assert "estado: IN_PROGRESS" in text
    assert "prioridad: HIGH" in text
    assert "Proyecto: Web" in text
    assert "Autor: Ana" in text
    assert "t1" in text


def test_build_slack_payload_handles_ping_without_ticket():
    message = webhook_service.build_slack_payload({"event": "PING"})
    assert set(message) == {"text"}
    assert "PING" in message["text"]


def _capturing_client_factory(status_code, sink):
    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, content=None, headers=None):
            sink["url"] = url
            sink["content"] = content
            sink["headers"] = headers or {}
            return _FakeResponse(status_code)

    return _FakeAsyncClient


async def test_deliver_webhook_slack_format_sends_text_body(monkeypatch):
    import json as _json

    worker_tasks, calls = await _capture_updates(monkeypatch)
    sink: dict = {}
    monkeypatch.setattr(worker_tasks.httpx, "AsyncClient", _capturing_client_factory(200, sink))

    payload = {
        "event": "TICKET_CREATED",
        "ticket": {"id": "t1", "title": "Nuevo", "status": "TODO", "priority": "LOW"},
    }
    await worker_tasks.deliver_webhook(
        {"job_try": 1},
        delivery_id=str(uuid4()),
        url="https://hooks.slack.com/services/T/B/X",
        secret="s",
        payload=payload,
        event_type="TICKET_CREATED",
        payload_format="SLACK",
    )

    sent = _json.loads(sink["content"].decode("utf-8"))
    assert set(sent) == {"text"}
    assert "Nuevo" in sent["text"]
    # La firma cubre el cuerpo REAL enviado (el de Slack), no el JSON propio.
    assert sink["headers"]["X-CoreStream-Signature"] == compute_signature("s", sink["content"])
    assert calls[0]["status"] == "SUCCESS"


async def test_deliver_webhook_json_is_sent_unchanged(monkeypatch):
    import json as _json

    worker_tasks, _ = await _capture_updates(monkeypatch)
    sink: dict = {}
    monkeypatch.setattr(worker_tasks.httpx, "AsyncClient", _capturing_client_factory(200, sink))

    payload = {"event": "TICKET_CREATED", "ticket": {"id": "t1"}}
    await worker_tasks.deliver_webhook(
        {"job_try": 1},
        delivery_id=str(uuid4()),
        url="https://example.com/hook",
        secret=None,
        payload=payload,
        event_type="TICKET_CREATED",
    )

    assert _json.loads(sink["content"].decode("utf-8")) == payload


async def test_flush_passes_payload_format(db_session, sample_client, sample_ticket, monkeypatch):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        await _make_webhook(
            db_session, sample_client, name="slack", format="SLACK", event_types=[]
        )
        await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.CREATED,
            detail={},
        )
        await db_session.commit()

        pool = _FakePool()
        monkeypatch.setattr(webhook_service, "get_arq_pool", lambda: pool)
        await webhook_service.flush_pending_webhook_deliveries(db_session)

        assert len(pool.jobs) == 1
        assert pool.jobs[0][1]["payload_format"] == "SLACK"
    finally:
        current_client_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# Plantilla de mensaje (NEW-12+)
# ---------------------------------------------------------------------------

def _full_payload() -> dict:
    return {
        "event": "STATUS_CHANGED",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "project": {"id": "p1", "name": "Web"},
        "ticket": {
            "id": "t1",
            "title": "Arreglar login",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
        },
        "actor": {"id": "u1", "name": "Ana"},
        "data": {"from_status": "TODO", "to_status": "IN_PROGRESS"},
    }


def test_render_template_replaces_variables():
    text = webhook_service.render_template(
        "{evento}: {ticket} ({estado}, {prioridad}) en {proyecto} por {autor}",
        _full_payload(),
    )
    assert text == "Cambio de estado: Arreglar login (IN_PROGRESS, HIGH) en Web por Ana"


def test_render_template_keeps_unknown_placeholders():
    text = webhook_service.render_template("Hola {desconocido} {ticket}", _full_payload())
    assert text == "Hola {desconocido} Arreglar login"


def test_render_template_does_not_raise_on_stray_braces():
    # A diferencia de str.format, una llave suelta no debe lanzar excepción.
    assert webhook_service.render_template("50% {", _full_payload()) == "50% {"


def test_build_slack_payload_uses_template_when_present():
    message = webhook_service.build_slack_payload(
        _full_payload(), "{ticket} → {estado}"
    )
    assert message == {"text": "Arreglar login → IN_PROGRESS"}


def test_build_slack_payload_falls_back_to_default_on_blank_template():
    message = webhook_service.build_slack_payload(_full_payload(), "   ")
    assert "Cambio de estado" in message["text"]
    assert "Arreglar login" in message["text"]


async def test_deliver_webhook_slack_uses_template(monkeypatch):
    import json as _json

    worker_tasks, _ = await _capture_updates(monkeypatch)
    sink: dict = {}
    monkeypatch.setattr(worker_tasks.httpx, "AsyncClient", _capturing_client_factory(200, sink))

    await worker_tasks.deliver_webhook(
        {"job_try": 1},
        delivery_id=str(uuid4()),
        url="https://hooks.slack.com/services/T/B/X",
        secret=None,
        payload=_full_payload(),
        event_type="STATUS_CHANGED",
        payload_format="SLACK",
        message_template="Ticket {ticket}: {estado}",
    )

    assert _json.loads(sink["content"].decode("utf-8")) == {
        "text": "Ticket Arreglar login: IN_PROGRESS"
    }


async def test_flush_passes_message_template(db_session, sample_client, sample_ticket, monkeypatch):
    token = current_client_id_ctx.set(sample_client.id)
    try:
        await _make_webhook(
            db_session,
            sample_client,
            name="slack-plantilla",
            format="SLACK",
            message_template="Evento {evento}",
            event_types=[],
        )
        await webhook_service.record_ticket_event(
            db_session,
            ticket_id=sample_ticket.id,
            event_type=TicketEventType.CREATED,
            detail={},
        )
        await db_session.commit()

        pool = _FakePool()
        monkeypatch.setattr(webhook_service, "get_arq_pool", lambda: pool)
        await webhook_service.flush_pending_webhook_deliveries(db_session)

        assert len(pool.jobs) == 1
        assert pool.jobs[0][1]["message_template"] == "Evento {evento}"
    finally:
        current_client_id_ctx.reset(token)
