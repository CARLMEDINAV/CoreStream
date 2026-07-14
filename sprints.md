# CoreStream — Plan de Sprints Detallado

> **Plataforma de Inteligencia Operacional**
> Stack: PostgreSQL · Vue 3 + Vite + TypeScript · FastAPI (Python) · Redis
> Duración: 10 semanas · 4 Desarrolladores · Sprints semanales

---

## Equipo

| Dev | Especialización | Rol principal |
|-----|----------------|---------------|
| **Dev 1** | Backend Lead / Infra | Arquitectura FastAPI, autenticación, testing backend |
| **Dev 2** | Backend / Data | Modelo de datos, state machine, métricas, lógica de negocio |
| **Dev 3** | Frontend Lead / UI | Componentes Vue, sistema de diseño, vistas, UX |
| **Dev 4** | Full-Stack / DevOps | Docker, Redis, WebSockets, Drag & Drop, i18n, testing E2E |

---

## Metodología

- **Ceremonias:** Planning el lunes · Daily de 15 min · Review + Retro el viernes
- **Estimación:** Fibonacci (1, 2, 3, 5, 8 puntos) · Velocidad objetivo: 18–22 pts/sprint
- **Definition of Done:** PR aprobado + tests pasando + desplegado en staging + sin regresiones

---

## Vista global de los 10 sprints

| Sprint | Foco | Puntos | Qué queda funcionando al terminar |
|--------|------|--------|-----------------------------------|
| S1 | Infraestructura base | 17 | Repo, BD, proyectos levantados, Redis conectado |
| S2 | Auth, roles, primera vista | 18 | Login funcional, roles RBAC, CRUD de Aplicaciones |
| S3 | The Builder (parte 1) | 15 | Epics y tickets con Drag & Drop de epics |
| S4 | The Builder (parte 2) + Workbench inicio | 16 | DnD de tickets entre epics, subtareas, vista dev |
| S5 | Núcleo operacional + WebSockets | 28 | State machine, Action Dock completo, WS conectado |
| S6 | Timer, logs, notificaciones, equipo base | 22 | Cronómetro, activity log, campana de notificaciones |
| S7 | Analytics + Team Management | 26 | Dashboard analítico, gestión de líderes y asignación |
| S8 | Analytics avanzado, Code & Docs, i18n | 26 | Burndown, exportación, repositorio docs, 5 idiomas |
| S9 | Docs restantes, config, tests unitarios | 24 | Modo oscuro, configuración usuario, tests 80%/70% |
| S10 | E2E, QA, accesibilidad, deploy | 22 | Producto terminado, documentado y desplegado |

---

## Sprint 1 — Semana 1
**Objetivo: sentar las bases — repositorio, base de datos, proyectos y Redis**
**17 puntos · 5 tickets**

Al finalizar este sprint el equipo debe poder levantar el entorno completo con un solo comando y tener la estructura de carpetas acordada.

### Tickets

#### CS-001 · Configurar repositorio monorepo — Dev 1 · 3 pts
Crear la estructura de carpetas `backend/` (FastAPI) y `frontend/` (Vue). Configurar `.gitignore`, `README.md`, pre-commit hooks (formateo, linting) y el pipeline de CI base que corra en cada PR. Es el primer ticket que debe completarse porque desbloquea al resto del equipo.

#### CS-002 · Diseñar y crear esquema de base de datos PostgreSQL — Dev 2 · 5 pts
Modelar todas las tablas del sistema desde el día uno: `users`, `roles`, `applications`, `epics`, `tickets`, `subtasks`, `ticket_events`, `notifications`, `documents`. Crear las migraciones con Alembic y los seeds de datos de prueba. Este esquema es el contrato de datos de todo el proyecto.

#### CS-003 · Configurar proyecto FastAPI con estructura modular — Dev 1 · 3 pts
Inicializar el proyecto FastAPI con arquitectura en capas: `routers/`, `schemas/`, `models/`, `services/`. Configurar middleware CORS, manejo de variables de entorno (`.env`), y generar la documentación Swagger automática en `/docs`.

#### CS-004 · Configurar proyecto Vue 3 con Vite y sistema de diseño — Dev 3 · 3 pts
Inicializar Vue 3 + Vite + TypeScript. Configurar Tailwind CSS con la paleta de Alloxentric (ver `corestream-color-guide.md`), Vue Router con las rutas base, Pinia como store global y el layout principal (sidebar + área de contenido). Definir los tokens de diseño que se usarán en todo el proyecto.

#### CS-005 · Integrar Redis como sistema de colas y cache — Dev 4 · 3 pts
Conectar Redis al backend FastAPI. Configurar el sistema de colas para notificaciones asíncronas, el cache de sesiones de usuario y las estructuras pub/sub que se usarán en S5 para WebSockets. Documentar la arquitectura de canales.

### Distribución de carga S1
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-001, CS-003 | 6 |
| Dev 2 | CS-002 | 5 |
| Dev 3 | CS-004 | 3 |
| Dev 4 | CS-005 | 3 |

---

## Sprint 2 — Semana 2
**Objetivo: autenticación, permisos, Docker y primera vista real**
**18 puntos · 4 tickets**

Al finalizar este sprint cualquier developer puede hacer login, el sistema conoce los roles, y se puede correr todo en Docker con un solo `docker-compose up`.

### Tickets

#### CS-006 · Implementar sistema de autenticación JWT — Dev 1 · 5 pts
Login y logout con JWT. Refresh tokens con rotación segura. Middleware de autenticación en FastAPI que protege todas las rutas privadas. Guards de ruta en Vue Router que redirigen al login si el token expiró. Endpoint `POST /auth/login` y `POST /auth/refresh`.

#### CS-007 · Implementar sistema de roles y permisos (RBAC) — Dev 2 · 5 pts
Definir los tres roles del sistema: `admin`, `group_leader`, `developer`. Decoradores de permisos en el backend (`@require_role`) para proteger endpoints por rol. Directivas de permisos en Vue (`v-permission`) para mostrar/ocultar elementos de UI según el rol del usuario autenticado. Permisos dinámicos que cambian sin recargar la página.

#### CS-008 · Configurar Docker Compose para entorno local — Dev 4 · 3 pts
Docker Compose con cuatro servicios: `postgres`, `redis`, `backend` (FastAPI con hot reload), `frontend` (Vue dev server con HMR). Variables de entorno por servicio. Script de inicialización que corre las migraciones de Alembic automáticamente al levantar el contenedor por primera vez.

#### CS-009 · CRUD de Aplicaciones (API + UI) — Dev 3 · 5 pts
Primeros endpoints REST reales: `GET/POST /applications`, `GET/PUT/DELETE /applications/{id}`. En el frontend: barra lateral izquierda con la lista de aplicaciones, indicadores de conteo de tickets pendientes y retrasados por app, modal de creación/edición, confirmación de eliminación. Esta es la primera vista completa del proyecto.

### Distribución de carga S2
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-006 | 5 |
| Dev 2 | CS-007 | 5 |
| Dev 3 | CS-009 | 5 |
| Dev 4 | CS-008 | 3 |

---

## Sprint 3 — Semana 3
**Objetivo: The Builder — Epics, Tickets y primer Drag & Drop**
**15 puntos · 3 tickets**

Al finalizar este sprint el Admin puede crear la jerarquía completa (App → Epic → Ticket) y reordenar Epics arrastrándolas.

### Tickets

#### CS-010 · CRUD de Epics con swimlanes colapsables — Dev 3 · 5 pts
Endpoints REST para epics (`GET/POST /applications/{id}/epics`, etc). UI con swimlanes tipo accordion: cada Epic es una sección expandible/colapsable con su lista de tickets dentro. Barra de progreso que muestra el porcentaje de tickets completados. Botón de creación rápida inline "+ Nueva Épica" sin abrir modal.

#### CS-011 · CRUD de Tickets con tarjetas y panel lateral — Dev 1 · 5 pts
Endpoints REST para tickets. En el frontend: tarjetas con estado visual usando color-coding (gris = TODO, azul = IN PROGRESS, ámbar = BLOCKED, verde = DONE). Panel lateral deslizante (side-panel) que se abre al hacer clic en un ticket, con breadcrumbs de navegación `App > Epic > Ticket` y todos los detalles del ticket.

#### CS-012 · Implementar Drag & Drop para Epics — Dev 4 · 5 pts
Arrastrar épicas para reordenar su prioridad dentro de una aplicación. Efecto visual de elevación (box-shadow) mientras se arrastra. Al soltar: llamada a `PATCH /epics/{id}` para persistir el nuevo `order_index`. Animación fluida de los demás elementos al reorganizarse. Evaluar si usar `@vueuse/gesture` o `vuedraggable`.

### Distribución de carga S3
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-011 | 5 |
| Dev 3 | CS-010 | 5 |
| Dev 4 | CS-012 | 5 |

---

## Sprint 4 — Semana 4
**Objetivo: The Builder completo + arranque del Workbench**
**16 puntos · 4 tickets**

Al finalizar este sprint The Builder está feature-complete (DnD de tickets, subtareas, adjuntos) y el developer puede ver sus tickets asignados.

### Tickets

#### CS-013 · Implementar Drag & Drop de Tickets entre Epics — Dev 4 · 5 pts
Extender el DnD de S3: ahora los tickets se pueden arrastrar entre distintas épicas. Al soltar en otra epic: actualizar `epic_id` del ticket vía `PATCH /tickets/{id}`. Animaciones de transición fluidas. El ticket debe mantener su posición visual hasta que la API confirme el cambio (optimistic update).

#### CS-014 · CRUD de Subtareas con checklist dinámico — Dev 1 · 3 pts
Lista de subtareas tipo checklist dentro del panel lateral de un ticket. Barra de progreso lineal que se actualiza en tiempo real al marcar/desmarcar. Opción de convertir una subtarea en ticket independiente (drag out hacia el tablero). Endpoints: `POST /tickets/{id}/subtasks`, `PATCH /subtasks/{id}`.

#### CS-015 · Adjuntar documentos a nivel de Epic — Dev 3 · 3 pts
Botón de clip (📎) en el encabezado de cada Epic para subir especificaciones, PDFs o cualquier documento. Los archivos quedan asociados a la Epic y son visibles (con previsualización) desde el panel de cualquier ticket hijo. Endpoint: `POST /epics/{id}/attachments`.

#### CS-016 · Vista My Workbench con lista de tickets asignados — Dev 2 · 5 pts
Dashboard principal del desarrollador. Tarjetas de tickets con su estado y métricas básicas. Filtros por estado (Todos / En Progreso / Por Hacer) y por fecha (Vencidos / Hoy / Esta Semana). Esta vista es la pantalla de inicio del developer cuando hace login.

### Distribución de carga S4
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-014 | 3 |
| Dev 2 | CS-016 | 5 |
| Dev 3 | CS-015 | 3 |
| Dev 4 | CS-013 | 5 |

---

## Sprint 5 — Semana 5
**Objetivo: el núcleo operacional — State Machine, Action Dock y WebSockets**
**28 puntos · 5 tickets** ⚠️ Sprint más pesado del proyecto

Al finalizar este sprint un developer puede tomar un ticket, ejecutarlo, completarlo, preguntar o redirigirlo. Los WebSockets están conectados y listos para el sprint siguiente.

### Tickets

#### CS-017 · Implementar máquina de estados del ticket — Dev 2 · 8 pts
El ticket más complejo de todo el proyecto. State machine formal con estos estados y transiciones:
```
TODO → IN_PROGRESS → DONE
             ↓              ↑
       BLOCKED_QUESTION ────┘
             ↓
        REDIRECTED
```
Cada transición se valida en el backend y genera un `ticket_event` con timestamp preciso. El estado debe ser consistente aunque múltiples usuarios estén viendo el mismo ticket. Evaluar usar `transitions` (Python) o implementar la máquina manualmente.

#### CS-018 · Implementar Action Dock: Botón Completar — Dev 3 · 5 pts
Botón verde en el panel del ticket. Validación obligatoria: no se puede completar si no hay un PR link ingresado. Al completar: micro-animación de confeti, el cronómetro se detiene, el ticket pasa a `DONE` y desaparece del Workbench activo. Registrar timestamp de cierre.

#### CS-019 · Implementar Action Dock: Botón Levantar Pregunta — Dev 1 · 5 pts
Botón ámbar. Al hacer clic despliega un mini-chat inline donde el developer escribe su duda. Al enviar: el ticket pasa a `BLOCKED_QUESTION`, el timer de ejecución se pausa y empieza a correr un timer de bloqueo separado. Se envía notificación al owner del ticket (Admin o Leader). La pregunta queda registrada en el Activity Log.

#### CS-020 · Implementar Action Dock: Botón Redireccionar — Dev 4 · 5 pts
Botón azul. Al hacer clic abre un popover con buscador de usuarios (filtrado por equipo) y un campo de contexto obligatorio (mínimo 10 caracteres explicando por qué se redirige). Al confirmar: se cierra el ciclo del usuario A (registrando su tiempo), se abre un nuevo ciclo para el usuario B, se actualiza el `assigned_to`, y se notifica al usuario B. Todo queda en el Activity Log.

#### CS-024 · Configurar WebSocket con FastAPI y Vue — Dev 4 · 5 pts
Endpoint WebSocket en FastAPI: `ws://api/ws/{user_id}`. Conexión persistente desde Vue al hacer login. Heartbeat cada 30 segundos para mantener la conexión viva. Reconexión automática con backoff exponencial si se cae. Composable `useWebSocket()` reutilizable en toda la app. Este ticket es prerequisito de CS-025.

### Distribución de carga S5
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-019 | 5 |
| Dev 2 | CS-017 | 8 |
| Dev 3 | CS-018 | 5 |
| Dev 4 | CS-020, CS-024 | 10 |

---

## Sprint 6 — Semana 6
**Objetivo: timer, logs, notificaciones en tiempo real y base de Team Management**
**22 puntos · 6 tickets**

Al finalizar este sprint el sistema tiene telemetría completa de cada ticket (tiempo efectivo vs bloqueado), el developer ve notificaciones en tiempo real, y el Admin puede gestionar el equipo.

### Tickets

#### CS-021 · Sistema de cronómetro y tracking de tiempo — Dev 2 · 5 pts
Cronómetro visible en el panel del ticket que muestra el tiempo transcurrido. Ciclo de vida del timer: inicia cuando el developer abre el ticket en IN_PROGRESS, se pausa automáticamente cuando el ticket pasa a BLOCKED, se reanuda cuando se resuelve la duda. Al cerrar el ticket registra dos métricas: **tiempo efectivo de trabajo** y **tiempo de bloqueo**. Ambas se usan en Analytics de S7.

#### CS-022 · Historial de actividad del ticket (Activity Log) — Dev 1 · 3 pts
Timeline cronológico dentro del panel del ticket que muestra todos los eventos: creación, cambios de estado, preguntas y respuestas, redirecciones con el contexto escrito, comentarios. Cada evento muestra avatar, nombre, acción y timestamp relativo ("hace 2 horas"). Los handoffs entre usuarios deben quedar visualmente claros para ver la trazabilidad del actor.

#### CS-023 · Reactivación de tickets bloqueados — Dev 3 · 3 pts
Flujo completo de resolución de bloqueos. El Admin o Leader ve los tickets en BLOCKED_QUESTION en su vista. Puede responder la duda directamente en el mini-chat. Botón "Resolver Duda" que marca la pregunta como respondida. El developer recibe notificación y ve el botón "Reanudar Trabajo" que hace la transición `BLOCKED → IN_PROGRESS` y reactiva el timer de ejecución.

#### CS-025 · Cola de notificaciones con Redis — Dev 4 · 5 pts
Sistema de notificaciones basado en Redis pub/sub. Cuando ocurre un evento relevante (pregunta levantada, ticket redirigido, ticket asignado) el backend publica un mensaje en el canal del usuario destino. Un worker asíncrono consume el canal y envía el mensaje via WebSocket al cliente Vue conectado. Garantizar entrega aunque el usuario no esté conectado (cola persistente).

#### CS-026 · UI de notificaciones (campana + panel) — Dev 3 · 3 pts
Icono de campana en el header con badge numérico de notificaciones no leídas. Al hacer clic: panel desplegable con lista de notificaciones ordenadas por recencia. Cada notificación tiene ícono según tipo, texto descriptivo y tiempo relativo. Click en notificación hace deep-link al ticket relacionado. Botón "Marcar todas como leídas".

#### CS-033 · CRUD de miembros del equipo — Dev 2 · 3 pts
Vista de gestión de equipo para el Admin. Alta, baja y edición de developers. Asignación de usuarios a proyectos/aplicaciones. Cada tarjeta de developer muestra sus estadísticas actuales: tickets completados, pendientes y bloqueados. Endpoints: `GET/POST /teams/{id}/members`, `DELETE /teams/{id}/members/{user_id}`.

### Distribución de carga S6
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-022 | 3 |
| Dev 2 | CS-021, CS-033 | 8 |
| Dev 3 | CS-023, CS-026 | 6 |
| Dev 4 | CS-025 | 5 |

---

## Sprint 7 — Semana 7
**Objetivo: Analytics y Team Management completo**
**26 puntos · 6 tickets**

Al finalizar este sprint el Admin tiene un dashboard con métricas reales de rendimiento del equipo, y los Líderes pueden asignar tickets con visibilidad de carga.

### Tickets

#### CS-027 · API de métricas agregadas por usuario — Dev 2 · 5 pts
Endpoints de analítica que calculan en tiempo real (o desde cache Redis): tickets procesados, editados, preguntas levantadas, derivaciones realizadas, y tiempo promedio de resolución por developer. Soporte de filtros por rango de fechas. Estas métricas son el motor del dashboard de S7-S8.

#### CS-028 · Tabla de rendimiento por persona — Dev 3 · 5 pts
Vista de tabla en el dashboard de Analytics. Columnas: Nombre, Tickets Procesados (con barra de progreso verde), Editados, Preguntas Levantadas, Derivaciones, Tiempo Promedio. Click en el nombre de un developer abre un drill-down con su histórico detallado. La tabla es exportable (conecta con CS-032).

#### CS-029 · Heatmap de actividad semanal — Dev 1 · 5 pts
Gráfico tipo heatmap: eje X = días de la semana, eje Y = developers del equipo, color = intensidad de tickets cerrados ese día (más oscuro = más productivo). Permite identificar de un vistazo los patrones de trabajo y los días de baja actividad. Implementar con Chart.js u otra librería compatible con Vue 3.

#### CS-034 · Sistema de promoción a Líder de Grupo — Dev 2 · 3 pts
Botón en la tarjeta de cada developer para promoverlo a Group Leader o degradarlo de vuelta a Developer. El cambio de rol es inmediato: los permisos se actualizan dinámicamente sin recargar la página (Pinia store + directivas `v-permission`). El Líder recibe un badge visual dorado en su avatar en toda la app.

#### CS-035 · Vista Team Assignment para Líderes — Dev 4 · 5 pts
Vista exclusiva para Group Leaders. Dos paneles en grid lado a lado:
- **Panel izquierdo:** tickets sin asignar del proyecto actual, con filtros por Epic y prioridad, botón "Asignar" en cada ticket.
- **Panel derecho:** tarjetas de cada developer con su carga actual y una barra de color: verde (1–3 tickets), amarillo (4–5), rojo (6+). Botón "Ver tickets" que expande la lista. Botón "Desasignar" en cada ticket expandido.
Los cambios se reflejan en tiempo real via WebSocket en el Workbench del developer asignado.

#### CS-036 · Modal de asignación con vista de carga — Dev 3 · 3 pts
Modal que se abre al hacer click en "Asignar" (desde CS-035 o desde el panel del ticket). Muestra la lista completa de developers del equipo con su carga actual visual. El Líder selecciona un developer y confirma. Al confirmar: el ticket aparece en el Workbench del developer y este recibe una notificación push.

### Distribución de carga S7
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-029 | 5 |
| Dev 2 | CS-027, CS-034 | 8 |
| Dev 3 | CS-028, CS-036 | 8 |
| Dev 4 | CS-035 | 5 |

---

## Sprint 8 — Semana 8
**Objetivo: Analytics avanzado, repositorio de Code & Docs, internacionalización**
**26 puntos · 6 tickets**

Al finalizar este sprint el Admin puede ver burndowns y exportar reportes, hay un repositorio de archivos por proyecto, y la app está lista en 5 idiomas.

### Tickets

#### CS-030 · Gráfico Burndown de Epics — Dev 1 · 5 pts
Gráfico de línea que muestra el progreso real vs el progreso ideal de una Epic a lo largo del tiempo. Eje X = días transcurridos desde el inicio de la Epic, eje Y = tickets restantes. Línea ideal (calculada al crear la Epic) vs línea real (actualizada diariamente). Filtros por aplicación y por epic. Permite detectar si el equipo va adelantado o retrasado respecto al plan.

#### CS-031 · Calcular índices de eficiencia, bloqueo y rotación — Dev 2 · 3 pts
Tres KPIs calculados automáticamente:
- **Índice de Eficiencia:** tickets completados / horas trabajadas
- **Índice de Bloqueo:** preguntas levantadas / total de tickets procesados
- **Índice de Rotación:** redirecciones realizadas / tickets asignados

Cada índice se muestra con un indicador semáforo (verde/amarillo/rojo) según umbrales configurables. Se muestran a nivel equipo y a nivel individual.

#### CS-032 · Exportar reportes a PDF/CSV — Dev 4 · 3 pts
Botón de exportación en el dashboard de Analytics. Dos formatos: PDF con el resumen visual de métricas del período seleccionado (usando una librería de generación PDF), y CSV con la tabla cruda de rendimiento por developer. La exportación se genera en el backend y se descarga directamente desde el browser.

#### CS-037 · Upload de archivos de código y documentación — Dev 3 · 5 pts
Formulario de subida de archivos con drag & drop en la sección Code & Docs. Tipos válidos: `.js`, `.ts`, `.py`, `.md`, `.pdf`, `.docx`. Al subir: el archivo se almacena con metadatos (nombre, tipo, tamaño, uploader, timestamp, proyecto asociado). Previsualización de texto para `.md` y `.py`. Vista de PDF embebida para archivos `.pdf`.

#### CS-038 · Vista de repositorio por proyecto — Dev 1 · 3 pts
Pantalla principal del módulo Code & Docs. Selector de proyecto en la parte superior. Tarjetas de estadísticas: total de archivos de código, total de documentación y número de contribuidores. Paneles de detalle con la lista de archivos organizados por tipo, con búsqueda y filtros.

#### CS-041 · Sistema de internacionalización (vue-i18n) — Dev 4 · 5 pts
Configurar `vue-i18n` con archivos de traducción JSON para 5 idiomas: Español, Inglés, Francés, Alemán y Portugués. Selector de idioma en el header (dropdown con banderas). Persistencia de la preferencia en el perfil del usuario. Todas las cadenas de texto de la app deben estar externalizadas en los archivos de traducción (cero strings hardcodeadas en los componentes).

### Distribución de carga S8
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-030, CS-038 | 8 |
| Dev 2 | CS-031 | 3 |
| Dev 3 | CS-037 | 5 |
| Dev 4 | CS-032, CS-041 | 8 |

---

## Sprint 9 — Semana 9
**Objetivo: cerrar Code & Docs, configuración de usuario, modo oscuro y tests unitarios**
**24 puntos · 6 tickets**

Al finalizar este sprint el producto está feature-complete y con una cobertura de tests sólida en backend (80%) y frontend (70%).

### Tickets

#### CS-039 · Vinculación de PR al completar ticket — Dev 4 · 3 pts
Campo de texto en el panel del ticket para ingresar el link del PR (Pull Request). Validación con regex que acepta URLs de GitHub, GitLab y Bitbucket. El botón "Completar" (CS-018) está deshabilitado hasta que haya un PR válido ingresado. El link del PR queda guardado en el ticket y visible en el Activity Log y en el módulo Code & Docs.

#### CS-040 · Traducción automática de documentos — Dev 2 · 5 pts
Integración con una API de traducción (DeepL o Google Translate). En la vista de un documento en Code & Docs aparece un botón "Traducir" con un selector de idioma destino. La traducción se genera de forma asíncrona (con indicador de carga) y se muestra en un panel paralelo al texto original. Soporte para los 8 idiomas de la integración. El resultado de la traducción se puede descargar.

#### CS-042 · Implementar modo oscuro — Dev 3 · 3 pts
Toggle de tema en la pantalla de configuración (y opcionalmente en el header). Variables CSS con dos sets de valores: tema oscuro (por defecto, basado en la paleta Alloxentric de `corestream-color-guide.md`) y tema claro. Persistencia de la preferencia en localStorage y en el perfil del usuario. Transición suave entre temas con `transition: background-color 300ms`.

#### CS-043 · Pantalla de configuración de usuario — Dev 1 · 3 pts
Modal o página de ajustes accesible desde el avatar del usuario. Secciones: perfil (nombre, foto, email), preferencias (idioma, tema, zona horaria), notificaciones (qué tipos de notificaciones recibir). Guardado de preferencias vía `PATCH /users/me/preferences`. Los cambios de idioma y tema se aplican inmediatamente sin recargar.

#### CS-044 · Tests unitarios backend (pytest) — Dev 2 · 5 pts
Suite de tests con pytest que cubre los servicios críticos del backend. Cobertura mínima del 80% en: state machine de tickets (todas las transiciones válidas e inválidas), cálculo de métricas, decoradores de permisos RBAC, y lógica de notificaciones. Fixtures con datos de prueba realistas. Los tests corren en el pipeline de CI en cada PR.

#### CS-045 · Tests unitarios frontend (Vitest) — Dev 1 · 5 pts
Suite de tests con Vitest (integrado con Vue Test Utils) que cubre los componentes críticos del frontend. Cobertura mínima del 70% en: ActionDock (los tres botones y sus validaciones), TicketPanel (renderizado por estado), componentes de Drag & Drop, store de Pinia (mutations y actions). Mocks de las llamadas a la API. Los tests corren en CI en cada PR.

### Distribución de carga S9
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-043, CS-045 | 8 |
| Dev 2 | CS-040, CS-044 | 10 |
| Dev 3 | CS-042 | 3 |
| Dev 4 | CS-039 | 3 |

---

## Sprint 10 — Semana 10
**Objetivo: E2E testing, QA, accesibilidad, polish final y deploy**
**22 puntos · 5 tickets**

Sprint de cierre. Al finalizar el producto está testeado end-to-end, es accesible, está optimizado y documentado. Listo para producción.

### Tickets

#### CS-046 · Tests end-to-end (Cypress o Playwright) — Dev 4 · 5 pts
Suite E2E que cubre los flujos críticos del negocio de principio a fin:
1. Crear aplicación → epic → ticket → asignar a developer
2. Developer completa un ticket (con PR link)
3. Developer levanta una pregunta → Admin responde → developer reanuda
4. Developer redirige ticket a otro developer
5. Admin ve el dashboard de Analytics con métricas reales

Los tests corren en el pipeline de CI contra un entorno de staging con datos seed.

#### CS-047 · Auditoría de accesibilidad WCAG AA — Dev 3 · 3 pts
Revisión completa de accesibilidad en toda la app:
- Navegación completa por teclado (Tab, Enter, Escape, flechas)
- Contraste de colores mínimo 4.5:1 en todos los textos (verificar con la paleta Alloxentric)
- ARIA labels en todos los elementos interactivos que no tengan texto visible
- Testing con screen reader (NVDA o VoiceOver)
- Corrección de todos los issues encontrados

#### CS-048 · Optimización de rendimiento y lazy loading — Dev 1 · 3 pts
En el frontend: code splitting por rutas (cada vista se carga solo cuando se navega a ella), lazy loading de módulos pesados como Chart.js y la librería de PDF. En el backend: revisión de queries SQL lentas con `EXPLAIN ANALYZE`, creación de índices en las columnas más consultadas (`tickets.status`, `tickets.assigned_to`, `ticket_events.ticket_id`). Meta: tiempo de carga inicial < 2 segundos.

#### CS-049 · Sprint de corrección de bugs y polish — Todos · 8 pts
Sprint buffer dedicado a resolver los bugs encontrados durante el QA de S10, pulir micro-interacciones (hover states, loading skeletons, empty states), revisar la consistencia visual en todas las vistas, y hacer una revisión final de UX con el equipo completo. Los bugs se priorizan en el planning del lunes según impacto.

#### CS-050 · Documentación técnica y guía de despliegue — Dev 2 · 3 pts
Entregables de documentación:
- `README.md` actualizado con instrucciones de setup, variables de entorno y comandos
- Diagrama de arquitectura del sistema (base de datos, servicios, flujo de datos)
- Guía de despliegue en producción con Docker (variables de entorno de producción, secretos, health checks)
- Documentación de la API en formato OpenAPI/Swagger (ya auto-generada por FastAPI, revisar y completar descripciones)

### Distribución de carga S10
| Dev | Tickets | Puntos |
|-----|---------|--------|
| Dev 1 | CS-048 | 3 |
| Dev 2 | CS-050 | 3 |
| Dev 3 | CS-047 | 3 |
| Dev 4 | CS-046 | 5 |
| Todos | CS-049 | 8 |

---

## Mapa de dependencias críticas

```
S1: CS-001 → todos los demás (repo)
S1: CS-002 → CS-006, CS-007, CS-017 (esquema BD)
S1: CS-005 → CS-025 (Redis → cola de notificaciones)
S2: CS-006 + CS-007 → toda la app (auth + roles)
S3: CS-011 → CS-013, CS-014, CS-017 (tickets → DnD, subtareas, state machine)
S5: CS-017 → CS-018, CS-019, CS-020 (state machine → Action Dock)
S5: CS-024 → CS-025 (WebSocket → cola notificaciones)
S6: CS-021 → CS-027, CS-031 (timer → métricas de tiempo)
S6: CS-033 → CS-034, CS-035 (CRUD equipo → promoción y asignación)
S7: CS-027 → CS-028, CS-031 (API métricas → tabla y KPIs)
S9: CS-044 + CS-045 → CS-046 (unit tests → E2E)
```

---

## Riesgos identificados

| Riesgo | Probabilidad | Sprint afectado | Mitigación |
|--------|-------------|-----------------|------------|
| Complejidad del Drag & Drop | Media | S3, S4 | Spike técnico en S2. Prototipo rápido antes de comprometerse con la librería. |
| State machine inconsistente | Alta | S5 | Implementar con patrón formal. Tests exhaustivos de todas las transiciones. |
| WebSocket: desconexiones frecuentes | Media | S5, S6 | Heartbeat cada 30s. Reconexión con backoff exponencial. Fallback a polling. |
| Queries analíticas lentas | Media | S7, S8 | Índices en PostgreSQL desde S1. Vistas materializadas para métricas pesadas. |
| Scope creep | Alta | Todos | Sprint backlog cerrado al iniciar. Cambios van al sprint siguiente. Buffer en S10. |
| Dependencias front/back no sincronizadas | Media | S3–S7 | Contratos API (OpenAPI) definidos en S1. Mocks para desarrollo paralelo. |

---

## Criterios de aceptación del proyecto

- [ ] Admin crea jerarquía completa (App → Epic → Ticket → Subtarea) con Drag & Drop funcional
- [ ] Developer ejecuta los tres flujos: Completar (con PR), Preguntar (con pausa de timer), Redireccionar (con contexto obligatorio)
- [ ] State machine funciona correctamente con todas las transiciones y el tracking de tiempo es preciso
- [ ] Dashboard de Analytics muestra: eficiencia, índice de bloqueo, índice de rotación, heatmap y burndown
- [ ] Notificaciones en tiempo real funcionan via WebSocket con Redis como broker
- [ ] La app soporta 5 idiomas y tiene modo oscuro funcional
- [ ] Cobertura de tests: ≥80% backend · ≥70% frontend · flujos críticos en E2E
- [ ] Accesibilidad WCAG AA verificada con navegación completa por teclado

---

*CoreStream — Plan de Desarrollo · 10 sprints · 50 tickets · 212 story points · Marzo 2026*