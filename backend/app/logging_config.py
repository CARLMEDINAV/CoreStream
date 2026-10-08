"""
Logging estructurado para CoreStream (plan fase 8).

Antes: print() repartido por todo app/, y el manejador global de
excepciones (main.py) registraba con logging.error(...) sin exc_info — los
500 no dejaban traza. Los tres bugs de MissingGreenlet de la fase 2 solo
salieron a la luz porque uvicorn los imprime por su cuenta, no porque
nuestro propio logging los hubiera capturado.

Este módulo configura el logger raíz una sola vez, en el arranque de la
aplicación (main.py lifespan), con salida JSON (una línea por evento, fácil
de indexar si algún día hay un colector) e incluye el request_id de
middleware.request_id cuando existe.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.context import get_audit_bucket
from app.middleware.request_id import get_request_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id

        # Cualquier línea emitida dentro de una petición lleva quién la provocó,
        # no solo su request_id: un error sin actor obliga a cruzar a mano con
        # la tabla de auditoría para saber de quién era la petición.
        bucket = get_audit_bucket()
        if bucket:
            if bucket.get("client_id"):
                payload["client_id"] = str(bucket["client_id"])
            if bucket.get("actor_email"):
                payload["actor"] = bucket["actor_email"]
            if bucket.get("actor_role"):
                payload["actor_role"] = bucket["actor_role"]

        # Mismo evento, dos destinos (TRV-07): la entrada va a audit_logs para
        # ser consultable y exportable, y el evento completo sale aquí para que
        # un colector externo lo recoja sin tocar código.
        audit_event = getattr(record, "audit", None)
        if audit_event is not None:
            payload["audit"] = audit_event

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "info") -> None:
    """Reemplaza los handlers del logger raíz. Llamar una sola vez, al arrancar."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root.handlers.clear()
    root.addHandler(handler)

    # uvicorn.access ya imprime una línea por request en su propio formato;
    # dejarlo pasar por nuestro handler JSON en vez de duplicar salida.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    # httpx emite una línea INFO por petición saliente. Con el destino de
    # Elasticsearch activo eso es una línea extra POR CADA evento auditado,
    # justo al lado de la del propio evento: duplica el volumen de logs sin
    # añadir nada. Sus errores siguen apareciendo.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
