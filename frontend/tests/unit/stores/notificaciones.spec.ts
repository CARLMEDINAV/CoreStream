import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { useAuthStore } from '@/stores/auth'
import { NotificationType } from '@/types'
import { api } from '@/services/api'
import NotificationBell from '@/components/shared/NotificationBell.vue'
import IncidentsView from '@/views/admin/IncidentsView.vue'
import ManageIncidentModal from '@/components/dev/ManageIncidentModal.vue'
import es from '@/i18n/es'

const navegar = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }))
let ruta = reactive({ query: {} as Record<string, string> })
vi.mock('vue-router', () => ({ useRouter: () => navegar, useRoute: () => ruta }))
vi.mock('@/composables/useWebSocket', () => ({ useWebSocket: () => ({ connect: vi.fn(), disconnect: vi.fn() }) }))
vi.mock('@/services/api', () => ({
  api: {
    notifications: {
      list: vi.fn(), getUnreadCount: vi.fn(), markReadBatch: vi.fn(), markAllRead: vi.fn()
    },
    incidents: { list: vi.fn(), getById: vi.fn(), eventos: vi.fn(), update: vi.fn(), updateStatus: vi.fn(), comentar: vi.fn() },
    team: { list: vi.fn() }
  }
}))

const aviso = (numero: number, tipo = NotificationType.INCIDENT_ASSIGNED) => ({
  id: '00000000-0000-4000-8000-' + String(numero).padStart(12, '0'),
  user_id: 'usuario', title: 'aviso ' + numero, message: 'prueba', type: tipo,
  is_read: false, incident_id: tipo === NotificationType.INCIDENT_ASSIGNED ? 'incidencia-1' : null,
  ticket_id: tipo === NotificationType.TICKET_ASSIGNED ? 'ticket-1' : null,
  created_at: '2026-10-12T12:00:00Z'
})
const incidencia = {
  id: 'incidencia-1', title: 'incidencia fuera de la primera pagina', description: 'detalle',
  status: 'ASSIGNED', severity: 'P1', categoria: 'red', assignedToId: 'dev-1',
  createdAt: '2026-10-12T12:00:00Z', isMitigated: false
}
const opciones = () => ({
  plugins: [createI18n({ legacy: false, locale: 'es', messages: { es } })],
  stubs: { AppHeader: true, Icon: true }
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  ruta = reactive({ query: {} })
  vi.mocked(api.notifications.list).mockResolvedValue([] as any)
  vi.mocked(api.notifications.getUnreadCount).mockResolvedValue({ unread_count: 8 } as any)
  vi.mocked(api.notifications.markReadBatch).mockResolvedValue({} as any)
  vi.mocked(api.incidents.list).mockResolvedValue({ items: [] } as any)
  vi.mocked(api.incidents.getById).mockResolvedValue(incidencia as any)
  vi.mocked(api.incidents.eventos).mockResolvedValue([])
  vi.mocked(api.team.list).mockResolvedValue([])
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: vi.fn() })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: vi.fn() })
})

describe('web-17: filtros y enlaces', () => {
  it('mantiene el filtro al paginar y conserva incident_id', async () => {
    vi.mocked(api.notifications.list).mockResolvedValueOnce(Array.from({ length: 20 }, (_, numero) => aviso(numero)) as any)
    const almacen = useNotificationsStore()
    await almacen.fetch(1, 20, NotificationType.INCIDENT_ASSIGNED)
    expect(almacen.notifications[0].incidentId).toBe('incidencia-1')
    expect(almacen.hasMore).toBe(true)
    vi.mocked(api.notifications.list).mockResolvedValueOnce([aviso(21)] as any)
    await almacen.loadMore()
    expect(api.notifications.list).toHaveBeenLastCalledWith({ skip: 20, limit: 20, type: 'INCIDENT_ASSIGNED' })
    expect(almacen.notifications).toHaveLength(21)
    expect(almacen.hasMore).toBe(false)
    await almacen.fetch(1, 20, '')
    expect(api.notifications.list).toHaveBeenLastCalledWith({ skip: 0, limit: 20, type: undefined })
  })

  it('ignora una respuesta vieja cuando cambia el filtro', async () => {
    let terminar!: (datos: any) => void
    vi.mocked(api.notifications.list).mockReturnValueOnce(new Promise(resolver => { terminar = resolver }))
    const almacen = useNotificationsStore()
    const primera = almacen.fetch(1, 20, NotificationType.TICKET_ASSIGNED)
    vi.mocked(api.notifications.list).mockResolvedValueOnce([aviso(2)] as any)
    await almacen.fetch(1, 20, NotificationType.INCIDENT_ASSIGNED)
    terminar([aviso(1, NotificationType.TICKET_ASSIGNED)])
    await primera
    expect(almacen.notifications.map(elemento => elemento.type)).toEqual(['INCIDENT_ASSIGNED'])
  })

  it('no mezcla eventos en tiempo real de otros tipos y usa el contador global', async () => {
    const almacen = useNotificationsStore()
    await almacen.fetch(1, 20, NotificationType.INCIDENT_ASSIGNED)
    almacen.addNotification({
      id: aviso(1).id, userId: 'usuario', title: 'ticket', message: '', type: NotificationType.TICKET_ASSIGNED,
      isRead: false, ticketId: 'ticket-1', createdAt: '2026-10-12'
    })
    expect(almacen.notifications).toHaveLength(0)
    expect(almacen.unreadCount).toBe(9)
    vi.mocked(api.notifications.getUnreadCount).mockResolvedValueOnce({ unread_count: 7 } as any)
    await almacen.markAsRead([aviso(1).id])
    expect(almacen.unreadCount).toBe(7)
  })

  it.each(['ADMIN', 'TEAM_LEADER', 'DEVELOPER'])('abre la incidencia desde la campana para %s', async rol => {
    useAuthStore().user = { id: 'dev-1', role: rol } as any
    vi.mocked(api.notifications.list).mockResolvedValue([aviso(1)] as any)
    const componente = mount(NotificationBell, { global: opciones() })
    await flushPromises()
    await componente.find('button').trigger('click')
    await flushPromises()
    expect(componente.findAll('option')).toHaveLength(9)
    const boton = componente.findAll('button').find(elemento => elemento.text().includes('aviso 1'))!
    await boton.trigger('click')
    expect(navegar.push).toHaveBeenCalledWith({
      name: rol === 'DEVELOPER' ? 'DevIncidents' : 'AdminIncidents', query: { incidentId: 'incidencia-1' }
    })
    componente.unmount()
  })

  it('conserva el enlace al ticket', async () => {
    useAuthStore().user = { id: 'admin', role: 'ADMIN' } as any
    vi.mocked(api.notifications.list).mockResolvedValue([aviso(2, NotificationType.TICKET_ASSIGNED)] as any)
    const componente = mount(NotificationBell, { global: opciones() })
    await flushPromises()
    await componente.find('button').trigger('click')
    await flushPromises()
    await componente.findAll('button').find(elemento => elemento.text().includes('aviso 2'))!.trigger('click')
    expect(navegar.push).toHaveBeenCalledWith({ name: 'Builder', query: { ticketId: 'ticket-1' } })
    componente.unmount()
  })
})

describe('web-14: detalle de incidencias', () => {
  it('abre por identificador aunque no este en la primera pagina y reacciona a otro enlace', async () => {
    useAuthStore().user = { id: 'dev-1', role: 'DEVELOPER' } as any
    ruta.query.incidentId = 'incidencia-1'
    const componente = mount(IncidentsView, { global: { ...opciones(), stubs: { AppHeader: true, ManageIncidentModal: true, CreateIncidentModal: true } } })
    await flushPromises()
    expect(api.incidents.getById).toHaveBeenCalledWith('incidencia-1')
    expect(componente.findComponent(ManageIncidentModal).props('incident').id).toBe('incidencia-1')
    ruta.query.incidentId = 'incidencia-2'
    await flushPromises()
    expect(api.incidents.getById).toHaveBeenLastCalledWith('incidencia-2')
    componente.unmount()
  })

  it('informa cuando el recurso no existe o no es accesible', async () => {
    useAuthStore().user = { id: 'dev-1', role: 'DEVELOPER' } as any
    ruta.query.incidentId = 'ajeno'
    vi.mocked(api.incidents.getById).mockRejectedValueOnce(new Error('404'))
    const componente = mount(IncidentsView, { global: { ...opciones(), stubs: { AppHeader: true, ManageIncidentModal: true, CreateIncidentModal: true } } })
    await flushPromises()
    expect(componente.find('[role="alert"]').text()).toBe(es.incidencias.errorAbrir)
    componente.unmount()
  })

  it('permite al asignado tomar su incidencia y comentar, sin asignar ni cerrar', async () => {
    useAuthStore().user = { id: 'dev-1', role: 'DEVELOPER' } as any
    const componente = mount(ManageIncidentModal, { props: { show: true, incident: incidencia as any }, global: opciones() })
    await flushPromises()
    expect(componente.findAll('select')).toHaveLength(0)
    expect(componente.text()).not.toContain(es.incidencias.acciones.CLOSED)
    await componente.findAll('button').find(elemento => elemento.text() === es.incidencias.acciones.INVESTIGATING)!.trigger('click')
    expect(api.incidents.updateStatus).toHaveBeenCalledWith('incidencia-1', 'INVESTIGATING')
    await flushPromises()
    const formulario = componente.findAll('form').at(-1)!
    await formulario.find('textarea').setValue('listo para revisar')
    await formulario.trigger('submit')
    expect(api.incidents.comentar).toHaveBeenCalledWith('incidencia-1', 'listo para revisar')
    componente.unmount()
  })

  it('ofrece asignacion al lider y envia el responsable elegido', async () => {
    useAuthStore().user = { id: 'lider-1', role: 'TEAM_LEADER' } as any
    vi.mocked(api.team.list).mockResolvedValue([{ id: 'dev-2', fullName: 'ana', role: 'DEVELOPER', isActive: true }] as any)
    const componente = mount(ManageIncidentModal, { props: { show: true, incident: incidencia as any }, global: opciones() })
    await flushPromises()
    await componente.find('select').setValue('dev-2')
    await componente.find('form').trigger('submit')
    expect(api.incidents.update).toHaveBeenCalledWith('incidencia-1', expect.objectContaining({ assigned_to_id: 'dev-2' }))
    componente.unmount()
  })
})

