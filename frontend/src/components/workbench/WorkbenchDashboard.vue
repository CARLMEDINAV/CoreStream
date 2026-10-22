<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import ManageIncidentModal from '@/components/dev/ManageIncidentModal.vue'
import ResumenTrabajo from '@/components/shared/ResumenTrabajo.vue'
import type { Incident, ResumenTrabajo as DatosResumen, Ticket, TrabajoPersonal } from '@/types'

const propiedades = defineProps<{ actualizacion?: number }>()
const emit = defineEmits<{ ticketSelected: [ticket: Ticket] }>()
const { t, locale } = useI18n()
const sesion = useAuthStore()
const trabajos = ref<TrabajoPersonal[]>([])
const resumen = ref<DatosResumen | null>(null)
const cargando = ref(false)
const errorLista = ref(false)
const errorResumen = ref(false)
const errorDetalle = ref(false)
const abriendo = ref(false)
const incidencia = ref<Incident | null>(null)
const tipo = ref('all')
const estado = ref('all')
const fecha = ref('all')
const grupos: Record<string, string[]> = {
  todo: ['TODO', 'REDIRECTED', 'REPORTED', 'ASSIGNED', 'REOPENED'],
  in_progress: ['IN_PROGRESS', 'INVESTIGATING', 'MITIGATED', 'IN_REVIEW'],
  blocked: ['BLOCKED', 'BLOCKED_QUESTION'],
}
const filtrosFecha = ['all', 'overdue', 'today', 'week']
const etiquetasFecha: Record<string, string> = {
  all: 'dateAll', overdue: 'dateOverdue', today: 'dateToday', week: 'dateThisWeek',
}
const estados = computed(() => [...new Set(trabajos.value
  .filter(trabajo => tipo.value === 'all' || trabajo.type === tipo.value)
  .map(trabajo => trabajo.status))])
let consulta = 0
const visibles = computed(() => {
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  const finSemana = new Date(hoy)
  finSemana.setDate(hoy.getDate() + (7 - hoy.getDay()) % 7)
  return trabajos.value.filter(trabajo => {
    if (tipo.value !== 'all' && trabajo.type !== tipo.value) return false
    if (estado.value !== 'all' && !(grupos[estado.value] ?? [estado.value]).includes(trabajo.status)) return false
    if (fecha.value === 'all') return true
    if (!trabajo.due_date) return false
    const vencimiento = new Date(trabajo.due_date)
    vencimiento.setHours(0, 0, 0, 0)
    if (fecha.value === 'overdue') return vencimiento < hoy
    if (fecha.value === 'today') return vencimiento.getTime() === hoy.getTime()
    return vencimiento >= hoy && vencimiento <= finSemana
  })
})

function mostrarFecha(valor: string) {
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(valor))
}

async function actualizar() {
  const usuario = sesion.user?.id
  if (!usuario) return
  const solicitud = ++consulta
  cargando.value = true
  errorLista.value = false
  errorResumen.value = false
  const [lista, estadisticas] = await Promise.allSettled([
    api.users.getWorkbench(), api.users.getStats(usuario),
  ])
  if (solicitud !== consulta) return
  trabajos.value = lista.status === 'fulfilled' ? lista.value : []
  resumen.value = estadisticas.status === 'fulfilled' ? estadisticas.value.work_summary : null
  errorLista.value = lista.status === 'rejected'
  errorResumen.value = estadisticas.status === 'rejected'
  cargando.value = false
}

async function abrir(trabajo: TrabajoPersonal) {
  if (abriendo.value) return
  abriendo.value = true
  errorDetalle.value = false
  try {
    if (trabajo.type === 'ticket') emit('ticketSelected', await api.tickets.getById(trabajo.id))
    else incidencia.value = await api.incidents.getById(trabajo.id)
  } catch {
    errorDetalle.value = true
  } finally {
    abriendo.value = false
  }
}

async function actualizarIncidencia() {
  incidencia.value = null
  await actualizar()
}

watch(tipo, () => { estado.value = 'all' })
watch(() => propiedades.actualizacion, actualizar)
onMounted(actualizar)
</script>

<template>
  <section class="h-full overflow-y-auto bg-[var(--bg-app)] p-4 md:p-6 space-y-5" :aria-label="t('trabajo.personal')" :aria-busy="cargando">
    <div class="flex items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-[var(--text-primary)]">{{ t('trabajo.personal') }}</h2>
      <button type="button" :disabled="cargando" class="px-3 py-2 rounded-lg bg-[var(--lime)] text-[var(--dark-gray)] disabled:opacity-50" @click="actualizar">
        {{ t('workbenchDashboard.refresh') }}
      </button>
    </div>
    <p class="text-sm text-[var(--text-secondary)]">{{ t('trabajo.alcancePersonal') }}</p>
    <p v-if="cargando" role="status">{{ t('common.loading') }}</p>
    <div v-if="errorResumen" role="alert" class="text-red-500">
      {{ t('trabajo.errorResumen') }}
      <button type="button" :disabled="cargando" class="underline" @click="actualizar">{{ t('workbenchDashboard.retry') }}</button>
    </div>
    <ResumenTrabajo v-else-if="resumen && !cargando" :resumen="resumen" />

    <div class="flex flex-wrap gap-3 text-sm text-[var(--text-primary)]">
      <label class="flex flex-col gap-1">
        {{ t('trabajo.tipo') }}
        <select v-model="tipo" class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
          <option value="all">{{ t('workbenchDashboard.statusAll') }}</option>
          <option value="ticket">{{ t('trabajo.tickets') }}</option>
          <option value="incident">{{ t('trabajo.incidents') }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1">
        {{ t('workbenchDashboard.statusLabel') }}
        <select v-model="estado" class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
          <option value="all">{{ t('workbenchDashboard.statusAll') }}</option>
          <optgroup :label="t('trabajo.grupos')">
            <option value="todo">{{ t('trabajo.pendientes') }}</option>
            <option value="in_progress">{{ t('trabajo.in_progress') }}</option>
            <option value="blocked">{{ t('trabajo.blocked') }}</option>
          </optgroup>
          <optgroup :label="t('trabajo.estadoExacto')">
            <option v-for="valor in estados" :key="valor" :value="valor">{{ t('trabajo.estados.' + valor) }}</option>
          </optgroup>
        </select>
      </label>
      <label class="flex flex-col gap-1">
        {{ t('workbenchDashboard.dateLabel') }}
        <select v-model="fecha" class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
          <option v-for="valor in filtrosFecha" :key="valor" :value="valor">{{ t('workbenchDashboard.' + etiquetasFecha[valor]) }}</option>
        </select>
      </label>
      <button type="button" class="self-end p-2 underline" @click="tipo = 'all'; estado = 'all'; fecha = 'all'">{{ t('workbenchDashboard.clearFilters') }}</button>
    </div>
    <p class="text-xs text-[var(--text-muted)]">{{ t('trabajo.orden') }}</p>
    <p v-if="errorDetalle" role="alert" class="text-red-500">{{ t('trabajo.errorDetalle') }}</p>
    <div v-if="errorLista" role="alert" class="text-red-500">
      <p>{{ t('trabajo.errorLista') }}</p>
      <button type="button" :disabled="cargando" class="underline mt-2" @click="actualizar">{{ t('workbenchDashboard.retry') }}</button>
    </div>
    <p v-else-if="!cargando && !visibles.length" role="status" class="py-10 text-center text-[var(--text-muted)]">
      {{ t(trabajos.length ? 'workbenchDashboard.noResults' : 'trabajo.vacio') }}
    </p>
    <ul v-else-if="!cargando" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <li v-for="trabajo in visibles" :key="trabajo.type + trabajo.id">
        <button type="button" :disabled="abriendo" class="h-full w-full text-left rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 hover:border-[var(--teal)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50" @click="abrir(trabajo)">
          <span class="text-xs font-semibold text-[var(--teal)]">{{ t('trabajo.' + trabajo.type) }}</span>
          <h3 class="my-2 font-semibold text-[var(--text-primary)] break-words">{{ trabajo.title }}</h3>
          <p class="text-sm text-[var(--text-secondary)]">{{ t('trabajo.estados.' + trabajo.status) }}</p>
          <p class="mt-3 text-xs text-[var(--text-muted)]">
            {{ t(trabajo.type === 'incident' ? 'trabajo.estimada' : 'trabajo.vencimiento') }}:
            <time v-if="trabajo.due_date" :datetime="trabajo.due_date">{{ mostrarFecha(trabajo.due_date) }}</time>
            <span v-else>{{ t('trabajo.sinFecha') }}</span>
          </p>
        </button>
      </li>
    </ul>
    <ManageIncidentModal :show="incidencia !== null" :incident="incidencia" @close="incidencia = null" @updated="actualizarIncidencia" />
  </section>
</template>
