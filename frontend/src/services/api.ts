/**
 * Servicio de API para CoreStream
 *
 * Centraliza toda la comunicación con el backend de FastAPI.
 * Proporciona:
 * - Instancia de Axios configurada con base URL, headers por defecto, etc.
 * - Interceptores para manejo automático de tokens JWT y renovación
 * - Métodos tipados para cada endpoint del API
 * - Manejo de errores consistente
 *
 * Todas las llamadas al API deben ir a través de este servicio.
 *
 * MODO PROTOTIPO:
 * Si VITE_MODO_PROTOTIPO=true, el frontend NO hace queries al backend
 * Todos los datos se guardan en localStorage y se devuelven valores mockeados
 */

import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios'
import type {
  User,
  UserRole,
  Application,
  Epic,
  Ticket,
  Subtask,
  TicketStatus,
  TicketPriority,
  Notification,
  Document,
  AnalyticsSummary,
  AuthTokens,
  ApiResponse,
  LoginRequest,
  RegisterRequest,
  TicketFilters,
  PaginatedResponse,
  Incident,
  Meeting,
  MeetingAttendance,
  UserPerformance,
  HeatmapData,
  BurndownData,
  SupportSummary,
  TranslateResponse
} from '@/types'

/**
 * Interfaz para estado de autenticación
 * Se utiliza en el store de Pinia para mantener tokens
 */
interface AuthState {
  accessToken: string | null
  refreshToken: string | null
}

/**
 * Variable global para almacenar tokens
 * En una aplicación real, esto vendría del store de Pinia
 * Aquí se mantiene por simplicidad
 */
let authState: AuthState = {
  accessToken: null,
  refreshToken: null
}

/**
 * Extrae la carga útil real de respuestas que pueden venir directas o
 * envueltas en un objeto { data }.
 */
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
  isPresent: raw.isPresent ?? raw.is_present ?? false,
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

/**
 * Crea y configura la instancia de Axios
 * 
 * Configuración:
 * - Base URL: /api (se usa proxy de Vite para redirigir a localhost:8000)
 * - Timeout: 30 segundos
 * - Headers por defecto: Content-Type application/json
 * 
 * @returns Instancia de Axios configurada
 */
const createApiClient = (): AxiosInstance => {
  const instance = axios.create({
    /**
     * Base URL para todas las solicitudes
     * Las URLs relativas se combinarán con esta base
     * El proxy de Vite redirigirá /api a http://localhost:8000
     */
    baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',

    /**
     * Timeout en milisegundos para todas las solicitudes
     */
    timeout: 30000,

    /**
     * Headers por defecto para todas las solicitudes
     */
    headers: {
      /**
       * Content-Type: especifica que estamos enviando JSON
       */
      'Content-Type': 'application/json'
    }
  })

  /**
   * INTERCEPTOR DE REQUEST
   * 
   * Se ejecuta antes de que se envíe cada solicitud.
   * Aquí agregamos el token JWT en el header Authorization si existe.
   */
  instance.interceptors.request.use(
    (config) => {
      /**
       * Si existe un token de acceso, lo agregamos al header Authorization
       * Formato: Bearer <token>
       * Primero intenta authState, luego localStorage como fallback
       */
      let token = authState.accessToken
      
      // Si no hay token en authState, intenta localStorage
      if (!token) {
        try {
          const storedToken = localStorage.getItem('accessToken')
          if (storedToken) {
            token = storedToken
            authState.accessToken = storedToken
          }
        } catch (e) {
          // localStorage no disponible en algunos contextos
        }
      }
      
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

    /**
     * En caso de error en la preparación de la solicitud
     */
    (error) => {
      return Promise.reject(error)
    }
  )

  /**
   * INTERCEPTOR DE RESPONSE
   * 
   * Se ejecuta cuando se recibe una respuesta.
   * Maneja:
   * - Errores 401 (Unauthorized): intenta renovar el token
   * - Otros errores: propaga el error
   */
  instance.interceptors.response.use(
    /**
     * Respuesta exitosa: retorna tal cual
     */
    (response) => response,

    /**
     * Respuesta con error
     * Principalmente maneja tokens expirados
     */
    async (error: AxiosError) => {
      /**
       * Obtiene la solicitud original que falló
       * Se puede usar para reintentar
       */
      const originalRequest = error.config as any

      /**
       * Si el error es 401 (Unauthorized) y no hemos intentado renovar ya
       * (para evitar loops infinitos)
       */
      if (error.response?.status === 401 && !originalRequest._retry) {
        /**
         * Marca que ya hemos intentado renovar este request
         */
        originalRequest._retry = true

        /**
         * Intenta renovar el token usando el refresh token
         */
        const storedRefresh = authState.refreshToken ?? (typeof localStorage !== 'undefined' ? localStorage.getItem('refreshToken') : null)
        if (storedRefresh) {
          authState.refreshToken = storedRefresh
          try {
            /**
             * Solicitud especial para renovar el token
             * Usa directamente axios (no la instancia con interceptores)
             * para evitar recursión infinita
             */
            const response = await axios.post<Record<string, unknown>>(
              '/api/auth/refresh',
              { refresh_token: authState.refreshToken }
            )

            const d = response.data
            if (d && typeof d === 'object' && 'access_token' in d) {
              const mapped = mapTokenResponse(d as Record<string, unknown>)
              authState.accessToken = mapped.accessToken
              authState.refreshToken = mapped.refreshToken

              if (typeof localStorage !== 'undefined') {
                localStorage.setItem('accessToken', mapped.accessToken)
                localStorage.setItem('refreshToken', mapped.refreshToken)
              }

              /**
               * Actualiza el header Authorization del request original
               */
              originalRequest.headers.Authorization = `Bearer ${authState.accessToken}`

              /**
               * Reintenta el request original con el nuevo token
               */
              return instance(originalRequest)
            }
          } catch (refreshError) {
            /**
             * Si la renovación falla (refresh token expirado),
             * limpia los tokens y rechaza la promesa
             * El usuario será redirigido a login
             */
            authState.accessToken = null
            authState.refreshToken = null

            return Promise.reject(refreshError)
          }
        } else {
          /**
           * No hay refresh token disponible
           * Limpia tokens y rechaza
           */
          authState.accessToken = null
          authState.refreshToken = null
        }
      }

      /**
       * Propaga el error para que sea manejado por quien llamó
       */
      return Promise.reject(error)
    }
  )

  return instance
}

/**
 * Instancia de Axios lista para usar
 */
const apiClient = createApiClient()

/**
 * Convierte una épica devuelta por FastAPI (snake_case) al tipo Epic del frontend.
 */
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
    preferences: raw.preferences || {}
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
    refreshToken: String(d.refresh_token ?? ''),
    tokenType: String(d.token_type ?? 'bearer'),
    expiresIn: typeof d.expires_in === 'number' ? d.expires_in : undefined,
  }
}

/**
 * OBJETO API
 *
 * Contiene todos los métodos para comunicarse con el backend.
 * Los métodos están organizados por dominio (auth, users, applications, etc.)
 * para mantener orden y facilitar el mantenimiento.
 *
 * Todos los métodos retornan Promesas tipadas con tipos de TypeScript.
 *
 * NOTA: Si VITE_MODO_PROTOTIPO=true, este objeto será reemplazado por mockApi
 * al final de este archivo para usar localStorage en lugar del backend real.
 */
// Mapea la respuesta snake_case del backend al tipo UserPerformance camelCase del frontend.
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

// Mapper CS-040: convierte respuesta snake_case de POST /documents/{id}/translate
function toTranslateResponse(raw: any): TranslateResponse {
  return {
    documentId:       raw.document_id,
    originalFilename: raw.original_filename,
    targetLanguage:   raw.target_language,
    translatedText:   raw.translated_text,
  }
}

const realApi = {
  /**
   * ========================================
   * MÓDULO DE AUTENTICACIÓN
   * ========================================
   * 
   * Maneja login, registro, tokens y sesión del usuario
   */
  auth: {
    /**
     * Autentica un usuario con correo y contraseña
     * 
     * @param credentials - Email y contraseña del usuario
     * @returns Respuesta con usuario y tokens de autenticación
     * 
     * @example
     * const response = await api.auth.login({ email: 'user@example.com', password: '123456' })
     * // Guarda tokens en el store y redirige al dashboard
     */
    /**
     * Login: FastAPI devuelve TokenResponse (access_token, refresh_token, ...).
     */
    login: async (credentials: LoginRequest): Promise<{ tokens: AuthTokens }> => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/auth/login',
        credentials
      )
      return { tokens: mapTokenResponse((response.data ?? {}) as Record<string, unknown>) }
    },

    /**
     * Registro: el backend devuelve UserResponse (sin tokens).
     */
    register: async (data: RegisterRequest): Promise<User> => {
      const response = await apiClient.post<Record<string, unknown>>('/auth/register', {
        email: data.email,
        password: data.password,
        full_name: data.fullName,
      })
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    /**
     * Refresh: cuerpo { refresh_token } según el backend.
     */
    refresh: async (refreshToken: string): Promise<AuthTokens> => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/auth/refresh',
        { refresh_token: refreshToken }
      )
      return mapTokenResponse((response.data ?? {}) as Record<string, unknown>)
    },

    getMe: async (): Promise<User> => {
      const response = await apiClient.get<Record<string, unknown>>('/auth/me')
      return mapUserFromApi((response.data ?? {}) as Record<string, unknown>)
    },

    /** Alias usado en pinia (stores/auth) */
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

    /** Alias usado en stores/auth */
    updateProfile: async (data: Partial<User>): Promise<User> => {
      return realApi.auth.updateMe(data)
    },

    logout: async (): Promise<void> => {
      try {
        await apiClient.post('/auth/logout')
      } catch {
        /* ignorar 404/401 al cerrar */
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

    deleteAccount: async (): Promise<void> => {
      // Endpoint típico para eliminar la propia cuenta
      await apiClient.delete('/auth/me')
      clearAuthTokens()
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

  /**
   * ========================================
   * MÓDULO DE USUARIOS
   * ========================================
   * 
   * Gestión de usuarios del sistema (solo para administradores)
   */
  users: {
    /**
     * Obtiene lista de todos los usuarios del sistema
     * 
     * @param filters - Filtros opcionales (página, límite, rol, búsqueda)
     * @returns Array paginado de usuarios
     * 
     * @example
     * const { items: usuarios } = await api.users.list({ limit: 20, page: 1 })
     */
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

    /**
     * Obtiene los detalles de un usuario específico
     * 
     * @param userId - ID del usuario
     * @returns Objeto usuario
     */
    getById: async (userId: string): Promise<ApiResponse<User>> => {
      const response = await apiClient.get<ApiResponse<User>>(`/users/${userId}`)
      return response.data
    },

    /**
     * Actualiza un usuario existente
     * Solo administradores pueden actualizar otros usuarios
     * 
     * @param userId - ID del usuario
     * @param data - Campos a actualizar
     * @returns Usuario actualizado
     */
    update: async (userId: string, data: Partial<User>): Promise<ApiResponse<User>> => {
      const response = await apiClient.put<ApiResponse<User>>(
        `/users/${userId}`,
        data
      )
      return response.data
    },

    /**
     * Elimina (desactiva) un usuario del sistema
     * 
     * @param userId - ID del usuario a eliminar
     */
    delete: async (userId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(`/users/${userId}`)
      return response.data
    },

    /**
     * Cambia el rol de un usuario
     * Solo administradores pueden cambiar roles
     * 
     * @param userId - ID del usuario
     * @param newRole - Nuevo rol (ADMIN, TEAM_LEADER, DEVELOPER)
     * @returns Usuario con rol actualizado
     */
    changeRole: async (userId: string, newRole: UserRole): Promise<ApiResponse<User>> => {
      const response = await apiClient.post<ApiResponse<User>>(
        `/users/${userId}/change-role`,
        { role: newRole }
      )
      return response.data
    },

    /**
     * Obtiene estadísticas de rendimiento de un usuario
     * 
     * @param userId - ID del usuario
     * @returns Métricas de rendimiento
     */
    getStats: async (userId: string): Promise<ApiResponse<UserPerformance>> => {
      const response = await apiClient.get<ApiResponse<UserPerformance>>(
        `/users/${userId}/stats`
      )
      return response.data
    }
  },

  /**
   * ========================================
   * MÓDULO DE APLICACIONES
   * ========================================
   * 
   * CRUD de aplicaciones (proyectos)
   */
  applications: {
    /**
     * Obtiene lista de todas las aplicaciones
     * 
     * @param filters - Filtros opcionales
     * @returns Array de aplicaciones
     * 
     * @example
     * const aplicaciones = await api.applications.list()
     */
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

    /**
     * Crea una nueva aplicación
     * 
     * @param data - Datos de la nueva aplicación
     * @returns Aplicación creada
     * 
     * @example
     * const app = await api.applications.create({
     *   name: 'Mi Aplicación',
     *   description: 'Descripción...',
     *   color: '#2563EB',
     *   icon: 'star'
     * })
     */
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

    /**
     * Obtiene detalles de una aplicación específica
     * 
     * @param appId - ID de la aplicación
     * @returns Aplicación con todos sus detalles
     */
    getById: async (appId: string): Promise<Application> => {
      const response = await apiClient.get<ApiResponse<Application>>(
        `/applications/${appId}`
      )
      return toApplication(unwrapResponseData<any>(response))
    },

    /**
     * Actualiza una aplicación existente
     * 
     * @param appId - ID de la aplicación
     * @param data - Campos a actualizar
     * @returns Aplicación actualizada
     */
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

    /**
     * Elimina una aplicación
     * 
     * @param appId - ID de la aplicación
     */
    delete: async (appId: string): Promise<void> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/applications/${appId}`
      )
      return unwrapResponseData<void>(response)
    }
  },

  /**
   * ========================================
   * MÓDULO DE ÉPICAS
   * ========================================
   * 
   * CRUD de épicas dentro de aplicaciones
   */
  epics: {
    /**
     * Lista épicas de una aplicación (GET /epics/by-app/{app_id})
     */
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

    /**
     * Crea una nueva épica
     * 
     * @param appId - ID de la aplicación
     * @param data - Datos de la nueva épica
     * @returns Épica creada
     */
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


    /** Detalle por ID (GET /epics/{epic_id}) */
    getById: async (epicId: string): Promise<Epic> => {
      const response = await apiClient.get<Record<string, unknown>>(`/epics/${epicId}`)
      return mapEpicFromApi(response.data as Record<string, unknown>)
    },

    /** Actualización (PUT /epics/{epic_id}) */
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

    /**
     * CS-012: Reordenar prioridad (PATCH /epics/{epic_id}/reorder)
     * El backend ajusta order_index de las épicas hermanas.
     */
    reorder: async (epicId: string, newIndex: number): Promise<Epic> => {
      const response = await apiClient.patch<Record<string, unknown>>(
        `/epics/${epicId}/reorder`,
        { new_index: newIndex }
      )
      return mapEpicFromApi(response.data as Record<string, unknown>)
    },

    /**
     * Carga un documento asociado a una épica
     * 
     * @param appId - ID de la aplicación
     * @param epicId - ID de la épica
     * @param file - Archivo a cargar
     * @returns Documento creado
     */
    uploadDoc: async (appId: string, epicId: string, file: File): Promise<Document> => {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post<ApiResponse<Document>>(
        `/applications/${appId}/epics/${epicId}/documents`,
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

  /**
   * ========================================
   * MÓDULO DE TICKETS
   * ========================================
   * 
   * CRUD de tareas/tickets
   */
  tickets: {
    /**
     * Obtiene lista de tickets con filtros opcionales
     * 
     * @param filters - Filtros para búsqueda y paginación
     * @returns Array paginado de tickets
     * 
     * @example
     * const tickets = await api.tickets.list({
     *   applicationId: 'app-123',
     *   status: 'TODO',
     *   assigneeId: 'user-456'
     * })
     */
    list: async (filters?: TicketFilters): Promise<ApiResponse<PaginatedResponse<Ticket>>> => {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Ticket>>>(
        '/tickets/',
        { params: filters }
      )
      return response.data
    },

    /**
     * Crea un nuevo ticket
     * * @param data - Datos del nuevo ticket
     * @returns Ticket creado
     */
    create: async (data: Omit<Ticket, 'id' | 'createdAt' | 'updatedAt' | 'createdById'>): Promise<Ticket> => {
      // 1. Convertimos temporalmente a any para leer las variables
      const rawData = data as any; 
      
      // 2. Armamos la caja EXACTAMENTE como la pide FastAPI (snake_case)
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

    /**
     * Obtiene detalles de un ticket específico
     *
     * @param ticketId - ID del ticket
     * @returns Ticket con detalles completos (subtareas, eventos, etc.)
     */
    getById: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.get<any>(`/tickets/${ticketId}`)
      return toTicket(response.data)
    },

    /**
     * Actualiza un ticket existente
     *
     * @param ticketId - ID del ticket
     * @param data - Campos a actualizar
     * @returns Ticket actualizado
     */
    update: async (ticketId: string, data: Partial<Ticket>): Promise<Ticket> => {
      const response = await apiClient.put<any>(`/tickets/${ticketId}`, data)
      return toTicket(response.data)
    },

    /**
     * Elimina un ticket
     * 
     * @param ticketId - ID del ticket
     */
    delete: async (ticketId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/tickets/${ticketId}`
      )
      return response.data
    },

    /**
     * Mueve un ticket a otra épica
     * Se utiliza con drag & drop entre épicas
     * 
     * @param ticketId - ID del ticket
     * @param newEpicId - ID de la nueva épica
     * @param newOrderIndex - Nuevo índice de orden
     * @returns Ticket actualizado
     */
    move: async (ticketId: string, newEpicId: string, _newOrderIndex?: number): Promise<ApiResponse<Ticket>> => {
      const response = await apiClient.post<ApiResponse<Ticket>>(
        `/tickets/${ticketId}/move`,
        { new_epic_id: newEpicId }
      )
      return response.data
    },

    /**
     * Marca un ticket como completado
     * 
     * @param ticketId - ID del ticket
     * @param prLink - Link del Pull Request
     * @returns Ticket actualizado
     */
    complete: async (ticketId: string, prLink: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(
        `/tickets/${ticketId}/complete`,
        { pr_link: prLink }
      )
      return toTicket(response.data)
    },

    /**
     * Plantea una pregunta sobre un ticket (genera evento de pregunta)
     *
     * @param ticketId - ID del ticket
     * @param question - Texto de la pregunta
     * @returns Evento de pregunta creado
     */
    question: async (ticketId: string, question: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(
        `/tickets/${ticketId}/question`,
        { question_text: question }
      )
      return toTicket(response.data)
    },

    /**
     * Resuelve una pregunta sobre un ticket
     * 
     * @param ticketId - ID del ticket
     * @param questionId - ID de la pregunta
     * @param answer - Respuesta a la pregunta
     * @returns Evento de resolución
     */
    /**
     * Redirige un ticket a otro desarrollador/equipo
     * 
     * @param ticketId - ID del ticket
     * @param newAssigneeId - ID del nuevo asignado
     * @param reason - Razón de la redirección
     * @returns Ticket actualizado
     */
   

    /**
     * Marca un ticket como iniciado (cambia estado a IN_PROGRESS)
     * 
     * @param ticketId - ID del ticket
     * @returns Ticket actualizado
     */
    start: async (ticketId: string): Promise<Ticket> => {
      const response = await apiClient.post<any>(`/tickets/${ticketId}/start`)
      return toTicket(response.data)
    },

    /**
     * Obtiene el workbench del usuario actual
     * Lista todas sus tareas activas y pendientes
     * 
     * @returns Array de tickets asignados al usuario actual
     */
    getMyWorkbench: async (): Promise<ApiResponse<Ticket[]>> => {
      const response = await apiClient.get<ApiResponse<Ticket[]>>(
        '/tickets/workbench'
      )
      return response.data
    }

    ,

    /**
     * Alias compatible con el store existente para listar tickets por épica.
     */
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

    /**
     * Obtiene el banco de trabajo personal.
     * Sincronizado con el endpoint real del backend: /api/tickets/my-workbench
     */
    listMyWorkbench: async (): Promise<Ticket[]> => {
      const response = await apiClient.get<any[]>('/tickets/my-workbench')
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw.map(toTicket) : []
    },

    /**
     * Alias compatible para mover ticket a otra épica.
     */
    moveToEpic: async (data: { ticketId: string; newEpicId: string }): Promise<Ticket> => {
      const response = await apiClient.post<any>(
        `/tickets/${data.ticketId}/move`,
        { new_epic_id: data.newEpicId }
      )
      return toTicket(unwrapResponseData<any>(response.data))
    },

    /**
     * Reordena un ticket dentro de su épica actual
     */
    reorder: async (ticketId: string, newIndex: number): Promise<Ticket> => {
      const response = await apiClient.patch<any>(
        `/tickets/${ticketId}/reorder`,
        { new_index: newIndex }
      )
      return toTicket(unwrapResponseData<any>(response.data))
    },

    /**
     * Alias compatible para actualizar estado del ticket.
     */
    updateStatus: async (ticketId: string, status: TicketStatus): Promise<Ticket> => {
      if (status === 'IN_PROGRESS') {
        return await realApi.tickets.start(ticketId)
      }
      return await realApi.tickets.update(ticketId, { status })
    },

    /**
     * Alias para levantar preguntas con la firma que espera el store.
     */
    raiseQuestion: async (ticketId: string, question: string): Promise<Ticket> => {
      return await realApi.tickets.question(ticketId, question)
    },

    /**
     * CS-020: Obtiene miembros del equipo para redirección
     * 
     * @param epicId - ID de la épica (opcional)
     * @returns Lista de miembros del equipo
     */
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

    /**
     * Resuelve una pregunta sobre un ticket
     * 
     * @param ticketId - ID del ticket
     * @param questionId - ID de la pregunta
     * @param answer - Respuesta a la pregunta
     * @returns Evento de resolución
     */
    resolveQuestion: async (ticketId: string, _questionId?: string, answer?: string): Promise<Ticket> => {
      const response = await apiClient.post<Ticket>(
        `/tickets/${ticketId}/resolve-question`,
        { resolution: answer || 'Pregunta resuelta' }
      )
      return response.data
    },

    /**
     * Alias para redireccionar tickets con soporte para la firma antigua.
     */
    redirect: async (ticketId: string, newAssigneeIdOrData: string | { toUserId: string; reason: string }, reason?: string): Promise<Ticket> => {
      const targetUserId = typeof newAssigneeIdOrData === 'string' ? newAssigneeIdOrData : newAssigneeIdOrData.toUserId
      const redirectReason = typeof newAssigneeIdOrData === 'string' ? (reason || 'Sin motivo especificado') : newAssigneeIdOrData.reason

      const response = await apiClient.post<Ticket>(
        `/tickets/${ticketId}/redirect`,
        { to_user_id: targetUserId, justification: redirectReason }
      )
      return toTicket(response.data)
    },

    /**
     * Obtiene el historial de eventos de un ticket
     * * @param ticketId - ID del ticket
     * @returns Array de eventos
     */
    getEvents: async (ticketId: string): Promise<any[]> => {
      const response = await apiClient.get<any[]>(`/tickets/${ticketId}/events`)
      // Usamos el des-empaquetador nativo de tu archivo por si FastAPI lo envuelve
      const raw = unwrapResponseData<any[]>(response.data)
      return Array.isArray(raw) ? raw : []
    }
  },

  /**
   * ========================================
   * MÓDULO DE SUBTAREAS
   * ========================================
   * 
   * CRUD de subtareas dentro de tickets
   */
  subtasks: {
    /**
     * Crea una nueva subtarea
     * 
     * @param ticketId - ID del ticket padre
     * @param data - Datos de la subtarea
     * @returns Subtarea creada
     */
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

    /**
     * Actualiza una subtarea
     *
     * @param ticketId - ID del ticket padre
     * @param subtaskId - ID de la subtarea
     * @param data - Campos a actualizar
     * @returns Subtarea actualizada
     */
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

    /**
     * Elimina una subtarea
     * 
     * @param ticketId - ID del ticket padre
     * @param subtaskId - ID de la subtarea
     */
    delete: async (ticketId: string, subtaskId: string): Promise<void> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/tickets/${ticketId}/subtasks/${subtaskId}`
      )
      return unwrapResponseData<void>(response)
    },

    /**
     * Reordena las subtareas de un ticket
     * 
     * @param ticketId - ID del ticket
     * @param subtaskIds - Array de IDs en el nuevo orden
     * @returns Subtareas reordenadas
     */
    reorder: async (ticketId: string, subtaskIds: string[]): Promise<Subtask[]> => {
      const response = await apiClient.patch<ApiResponse<Subtask[]>>(
        `/tickets/${ticketId}/subtasks/reorder`,
        { subtask_ids: subtaskIds }
      )
      return unwrapResponseData<Subtask[]>(response)
    }
  },

  /**
   * ========================================
   * MÓDULO DE ANÁLISIS Y REPORTES
   * ========================================
   *
   * Obtiene datos agregados para análisis y dashboards
   */

  analytics: {
    /**
     * Obtiene resumen general de analítica
     * Incluye métricas globales, rendimiento del equipo, gráficos
     * 
     * @param filters - Filtros opcionales (rango de fechas, etc.)
     * @returns Resumen de analítica
     */
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

    /**
     * Obtiene datos de rendimiento de usuarios
     *
     * @param filters - Filtros opcionales
     * @returns Array de rendimiento por usuario
     */
    getPerformance: async (filters?: {
      applicationId?: string
      startDate?: string
      endDate?: string
    }): Promise<UserPerformance[]> => {
      const appId = filters?.applicationId ?? ''
      const url = appId ? `/analytics/performance/${appId}` : '/analytics/performance'
      const response = await apiClient.get<any>(
        url,
        { params: { start_date: filters?.startDate, end_date: filters?.endDate } }
      )
      // El backend devuelve { application_id, period, user_performance: [...] }
      const raw = response.data
      const users: any[] = Array.isArray(raw) ? raw : (raw?.user_performance ?? [])
      return users.map(toUserPerformance)
    },

    /**
     * Obtiene datos del mapa de calor (heatmap)
     * Muestra actividad de desarrolladores en el tiempo
     * 
     * @param filters - Filtros opcionales
     * @returns Array de datos de mapa de calor
     */
    getHeatmap: async (applicationId: string, filters?: {
      startDate?: string
      endDate?: string
    }): Promise<any> => {
      // Ahora enviamos el applicationId en la URL tal como lo pide el backend
      const response = await apiClient.get<any>(
        `/analytics/heatmap/${applicationId}`,
        { params: filters }
      )
      return response.data
    },

    /**
     * Obtiene datos del gráfico de quemado (burndown)
     * Muestra progreso de trabajo a lo largo del tiempo
     * 
     * @param applicationId - ID de la aplicación
     * @param filters - Filtros opcionales (rango de fechas)
     * @returns Datos de burndown
     */
    getBurndown: async (applicationId: string, filters?: {
      startDate?: string
      endDate?: string
    }): Promise<ApiResponse<BurndownData>> => {
      const response = await apiClient.get<ApiResponse<BurndownData>>(
        `/analytics/burndown/${applicationId}`,
        { params: filters }
      )
      return response.data
    },

    /**
     * Obtiene el resumen de tickets de soporte (global, sin aplicación).
     * Conteos por estado/severidad y tiempo promedio de resolución.
     *
     * @returns Resumen de tickets de soporte
     */
    getSupportSummary: async (): Promise<SupportSummary> => {
      const response = await apiClient.get<SupportSummary>('/analytics/support-summary')
      return response.data
    },
    exportPdf: async (filters?: {
      applicationId?: string
      startDate?: string
      endDate?: string
    }): Promise<Blob> => {
      const response = await apiClient.get<Blob>(
        '/analytics/export/pdf',
        {
          params: filters,
          responseType: 'blob'
        }
      )
      return response.data
    },
    /**
     * Exporta datos de analítica a CSV
     * 
     * @param filters - Filtros para qué datos exportar
     * @returns Blob con contenido CSV
     */
    exportCsv: async (filters?: {
      applicationId?: string
      startDate?: string
      endDate?: string
    }): Promise<Blob> => {
      const response = await apiClient.get<Blob>(
        '/analytics/export/csv',
        {
          params: filters,
          responseType: 'blob'
        }
      )
      return response.data
    }
  },

  /**
   * ========================================
   * MÓDULO DE DOCUMENTOS
   * ========================================
   * 
   * Gestión de archivos adjuntos
   */
  documents: {
    /**
     * Obtiene lista de documentos de un ticket o épica
     * 
     * @param filters - Filtros para qué documentos obtener
     * @returns Array de documentos
     */
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

    /**
     * Carga un nuevo documento
     * 
     * @param file - Archivo a cargar
     * @param data - Metadatos del documento (ticketId, epicId, docType, etc.)
     * @returns Documento creado
     */
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

    /**
     * Descarga un documento
     * Abre en nueva pestaña o descarga según el navegador
     * 
     * @param documentId - ID del documento
     */
    download: async (documentId: string): Promise<void> => {
      const response = await apiClient.get<Blob>(
        `/documents/${documentId}/download`,
        { responseType: 'blob' }
      )

      // Crea un link temporal para descargar
      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      // Fuerza la descarga en lugar de abrir en nueva pestaña.
      // El header Content-Disposition del backend define el nombre final.
      link.download = documentId
      link.click()
      window.URL.revokeObjectURL(url)
    },

    /**
     * Elimina un documento
     * 
     * @param documentId - ID del documento
     */
    delete: async (documentId: string): Promise<ApiResponse<void>> => {
      const response = await apiClient.delete<ApiResponse<void>>(
        `/documents/${documentId}`
      )
      return response.data
    },

    /**
     * Traduce un documento a otro idioma
     * Usa IA/servicio de traducción del backend
     * 
     * @param documentId - ID del documento
     * @param targetLanguage - Idioma destino (es, en, fr, etc.)
     * @returns Documento traducido
     */
    translate: async (documentId: string, targetLanguage: string): Promise<TranslateResponse> => {
      const response = await apiClient.post<any>(
        `/documents/${documentId}/translate`,
        { target_language: targetLanguage },
        { timeout: 600_000 }  // 10 min: documentos grandes con muchos chunks
      )
      return toTranslateResponse(response.data)
    },

    translateDownload: async (documentId: string, targetLanguage: string): Promise<void> => {
      const response = await apiClient.post(
        `/documents/${documentId}/translate/download`,
        { target_language: targetLanguage },
        { responseType: 'blob', timeout: 600_000 }  // 10 min para documentos grandes
      )

      // Extraer nombre de archivo del header Content-Disposition
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

  /**
   * ========================================
   * MÓDULO DE NOTIFICACIONES
   * ========================================
   * 
   * Sistema de notificaciones del usuario
   */
  notifications: {
    /**
     * Obtiene lista de notificaciones del usuario
     * 
     * @param filters - Filtros opcionales (leídas/no leídas, tipo, etc.)
     * @returns Array de notificaciones
     */
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

    /**
     * Obtiene el número de notificaciones no leídas
     * Útil para mostrar un badge en la interfaz
     * 
     * @returns Número de notificaciones no leídas
     */
    getUnreadCount: async (): Promise<ApiResponse<{ count: number }>> => {
      const response = await apiClient.get<ApiResponse<{ count: number }>>(
        '/notifications/unread-count'
      )
      return response.data
    },

    /**
     * Marca una notificación como leída
     * 
     * @param notificationId - ID de la notificación
     * @returns Notificación actualizada
     */
    markRead: async (notificationId: string): Promise<ApiResponse<Notification>> => {
      const response = await apiClient.post<ApiResponse<Notification>>(
        '/notifications/mark-read',
        { notification_ids: [notificationId] }
      )
      return response.data
    },

    /**
     * Marca todas las notificaciones como leídas
     * 
     * @returns Número de notificaciones marcadas
     */
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

    addMember: async (data: { email: string; fullName: string; role: UserRole; specialty?: string; appId?: string | null }): Promise<User> => {
      const response = await apiClient.post<Record<string, unknown>>('/auth/register', {
        email: data.email,
        full_name: data.fullName,
        password: 'TemporaryPassword123!',
        role: data.role,
        specialty: data.specialty
      })
      return mapUserFromApi(response.data)
    },

    updateMember: async (id: string, data: Partial<User>): Promise<User> => {
      const response = await apiClient.put<Record<string, unknown>>(`/users/${id}`, mapUserUpdateToApi(data))
      return mapUserFromApi(response.data)
    },

    deleteMember: async (id: string, hardDelete: boolean = false): Promise<void> => {
      // Enviamos el booleano como query parameter en la URL
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

  // ========================================
  // MÓDULO DE TICKETS DE SOPORTE
  // ========================================
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

    /**
     * Lista tickets de desarrollo existentes para vincularlos a un reporte de bug
     * (el ticket de soporte hereda la épica del ticket seleccionado).
     */
    listLinkableTickets: async (): Promise<Ticket[]> => {
      const response = await apiClient.get<any[]>('/tickets/', { params: { limit: 100 } })
      return Array.isArray(response.data) ? response.data.map(toTicket) : []
    },
  },

  /**
   * ========================================
   * MÓDULO DE INCIDENTES
   * ========================================
   */
  incidents: {
    list: async (filters?: { page?: number, limit?: number, application_id?: string, status?: string }): Promise<PaginatedResponse<Incident>> => {
      const response = await apiClient.get<any>('/incidents/', { params: filters })
      const data = response.data
      
      if (Array.isArray(data)) {
        return {
          items: data.map(toIncident),
          total: data.length,
          page: 1,
          pages: 1
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
      const response = await apiClient.put<any>(`/incidents/${incidentId}`, data)
      return toIncident(response.data)
    },
    
    updateStatus: async (incidentId: string, status: string): Promise<Incident> => {
      const response = await apiClient.patch<any>(`/incidents/${incidentId}/status`, { status })
      return toIncident(response.data)
    }
  },

  /**
   * ========================================
   * MÓDULO DE REUNIONES
   * ========================================
   */
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
      const response = await apiClient.put<any>(`/meetings/${meetingId}`, data)
      return toMeeting(response.data)
    },
    
    setAttendance: async (meetingId: string, data: any[]): Promise<MeetingAttendance[]> => {
      const response = await apiClient.post<any[]>(`/meetings/${meetingId}/attendance`, data)
      return Array.isArray(response.data) ? response.data.map(toMeetingAttendance) : []
    },
    
    updateSummary: async (meetingId: string, summary: string): Promise<Meeting> => {
      const response = await apiClient.patch<any>(`/meetings/${meetingId}`, { summary_markdown: summary })
      return toMeeting(response.data)
    }
  },
}

/**
 * Función auxiliar para actualizar el estado de autenticación
 * Debe llamarse desde el store de Pinia cuando el usuario se autentica o renueva sesión
 *
 * @param tokens - Nuevos tokens de autenticación
 */
export const setAuthTokens = (tokens: AuthTokens): void => {
  authState.accessToken = tokens.accessToken
  authState.refreshToken = tokens.refreshToken
}

/**
 * Función auxiliar para limpiar los tokens
 * Debe llamarse cuando el usuario cierra sesión
 */
export const clearAuthTokens = (): void => {
  authState.accessToken = null
  authState.refreshToken = null
}

/**
 * API Object exportado:
 * Usa realApi (Axios + backend)
 */
export const api = realApi

/**
 * Export default: el objeto api para que pueda importarse como default
 */
export default api

/**
 * Exporta la instancia de Axios por si se necesita usar directamente
 */
export { apiClient }
