# WEB-15: Panel de estadísticas de incidencias

El sistema expone estadísticas agregadas de incidencias para alimentar los
paneles de administración y liderazgo, mediante un único endpoint.

Roles con acceso: **ADMIN** y **TEAM_LEADER** (`TEAM_LEADER` es el rol real en
la base de datos; `GROUP_LEADER` fue un nombre histórico que nunca existió como
rol, ver `docs/RBAC.md`).

---

## Backend

`app/routers/incidents.py` incorpora:

| Operación | Endpoint | Descripción |
| --------- | -------- | ----------- |
| Estadísticas | `GET /api/incidents/dashboard/stats` | Conteos de incidencias por severidad y por estado |

### Respuesta

```json
{
  "total": 12,
  "by_severity": { "P1": 3, "P2": 5, "P3": 4 },
  "by_status": {
    "REPORTED": 2,
    "ASSIGNED": 3,
    "INVESTIGATING": 4,
    "IN_REVIEW": 0,
    "MITIGATED": 1,
    "RESOLVED": 1,
    "CLOSED": 1,
    "REOPENED": 0
  }
}
```

`by_severity` siempre incluye las claves `P1`, `P2` y `P3`, y `by_status` las
ocho claves del enum `IncidentStatus`; cuando no hay incidencias de una clave su
valor es `0`. `total` es la suma de `by_status`.

### Cálculo y consistencia

Los conteos se obtienen con dos consultas `GROUP BY` (`status` y `severity`)
sobre las incidencias del cliente autenticado:

```python
select(columna, func.count(Incident.id))
    .where(Incident.client_id == current_user.client_id)
    .group_by(columna)
```

No existe ningún contador persistido ni caché intermedia, por lo que el panel se
actualiza de forma consistente con el estado real de las incidencias: cada
cambio de estado hecho a través de `PATCH /api/incidents/{id}/status` se refleja
en la siguiente consulta del panel.

### Orden de la ruta

El endpoint se declara **antes** de `GET /{incident_id}`. De lo contrario FastAPI
intentaría interpretar `dashboard` como un `UUID` y respondería `422`.

---

## Seguridad y aislamiento

* `require_admin_or_leader(current_user)` exige rol ADMIN o TEAM_LEADER. Un
  DEVELOPER recibe `403`.
* El `WHERE client_id = current_user.client_id` limita los conteos al cliente
  (tenant) autenticado: un usuario de otro cliente no ve sus incidencias.

---

## Esquemas

`app/schemas/incident.py` define `IncidentDashboardStats`:

| Campo | Tipo | Descripción |
| ----- | ---- | ----------- |
| `total` | `int` | Total de incidencias del cliente |
| `by_severity` | `dict[str, int]` | Conteo por severidad (`P1`, `P2`, `P3`) |
| `by_status` | `dict[str, int]` | Conteo por estado |

---

## Pruebas

* `backend/tests/test_incidentes_notificaciones.py`
  * `test_panel_agrega_por_severidad_y_estado`: conteos correctos y
    actualización al mover una incidencia de estado.
  * `test_panel_solo_admin_o_lider`: 403 para DEVELOPER, 200 para ADMIN y
    TEAM_LEADER.
  * `test_panel_aislado_por_cliente`: no cuenta incidencias de otro cliente.
* `backend/tests/integration/test_api_contract.py`
  * `test_estadisticas_de_incidentes`: la ruta responde 200 (no la captura
    `/{incident_id}`) y la forma del payload es la esperada.
  * `test_estadisticas_de_incidentes_requiere_rol`: 403 para DEVELOPER.

---

## Resultado

WEB-15 queda **implementado**: `GET /api/incidents/dashboard/stats` entrega los
conteos por severidad y por estado, restringido a ADMIN y TEAM_LEADER y aislado
por cliente, sin migración de base de datos ni cambios de modelo.
