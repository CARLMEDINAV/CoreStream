<script setup lang="ts">
import { ref, reactive, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { Incident, EventoIncidencia, User } from '@/types'

const props = defineProps<{ show: boolean; incident: Incident | null }>()
const emit = defineEmits(['close', 'updated'])
const { t } = useI18n()
const sesion = useAuthStore()
const dialogo = ref<HTMLDialogElement | null>(null)
const isSubmitting = ref(false)
const avisoError = ref('')
const eventos = ref<EventoIncidencia[]>([])
const responsables = ref<User[]>([])
const comentario = ref('')
const form = reactive({ status: 'REPORTED', mitigationState: '', responsableId: '', categoria: '', severidad: 'P3' })
const puedeGestionar = computed(() => sesion.isAdmin || sesion.isTeamLeader)
const puedeTrabajar = computed(() => puedeGestionar.value || props.incident?.assignedToId === sesion.user?.id)
const cambios: Record<string, string[]> = {
  REPORTED: ['INVESTIGATING'], ASSIGNED: ['INVESTIGATING'],
  INVESTIGATING: ['MITIGATED', 'IN_REVIEW'], MITIGATED: ['INVESTIGATING', 'IN_REVIEW'],
  IN_REVIEW: ['INVESTIGATING', 'RESOLVED'], RESOLVED: ['CLOSED', 'REOPENED'],
  CLOSED: ['REOPENED'], REOPENED: ['INVESTIGATING']
}
const siguientes = computed(() => {
  if (!props.incident || !puedeTrabajar.value) return []
  return (cambios[props.incident.status] || []).filter(estado =>
    (puedeGestionar.value || !['RESOLVED', 'CLOSED', 'REOPENED'].includes(estado)) &&
    (estado !== 'INVESTIGATING' || props.incident?.assignedToId)
  )
})
let numeroCarga = 0
watch(() => props.incident, async newInc => {
  const cargaActual = ++numeroCarga
  eventos.value = []
  avisoError.value = ''
  comentario.value = ''
  if (!newInc) return
  form.status = newInc.status
  form.mitigationState = newInc.mitigationState || ''
  form.responsableId = newInc.assignedToId || ''
  form.categoria = newInc.categoria
  form.severidad = newInc.severity
  try {
    const [historial, equipo] = await Promise.all([
      api.incidents.eventos(newInc.id),
      puedeGestionar.value ? api.team.list() : Promise.resolve([])
    ])
    if (cargaActual !== numeroCarga) return
    eventos.value = historial
    responsables.value = equipo.filter(persona => persona.isActive && ['DEVELOPER', 'TEAM_LEADER'].includes(persona.role))
  } catch {
    if (cargaActual === numeroCarga) avisoError.value = t('incidencias.errorCarga')
  }
}, { immediate: true })

watch(() => props.show, async abierto => {
  await nextTick()
  if (abierto) dialogo.value?.showModal()
  else dialogo.value?.close()
}, { immediate: true })

const handleClose = () => { if (!isSubmitting.value) emit('close') }

const handleSubmit = async () => {
  if (!props.incident || isSubmitting.value) return
  isSubmitting.value = true
  avisoError.value = ''
  try {
    const datos: Record<string, unknown> = { mitigation_state: form.mitigationState }
    if (puedeGestionar.value) {
      datos.categoria = form.categoria
      datos.severity = form.severidad
      if (form.responsableId !== (props.incident.assignedToId || '')) {
        datos.assigned_to_id = form.responsableId || null
      }
    }
    await api.incidents.update(props.incident.id, datos)
    emit('updated')
  } catch {
    avisoError.value = t('incidencias.errorGuardar')
  } finally {
    isSubmitting.value = false
  }
}

const cambiarEstado = async (estado: string) => {
  if (!props.incident || isSubmitting.value) return
  isSubmitting.value = true
  avisoError.value = ''
  try {
    await api.incidents.updateStatus(props.incident.id, estado)
    emit('updated')
  } catch {
    avisoError.value = t('incidencias.errorGuardar')
  } finally {
    isSubmitting.value = false
  }
}

const enviarComentario = async () => {
  if (!props.incident || !comentario.value.trim() || isSubmitting.value) return
  isSubmitting.value = true
  avisoError.value = ''
  try {
    await api.incidents.comentar(props.incident.id, comentario.value.trim())
    comentario.value = ''
    eventos.value = await api.incidents.eventos(props.incident.id)
  } catch {
    avisoError.value = t('incidencias.errorGuardar')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <dialog ref="dialogo" aria-labelledby="titulo-incidencia" class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-[var(--bg-panel)] p-6 text-[var(--text-primary)] backdrop:bg-black/50" @cancel.prevent="handleClose">
    <div v-if="incident" class="space-y-4">
      <header class="flex items-start justify-between gap-3">
        <div>
          <h2 id="titulo-incidencia" class="text-xl font-bold">{{ incident.title }}</h2>
          <p class="text-xs">{{ incident.id }}</p>
        </div>
        <button :disabled="isSubmitting" @click="handleClose">{{ t('incidencias.cerrar') }}</button>
      </header>
      <p class="whitespace-pre-wrap">{{ incident.description }}</p>
      <p>{{ t('incidencias.estados.' + incident.status) }} · {{ t('incidencias.severidades.' + incident.severity) }} · {{ incident.categoria }}</p>
      <p v-if="avisoError" role="alert" class="text-red-500">{{ avisoError }}</p>

      <form v-if="puedeTrabajar" @submit.prevent="handleSubmit" class="space-y-3">
        <template v-if="puedeGestionar">
          <label class="block">{{ t('incidencias.responsable') }}
            <select v-model="form.responsableId" :disabled="['RESOLVED', 'CLOSED'].includes(incident.status)" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2">
              <option value="">{{ t('incidencias.sinAsignar') }}</option>
              <option v-if="incident.assignedToId && !responsables.some(persona => persona.id === incident?.assignedToId)" :value="incident.assignedToId">{{ incident.assignedToId }}</option>
              <option v-for="persona in responsables" :key="persona.id" :value="persona.id">{{ persona.fullName }}</option>
            </select>
          </label>
          <label class="block">{{ t('incidencias.categoria') }}
            <input v-model="form.categoria" maxlength="50" required class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2" />
          </label>
          <label class="block">{{ t('incidencias.severidad') }}
            <select v-model="form.severidad" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2">
              <option v-for="severidad in ['P1', 'P2', 'P3']" :key="severidad" :value="severidad">{{ t('incidencias.severidades.' + severidad) }}</option>
            </select>
          </label>
        </template>
        <label class="block">{{ t('incidencias.notas') }}
          <textarea v-model="form.mitigationState" maxlength="10000" rows="3" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2"></textarea>
        </label>
        <button :disabled="isSubmitting" class="rounded border px-4 py-2">{{ t('incidencias.guardar') }}</button>
      </form>
      <p v-else-if="incident.mitigationState" class="whitespace-pre-wrap">{{ incident.mitigationState }}</p>

      <div class="flex flex-wrap gap-2">
        <button v-for="estado in siguientes" :key="estado" :disabled="isSubmitting" @click="cambiarEstado(estado)"
          class="rounded bg-teal-700 px-3 py-2 text-white">{{ t('incidencias.acciones.' + estado) }}</button>
      </div>

      <section>
        <h3 class="font-semibold">{{ t('incidencias.historial') }}</h3>
        <p v-if="!eventos.length">{{ t('incidencias.sinHistorial') }}</p>
        <ol class="space-y-3 py-3">
          <li v-for="evento in eventos" :key="evento.id" class="border-l-2 border-teal-500 pl-3 text-sm">
            <p>{{ evento.autor_nombre }} · {{ new Date(evento.created_at).toLocaleString() }}</p>
            <p>{{ t('incidencias.eventos.' + evento.tipo) }}</p>
            <p v-if="evento.estado_anterior !== evento.estado_nuevo && evento.estado_nuevo">
              <template v-if="evento.estado_anterior">{{ t('incidencias.estados.' + evento.estado_anterior) }} → </template>
              {{ t('incidencias.estados.' + evento.estado_nuevo) }}
            </p>
            <p v-if="evento.comentario" class="whitespace-pre-wrap">{{ evento.comentario }}</p>
          </li>
        </ol>
      </section>
      <form @submit.prevent="enviarComentario" class="space-y-2">
        <label class="block">{{ t('incidencias.comentario') }}
          <textarea v-model="comentario" maxlength="10000" required rows="2" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2"></textarea>
        </label>
        <button :disabled="isSubmitting || !comentario.trim()" class="rounded border px-4 py-2">{{ t('incidencias.enviar') }}</button>
      </form>
    </div>
  </dialog>
</template>
