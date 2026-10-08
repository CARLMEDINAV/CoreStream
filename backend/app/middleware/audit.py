"""
Middleware de auditoría de no repudio (TRV-07).

Decide si la petición es auditable, construye la entrada y la deriva. Los
destinos los resuelve `audit_service.record` a través de la abstracción de
`audit_sinks`: este módulo no sabe cuántos hay ni cuáles son.

No se auditan las lecturas con éxito. Un GET que devuelve 200 multiplicaría el
volumen del registro por el tráfico de navegación normal, y es justo lo que
vuelve impracticable la retención de TRV-08. Sí se audita CUALQUIER verbo que
acabe en 401/403/429: un intento de acceso denegado es lo más valioso que
guarda un log de auditoría.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.context import audit_ctx
from app.middleware.request_id import get_request_id
from app.services.audit_records import outcome_for
from app.services.audit_service import record

logger = logging.getLogger("corestream.audit")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DENIED_STATUS = frozenset({401, 403, 429})

# Sondas y métricas: las consulta el orquestador en bucle y no son actos de
# ningún usuario.
_SKIP_PATHS = frozenset({"/health", "/api/health", "/metrics"})

_SECURITY_PREFIX = "/api/auth/"

_MAX_PATH = 512
_MAX_USER_AGENT = 512


def _client_ip(request: Request) -> str | None:
    """
    request.client.host ya es la IP real del cliente: uvicorn corre con
    --forwarded-allow-ips (ver backend/Dockerfile) y resuelve X-Forwarded-For
    por su cuenta. Esa variable DEBE apuntar al proxy concreto — con el
    comodín, el propio cliente puede dictar esta cabecera y el campo deja de
    servir para no repudio. config.py aborta el arranque en producción si se
    queda en "*".
    """
    return request.client.host if request.client else None


def _resource_id_from_path(request: Request) -> UUID | None:
    for value in (request.scope.get("path_params") or {}).values():
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            continue
    return None


def _route_template(request: Request) -> str | None:
    route = request.scope.get("route")
    return getattr(route, "path", None)


def _should_record(
    method: str,
    status_code: int,
    path: str,
    forced: bool = False,
    audit_reads: bool = True,
) -> bool:
    """
    Con audit_reads (el valor por defecto) se registra toda petición que
    llegue a un handler: es la lectura estricta de "todo evento de la
    plataforma" que pide la descripción de TRV-07. Las sondas ya se han
    descartado antes de llegar aquí.

    Con audit_reads=False se registran solo las mutaciones, los accesos
    denegados en cualquier verbo y las rutas de autenticación — bastante más
    barato, porque entonces un GET con éxito no escribe nada.
    """
    if forced or audit_reads:
        return True
    if method in _MUTATING_METHODS:
        return True
    if status_code in _DENIED_STATUS:
        return True
    return path.startswith(_SECURITY_PREFIX)


def _build_entry(
    request: Request,
    bucket: dict,
    *,
    status_code: int,
    duration_ms: int,
) -> dict[str, Any]:
    """Los campos que exige el criterio 1 de TRV-07, en un solo sitio."""
    return {
        "client_id": bucket.get("client_id"),
        "request_id": get_request_id(),
        "actor_user_id": bucket.get("actor_user_id"),
        "actor_email": bucket.get("actor_email"),
        "actor_role": bucket.get("actor_role"),
        "method": request.method,
        "path": request.url.path[:_MAX_PATH],
        "route_template": _route_template(request),
        "resource_type": bucket.get("resource_type"),
        "resource_id": bucket.get("resource_id") or _resource_id_from_path(request),
        "status_code": status_code,
        "outcome": outcome_for(status_code),
        "ip": _client_ip(request),
        "user_agent": (request.headers.get("user-agent") or "")[:_MAX_USER_AGENT] or None,
        "duration_ms": duration_ms,
    }


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        bucket: dict = {}
        token = audit_ctx.set(bucket)
        started = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            # El reset va DESPUÉS de registrar, no antes: si un destino falla,
            # su traza debe salir con el actor y el cliente puestos — es justo
            # cuando hace falta saber de quién era el evento perdido.
            try:
                if _should_record(
                    request.method,
                    status_code,
                    request.url.path,
                    forced=bool(bucket.get("force")),
                    audit_reads=get_settings().AUDIT_READS,
                ):
                    await record(
                        _build_entry(
                            request,
                            bucket,
                            status_code=status_code,
                            duration_ms=int((time.perf_counter() - started) * 1000),
                        )
                    )
            except Exception:
                # La excepción saldría del finally de dispatch y se comería la
                # respuesta ya construida: un fallo de auditoría convertiría un
                # 201 en un 500. TRV-07 no exige que la API caiga cuando el
                # registro no está disponible; sí exige que el fallo se vea.
                logger.exception(
                    "Fallo al registrar la auditoría de %s %s",
                    request.method, request.url.path,
                )
            finally:
                audit_ctx.reset(token)
