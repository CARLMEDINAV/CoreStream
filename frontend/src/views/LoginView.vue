<!--
  Login contra la API /api/auth/login. Guarda tokens y rol en localStorage
  para el router; sincroniza axios con setAuthTokens.
-->
<template>
  <div
    class="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 transition-colors duration-300"
    :class="isDark
      ? 'bg-[#0A1A20]'
      : 'bg-gradient-to-br from-[#E6F8F7] via-[#F7FDED] to-[#CDF1F0]'"
  >
    <!-- Controles de esquina superior derecha: idioma + dark mode -->
    <div class="absolute top-4 right-4 flex items-center gap-2">
      <!-- Selector de idioma -->
      <div class="relative">
        <button
          @click="showLangMenu = !showLangMenu"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium transition-colors"
          :class="isDark
            ? 'bg-[#142730] text-[#A1A9AC] hover:text-white border border-[#2A4A55]'
            : 'bg-white/80 text-[#5A686E] hover:text-[#142730] border border-[#D0D4D6]'"
        >
          <span>{{ langFlags[currentLocale] }}</span>
          <span class="hidden sm:inline">{{ langNames[currentLocale] }}</span>
          <span class="text-xs opacity-60">▾</span>
        </button>
        <div
          v-if="showLangMenu"
          class="absolute right-0 top-full mt-1 rounded-xl shadow-lg border overflow-hidden z-50 min-w-[140px]"
          :class="isDark ? 'bg-[#142730] border-[#2A4A55]' : 'bg-white border-[#D0D4D6]'"
        >
          <button
            v-for="(name, code) in langNames"
            :key="code"
            @click="setLocale(code)"
            class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left transition-colors"
            :class="[
              currentLocale === code
                ? 'bg-[#06B7B2]/10 text-[#06B7B2] font-semibold'
                : isDark ? 'text-[#A1A9AC] hover:bg-[#1E3A45]' : 'text-[#5A686E] hover:bg-[#F0F9F9]'
            ]"
          >
            <span>{{ langFlags[code] }}</span>
            {{ name }}
          </button>
        </div>
        <!-- Overlay cierre -->
        <div v-if="showLangMenu" class="fixed inset-0 z-40" @click="showLangMenu = false" />
      </div>

      <!-- Toggle dark mode -->
      <button
        @click="toggleDark"
        class="w-9 h-9 rounded-xl flex items-center justify-center text-base transition-colors border"
        :class="isDark
          ? 'bg-[#142730] text-yellow-400 border-[#2A4A55] hover:bg-[#1E3A45]'
          : 'bg-white/80 text-[#5A686E] border-[#D0D4D6] hover:bg-white hover:text-[#142730]'"
        :title="isDark ? t('login.lightMode') : t('login.darkMode')"
      >
        <!-- Sol (modo claro activo → muestra luna) -->
        <svg v-if="!isDark" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
        <!-- Luna (modo oscuro activo → muestra sol) -->
        <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <div class="max-w-md w-full">
      <!-- Header con logo y títulos -->
      <div class="text-center mb-8">
        <div class="flex justify-center mb-6">
          <img
            :src="logoUrl"
            alt="CoreStream"
            class="w-40 h-auto rounded-xl object-contain shadow-lg"
          />
        </div>
        <h1 class="text-3xl font-bold mb-2 transition-colors" :class="isDark ? 'text-white' : 'text-[#142730]'">
          CoreStream
        </h1>
        <p class="text-sm transition-colors" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
          {{ t('login.subtitle') }}
        </p>
      </div>

      <!-- Card del formulario -->
      <form
        v-if="!pending"
        class="rounded-2xl p-10 space-y-5 transition-colors duration-300"
        :class="isDark
          ? 'bg-[#142730] shadow-[0_20px_60px_rgba(0,0,0,0.4)]'
          : 'bg-white shadow-[0_20px_60px_rgba(6,183,178,0.15),0_4px_16px_rgba(0,0,0,0.08)]'"
        @submit.prevent="onSubmit"
      >
        <!-- Campo Email -->
        <div>
          <label for="email" class="block text-sm font-medium mb-2 transition-colors" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
            {{ t('login.email') }}
          </label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            autocomplete="email"
            class="w-full rounded-xl border px-4 py-3 text-sm placeholder-[#A1A9AC] focus:outline-none focus:ring-2 transition-all"
            :class="isDark
              ? 'bg-[#0A1A20] border-[#2A4A55] text-white focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'
              : 'bg-white border-[#D0D4D6] text-[#142730] focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'"
            :placeholder="t('login.emailPlaceholder')"
          />
        </div>

        <!-- Campo Contraseña -->
        <div>
          <label for="password" class="block text-sm font-medium mb-2 transition-colors" :class="isDark ? 'text-[#A1A9AC]' : 'text-[#5A686E]'">
            {{ t('login.password') }}
          </label>
          <div class="relative">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              required
              autocomplete="current-password"
              class="w-full rounded-xl border px-4 py-3 pr-12 text-sm placeholder-[#A1A9AC] focus:outline-none focus:ring-2 transition-all"
              :class="isDark
                ? 'bg-[#0A1A20] border-[#2A4A55] text-white focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'
                : 'bg-white border-[#D0D4D6] text-[#142730] focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'"
              :placeholder="t('login.passwordPlaceholder')"
            />
            <button
              type="button"
              @click="showPassword = !showPassword"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-[#A1A9AC] hover:text-[#5A686E] transition-colors"
              :title="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'"
            >
              <!-- Ojo abierto (contraseña visible) -->
              <svg v-if="showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <!-- Ojo tachado (contraseña oculta) -->
              <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Mensaje de error -->
        <p v-if="errorMessage" class="text-sm text-[#DC2626] bg-[#FEE2E2] px-4 py-3 rounded-lg">
          {{ errorMessage }}
        </p>

        <!-- Botón Ingresar -->
        <button
          type="submit"
          :disabled="authStore.isLoading"
          class="w-full py-3 px-4 rounded-xl bg-[#ADEA4B] text-[#142730] text-base font-bold hover:bg-[#B5EC5D] active:bg-[#BDEE6F] disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center justify-center gap-2"
        >
          <Icon v-if="authStore.isLoading" icon="mdi:loading" class="animate-spin text-lg" />
          {{ authStore.isLoading ? t('login.submitting') : t('login.submit') }}
        </button>

        <!-- SSO: solo se muestra si el backend tiene proveedores configurados -->
        <div v-if="ssoProviders.length > 0" class="space-y-3">
          <div class="flex items-center gap-3">
            <span class="flex-1 h-px" :class="isDark ? 'bg-[#2A4A55]' : 'bg-[#D0D4D6]'" />
            <span class="text-xs" :class="mutedClass">{{ tsso('or') }}</span>
            <span class="flex-1 h-px" :class="isDark ? 'bg-[#2A4A55]' : 'bg-[#D0D4D6]'" />
          </div>
          <button
            v-for="p in ssoProviders"
            :key="p"
            type="button"
            class="w-full py-3 px-4 rounded-xl border text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
            :class="isDark
              ? 'border-[#2A4A55] text-white hover:bg-[#1E3A45]'
              : 'border-[#D0D4D6] text-[#142730] hover:bg-[#F0F9F9]'"
            @click="startSso(p)"
          >
            <Icon :icon="ssoIcons[p]" class="text-lg" />
            {{ tsso('continueWith') }} {{ ssoNames[p] }}
          </button>
        </div>
      </form>

      <!-- 2FA · Paso: ingresar el código (TOTP o código de recuperación) -->
      <form
        v-else-if="pending.kind === 'verify'"
        class="rounded-2xl p-10 space-y-5 transition-colors duration-300"
        :class="cardClass"
        @submit.prevent="onVerify"
      >
        <div>
          <h2 class="text-xl font-bold mb-1" :class="titleClass">{{ tm('verifyTitle') }}</h2>
          <p class="text-sm" :class="mutedClass">
            {{ useRecovery ? tm('recoveryHint') : tm('verifyHint') }}
          </p>
        </div>

        <div>
          <label for="mfa-code" class="block text-sm font-medium mb-2" :class="mutedClass">
            {{ useRecovery ? tm('recoveryLabel') : tm('codeLabel') }}
          </label>
          <input
            id="mfa-code"
            v-model="mfaCode"
            v-focus
            type="text"
            :inputmode="useRecovery ? 'text' : 'numeric'"
            autocomplete="one-time-code"
            :maxlength="useRecovery ? 32 : 7"
            :placeholder="useRecovery ? 'XXXXX-XXXXX' : '000000'"
            :class="[inputBase, inputClass, 'text-center text-lg font-mono tracking-widest']"
          />
        </div>

        <p v-if="errorMessage" class="text-sm text-[#DC2626] bg-[#FEE2E2] px-4 py-3 rounded-lg">
          {{ errorMessage }}
        </p>

        <button type="submit" :disabled="authStore.isLoading || !canSubmitVerify" :class="primaryBtnClass">
          <Icon v-if="authStore.isLoading" icon="mdi:loading" class="animate-spin text-lg" />
          {{ authStore.isLoading ? tm('verifying') : tm('verifySubmit') }}
        </button>

        <div class="flex flex-col items-center gap-2 text-sm">
          <button type="button" class="text-[#06B7B2] hover:underline" @click="toggleRecovery">
            {{ useRecovery ? tm('useTotp') : tm('useRecovery') }}
          </button>
          <button type="button" class="hover:underline" :class="mutedClass" @click="backToLogin">
            {{ tm('back') }}
          </button>
        </div>
      </form>

      <!-- 2FA · Enrolamiento obligatorio por política del cliente -->
      <div
        v-else
        class="rounded-2xl p-10 space-y-5 transition-colors duration-300"
        :class="cardClass"
      >
        <!-- Paso 1: QR + código de confirmación -->
        <form v-if="!showCodes" class="space-y-5" @submit.prevent="onConfirmSetup">
          <div>
            <h2 class="text-xl font-bold mb-1" :class="titleClass">{{ tm('setupTitle') }}</h2>
            <p class="text-sm" :class="mutedClass">{{ tm('setupHint') }}</p>
          </div>

          <div v-if="setupData" class="flex flex-col items-center gap-3">
            <!-- El SVG lo genera nuestro propio backend (/auth/mfa/setup) -->
            <div
              class="bg-white p-3 rounded-xl w-48 h-48 [&_svg]:w-full [&_svg]:h-full"
              v-html="setupData.qrSvg"
            />
            <p class="text-xs text-center" :class="mutedClass">{{ tm('cantScan') }}</p>
            <code
              class="text-xs font-mono break-all select-all px-3 py-2 rounded-lg"
              :class="isDark ? 'bg-[#0A1A20] text-[#ADEA4B]' : 'bg-[#F0F9F9] text-[#046B74]'"
            >{{ setupData.secret }}</code>
          </div>
          <p v-else-if="!errorMessage" class="text-sm text-center" :class="mutedClass">
            {{ tm('loadingQr') }}
          </p>

          <div v-if="setupData">
            <label for="mfa-confirm" class="block text-sm font-medium mb-2" :class="mutedClass">
              {{ tm('confirmLabel') }}
            </label>
            <input
              id="mfa-confirm"
              v-model="mfaCode"
              v-focus
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="7"
              placeholder="000000"
              :class="[inputBase, inputClass, 'text-center text-lg font-mono tracking-widest']"
            />
          </div>

          <p v-if="errorMessage" class="text-sm text-[#DC2626] bg-[#FEE2E2] px-4 py-3 rounded-lg">
            {{ errorMessage }}
          </p>

          <button
            v-if="setupData"
            type="submit"
            :disabled="authStore.isLoading || !canConfirmSetup"
            :class="primaryBtnClass"
          >
            <Icon v-if="authStore.isLoading" icon="mdi:loading" class="animate-spin text-lg" />
            {{ authStore.isLoading ? tm('verifying') : tm('confirmSubmit') }}
          </button>

          <div class="flex justify-center text-sm">
            <button type="button" class="hover:underline" :class="mutedClass" @click="backToLogin">
              {{ tm('back') }}
            </button>
          </div>
        </form>

        <!-- Paso 2: códigos de recuperación (se muestran una sola vez) -->
        <div v-else class="space-y-5">
          <div>
            <h2 class="text-xl font-bold mb-1" :class="titleClass">{{ tm('codesTitle') }}</h2>
            <p class="text-sm" :class="mutedClass">{{ tm('codesHint') }}</p>
          </div>

          <ul
            class="grid grid-cols-2 gap-2 font-mono text-sm rounded-xl p-4 select-all"
            :class="isDark ? 'bg-[#0A1A20] text-[#ADEA4B]' : 'bg-[#F0F9F9] text-[#046B74]'"
          >
            <li v-for="c in recoveryCodes" :key="c" class="text-center">{{ c }}</li>
          </ul>

          <div class="flex gap-2">
            <button
              type="button"
              class="flex-1 py-2 rounded-xl border text-sm font-medium transition-colors"
              :class="isDark
                ? 'border-[#2A4A55] text-[#A1A9AC] hover:text-white'
                : 'border-[#D0D4D6] text-[#5A686E] hover:text-[#142730]'"
              @click="copyCodes"
            >
              {{ copied ? tm('copied') : tm('copy') }}
            </button>
            <button
              type="button"
              class="flex-1 py-2 rounded-xl border text-sm font-medium transition-colors"
              :class="isDark
                ? 'border-[#2A4A55] text-[#A1A9AC] hover:text-white'
                : 'border-[#D0D4D6] text-[#5A686E] hover:text-[#142730]'"
              @click="downloadCodes"
            >
              {{ tm('download') }}
            </button>
          </div>

          <label class="flex items-start gap-2 text-sm cursor-pointer" :class="mutedClass">
            <input v-model="codesSaved" type="checkbox" class="mt-0.5 accent-[#06B7B2]" />
            <span>{{ tm('savedCheck') }}</span>
          </label>

          <p v-if="errorMessage" class="text-sm text-[#DC2626] bg-[#FEE2E2] px-4 py-3 rounded-lg">
            {{ errorMessage }}
          </p>

          <button
            type="button"
            :disabled="!codesSaved || authStore.isLoading"
            :class="primaryBtnClass"
            @click="onFinishSetup"
          >
            <Icon v-if="authStore.isLoading" icon="mdi:loading" class="animate-spin text-lg" />
            {{ tm('continue') }}
          </button>
        </div>
      </div>

      <!-- Footer -->
      <p class="text-xs text-center mt-8 transition-colors" :class="isDark ? 'text-[#2A4A55]' : 'text-[#A1A9AC]'">
        {{ t('login.footer', { year: new Date().getFullYear() }) }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores'
import { UserRole, type MfaSetupData } from '@/types'
import { loginMfaMessages, type LoginMfaKey } from '@/i18n/loginMfa'
import { loginSsoMessages, SSO_ERROR_CODES, type LoginSsoKey } from '@/i18n/loginSso'
import { api, ssoLoginUrl } from '@/services/api'
import logoUrl from '@/assets/logo-corestream.jpeg'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const i18n = useI18n()
const { t } = i18n

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const showLangMenu = ref(false)

const errorMessage = computed(() => authStore.error)
const isDark = computed(() => themeStore.isDark())

const currentLocale = computed<string>(() => i18n.locale.value)

const langFlags: Record<string, string> = { es: '🇪🇸', en: '🇬🇧', pt: '🇵🇹', fr: '🇫🇷', de: '🇩🇪' }
const langNames: Record<string, string> = { es: 'Español', en: 'English', pt: 'Português', fr: 'Français', de: 'Deutsch' }

function setLocale(code: string) {
  i18n.locale.value = code
  localStorage.setItem('corestream-locale', code)
  showLangMenu.value = false
}

function toggleDark() {
  themeStore.toggleTheme()
}

// ---- Estado del flujo 2FA --------------------------------------------------
const pending = computed(() => authStore.pendingMfa)
const mfaCode = ref('')
const useRecovery = ref(false)
const setupData = ref<MfaSetupData | null>(null)
const showCodes = ref(false)
const recoveryCodes = ref<string[]>([])
const codesSaved = ref(false)
const copied = ref(false)

// Enfoca el campo de código al mostrarse (directiva local v-focus)
const vFocus = { mounted: (el: HTMLElement) => el.focus() }

// Textos del flujo 2FA (módulo propio, 5 idiomas)
const tm = (key: LoginMfaKey): string =>
  (loginMfaMessages[currentLocale.value] ?? loginMfaMessages.es)[key]

// Clases compartidas por las pantallas 2FA (mismos colores que el formulario)
const cardClass = computed(() =>
  isDark.value
    ? 'bg-[#142730] shadow-[0_20px_60px_rgba(0,0,0,0.4)]'
    : 'bg-white shadow-[0_20px_60px_rgba(6,183,178,0.15),0_4px_16px_rgba(0,0,0,0.08)]'
)
const titleClass = computed(() => (isDark.value ? 'text-white' : 'text-[#142730]'))
const mutedClass = computed(() => (isDark.value ? 'text-[#A1A9AC]' : 'text-[#5A686E]'))
const inputBase =
  'w-full rounded-xl border px-4 py-3 placeholder-[#A1A9AC] focus:outline-none focus:ring-2 transition-all'
const inputClass = computed(() =>
  isDark.value
    ? 'bg-[#0A1A20] border-[#2A4A55] text-white focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'
    : 'bg-white border-[#D0D4D6] text-[#142730] focus:border-[#06B7B2] focus:ring-[#06B7B2]/20'
)
const primaryBtnClass =
  'w-full py-3 px-4 rounded-xl bg-[#ADEA4B] text-[#142730] text-base font-bold hover:bg-[#B5EC5D] active:bg-[#BDEE6F] disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center justify-center gap-2'

// Un TOTP son 6 dígitos (se toleran espacios); un código de recuperación es XXXXX-XXXXX
const cleanCode = computed(() =>
  useRecovery.value ? mfaCode.value.trim() : mfaCode.value.replace(/\s/g, '')
)
const canSubmitVerify = computed(() =>
  useRecovery.value ? cleanCode.value.length >= 10 : /^\d{6}$/.test(cleanCode.value)
)
const canConfirmSetup = computed(() => /^\d{6}$/.test(mfaCode.value.replace(/\s/g, '')))

function resetMfaUi() {
  mfaCode.value = ''
  useRecovery.value = false
  setupData.value = null
  showCodes.value = false
  recoveryCodes.value = []
  codesSaved.value = false
  copied.value = false
}

async function redirectAfterLogin() {
  const user = authStore.user
  let redirect = typeof route.query.redirect === 'string' ? route.query.redirect : null
  try {
    // Tras un login SSO la URL pierde el ?redirect=..., se guardó antes de salir
    if (!redirect) redirect = sessionStorage.getItem(SSO_REDIRECT_KEY)
    sessionStorage.removeItem(SSO_REDIRECT_KEY)
  } catch {
    /* sessionStorage no disponible */
  }
  if (redirect && redirect.startsWith('/')) {
    await router.replace(redirect)
    return
  }
  if (user?.role === UserRole.ADMIN) {
    await router.replace({ path: '/admin/builder' })
  } else {
    await router.replace({ path: '/dev/workbench' })
  }
}

// ---- Paso 1: correo y contraseña -------------------------------------------
async function onSubmit() {
  try {
    const user = await authStore.login(email.value.trim(), password.value)
    if (user) {
      await redirectAfterLogin()
      return
    }
    // Falta un segundo paso: authStore.pendingMfa indica cuál
    resetMfaUi()
    if (authStore.pendingMfa?.kind === 'setup') await loadSetup()
  } catch {
    /* mensaje en store */
  }
}

// ---- Paso 2a: código del segundo factor ------------------------------------
async function onVerify() {
  if (!canSubmitVerify.value) return
  try {
    await authStore.verifyMfa(cleanCode.value)
    resetMfaUi()
    await redirectAfterLogin()
  } catch {
    mfaCode.value = '' // mensaje en store
  }
}

function toggleRecovery() {
  useRecovery.value = !useRecovery.value
  mfaCode.value = ''
  authStore.error = null
}

// ---- Paso 2b: enrolamiento obligatorio ------------------------------------
async function loadSetup() {
  setupData.value = null
  try {
    setupData.value = await authStore.beginMfaSetup()
  } catch {
    /* mensaje en store */
  }
}

async function onConfirmSetup() {
  if (!canConfirmSetup.value) return
  try {
    recoveryCodes.value = await authStore.confirmMfaSetup(mfaCode.value.replace(/\s/g, ''))
    mfaCode.value = ''
    showCodes.value = true
  } catch {
    mfaCode.value = '' // mensaje en store
  }
}

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
  const text = `CoreStream - ${tm('codesTitle')}\n\n${recoveryCodes.value.join('\n')}\n`
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  const a = document.createElement('a')
  a.href = url
  a.download = 'corestream-recovery-codes.txt'
  a.click()
  URL.revokeObjectURL(url)
}

async function onFinishSetup() {
  try {
    await authStore.finishMfaSetup()
    resetMfaUi()
    await redirectAfterLogin()
  } catch {
    authStore.error = tm('finishError')
  }
}

function backToLogin() {
  authStore.cancelMfa()
  resetMfaUi()
  password.value = ''
}

// ---- SSO (Google / Microsoft) ---------------------------------------------
const SSO_REDIRECT_KEY = 'corestream-sso-redirect'
const ssoProviders = ref<string[]>([])
const ssoIcons: Record<string, string> = {
  google: 'logos:google-icon',
  microsoft: 'logos:microsoft-icon',
}
const ssoNames: Record<string, string> = { google: 'Google', microsoft: 'Microsoft' }

const tsso = (key: LoginSsoKey): string =>
  (loginSsoMessages[currentLocale.value] ?? loginSsoMessages.es)[key]

function ssoErrorText(code: string): string {
  return (SSO_ERROR_CODES as readonly string[]).includes(code)
    ? tsso(code as LoginSsoKey)
    : tsso('genericError')
}

// El botón NAVEGA (no es una petición XHR): el proveedor responde con redirecciones
function startSso(provider: string) {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  try {
    if (redirect.startsWith('/')) sessionStorage.setItem(SSO_REDIRECT_KEY, redirect)
    else sessionStorage.removeItem(SSO_REDIRECT_KEY)
  } catch {
    /* sessionStorage no disponible */
  }
  window.location.assign(ssoLoginUrl(provider))
}

// Retorno del SSO: el backend ya dejó las cookies de sesión; el guard del router
// las usa en /auth/refresh (ensureInitialized), así que aquí solo se espera y se redirige.
async function finishSsoLogin() {
  await authStore.ensureInitialized()
  if (authStore.isAuthenticated) {
    await redirectAfterLogin()
  } else {
    authStore.error = tsso('sessionFailed')
  }
}

onMounted(async () => {
  const ssoError = route.query.sso_error
  const ssoResult = route.query.sso
  if (typeof ssoError === 'string') {
    authStore.error = ssoErrorText(ssoError)
    await router.replace({ path: route.path })
  } else if (ssoResult === 'success') {
    await router.replace({ path: route.path })
    await finishSsoLogin()
  }
  try {
    ssoProviders.value = await api.sso.providers()
  } catch {
    ssoProviders.value = [] // sin SSO el login por contraseña sigue funcionando
  }
})

// Si se abandona la pantalla a mitad del flujo, se descarta el desafío pendiente
onBeforeUnmount(() => {
  if (authStore.pendingMfa) authStore.cancelMfa()
})
</script>
