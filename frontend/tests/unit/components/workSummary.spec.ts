import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import WorkbenchDashboard from '@/components/workbench/WorkbenchDashboard.vue'
import ResumenEquipoTrabajo from '@/components/analytics/ResumenEquipoTrabajo.vue'
import ManageIncidentModal from '@/components/dev/ManageIncidentModal.vue'
import { api } from '@/services/api'
import es from '@/i18n/es'
import en from '@/i18n/en'
import fr from '@/i18n/fr'
import de from '@/i18n/de'
import pt from '@/i18n/pt'
import type { EstadisticasUsuario, Incident, ResumenTrabajo, Ticket, TrabajoPersonal } from '@/types'

vi.mock('@/services/api', () => ({ api: {
  users: { getWorkbench: vi.fn(), getStats: vi.fn() },
  analytics: { getWorkSummary: vi.fn() },
  tickets: { getById: vi.fn() },
  incidents: { getById: vi.fn() },
} }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'persona' } }) }))

const cero = { active: 0, in_progress: 0, blocked: 0, completed_last_7_days: 0 }
const resumen: ResumenTrabajo = {
  tickets: { active: 2, in_progress: 1, blocked: 1, completed_last_7_days: 1 },
  incidents: { active: 1, in_progress: 1, blocked: 0, completed_last_7_days: 2 },
  total: { active: 3, in_progress: 2, blocked: 1, completed_last_7_days: 3 },
}
const trabajos: TrabajoPersonal[] = [
  { id: 'ticket', type: 'ticket', title: 'Ticket vencido', status: 'BLOCKED_QUESTION', due_date: '2026-10-20T10:00:00Z' },
  { id: 'incidencia', type: 'incident', title: 'Incidencia de hoy', status: 'INVESTIGATING', due_date: '2026-10-22T15:00:00Z' },
  { id: 'sin-fecha', type: 'ticket', title: 'Ticket sin fecha', status: 'IN_PROGRESS', due_date: null },
]

function configuracion() {
  return { plugins: [createI18n({ legacy: false, locale: 'es', messages: { es } })],
    stubs: { ManageIncidentModal: true } }
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-22T12:00:00Z'))
  vi.mocked(api.users.getWorkbench).mockResolvedValue(trabajos)
  vi.mocked(api.users.getStats).mockResolvedValue({ work_summary: resumen } as EstadisticasUsuario)
  vi.mocked(api.analytics.getWorkSummary).mockResolvedValue(resumen)
})
afterEach(() => vi.useRealTimers())

describe('WEB-18 en Workbench', () => {
  it('carga la lista combinada y las estadisticas propias, conservando el orden de vencimiento', async () => {
    const vista = mount(WorkbenchDashboard, { global: configuracion() })
    await flushPromises()
    expect(api.users.getStats).toHaveBeenCalledWith('persona')
    expect(vista.findAll('li h3').map(titulo => titulo.text())).toEqual(trabajos.map(trabajo => trabajo.title))
    expect(vista.text()).toContain('Resolución estimada')
    expect(vista.text()).toContain('Sin fecha')
    expect(vista.findAll('dt').map(campo => campo.text())).toContain('Completado en los últimos 7 días')
    expect(vista.findAll('dd')[0].text()).toBe('3')
  })

  it('filtra tipo, estados compartidos, estados especificos y fechas sin alterar los conteos', async () => {
    const vista = mount(WorkbenchDashboard, { global: configuracion() })
    await flushPromises()
    const [tipo, estado, fecha] = vista.findAll('select')
    await estado.setValue('blocked')
    expect(vista.findAll('li')).toHaveLength(1)
    expect(vista.find('li').text()).toContain('Ticket vencido')
    await tipo.setValue('incident')
    await estado.setValue('INVESTIGATING')
    await fecha.setValue('today')
    expect(vista.find('li').text()).toContain('Incidencia de hoy')
    expect(vista.findAll('dd')[0].text()).toBe('3')
    await fecha.setValue('overdue')
    expect(vista.findAll('li')).toHaveLength(0)
    expect(vista.text()).toContain(es.workbenchDashboard.noResults)
    const limpiar = vista.findAll('button').find(boton => boton.text() === es.workbenchDashboard.clearFilters)!
    await limpiar.trigger('click')
    await fecha.setValue('week')
    expect(vista.findAll('li')).toHaveLength(1)
    expect(vista.find('li').text()).toContain('Incidencia de hoy')
  })

  it('obtiene el ticket completo antes de abrir su panel y abre el modal de incidencias', async () => {
    const ticket = { id: 'ticket', title: 'Ticket completo' } as Ticket
    const incidencia = { id: 'incidencia', title: 'Detalle incidencia' } as Incident
    vi.mocked(api.tickets.getById).mockResolvedValue(ticket)
    vi.mocked(api.incidents.getById).mockResolvedValue(incidencia)
    const vista = mount(WorkbenchDashboard, { global: configuracion() })
    await flushPromises()
    await vista.findAll('li button')[0].trigger('click')
    await flushPromises()
    expect(vista.emitted('ticketSelected')).toEqual([[ticket]])
    await vista.findAll('li button')[1].trigger('click')
    await flushPromises()
    expect(api.incidents.getById).toHaveBeenCalledWith('incidencia')
    expect(vista.findComponent(ManageIncidentModal).props('incident')).toEqual(incidencia)
    expect(vista.findComponent(ManageIncidentModal).props('show')).toBe(true)
  })

  it('actualiza listado y conteos tras cambios en tickets o incidencias', async () => {
    const vista = mount(WorkbenchDashboard, { props: { actualizacion: 0 }, global: configuracion() })
    await flushPromises()
    vi.mocked(api.users.getWorkbench).mockResolvedValue([])
    vi.mocked(api.users.getStats).mockResolvedValue({ work_summary: { tickets: cero, incidents: cero, total: cero } } as EstadisticasUsuario)
    await vista.setProps({ actualizacion: 1 })
    await flushPromises()
    expect(vista.findAll('li')).toHaveLength(0)
    expect(vista.findAll('dd')[0].text()).toBe('0')
    expect(vista.text()).toContain(es.trabajo.vacio)
    vista.findComponent(ManageIncidentModal).vm.$emit('updated')
    await flushPromises()
    expect(api.users.getWorkbench).toHaveBeenCalledTimes(3)
    expect(api.users.getStats).toHaveBeenCalledTimes(3)
  })

  it('mantiene el listado si fallan los conteos y permite reintentar', async () => {
    vi.mocked(api.users.getStats).mockRejectedValueOnce(new Error('fallo'))
    const vista = mount(WorkbenchDashboard, { global: configuracion() })
    await flushPromises()
    expect(vista.find('[role="alert"]').text()).toContain(es.trabajo.errorResumen)
    expect(vista.findAll('li')).toHaveLength(3)
    await vista.find('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(vista.find('[role="alert"]').exists()).toBe(false)
    expect(vista.find('dl').exists()).toBe(true)
  })

  it('muestra errores de listado y de apertura sin presentar un vacio como exito', async () => {
    vi.mocked(api.users.getWorkbench).mockRejectedValueOnce(new Error('fallo'))
    vi.mocked(api.tickets.getById).mockRejectedValue(new Error('404'))
    const vista = mount(WorkbenchDashboard, { global: configuracion() })
    await flushPromises()
    expect(vista.text()).toContain(es.trabajo.errorLista)
    expect(vista.text()).not.toContain(es.trabajo.vacio)
    await vista.find('[role="alert"] button').trigger('click')
    await flushPromises()
    await vista.find('li button').trigger('click')
    await flushPromises()
    expect(vista.text()).toContain(es.trabajo.errorDetalle)
    expect(vista.emitted('ticketSelected')).toBeUndefined()
  })
})

describe('WEB-18 en Analitica', () => {
  it('muestra total y desglose con alcance independiente de los filtros por proyecto', async () => {
    let resolver!: (valor: ResumenTrabajo) => void
    vi.mocked(api.analytics.getWorkSummary).mockReturnValueOnce(new Promise(respuesta => { resolver = respuesta }))
    const vista = mount(ResumenEquipoTrabajo, { global: configuracion() })
    await nextTick()
    expect(vista.find('[role="status"]').text()).toBe(es.common.loading)
    resolver(resumen)
    await flushPromises()
    expect(api.analytics.getWorkSummary).toHaveBeenCalledWith()
    expect(vista.text()).toContain(es.trabajo.alcanceEquipo)
    expect(vista.findAll('dd')[1].text()).toContain('Tickets: 2')
    expect(vista.findAll('dd')[1].text()).toContain('Incidencias: 1')
  })

  it('borra datos anteriores ante errores y permite reintentar sin mostrar ceros ficticios', async () => {
    const vista = mount(ResumenEquipoTrabajo, { global: configuracion() })
    await flushPromises()
    vi.mocked(api.analytics.getWorkSummary).mockRejectedValueOnce(new Error('403'))
    await vista.find('button').trigger('click')
    await flushPromises()
    expect(vista.find('dl').exists()).toBe(false)
    expect(vista.find('[role="alert"]').text()).toContain(es.trabajo.errorResumen)
    vi.mocked(api.analytics.getWorkSummary).mockResolvedValue({ tickets: cero, incidents: cero, total: cero })
    await vista.find('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(vista.find('[role="alert"]').exists()).toBe(false)
    expect(vista.findAll('dd')[0].text()).toBe('0')
  })
})

it('conserva las mismas claves de WEB-18 en los cinco idiomas', () => {
  for (const idioma of [en, fr, de, pt]) {
    expect(Object.keys(idioma.trabajo).sort()).toEqual(Object.keys(es.trabajo).sort())
    expect(Object.keys(idioma.trabajo.estados).sort()).toEqual(Object.keys(es.trabajo.estados).sort())
  }
})
