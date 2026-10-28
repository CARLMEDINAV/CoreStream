<!--
  Panel de seguridad (NEW-08). Se coloca dentro de SettingsView.vue: <SecuritySettings />

  - "Verificación en dos pasos" (todos los roles):
      * ADMIN: activa/desactiva su propio 2FA y regenera sus códigos.
      * Resto de roles: solo ven su estado y pueden regenerar sus códigos. La
        activación la controla el ADMIN (política de la organización).
  - "Política de la organización" (solo ADMIN): interruptor require_2fa
    (PUT /auth/mfa/policy). Afecta a todos los usuarios del mismo cliente. El
    backend exige que el ADMIN tenga su propio 2FA antes de poder exigirlo.
-->
<template>
  <div>
    <!-- ===== Mi verificación en dos pasos ===== -->
    <section class="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-6 mb-6">
      <h2 class="text-base font-semibold text-[var(--text-primary)] mb-1">🔐 {{ tx('title') }}</h2>
      <p class="text-xs text-[var(--text-secondary)] mb-4">{{ tx('desc') }}</p>

      <p v-if="notice" class="text-xs text-[var(--teal)] mb-3">✓ {{ notice }}</p>
      <p v-if="error" class="text-xs text-red-500 mb-3">{{ error }}</p>

      <div v-if="loadFailed" class="space-y-3">
        <p class="text-sm text-[var(--text-secondary)]">{{ tx('loadError') }}</p>
        <button type="button" :class="outlineBtn" @click="loadStatus">{{ tx('retry') }}</button>
      </div>
      <p v-else-if="!status" class="text-sm text-[var(--text-secondary)]">{{ tx('loading') }}</p>

      <template v-else>
        <!-- Estado -->
        <div v-if="mode === 'idle'" class="space-y-3">
          <div class="flex flex-wrap items-center gap-3">
            <span
              class="px-3 py-1 rounded-full text-xs font-semibold"
              :class="status.totpEnabled
                ? 'bg-[var(--teal)] text-white'
                : 'bg-[var(--bg-panel)] text-[var(--text-secondary)] border border-[var(--border-subtle)]'"
            >
              {{ status.totpEnabled ? tx('statusOn') : tx('statusOff') }}
            </span>
            <span
              v-if="status.totpEnabled"
              class="text-sm"
              :class="status.recoveryCodesRemaining <= 2 ? 'text-amber-500' : 'text-[var(--text-secondary)]'"
            >
              {{ tx('codesLeft') }}: {{ status.recoveryCodesRemaining }}
            </span>
          </div>

          <p v-if="status.totpEnabled && status.recoveryCodesRemaining <= 2" class="text-xs text-amber-500">
            {{ tx('codesLow') }}
          </p>
          <p v-if="status.totpEnabled && status.clientRequires2fa" class="text-xs text-[var(--text-secondary)]">
            {{ tx('orgRequires') }}
          </p>
          <p v-if="!authStore.isAdmin && !status.totpEnabled" class="text-xs text-[var(--text-secondary)]">
            {{ tx('adminManaged') }}
          </p>

          <div class="flex flex-wrap gap-2">
            <button
              v-if="authStore.isAdmin && !status.totpEnabled"
              type="button"
              :class="primaryBtn"
              @click="startEnroll"
            >
              {{ tx('activate') }}
            </button>
            <template v-if="status.totpEnabled">
              <button type="button" :class="outlineBtn" @click="openSensitive('regenerate')">
                {{ tx('regenerate') }}
              </button>
              <button
                v-if="authStore.isAdmin && !status.clientRequires2fa"
                type="button"
                :class="dangerBtn"
                @click="openSensitive('disable')"
              >
                {{ tx('disable') }}
              </button>
            </template>
          </div>
        </div>

        <!-- Activar: QR + código -->
        <form v-else-if="mode === 'enroll'" class="space-y-4" @submit.prevent="confirmEnroll">
          <p class="text-sm text-[var(--text-secondary)]">{{ tx('scanHint') }}</p>

          <div v-if="setupData" class="flex flex-col items-center gap-3">
            <!-- El SVG lo genera nuestro propio backend (/auth/mfa/setup) -->
            <div
              class="bg-white p-3 rounded-xl w-48 h-48 [&_svg]:w-full [&_svg]:h-full"
              v-html="setupData.qrSvg"
            />
            <p class="text-xs text-center text-[var(--text-secondary)]">{{ tx('cantScan') }}</p>
            <code
              class="text-xs font-mono break-all select-all px-3 py-2 rounded-lg bg-[var(--bg-panel)] border border-[var(--border-subtle)] text-[var(--teal)]"
            >{{ setupData.secret }}</code>
          </div>
          <p v-else-if="!error" class="text-sm text-center text-[var(--text-secondary)]">
            {{ tx('loadingQr') }}
          </p>

          <div v-if="setupData" class="max-w-xs">
            <label for="sec-confirm" :class="labelClass">{{ tx('codeLabel') }}</label>
            <input
              id="sec-confirm"
              v-model="code"
              v-focus
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="7"
              placeholder="000000"
              :class="[inputClass, 'text-center text-lg font-mono tracking-widest']"
            />
          </div>

          <div class="flex gap-2">
            <button v-if="setupData" type="submit" :disabled="busy || !validCode" :class="primaryBtn">
              {{ busy ? tx('working') : tx('confirm') }}
            </button>
            <button type="button" :class="outlineBtn" @click="backToIdle">{{ tx('cancel') }}</button>
          </div>
        </form>

        <!-- Desactivar / regenerar: pide contraseña + código -->
        <form
          v-else-if="mode === 'disable' || mode === 'regenerate'"
          class="space-y-4"
          @submit.prevent="submitSensitive"
        >
          <div>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">
              {{ mode === 'disable' ? tx('disableTitle') : tx('regenerateTitle') }}
            </h3>
            <p class="text-xs mt-1 text-[var(--text-secondary)]">
              {{ mode === 'disable' ? tx('disableHint') : tx('regenerateHint') }}
            </p>
          </div>

          <div class="max-w-xs space-y-3">
            <div>
              <label for="sec-password" :class="labelClass">{{ tx('passwordLabel') }}</label>
              <input
                id="sec-password"
                v-model="password"
                v-focus
                type="password"
                autocomplete="current-password"
                :class="inputClass"
              />
            </div>
            <div>
              <label for="sec-code" :class="labelClass">{{ tx('appCodeLabel') }}</label>
              <input
                id="sec-code"
                v-model="code"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="7"
                placeholder="000000"
                :class="[inputClass, 'text-center text-lg font-mono tracking-widest']"
              />
            </div>
          </div>

          <div class="flex gap-2">
            <button
              type="submit"
              :disabled="busy || !password || !validCode"
              :class="mode === 'disable' ? dangerBtn : primaryBtn"
            >
              {{ busy ? tx('working') : tx('confirm') }}
            </button>
            <button type="button" :class="outlineBtn" @click="backToIdle">{{ tx('cancel') }}</button>
          </div>
        </form>

        <!-- Códigos de recuperación (una sola vez) -->
        <div v-else-if="mode === 'codes'" class="space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">{{ tx('codesTitle') }}</h3>
            <p class="text-xs mt-1 text-[var(--text-secondary)]">{{ tx('codesHint') }}</p>
          </div>

          <ul
            class="grid grid-cols-2 gap-2 font-mono text-sm rounded-lg p-4 select-all max-w-sm bg-[var(--bg-panel)] border border-[var(--border-subtle)] text-[var(--teal)]"
          >
            <li v-for="c in recoveryCodes" :key="c" class="text-center">{{ c }}</li>
          </ul>

          <div class="flex gap-2">
            <button type="button" :class="outlineBtn" @click="copyCodes">
              {{ copied ? tx('copied') : tx('copy') }}
            </button>
            <button type="button" :class="outlineBtn" @click="downloadCodes">{{ tx('download') }}</button>
          </div>

          <label class="flex items-start gap-2 text-sm cursor-pointer text-[var(--text-secondary)]">
            <input v-model="codesSaved" type="checkbox" class="mt-0.5 accent-[#06B7B2]" />
            <span>{{ tx('savedCheck') }}</span>
          </label>

          <button type="button" :disabled="!codesSaved" :class="primaryBtn" @click="finishCodes">
            {{ tx('done') }}
          </button>
        </div>
      </template>
    </section>

    <!-- ===== Política de la organización (solo ADMIN) ===== -->
    <section
      v-if="authStore.isAdmin"
      class="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-6 mb-6"
    >
      <h2 class="text-base font-semibold text-[var(--text-primary)] mb-1">🛡️ {{ tx('policyTitle') }}</h2>
      <p class="text-xs text-[var(--text-secondary)] mb-4">{{ tx('policyDesc') }}</p>

      <p v-if="policyNotice" class="text-xs text-[var(--teal)] mb-3">✓ {{ policyNotice }}</p>
      <p v-if="policyError" class="text-xs text-red-500 mb-3">{{ policyError }}</p>

      <div class="flex items-start justify-between gap-4">
        <div class="space-y-1">
          <p class="text-sm font-medium text-[var(--text-primary)]">{{ tx('policyLabel') }}</p>
          <p
            v-if="status && !status.totpEnabled && !status.clientRequires2fa"
            class="text-xs text-amber-500"
          >
            {{ tx('policyNeedOwn') }}
          </p>
        </div>

        <button
          type="button"
          role="switch"
          :aria-checked="status?.clientRequires2fa ?? false"
          :disabled="!status || policyBusy || (!status.clientRequires2fa && !status.totpEnabled)"
          class="relative w-12 h-7 rounded-full transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
          :class="status?.clientRequires2fa ? 'bg-[var(--teal)]' : 'bg-[var(--border-subtle)]'"
          @click="onPolicyClick"
        >
          <span
            class="absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform"
            :class="status?.clientRequires2fa ? 'translate-x-5' : 'translate-x-0'"
          />
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useDialogStore } from '@/stores/dialog'
import type { MfaStatus, MfaSetupData } from '@/types'
import { securityMessages, type SecurityKey } from '@/i18n/securitySettings'

const authStore = useAuthStore()
const dialogStore = useDialogStore()
const i18n = useI18n()

const tx = (key: SecurityKey): string =>
  (securityMessages[i18n.locale.value] ?? securityMessages.es)[key]

// ---- Estilos (variables CSS del tema, igual que SettingsView) --------------------
const labelClass = 'block text-xs font-semibold text-[var(--text-secondary)] mb-1'
const inputClass =
  'w-full px-3 py-2 text-sm bg-[var(--bg-panel)] border border-[var(--border-subtle)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-[var(--teal)]'
const primaryBtn =
  'px-4 py-2 text-sm font-semibold bg-[var(--teal)] text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed'
const outlineBtn =
  'px-4 py-2 text-sm font-medium rounded-lg border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50'
const dangerBtn =
  'px-4 py-2 text-sm font-semibold bg-red-600 text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed'

// Enfoca el campo al mostrarse (directiva local v-focus)
const vFocus = { mounted: (el: HTMLElement) => el.focus() }

// ---- Estado ------------------------------------------------------------------
type Mode = 'idle' | 'enroll' | 'disable' | 'regenerate' | 'codes'

const status = ref<MfaStatus | null>(null)
const loadFailed = ref(false)
const mode = ref<Mode>('idle')
const busy = ref(false)
const error = ref('')
const notice = ref('')

const setupData = ref<MfaSetupData | null>(null)
const code = ref('')
const password = ref('')
const recoveryCodes = ref<string[]>([])
const codesSaved = ref(false)
const copied = ref(false)
// Qué mensaje mostrar al cerrar la vista de códigos
let afterCodesNotice: SecurityKey = 'noticeEnabled'

const policyBusy = ref(false)
const policyError = ref('')
const policyNotice = ref('')

const cleanCode = computed(() => code.value.replace(/\s/g, ''))
const validCode = computed(() => /^\d{6}$/.test(cleanCode.value))

function describe(err: unknown): string {
  const e = err as any
  if (e?.response?.status === 429) return tx('tooMany')
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return tx('genericError')
}

async function loadStatus() {
  loadFailed.value = false
  try {
    status.value = await api.mfa.status()
  } catch {
    loadFailed.value = true
  }
}

function backToIdle() {
  mode.value = 'idle'
  setupData.value = null
  code.value = ''
  password.value = ''
  recoveryCodes.value = []
  codesSaved.value = false
  copied.value = false
  error.value = ''
}

// ---- Activar (solo ADMIN desde la UI) -------------------------------------------
async function startEnroll() {
  notice.value = ''
  backToIdle()
  mode.value = 'enroll'
  try {
    setupData.value = await api.mfa.setup()
  } catch (err) {
    error.value = describe(err)
  }
}

async function confirmEnroll() {
  if (!validCode.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api.mfa.confirm(cleanCode.value)
    recoveryCodes.value = result.recoveryCodes
    code.value = ''
    afterCodesNotice = 'noticeEnabled'
    mode.value = 'codes'
  } catch (err) {
    error.value = describe(err)
    code.value = ''
  } finally {
    busy.value = false
  }
}

// ---- Desactivar / regenerar (piden contraseña + código) ---------------------------
function openSensitive(target: 'disable' | 'regenerate') {
  notice.value = ''
  backToIdle()
  mode.value = target
}

async function submitSensitive() {
  if (!password.value || !validCode.value) return
  busy.value = true
  error.value = ''
  try {
    if (mode.value === 'disable') {
      await api.mfa.disable(password.value, cleanCode.value)
      backToIdle()
      notice.value = tx('noticeDisabled')
      await loadStatus()
    } else {
      recoveryCodes.value = await api.mfa.regenerateRecoveryCodes(password.value, cleanCode.value)
      password.value = ''
      code.value = ''
      afterCodesNotice = 'noticeCodes'
      mode.value = 'codes'
    }
  } catch (err) {
    error.value = describe(err)
    code.value = ''
  } finally {
    busy.value = false
  }
}

// ---- Códigos de recuperación -------------------------------------------------------
async function copyCodes() {
  try {
    await navigator.clipboard.writeText(recoveryCodes.value.join('\n'))
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* sin permiso de portapapeles: queda la opción de descargar */
  }
}

function downloadCodes() {
  const text = `CoreStream - ${tx('codesTitle')}\n\n${recoveryCodes.value.join('\n')}\n`
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'corestream-recovery-codes.txt'
  a.click()
  URL.revokeObjectURL(url)
}

async function finishCodes() {
  backToIdle()
  notice.value = tx(afterCodesNotice)
  await loadStatus()
}

// ---- Política de la organización (ADMIN) ------------------------------------------
async function onPolicyClick() {
  if (!status.value) return
  policyError.value = ''
  policyNotice.value = ''
  if (status.value.clientRequires2fa) {
    await applyPolicy(false)
    return
  }
  // Exigirla afecta a todos los usuarios del cliente: pide confirmación
  const ok = await dialogStore.confirm(`${tx('policyConfirmQ')}\n\n${tx('policyWarn')}`)
  if (ok) await applyPolicy(true)
}

async function applyPolicy(next: boolean) {
  policyBusy.value = true
  policyError.value = ''
  try {
    await api.mfa.setPolicy(next)
    policyNotice.value = next ? tx('policyOnNotice') : tx('policyOffNotice')
    await loadStatus()
  } catch (err) {
    policyError.value = describe(err)
  } finally {
    policyBusy.value = false
  }
}

onMounted(loadStatus)
</script>
