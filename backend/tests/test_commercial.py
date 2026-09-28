"""prueba el control comercial por http con una base de datos en memoria."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.middleware.commercial import get_commercial_profile, require_feature
from app.models import Client


@pytest.fixture
async def commercial_api(db_session, sample_user):
    async def db_override():
        yield db_session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: sample_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        yield api
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path,method", [
    ("/api/analytics/support-summary", "get"),
    (f"/api/analytics/summary/{uuid4()}", "get"),
    (f"/api/documents/{uuid4()}/translate", "post"),
    (f"/api/documents/{uuid4()}/translate/download", "post"),
])
async def test_basico_denies_premium_even_for_admin(commercial_api, path, method):
    kwargs = {"json": {"target_language": "en"}} if method == "post" else {}
    response = await getattr(commercial_api, method)(path, **kwargs)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FEATURE_NOT_INCLUDED"


async def test_plan_changes_apply_on_next_request(commercial_api, db_session, sample_client):
    url = "/api/analytics/support-summary"
    assert (await commercial_api.get(url)).status_code == 403
    sample_client.commercial_plan = "Pro"
    await db_session.commit()
    assert (await commercial_api.get(url)).status_code == 200
    sample_client.commercial_plan = "Basico"
    await db_session.commit()
    assert (await commercial_api.get(url)).status_code == 403


async def test_profile_is_only_for_authenticated_tenant(commercial_api, db_session, sample_client):
    other = Client(name="Other", slug="other", commercial_plan="Pro")
    db_session.add(other)
    await db_session.commit()
    response = await commercial_api.get(f"/api/auth/commercial-profile?client_id={other.id}&plan=Pro")
    assert response.status_code == 200
    profile = response.json()
    assert profile["client_id"] == str(sample_client.id)
    assert profile["plan"] == "Basico"
    assert profile["feature_flags"]["tickets"] is True
    assert profile["feature_flags"]["analytics"] is False
    assert (await commercial_api.put("/api/auth/commercial-profile", json={"plan": "Pro"})).status_code == 405


@pytest.mark.parametrize("plan,active", [("Unknown", True), ("Pro", False)])
async def test_invalid_or_inactive_profile_denies(commercial_api, db_session, sample_client, plan, active):
    sample_client.commercial_plan = plan
    sample_client.is_active = active
    await db_session.commit()
    assert (await commercial_api.get("/api/analytics/support-summary")).status_code == 403
    profile = (await commercial_api.get("/api/auth/commercial-profile")).json()
    assert not any(profile["feature_flags"].values())


async def test_missing_profile_denies(db_session):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await get_commercial_profile(SimpleNamespace(client_id=uuid4()), db_session)
    assert error.value.status_code == 403


async def test_profile_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        assert (await api.get("/api/auth/commercial-profile")).status_code == 401


def test_unknown_flag_is_configuration_error():
    with pytest.raises(ValueError):
        require_feature("typo")


async def test_pro_reaches_both_translation_handlers(commercial_api, db_session, sample_client):
    sample_client.commercial_plan = "Pro"
    await db_session.commit()
    for suffix in ("translate", "translate/download"):
        response = await commercial_api.post(
            f"/api/documents/{uuid4()}/{suffix}", json={"target_language": "en"}
        )
        assert response.status_code == 404  # llega al handler: documento inexistente


async def test_pro_does_not_override_rbac(commercial_api, db_session, sample_client, sample_user):
    sample_client.commercial_plan = "Pro"
    await db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        client_id=sample_user.client_id, role=SimpleNamespace(name="DEVELOPER")
    )
    response = await commercial_api.get(f"/api/analytics/export/csv/{uuid4()}")
    assert response.status_code == 403
    assert isinstance(response.json()["detail"], str)


def test_migration_backfills_existing_clients_and_downgrades():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    path = Path(__file__).parents[1] / "alembic/versions/7e9ab80b3e68_add_commercial_plan.py"
    spec = importlib.util.spec_from_file_location("commercial_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE clients (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO clients (id) VALUES (1)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.scalar(text("SELECT commercial_plan FROM clients")) == "Basico"
            migration.downgrade()
            assert connection.scalar(text("SELECT id FROM clients")) == 1
    engine.dispose()
