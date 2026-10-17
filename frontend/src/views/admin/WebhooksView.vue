<script setup lang="ts">
/**
 * WebhooksView - Gestión de integraciones salientes (NEW-12)
 *
 * Sólo ADMIN (la ruta /admin/webhooks lo exige). Permite configurar webhooks
 * por proyecto y/o por tipo de evento, ver el historial de entregas con sus
 * reintentos y enviar un evento de prueba.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Webhook as WebhookIcon,
  XCircle,
} from 'lucide-vue-next'
import { api } from '@/services/api'
import type {
  Application,
  Webhook,
  WebhookDelivery,
  WebhookEventTypeOption,
} from '@/types'
import AppHeader from '@/components/layout/AppHeader.vue'

const { t } = useI18n()

const webhooks = ref<Webhook[]>([])
const eventTypes = ref<WebhookEventTypeOption[]>([])
const applications = ref<Application[]>([])
const isLoading = ref(true)
const loadError = ref(false)

const showForm = ref(false)
const editing = ref<Webhook | null>(null)
const isSaving = ref(false)
const form = ref({
  name: '',
  url: '',
  eventTypes: [] as string[],
  projectId: '' as string,
  isActive: true,
})

const secretRevealed = ref<string | null>(null)

const expandedId = ref<string | null>(null)
const deliveries = ref<Record<string, WebhookDelivery[]>>({})
const loadingDeliveries = ref<string | null>(null)

const eventLabel = (value: string) =>
  eventTypes.value.find((e) => e.value === value)?.label ?? value

const loadAll = async () => {
  isLoading.value = true
  loadError.value = false
  try {
    const [hooks, types, apps] = await Promise.all([
      api.webhooks.list(),
      api.webhooks.eventTypes(),
      api.applications.list(),
    ])
    webhooks.value = hooks
    eventTypes.value = types
    applications.value = apps
  } catch (error) {
    console.error('Error cargando webhooks:', error)
    loadError.value = true
  } finally {
    isLoading.value = false
  }
}

const openCreate = () => {
  editing.value = null
  form.value = { name: '', url: '', eventTypes: [], projectId: '', isActive: true }
  secretRevealed.value = null
  showForm.value = true
}

const openEdit = (webhook: Webhook) => {
  editing.value = webhook
  form.value = {
    name: webhook.name,
    url: webhook.url,
    eventTypes: [...webhook.eventTypes],
    projectId: webhook.projectId ?? '',
    isActive: webhook.isActive,
  }
  secretRevealed.value = null
  showForm.value = true
}

const toggleEventType = (value: string) => {
  const list = form.value.eventTypes
  const index = list.indexOf(value)
  if (index >= 0) list.splice(index, 1)
  else list.push(value)
}

const save = async () => {
  if (!form.value.name.trim() || !form.value.url.trim()) return
  isSaving.value = true
  try {
    if (editing.value) {
      const updated = await api.webhooks.update(editing.value.id, {
        name: form.value.name,
        url: form.value.url,
        eventTypes: form.value.eventTypes,
        projectId: form.value.projectId || null,
        isActive: form.value.isActive,
      })
      const index = webhooks.value.findIndex((w) => w.id === updated.id)
      if (index >= 0) webhooks.value[index] = updated
    } else {
      const created = await api.webhooks.create({
        name: form.value.name,
        url: form.value.url,
        eventTypes: form.value.eventTypes,
        projectId: form.value.projectId || undefined,
        isActive: form.value.isActive,
      })
      webhooks.value.unshift(created)
      // El secreto sólo se muestra una vez, al crear.
      if (created.secret) secretRevealed.value = created.secret
    }
    showForm.value = false
  } catch (error) {
    console.error('Error guardando webhook:', error)
    alert(t('webhooksView.saveError'))
  } finally {
    isSaving.value = false
  }
}

const remove = async (webhook: Webhook) => {
  if (!confirm(t('webhooksView.deleteConfirm', { name: webhook.name }))) return
  try {
    await api.webhooks.remove(webhook.id)
    webhooks.value = webhooks.value.filter((w) => w.id !== webhook.id)
  } catch (error) {
    console.error('Error eliminando webhook:', error)
  }
}

const rotate = async (webhook: Webhook) => {
  if (!confirm(t('webhooksView.rotateConfirm', { name: webhook.name }))) return
  try {
    secretRevealed.value = await api.webhooks.rotateSecret(webhook.id)
  } catch (error) {
    console.error('Error rotando secreto:', error)
  }
}

const sendTest = async (webhook: Webhook) => {
  try {
    await api.webhooks.test(webhook.id)
    if (expandedId.value === webhook.id) await loadDeliveries(webhook.id)
  } catch (error) {
    console.error('Error enviando prueba:', error)
  }
}

const toggleActive = async (webhook: Webhook) => {
  try {
    const updated = await api.webhooks.update(webhook.id, { isActive: !webhook.isActive })
    const index = webhooks.value.findIndex((w) => w.id === updated.id)
    if (index >= 0) webhooks.value[index] = updated
  } catch (error) {
    console.error('Error cambiando estado:', error)
  }
}

const loadDeliveries = async (webhookId: string) => {
  loadingDeliveries.value = webhookId
  try {
    deliveries.value[webhookId] = await api.webhooks.deliveries(webhookId)
  } catch (error) {
    console.error('Error cargando entregas:', error)
  } finally {
    loadingDeliveries.value = null
  }
}

const toggleDeliveries = async (webhook: Webhook) => {
  if (expandedId.value === webhook.id) {
    expandedId.value = null
    return
  }
  expandedId.value = webhook.id
  await loadDeliveries(webhook.id)
}

const retryDelivery = async (webhookId: string, delivery: WebhookDelivery) => {
  try {
    await api.webhooks.retryDelivery(delivery.id)
    await loadDeliveries(webhookId)
  } catch (error) {
    console.error('Error reintentando entrega:', error)
  }
}

const projectName = (projectId?: string) =>
  applications.value.find((a) => a.id === projectId)?.name ?? t('webhooksView.allProjects')

const statusClass = (status?: string) => {
  if (status === 'SUCCESS') return 'text-green-600 dark:text-green-400'
  if (status === 'FAILED') return 'text-red-600 dark:text-red-400'
  return 'text-amber-600 dark:text-amber-400'
}

const deliveryStatusIcon = (status: string) => {
  if (status === 'SUCCESS') return CheckCircle2
  if (status === 'FAILED') return XCircle
  return Clock
}

const formatDate = (value?: string) => (value ? new Date(value).toLocaleString() : '—')

const activeCount = computed(() => webhooks.value.filter((w) => w.isActive).length)

onMounted(loadAll)
</script>

<template>
  <div class="h-full bg-slate-50 dark:bg-[var(--bg-body)]">
    <AppHeader />

    <header class="bg-white dark:bg-[var(--bg-panel)] border-b border-slate-200 dark:border-[var(--border-subtle)] px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-900 dark:text-[var(--text-primary)] flex items-center gap-2">
          <WebhookIcon class="text-[var(--teal)]" :size="28" />
          {{ t('webhooksView.title') }}
        </h1>
        <p class="text-sm text-slate-500 dark:text-[var(--text-muted)] mt-1">
          {{ t('webhooksView.subtitle') }}
        </p>
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="openCreate"
          class="px-4 py-2 bg-[var(--teal)] hover:opacity-90 text-white font-medium rounded-lg transition-colors flex items-center gap-2 shadow-sm"
        >
          <Plus :size="18" /> {{ t('webhooksView.createButton') }}
        </button>
        <button
          @click="loadAll"
          :disabled="isLoading"
          class="px-4 py-2 bg-slate-100 dark:bg-[var(--bg-card)] text-slate-700 dark:text-[var(--text-secondary)] font-medium rounded-lg hover:bg-slate-200 dark:hover:bg-[var(--border-subtle)] transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          <RefreshCw :size="16" /> {{ t('webhooksView.refresh') }}
        </button>
      </div>
    </header>

    <div class="p-6 overflow-y-auto" style="height: calc(100vh - 89px);">
      <div v-if="isLoading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--teal)]"></div>
      </div>

      <div v-else-if="loadError" class="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 rounded-xl p-6 flex items-center gap-3">
        <AlertTriangle class="text-red-500" :size="20" />
        <span class="text-red-700 dark:text-red-400">{{ t('webhooksView.loadError') }}</span>
      </div>

      <div v-else class="space-y-6">
        <div class="flex items-center gap-3 text-sm text-slate-600 dark:text-[var(--text-secondary)]">
          <span>{{ t('webhooksView.activeCount', { count: activeCount, total: webhooks.length }) }}</span>
        </div>

        <div v-if="webhooks.length === 0" class="bg-white dark:bg-[var(--bg-panel)] border border-dashed border-slate-300 dark:border-[var(--border-subtle)] rounded-xl p-10 text-center">
          <WebhookIcon class="mx-auto text-slate-400 mb-3" :size="40" />
          <p class="text-slate-600 dark:text-[var(--text-secondary)]">{{ t('webhooksView.empty') }}</p>
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="webhook in webhooks"
            :key="webhook.id"
            class="bg-white dark:bg-[var(--bg-panel)] rounded-xl border border-slate-200 dark:border-[var(--border-subtle)] shadow-sm overflow-hidden"
          >
            <div class="p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <h3 class="text-lg font-bold text-slate-900 dark:text-white truncate">{{ webhook.name }}</h3>
                  <span
                    class="text-xs px-2 py-0.5 rounded-full font-semibold"
                    :class="webhook.isActive ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'"
                  >
                    {{ webhook.isActive ? t('webhooksView.active') : t('webhooksView.inactive') }}
                  </span>
                  <span v-if="webhook.lastStatus" class="text-xs font-semibold" :class="statusClass(webhook.lastStatus)">
                    {{ webhook.lastStatus }}
                  </span>
                </div>
                <p class="text-sm text-slate-500 dark:text-[var(--text-muted)] mt-1 truncate">{{ webhook.url }}</p>
                <div class="flex flex-wrap gap-2 mt-3 text-xs">
                  <span class="px-2 py-1 rounded-md bg-slate-100 dark:bg-[var(--bg-card)] text-slate-600 dark:text-[var(--text-secondary)]">
                    {{ t('webhooksView.project') }}: {{ projectName(webhook.projectId) }}
                  </span>
                  <span class="px-2 py-1 rounded-md bg-slate-100 dark:bg-[var(--bg-card)] text-slate-600 dark:text-[var(--text-secondary)]">
                    {{ webhook.eventTypes.length === 0 ? t('webhooksView.allEvents') : webhook.eventTypes.map(eventLabel).join(', ') }}
                  </span>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <button @click="toggleActive(webhook)" class="px-3 py-2 text-sm rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] hover:bg-slate-200 dark:hover:bg-[var(--border-subtle)] transition-colors">
                  {{ webhook.isActive ? t('webhooksView.deactivate') : t('webhooksView.activate') }}
                </button>
                <button @click="sendTest(webhook)" :title="t('webhooksView.test')" class="p-2 rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] hover:bg-slate-200 dark:hover:bg-[var(--border-subtle)] transition-colors">
                  <Send :size="16" />
                </button>
                <button @click="rotate(webhook)" :title="t('webhooksView.rotate')" class="p-2 rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] hover:bg-slate-200 dark:hover:bg-[var(--border-subtle)] transition-colors">
                  <KeyRound :size="16" />
                </button>
                <button @click="openEdit(webhook)" :title="t('webhooksView.edit')" class="p-2 rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] hover:bg-slate-200 dark:hover:bg-[var(--border-subtle)] transition-colors">
                  <Pencil :size="16" />
                </button>
                <button @click="remove(webhook)" :title="t('webhooksView.delete')" class="p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100 transition-colors">
                  <Trash2 :size="16" />
                </button>
              </div>
            </div>

            <div class="border-t border-slate-100 dark:border-[var(--border-subtle)] px-5 py-2 bg-slate-50 dark:bg-[var(--bg-card)] flex items-center justify-between">
              <span class="text-xs text-slate-500 dark:text-[var(--text-muted)]">
                {{ t('webhooksView.lastTriggered') }}: {{ formatDate(webhook.lastTriggeredAt) }}
              </span>
              <button @click="toggleDeliveries(webhook)" class="text-sm font-medium text-[var(--teal)] flex items-center gap-1 hover:underline">
                <component :is="expandedId === webhook.id ? ChevronDown : ChevronRight" :size="16" />
                {{ t('webhooksView.deliveries') }}
              </button>
            </div>

            <div v-if="expandedId === webhook.id" class="border-t border-slate-100 dark:border-[var(--border-subtle)] p-4">
              <div v-if="loadingDeliveries === webhook.id" class="text-sm text-slate-500 py-4 text-center">
                {{ t('webhooksView.loading') }}
              </div>
              <div v-else-if="(deliveries[webhook.id] || []).length === 0" class="text-sm text-slate-500 py-4 text-center">
                {{ t('webhooksView.noDeliveries') }}
              </div>
              <div v-else class="space-y-2">
                <div
                  v-for="delivery in deliveries[webhook.id]"
                  :key="delivery.id"
                  class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm bg-slate-50 dark:bg-[var(--bg-card)] rounded-lg px-3 py-2"
                >
                  <div class="flex items-center gap-3 min-w-0">
                    <component :is="deliveryStatusIcon(delivery.status)" :size="16" :class="statusClass(delivery.status)" />
                    <span class="font-medium text-slate-700 dark:text-slate-200">{{ delivery.eventType }}</span>
                    <span class="text-xs text-slate-500 dark:text-[var(--text-muted)]">
                      {{ t('webhooksView.attempts') }}: {{ delivery.attemptCount }}
                    </span>
                    <span v-if="delivery.responseStatus" class="text-xs text-slate-500 dark:text-[var(--text-muted)]">
                      HTTP {{ delivery.responseStatus }}
                    </span>
                    <span v-if="delivery.error" class="text-xs text-red-500 truncate max-w-[220px]">{{ delivery.error }}</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="text-xs text-slate-500 dark:text-[var(--text-muted)]">{{ formatDate(delivery.createdAt) }}</span>
                    <button
                      v-if="delivery.status === 'FAILED'"
                      @click="retryDelivery(webhook.id, delivery)"
                      class="text-xs font-medium text-[var(--teal)] hover:underline"
                    >
                      {{ t('webhooksView.retry') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de creación / edición -->
    <div v-if="showForm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-white dark:bg-[var(--bg-panel)] rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-200 dark:border-[var(--border-subtle)]">
          <h2 class="text-lg font-bold text-slate-900 dark:text-white">
            {{ editing ? t('webhooksView.editTitle') : t('webhooksView.createTitle') }}
          </h2>
        </div>

        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">{{ t('webhooksView.name') }}</label>
            <input v-model="form.name" type="text" class="w-full rounded-lg border border-slate-300 dark:border-[var(--border-subtle)] bg-white dark:bg-[var(--bg-card)] px-3 py-2 text-slate-900 dark:text-white" />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">{{ t('webhooksView.url') }}</label>
            <input v-model="form.url" type="url" placeholder="https://hooks.example.com/..." class="w-full rounded-lg border border-slate-300 dark:border-[var(--border-subtle)] bg-white dark:bg-[var(--bg-card)] px-3 py-2 text-slate-900 dark:text-white" />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">{{ t('webhooksView.project') }}</label>
            <select v-model="form.projectId" class="w-full rounded-lg border border-slate-300 dark:border-[var(--border-subtle)] bg-white dark:bg-[var(--bg-card)] px-3 py-2 text-slate-900 dark:text-white">
              <option value="">{{ t('webhooksView.allProjects') }}</option>
              <option v-for="app in applications" :key="app.id" :value="app.id">{{ app.name }}</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">{{ t('webhooksView.events') }}</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in eventTypes"
                :key="option.value"
                type="button"
                @click="toggleEventType(option.value)"
                class="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
                :class="form.eventTypes.includes(option.value)
                  ? 'bg-[var(--teal)] text-white border-[var(--teal)]'
                  : 'bg-slate-100 dark:bg-[var(--bg-card)] text-slate-600 dark:text-[var(--text-secondary)] border-slate-200 dark:border-[var(--border-subtle)]'"
              >
                {{ option.label }}
              </button>
            </div>
            <p class="text-xs text-slate-500 dark:text-[var(--text-muted)] mt-2">{{ t('webhooksView.allEventsHint') }}</p>
          </div>

          <label class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input v-model="form.isActive" type="checkbox" class="rounded" />
            {{ t('webhooksView.active') }}
          </label>
        </div>

        <div class="px-6 py-4 border-t border-slate-200 dark:border-[var(--border-subtle)] flex justify-end gap-3">
          <button @click="showForm = false" class="px-4 py-2 rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] text-slate-700 dark:text-[var(--text-secondary)]">
            {{ t('webhooksView.cancel') }}
          </button>
          <button @click="save" :disabled="isSaving" class="px-4 py-2 rounded-lg bg-[var(--teal)] text-white font-medium disabled:opacity-50">
            {{ isSaving ? t('webhooksView.saving') : t('webhooksView.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Secreto mostrado una única vez -->
    <div v-if="secretRevealed" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-white dark:bg-[var(--bg-panel)] rounded-xl shadow-xl w-full max-w-lg p-6">
        <h2 class="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <KeyRound class="text-[var(--teal)]" :size="20" /> {{ t('webhooksView.secretOnce') }}
        </h2>
        <p class="text-sm text-slate-600 dark:text-[var(--text-secondary)] mt-2">{{ t('webhooksView.secretHelp') }}</p>
        <code class="block mt-4 p-3 rounded-lg bg-slate-100 dark:bg-[var(--bg-card)] text-sm break-all text-slate-800 dark:text-slate-200">{{ secretRevealed }}</code>
        <div class="flex justify-end mt-6">
          <button @click="secretRevealed = null" class="px-4 py-2 rounded-lg bg-[var(--teal)] text-white font-medium">
            {{ t('webhooksView.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
