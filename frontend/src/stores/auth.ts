/**
 * Store de Autenticación - CoreStream
 * Gestiona la sesión JWT, usuario actual y permisos RBAC
 * 
 * Responsabilidades:
 * - Autenticación (login, logout, registro)
 * - Gestión de tokens (almacenamiento, refresco)
 * - Control de acceso basado en roles
 * - Persistencia de sesión en localStorage
 */
 
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { UserRole, type User, type AuthTokens } from '@/types'
import { api, setAuthTokens, clearAuthTokens } from '@/services/api'
import { useThemeStore } from '@/stores/theme'

export const useAuthStore = defineStore('auth', () => {
  // ========== ESTADO REACTIVO ==========
  
  /**
   * Usuario actualmente autenticado
   * null si no hay sesión activa
   */
  const user = ref<User | null>(null)

  /**
   * Tokens de autenticación (access y refresh)
   * Se persiste en localStorage para mantener sesión
   */
  const tokens = ref<AuthTokens | null>(null)

  /**
   * Indica si el usuario está autenticado
   * Derivado del estado de tokens y usuario
   */
  const isAuthenticated = ref(false)

  /**
   * Flag de carga durante operaciones async
   * Previene múltiples llamadas simultáneas
   */
  const isLoading = ref(false)

  /**
   * Mensaje de error de la última operación fallida
   */
  const error = ref<string | null>(null)

  // ========== GETTERS COMPUTADOS ==========

  /**
   * Comprueba si el usuario tiene rol de administrador
   */
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  /**
   * Comprueba si el usuario tiene rol de desarrollador
   */
  const isDeveloper = computed(() => user.value?.role === 'DEVELOPER')

  /**
   * Comprueba si el usuario tiene rol de líder de equipo
   */
  const isTeamLeader = computed(() => user.value?.role === 'TEAM_LEADER')

  /**
   * Retorna el rol actual del usuario
   */
  const userRole = computed((): UserRole | undefined => user.value?.role)

  /**
   * Retorna el nombre completo del usuario autenticado
   */
  const fullName = computed(() => user.value?.fullName ?? '')

  /**
   * Retorna el email del usuario autenticado
   */
  const userEmail = computed(() => user.value?.email ?? '')

  /**
   * Comprueba si el access token está próximo a expirar (menos de 5 minutos)
   */
  const isTokenExpiringSoon = computed(() => {
    // expiresIn is a duration in seconds, not a timestamp — we don't have issuedAt
    // so we can't compute absolute expiry here. The Axios 401 interceptor handles
    // reactive refresh; this proactive check is left as a safe no-op.
    return false
  })

  // ========== ACCIONES ==========

  /**
   * Inicializa el store desde localStorage.
   * Restaura tokens, configura el cliente HTTP y carga el perfil del usuario.
   * Lanza error si la sesión no puede restaurarse (el caller debe redirigir a login).
   */
  const initialize = async (): Promise<void> => {
    try {
      // Intentar authTokens (objeto JSON guardado en login)
      let parsed: AuthTokens | null = null
      const storedAuthTokens = localStorage.getItem('authTokens')
      if (storedAuthTokens) {
        try { parsed = JSON.parse(storedAuthTokens) } catch { /* ignorar JSON inválido */ }
      }
      // Fallback: claves individuales (compatibilidad hacia atrás)
      if (!parsed?.accessToken) {
        const accessToken = localStorage.getItem('accessToken')
        const refreshToken = localStorage.getItem('refreshToken')
        if (accessToken && refreshToken) {
          parsed = { accessToken, refreshToken, tokenType: 'Bearer' }
        }
      }

      if (!parsed?.accessToken) return  // Sin tokens almacenados, nada que restaurar

      // Validar formato JWT básico (3 segmentos separados por punto)
      if (parsed.accessToken.split('.').length !== 3) {
        clearSession()
        return
      }

      tokens.value = parsed
      setAuthTokens(parsed)       // Configura headers en el cliente HTTP
      isAuthenticated.value = true
      await fetchMe()             // Carga user.value desde el backend
    } catch (err) {
      console.error('Error al inicializar autenticación desde localStorage:', err)
      clearSession()
      throw err  // El caller (App.vue) redirige a login
    }
  }

  /**
   * Autentica al usuario con email y contraseña
   * 
   * @param email - Email del usuario
   * @param password - Contraseña en texto plano
   * @returns Promise<User> - Datos del usuario autenticado
   * 
   * Flujo:
   * 1. Llama a api.auth.login(email, password)
   * 2. Almacena tokens en localStorage
   * 3. Marca isAuthenticated = true
   * 4. Obtiene datos completos del usuario con fetchMe()
   */
  const login = async (email: string, password: string): Promise<User> => {
    isLoading.value = true
    error.value = null

    try {
      const response = await api.auth.login({ email, password })

      tokens.value = response.tokens
      setAuthTokens(response.tokens)
      localStorage.setItem('authTokens', JSON.stringify(response.tokens))
      localStorage.setItem('accessToken', response.tokens.accessToken)
      localStorage.setItem('refreshToken', response.tokens.refreshToken)

      isAuthenticated.value = true
      console.log('Auth.login: isAuthenticated set to true')

      await fetchMe()
      if (user.value) {
        localStorage.setItem('userRole', user.value.role)
        localStorage.setItem('userId', user.value.id)
        localStorage.setItem('userName', user.value.fullName)
      }

      return user.value!
    } catch (err) {
      const message = (err as any)?.response?.data?.detail
        || (err as any)?.response?.data?.message
        || (err instanceof Error ? err.message : 'Error al iniciar sesión')
      console.error('Auth.login: Error en login:', err)
      clearSession()
      error.value = message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Registra un nuevo usuario en el sistema
   * 
   * @param data - Datos de registro {email, password, fullName, departament?}
   * @returns Promise<User> - Usuario creado
   * 
   * Nota: Generalmente no autentica automáticamente, requiere login posterior
   */
  const register = async (data: {
    email: string
    password: string
    fullName: string
    department?: string
  }): Promise<User> => {
    isLoading.value = true
    error.value = null

    try {
      const created = await api.auth.register({
        email: data.email,
        password: data.password,
        fullName: data.fullName,
        role: UserRole.DEVELOPER,
      })
      return created
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al registrarse'
      error.value = message
      console.error('Error en register:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Obtiene los datos actuales del usuario autenticado
   * Se ejecuta después del login para obtener información completa
   * 
   * @returns Promise<User>
   */
  const fetchMe = async (): Promise<User> => {
    try {
      console.log('fetchMe: Calling api.auth.getMe()...')
      const userData = await api.auth.getMe()
      console.log('fetchMe: User data received:', userData)

      user.value = userData
      localStorage.setItem('userRole', userData.role)
      localStorage.setItem('userId', userData.id)
      localStorage.setItem('userName', userData.fullName)

      // Restaurar tema guardado en el servidor
      const savedTheme = userData.preferences?.theme
      if (savedTheme === 'light' || savedTheme === 'dark') {
        useThemeStore().applyTheme(savedTheme)
      }

      return userData
    } catch (err) {
      console.error('fetchMe: Error al obtener datos del usuario:', err)
      clearSession()
      throw err
    }
  }

  /**
   * Refresca el access token usando el refresh token
   * Se debe ejecutar automáticamente cuando el token está próximo a expirar
   * 
   * @returns Promise<AuthTokens> - Nuevos tokens
   */
  const refreshToken = async (): Promise<AuthTokens> => {
    if (!tokens.value?.refreshToken) {
      throw new Error('No hay refresh token disponible')
    }

    try {
      const response = await api.auth.refresh(tokens.value.refreshToken)
      const newTokens = ((response as any).data || response) as AuthTokens
      tokens.value = newTokens
      setAuthTokens(newTokens)
      localStorage.setItem('authTokens', JSON.stringify(newTokens))
      localStorage.setItem('accessToken', newTokens.accessToken)
      localStorage.setItem('refreshToken', newTokens.refreshToken)
      return newTokens
    } catch (err) {
      console.error('Error al refrescar token:', err)
      clearSession()
      throw err
    }
  }

  /**
   * Actualiza el perfil del usuario autenticado
   * 
   * @param data - Datos a actualizar {fullName?, email?, phone?, avatar?}
   * @returns Promise<User> - Usuario actualizado
   */
  const updateProfile = async (data: Partial<User>): Promise<User> => {
    isLoading.value = true
    error.value = null

    try {
      const updated = await api.auth.updateProfile(data)
      user.value = updated
      return updated
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al actualizar perfil'
      error.value = message
      console.error('Error en updateProfile:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Cambia la contraseña del usuario autenticado
   * 
   * @param oldPassword - Contraseña actual
   * @param newPassword - Nueva contraseña
   * @returns Promise<void>
   */
  const changePassword = async (oldPassword: string, newPassword: string): Promise<void> => {
    isLoading.value = true
    error.value = null

    try {
      await api.auth.changePassword({ oldPassword, newPassword })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al cambiar contraseña'
      error.value = message
      console.error('Error en changePassword:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Cierra la sesión del usuario
   * 
   * Flujo:
   * 1. Llama a api.auth.logout para invalidar sesión en servidor
   * 2. Limpia todos los datos locales
   * 3. Elimina tokens de localStorage
   * 4. Redirige a página de login (manejado por router)
   */
  const logout = async (): Promise<void> => {
    try {
      // Intentar notificar al servidor
      await api.auth.logout()
    } catch (err) {
      console.error('Error al notificar logout al servidor:', err)
      // Continuar con limpieza local incluso si falla
    } finally {
      clearSession()
    }
  }

  /**
   * Limpia toda la información de sesión
   * Función auxiliar llamada por logout e initialize en caso de error
   */
  const clearSession = (): void => {
    user.value = null
    tokens.value = null
    isAuthenticated.value = false
    error.value = null
    clearAuthTokens()
    localStorage.removeItem('authTokens')
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('userRole')
    localStorage.removeItem('userId')
    localStorage.removeItem('userName')
  }

  /**
   * Solicita reset de contraseña por email
   * 
   * @param email - Email del usuario
   * @returns Promise<void>
   */
  const requestPasswordReset = async (email: string): Promise<void> => {
    isLoading.value = true
    error.value = null

    try {
      await api.auth.requestPasswordReset({ email })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al solicitar reset de contraseña'
      error.value = message
      console.error('Error en requestPasswordReset:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Confirma el reset de contraseña con token
   * 
   * @param token - Token recibido en email
   * @param newPassword - Nueva contraseña
   * @returns Promise<void>
   */
  const confirmPasswordReset = async (token: string, newPassword: string): Promise<void> => {
    isLoading.value = true
    error.value = null

    try {
      await api.auth.confirmPasswordReset({ token, newPassword })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al confirmar reset de contraseña'
      error.value = message
      console.error('Error en confirmPasswordReset:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    // Estado
    user,
    tokens,
    isAuthenticated,
    isLoading,
    error,
    // Getters
    isAdmin,
    isDeveloper,
    isTeamLeader,
    userRole,
    fullName,
    userEmail,
    isTokenExpiringSoon,
    // Acciones
    initialize,
    login,
    register,
    fetchMe,
    refreshToken,
    updateProfile,
    changePassword,
    logout,
    clearSession,
    requestPasswordReset,
    confirmPasswordReset,
  }
})
