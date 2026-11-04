NEW-11: Panel interno de planes y feature flags

Permite a Alloxentric consultar clientes, asignar Basico, Pro o Enterprise, activar o desactivar funciones por cliente y consultar uso premium. Reutiliza TRV-02, la autenticación existente y audit.audit_logs. No agrega dependencias.

Acceso

El permiso de plataforma es independiente de ADMIN, TEAM_LEADER y DEVELOPER. Requiere una cuenta activa cuyo UUID esté en PLATFORM_ADMIN_IDS y cuyo client_id coincida con PLATFORM_CLIENT_ID. La organización interna también debe estar activa. Sin configuración, nadie tiene acceso.

PLATFORM_CLIENT_ID debe identificar una organización exclusiva de Alloxentric, nunca una organización cliente. Sus administradores son personal interno de confianza, porque conservan las facultades existentes para gestionar las cuentas de esa organización. Los administradores de clientes finales no pueden concederse este permiso desde la API.

Preparación

Desde backend, aplicar la migración con ..\.venv\Scripts\python.exe -m alembic upgrade head.
La migración e4a5b6c7d8e9 sigue a c7f3a91d2e45. Agrega clients.feature_overrides y las columnas feature_flag y commercial_detail al esquema audit. Conserva los planes y datos existentes. Revertirla elimina las excepciones y estos detalles nuevos.

Usar una cuenta interna existente o crear el primer administrador de una organización interna mediante app.scripts.create_admin. Consultar sus UUID en la base:
SELECT id, email, client_id FROM users WHERE email = 'operador@alloxentric.com';

En backend/.env para ejecución manual, o en el .env raíz para Docker, configurar:
PLATFORM_CLIENT_ID=uuid-real-del-cliente-interno
PLATFORM_ADMIN_IDS=["uuid-real-del-operador"]

Reiniciar el backend para cargar esta autorización inicial. Docker Compose transmite ambas variables al backend. No se habilita ninguna cuenta automáticamente.

Funcionamiento

Iniciar sesión normalmente y pulsar Administración de plataforma · Planes y funciones en la cabecera, junto a las opciones de usuario. El enlace aparece únicamente cuando el backend confirma el permiso interno al iniciar o restaurar la sesión; se oculta al cerrar sesión o si la consulta falla. Abre /#/platform/plans. La ruta vuelve a comprobar el permiso con el servidor antes de mostrar la consola. Los clientes finales no ven esta entrada.

Elegir un cliente, cambiar el plan y seleccionar Según plan, Activada o Desactivada para cada bandera. Guardar persiste el plan y reemplaza el conjunto de excepciones. Según plan elimina la excepción. Las excepciones se conservan al cambiar el plan hasta quitarlas expresamente. El acceso efectivo mostrado corresponde al último valor guardado.

El backend aplica los cambios en la siguiente petición, sin despliegue ni reinicio. Para refrescar el perfil comercial y la navegación de una sesión cliente abierta, recargar la página. Los clientes inactivos y los planes desconocidos nunca obtienen acceso, aunque existan excepciones. Los permisos de rol y pertenencia siguen vigentes. Algunas vistas antiguas no ocultan todos sus enlaces por bandera; el backend rechaza la función desactivada con 403.

La consola incluye selector de cliente paginado, estado del cliente, editor, conteos premium y los últimos 50 cambios disponibles. Usa los colores existentes y textos en los cinco idiomas de la aplicación. Es una vista simple de prueba.

Auditoría

Cada guardado almacena actor, función PLATFORM_ADMIN, cliente afectado, fecha, IP, User-Agent y valores anterior y nuevo en audit.audit_logs. Se confirma en la misma transacción que el perfil: si falla este registro, tampoco se guarda el cambio. PLATFORM_ADMIN es la etiqueta de auditoría del permiso interno, no un nuevo rol asignable por clientes.

El middleware conserva además el registro HTTP general y sus destinos existentes. El detalle anterior/nuevo se almacena en PostgreSQL y se consulta desde la consola. Ambos registros cumplen propósitos distintos. Se aplica la retención existente por plan, incluso después de cambiarlo.

Uso premium

Cuenta peticiones exitosas registradas para analytics, document_translation y audit_export. Incluye lecturas de analítica aunque AUDIT_READS esté desactivado. Las exportaciones usan su registro al finalizar la descarga. Los rechazos y errores no suman. Repetir una consulta exitosa suma otra petición.

La consulta acepta entre 1 y 730 días, con 30 por defecto, y se limita a la retención vigente del cliente. No reconstruye actividad anterior a esta implementación. No representa usuarios únicos, consumo facturable ni documentos procesados. Hereda los límites de entrega de auditoría existentes: una caída del registro puede dejar peticiones sin contabilizar y una descarga abortada puede no producir evento. No sirve como contador de cobro.

API

GET /api/platform/access comprueba el permiso interno.
GET /api/platform/clients lista perfiles con offset y limit, máximo 100.
PUT /api/platform/clients/{cliente_id} guarda plan y feature_overrides completos.
GET /api/platform/clients/{cliente_id}/usage?days=30 devuelve fecha inicial y conteos.
GET /api/platform/clients/{cliente_id}/changes devuelve los últimos 50 cambios dentro de la retención.

Ejemplo de cuerpo para guardar:
{"plan":"Pro","feature_overrides":{"analytics":false,"audit_export":true}}

Las banderas desconocidas, planes inválidos, valores que no sean booleanos y campos extra se rechazan con 422. Un cliente inexistente devuelve 404. Un usuario autenticado sin permiso interno recibe 403. GET /api/auth/commercial-profile conserva su contrato y devuelve únicamente el perfil del cliente autenticado, incluyendo las excepciones aplicadas.

Prueba manual propuesta

Entrar con la cuenta interna y dejar un cliente en Basico sin excepciones. Con una sesión de ese cliente, comprobar que Analítica devuelve 403. Desde la consola interna, activar analytics y guardar. Repetir la petición: debe permitirse según el rol. Consultar el contador y el historial, desactivar analytics y comprobar nuevamente el 403. Volver a Según plan y verificar que se respeta Basico. Entrar con ADMIN de un cliente final y comprobar que no puede abrir la consola ni llamar a sus endpoints.

Verificación del desarrollo, 4 de noviembre de 2026

Pruebas automatizadas nuevas en backend/tests/test_platform.py: autorización interna, rechazo de ADMIN cliente, validación, cambio inmediato, aislamiento, auditoría, reversión ante fallo de auditoría, uso por cliente y retención, migración de subida y bajada sobre SQLite.
Suite de backend: 357 correctas y una omitida. Comando desde backend: ..\.venv\Scripts\python.exe -m pytest tests --ignore=tests/integration -q.
Pruebas de frontend: 9 correctas entre tests/unit/platform.spec.ts y tests/unit/stores/commercial.spec.ts. Incluyen edición de planes, visibilidad de la entrada interna, restauración de permisos y limpieza de sesión.
Compilación Vite correcta. Ruff correcto en todos los archivos Python modificados. Alembic tiene una sola cabeza y genera correctamente el SQL PostgreSQL de la migración.
La revisión de tipos del frontend pasa. Se corrigió la importación de MfaStatus en services/api.ts: el tipo ya existía en types/index.ts y describe el estado de la verificación en dos pasos. También se corrigió el orden de imports en app/models/__init__.py que bloqueaba GitHub Actions. La validación completa ruff check app tests pasa con Ruff 0.16.1.
No se aplicó la migración a la base de trabajo ni se ejecutó integración con PostgreSQL y Redis reales o un recorrido manual en navegador. La prueba manual anterior queda propuesta, no ejecutada.

No se realizó commit, push ni despliegue.
