"""Contrato de la API de auditoría: filtros de entrada y forma de salida."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, get_args, get_origin
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict


@dataclass
class AuditFilters:
    """
    Criterios de búsqueda del visor de auditoría (NEW-14).

    Un solo objeto en vez de una lista de parámetros repetida en cada capa:
    lo reciben por igual la consulta paginada y la exportación, así que no
    pueden aceptar filtros distintos. Antes la exportación admitía solo el
    rango de fechas, y quien filtraba por usuario se llevaba el historial
    completo.

    El cliente y la retención del plan no están aquí a propósito: no son
    criterios que el usuario elija, son el límite de lo que puede ver.
    """

    actor_email: Annotated[str | None, Query(max_length=255)] = None
    actor_user_id: UUID | None = None
    resource_type: Annotated[str | None, Query(max_length=50)] = None
    resource_id: UUID | None = None
    outcome: Literal["SUCCESS", "DENIED", "FAILED", "ERROR"] | None = None
    method: Literal["POST", "PUT", "PATCH", "DELETE", "GET"] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _valores_admitidos(campo: str) -> tuple[str, ...]:
    """
    Valores que acepta un filtro, leídos de su propia declaración.

    Así el desplegable del visor no es una segunda lista que mantener: si se
    añade un resultado nuevo al filtro, la interfaz lo ofrece sin que nadie
    tenga que acordarse de tocar nada.
    """
    for parte in get_args(AuditFilters.__annotations__[campo]):
        if get_origin(parte) is Literal:
            return get_args(parte)
    return ()


OUTCOME_VALUES = _valores_admitidos("outcome")
METHOD_VALUES = _valores_admitidos("method")


class AuditActor(BaseModel):
    """
    Quien figura como autor de un evento.

    El id puede faltar: un intento de acceso con un correo que no existe deja
    el email del que lo intentó pero ningún usuario al que atribuirlo.
    """

    id: UUID | None = None
    email: str


class AuditFilterOptions(BaseModel):
    """
    Valores presentes en el historial, para poblar los filtros del visor.

    Se calculan sobre lo que el propio cliente puede consultar, así que el
    visor nunca ofrece una opción que no devolvería resultados.
    """

    resource_types: list[str]
    actors: list[AuditActor]
    actors_truncated: bool
    outcomes: list[str]
    methods: list[str]
    retention_days: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    request_id: str | None = None
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    method: str
    path: str
    route_template: str | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    status_code: int
    outcome: str
    ip: str | None = None
    user_agent: str | None = None
    duration_ms: int | None = None


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int
    retention_days: int
