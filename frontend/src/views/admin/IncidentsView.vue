<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { Incident } from '@/types'
import CreateIncidentModal from '@/components/dev/CreateIncidentModal.vue'
import ManageIncidentModal from '@/components/dev/ManageIncidentModal.vue'
import AppHeader from '@/components/layout/AppHeader.vue'

const authStore = useAuthStore()
const ruta = useRoute()
const navegador = useRouter()
const { t } = useI18n()
const incidents = ref<Incident[]>([])
const isLoading = ref(true)
const showCreateModal = ref(false)
const showManageModal = ref(false)
const selectedIncident = ref<Incident | null>(null)
const avisoError = ref('')
const pendientesAtencion = ref<Incident[]>([])
const hayMas = ref(false)
let numeroApertura = 0
const puedeGestionar = computed(() => authStore.isAdmin || authStore.isTeamLeader)
const activeIncidents = computed(() => incidents.value.filter(i => !i.isMitigated))
const pastIncidents = computed(() => incidents.value.filter(i => i.isMitigated))

const openManageModal = (incident: Incident) => {
  navegador.push({ query: { ...ruta.query, incidentId: incident.id } })
}

const loadIncidents = async (agregar = false) => {
  isLoading.value = true
  avisoError.value = ''
  try {
    const response = await api.incidents.list({ limit: 100, skip: agregar ? incidents.value.length : 0 })
    incidents.value = agregar ? [...incidents.value, ...response.items] : response.items
    hayMas.value = response.items.length === 100
    if (puedeGestionar.value) {
      pendientesAtencion.value = (await api.incidents.list({ atencion: true, limit: 100 })).items
    }
  } catch {
    avisoError.value = t('incidencias.errorCarga')
  } finally {
    isLoading.value = false
  }
}

const abrirDesdeEnlace = async () => {
  const aperturaActual = ++numeroApertura
  const identificador = ruta.query.incidentId
  selectedIncident.value = null
  showManageModal.value = false
  if (typeof identificador !== 'string') return
  try {
    const incidencia = await api.incidents.getById(identificador)
    if (aperturaActual !== numeroApertura) return
    selectedIncident.value = incidencia
    showManageModal.value = true
    avisoError.value = ''
  } catch {
    if (aperturaActual === numeroApertura) avisoError.value = t('incidencias.errorAbrir')
  }
}

const cerrarDetalle = () => {
  showManageModal.value = false
  const consulta = { ...ruta.query }
  delete consulta.incidentId
  navegador.replace({ query: consulta })
}

const actualizarDetalle = async () => {
  await loadIncidents()
  await abrirDesdeEnlace()
}

watch(() => ruta.query.incidentId, abrirDesdeEnlace, { immediate: true })
onMounted(() => loadIncidents())
</script>

<template>
  <div class="h-full bg-[var(--bg-body)] text-[var(--text-primary)]">
    <AppHeader />
    <main class="space-y-6 p-6">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-2xl font-bold">{{ t('incidencias.titulo') }}</h1>
        <div class="flex gap-3">
          <button class="rounded bg-red-600 px-4 py-2 text-white" @click="showCreateModal = true">{{ t('incidencias.reportar') }}</button>
          <button class="rounded border px-4 py-2" :disabled="isLoading" @click="loadIncidents()">{{ t('incidencias.actualizar') }}</button>
        </div>
      </header>
      <p v-if="avisoError" role="alert" class="text-red-500">{{ avisoError }}</p>
      <section v-if="puedeGestionar" class="rounded border border-red-400 p-4">
        <h2 class="mb-2 font-semibold">{{ t('incidencias.atencion') }}</h2>
        <p v-if="!pendientesAtencion.length">{{ t('incidencias.sinUrgentes') }}</p>
        <button v-for="incidencia in pendientesAtencion" :key="incidencia.id"
          class="block py-1 text-left underline" @click="openManageModal(incidencia)">
          {{ incidencia.severity }} · {{ incidencia.title }}
        </button>
      </section>
      <p v-if="isLoading" role="status">{{ t('avisos.cargando') }}</p>
      <section v-for="grupo in [{ titulo: 'activas', lista: activeIncidents }, { titulo: 'cerradas', lista: pastIncidents }]" :key="grupo.titulo">
        <h2 class="mb-3 text-lg font-semibold">{{ t('incidencias.' + grupo.titulo) }}</h2>
        <p v-if="!grupo.lista.length && !isLoading">{{ t('incidencias.vacio') }}</p>
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <article v-for="incident in grupo.lista" :key="incident.id" class="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-panel)] p-4">
            <p class="text-sm">{{ t('incidencias.severidades.' + incident.severity) }} · {{ incident.categoria }}</p>
            <h3 class="my-2 font-semibold">{{ incident.title }}</h3>
            <p class="line-clamp-2 text-sm">{{ incident.description }}</p>
            <p class="my-2 text-sm">{{ t('incidencias.estados.' + incident.status) }}</p>
            <button class="underline" @click="openManageModal(incident)">{{ t('incidencias.detalle') }}</button>
          </article>
        </div>
      </section>
      <button v-if="hayMas" :disabled="isLoading" class="rounded border px-4 py-2" @click="loadIncidents(true)">{{ t('avisos.mas') }}</button>
    </main>
    <CreateIncidentModal :show="showCreateModal" @close="showCreateModal = false" @created="loadIncidents()" />
    <ManageIncidentModal :show="showManageModal" :incident="selectedIncident" @close="cerrarDetalle" @updated="actualizarDetalle" />
  </div>
</template>
