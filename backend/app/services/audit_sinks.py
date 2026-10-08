"""
Destinos del registro de auditoría (criterio 2 de TRV-07).

El criterio pide que los eventos "se deriven a un motor especializado" y no
vivan en las tablas operativas. Aquí la derivación es una abstracción, no dos
llamadas cableadas en el middleware: el middleware depende de `AuditSink` y no
sabe cuántos destinos hay ni cuáles son.

Hoy hay dos: el esquema `audit` de PostgreSQL (consultable y exportable) y la
salida estándar en JSON (para que un colector la ingiera sin tocar código).
Añadir un tercero — ELK, CloudWatch, un fichero aparte — es escribir una clase
con `emit` y registrarla en `build_default_sink`; ningún otro módulo cambia.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol, Sequence, runtime_checkable

from app.database import get_session_maker
from app.models import AuditLog

logger = logging.getLogger("corestream.audit")

# Logger propio para que un colector pueda seleccionar la auditoría por nombre,
# sin filtrar por contenido el resto de los logs de la aplicación.
event_logger = logging.getLogger("corestream.audit.event")


@runtime_checkable
class AuditSink(Protocol):
    """Un destino al que se deriva cada evento auditable."""

    name: str

    async def emit(self, entry: Mapping[str, Any]) -> None: ...


class DatabaseSink:
    """
    Escribe la entrada en `audit.audit_logs`.

    Usa su propia sesión, independiente de la del request: la del request puede
    estar en estado fallido o con un rollback pendiente justo cuando más
    interesa dejar rastro (un 500, un 403), así que no puede compartirse.
    """

    name = "database"

    async def emit(self, entry: Mapping[str, Any]) -> None:
        async with get_session_maker()() as db:
            db.add(AuditLog(**entry))
            await db.commit()


class LogStreamSink:
    """
    Emite el evento completo como una línea JSON por el logger de auditoría.

    `JSONFormatter` reconoce la clave `audit` del `extra` y la incrusta en el
    payload (ver app/logging_config.py).
    """

    name = "logstream"

    def __init__(self, serializer=None) -> None:
        # Inyectable para no acoplar el sink al módulo de registros: el
        # serializador es una decisión de formato, no de destino.
        if serializer is None:
            from app.services.audit_records import as_log_payload

            serializer = as_log_payload
        self._serialize = serializer

    async def emit(self, entry: Mapping[str, Any]) -> None:
        event_logger.info(
            "audit %s %s -> %s",
            entry["method"], entry["path"], entry["status_code"],
            extra={"audit": self._serialize(entry)},
        )


class CompositeSink:
    """
    Reparte el evento entre varios destinos, aislando sus fallos.

    Un destino caído no debe impedir que los demás reciban el evento: si la
    base de datos no está disponible, la línea de log sigue siendo la única
    constancia que queda, y al revés. Por eso cada `emit` va en su propio
    try/except en vez de en una secuencia donde el primer fallo corta el resto.

    Tampoco propaga: dejar la API entera fuera de servicio porque la auditoría
    no está disponible no es un comportamiento exigido por TRV-07. El fallo sí
    queda registrado.
    """

    name = "composite"

    def __init__(self, sinks: Sequence[AuditSink]) -> None:
        self._sinks = tuple(sinks)

    @property
    def sinks(self) -> tuple[AuditSink, ...]:
        return self._sinks

    async def emit(self, entry: Mapping[str, Any]) -> None:
        for sink in self._sinks:
            try:
                await sink.emit(entry)
            except Exception:
                logger.exception(
                    "El destino de auditoría '%s' falló para %s %s",
                    sink.name, entry.get("method"), entry.get("path"),
                )


def _auth_header(*, api_key: str, username: str, password: str) -> dict[str, str]:
    """
    Cabecera de autenticación para Elasticsearch. La API key gana si se dan
    las dos: es la credencial de alcance limitado, y mezclar ambas en la misma
    petición es un error de configuración que conviene resolver de forma
    predecible en vez de dejar al azar del servidor.
    """
    if api_key:
        return {"Authorization": f"ApiKey {api_key}"}
    if username and password:
        credenciales = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {credenciales}"}
    return {}


class ElasticSink:
    """
    Envía el evento a Elasticsearch (la E de ELK), el motor que TRV-07 nombra.

    Índice con sufijo de fecha (`corestream-audit-2026.10.03`), que es lo que
    espera el ciclo de vida de índices de Elastic para aplicar su propia
    retención y archivado por días.

    El envío ocurre dentro de la petición, así que el timeout es corto y
    CompositeSink aísla el fallo: un Elasticsearch caído o lento no puede
    quedarse colgado del request ni impedir que la fila llegue a Postgres.
    Para tráfico alto, la ruta sin latencia en petición es el driver de logs
    de Docker sobre la salida de LogStreamSink — ver docs/DEPLOYMENT.md.
    """

    name = "elastic"

    def __init__(
        self,
        *,
        url: str,
        index: str,
        api_key: str = "",
        username: str = "",
        password: str = "",
        timeout_seconds: float = 2.0,
        serializer=None,
    ) -> None:
        if not url:
            raise ValueError("ElasticSink necesita una URL de Elasticsearch")
        self._url = url.rstrip("/")
        self._index = index
        self._timeout = timeout_seconds
        self._headers = {
            "Content-Type": "application/json",
            **_auth_header(api_key=api_key, username=username, password=password),
        }
        if serializer is None:
            from app.services.audit_records import as_log_payload

            serializer = as_log_payload
        self._serialize = serializer
        self._template_ready = False

    # Mapeo explícito, no el dinámico de Elasticsearch. Hacen falta dos cosas
    # de él:
    #
    #   CORRECCIÓN. Por defecto Elasticsearch mapea un UUID como `text`
    #   analizado, y el analizador estándar parte por los guiones: una
    #   consulta `terms` sobre client_id no coincide con nada, así que la
    #   purga de retención no borraba nada. Con `keyword` la coincidencia es
    #   exacta.
    #
    #   COSTE. Analizar UUID, IP, métodos y rutas genera un índice invertido
    #   de tokens que nunca se consulta. Con `keyword` se guarda el valor tal
    #   cual, y `dynamic: false` evita que un campo nuevo inesperado haga
    #   crecer el mapeo (sigue en _source, simplemente no se indexa).
    _TEMPLATE = {
        "index_patterns": [],  # se rellena con el índice configurado
        "template": {
            "settings": {
                "number_of_shards": 1,
                # Un solo nodo: una réplica no se podría asignar, dejaría el
                # índice en amarillo y duplicaría el disco sin dar nada.
                "number_of_replicas": 0,
            },
            "mappings": {
                "dynamic": False,
                "properties": {
                    "occurred_at": {"type": "date"},
                    "status_code": {"type": "integer"},
                    "duration_ms": {"type": "integer"},
                    **{
                        campo: {"type": "keyword", "ignore_above": 1024}
                        for campo in (
                            "client_id", "request_id", "actor_user_id",
                            "actor_email", "actor_role", "method", "path",
                            "route_template", "resource_type", "resource_id",
                            "outcome", "ip", "user_agent",
                        )
                    },
                },
            },
        },
    }

    async def _ensure_template(self, client) -> None:
        """
        Instala la plantilla una vez por proceso. Idempotente (PUT).

        Solo afecta a índices que se creen después, que es lo que interesa:
        los diarios nacen con el primer evento del día.
        """
        if self._template_ready:
            return
        cuerpo = dict(self._TEMPLATE)
        cuerpo["index_patterns"] = [f"{self._index}-*"]
        response = await client.put(
            f"{self._url}/_index_template/{self._index}",
            json=cuerpo,
            headers=self._headers,
        )
        response.raise_for_status()
        self._template_ready = True

    def _index_for(self, entry: Mapping[str, Any]) -> str:
        occurred = entry.get("occurred_at")
        fecha = occurred if isinstance(occurred, datetime) else datetime.now(timezone.utc)
        return f"{self._index}-{fecha:%Y.%m.%d}"

    async def emit(self, entry: Mapping[str, Any]) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            await self._ensure_template(client)
            response = await client.post(
                f"{self._url}/{self._index_for(entry)}/_doc",
                json=self._serialize(entry),
                headers=self._headers,
            )
            response.raise_for_status()

    async def purge(self, groups: Mapping[int, Sequence[Any]], now: datetime) -> int:
        """
        Aplica la retención de TRV-08 también aquí, por grupo de clientes.

        Un índice diario contiene los eventos de TODOS los tenants, así que
        soltarlo entero solo sería posible pasada la retención más larga — y
        eso conservaría los eventos de un cliente Basico los 730 días del plan
        Enterprise, incumpliendo la política. Por eso se borra por consulta,
        con los mismos grupos y cortes que la tabla.

        Timeout generoso: esto lo llama el cron nocturno, no una petición.
        """
        import httpx

        from app.plans import DEFAULT_RETENTION_DAYS, cutoff_for_days

        borrados = 0
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Si la plantilla no está, los índices existentes tienen client_id
            # analizado y las consultas de abajo no coincidirían: mejor que
            # falle y se vea en el log del cron que borrar cero en silencio.
            await self._ensure_template(client)

            for dias, client_ids in groups.items():
                if not client_ids:
                    continue
                borrados += await self._delete_by_query(
                    client,
                    {
                        "bool": {
                            "filter": [
                                {"terms": {"client_id": [str(c) for c in client_ids]}},
                                {"range": {"occurred_at": {
                                    "lt": cutoff_for_days(dias, now=now).isoformat()
                                }}},
                            ]
                        }
                    },
                )

            # Entradas sin cliente resuelto (login fallido contra un email
            # inexistente): no pertenecen a ningún tenant, así que caducan con
            # la retención más corta. Mismo criterio que en la tabla.
            borrados += await self._delete_by_query(
                client,
                {
                    "bool": {
                        "must_not": [{"exists": {"field": "client_id"}}],
                        "filter": [{"range": {"occurred_at": {
                            "lt": cutoff_for_days(
                                DEFAULT_RETENTION_DAYS, now=now
                            ).isoformat()
                        }}}],
                    }
                },
            )

        return borrados

    async def _delete_by_query(self, client, query: dict) -> int:
        # ignore_unavailable: el patrón no coincide con nada mientras no haya
        # llegado el primer evento, y eso no es un error.
        response = await client.post(
            f"{self._url}/{self._index}-*/_delete_by_query",
            params={"conflicts": "proceed", "ignore_unavailable": "true"},
            json={"query": query},
            headers=self._headers,
        )
        response.raise_for_status()
        return int(response.json().get("deleted", 0))


def _build_elastic_sink() -> AuditSink:
    from app.config import get_settings

    settings = get_settings()
    return ElasticSink(
        url=settings.ELASTIC_URL,
        index=settings.ELASTIC_INDEX,
        api_key=settings.ELASTIC_API_KEY,
        username=settings.ELASTIC_USERNAME,
        password=settings.ELASTIC_PASSWORD,
        timeout_seconds=settings.ELASTIC_TIMEOUT_SECONDS,
    )


# Registro de destinos: añadir uno es registrar su fábrica aquí y nombrarlo en
# AUDIT_SINKS. Ningún otro módulo cambia.
SINK_FACTORIES: dict[str, Callable[[], AuditSink]] = {
    "database": DatabaseSink,
    "logstream": LogStreamSink,
    "elastic": _build_elastic_sink,
}


def build_default_sink() -> AuditSink:
    """
    Construye los destinos que nombra AUDIT_SINKS.

    Un nombre desconocido aborta el arranque en vez de ignorarse: creer que
    los eventos van a un motor que nadie construyó es peor que no tenerlo.
    """
    from app.config import get_settings

    nombres = [s.strip() for s in get_settings().AUDIT_SINKS.split(",") if s.strip()]

    desconocidos = [n for n in nombres if n not in SINK_FACTORIES]
    if desconocidos:
        raise ValueError(
            f"Destinos de auditoría desconocidos en AUDIT_SINKS: {desconocidos}. "
            f"Válidos: {sorted(SINK_FACTORIES)}"
        )

    return CompositeSink([SINK_FACTORIES[n]() for n in nombres])


_default_sink: AuditSink | None = None


def get_audit_sink() -> AuditSink:
    """Instancia compartida, construida en el primer uso."""
    global _default_sink
    if _default_sink is None:
        _default_sink = build_default_sink()
    return _default_sink


def set_audit_sink(sink: AuditSink | None) -> None:
    """Sustituye los destinos. Para los tests; no se usa en producción."""
    global _default_sink
    _default_sink = sink
