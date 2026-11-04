<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/services/api'
import { platformMessages } from '@/i18n/platform'

interface Cliente {
  id: string; name: string; is_active: boolean; plan: string
  feature_overrides: Record<string, boolean>; feature_flags: Record<string, boolean>
}
interface Cambio {
  id: string; date: string; actor: string
  detail: { before: unknown; after: unknown }
}
const { locale } = useI18n()
const textos = computed(() => platformMessages[locale.value] ?? platformMessages.es)
const clientes = ref<Cliente[]>([])
const seleccionado = ref('')
const cliente = computed(() => clientes.value.find(item => item.id === seleccionado.value))
const plan = ref('Basico')
const banderas = ref<Record<string, string>>({})
const uso = ref<{ since: string; requests: Record<string, number> } | null>(null)
const cambios = ref<Cambio[]>([])
const dias = ref(30)
const pagina = ref(0)
const ocupado = ref(false)
const error = ref('')
const mensaje = ref('')

async function consultar() {
  if (!cliente.value) return
  const [consumo, historial] = await Promise.all([
    apiClient.get(`/platform/clients/${seleccionado.value}/usage`, { params: { days: dias.value } }),
    apiClient.get(`/platform/clients/${seleccionado.value}/changes`),
  ])
  uso.value = consumo.data
  cambios.value = historial.data
}

async function elegir() {
  error.value = ''; mensaje.value = ''; uso.value = null; cambios.value = []
  if (!cliente.value) return
  plan.value = cliente.value.plan
  banderas.value = Object.fromEntries(Object.keys(cliente.value.feature_flags).map(bandera => [
    bandera, bandera in cliente.value!.feature_overrides ? String(cliente.value!.feature_overrides[bandera]) : '',
  ]))
  ocupado.value = true
  try { await consultar() } catch { error.value = textos.value.error }
  finally { ocupado.value = false }
}

async function cargar(destino = 0) {
  ocupado.value = true; error.value = ''; mensaje.value = ''
  try {
    const respuesta = await apiClient.get('/platform/clients', { params: { offset: destino * 50, limit: 50 } })
    clientes.value = respuesta.data
    pagina.value = destino
    seleccionado.value = clientes.value[0]?.id ?? ''
    await elegir()
  } catch { error.value = textos.value.error }
  finally { ocupado.value = false }
}

async function guardar() {
  if (!cliente.value) return
  ocupado.value = true; error.value = ''; mensaje.value = ''
  try {
    const excepciones = Object.fromEntries(Object.entries(banderas.value)
      .filter(([, valor]) => valor !== '').map(([bandera, valor]) => [bandera, valor === 'true']))
    const respuesta = await apiClient.put(`/platform/clients/${seleccionado.value}`, {
      plan: plan.value, feature_overrides: excepciones,
    })
    clientes.value = clientes.value.map(item => item.id === seleccionado.value ? respuesta.data : item)
    mensaje.value = textos.value.saved
    await consultar()
  } catch { error.value = textos.value.error }
  finally { ocupado.value = false }
}
async function actualizarUso() {
  ocupado.value = true; error.value = ''
  try { await consultar() } catch { error.value = textos.value.error }
  finally { ocupado.value = false }
}
onMounted(() => cargar())
</script>

<template>
  <main class="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)] p-6">
    <div class="max-w-4xl mx-auto space-y-6">
      <RouterLink to="/" class="text-[var(--teal)]">{{ textos.back }}</RouterLink>
      <h1 class="text-2xl font-bold">Alloxentric · {{ textos.title }}</h1>
      <p v-if="error" role="alert" class="text-red-600">{{ error }}</p>
      <p v-if="mensaje" role="status">{{ mensaje }}</p>
      <p v-if="ocupado" role="status">{{ textos.loading }}</p>
      <fieldset :disabled="ocupado" class="space-y-4">
        <label class="block">{{ textos.client }}
          <select v-model="seleccionado" class="campo w-full" @change="elegir">
            <option v-for="item in clientes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <div class="flex gap-4">
          <button :disabled="pagina === 0" class="boton" @click="cargar(pagina - 1)">{{ textos.previous }}</button>
          <button :disabled="clientes.length < 50" class="boton" @click="cargar(pagina + 1)">{{ textos.next }}</button>
        </div>
        <p v-if="!clientes.length && !ocupado">{{ textos.empty }}</p>
        <form v-if="cliente" class="bg-[var(--bg-panel)] rounded-lg p-5 space-y-4" @submit.prevent="guardar">
          <p v-if="!cliente.is_active">{{ textos.inactive }}</p>
          <label class="block">{{ textos.plan }}
            <select v-model="plan" class="campo ml-3">
              <option>Basico</option><option>Pro</option><option>Enterprise</option>
            </select>
          </label>
          <div v-for="(_, bandera) in cliente.feature_flags" :key="bandera" class="flex flex-wrap gap-3 items-center">
            <label :for="`flag-${bandera}`" class="w-48">{{ bandera }}</label>
            <select :id="`flag-${bandera}`" v-model="banderas[bandera]" class="campo">
              <option value="">{{ textos.inherit }}</option>
              <option value="true">{{ textos.enabled }}</option>
              <option value="false">{{ textos.disabled }}</option>
            </select>
            <span class="text-sm">{{ textos.effective }}: {{ cliente.feature_flags[bandera] ? textos.enabled : textos.disabled }}</span>
          </div>
          <button type="submit" class="boton bg-[var(--teal)] text-white">{{ textos.save }}</button>
        </form>
        <section v-if="cliente" class="space-y-3">
          <h2 class="text-xl font-bold">{{ textos.usage }}</h2>
          <p>{{ textos.note }}</p>
          <form class="flex gap-3" @submit.prevent="actualizarUso">
            <label>{{ textos.days }} <input v-model.number="dias" type="number" min="1" max="730" required class="campo w-24"></label>
            <button class="boton" type="submit">{{ textos.refresh }}</button>
          </form>
          <template v-if="uso">
            <p>{{ textos.since }}: {{ new Date(uso.since).toLocaleString(locale) }}</p>
            <p v-for="(cantidad, bandera) in uso.requests" :key="bandera">{{ bandera }}: {{ cantidad }}</p>
          </template>
          <h2 class="text-xl font-bold">{{ textos.changes }}</h2>
          <p v-if="!cambios.length">{{ textos.empty }}</p>
          <article v-for="cambio in cambios" :key="cambio.id" class="border border-[var(--border-subtle)] rounded p-3 break-words">
            <p>{{ new Date(cambio.date).toLocaleString(locale) }} · {{ cambio.actor }}</p>
            <p>{{ textos.before }}: {{ JSON.stringify(cambio.detail.before) }}</p>
            <p>{{ textos.after }}: {{ JSON.stringify(cambio.detail.after) }}</p>
          </article>
        </section>
      </fieldset>
    </div>
  </main>
</template>

<style scoped>
.campo { padding: 0.5rem; border: 1px solid var(--border-subtle); border-radius: 0.5rem; background: var(--bg-panel); }
.boton { padding: 0.5rem 1rem; border: 1px solid var(--border-subtle); border-radius: 0.5rem; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
