/**
 * API mockeada para modo prototipo
 * Simula todas las respuestas del backend usando localStorage
 */

import { mockDataService } from './mockData'
import type {
  User,
  Application,
  Epic,
  Ticket,
  Subtask,
  Notification,
  Document,
  AnalyticsSummary,
  AuthTokens,
  ApiResponse,
  LoginRequest,
  RegisterRequest,
  TicketFilters,
  PaginatedResponse,
  UserPerformance,
  HeatmapData,
  SupportSummary,
  BurndownData,
} from '@/types'
import { UserRole, TicketStatus, NotificationType, DocumentType } from '@/types'
import type { Incident, Meeting, MeetingAttendance } from '@/types'

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// Generar UUID v4 válido
const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Generar JWT mockeado válido (no necesita ser criptográficamente válido)
const generateMockJWT = (userId: string): string => {
  const header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
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

const getMockAuthTokens = (userId: string = 'user-1'): AuthTokens => ({
  accessToken: generateMockJWT(userId),
  refreshToken: generateMockJWT(userId),
  tokenType: 'bearer',
  expiresIn: 3600,
})

export const mockApi = {
  auth: {
    login: async (credentials: LoginRequest): Promise<{ tokens: AuthTokens }> => {
      await delay(500)
      // Buscar usuario por email
      const users = mockDataService.getUsers()?.items || []
      const user = users.find(u => u.email === credentials.email)

      if (user) {
        // Usuario encontrado: establecerlo como usuario actual
        mockDataService.setCurrentUser(user.id)
        return { tokens: getMockAuthTokens(user.id) }
      }

      // Usuario no encontrado pero permitir login (modo prototipo flexible)
      // Usar el primer usuario disponible como fallback
      if (users.length > 0) {
        mockDataService.setCurrentUser(users[0].id)
        return { tokens: getMockAuthTokens(users[0].id) }
      }

      throw new Error('No users available in mock data')
    },

    register: async (data: RegisterRequest): Promise<User> => {
      await delay(500)
      const newUser: User = {
        id: generateUUID(),
        email: data.email,
        fullName: data.fullName,
        role: UserRole.DEVELOPER,
        isActive: true,
        createdAt: new Date().toISOString(),
      }
      return newUser
    },

    refresh: async (refreshToken: string): Promise<AuthTokens> => {
      await delay(300)
      return getMockAuthTokens()
    },

    getMe: async (): Promise<User> => {
      await delay(200)
      const currentUser = mockDataService.getCurrentUser()
      if (!currentUser) throw new Error('No current user set')
      return currentUser
    },

    me: async (): Promise<User> => {
      await delay(200)
      const currentUser = mockDataService.getCurrentUser()
      if (!currentUser) throw new Error('No current user set')
      return currentUser
    },

    updateMe: async (data: Partial<User>): Promise<User> => {
      await delay(300)
      return mockDataService.updateUser(mockDataService.getCurrentUser().id, data)
    },

    updateProfile: async (data: Partial<User>): Promise<User> => {
      await delay(300)
      return mockDataService.updateUser(mockDataService.getCurrentUser().id, data)
    },

    updateSettings: async (data: { firstName: string; lastName: string; email: string; preferences: any }): Promise<User> => {
      await delay(300)
      const currentUser = mockDataService.getCurrentUser()
      return mockDataService.updateUser(currentUser.id, {
        fullName: `${data.firstName} ${data.lastName}`.trim(),
        email: data.email,
        preferences: data.preferences
      })
    },

    logout: async (): Promise<void> => {
      await delay(200)
    },

    changePassword: async (): Promise<void> => {
      throw new Error('Not implemented in mock')
    },

    requestPasswordReset: async (): Promise<void> => {
      throw new Error('Not implemented in mock')
    },

    confirmPasswordReset: async (): Promise<void> => {
      throw new Error('Not implemented in mock')
    },
  },

  users: {
    list: async (filters?: any): Promise<ApiResponse<PaginatedResponse<User>>> => {
      await delay(300)
      return { data: mockDataService.getUsers(filters), success: true }
    },

    getById: async (userId: string): Promise<ApiResponse<User>> => {
      await delay(200)
      const user = mockDataService.getUserById(userId)
      if (!user) throw new Error('User not found')
      return { data: user, success: true }
    },

    update: async (userId: string, data: Partial<User>): Promise<ApiResponse<User>> => {
      await delay(300)
      return { data: mockDataService.updateUser(userId, data), success: true }
    },

    delete: async (userId: string): Promise<ApiResponse<void>> => {
      await delay(300)
      mockDataService.deleteUser(userId)
      return { data: undefined, success: true }
    },

    changeRole: async (userId: string, newRole: any): Promise<ApiResponse<User>> => {
      await delay(300)
      return { data: mockDataService.updateUser(userId, { role: newRole }), success: true }
    },

    getStats: async (userId: string): Promise<ApiResponse<UserPerformance>> => {
      await delay(300)
      const user = mockDataService.getUserById(userId)
      return {
        data: {
          userId,
          userName: user?.fullName || 'Unknown',
          completedTickets: 7,
          averageHoursPerTicket: 24,
          activeTickets: 2,
          blockedPercentage: 5,
          velocity: 3.5,
          performanceScore: 85,
        },
        success: true,
      }
    },
  },

  applications: {
    list: async (filters?: any): Promise<Application[]> => {
      await delay(300)
      return mockDataService.getApplications(filters)
    },

    create: async (data: Omit<Application, 'id' | 'createdAt' | 'updatedAt' | 'ticketCount' | 'epicCount' | 'pendingCount' | 'delayedCount'>): Promise<Application> => {
      await delay(400)
      return mockDataService.createApplication(data)
    },

    getById: async (appId: string): Promise<Application> => {
      await delay(200)
      const app = mockDataService.getApplicationById(appId)
      if (!app) throw new Error('Application not found')
      return app
    },

    update: async (appId: string, data: Partial<Application>): Promise<Application> => {
      await delay(300)
      return mockDataService.updateApplication(appId, data)
    },

    delete: async (appId: string): Promise<void> => {
      await delay(300)
      mockDataService.deleteApplication(appId)
    },
  },

  epics: {
    list: async (appId: string, filters?: any): Promise<Epic[]> => {
      await delay(300)
      return mockDataService.getEpics(appId)
    },

    create: async (appId: string, data: { title: string; description?: string; dueDate?: string }): Promise<Epic> => {
      await delay(400)
      return mockDataService.createEpic({
        title: data.title,
        description: data.description || '',
        applicationId: appId,
        orderIndex: 0,
        dueDate: data.dueDate,
        isCollapsed: false,
        progress: 0,
        totalTickets: 0,
        completedTickets: 0,
      })
    },

    getById: async (epicId: string): Promise<Epic> => {
      await delay(200)
      const epic = mockDataService.getEpicById(epicId)
      if (!epic) throw new Error('Epic not found')
      return epic
    },

    update: async (epicId: string, data: Partial<Epic>): Promise<Epic> => {
      await delay(300)
      return mockDataService.updateEpic(epicId, data)
    },

    delete: async (epicId: string): Promise<void> => {
      await delay(300)
      mockDataService.deleteEpic(epicId)
    },

    reorder: async (epicId: string, newIndex: number): Promise<Epic> => {
      await delay(300)
      return mockDataService.updateEpic(epicId, { orderIndex: newIndex })
    },

    uploadDoc: async (appId: string, epicId: string, file: File): Promise<Document> => {
      await delay(500)
      return {
        id: generateUUID(),
        filename: file.name,
        mimeType: file.type,
        filePath: `/documents/${file.name}`,
        fileSize: file.size,
        epicId,
        uploadedById: mockDataService.getCurrentUser().id,
        docType: DocumentType.SPECIFICATION,
        createdAt: new Date().toISOString(),
      } as Document
    },
  },

  tickets: {
    list: async (filters?: TicketFilters): Promise<ApiResponse<PaginatedResponse<Ticket>>> => {
      await delay(300)
      return { data: mockDataService.getTickets(filters), success: true }
    },

    create: async (data: {
      epicId: string
      title: string
      description?: string
      priority?: string | any
      dueDate?: string
      assignedTo?: string
    }): Promise<Ticket> => {
      console.log('🎫 mockApi.tickets.create called with:', data)
      await delay(400)
      const result = mockDataService.createTicket(data as any)
      console.log('🎫 mockApi.tickets.create returning:', result)
      return result
    },

    getById: async (ticketId: string): Promise<Ticket> => {
      await delay(200)
      const ticket = mockDataService.getTicketById(ticketId)
      if (!ticket) throw new Error('Ticket not found')
      return {
        ...ticket,
        subtasks: mockDataService.getSubtasks(ticketId),
      }
    },

    update: async (ticketId: string, data: Partial<Ticket>): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, data)
    },

    delete: async (ticketId: string): Promise<ApiResponse<void>> => {
      await delay(300)
      mockDataService.deleteTicket(ticketId)
      return { data: undefined, success: true }
    },

    move: async (ticketId: string, newEpicId: string, newOrderIndex: number): Promise<ApiResponse<Ticket>> => {
      await delay(300)
      const ticket = mockDataService.updateTicket(ticketId, { epicId: newEpicId, orderIndex: newOrderIndex })
      return { data: ticket, success: true }
    },

    complete: async (ticketId: string, prLink: string): Promise<Ticket> => {
      await delay(400)
      return mockDataService.updateTicket(ticketId, { status: TicketStatus.COMPLETED, prLink })
    },

    question: async (ticketId: string, question: string): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { blockedQuestion: question, blockedAt: new Date().toISOString() })
    },

    start: async (ticketId: string): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { status: TicketStatus.IN_PROGRESS })
    },

    getMyWorkbench: async (): Promise<ApiResponse<Ticket[]>> => {
      await delay(300)
      return { data: mockDataService.getMyWorkbench(), success: true }
    },

    listByEpic: async (epicId: string, filters?: any): Promise<Ticket[]> => {
      await delay(300)
      const tickets = mockDataService.getTickets({ epicId })
      return tickets.items
    },

    listMyWorkbench: async (): Promise<Ticket[]> => {
      await delay(300)
      return mockDataService.getMyWorkbench()
    },

    moveToEpic: async (data: { ticketId: string; newEpicId: string }): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(data.ticketId, { epicId: data.newEpicId })
    },

    reorder: async (ticketId: string, newIndex: number): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { orderIndex: newIndex })
    },

    updateStatus: async (ticketId: string, status: any): Promise<Ticket> => {
      await delay(300)
      if (status === TicketStatus.IN_PROGRESS) {
        return mockApi.tickets.start(ticketId)
      }
      return mockDataService.updateTicket(ticketId, { status })
    },

    raiseQuestion: async (ticketId: string, question: string): Promise<Ticket> => {
      await delay(300)
      return mockApi.tickets.question(ticketId, question)
    },

    getTeamMembers: async (epicId?: string): Promise<User[]> => {
      await delay(300)
      return mockDataService.getUsers()?.items || []
    },

    resolveQuestion: async (ticketId: string, _questionId?: string, answer?: string): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { blockedQuestion: undefined, blockedAt: undefined })
    },

    redirect: async (ticketId: string, newAssigneeIdOrData: string | { toUserId: string; reason: string }, reason?: string): Promise<Ticket> => {
      await delay(400)
      const targetUserId = typeof newAssigneeIdOrData === 'string' ? newAssigneeIdOrData : newAssigneeIdOrData.toUserId
      return mockDataService.updateTicket(ticketId, { assigneeId: targetUserId })
    },

    getEvents: async (ticketId: string): Promise<any[]> => {
      await delay(300)
      return []
    },
  },

  subtasks: {
    create: async (ticketId: string, data: Omit<Subtask, 'id' | 'createdAt' | 'completedAt'>): Promise<Subtask> => {
      await delay(300)
      return mockDataService.createSubtask(ticketId, data)
    },

    update: async (ticketId: string, subtaskId: string, data: Partial<Subtask>): Promise<Subtask> => {
      await delay(300)
      return mockDataService.updateSubtask(subtaskId, data)
    },

    delete: async (ticketId: string, subtaskId: string): Promise<void> => {
      await delay(300)
      mockDataService.deleteSubtask(subtaskId)
    },

    reorder: async (ticketId: string, subtaskIds: string[]): Promise<Subtask[]> => {
      await delay(300)
      return subtaskIds
        .map((id, idx) => mockDataService.updateSubtask(id, { orderIndex: idx }))
        .filter((s): s is Subtask => s !== undefined)
    },
  },

  analytics: {
    getSummary: async (filters?: any): Promise<ApiResponse<AnalyticsSummary>> => {
      await delay(300)
      return { data: mockDataService.getAnalyticsSummary(filters), success: true }
    },

    getPerformance: async (filters?: any): Promise<ApiResponse<UserPerformance[]>> => {
      await delay(300)
      return {
        data: mockDataService.getUsers()?.items?.map(u => ({
          userId: u.id,
          userName: u.fullName,
          completedTickets: 7,
          averageHoursPerTicket: 24,
          activeTickets: 2,
          blockedPercentage: 5,
          velocity: 3.5,
          performanceScore: 85,
        })) || [],
        success: true,
      }
    },

    getHeatmap: async (filters?: any): Promise<ApiResponse<HeatmapData[]>> => {
      await delay(300)
      return { data: [], success: true }
    },

    getBurndown: async (applicationId: string, filters?: any): Promise<ApiResponse<BurndownData>> => {
      await delay(300)
      return {
        data: {
          name: 'Sprint Burndown',
          startDate: new Date().toISOString().split('T')[0],
          endDate: new Date().toISOString().split('T')[0],
          points: [],
          idealLine: [],
        } as BurndownData,
        success: true,
      }
    },

    getSupportSummary: async (): Promise<SupportSummary> => {
      await delay(300)
      return {
        by_status: { REPORTED: 0, INVESTIGATING: 0, RESOLVED: 0 },
        by_severity: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
        avg_resolution_time_hours: 0,
      }
    },

    exportPdf: async (filters?: any): Promise<Blob> => {
      await delay(500)
      return new Blob(['PDF Content'], { type: 'application/pdf' })
    },

    exportCsv: async (filters?: any): Promise<Blob> => {
      await delay(500)
      return new Blob(['CSV Content'], { type: 'text/csv' })
    },
  },

  documents: {
    list: async (filters?: any): Promise<ApiResponse<Document[]>> => {
      await delay(300)
      return { data: [], success: true }
    },

    upload: async (file: File, data: any): Promise<ApiResponse<Document>> => {
      await delay(500)
      return {
        data: {
          id: generateUUID(),
          filename: file.name,
          mimeType: file.type,
          filePath: `/documents/${file.name}`,
          fileSize: file.size,
          uploadedById: mockDataService.getCurrentUser().id,
          docType: DocumentType.SPECIFICATION,
          createdAt: new Date().toISOString(),
        } as Document,
        success: true,
      }
    },

    download: async (documentId: string): Promise<void> => {
      await delay(300)
    },

    delete: async (documentId: string): Promise<ApiResponse<void>> => {
      await delay(300)
      return { data: undefined, success: true }
    },

    translate: async (documentId: string, targetLanguage: string): Promise<ApiResponse<Document>> => {
      await delay(500)
      return {
        data: {
          id: documentId,
          filename: 'Translated Document',
          mimeType: 'application/pdf',
          filePath: `/documents/${documentId}`,
          fileSize: 0,
          uploadedById: mockDataService.getCurrentUser().id,
          docType: DocumentType.SPECIFICATION,
          createdAt: new Date().toISOString(),
        } as Document,
        success: true,
      }
    },

    translateDownload: async (_documentId: string, _targetLanguage: string): Promise<void> => {
      await delay(500)
    },
  },

  notifications: {
    list: async (filters?: any): Promise<ApiResponse<PaginatedResponse<Notification>>> => {
      await delay(300)
      return { data: mockDataService.getNotifications(filters), success: true }
    },

    getUnreadCount: async (): Promise<ApiResponse<{ count: number }>> => {
      await delay(200)
      return { data: { count: mockDataService.getUnreadCount() }, success: true }
    },

    markRead: async (notificationId: string): Promise<ApiResponse<Notification>> => {
      await delay(300)
      return {
        data: {
          id: notificationId,
          userId: mockDataService.getCurrentUser().id,
          title: 'Notification',
          message: 'This is a mock notification',
          type: NotificationType.TICKET_ASSIGNED,
          isRead: true,
          createdAt: new Date().toISOString(),
        },
        success: true,
      }
    },

    markAllRead: async (): Promise<ApiResponse<{ markedCount: number }>> => {
      await delay(300)
      return { data: { markedCount: 5 }, success: true }
    },

    delete: async (notificationId: string): Promise<void> => {
      await delay(300)
    },

    deleteAllRead: async (): Promise<void> => {
      await delay(300)
    },
  },

  team: {
    list: async (): Promise<User[]> => {
      await delay(300)
      return mockDataService.getUsers()?.items || []
    },

    listByApplication: async (appId: string): Promise<User[]> => {
      await delay(300)
      return mockDataService.getUsers()?.items || []
    },

    addMember: async (data: any): Promise<User> => {
      await delay(400)
      return {
        id: generateUUID(),
        email: data.email,
        fullName: data.fullName,
        role: data.role || UserRole.DEVELOPER,
        isActive: true,
        createdAt: new Date().toISOString(),
      }
    },

    updateMember: async (id: string, data: any): Promise<User> => {
      await delay(300)
      return mockDataService.updateUser(id, data)
    },

    deleteMember: async (id: string): Promise<void> => {
      await delay(300)
      mockDataService.deleteUser(id)
    },

    promoteToLeader: async (userId: string): Promise<User> => {
      await delay(300)
      return mockDataService.updateUser(userId, { role: UserRole.TEAM_LEADER })
    },

    demoteLeader: async (userId: string): Promise<User> => {
      await delay(300)
      return mockDataService.updateUser(userId, { role: UserRole.DEVELOPER })
    },

    getUnassignedTickets: async (appId: string): Promise<Ticket[]> => {
      await delay(300)
      return mockDataService.getTickets({ applicationId: appId })?.items?.filter(t => !t.assigneeId) || []
    },

    assignTicket: async (ticketId: string, userId: string): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { assigneeId: userId })
    },

    unassignTicket: async (ticketId: string): Promise<Ticket> => {
      await delay(300)
      return mockDataService.updateTicket(ticketId, { assigneeId: undefined })
    },
  },

  /**
   * ========================================
   * SOPORTE (MOCK)
   * ========================================
   */
  supportTickets: {
    list: async (filters?: { status?: string; severity?: string; assigneeId?: string; skip?: number; limit?: number }): Promise<Ticket[]> => {
      await delay(300)
      return []
    },
    getById: async (ticketId: string): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    create: async (data: any): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    update: async (ticketId: string, data: any): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    delete: async (ticketId: string): Promise<void> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    updateStatus: async (ticketId: string, status: string): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    addMessage: async (ticketId: string, data: { text: string }): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    assign: async (ticketId: string, assigneeId: string): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    investigate: async (ticketId: string): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    resolve: async (ticketId: string, prLink?: string): Promise<Ticket> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    getEvents: async (ticketId: string): Promise<any[]> => {
      await delay(300)
      return []
    },
    listLinkableTickets: async (): Promise<Ticket[]> => {
      await delay(300)
      return []
    }
  },

  /**
   * ========================================
   * MÓDULO DE INCIDENTES (MOCK)
   * ========================================
   */
  incidents: {
    list: async (filters?: { page?: number, limit?: number, application_id?: string, status?: string }): Promise<PaginatedResponse<Incident>> => {
      await delay(300)
      return { items: [], total: 0, page: 1, limit: filters?.limit || 10, totalPages: 0 }
    },
    getById: async (incidentId: string): Promise<Incident> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    create: async (data: any): Promise<Incident> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    update: async (incidentId: string, data: any): Promise<Incident> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    mitigate: async (incidentId: string, data: any): Promise<Incident> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    }
  },

  /**
   * ========================================
   * MÓDULO DE REUNIONES (MOCK)
   * ========================================
   */
  meetings: {
    list: async (filters?: { limit?: number, application_id?: string }): Promise<Meeting[]> => {
      await delay(300)
      return []
    },
    getById: async (meetingId: string): Promise<Meeting> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    create: async (data: any): Promise<Meeting> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    update: async (meetingId: string, data: any): Promise<Meeting> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    setAttendance: async (meetingId: string, data: any[]): Promise<MeetingAttendance[]> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    },
    updateSummary: async (meetingId: string, summary: string): Promise<Meeting> => {
      await delay(300)
      throw new Error("Not implemented in mock")
    }
  },
}
