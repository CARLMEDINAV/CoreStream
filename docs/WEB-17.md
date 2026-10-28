WEB-17: notificaciones relacionadas con tickets e incidencias

Este requerimiento permite identificar qué ticket o incidencia originó una notificación y filtrar las notificaciones por el tipo de evento. Esta explicación corresponde al backend de CoreStream.

Una notificación relacionada con un ticket guarda su identificador en ticket\_id y deja incident\_id vacío. Una notificación relacionada con una incidencia hace lo contrario: guarda incident\_id y deja ticket\_id vacío. No puede apuntar a los dos recursos a la vez.

Los mensajes generales de tipo SYSTEM pueden no tener un recurso asociado. Esa excepción no se aplica a los avisos de tickets o incidencias, que necesitan su identificador correspondiente.

Cuando alguien reporta una incidencia, los administradores y líderes activos del mismo cliente reciben una notificación de tipo INCIDENT\_REPORTED. Cuando se asigna a un responsable, ese usuario recibe una notificación de tipo INCIDENT\_ASSIGNED. Estos tipos se guardan como tales en la base de datos, sin convertirse en SYSTEM.

El identificador permite que quien consume la API sepa qué recurso consultar. Si la notificación contiene incident\_id, puede consultar GET /api/incidents/{id}; si contiene ticket\_id, puede consultar GET /api/tickets/{id}. Tener una notificación no evita los controles de acceso del recurso. La navegación visual depende del frontend.

El usuario consulta sus notificaciones con GET /api/notifications/. Solo recibe las suyas y las de su propio cliente, ordenadas de más reciente a más antigua.

Para ver únicamente un tipo de evento se agrega el parámetro opcional type. Por ejemplo, GET /api/notifications/?type=INCIDENT\_ASSIGNED muestra las asignaciones de incidencias. GET /api/notifications/?type=INCIDENT\_REPORTED muestra los reportes, y GET /api/notifications/?type=TICKET\_ASSIGNED muestra las asignaciones de tickets.

Si no se envía type, el listado incluye todos los tipos. Si se envía un tipo que no existe, el backend responde con un error 422. El filtro también se puede combinar con unread\_only=true para ver solo las no leídas y con skip y limit para consultar el listado por partes.

El desarrollo se conectó con WEB-14 para generar los avisos al reportar y asignar incidencias. Los datos del recurso también se conservan al preparar su envío por el servicio de notificaciones.

Una prueba sencilla consiste en reportar una incidencia y revisar las notificaciones de un administrador o líder. Debe aparecer un aviso INCIDENT\_REPORTED con incident\_id y sin ticket\_id. Después, al asignarla a un desarrollador, ese usuario debe recibir un aviso INCIDENT\_ASSIGNED con la misma referencia.

Para comprobar el filtro, se consulta el listado con type=INCIDENT\_ASSIGNED y se verifica que solo aparezcan avisos de ese tipo. Al crear un ticket con responsable también debe generarse su aviso con ticket\_id y sin incident\_id. El ticket obtiene su identificador antes de crear la notificación para que el guardado no falle.

