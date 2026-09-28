import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/services/api'
import AdminLayout from '@/layouts/AdminLayout.vue'
import CodeDocsView from '@/views/admin/CodeDocsView.vue'
import es from '@/i18n/es'
import router from '@/router'

vi.mock('@/services/api', () => ({
  api: { auth: { login: vi.fn(), refresh: vi.fn(), getMe: vi.fn(), getCommercialProfile: vi.fn() } },
  setAuthTokens: vi.fn(), clearAuthTokens: vi.fn(),
}))
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({ connect: vi.fn(), disconnect: vi.fn() }),
}))
vi.mock('@/stores/theme', () => ({ useThemeStore: () => ({ applyTheme: vi.fn() }) }))
vi.mock('@/stores/documents', () => ({
  useDocumentsStore: () => {
    const docs = [{ id: 'doc-1', filename: 'manual.txt', docType: 'DOCUMENTATION',
      mimeType: 'text/plain', fileSize: 20, createdAt: '2026-09-28' }]
    return { documents: docs, recentDocuments: docs, docDocuments: docs,
      codeDocuments: [], uploaderIds: [], isLoading: false, fetchDocuments: vi.fn() }
  },
}))

const profile = (plan = 'Basico') => ({
  client_id: 'tenant-a', plan, is_active: true,
  feature_flags: { analytics: plan === 'Pro', document_translation: plan === 'Pro', tickets: true },
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  vi.mocked(api.auth.getMe).mockResolvedValue({ id: 'user-a', role: 'ADMIN' } as any)
  vi.mocked(api.auth.getCommercialProfile).mockResolvedValue(profile())
  vi.mocked(api.auth.login).mockResolvedValue({ tokens: { accessToken: 'token' } } as any)
  vi.mocked(api.auth.refresh).mockResolvedValue({ accessToken: 'token' } as any)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})

describe('TRV-02', () => {
  it('consulta el perfil al iniciar y restaurar la sesión', async () => {
    const auth = useAuthStore()
    await auth.login('a@test.com', 'password')
    expect(api.auth.getCommercialProfile).toHaveBeenCalledOnce()
    expect(auth.hasFeature('analytics')).toBe(false)
    vi.mocked(api.auth.getCommercialProfile).mockResolvedValue(profile('Pro'))
    await auth.initialize()
    expect(api.auth.getCommercialProfile).toHaveBeenCalledTimes(2)
    expect(auth.hasFeature('analytics')).toBe(true)
    expect(auth.hasFeature('unknown')).toBe(false)
    auth.clearSession()
    expect(auth.commercialProfile).toBeNull()
    expect(auth.hasFeature('analytics')).toBe(false)
  })

  it('limpia permisos anteriores si falla la carga comercial', async () => {
    const auth = useAuthStore()
    auth.commercialProfile = profile('Pro')
    vi.mocked(api.auth.getCommercialProfile).mockRejectedValue(new Error('offline'))
    await expect(auth.login('a@test.com', 'password')).rejects.toThrow('offline')
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.hasFeature('analytics')).toBe(false)
  })

  it('oculta Analítica en Basico y muestra el plan solo a ADMIN', async () => {
    const auth = useAuthStore()
    await auth.login('a@test.com', 'password')
    const wrapper = mount(AdminLayout, { global: {
      plugins: [createI18n({ legacy: false, locale: 'es', messages: { es } })],
      stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true },
    } })
    expect(wrapper.text()).toContain('Plan comercial: Basico')
    expect(wrapper.text()).not.toContain(es.nav.analytics)
    auth.commercialProfile = profile('Pro')
    await nextTick()
    expect(wrapper.text()).toContain(es.nav.analytics)
    auth.user = { id: 'leader', role: 'TEAM_LEADER' } as any
    await nextTick()
    expect(wrapper.text()).not.toContain('Plan comercial:')
    wrapper.unmount()
  })

  it('oculta la traduccion en Basico y la muestra en Pro', async () => {
    const auth = useAuthStore()
    await auth.login('a@test.com', 'password')
    const wrapper = shallowMount(CodeDocsView, { global: {
      plugins: [createI18n({ legacy: false, locale: 'es', messages: { es } })],
    } })
    expect(wrapper.text()).toContain(es.codeDocs.download)
    expect(wrapper.text()).not.toContain(es.codeDocs.translate)
    auth.commercialProfile = profile('Pro')
    await nextTick()
    expect(wrapper.text()).toContain(es.codeDocs.translate)
    wrapper.unmount()
  })

  it('impide abrir Analítica por URL en Basico y permite Pro', async () => {
    const auth = useAuthStore()
    await auth.ensureInitialized()
    await router.push('/admin/analytics')
    expect(router.currentRoute.value.path).toBe('/admin/builder')
    auth.commercialProfile = profile('Pro')
    await router.push('/admin/analytics')
    expect(router.currentRoute.value.path).toBe('/admin/analytics')
  })
})
