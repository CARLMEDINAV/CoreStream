# WEB-18: Analítica agregada de trabajo

## Propósito y estado inicial

Reunir tickets e incidencias activos de una persona y consultar los conteos de
trabajo personal y de equipo. La entrega incluye la API y su integración en
Workbench y Analítica.

El documento original indicaba «no verificable». El código ya tenía workbench de
tickets, estadísticas personales y analítica por aplicación. Faltaban el listado
combinado y los conteos agregados. El workbench ordenaba por creación y las
estadísticas permitían consultar a otras personas sin comprobar el rol.
Se reutilizan los modelos y el historial existentes, sin dependencias nuevas ni
migraciones. La primera parte del trabajo dejó la capacidad en la API; la
continuación conecta las pantallas existentes sin crear una sección nueva.

## Quién puede usarlo

Todos los roles pueden consultar su propio trabajo. DEVELOPER solo puede consultar
sus estadísticas; ADMIN y TEAM_LEADER pueden consultar otras personas del mismo
cliente. Un desarrollador que consulta estadísticas ajenas recibe 403. Para gestión,
un usuario inexistente o de otro cliente devuelve 404. Un UUID inválido devuelve 422.

El resumen de equipo requiere ADMIN o TEAM_LEADER y la función comercial analytics,
disponible en Pro y Enterprise. El workbench y las estadísticas personales conservan
el acceso de Basico. El cliente se obtiene de la sesión, no de un parámetro del navegador.

## Endpoints y flujo

GET /api/users/me/workbench devuelve trabajo activo asignado al usuario autenticado.
Cada elemento contiene id, type (ticket o incident), title, status y due_date.
El tipo permite elegir la ruta de detalle correspondiente, conservando sus permisos.

Los tickets usan due_date. Como las incidencias no tienen fecha límite propia,
se calcula una fecha estimada sumando created_at y estimated_resolution_time_seconds.
Una estimación de cero significa que no hay fecha. Es una previsión con los datos
existentes, no un SLA ni una fecha nueva guardada en la base.

Se ordena por fecha ascendente: vencidos primero, sin fecha al final. Los empates
se ordenan por tipo e identificador. Incluye incidencias reabiertas y excluye
recursos finalizados. No tiene paginación, igual que el workbench anterior.

GET /api/tickets/my-workbench conserva TicketResponse, status_filter y priority_filter.
Ahora ordena por vencimiento, pero sigue permitiendo consultar tickets finalizados.
Los consumidores anteriores siguen disponibles. El listado principal «Mi trabajo»
ahora utiliza /api/users/me/workbench; los contadores de tickets por aplicación
conservan su consulta anterior.

GET /api/users/{user_id}/stats conserva user_id, completed_tickets,
in_progress_tickets, blocked_tickets, total_activity y join_date. Agrega
work_summary, con los conteos del trabajo asignado actualmente a esa persona.
Los campos anteriores no pasan a representar siete días. blocked_tickets ahora
incluye BLOCKED y BLOCKED_QUESTION.

GET /api/analytics/work-summary devuelve los conteos del cliente completo,
incluido el trabajo sin responsable o asignado a usuarios inactivos.
No filtra por aplicación ni calcula productividad individual.

## Reglas de los conteos

work_summary y el resumen de equipo contienen tickets, incidents y total.
Cada grupo tiene active, in_progress, blocked y completed_last_7_days.

active cuenta tickets distintos de COMPLETED y RESOLVED, e incidencias distintas
de RESOLVED y CLOSED. Representa el estado actual. Incluye trabajo pendiente,
en progreso y bloqueado: no se suma con estos últimos, que son subconjuntos.

in_progress cuenta tickets IN_PROGRESS o INVESTIGATING, e incidencias
INVESTIGATING, MITIGATED o IN_REVIEW. Una incidencia mitigada sigue abierta.

blocked cuenta tickets BLOCKED o BLOCKED_QUESTION. Las incidencias no tienen
un estado de bloqueo, por lo que su conteo es cero.

completed_last_7_days usa una ventana móvil de siete días hasta el instante de
consulta, en UTC, con ambos límites incluidos. Para tickets exige estado
COMPLETED o RESOLVED y completed_at dentro de la ventana. Para incidencias exige
estado actual RESOLVED o CLOSED y el último evento de tipo estado hacia RESOLVED
dentro de la ventana. Cada incidencia cuenta una sola vez aunque tenga varias
resoluciones. Cerrar o comentar no cambia la fecha usada. Una incidencia reabierta
deja de contar como completada mientras siga activa.

Los registros antiguos sin completed_at o sin evento de resolución no cuentan
como completados recientes. No se usa updated_at para inventar una fecha.
Las estadísticas personales corresponden al responsable actual, no al autor de
la resolución; no son un historial de productividad por persona.

Los conteos usan dos consultas SQL agregadas, sin contadores persistidos ni una
consulta por cada miembro del equipo.

## Pantallas

En /dev/workbench, la pestaña «Mi trabajo» muestra los cuatro conteos personales
con el desglose de tickets e incidencias. Debajo aparece el listado combinado de
trabajo activo. La vista «Por épica» se conserva para navegar por los tickets del
proyecto, incluidos los finalizados.

El listado permite filtrar por tipo de recurso, grupo de trabajo, estado específico
y fecha: todas, vencidos, hoy o esta semana. Las fechas se muestran en el idioma
elegido y la zona horaria del navegador. «Esta semana» abarca desde hoy hasta el
domingo; «vencidos» incluye fechas anteriores al día actual. Los recursos sin
fecha aparecen solo al seleccionar todas las fechas. Los filtros conservan el
orden del servidor y no alteran los conteos, que representan todo el trabajo propio.

Cada tarjeta indica si corresponde a un ticket o una incidencia. Los tickets
abren su panel existente después de obtener el detalle completo. Las incidencias
abren su modal existente, con historial, comentarios y acciones según los permisos.
Después de modificar un ticket o guardar una incidencia se recargan listado y
conteos. El botón Actualizar permite consultar otros cambios del equipo.

En /admin/analytics aparece el bloque «Trabajo del equipo», antes de los filtros
de aplicación y período existentes. Tiene su propio botón Actualizar y muestra
los cuatro conteos con desglose. Su alcance es todo el cliente y los últimos siete
días para los completados; los filtros de los otros gráficos no lo modifican.
La ruta conserva el control de ADMIN/TEAM_LEADER y la función comercial analytics.

Ambos bloques incluyen carga, mensajes de error y reintento. Si falla un resumen
no se presenta como un conteo de cero. El listado personal puede seguir funcionando
si falla solamente la consulta de sus estadísticas. Los textos nuevos están
disponibles en español, inglés, francés, alemán y portugués.

## Ejemplo de prueba manual

Asignar a un DEVELOPER un ticket con vencimiento y una incidencia con estimación.
Con su sesión, consultar GET /api/users/me/workbench y comprobar que aparecen
ordenados. Un recurso asignado a otra persona no debe aparecer.

Consultar GET /api/users/{id_propio}/stats y comprobar work_summary. Consultar
el ID de otra persona debe devolver 403. Con ADMIN o TEAM_LEADER del mismo
cliente debe devolver 200.

Con un cliente Pro o Enterprise y rol de gestión, consultar
GET /api/analytics/work-summary. Completar un ticket y resolver una incidencia
mediante sus operaciones habituales aumenta completed_last_7_days. Reabrir
la incidencia la devuelve a active. Con Basico el resumen devuelve 403 con
FEATURE_NOT_INCLUDED; con DEVELOPER tampoco está permitido.

En la interfaz, entrar a /dev/workbench y revisar «Mi trabajo». Probar los filtros,
abrir un ticket y una incidencia, y cambiar un estado permitido desde el detalle.
El listado y los conteos deben actualizarse. Para verificar el equipo, entrar a
/admin/analytics con un rol de gestión y plan Pro o Enterprise. El bloque debe
estar disponible aunque todavía no se haya seleccionado una aplicación.

## Verificación del 22 de octubre de 2026

Se añadieron siete pruebas HTTP sobre SQLite en backend/tests/test_work_summary.py.
Las siete pasaron. Cubren mezcla y orden, exclusión de finalizados, permisos,
planes, aislamiento, trabajo sin responsable, límites de fechas, historial
repetido, comentarios, reaperturas y compatibilidad de la respuesta anterior.

Desde backend se ejecutaron python -m ruff check app tests, sin errores,
y python -m alembic heads, con una sola cabeza: d2e3f4a5b6c7.
La suite sin integración se ejecutó con
python -m pytest tests --ignore=tests/integration -q:
340 pruebas aprobadas y una omitida, con 55 advertencias de deprecación.

La continuación de frontend añadió nueve pruebas de componentes en
frontend/tests/unit/components/workSummary.spec.ts. Pasaron las nueve: listado
combinado, filtros, apertura de detalles, actualización, estados vacíos, errores,
reintentos, resumen del equipo y correspondencia de claves en los cinco idiomas.
La comprobación final junto con las cinco pruebas comerciales terminó con
14 pruebas aprobadas, incluido el bloqueo de Analítica en Basico y su acceso en Pro.
Los comandos npm run type-check y npm run build también terminaron correctamente.

La suite completa del frontend terminó con 58 pruebas aprobadas y una fallida,
además de una suite que no pudo cargarse. Los problemas son una prueba de
useDragDrop.spec.ts y una llave sobrante en authStore.spec.ts, línea 346.
Se comprobó que esos archivos y el composable de arrastre no tienen diferencias
respecto de HEAD. No se modificaron para este requerimiento.

Se revisaron en navegador los componentes con datos ficticios: presentación del
listado y conteos, apertura del modal de incidencias y actualización de la tarjeta
tras mitigar una incidencia. La página temporal de prueba se retiró al terminar.

No se ejecutó un recorrido completo con sesión real, PostgreSQL y Redis. Las
pruebas HTTP del backend sustituyen la autenticación por usuarios de prueba;
no verifican JWT, auditoría ni despliegue. No se aplicaron migraciones ni se
modificaron datos de la base de trabajo.
