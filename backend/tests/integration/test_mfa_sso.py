"""
NEW-08 — 2FA por TOTP y login SSO, contra Postgres y Redis reales.

El reloj del TOTP se controla con la fixture `clock`: la protección contra
reuso (un código vale una sola vez) impide pedir dos veces el mismo código en
el mismo paso de 30 s, así que cada paso de la prueba avanza el reloj.

El proveedor SSO se simula (no hay red): se sustituyen get_providers() y
finish(). La validación real del id_token está en test_sso_id_token (pura).
"""

import time
import uuid

import psycopg2
import pyotp
import pytest

from app.services import mfa_service, sso_service

from .conftest import ADMIN, ADMIN_B, DEV, DEV2, TEST_DATABASE_URL, _login, _sync_url

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.t = time.time()

    def code(self, secret: str, offset: int = 0) -> str:
        return pyotp.TOTP(secret).at(int(self.t // 30) * 30 + offset * 30)

    def advance(self, steps: int = 1) -> None:
        self.t += 30 * steps


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(mfa_service, "_now", lambda: c.t)
    return c


def _sql(query: str, params: tuple = ()):
    conn = psycopg2.connect(_sync_url(TEST_DATABASE_URL))
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall() if cur.description else None
    finally:
        conn.close()


def _uid(user: dict) -> str:
    """Mismo id determinístico con el que conftest siembra a cada usuario."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"corestream-test-user:{user['email']}"))


@pytest.fixture(autouse=True)
def _reset_mfa_state():
    """
    Deja el 2FA como estaba al terminar cada test.

    Las fixtures de sesión del proyecto (admin_headers, dev_headers...) se crean
    la primera vez que alguien las pide, ANTES de que se limpie la base para ese
    test: si este archivo dejara a un usuario con 2FA o la política activa, el
    login de esas fixtures devolvería "falta el código" y se quedarían con un
    token inválido. Por eso estos tests usan _login() propio y además limpian.
    """
    yield
    _sql("UPDATE users SET totp_enabled=false, totp_secret_encrypted=NULL, "
         "totp_enabled_at=NULL, totp_last_used_step=NULL")
    _sql("UPDATE clients SET require_2fa=false")
    _sql("DELETE FROM user_recovery_codes")
    _sql("DELETE FROM user_identities")


async def _enroll(client, user, clock) -> tuple[str, list[str]]:
    """Activa el 2FA del usuario. Devuelve (secreto, códigos de recuperación)."""
    headers = await _login(client, user)
    res = await client.post("/api/auth/mfa/setup", headers=headers)
    assert res.status_code == 200, res.text
    secret = res.json()["secret"]
    res = await client.post(
        "/api/auth/mfa/confirm", headers=headers, json={"code": clock.code(secret)}
    )
    assert res.status_code == 200, res.text
    codes = res.json()["recovery_codes"]
    assert len(codes) == 10
    clock.advance()  # el código de confirmación ya está gastado
    return secret, codes


async def _login_challenge(client, user) -> str:
    client.cookies.clear()
    res = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mfa_required"] is True
    assert body["access_token"] is None
    assert not client.cookies.get("refresh_token")
    return body["mfa_token"]


# ---------------------------------------------------------------------------
# TOTP
# ---------------------------------------------------------------------------

async def test_login_sin_2fa_no_cambia(client):
    client.cookies.clear()
    res = await client.post("/api/auth/login", json={"email": DEV["email"], "password": DEV["password"]})
    body = res.json()
    assert body["access_token"] and body["mfa_required"] is False
    assert client.cookies.get("refresh_token")


async def test_login_con_2fa_en_dos_pasos(client, clock):
    secret, _ = await _enroll(client, DEV, clock)
    mfa_token = await _login_challenge(client, DEV)

    res = await client.post(
        "/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": clock.code(secret)}
    )
    assert res.status_code == 200, res.text
    assert client.cookies.get("refresh_token") and client.cookies.get("csrf_token")
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}
    )
    assert me.status_code == 200 and me.json()["email"] == DEV["email"]


async def test_codigo_incorrecto_no_abre_sesion(client, clock):
    secret, _ = await _enroll(client, DEV, clock)
    mfa_token = await _login_challenge(client, DEV)
    wrong = "000000" if clock.code(secret) != "000000" else "111111"
    res = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": wrong})
    assert res.status_code == 401
    assert not client.cookies.get("refresh_token")


async def test_un_codigo_usado_no_vale_dos_veces(client, clock):
    secret, _ = await _enroll(client, DEV, clock)

    mfa_token = await _login_challenge(client, DEV)
    code = clock.code(secret)
    assert (await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": code})).status_code == 200

    # Mismo paso de 30 s, otro desafío: el código ya está gastado.
    mfa_token = await _login_challenge(client, DEV)
    assert (await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": code})).status_code == 401

    clock.advance()
    assert (
        await client.post(
            "/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": clock.code(secret)}
        )
    ).status_code == 200


async def test_el_desafio_es_de_un_solo_uso(client, clock):
    secret, _ = await _enroll(client, DEV, clock)
    mfa_token = await _login_challenge(client, DEV)
    assert (await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": clock.code(secret)})).status_code == 200
    clock.advance()
    again = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": clock.code(secret)})
    assert again.status_code == 401


async def test_el_token_de_desafio_no_sirve_como_access_token(client, clock):
    await _enroll(client, DEV, clock)
    mfa_token = await _login_challenge(client, DEV)
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert res.status_code == 401


async def test_fuerza_bruta_contra_el_codigo_se_frena(client, clock):
    await _enroll(client, DEV, clock)
    mfa_token = await _login_challenge(client, DEV)
    statuses = []
    for _ in range(6):
        res = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
        statuses.append(res.status_code)
    assert statuses[:5] == [401] * 5 and statuses[5] == 429


async def test_codigo_de_recuperacion_sirve_una_sola_vez(client, clock):
    _, codes = await _enroll(client, DEV, clock)

    mfa_token = await _login_challenge(client, DEV)
    ok = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": codes[0].lower()})
    assert ok.status_code == 200

    mfa_token = await _login_challenge(client, DEV)
    bad = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": codes[0]})
    assert bad.status_code == 401
    other = await client.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": codes[1]})
    assert other.status_code == 200


async def test_el_secreto_se_guarda_cifrado(client, clock):
    secret, codes = await _enroll(client, DEV, clock)
    (stored,) = _sql("SELECT totp_secret_encrypted FROM users WHERE email=%s", (DEV["email"],))[0]
    assert stored and secret not in stored
    hashes = [h for (h,) in _sql("SELECT code_hash FROM user_recovery_codes")]
    assert len(hashes) == 10
    assert not any(c.replace("-", "") in h for c in codes for h in hashes)


async def test_confirmar_con_codigo_incorrecto_no_activa(client, clock):
    headers = await _login(client, DEV)
    await client.post("/api/auth/mfa/setup", headers=headers)
    res = await client.post("/api/auth/mfa/confirm", headers=headers, json={"code": "000000"})
    assert res.status_code == 400
    assert _sql("SELECT totp_enabled FROM users WHERE email=%s", (DEV["email"],))[0][0] is False


async def test_desactivar_exige_password_y_codigo(client, clock):
    headers = await _login(client, DEV)  # antes de enrolar: después el login pediría el segundo factor
    secret, _ = await _enroll(client, DEV, clock)

    bad_pw = await client.post(
        "/api/auth/mfa/disable", headers=headers, json={"password": "nope", "code": clock.code(secret)}
    )
    assert bad_pw.status_code == 400

    ok = await client.post(
        "/api/auth/mfa/disable",
        headers=headers,
        json={"password": DEV["password"], "code": clock.code(secret)},
    )
    assert ok.status_code == 204
    client.cookies.clear()
    res = await client.post("/api/auth/login", json={"email": DEV["email"], "password": DEV["password"]})
    assert res.json()["access_token"]


# ---------------------------------------------------------------------------
# Política por cliente y administración
# ---------------------------------------------------------------------------

async def test_politica_obligatoria_fuerza_el_enrolamiento(client, clock):
    admin_headers = await _login(client, ADMIN)
    # El ADMIN no puede exigir 2FA sin tenerlo él mismo (se dejaría fuera).
    res = await client.put("/api/auth/mfa/policy", headers=admin_headers, json={"require_2fa": True})
    assert res.status_code == 400

    await _enroll(client, ADMIN, clock)  # admin_headers sigue valiendo: el access token ya emitido no cambia
    res = await client.put("/api/auth/mfa/policy", headers=admin_headers, json={"require_2fa": True})
    assert res.status_code == 200 and res.json() == {"require_2fa": True}

    # Un DEV sin 2FA ya no recibe sesión: solo un token para enrolarse.
    client.cookies.clear()
    res = await client.post("/api/auth/login", json={"email": DEV["email"], "password": DEV["password"]})
    body = res.json()
    assert body["mfa_setup_required"] is True and body["access_token"] is None
    assert not client.cookies.get("refresh_token")
    setup_headers = {"Authorization": f"Bearer {body['mfa_token']}"}

    # Ese token no abre nada más…
    assert (await client.get("/api/auth/me", headers=setup_headers)).status_code == 401
    # …salvo el enrolamiento, que además abre la sesión al confirmar.
    secret = (await client.post("/api/auth/mfa/setup", headers=setup_headers)).json()["secret"]
    res = await client.post("/api/auth/mfa/confirm", headers=setup_headers, json={"code": clock.code(secret)})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"] and len(res.json()["recovery_codes"]) == 10
    assert client.cookies.get("refresh_token")

    # Con la política activa, ni siquiera el propio usuario puede quitárselo.
    clock.advance()
    dev_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    res = await client.post(
        "/api/auth/mfa/disable",
        headers=dev_headers,
        json={"password": DEV["password"], "code": clock.code(secret)},
    )
    assert res.status_code == 403


async def test_solo_admin_cambia_la_politica(client):
    dev_headers = await _login(client, DEV)
    res = await client.put("/api/auth/mfa/policy", headers=dev_headers, json={"require_2fa": True})
    assert res.status_code == 403


async def test_admin_resetea_el_2fa_de_un_usuario_de_su_cliente(client, clock):
    dev_id = _uid(DEV)
    await _enroll(client, DEV, clock)
    admin_headers = await _login(client, ADMIN)
    res = await client.delete(f"/api/auth/mfa/users/{dev_id}", headers=admin_headers)
    assert res.status_code == 204

    client.cookies.clear()
    res = await client.post("/api/auth/login", json={"email": DEV["email"], "password": DEV["password"]})
    assert res.json()["access_token"]
    assert _sql("SELECT count(*) FROM user_recovery_codes")[0][0] == 0


async def test_admin_de_otro_cliente_no_puede_resetear(client, clock):
    dev_id = _uid(DEV)
    await _enroll(client, DEV, clock)
    admin_b_headers = await _login(client, ADMIN_B)
    res = await client.delete(f"/api/auth/mfa/users/{dev_id}", headers=admin_b_headers)
    assert res.status_code == 404
    assert _sql("SELECT totp_enabled FROM users WHERE email=%s", (DEV["email"],))[0][0] is True


async def test_un_developer_no_puede_resetear_el_2fa_de_otro(client):
    dev_headers = await _login(client, DEV)
    res = await client.delete(f"/api/auth/mfa/users/{_uid(DEV2)}", headers=dev_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# SSO
# ---------------------------------------------------------------------------

FAKE = sso_service.ProviderConfig(
    id="google", name="Google", client_id="cid", client_secret="sec",
    authorize_url="https://idp.example/auth", token_url="https://idp.example/token",
    jwks_url="https://idp.example/jwks",
)


@pytest.fixture
def sso(monkeypatch):
    """Proveedor 'google' configurado y un id_token controlado por el test."""
    state = {"identity": None}
    monkeypatch.setattr(sso_service, "get_providers", lambda: {"google": FAKE})

    async def fake_finish(cfg, code, st):
        if state["identity"] is None:
            raise sso_service.SsoError("state_invalid")
        return state["identity"]

    monkeypatch.setattr(sso_service, "finish", fake_finish)
    return state


def _ident(email, sub="g-sub-1", trusted=True):
    return sso_service.SsoIdentity("google", sub, email, trusted)


async def _callback(client):
    client.cookies.clear()
    return await client.get("/api/auth/sso/google/callback", params={"code": "c", "state": "s"})


async def test_sso_sin_proveedores_configurados(client):
    res = await client.get("/api/auth/sso/providers")
    assert res.status_code == 200 and res.json() == {"providers": []}
    assert (await client.get("/api/auth/sso/google/login")).status_code == 404


async def test_sso_lista_y_redirige_al_proveedor(client, sso):
    assert (await client.get("/api/auth/sso/providers")).json()["providers"] == [
        {"id": "google", "name": "Google"}
    ]
    res = await client.get("/api/auth/sso/google/login")
    assert res.status_code == 302
    loc = res.headers["location"]
    assert loc.startswith("https://idp.example/auth?")
    for needle in ("code_challenge_method=S256", "state=", "nonce=", "client_id=cid"):
        assert needle in loc


async def test_sso_con_state_inexistente_es_rechazado(client, monkeypatch):
    monkeypatch.setattr(sso_service, "get_providers", lambda: {"google": FAKE})
    res = await client.get("/api/auth/sso/google/callback", params={"code": "c", "state": "inventado"})
    assert res.status_code == 403 and "sso_error=state_invalid" in res.text


async def test_sso_usuario_existente_entra_y_queda_enlazado(client, sso):
    sso["identity"] = _ident(DEV["email"])
    res = await _callback(client)
    assert res.status_code == 303 and "sso=success" in res.headers["location"]
    assert client.cookies.get("refresh_token")

    refreshed = await client.post(
        "/api/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("csrf_token")}
    )
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]
    assert _sql("SELECT provider, subject FROM user_identities") == [("google", "g-sub-1")]


async def test_sso_no_crea_usuarios(client, sso):
    sso["identity"] = _ident("desconocido@corestream-tests.com")
    res = await _callback(client)
    assert res.status_code == 403 and "sso_error=no_account" in res.text
    assert not client.cookies.get("refresh_token")
    assert _sql("SELECT count(*) FROM users WHERE email=%s", ("desconocido@corestream-tests.com",))[0][0] == 0


async def test_sso_con_correo_no_verificado_no_enlaza(client, sso):
    sso["identity"] = _ident(DEV["email"], trusted=False)
    res = await _callback(client)
    assert res.status_code == 403
    assert _sql("SELECT count(*) FROM user_identities")[0][0] == 0


async def test_sso_reconoce_por_subject_aunque_cambie_el_correo(client, sso):
    sso["identity"] = _ident(DEV["email"])
    assert (await _callback(client)).status_code == 303
    sso["identity"] = _ident("otro-correo@corestream-tests.com", trusted=False)
    assert (await _callback(client)).status_code == 303


async def test_sso_no_deja_entrar_a_un_usuario_desactivado(client, sso):
    _sql("UPDATE users SET is_active=false WHERE email=%s", (DEV["email"],))
    sso["identity"] = _ident(DEV["email"])
    res = await _callback(client)
    assert res.status_code == 403 and "sso_error=inactive" in res.text


async def test_sso_no_exige_totp_adicional(client, sso, clock):
    await _enroll(client, DEV, clock)
    sso["identity"] = _ident(DEV["email"])
    res = await _callback(client)
    assert res.status_code == 303 and client.cookies.get("refresh_token")


async def test_sso_una_cuenta_externa_no_puede_tomar_una_ya_enlazada(client, sso):
    sso["identity"] = _ident(DEV["email"], sub="g-sub-1")
    assert (await _callback(client)).status_code == 303
    sso["identity"] = _ident(DEV["email"], sub="g-sub-ATACANTE")
    assert (await _callback(client)).status_code == 403
