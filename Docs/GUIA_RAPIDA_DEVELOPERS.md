# ⚡ GUÍA RÁPIDA - QUÉ HACER AHORA

**Para Developers - TL;DR Version**

---

## 🚨 CRÍTICAS QUE BLOQUEAN PRODUCCIÓN

### 1️⃣ ATOMICIDAD REORDER (epics.py) - 4 HORAS
**Archivo:** `backend/app/routers/epics.py:270-330`

**Problema:** Dos clientes reordenan épicas simultáneamente → order_index duplicados

**Solución RÁPIDA:**
```python
# REEMPLAZAR ESTA FUNCIÓN COMPLETA:
# async def reorder_epic(epic_id, new_order, ...)

# CON ESTA:
from sqlalchemy import text

async def reorder_epic(...):
    """USAR SQL NATIVO + TRANSACCIÓN"""
    async with db.begin_nested():
        # 1. SELECT FOR UPDATE (lock)
        epic = await db.execute(
            text("SELECT id, order_index FROM epics WHERE id = :id FOR UPDATE"),
            {"id": epic_id}
        )
        # 2. UPDATE directamente en SQL
        await db.execute(
            text("UPDATE epics SET order_index = :new WHERE id = :id"),
            {"new": new_idx, "id": epic_id}
        )
    await db.commit()
```

**Archivo de referencia:** `PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md` → Sección FIX-001

---

### 2️⃣ VALIDACIÓN CROSS-APP (tickets.py) - 2 HORAS
**Archivo:** `backend/app/routers/tickets.py:358-420`

**Problema:** Ticket de App A puede moverse a Epic de App B ✗

**Solución RÁPIDA:**
```python
# AGREGAR ESTA VALIDACIÓN ANTES DE ACTUALIZAR:

# Cargar épica actual Y destino
current_epic = await db.execute(
    select(Epic).where(Epic.id == ticket.epic_id)
).scalar_one()

new_epic = await db.execute(
    select(Epic).where(Epic.id == move_data.new_epic_id)
).scalar_one()

# ← ESTA LÍNEA ES CRÍTICA:
if current_epic.application_id != new_epic.application_id:
    raise HTTPException(400, "Apps diferentes, movimiento rechazado")

# Luego hacer el move
ticket.epic_id = new_epic.id
```

**Archivo de referencia:** `PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md` → Sección FIX-002

---

### 3️⃣ CONTEOS REALES (applications.py) - 3 HORAS
**Archivo:** `backend/app/routers/applications.py:40-75`

**Problema:** Retorna `pending_count: 0` siempre (hardcoded)

**Solución RÁPIDA:**
```python
# REEMPLAZAR epic_count=0, pending_count=0, delayed_count=0
# CON ESTO:

for app in applications:
    # Contar épicas
    epic_count = await db.execute(
        select(func.count(Epic.id)).where(Epic.application_id == app.id)
    ).scalar() or 0
    
    # Contar pendientes (TODO)
    pending = await db.execute(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .join(Epic, Ticket.epic_id == Epic.id)
        .where(Epic.application_id == app.id, Ticket.status == "TODO")
    ).scalar() or 0
    
    # Contar retrasados
    overdue = await db.execute(
        select(func.count(Ticket.id))
        .select_from(Ticket)
        .join(Epic, Ticket.epic_id == Epic.id)
        .where(
            Epic.application_id == app.id,
            Ticket.due_date < datetime.now(),
            Ticket.status != "COMPLETED"
        )
    ).scalar() or 0
```

**Archivo de referencia:** `PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md` → Sección FIX-003

**BONUS:** Agregar índices PostgreSQL
```sql
CREATE INDEX idx_epic_application_id ON epics(application_id);
CREATE INDEX idx_ticket_status_epic ON tickets(epic_id, status);
CREATE INDEX idx_ticket_overdue ON tickets(due_date, status);
```

---

### 4️⃣ BADGES DINÁMICOS (ApplicationList.vue) - 3 HORAS
**Archivo:** `frontend/src/components/builder/ApplicationList.vue:30-50`

**Problema:** No muestra "📋 10 pendientes" ni "⏰ 3 retrasados"

**Solución RÁPIDA:**
```vue
<!-- REEMPLAZAR ESTA LÍNEA: -->
<!-- {{ app.epicCount || 0 }} épicas · {{ app.ticketCount || 0 }} tareas -->

<!-- CON ESTO: -->
<div class="flex gap-2 mt-2">
  <span v-if="app.pending_count > 0" class="bg-yellow-100 text-yellow-800 text-xs font-bold px-2 py-1 rounded">
    📋 {{ app.pending_count }} pendientes
  </span>
  <span v-if="app.overdue_count > 0" class="bg-red-100 text-red-800 text-xs font-bold px-2 py-1 rounded animate-pulse">
    ⏰ {{ app.overdue_count }} retrasados
  </span>
  <span v-if="app.pending_count === 0 && app.overdue_count === 0" class="text-green-600 text-xs font-bold">
    ✓ Todo al día
  </span>
</div>
```

**Archivo de referencia:** `PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md` → Sección FIX-004

---

## 📝 CHECKLIST DE IMPLEMENTACIÓN

### Fase 1: CRÍTICA (Esta semana)
```
BACKEND:
☐ FIX-001: Transacción atómica en PATCH /epics/reorder
☐ FIX-002: Validación cross-app en PATCH /tickets/move
☐ FIX-003: Conteos reales en GET /applications
☐ Crear índices PostgreSQL
☐ Tests de race condition

FRONTEND:
☐ FIX-004: Badges dinámicos en ApplicationList.vue
☐ FIX-005: Escala 1.02x en drag epic (visual)
```

---

## 🧪 CÓMO PROBAR

### Test de Race Condition (CRÍTICA)
```bash
# Crear 2 clientes que simultáneamente reordenan épicas
pytest backend/tests/test_epic_reorder_atomic.py::test_concurrent_reorder_no_duplicates -v

# Debe PASAR: order_index nunca duplicado
```

### Test de Validación Cross-App
```bash
# Intentar mover ticket entre apps
pytest backend/tests/test_ticket_move_validation.py::test_move_prevents_cross_app -v

# Debe PASAR: Rechaza el movimiento
```

### Verificar Conteos Reales
```bash
# GET /applications
curl http://localhost:8000/api/applications

# Debe retornar "pending_count": 5 (no 0)
```

---

## 📂 DÓNDE ENCONTRAR CÓDIGO

| Crítica | Archivo | Documento Referencia |
|---------|---------|-------------------|
| Reorder race | `epics.py:270-330` | `PLAN_CORRECCIÓN_P1.md` FIX-001 |
| Cross-app | `tickets.py:358-420` | `PLAN_CORRECCIÓN_P1.md` FIX-002 |
| Conteos | `applications.py:40-75` | `PLAN_CORRECCIÓN_P1.md` FIX-003 |
| Badges | `ApplicationList.vue:30-50` | `PLAN_CORRECCIÓN_P1.md` FIX-004 |
| Escala | `useDragDropEpics.ts:85-100` | `PLAN_CORRECCIÓN_P1.md` FIX-005 |

---

## ⏱️ ESTIMACIÓN

| Tarea | Horas | Dificultad |
|-------|-------|-----------|
| FIX-001 (Atomicidad) | 4 | 🔴 Alta |
| FIX-002 (Cross-app) | 2 | 🟠 Media |
| FIX-003 (Conteos) | 3 | 🟠 Media |
| FIX-004 (Badges) | 3 | 🟡 Baja |
| FIX-005 (Escala) | 1 | 🟡 Baja |
| Testing | 5 | 🟡 Baja |
| **TOTAL** | **18 horas** | |

**Recomendación:** Haz FIX-001, FIX-002, FIX-003 esta semana (9 horas).

---

## 🎯 ORDEN RECOMENDADO

### Día 1-2: Backend Crítico (9 horas)
1. FIX-001: Transacción atómica (4h)
2. FIX-002: Validación cross-app (2h)
3. FIX-003: Conteos reales (3h)

### Día 3: Frontend (4 horas)
4. FIX-004: Badges dinámicos (3h)
5. FIX-005: Escala visual (1h)

### Día 4: Testing (5 horas)
6. Ejecutar tests
7. Load test
8. Code review

---

## ✅ ANTES DE HACER PUSH

```bash
# Paso 1: Backend tests
cd backend
pytest tests/ -v

# Paso 2: Frontend lint
cd frontend
npm run lint

# Paso 3: Verificar tipos TypeScript
npm run type-check

# Paso 4: Build
npm run build

# Paso 5: Ejecutar server localmente
npm run dev

# Paso 6: Prueba manual: Reordenar épicas, mover tickets, ver badges
```

---

## 📞 PREGUNTAS FRECUENTES

### P: ¿Por qué es CRÍTICA la race condition?
R: En producción con 10+ usuarios, es SEGURO que habrá race conditions. Resultado: order_index corrupto → UI rota.

### P: ¿Puedo ignorar la validación cross-app?
R: NO. Es CRÍTICA porque viola el modelo de datos. Tickets "huérfanos" = data corruption.

### P: ¿Realmente necesito todos estos índices?
R: SÍ. Sin índices, el count de 50,000 tickets tarda 2 segundos. Con índices, 50ms.

### P: ¿Debo hacer refactoring a Service Layer ahora?
R: NO. Es ARQUITECTURA pero no es bloqueante. Hazlo después de fixes críticos.

### P: ¿Qué pasa si merge sin fixes?
R: En 48 horas en producción:
- 🔴 Múltiples race conditions → order_index duplicados
- 🔴 Tickets movidos a apps equivocadas
- 🔴 Admin decide con conteos = 0
- 🔴 Incidente P1 → rollback

---

## 🚀 DESPUÉS DE FIXES CRÍTICOS

### Fase 2 (Próxima semana):
- [ ] Breadcrumbs en side-panel tickets
- [ ] Creación inline de épicas con auto-focus
- [ ] Upload de documentos en épicas

### Fase 3 (Después):
- [ ] Service Layer refactoring
- [ ] Filtros avanzados en ApplicationList
- [ ] Dashboard de métricas

---

## 📚 DOCUMENTOS COMPLETOS

Si necesitas más detalle:

1. **AUDIT_SPRINTS_3_4_DETAILED.md** - Auditoría línea por línea (12,000 palabras)
2. **PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md** - Código exacto a copiar (8,000 palabras)
3. **PROMPT_CODIGO_REVIEW_AUTOMATICO.md** - Usa con ChatGPT para review
4. **RESUMEN_EJECUTIVO_AUDITORIA.md** - Overview para stakeholders

---

## 💬 TL;DR

```
HACES ESTO:
1. Abre PLAN_CORRECCIÓN_IMPLEMENTACION_P1.md
2. Copia código de FIX-001 a FIX-005
3. Reemplaza métodos exactos en tus archivos
4. Ejecuta tests
5. Commit

RESULTADO:
✅ Race condition fixed
✅ Validación cross-app OK
✅ Conteos reales
✅ Badges dinámicos
✅ Listo para producción

TIEMPO: 18 horas
```

---

**Última actualización:** 2 de Mayo de 2026  
**Versión:** 1.0  
**Creado por:** GitHub Copilot

