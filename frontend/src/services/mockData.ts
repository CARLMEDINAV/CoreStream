/**
 * Datos mockeados para el modo prototipo
 * Se almacenan en localStorage bajo la clave 'corestream_mock_data'
 */

import type {
  User,
  Application,
  Epic,
  Ticket,
  Subtask,
  Notification,
  Document,
  AnalyticsSummary,
  UserPerformance,
  HeatmapData,
  BurndownData,
  PaginatedResponse,
  ApiResponse,
} from '@/types'
import { UserRole, TicketStatus, TicketPriority, NotificationType, DocumentType } from '@/types'

const STORAGE_KEY = 'corestream_mock_data'

// Generar UUID v4 válido
const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Predefined UUIDs para datos mockeados (consistentes entre recargas)
const MOCK_UUIDS = {
  // Users
  user1: '550e8400-e29b-41d4-a716-446655440001',
  user2: '550e8400-e29b-41d4-a716-446655440002',
  user3: '550e8400-e29b-41d4-a716-446655440003',
  user4: '550e8400-e29b-41d4-a716-446655440004',
  // Applications
  app1: '650e8400-e29b-41d4-a716-446655440001',
  app2: '650e8400-e29b-41d4-a716-446655440002',
  // Epics
  epic1: '750e8400-e29b-41d4-a716-446655440001',
  epic2: '750e8400-e29b-41d4-a716-446655440002',
  epic3: '750e8400-e29b-41d4-a716-446655440003',
  // Tickets
  ticket1: '850e8400-e29b-41d4-a716-446655440001',
  ticket2: '850e8400-e29b-41d4-a716-446655440002',
  ticket3: '850e8400-e29b-41d4-a716-446655440003',
  ticket4: '850e8400-e29b-41d4-a716-446655440004',
  ticket5: '850e8400-e29b-41d4-a716-446655440005',
  ticket6: '850e8400-e29b-41d4-a716-446655440006',
  ticket7: '850e8400-e29b-41d4-a716-446655440007',
  ticket8: '850e8400-e29b-41d4-a716-446655440008',
}

// JWT mockeado válido (no necesita ser criptográficamente válido, solo tener 3 partes)
const generateMockJWT = (userId: string): string => {
  const header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' // {"alg":"HS256","typ":"JWT"}
  const payloadObj = {
    sub: userId,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  }
  // Usar btoa (disponible en navegadores) en lugar de Buffer (Node.js)
  const payload = btoa(JSON.stringify(payloadObj))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
  const signature = 'mock_signature_placeholder_12345'
  return `${header}.${payload}.${signature}`
}

interface MockDataStore {
  users: User[]
  applications: Application[]
  epics: Epic[]
  tickets: Ticket[]
  subtasks: Subtask[]
  notifications: Notification[]
  documents: Document[]
  currentUserId: string
  accessToken: string
  refreshToken: string
}

const defaultMockData: MockDataStore = {
  currentUserId: MOCK_UUIDS.user1,
  accessToken: generateMockJWT(MOCK_UUIDS.user1),
  refreshToken: generateMockJWT(MOCK_UUIDS.user1),
  users: [
    {
      id: MOCK_UUIDS.user1,
      email: 'admin@corestream.local',
      fullName: 'Admin User',
      role: UserRole.ADMIN,
      specialty: 'Project Management',
      isActive: true,
      createdAt: new Date('2026-01-01').toISOString(),
    },
    {
      id: MOCK_UUIDS.user2,
      email: 'leader@corestream.local',
      fullName: 'Team Leader',
      role: UserRole.TEAM_LEADER,
      specialty: 'Backend Development',
      isActive: true,
      createdAt: new Date('2026-01-05').toISOString(),
    },
    {
      id: MOCK_UUIDS.user3,
      email: 'dev1@corestream.local',
      fullName: 'Developer One',
      role: UserRole.DEVELOPER,
      specialty: 'Frontend Development',
      isActive: true,
      createdAt: new Date('2026-01-10').toISOString(),
    },
    {
      id: MOCK_UUIDS.user4,
      email: 'dev2@corestream.local',
      fullName: 'Developer Two',
      role: UserRole.DEVELOPER,
      specialty: 'Full Stack',
      isActive: true,
      createdAt: new Date('2026-01-15').toISOString(),
    },
  ],
  applications: [
    {
      id: MOCK_UUIDS.app1,
      name: 'CoreStream Dashboard',
      description: 'Dashboard principal de gestión de proyectos',
      color: '#2563EB',
      icon: 'dashboard',
      ownerId: MOCK_UUIDS.user1,
      isActive: true,
      epicCount: 2,
      ticketCount: 8,
      pendingCount: 3,
      delayedCount: 1,
      createdAt: new Date('2026-01-01').toISOString(),
      updatedAt: new Date('2026-05-20').toISOString(),
    },
    {
      id: MOCK_UUIDS.app2,
      name: 'Mobile App',
      description: 'Aplicación móvil para iOS y Android',
      color: '#F59E0B',
      icon: 'smartphone',
      ownerId: MOCK_UUIDS.user2,
      isActive: true,
      epicCount: 3,
      ticketCount: 12,
      pendingCount: 5,
      delayedCount: 2,
      createdAt: new Date('2026-02-01').toISOString(),
      updatedAt: new Date('2026-05-18').toISOString(),
    },
  ],
  epics: [
    {
      id: MOCK_UUIDS.epic1,
      title: 'Autenticación y Autorización',
      description: 'Implementar sistema de login y control de acceso',
      applicationId: MOCK_UUIDS.app1,
      orderIndex: 0,
      dueDate: new Date('2026-06-30').toISOString().split('T')[0],
      isCollapsed: false,
      progress: 75,
      totalTickets: 4,
      completedTickets: 3,
      tickets: [],
      createdAt: new Date('2026-01-05').toISOString(),
      updatedAt: new Date('2026-05-20').toISOString(),
    },
    {
      id: MOCK_UUIDS.epic2,
      title: 'Panel de Control',
      description: 'Interfaz principal de usuario',
      applicationId: MOCK_UUIDS.app1,
      orderIndex: 1,
      dueDate: new Date('2026-07-15').toISOString().split('T')[0],
      isCollapsed: false,
      progress: 50,
      totalTickets: 4,
      completedTickets: 2,
      tickets: [],
      createdAt: new Date('2026-01-20').toISOString(),
      updatedAt: new Date('2026-05-15').toISOString(),
    },
    {
      id: MOCK_UUIDS.epic3,
      title: 'API REST',
      description: 'Desarrollo de endpoints de backend',
      applicationId: MOCK_UUIDS.app2,
      orderIndex: 0,
      dueDate: new Date('2026-06-15').toISOString().split('T')[0],
      isCollapsed: false,
      progress: 60,
      totalTickets: 5,
      completedTickets: 3,
      tickets: [],
      createdAt: new Date('2026-02-05').toISOString(),
      updatedAt: new Date('2026-05-19').toISOString(),
    },
  ],
  tickets: [
    {
      id: MOCK_UUIDS.ticket1,
      title: 'Implementar login',
      description: 'Crear página de login con validación',
      epicId: MOCK_UUIDS.epic1,
      assigneeId: MOCK_UUIDS.user3,
      status: TicketStatus.COMPLETED,
      priority: TicketPriority.HIGH,
      orderIndex: 0,
      dueDate: new Date('2026-06-15').toISOString().split('T')[0],
      timeSpentSeconds: 14400,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-01-10').toISOString(),
      updatedAt: new Date('2026-05-15').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user3,
        email: 'dev1@corestream.local',
        fullName: 'Developer One',
        role: UserRole.DEVELOPER,
        isActive: true,
      },
    },
    {
      id: MOCK_UUIDS.ticket2,
      title: 'Validar tokens JWT',
      description: 'Implementar renovación automática de tokens',
      epicId: MOCK_UUIDS.epic1,
      assigneeId: MOCK_UUIDS.user4,
      status: TicketStatus.IN_PROGRESS,
      priority: TicketPriority.HIGH,
      orderIndex: 1,
      dueDate: new Date('2026-06-20').toISOString().split('T')[0],
      timeSpentSeconds: 7200,
      blockedTimeSeconds: 3600,
      createdAt: new Date('2026-01-15').toISOString(),
      updatedAt: new Date('2026-05-18').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user4,
        email: 'dev2@corestream.local',
        fullName: 'Developer Two',
        role: UserRole.DEVELOPER,
        isActive: true,
      },
      blockedQuestion: 'Bearer token format unclear',
      blockedAt: new Date('2026-05-18').toISOString(),
    },
    {
      id: MOCK_UUIDS.ticket3,
      title: 'Control de roles RBAC',
      description: 'Implementar middleware de autorización',
      epicId: MOCK_UUIDS.epic1,
      assigneeId: MOCK_UUIDS.user2,
      status: TicketStatus.COMPLETED,
      priority: TicketPriority.MEDIUM,
      orderIndex: 2,
      dueDate: new Date('2026-06-25').toISOString().split('T')[0],
      timeSpentSeconds: 10800,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-01-20').toISOString(),
      updatedAt: new Date('2026-05-17').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user2,
        email: 'leader@corestream.local',
        fullName: 'Team Leader',
        role: UserRole.TEAM_LEADER,
        isActive: true,
      },
    },
    {
      id: MOCK_UUIDS.ticket4,
      title: 'Recuperación de contraseña',
      description: 'Implementar flujo de reset de contraseña',
      epicId: MOCK_UUIDS.epic1,
      assigneeId: undefined,
      status: TicketStatus.TODO,
      priority: TicketPriority.LOW,
      orderIndex: 3,
      dueDate: new Date('2026-07-05').toISOString().split('T')[0],
      timeSpentSeconds: 0,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-02-01').toISOString(),
      updatedAt: new Date('2026-02-01').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
    },
    {
      id: MOCK_UUIDS.ticket5,
      title: 'Diseño de header',
      description: 'Crear componente header reutilizable',
      epicId: MOCK_UUIDS.epic2,
      assigneeId: MOCK_UUIDS.user3,
      status: TicketStatus.COMPLETED,
      priority: TicketPriority.MEDIUM,
      orderIndex: 0,
      dueDate: new Date('2026-07-10').toISOString().split('T')[0],
      timeSpentSeconds: 5400,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-01-25').toISOString(),
      updatedAt: new Date('2026-05-16').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user3,
        email: 'dev1@corestream.local',
        fullName: 'Developer One',
        role: UserRole.DEVELOPER,
        isActive: true,
      },
    },
    {
      id: MOCK_UUIDS.ticket6,
      title: 'Sidebar dinámico',
      description: 'Implementar sidebar que responda a navegación',
      epicId: MOCK_UUIDS.epic2,
      assigneeId: MOCK_UUIDS.user4,
      status: TicketStatus.IN_PROGRESS,
      priority: TicketPriority.MEDIUM,
      orderIndex: 1,
      dueDate: new Date('2026-07-12').toISOString().split('T')[0],
      timeSpentSeconds: 3600,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-02-05').toISOString(),
      updatedAt: new Date('2026-05-19').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user4,
        email: 'dev2@corestream.local',
        fullName: 'Developer Two',
        role: UserRole.DEVELOPER,
        isActive: true,
      },
    },
    {
      id: MOCK_UUIDS.ticket7,
      title: 'Theme provider',
      description: 'Implementar tema oscuro y claro',
      epicId: MOCK_UUIDS.epic2,
      assigneeId: undefined,
      status: TicketStatus.TODO,
      priority: TicketPriority.LOW,
      orderIndex: 2,
      dueDate: new Date('2026-07-20').toISOString().split('T')[0],
      timeSpentSeconds: 0,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-02-10').toISOString(),
      updatedAt: new Date('2026-02-10').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
    },
    {
      id: MOCK_UUIDS.ticket8,
      title: 'Responsive layout',
      description: 'Hacer UI responsiva para móviles y tablets',
      epicId: MOCK_UUIDS.epic2,
      assigneeId: MOCK_UUIDS.user3,
      status: TicketStatus.IN_PROGRESS,
      priority: TicketPriority.HIGH,
      orderIndex: 3,
      dueDate: new Date('2026-07-15').toISOString().split('T')[0],
      timeSpentSeconds: 2700,
      blockedTimeSeconds: 0,
      createdAt: new Date('2026-02-15').toISOString(),
      updatedAt: new Date('2026-05-20').toISOString(),
      createdById: MOCK_UUIDS.user1,
      subtasks: [],
      assignee: {
        id: MOCK_UUIDS.user3,
        email: 'dev1@corestream.local',
        fullName: 'Developer One',
        role: UserRole.DEVELOPER,
        isActive: true,
      },
    },
  ],
  subtasks: [
    {
      id: generateUUID(),
      ticketId: MOCK_UUIDS.ticket1,
      title: 'Form de login',
      isCompleted: true,
      orderIndex: 0,
      createdAt: new Date('2026-01-10').toISOString(),
      completedAt: new Date('2026-05-12').toISOString(),
    },
    {
      id: generateUUID(),
      ticketId: MOCK_UUIDS.ticket1,
      title: 'Validaciones',
      isCompleted: true,
      orderIndex: 1,
      createdAt: new Date('2026-01-11').toISOString(),
      completedAt: new Date('2026-05-13').toISOString(),
    },
    {
      id: generateUUID(),
      ticketId: MOCK_UUIDS.ticket2,
      title: 'Endpoint de refresh',
      isCompleted: false,
      orderIndex: 0,
      createdAt: new Date('2026-01-15').toISOString(),
    },
  ],
  notifications: [
    {
      id: generateUUID(),
      userId: MOCK_UUIDS.user1,
      title: 'Ticket asignado',
      message: 'Te han asignado un nuevo ticket',
      type: NotificationType.TICKET_ASSIGNED,
      isRead: false,
      createdAt: new Date('2026-05-20T10:30:00').toISOString(),
    },
    {
      id: generateUUID(),
      userId: MOCK_UUIDS.user1,
      title: 'Ticket completado',
      message: 'El ticket ha sido completado',
      type: NotificationType.TICKET_COMPLETED,
      isRead: true,
      createdAt: new Date('2026-05-19T14:20:00').toISOString(),
    },
  ],
  documents: [
    {
      id: generateUUID(),
      filename: 'Especificación de login',
      mimeType: 'application/pdf',
      filePath: '/documents/spec-login.pdf',
      fileSize: 102400,
      uploadedById: MOCK_UUIDS.user1,
      createdAt: new Date('2026-01-10').toISOString(),
      ticketId: MOCK_UUIDS.ticket1,
      docType: DocumentType.SPECIFICATION,
    } as Document,
  ],
}

class MockDataService {
  private data: MockDataStore

  constructor() {
    // Intentar cargar del storage, pero validar que los IDs sean UUIDs
    const stored = this.loadFromStorage()
    if (stored && this.isValidMockData(stored)) {
      this.data = stored
    } else {
      // Si los datos no son válidos o no existen, usar los defaults y limpiar storage
      if (stored) {
        console.warn('Datos mockeados inválidos detectados. Limpiando localStorage y usando datos por defecto...')
      }
      this.data = defaultMockData
      this.saveToStorage()
    }
  }

  private isValidMockData(data: any): boolean {
    // Verificar que los IDs de las aplicaciones sean UUIDs válidos
    if (data?.applications && data.applications.length > 0) {
      const firstAppId = data.applications[0]?.id
      // UUID pattern: 8-4-4-4-12 hexadecimal characters
      const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      return uuidPattern.test(firstAppId)
    }
    return true // Si no hay datos, es válido (usaremos defaults)
  }

  private loadFromStorage(): MockDataStore | null {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? JSON.parse(stored) : null
    } catch (e) {
      console.warn('Error loading mock data from storage:', e)
      return null
    }
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data))
    } catch (e) {
      console.warn('Error saving mock data to storage:', e)
    }
  }

  reset(): void {
    this.data = defaultMockData
    this.saveToStorage()
  }

  getCurrentUser(): User {
    const user = this.data.users.find(u => u.id === this.data.currentUserId)
    return user || this.data.users[0]
  }

  setCurrentUser(userId: string): void {
    if (this.data.users.some(u => u.id === userId)) {
      this.data.currentUserId = userId
      this.saveToStorage()
    }
  }

  // Users
  getUsers(filters?: any): PaginatedResponse<User> {
    let users = this.data.users
    if (filters?.role) {
      users = users.filter(u => u.role === filters.role)
    }
    if (filters?.search) {
      const search = filters.search.toLowerCase()
      users = users.filter(
        u => u.fullName.toLowerCase().includes(search) || u.email.toLowerCase().includes(search)
      )
    }
    const limit = filters?.limit || 10
    const totalPages = Math.ceil(users.length / limit)
    return {
      items: users,
      total: users.length,
      page: filters?.page || 1,
      limit,
      totalPages,
    }
  }

  getUserById(userId: string): User | undefined {
    return this.data.users.find(u => u.id === userId)
  }

  updateUser(userId: string, data: Partial<User>): User {
    const index = this.data.users.findIndex(u => u.id === userId)
    if (index !== -1) {
      this.data.users[index] = { ...this.data.users[index], ...data, id: userId }
      this.saveToStorage()
      return this.data.users[index]
    }
    throw new Error('User not found')
  }

  deleteUser(userId: string): void {
    this.data.users = this.data.users.filter(u => u.id !== userId)
    this.saveToStorage()
  }

  // Applications
  getApplications(filters?: any): Application[] {
    return this.data.applications
  }

  getApplicationById(appId: string): Application | undefined {
    return this.data.applications.find(a => a.id === appId)
  }

  createApplication(data: Omit<Application, 'id' | 'createdAt' | 'updatedAt' | 'ticketCount' | 'epicCount' | 'pendingCount' | 'delayedCount'>): Application {
    const newApp: Application = {
      ...data,
      id: generateUUID(),
      ticketCount: 0,
      epicCount: 0,
      pendingCount: 0,
      delayedCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    this.data.applications.push(newApp)
    this.saveToStorage()
    return newApp
  }

  updateApplication(appId: string, data: Partial<Application>): Application {
    const index = this.data.applications.findIndex(a => a.id === appId)
    if (index !== -1) {
      this.data.applications[index] = {
        ...this.data.applications[index],
        ...data,
        id: appId,
        updatedAt: new Date().toISOString(),
      }
      this.saveToStorage()
      return this.data.applications[index]
    }
    throw new Error('Application not found')
  }

  deleteApplication(appId: string): void {
    this.data.applications = this.data.applications.filter(a => a.id !== appId)
    this.data.epics = this.data.epics.filter(e => e.applicationId !== appId)
    this.saveToStorage()
  }

  // Epics
  getEpics(appId: string): Epic[] {
    return this.data.epics.filter(e => e.applicationId === appId)
  }

  getEpicById(epicId: string): Epic | undefined {
    return this.data.epics.find(e => e.id === epicId)
  }

  createEpic(data: Omit<Epic, 'id' | 'createdAt' | 'updatedAt' | 'tickets'>): Epic {
    const newEpic: Epic = {
      ...data,
      id: `epic-${Date.now()}`,
      tickets: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    this.data.epics.push(newEpic)
    this.saveToStorage()
    return newEpic
  }

  updateEpic(epicId: string, data: Partial<Epic>): Epic {
    const index = this.data.epics.findIndex(e => e.id === epicId)
    if (index !== -1) {
      this.data.epics[index] = {
        ...this.data.epics[index],
        ...data,
        id: epicId,
        updatedAt: new Date().toISOString(),
      }
      this.saveToStorage()
      return this.data.epics[index]
    }
    throw new Error('Epic not found')
  }

  deleteEpic(epicId: string): void {
    this.data.epics = this.data.epics.filter(e => e.id !== epicId)
    this.saveToStorage()
  }

  // Tickets
  getTickets(filters?: any): PaginatedResponse<Ticket> {
    let tickets = this.data.tickets
    if (filters?.epicId) {
      tickets = tickets.filter(t => t.epicId === filters.epicId)
    }
    if (filters?.status) {
      tickets = tickets.filter(t => t.status === filters.status)
    }
    if (filters?.assigneeId) {
      tickets = tickets.filter(t => t.assigneeId === filters.assigneeId)
    }
    const limit = filters?.limit || 10
    const totalPages = Math.ceil(tickets.length / limit)
    return {
      items: tickets,
      total: tickets.length,
      page: filters?.page || 1,
      limit,
      totalPages,
    }
  }

  getTicketById(ticketId: string): Ticket | undefined {
    return this.data.tickets.find(t => t.id === ticketId)
  }

  createTicket(data: Partial<Omit<Ticket, 'id' | 'createdAt' | 'updatedAt' | 'createdById' | 'subtasks'>>): Ticket {
    console.log('🎫 MockDataService.createTicket called with:', data)
    const newTicket: Ticket = {
      epicId: data.epicId || '',
      title: data.title || '',
      description: data.description || '',
      status: (data.status as TicketStatus) || TicketStatus.TODO,
      priority: (data.priority as TicketPriority) || TicketPriority.MEDIUM,
      orderIndex: data.orderIndex ?? 0,
      assigneeId: data.assigneeId,
      dueDate: data.dueDate,
      prLink: data.prLink,
      id: `ticket-${Date.now()}`,
      subtasks: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      createdById: this.data.currentUserId,
      timeSpentSeconds: data.timeSpentSeconds || 0,
      blockedTimeSeconds: data.blockedTimeSeconds || 0,
    }
    console.log('🎫 Created ticket:', newTicket)
    this.data.tickets.push(newTicket)
    console.log('🎫 Total tickets after push:', this.data.tickets.length)
    this.saveToStorage()
    console.log('🎫 Saved to localStorage')
    return newTicket
  }

  updateTicket(ticketId: string, data: Partial<Ticket>): Ticket {
    const index = this.data.tickets.findIndex(t => t.id === ticketId)
    if (index !== -1) {
      this.data.tickets[index] = {
        ...this.data.tickets[index],
        ...data,
        id: ticketId,
        updatedAt: new Date().toISOString(),
      }
      this.saveToStorage()
      return this.data.tickets[index]
    }
    throw new Error('Ticket not found')
  }

  deleteTicket(ticketId: string): void {
    this.data.tickets = this.data.tickets.filter(t => t.id !== ticketId)
    this.data.subtasks = this.data.subtasks.filter(s => s.ticketId !== ticketId)
    this.saveToStorage()
  }

  getMyWorkbench(): Ticket[] {
    return this.data.tickets.filter(t => t.assigneeId === this.data.currentUserId)
  }

  // Subtasks
  getSubtasks(ticketId: string): Subtask[] {
    return this.data.subtasks.filter(s => s.ticketId === ticketId)
  }

  createSubtask(ticketId: string, data: Omit<Subtask, 'id' | 'createdAt' | 'completedAt'>): Subtask {
    const newSubtask: Subtask = {
      ...data,
      id: `subtask-${Date.now()}`,
      createdAt: new Date().toISOString(),
    }
    this.data.subtasks.push(newSubtask)
    this.saveToStorage()
    return newSubtask
  }

  updateSubtask(subtaskId: string, data: Partial<Subtask>): Subtask {
    const index = this.data.subtasks.findIndex(s => s.id === subtaskId)
    if (index !== -1) {
      this.data.subtasks[index] = {
        ...this.data.subtasks[index],
        ...data,
        completedAt: data.isCompleted ? new Date().toISOString() : undefined,
      }
      this.saveToStorage()
      return this.data.subtasks[index]
    }
    throw new Error('Subtask not found')
  }

  deleteSubtask(subtaskId: string): void {
    this.data.subtasks = this.data.subtasks.filter(s => s.id !== subtaskId)
    this.saveToStorage()
  }

  // Notifications
  getNotifications(filters?: any): PaginatedResponse<Notification> {
    let notifs = this.data.notifications.filter(n => n.userId === this.data.currentUserId)
    if (filters?.unreadOnly) {
      notifs = notifs.filter(n => !n.isRead)
    }
    const limit = filters?.limit || 10
    const totalPages = Math.ceil(notifs.length / limit)
    return {
      items: notifs,
      total: notifs.length,
      page: filters?.page || 1,
      limit,
      totalPages,
    }
  }

  getUnreadCount(): number {
    return this.data.notifications.filter(n => n.userId === this.data.currentUserId && !n.isRead).length
  }

  // Analytics
  getAnalyticsSummary(filters?: any): AnalyticsSummary {
    return {
      totalCompleted: this.data.tickets.filter(t => t.status === TicketStatus.COMPLETED).length,
      totalActive: this.data.tickets.filter(t => t.status === TicketStatus.IN_PROGRESS).length,
      totalPending: this.data.tickets.filter(t => t.status === TicketStatus.TODO).length,
      totalBlocked: 2,
      onTimePercentage: 85,
      teamVelocity: 25,
      teamPerformance: [],
      burndownData: {
        name: 'Sprint',
        startDate: new Date().toISOString(),
        endDate: new Date().toISOString(),
        points: [],
        idealLine: [],
      },
      heatmapData: [],
      generatedAt: new Date().toISOString(),
    }
  }
}

export const mockDataService = new MockDataService()

/**
 * Función helper para limpiar datos mockeados desde la consola
 * Ejecutar en DevTools: clearMockData()
 */
export const clearMockData = (): void => {
  console.log('🧹 Limpiando datos mockeados...')
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem('authTokens')
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('userRole')
  localStorage.removeItem('userId')
  localStorage.removeItem('userName')
  console.log('✅ Datos limpios. Recargando página...')
  location.reload()
}
