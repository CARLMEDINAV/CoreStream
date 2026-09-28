# TRV-02: acceso por perfil comercial

Cada cliente tiene un `commercial_plan` en la tabla `clients`. Los nombres son
`Basico` y `Pro`. La migración asigna `Basico` a los clientes existentes y a los
nuevos que no indiquen un plan. Los documentos no establecían una matriz de
planes para CoreStream; esta es la distribución inicial acordada para el cambio.

| Item                 | Recursos                | Basico | Pro|
|----------------------|-------------------------|--------|----|
| projects             | Aplicaciones y épicas   | Sí     | Sí |
| tickets              | Tickets/redir/subtareas | Sí     | Sí |
| documents            | Docs y archivos subidos | Sí     | Sí |
| team                 | Usuarios                | Sí     | Sí |
| incidents            | Incidencias             | Sí     | Sí |
| meetings             | Reuniones               | Sí     | Sí |
| support              | Tickets de soporte      | Sí     | Sí |
| notifications        | Consulta/gest de notif  | Sí     | Sí |
| analytics            | Analitica               | No     | Sí |
| document_translation | Traducción y descarga   | No     | Sí |

La autenticación, la aceptación pública de invitaciones y el transporte WebSocket
conservan sus controles existentes. No son funciones premium en esta matriz.

## Backend

`app/middleware/commercial.py` implementa el interceptor como dependencia de
FastAPI, igual que el control de roles existente. `require_feature(...)` se aplica
al incluir los routers en `main.py`; las dos operaciones de traducción tienen
además su dependencia específica. El control se ejecuta antes del handler y
consulta el cliente del usuario autenticado. No acepta un plan ni un `client_id`
elegidos desde el navegador. No guarda permisos comerciales en el JWT ni en Redis.

La falta de permiso devuelve HTTP 403:

```json
{
  "detail": {
    "code": "FEATURE_NOT_INCLUDED",
    "feature_flag": "analytics",
    "plan": "Basico",
    "message": "Funcionalidad no incluida en el perfil comercial activo"
  }
}
```

Un cliente inactivo o con un plan desconocido no obtiene funciones habilitadas.
Si no existe su perfil, se rechaza con 403. Un error de base de datos no concede
acceso. Los permisos RBAC y el aislamiento de TRV-01 siguen aplicándose.

`GET /api/auth/commercial-profile` requiere autenticación y devuelve `client_id`,
`plan`, `is_active` y `feature_flags`. No existe una operación de escritura para
usuarios cliente; ADMIN puede consultar el plan, no elevarlo.

## Frontend

El store de autenticación consulta el perfil comercial junto con `/auth/me` al
iniciar sesión y al restaurarla con la cookie de refresh. `hasFeature` exige una
bandera verdadera y un cliente activo; sin perfil no habilita funciones.
Los datos comerciales se borran al cerrar sesión o al fallar la autenticación.

El menú oculta Analítica en Basico y el router impide abrirla por URL directa.
Los cuatro botones de traducción y su modal se ocultan sin permiso. ADMIN ve
el nombre del plan y el estado del cliente en el menú lateral. Los textos nuevos
están en los cinco diccionarios de idiomas existentes.

Un cambio de plan se aplica en la siguiente petición del backend. Para actualizar
la navegación de una sesión abierta, recargar la página o volver a iniciar sesión.
No se añadió sincronización de planes por WebSocket.

## Dependencias y alcance

TRV-01 es la dependencia necesaria y ya existe en esta copia: aporta `Client`,
`client_id` y el aislamiento. La autenticación y WEB-02 también se reutilizan.
No hace falta desarrollar otro requerimiento antes de TRV-02.

NEW-11 es el futuro panel interno de administración de planes; depende de TRV-02,
no al revés. TRV-07 y TRV-08 quedan fuera de este cambio. No se añadió facturación,
gestión de suscripciones ni edición individual de banderas por cliente.

## Aplicar y probar en local

Con el entorno y las variables del backend configurados, desde `backend`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Si se usa otro entorno virtual, reemplazar la ruta del ejecutable por la de ese
entorno. Docker aplica las migraciones mediante su comando de arranque existente.

La migración nueva es `7e9ab80b3e68`, posterior a TRV-01 (`6d8fa79a2d57`). No se
aplicó a la base local de trabajo durante este desarrollo.

Hasta que exista NEW-11, el operador de la base puede asignar el plan por SQL.
Usar el identificador real del cliente que se quiere probar:

```sql
SELECT id, name, commercial_plan FROM clients;
UPDATE clients SET commercial_plan = 'Pro' WHERE id = '<client_id>';
```

Para volver al plan inicial, usar `Basico`. No hay que reiniciar el backend.
Después de recargar la web, comprobar el plan mostrado a ADMIN, el acceso a
Analítica y los botones de traducción. Las peticiones directas a funciones premium
con Basico deben responder 403, incluso cuando quien llama es ADMIN.

## Verificación realizada

- 157 pruebas unitarias existentes del backend: correctas.
- 14 pruebas nuevas en `backend/tests/test_commercial.py`: correctas. Incluyen
  HTTP sobre SQLite, separación de perfiles, cambios de plan, denegación por
  defecto, convivencia con RBAC y subida/bajada de la migración conservando datos.
- Pruebas del frontend en `frontend/tests/unit/stores/commercial.spec.ts`:
  autenticación, restauración, errores, navegación y componentes según plan.
- Compilación Vite, revisión de tipos y lint de los archivos Python modificados:
  correctos.
- La suite completa del frontend tenía 8 fallos previos: 7 en pruebas antiguas de
  autenticación y 1 en drag and drop. Se reprodujeron en una copia de HEAD sin
  estos cambios (60 correctas, 8 fallidas).
- Se añadieron 2 pruebas de integración con JWT, PostgreSQL y Redis reales en
  `backend/tests/integration/test_commercial.py`. No pudieron ejecutarse: el
  usuario PostgreSQL `corestream` no tiene permiso para crear la base de pruebas.
  La migración completa en PostgreSQL y el recorrido manual con servidor real
  quedan pendientes; no se alteraron los permisos del usuario de base de datos.

Los fixtures de integración usan Pro para mantener el acceso que necesitaban las
pruebas anteriores. Las nuevas pruebas cambian a Basico explícitamente.

```powershell
# desde backend
..\.venv\Scripts\python.exe -m pytest tests/test_commercial.py -q
..\.venv\Scripts\python.exe -m pytest tests/integration/test_commercial.py -q

# desde frontend
npm run test:unit -- --run tests/unit/stores/commercial.spec.ts
npm run type-check
npm run build
```
