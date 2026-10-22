WEB-14: ciclo de vida de incidencias

Este requerimiento permite seguir una incidencia desde que se reporta hasta que se cierra. Una incidencia representa un problema que debe investigar y solucionar el equipo. Esta explicación corresponde al backend de CoreStream.

El software entregado ya incluía operaciones básicas para incidencias. Durante el desarrollo de WEB-17 se amplió esa base para cubrir también WEB-14.

Cualquier usuario autenticado puede reportar una incidencia. Al hacerlo, indica un título y puede agregar descripción, categoría, severidad y ambiente afectado. La categoría inicial es general. Las severidades existentes son P1, P2 y P3; P1 corresponde a crítica y P2 a alta.

La incidencia comienza como REPORTED, es decir, reportada. Un administrador o líder puede asignarla a un desarrollador o líder activo del mismo cliente. Al asignarla pasa a ASSIGNED. En el código, el rol de líder se llama TEAM\_LEADER.

El responsable comienza a trabajar pasando la incidencia a INVESTIGATING. Para llegar a ese estado debe existir un responsable asignado. Desde ahí puede marcarla como MITIGATED si logró contener el problema, o enviarla a IN\_REVIEW para revisión. Una incidencia mitigada puede volver a investigación o enviarse a revisión.

Desde revisión se puede volver a investigación si falta trabajo. Un administrador o líder puede marcarla como RESOLVED y después como CLOSED. También puede reabrir una incidencia resuelta o cerrada: pasa a REOPENED y luego puede volver a investigación.

El backend comprueba que los cambios sigan ese recorrido. Por ejemplo, no permite pasar directamente de reportada a mitigada. Un cambio no permitido devuelve un error 409. El desarrollador solo puede gestionar las incidencias que tiene asignadas; resolver, cerrar y reabrir queda reservado a administradores y líderes.

Cada cambio de estado guarda quién lo hizo, la fecha, el estado anterior y el nuevo. El historial también registra el reporte, las asignaciones, las actualizaciones y los comentarios. Los usuarios del mismo cliente pueden consultar ese historial y agregar comentarios.

Los líderes y administradores tienen una consulta de atención. Muestra las incidencias P1 y P2 que todavía no están resueltas ni cerradas. Si una de ellas se reabre, vuelve a aparecer. Todas estas operaciones respetan la separación entre clientes.

Para usarlo desde la API, se crea una incidencia con POST /api/incidents/ y se consulta con GET /api/incidents/{id}. La asignación se cambia con PATCH /api/incidents/{id}, enviando assigned\_to\_id. El estado se cambia con PATCH /api/incidents/{id}/status, enviando status.

Los comentarios se agregan con POST /api/incidents/{id}/comments, enviando comentario. El historial se consulta con GET /api/incidents/{id}/events. La lista de atención se obtiene con GET /api/incidents/?atencion=true usando una sesión de administrador o líder.

Una prueba sencilla consiste en reportar una incidencia P1, asignarla, pasarla a investigación y enviarla a revisión. Después, un líder la resuelve y la cierra. Al consultar el historial deben aparecer los cambios con autor y fecha. La incidencia debe salir de la lista de atención al resolverse y volver a aparecer si se reabre.

