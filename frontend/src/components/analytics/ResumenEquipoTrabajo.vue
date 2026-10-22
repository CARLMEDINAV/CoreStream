<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import ResumenTrabajo from '@/components/shared/ResumenTrabajo.vue'
import type { ResumenTrabajo as DatosResumen } from '@/types'

const { t } = useI18n()
const resumen = ref<DatosResumen | null>(null)
const cargando = ref(false)
const error = ref(false)

async function actualizar() {
  if (cargando.value) return
  cargando.value = true
  error.value = false
  try {
    resumen.value = await api.analytics.getWorkSummary()
  } catch {
    resumen.value = null
    error.value = true
  } finally {
    cargando.value = false
  }
}

onMounted(actualizar)
</script>

<template>
  <section class="mb-6 rounded-xl border border-[var(--border-subtle)] p-5" :aria-label="t('trabajo.equipo')" :aria-busy="cargando">
    <div class="flex items-center justify-between gap-3 mb-2">
      <h2 class="text-lg font-semibold text-[var(--text-primary)]">{{ t('trabajo.equipo') }}</h2>
      <button type="button" :disabled="cargando" class="px-3 py-2 rounded-lg bg-[var(--lime)] text-[var(--dark-gray)] disabled:opacity-50" @click="actualizar">
        {{ t('workbenchDashboard.refresh') }}
      </button>
    </div>
    <p class="mb-4 text-sm text-[var(--text-secondary)]">{{ t('trabajo.alcanceEquipo') }}</p>
    <p v-if="cargando" role="status">{{ t('common.loading') }}</p>
    <div v-else-if="error" role="alert" class="text-red-500">
      <p>{{ t('trabajo.errorResumen') }}</p>
      <button type="button" class="underline mt-2" @click="actualizar">{{ t('workbenchDashboard.retry') }}</button>
    </div>
    <ResumenTrabajo v-else-if="resumen" :resumen="resumen" />
  </section>
</template>
