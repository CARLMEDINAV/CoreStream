import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createI18n } from 'vue-i18n'
import Vista from '@/views/PlatformPlansView.vue'
import { apiClient } from '@/services/api'

vi.mock('@/services/api', () => ({ apiClient: { get: vi.fn(), put: vi.fn() } }))
const cliente = { id: 'cliente', name: 'Empresa', is_active: true, plan: 'Basico',
  feature_overrides: {}, feature_flags: { analytics: false } }
const montar = () => mount(Vista, { global: {
  plugins: [createI18n({ legacy: false, locale: 'es', messages: { es: {} } })],
  stubs: { RouterLink: true },
} })

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(apiClient.get).mockImplementation(async (ruta) => ({ data:
    ruta.endsWith('/clients') ? [cliente] : ruta.endsWith('/usage')
      ? { since: '2026-11-04T00:00:00Z', requests: { analytics: 2 } } : [],
  }))
  vi.mocked(apiClient.put).mockResolvedValue({ data: { ...cliente, plan: 'Pro',
    feature_overrides: { analytics: false } } })
})

describe('consola comercial', () => {
  it('carga clientes, guarda el plan y las excepciones y muestra uso', async () => {
    const vista = montar()
    await flushPromises()
    expect(vista.text()).toContain('analytics: 2')
    await vista.findAll('select')[1].setValue('Pro')
    await vista.get('#flag-analytics').setValue('false')
    await vista.findAll('form')[0].trigger('submit')
    await flushPromises()
    expect(apiClient.put).toHaveBeenCalledWith('/platform/clients/cliente', {
      plan: 'Pro', feature_overrides: { analytics: false },
    })
    expect(vista.text()).toContain('Cambios guardados')
  })
  it('muestra el error y no ofrece editar si el servidor rechaza el acceso', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('403'))
    const vista = montar()
    await flushPromises()
    expect(vista.get('[role="alert"]').text()).toContain('No se pudo')
    expect(vista.find('form').exists()).toBe(false)
  })
})
