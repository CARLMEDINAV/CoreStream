/**
 * Servicio de API para CoreStream
 *
 * Centraliza toda la comunicación con el backend de FastAPI.
 * Proporciona:
 * - Instancia de Axios configurada con base URL, headers por defecto, etc.
 * - Interceptores para manejo automático de tokens JWT y renovación
 * - Métodos tipados para cada endpoint del API
 * - Manejo de errores consistente
 */

import axios, { AxiosInstance, AxiosError } from 'axios'
import type {
  User,
  UserRole,
  Application,
  Epic,
  Ticket,
  Subtask,
  TicketStatus,
  Notification,
  Document,
  AnalyticsSummary,
  AuthTokens,
  ApiResponse,
  LoginRequest,
  TicketFilters,
  PaginatedResponse,
  Incident,
  Meeting,
  MeetingAttendance,
  UserPerformance,
  BurndownData,
  SupportSummary,
  TranslateResponse
} from '@/types'

interface AuthState {
  accessToken: string | null
}

let authState: AuthState = {
  accessToken: null
}

// Configuración unificada de la URL base
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const BASE_URL = RAW_BASE_URL.endsWith('/') ? RAW_BASE_URL.slice(0, -1) : RAW_BASE_URL

const unwrapResponseData = <T>(payload: any): T => {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return (payload.data ?? payload) as T
  }
  return payload as T
}

const toSubtask = (raw: any): Subtask => ({
  id: raw.id,
  title: raw.title,
  isCompleted: raw.isCompleted ?? raw.is_completed ?? false,
  orderIndex: raw.orderIndex ?? raw.order_index ?? 0,
  completedAt: raw.completedAt ?? raw.completed_at ?? undefined,
  createdAt: raw.createdAt ?? raw.created_at ?? undefined,
  ticketId: raw.ticketId ?? raw.ticket_id ?? undefined,
})

const toTicket = (raw: any): Ticket => ({
  id: raw.id,
  title: raw.title,
  description: raw.description ?? '',
  epicId: raw.epicId ?? raw.epic_id ?? '',
  assigneeId: raw.assigneeId ?? raw.assignee_id ?? undefined,
  status: raw.status,
  priority: raw.priority,
  orderIndex: raw.orderIndex ?? raw.order_index ?? 0,
  dueDate: raw.dueDate ?? raw.due_date ?? undefined,
  prLink: raw.prLink ?? raw.pr_link ?? undefined,
  timeSpentSeconds: raw.timeSpentSeconds ?? raw.time_spent_seconds ?? 0,
  timerStartedAt: raw.timerStartedAt ?? raw.timer_started_at ?? undefined,
  blockedTimeSeconds: raw.blockedTimeSeconds ?? raw.blocked_time_seconds ?? 0,
  createdAt: raw.createdAt ?? raw.created_at,
  updatedAt: raw.updatedAt ?? raw.updated_at ?? raw.created_at,
  createdById: raw.createdById ?? raw.created_by_id ?? '',
  subtasks: (raw.subtasks ?? []).map(toSubtask),
  assignee: raw.assignee,
  epicTitle: raw.epicTitle ?? raw.epic_title ?? undefined,
  appName: raw.appName ?? raw.app_name ?? undefined,
  blockedQuestion: raw.blockedQuestion ?? raw.blocked_question ?? raw.block_reason ?? undefined,
  blockedAt: raw.blockedAt ?? raw.blocked_at ?? undefined,
  ticketType: raw.ticketType ?? raw.ticket_type ?? undefined,
  severity: raw.severity ?? undefined,
  stackTrace: raw.stackTrace ?? raw.stack_trace ?? undefined,
  reproductionSteps: raw.reproductionSteps ?? raw.reproduction_steps ?? undefined,
  browser: raw.browser ?? undefined,
  operatingSystem: raw.operatingSystem ?? raw.operating_system ?? undefined,
  linkedTicketId: raw.linkedTicketId ?? raw.linked_ticket_id ?? undefined,
  linkedTicketTitle: raw.linkedTicketTitle ?? raw.linked_ticket_title ?? undefined,
  originEpicTitle: raw.originEpicTitle ?? raw.origin_epic_title ?? undefined,
})

const toApplication = (raw: any): Application => ({
  id: raw.id,
  name: raw.name,
  description: raw.description ?? '',
  color: raw.color ?? '#2563EB',
  icon: raw.icon ?? 'folder',
  ownerId: raw.ownerId ?? raw.owner_id ?? '',
  isActive: raw.isActive ?? raw.is_active ?? true,
  epicCount: raw.epicCount ?? raw.epic_count ?? 0,
  ticketCount: raw.ticketCount ?? raw.ticket_count ?? 0,
  pendingCount: raw.pendingCount ?? raw.pending_count ?? 0,
  delayedCount: raw.delayedCount ?? raw.delayed_count ?? 0,
  createdAt: raw.createdAt ?? raw.created_at,
  updatedAt: raw.updatedAt ?? raw.updated_at,
})

const toIncident = (raw: any): Incident => ({
  id: raw.id,
  title: raw.title,
  description: raw.description,
  applicationId: raw.applicationId ?? raw.application_id ?? undefined,
  status: raw.status,
  severity: raw.severity,
  affectedEnvironment: raw.affectedEnvironment ?? raw.affected_environment,
  createdAt: raw.createdAt ?? raw.created_at,
  updatedAt: raw.updatedAt ?? raw.updated_at,
  createdById: raw.createdById ?? raw.created_by_id,
  assignedToId: raw.assignedToId ?? raw.assigned_to_id ?? undefined,
  mitigationTimeSeconds: raw.mitigationTimeSeconds ?? raw.mitigation_time_seconds ?? undefined,
  mitigationState: raw.mitigationState ?? raw.mitigation_state ?? undefined,
  isMitigated: raw.isMitigated ?? raw.is_mitigated ?? false,
  mitigatedAt: raw.mitigatedAt ?? raw.mitigated_at ?? undefined,
  rootCauseAnalysis: raw.rootCauseAnalysis ?? raw.root_cause_analysis ?? undefined,
  postMortemLink: raw.postMortemLink ?? raw.post_mortem_link ?? undefined,
})

const toMeetingAttendance = (raw: any): MeetingAttendance => ({
  id: raw.id,
  meetingId: raw.meetingId ?? raw.meeting_id,
  userId: raw.userId ?? raw.user_id,
  status: raw.status ?? 'ABSENT',
  notes: raw.notes ?? undefined,
  createdAt: raw.createdAt ?? raw.created_at,
  updatedAt: raw.updatedAt ?? raw.updated_at,
  user: raw.user ? mapUserFromApi(raw.user) : undefined,
})

const toMeeting = (raw: any): Meeting => ({
  id: raw.id,
  title: raw.title,
  meetingType: raw.meetingType ?? raw.meeting_type,
  applicationId: raw.applicationId ?? raw.application_id ?? undefined,
  scheduledAt: raw.scheduledAt ?? raw.scheduled_at,
  durationMinutes: raw.durationMinutes ?? raw.duration_minutes,
  summaryMarkdown: raw.summaryMarkdown ?? raw.summary_markdown ?? undefined,
  createdAt: raw.createdAt ?? raw.created_at,
  updatedAt: raw.updatedAt ?? raw.updated_at,
  createdById: raw.createdById ?? raw.created_by_id,
  attendances: Array.isArray(raw.attendances) ? raw.attendances.map(toMeetingAttendance) : undefined,
})

let refreshInFlight: Promise<Record<string, unknown>> | null = null

const getCookie = (name: string): string | null => {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

const performRefresh = (): Promise<Record<string, unknown>> => {
  if (!refreshInFlight) {
    const csrfToken = getCookie('csrf_token')
    refreshInFlight = axios
      .post<Record<string, unknown>>(
        `${BASE_URL}/auth/refresh`,
        {},
        {
          withCredentials: true,
          headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {}
        }
      )
      .then((response) => response.data ?? {})
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: BASE_URL,
    timeout: 30000,
    withCredentials: true,
    headers: {
      'Content-Type': 'application/json'
    }
  })

  instance.interceptors.request.use(
    (config) => {
      const token = authState.accessToken
      if (token) {
        const headers = config.headers as any
        if (headers && typeof headers.set === 'function') {
          headers.set('Authorization', `Bearer ${token}`)
        } else {
          config.headers = {
            ...(headers || {}),
            Authorization: `Bearer ${token}`
          }
        }
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  instance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as any
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true
        try {
          const d = await performRefresh()
          if (d && typeof d === 'object' && 'access_token' in d) {
            const mapped = mapTokenResponse(d as Record<string, unknown>)
            authState.accessToken = mapped.accessToken
            originalRequest.headers.Authorization = `Bearer ${authState.accessToken}`
            return instance(originalRequest)
          }
        } catch (refreshError) {
          authState.accessToken = null
          return Promise.reject(refreshError)
        }
      }
      return Promise.reject(error)
    }
  )

  return instance
}

const apiClient = createApiClient()

function mapEpicFromApi(raw: Record<string, unknown>): Epic {
  return {
    id: String(raw.id ?? ''),
    title: String(raw.title ?? ''),
    description: (raw.description as string) ?? '',
    applicationId: String(raw.application_id ?? raw.applicationId ?? ''),
    orderIndex: Number(raw.order_index ?? raw.orderIndex ?? 0),
    dueDate: raw.due_date ? String(raw.due_date) : undefined,
    isCollapsed: Boolean(raw.is_collapsed ?? raw.isCollapsed ?? false),
    progress: Number(raw.progress ?? 0),
    totalTickets: Number(raw.total_tickets ?? raw.totalTickets ?? 0),
    completedTickets: Number(raw.completed_tickets ?? raw.completedTickets ?? 0),
    tickets: Array.isArray(raw.tickets) ? (raw.tickets as any[]).map(toTicket) : [],
    createdAt: raw.created_at ? String(raw.created_at) : undefined,
    updatedAt: raw.updated_at ? String(raw.updated_at) : undefined,
  }
}

function mapEpicUpdateToApi(data: Partial<Epic>): Record<string, unknown> {
  const body: Record<string, unknown> = {}
  if (data.title !== undefined) body.title = data.title
  if (data.description !== undefined) body.description = data.description
  if (data.orderIndex !== undefined) body.order_index = data.orderIndex
  if (data.dueDate !== undefined) body.due_date = data.dueDate
  if (data.isCollapsed !== undefined) body.is_collapsed = data.isCollapsed
  return body
}

function mapUserFromApi(raw: Record<string, unknown>): User {
  const roleStr = String(raw.role ?? 'DEVELOPER').toUpperCase()
  return {
    id: String(raw.id ?? ''),
    email: String(raw.email ?? ''),
    fullName: String(raw.full_name ?? raw.fullName ?? ''),
    role: roleStr as UserRole,
    specialty: (raw.specialty as string) || undefined,
    avatarUrl: (raw.avatar_url as string) || (raw.avatarUrl as string) || undefined,
    isActive: Boolean(raw.is_active ?? true),
    createdAt: raw.created_at ? String(raw.created_at) : undefined,
    preferences: raw.preferences || {},
    mustChangePassword: Boolean(raw.must_change_password ?? false)
  } as User
}

function mapUserUpdateToApi(data: Partial<User>): Record<string, unknown> {
  const body: Record<string, unknown> = {}
  if (data.fullName !== undefined) body.full_name = data.fullName
  if (data.specialty !== undefined) body.specialty = data.specialty
  if (data.avatarUrl !== undefined) body.avatar_url = data.avatarUrl
  if (data.email !== undefined) body.email = data.email
  if (data.preferences !== undefined) body.preferences = data.preferences
  return body
}

function mapTokenResponse(d: Record<string, unknown>): AuthTokens {
  return {
    accessToken: String(d.access_token ?? ''),
    tokenType: String(d.token_type ?? 'bearer'),
    expiresIn: typeof d.expires_in === 'number' ? d.expires_in : undefined,
    mustChangePassword: Boolean(d.must_change_password ?? false),
  }
}

function toUserPerformance(raw: any): UserPerformance {
  return {
    userId: String(raw.user_id ?? ''),
    userName: raw.user_name ?? '',
    completedTickets: raw.tickets_completed ?? 0,
    averageHoursPerTicket: raw.avg_time_hours ?? 0,
    activeTickets: 0,
    blockedPercentage: raw.blocking_index ?? 0,
    velocity: 0,
    performanceScore: raw.efficiency ?? 0,
    efficiency: raw.efficiency ?? 0,
    blocking_index: raw.blocking_index ?? 0,
    churn_index: raw.churn_index ?? 0,
    tickets_processed: raw.tickets_processed ?? 0,
    questions_raised: raw.questions_raised ?? 0,
    redirections: raw.redirections ?? 0,
  }
}

function toTranslateResponse(raw: any): TranslateResponse {
  return {
    documentId: raw.document_id,
    originalFilename: raw.original_filename,
    targetLanguage: raw.target_language,
    translatedText: raw.translated_text,
  }
}

const realApi = {
  auth: {
    login: async (credentials: LoginRequest): Promise<{ tokens: AuthTokens }> => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/auth/login',
        credentials
      )
      return { tokens: mapTokenResponse((response.data ?? {}) as Record<string, unknown>) }
    },

    refresh: async (): Promise<AuthTokens> => {
      const d = await performRefresh()
      return mapTokenResponse(d)
    },

    getWsTicket: async (): Promise<string> => {
      const response = await apiClient.post<{ ticket: string }>('/auth/ws-ticket')
      return response.data.ticket
    },

    getMe: async (): Promise<User> => {
      const response = await apiClient.get<Record<string, unknown>>('/auth/me')
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    me: async (): Promise<User> => {
      const response = await apiClient.get<Record<string, unknown>>('/auth/me')
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    updateMe: async (data: Partial<User>): Promise<User> => {
      const response = await apiClient.put<Record<string, unknown>>(
        '/auth/me',
        mapUserUpdateToApi(data)
      )
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    updateProfile: async (data: Partial<User>): Promise<User> => {
      return realApi.auth.updateMe(data)
    },

    logout: async (): Promise<void> => {
      try {
        await apiClient.post('/auth/logout')
      } catch {
        /* mantener flujo de cierre local ante caídas */
      }
    },

    updateSettings: async (data: { firstName: string; lastName: string; email: string; preferences: any }): Promise<User> => {
      const response = await apiClient.put<Record<string, unknown>>(
        '/auth/me',
        mapUserUpdateToApi({ 
          fullName: `${data.firstName} ${data.lastName}`.trim(),
          email: data.email,
          preferences: data.preferences
        })
      )
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    changePassword: async (payload: { oldPassword: string; newPassword: string }): Promise<void> => {
      await apiClient.post('/auth/change-password', {
        old_password: payload.oldPassword,
        new_password: payload.newPassword
      })
    },

    requestPasswordReset: async (_payload: { email: string }): Promise<void> => {
      throw new Error('Recuperación de contraseña no implementada')
    },

    confirmPasswordReset: async (_payload: {
      token: string
      newPassword: string
    }): Promise<void> => {
      throw new Error('Recuperación de contraseña no implementada')
    }
  },

  invitations: {
    create: async (data: { email: string; role: string }): Promise<{
      id: string
      email: string
      role: string
      token: string
      expiresAt: string
    }> => {
      const response = await apiClient.post<Record<string, unknown>>('/invitations/', {
        email: data.email,
        role: data.role,
      })
      const d = response.data
      return {
        id: String(d.id ?? ''),
        email: String(d.email ?? ''),
        role: String(d.role ?? ''),
        token: String(d.token ?? ''),
        expiresAt: String(d.expires_at ?? ''),
      }
    },

    getInfo: async (token: string): Promise<{
      email: string
      role: string
      expiresAt: string
      isExpired: boolean
      isUsed: boolean
    }> => {
      const response = await apiClient.get<Record<string, unknown>>(`/invitations/${token}`)
      const d = response.data
      return {
        email: String(d.email ?? ''),
        role: String(d.role ?? ''),
        expiresAt: String(d.expires_at ?? ''),
        isExpired: Boolean(d.is_expired),
        isUsed: Boolean(d.is_used),
      }
    },

    accept: async (token: string, data: { fullName: string; password: string }): Promise<void> => {
      await apiClient.post(`/invitations/${token}/accept`, {
        full_name: data.fullName,
        password: data.password,
      })
    },
  },

  users: {
    list: async (filters?: {
      page?: number
      limit?: number
      role?: UserRole
      search?: string
    }): Promise<ApiResponse<PaginatedResponse<User>>> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<User>>>(
        '/users/',
        { params: filters }
      )
      return response.data
    },

    getById: async (userId: string): Promise<ApiResponse<User>> => {
      const response = await apiClient.get<ApiResponse<User>>(`/users/${userId}`)
      return response.data
    },

    update: async (userId: string, data: Partial<User>): Promise<ApiResponse<User>> => {
      const response = await apiClient.put<ApiResponse<User>>(
        `/users/${userId}`,
        data
      )
      return response.data
    },

    delete: async (userId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(`/users/${userId}`)
      return response.data
    },

    changeRole: async (userId: string, newRole: UserRole): Promise<ApiResponse<User>> => {
      const response = await apiClient.post<ApiResponse<User>>(
        `/users/${userId}/change-role`,
        { role: newRole }
      )
      return response.data
    },

    resetPassword: async (userId: string): Promise<{ temporaryPassword: string }> => {
      const response = await apiClient.post<{ temporary_password: string }>(
        `/users/${userId}/reset-password`
      )
      return { temporaryPassword: response.data.temporary_password }
    },

    getStats: async (userId: string): Promise<ApiResponse<UserPerformance>> => {
      const response = await apiClient.get<ApiResponse<UserPerformance>>(
        `/users/${userId}/stats`
      )
      return response.data
    }
  },

  applications: {
    list: async (filters?: {
      page?: number
      limit?: number
    }): Promise<Application[]> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Application>>>(
        '/applications/',
        { params: filters }
      )
      const payload = unwrapResponseData<any>(response)
      const items = Array.isArray(payload) ? payload : (payload?.items || payload?.data || [])
      return items.map(toApplication)
    },

    create: async (data: Omit<Application, 'id' | 'createdAt' | 'updatedAt' | 'ticketCount' | 'epicCount' | 'pendingCount' | 'delayedCount'>): Promise<Application> => {
      const response = await apiClient.post<ApiResponse<Application>>(
        '/applications/',
        {
          name: data.name,
          description: data.description,
          color: data.color,
          icon: data.icon,
        }
      )
      return toApplication(unwrapResponseData<any>(response))
    },

    getById: async (appId: string): Promise<Application> => {
      const response = await apiClient.get<ApiResponse<Application>>(
        `/applications/${appId}`
      )
      return toApplication(unwrapResponseData<any>(response))
    },

    update: async (appId: string, data: Partial<Application>): Promise<Application> => {
      const response = await apiClient.put<ApiResponse<Application>>(
        `/applications/${appId}`,
        {
          name: data.name,
          description: data.description,
          color: data.color,
          icon: data.icon,
          is_active: (data as any).isActive,
        }
      )
      return toApplication(unwrapResponseData<any>(response))
    },

    delete: async (appId: string): Promise<void> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/applications/${appId}`
      )
      return unwrapResponseData<void>(response)
    }
  },

  epics: {
    list: async (appId: string, filters?: {
      page?: number
      limit?: number
    }): Promise<Epic[]> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Epic>>>(
        `/epics/by-app/${appId}`,
        { params: filters }
      )
      const raw = unwrapResponseData<any[]>(response.data)
      const items = Array.isArray(raw) ? raw : []
      return items.map((row) => mapEpicFromApi(row as Record<string, unknown>))
    },

    create: async (appId: string, data: { title: string; description?: string; dueDate?: string }): Promise<Epic> => {
      const response = await apiClient.post<ApiResponse<Epic>>(
        '/epics/',
        {
          title: data.title,
          description: data.description,
          application_id: appId,
          due_date: data.dueDate || undefined,
        }
      )
      return mapEpicFromApi(unwrapResponseData<Record<string, unknown>>(response) ?? {})
    },

    getById: async (epicId: string): Promise<Epic> => {
      const response = await apiClient.get<Record<string, unknown>>(`/epics/${epicId}`)
      return mapEpicFromApi(response.data as Record<string, unknown>)
    },

    update: async (epicId: string, data: Partial<Epic>): Promise<Epic> => {
      const response = await apiClient.put<Record<string, unknown>>(
        `/epics/${epicId}`,
        mapEpicUpdateToApi(data)
      )
      return mapEpicFromApi(response.data as Record<string, unknown>)
    },

    delete: async (epicId: string): Promise<void> => {
      await apiClient.delete(`/epics/${epicId}`)
    },

    reorder: async (epicId: string, newIndex: number): Promise<Epic> => {
      const response = await apiClient.patch<Record<string, unknown>>(
        `/epics/${epicId}/reorder`,
        { new_index: newIndex }
      )
      return mapEpicFromApi(response.data as Record<string, unknown>)
    },

    uploadDoc: async (epicId: string, file: File): Promise<Document> => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('epicId', epicId)
      formData.append('docType', 'DOCUMENTATION')

      const response = await apiClient.post<ApiResponse<Document>>(
        '/documents/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      )
      return unwrapResponseData<Document>(response)
    }
  },

  tickets: {
    list: async (filters?: TicketFilters): Promise<ApiResponse<PaginatedResponse<Ticket>>> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Ticket>>>(
        '/tickets/',
        { params: filters }
      )
      return response.data
    },

    create: async (data: Omit<Ticket, 'id' | 'createdAt' | 'updatedAt' | 'createdById'>): Promise<Ticket> => {
      const rawData = data as any
      const payload = {
        title: rawData.title,
        description: rawData.description,
        epic_id: rawData.epicId || rawData.epic_id,
        assignee_id: rawData.assigneeId,
        priority: rawData.priority || 'MEDIUM',
        due_date: rawData.dueDate,
      }

      const response = await apiClient.post<Ticket>('/tickets/', payload)
      return toTicket(response.data)
    },

    getById: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.get<any>(`/tickets/${ticketId}`)
      return toTicket(response.data)
    },

    update: async (ticketId: string, data: Partial<Ticket>): Promise<Ticket> => {
      const response = await apiClient.put<any>(`/tickets/${ticketId}`, data)
      return toTicket(response.data)
    },

    delete: async (ticketId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/tickets/${ticketId}`
      )
      return response.data
    },

    move: async (ticketId: string, newEpicId: string, _newOrderIndex?: number): Promise<ApiResponse<Ticket>> => {
      const response = await apiClient.patch<ApiResponse<Ticket>>(
        `/tickets/${ticketId}/move`,
        { new_epic_id: newEpicId }
      )
      return response.data
    },

    complete: async (ticketId: string, prLink: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(
        `/tickets/${ticketId}/complete`,
        { pr_link: prLink }
      )
      return toTicket(response.data)
    },

    question: async (ticketId: string, question: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(
        `/tickets/${ticketId}/question`,
        { question_text: question }
      )
      return toTicket(response.data)
    },

    start: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(`/tickets/${ticketId}/start`)
      return toTicket(response.data)
    },

    listByEpic: async (epicId: string, filters?: {
      skip?: number
      limit?: number
      status_filter?: string
    }): Promise<Ticket[]> => {
      const response = await apiClient.get<any[]>(
        `/tickets/by-epic/${epicId}`,
        { params: filters }
      )
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw.map(toTicket) : []
    },

    listMyWorkbench: async (): Promise<Ticket[]> => {
      const response = await apiClient.get<any[]>('/tickets/my-workbench')
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw.map(toTicket) : []
    },

    moveToEpic: async (data: { ticketId: string; newEpicId: string }): Promise<Ticket> => {
      const response = await apiClient.patch<any>(
        `/tickets/${data.ticketId}/move`,
        { new_epic_id: data.newEpicId }
      )
      return toTicket(unwrapResponseData<any>(response.data))
    },

    reorder: async (ticketId: string, newIndex: number): Promise<Ticket> => {
      const response = await apiClient.patch<any>(
        `/tickets/${ticketId}/reorder`,
        { new_index: newIndex }
      )
      return toTicket(unwrapResponseData<any>(response.data))
    },

    updateStatus: async (ticketId: string, status: TicketStatus): Promise<Ticket> => {
      if (status === 'IN_PROGRESS') {
        return await realApi.tickets.start(ticketId)
      }
      return await realApi.tickets.update(ticketId, { status })
    },

    raiseQuestion: async (ticketId: string, question: string): Promise<Ticket> => {
      return await realApi.tickets.question(ticketId, question)
    },

    getTeamMembers: async (epicId?: string): Promise<User[]> => {
      const response = await apiClient.get<any>('/tickets/team-members', {
        params: epicId ? { epic_id: epicId } : {}
      })
      const items: any[] = Array.isArray(response.data) ? response.data : []
      return items.map((m: any) => ({
        ...m,
        fullName: m.full_name ?? m.fullName ?? m.email,
      })) as unknown as User[]
    },

    resolveQuestion: async (ticketId: string, _questionId?: string, answer?: string): Promise<Ticket> => {
      const response = await apiClient.post<Ticket>(
        `/tickets/${ticketId}/resolve-question`,
        { resolution: answer || 'Pregunta resuelta' }
      )
      return response.data
    },

    redirect: async (ticketId: string, newAssigneeIdOrData: string | { toUserId: string; reason: string }, reason?: string): Promise<Ticket> => {
      const targetUserId = typeof newAssigneeIdOrData === 'string' ? newAssigneeIdOrData : newAssigneeIdOrData.toUserId
      const redirectReason = typeof newAssigneeIdOrData === 'string' ? (reason || 'Sin motivo especificado') : newAssigneeIdOrData.reason

      const response = await apiClient.post<Ticket>(
        `/tickets/${ticketId}/redirect`,
        { to_user_id: targetUserId, justification: redirectReason }
      )
      return toTicket(response.data)
    },

    getEvents: async (ticketId: string): Promise<any[]> => {
      const response = await apiClient.get<any[]>(`/tickets/${ticketId}/events`)
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw : []
    }
  },

  subtasks: {
    create: async (ticketId: string, data: Omit<Subtask, 'id' | 'createdAt' | 'completedAt'>): Promise<Subtask> => {
      const response = await apiClient.post<ApiResponse<Subtask>>(
        `/tickets/${ticketId}/subtasks/`,
        {
          title: data.title,
          ticket_id: ticketId
        }
      )
      return toSubtask(unwrapResponseData<Subtask>(response))
    },

    update: async (ticketId: string, subtaskId: string, data: Partial<Subtask>): Promise<Subtask> => {
      const response = await apiClient.put<ApiResponse<Subtask>>(
        `/tickets/${ticketId}/subtasks/${subtaskId}`,
        {
          title: data.title,
          is_completed: data.isCompleted,
          order_index: data.orderIndex
        }
      )
      return toSubtask(unwrapResponseData<Subtask>(response))
    },

    delete: async (ticketId: string, subtaskId: string): Promise<void> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/tickets/${ticketId}/subtasks/${subtaskId}`
      )
      return unwrapResponseData<void>(response)
    },

    reorder: async (ticketId: string, subtaskIds: string[]): Promise<Subtask[]> => {
      const response = await apiClient.patch<ApiResponse<Subtask[]>>(
        `/tickets/${ticketId}/subtasks/reorder`,
        { subtask_ids: subtaskIds }
      )
      return unwrapResponseData<Subtask[]>(response)
    }
  },

  analytics: {
    getSummary: async (filters?: {
      startDate?: string
      endDate?: string
      applicationId?: string
    }): Promise<ApiResponse<AnalyticsSummary>> => {
      const appId = filters?.applicationId || ''
      const response = await apiClient.get<ApiResponse<AnalyticsSummary>>(
        `/analytics/summary/${appId}`,
        { params: { startDate: filters?.startDate, endDate: filters?.endDate } }
      )
      return response.data
    },

    getPerformance: async (filters: {
      applicationId: string
      startDate?: string
      endDate?: string
    }): Promise<UserPerformance[]> => {
      const response = await apiClient.get<any>(
        `/analytics/performance/${filters.applicationId}`,
        { params: { start_date: filters.startDate, end_date: filters.endDate } }
      )
      const raw = response.data
      const users: any[] = Array.isArray(raw) ? raw : (raw?.user_performance ?? [])
      return users.map(toUserPerformance)
    },

    getHeatmap: async (applicationId: string, filters?: {
      startDate?: string
      endDate?: string
    }): Promise<any> => {
      const response = await apiClient.get<any>(
        `/analytics/heatmap/${applicationId}`,
        { params: filters }
      )
      return response.data
    },

    getBurndown: async (epicId: string, filters?: {
      startDate?: string
      endDate?: string
    }): Promise<ApiResponse<BurndownData>> => {
      const response = await apiClient.get<ApiResponse<BurndownData>>(
        `/analytics/burndown/${epicId}`,
        { params: filters }
      )
      return response.data
    },

    getSupportSummary: async (): Promise<SupportSummary> => {
      const response = await apiClient.get<SupportSummary>('/analytics/support-summary')
      return response.data
    }
  },

  documents: {
    list: async (filters?: {
      ticketId?: string
      epicId?: string
    }): Promise<ApiResponse<Document[]>> => {
      const response = await apiClient.get<any>(
        '/documents/',
        { params: filters }
      )
      const raw: any[] = Array.isArray(response.data) ? response.data : (response.data?.data ?? [])
      const mapped: Document[] = raw.map((d: any) => ({
        ...d,
        uploadedById: d.uploadedById ?? d.uploaded_by_id ?? '',
        uploadedBy: d.uploaded_by
          ? {
              id: d.uploaded_by.id,
              fullName: d.uploaded_by.full_name ?? d.uploaded_by.fullName ?? undefined,
              email: d.uploaded_by.email,
            }
          : undefined,
        docType: d.docType ?? d.doc_type,
        createdAt: d.createdAt ?? d.created_at,
        epicId: d.epicId ?? d.epic_id,
        ticketId: d.ticketId ?? d.ticket_id,
        fileSize: d.fileSize ?? d.file_size,
        mimeType: d.mimeType ?? d.mime_type,
      }))
      return mapped as unknown as ApiResponse<Document[]>
    },

    upload: async (file: File, data: {
      ticketId?: string
      epicId?: string
      docType?: string
    }): Promise<ApiResponse<Document>> => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('ticketId', data.ticketId || '')
      formData.append('epicId', data.epicId || '')
      formData.append('docType', data.docType || 'OTHER')

      const response = await apiClient.post<ApiResponse<Document>>(
        '/documents/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      )
      return response.data
    },

    download: async (documentId: string): Promise<void> => {
      const response = await apiClient.get<Blob>(
        `/documents/${documentId}/download`,
        { responseType: 'blob' }
      )
      const disposition: string = (response.headers as any)['content-disposition'] ?? ''
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      const filename = match ? match[1].replace(/['"]/g, '') : documentId

      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    },

    delete: async (documentId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/documents/${documentId}`
      )
      return response.data
    },

    translate: async (documentId: string, targetLanguage: string): Promise<TranslateResponse> => {
      const response = await apiClient.post<any>(
        `/documents/${documentId}/translate`,
        { target_language: targetLanguage },
        { timeout: 600_000 }
      )
      return toTranslateResponse(response.data)
    },

    translateDownload: async (documentId: string, targetLanguage: string): Promise<void> => {
      const response = await apiClient.post(
        `/documents/${documentId}/translate/download`,
        { target_language: targetLanguage },
        { responseType: 'blob', timeout: 600_000 }
      )
      const disposition: string = (response.headers as any)['content-disposition'] ?? ''
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      const filename = match ? match[1].replace(/['"]/g, '') : `translated_${targetLanguage}.txt`

      const url = window.URL.createObjectURL(response.data as Blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }
  },

  notifications: {
    list: async (filters?: {
      unreadOnly?: boolean
      type?: string
      page?: number
      limit?: number
    }): Promise<ApiResponse<PaginatedResponse<Notification>>> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Notification>>>(
        '/notifications/',
        { params: filters }
      )
      return response.data
    },

    getUnreadCount: async (): Promise<ApiResponse<{ count: number }>> => {
      const response = await apiClient.get<ApiResponse<{ count: number }>>(
        '/notifications/unread-count'
      )
      return response.data
    },

    markRead: async (notificationId: string): Promise<ApiResponse<Notification>> => {
      const response = await apiClient.post<ApiResponse<Notification>>(
        '/notifications/mark-read',
        { notification_ids: [notificationId] }
      )
      return response.data
    },

    markAllRead: async (): Promise<ApiResponse<{ markedCount: number }>> => {
      const response = await apiClient.post<ApiResponse<{ markedCount: number }>>(
        '/notifications/mark-all-read'
      )
      return response.data
    },

    delete: async (notificationId: string): Promise<void> => {
      await apiClient.delete(`/notifications/${notificationId}`)
    },

    deleteAllRead: async (): Promise<void> => {
      await apiClient.delete('/notifications/read')
    }
  },

  team: {
    list: async (): Promise<User[]> => {
      const response = await apiClient.get<any>('/users/')
      const data = unwrapResponseData<any>(response)
      const items = Array.isArray(data) ? data : (data?.items ?? data?.data ?? [])
      return items.map((u: any) => mapUserFromApi(u as Record<string, unknown>))
    },

    listByApplication: async (appId: string): Promise<User[]> => {
      const response = await apiClient.get<any>('/users/', { params: { application_id: appId } })
      const data = unwrapResponseData<any>(response)
      const items = Array.isArray(data) ? data : (data?.items ?? data?.data ?? [])
      return items.map((u: any) => mapUserFromApi(u as Record<string, unknown>))
    },

    updateMember: async (id: string, data: Partial<User>): Promise<User> => {
      const response = await apiClient.put<Record<string, unknown>>(`/users/${id}`, mapUserUpdateToApi(data))
      return mapUserFromApi(response.data)
    },

    deleteMember: async (id: string, hardDelete: boolean = false): Promise<void> => {
      await apiClient.delete(`/users/${id}`, { 
        params: { hard_delete: hardDelete } 
      })
    },

    promoteToLeader: async (userId: string): Promise<User> => {
      const response = await apiClient.post<any>(`/users/${userId}/change-role`, { role: 'TEAM_LEADER' })
      return mapUserFromApi(unwrapResponseData<Record<string, unknown>>(response))
    },

    demoteLeader: async (userId: string): Promise<User> => {
      const response = await apiClient.post<any>(`/users/${userId}/change-role`, { role: 'DEVELOPER' })
      return mapUserFromApi(unwrapResponseData<Record<string, unknown>>(response))
    },

    getUnassignedTickets: async (appId: string): Promise<Ticket[]> => {
      const response = await apiClient.get<any>('/tickets/', { params: { application_id: appId, unassigned: true } })
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw.map(toTicket) : []
    },

    assignTicket: async (ticketId: string, userId: string): Promise<Ticket> => {
      const response = await apiClient.put<Ticket>(`/tickets/${ticketId}`, { assignee_id: userId })
      return response.data
    },

    unassignTicket: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.put<Ticket>(`/tickets/${ticketId}`, { assignee_id: null })
      return response.data
    },
  },

  supportTickets: {
    list: async (filters?: { status?: string; severity?: string; assigneeId?: string; skip?: number; limit?: number }): Promise<Ticket[]> => {
      const params: Record<string, any> = {}
      if (filters?.status) params.status_filter = filters.status
      if (filters?.severity) params.severity_filter = filters.severity
      if (filters?.assigneeId) params.assignee_id = filters.assigneeId
      if (filters?.skip !== undefined) params.skip = filters.skip
      if (filters?.limit !== undefined) params.limit = filters.limit
      const response = await apiClient.get<any[]>('/support-tickets/', { params })
      return Array.isArray(response.data) ? response.data.map(toTicket) : []
    },

    create: async (data: {
      title: string
      description?: string
      severity?: string
      stackTrace?: string
      reproductionSteps?: string
      browser?: string
      operatingSystem?: string
      linkedTicketId?: string
    }): Promise<Ticket> => {
      const response = await apiClient.post<any>('/support-tickets/', {
        title: data.title,
        description: data.description,
        severity: data.severity ?? 'MEDIUM',
        stack_trace: data.stackTrace,
        reproduction_steps: data.reproductionSteps,
        browser: data.browser,
        operating_system: data.operatingSystem,
        linked_ticket_id: data.linkedTicketId,
      })
      return toTicket(response.data)
    },

    getById: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.get<any>(`/support-tickets/${ticketId}`)
      return toTicket(response.data)
    },

    update: async (ticketId: string, data: {
      title?: string
      description?: string
      severity?: string
      stackTrace?: string
      reproductionSteps?: string
      browser?: string
      operatingSystem?: string
      linkedTicketId?: string
    }): Promise<Ticket> => {
      const response = await apiClient.put<any>(`/support-tickets/${ticketId}`, {
        title: data.title,
        description: data.description,
        severity: data.severity,
        stack_trace: data.stackTrace,
        reproduction_steps: data.reproductionSteps,
        browser: data.browser,
        operating_system: data.operatingSystem,
        linked_ticket_id: data.linkedTicketId,
      })
      return toTicket(response.data)
    },

    assign: async (ticketId: string, assigneeId: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(`/support-tickets/${ticketId}/assign`, { assignee_id: assigneeId })
      return toTicket(response.data)
    },

    investigate: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(`/support-tickets/${ticketId}/investigate`)
      return toTicket(response.data)
    },

    resolve: async (ticketId: string, prLink: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(`/support-tickets/${ticketId}/resolve`, { pr_link: prLink })
      return toTicket(response.data)
    },

    getEvents: async (ticketId: string): Promise<any[]> => {
      const response = await apiClient.get<any[]>(`/support-tickets/${ticketId}/events`)
      return Array.isArray(response.data) ? response.data : []
    },

    listLinkableTickets: async (): Promise<Ticket[]> => {
      const response = await apiClient.get<any[]>('/tickets/', { params: { limit: 100 } })
      return Array.isArray(response.data) ? response.data.map(toTicket) : []
    },
  },

  incidents: {
    list: async (filters?: { page?: number, limit?: number, application_id?: string, status?: string }): Promise<PaginatedResponse<Incident>> => {
      const response = await apiClient.get<any>('/incidents/', { params: filters })
      const data = response.data
      
      if (Array.isArray(data)) {
        return {
          items: data.map(toIncident),
          total: data.length,
          page: 1,
          limit: data.length,
          totalPages: 1
        }
      }
      
      return {
        ...data,
        items: Array.isArray(data?.items) ? data.items.map(toIncident) : []
      }
    },
    
    getById: async (incidentId: string): Promise<Incident> => {
      const response = await apiClient.get<any>(`/incidents/${incidentId}`)
      return toIncident(response.data)
    },
    
    create: async (data: any): Promise<Incident> => {
      const response = await apiClient.post<any>('/incidents/', data)
      return toIncident(response.data)
    },
    
    update: async (incidentId: string, data: any): Promise<Incident> => {
      const response = await apiClient.patch<any>(`/incidents/${incidentId}`, data)
      return toIncident(response.data)
    },
    
    updateStatus: async (incidentId: string, status: string): Promise<Incident> => {
      const response = await apiClient.patch<any>(`/incidents/${incidentId}/status`, { status })
      return toIncident(response.data)
    }
  },

  meetings: {
    list: async (filters?: { limit?: number, application_id?: string }): Promise<Meeting[]> => {
      const response = await apiClient.get<any[]>('/meetings/', { params: filters })
      return Array.isArray(response.data) ? response.data.map(toMeeting) : []
    },
    
    getById: async (meetingId: string): Promise<Meeting> => {
      const response = await apiClient.get<any>(`/meetings/${meetingId}`)
      return toMeeting(response.data)
    },
    
    create: async (data: any): Promise<Meeting> => {
      const response = await apiClient.post<any>('/meetings/', data)
      return toMeeting(response.data)
    },
    
    update: async (meetingId: string, data: any): Promise<Meeting> => {
      const response = await apiClient.patch<any>(`/meetings/${meetingId}`, data)
      return toMeeting(response.data)
    },
    
    setAttendance: async (
      meetingId: string,
      data: { user_id: string; status: string; notes?: string }
    ): Promise<MeetingAttendance> => {
      const response = await apiClient.post<any>(`/meetings/${meetingId}/attendance`, data)
      return toMeetingAttendance(response.data)
    },
    
    updateSummary: async (meetingId: string, summary: string): Promise<Meeting> => {
      const response = await apiClient.patch<any>(`/meetings/${meetingId}`, { summary_markdown: summary })
      return toMeeting(response.data)
    }
  },
}

export const setAuthTokens = (tokens: AuthTokens): void => {
  authState.accessToken = tokens.accessToken
}

export const clearAuthTokens = (): void => {
  authState.accessToken = null
}

export const api = realApi
export default api
export { apiClient }