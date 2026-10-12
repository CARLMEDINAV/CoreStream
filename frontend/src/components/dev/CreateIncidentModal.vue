<script setup lang="ts">
import { ref, reactive, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import { useDialogStore } from '@/stores/dialog'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits(['close', 'created'])
const dialogStore = useDialogStore()
const { t } = useI18n()
const dialogo = ref<HTMLDialogElement | null>(null)
const isSubmitting = ref(false)
const form = reactive({
  title: '', description: '', categoria: 'general', severity: 'P3',
  affectedEnvironment: 'PRODUCTION', estimatedResolutionTimeSeconds: 3600
})

watch(() => props.show, async abierto => {
  await nextTick()
  if (abierto) dialogo.value?.showModal()
  else dialogo.value?.close()
}, { immediate: true })

const resetForm = () => {
  form.title = ''
  form.description = ''
  form.categoria = 'general'
  form.severity = 'P3'
  form.affectedEnvironment = 'PRODUCTION'
  form.estimatedResolutionTimeSeconds = 3600
}
const handleClose = () => {
  if (isSubmitting.value) return
  resetForm()
  emit('close')
}
const handleSubmit = async () => {
  if (!form.title.trim() || !form.categoria.trim()) return
  isSubmitting.value = true
  try {
    const dataToSubmit = {
      title: form.title.trim(), description: form.description.trim() || undefined,
      categoria: form.categoria.trim(), severity: form.severity,
      affected_environment: form.affectedEnvironment,
      estimated_resolution_time_seconds: form.estimatedResolutionTimeSeconds
    }
    await api.incidents.create(dataToSubmit)
    emit('created')
    resetForm()
    emit('close')
  } catch {
    dialogStore.alert(t('incidencias.errorGuardar'))
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <dialog ref="dialogo" aria-labelledby="titulo-reporte" class="w-full max-w-lg rounded-xl bg-[var(--bg-panel)] p-6 text-[var(--text-primary)] backdrop:bg-black/50" @cancel.prevent="handleClose">
    <form @submit.prevent="handleSubmit" class="space-y-4">
      <h2 id="titulo-reporte" class="text-xl font-bold">{{ t('incidencias.reportar') }}</h2>
      <label class="block">{{ t('incidencias.nombre') }}
        <input v-model="form.title" required maxlength="255" autofocus class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2" />
      </label>
      <label class="block">{{ t('incidencias.descripcion') }}
        <textarea v-model="form.description" maxlength="10000" rows="3" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2"></textarea>
      </label>
      <label class="block">{{ t('incidencias.categoria') }}
        <input v-model="form.categoria" required maxlength="50" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2" />
      </label>
      <label class="block">{{ t('incidencias.severidad') }}
        <select v-model="form.severity" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2">
          <option v-for="severidad in ['P1', 'P2', 'P3']" :key="severidad" :value="severidad">{{ t('incidencias.severidades.' + severidad) }}</option>
        </select>
      </label>
      <label class="block">{{ t('incidencias.entorno') }}
        <select v-model="form.affectedEnvironment" class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2">
          <option v-for="entorno in ['PRODUCTION', 'STAGING', 'DEV']" :key="entorno" :value="entorno">{{ t('incidencias.entornos.' + entorno) }}</option>
        </select>
      </label>
      <label class="block">{{ t('incidencias.tiempo') }}
        <input v-model.number="form.estimatedResolutionTimeSeconds" type="number" min="0" required class="mt-1 w-full rounded border bg-[var(--bg-card)] p-2" />
      </label>
      <footer class="flex justify-end gap-3">
        <button type="button" :disabled="isSubmitting" @click="handleClose">{{ t('incidencias.cancelar') }}</button>
        <button :disabled="isSubmitting" class="rounded bg-red-600 px-4 py-2 text-white">{{ t('incidencias.reportar') }}</button>
      </footer>
    </form>
  </dialog>
</template>
