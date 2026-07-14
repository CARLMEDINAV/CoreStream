/**
 * Configuración de Vue Router para CoreStream
 * 
 * Define todas las rutas de la aplicación y sus componentes asociados.
 * Incluye:
 * - Rutas públicas (login)
 * - Rutas protegidas para administradores
 * - Rutas protegidas para desarrolladores
 * - Guards de navegación para validar autenticación y autorización
 * 
 * Las rutas utilizan layout anidados para mantener consistencia visual
 * en diferentes secciones de la aplicación.
 */
 
import { createRouter, createWebHashHistory, RouteRecordRaw, NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import type { UserRole } from '@/types'

/**
 * ========================================
 * DEFINICIÓN DE RUTAS
 * ========================================
 * 
 * Las rutas están organizadas por áreas funcionales:
 * - / : Raíz (redirige a login o dashboard)
 * - /login : Autenticación (pública)
 * - /admin/* : Panel de administración (requiere rol ADMIN)
 * - /dev/* : Área de desarrollo (requiere rol DEVELOPER o TEAM_LEADER)
 */
const routes: RouteRecordRaw[] = [
  {
    /**
     * Ruta raíz
     * Redirige a login si no está autenticado, o al dashboard si lo está
     */
    path: '/',
    redirect: (to) => {
      /**
       * Si hay token, redirige al dashboard apropiado
       * Si no hay token, redirige a login
       */
      const token = localStorage.getItem('accessToken')
      const userRole = localStorage.getItem('userRole')
      
      // // console.log('ROOT REDIRECT:', { token, userRole })
      
      if (!token) {
        // // console.log('NO TOKEN - Redirecting to /login')
        return { path: '/login' }
      }
      
      const target = userRole === 'ADMIN' ? '/admin' : '/dev'
      // // console.log('HAS TOKEN - Redirecting to', target)
      return { path: target }
    }
  },

  /**
   * ========================================
   * RUTAS PÚBLICAS
   * ========================================
   */
  {
    /**
     * Ruta de login
     * Accesible a usuarios no autenticados
     * Redirige al dashboard si ya está autenticado
     */
    path: '/login',
    name: 'Login',
    /**
     * Carga el componente de login
     * Utiliza lazy loading para optimizar el bundle inicial
     */
    component: () => import('@/views/LoginView.vue'),
    /**
     * Meta información de la ruta
     */
    meta: {
      /**
       * Indica que esta ruta es pública y no requiere autenticación
       */
      requiresAuth: false,
      /**
       * Título de la página
       */
      title: 'Iniciar Sesión - CoreStream'
    }
  },

  /**
   * ========================================
   * RUTAS DE ADMINISTRACIÓN
   * ========================================
   * 
   * Todas las subrutas bajo /admin requieren rol ADMIN
   * Utilizan un layout común para el panel de administración
   */
  {
    /**
     * Layout raíz para todas las rutas de administración
     */
    path: '/admin',
    name: 'AdminLayout',
    /**
     * Componente de layout que proporciona navegación y estructura común
     */
    component: () => import('@/layouts/AdminLayout.vue'),
    /**
     * Guards de navegación específicos para rutas admin
     */
    meta: {
      requiresAuth: true,
      requiredRoles: ['ADMIN'],
      title: 'Administración - CoreStream'
    },
    /**
     * Rutas anidadas dentro del layout de administración
     */
    children: [
      {
        /**
         * Ruta por defecto: /admin
         * Redirige a /admin/builder
         */
        path: '',
        name: 'AdminHome',
        redirect: '/admin/builder'
      },

      {
        /**
         * Vista principal de administración
         * Constructor de aplicaciones y épicas
         */
        path: 'builder',
        name: 'Builder',
        component: () => import('@/views/admin/BuilderView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Constructor - CoreStream Admin'
        }
      },

      {
        /**
         * Vista de analítica para administradores
         * Estadísticas globales del sistema, rendimiento del equipo
         */
        path: 'analytics',
        name: 'AdminAnalytics',
        component: () => import('@/views/admin/AnalyticsView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Analítica - CoreStream Admin'
        }
      },

      {
        /**
         * Vista de documentación de código
         * Gestión de especificaciones, documentos técnicos
         */
        path: 'code-docs',
        name: 'CodeDocs',
        component: () => import('@/views/admin/CodeDocsView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Documentación de Código - CoreStream Admin'
        }
      },

      {
        /**
         * Vista de gestión de equipo
         * Administración de usuarios, roles, permisos
         */
        path: 'team',
        name: 'TeamManagement',
        component: () => import('@/views/admin/TeamView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Gestión de Equipo - CoreStream Admin'
        }
      },

      {
        /**
         * Vista de carga de documentos y código
         * Gestión de archivos para el equipo (código, documentación)
         */
        path: 'uploads',
        name: 'DocumentsUpload',
        component: () => import('@/views/admin/DocumentsUploadView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Carga de Documentos - CoreStream Admin'
        }
      },

      {
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('@/views/shared/SettingsView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Configuración - CoreStream Admin'
        }
      },

      {
        /**
         * Vista de tickets de soporte para Admin
         * Permite gestionar bugs de producción reportados por el equipo
         */
        path: 'support',
        name: 'AdminSupport',
        component: () => import('@/views/dev/SupportView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['ADMIN'],
          title: 'Soporte - CoreStream Admin'
        }
      }
    ]
  },

  /**
   * ========================================
   * RUTAS DE DESARROLLO
   * ========================================
   * 
   * Rutas para desarrolladores y líderes de grupo
   * Incluye área de trabajo personal y herramientas de desarrollo
   */
  {
    /**
     * Layout para todas las rutas de desarrollo
     */
    path: '/dev',
    name: 'DeveloperLayout',
    component: () => import('@/layouts/DeveloperLayout.vue'),
    /**
     * Guards: requiere autenticación y rol DEVELOPER o TEAM_LEADER
     */
    meta: {
      requiresAuth: true,
      requiredRoles: ['DEVELOPER', 'TEAM_LEADER'],
      title: 'Área de Desarrollo - CoreStream'
    },
    /**
     * Rutas anidadas bajo el layout de desarrollo
     */
    children: [
      {
        /**
         * Ruta por defecto: /dev
         * Redirige a /dev/workbench
         */
        path: '',
        name: 'DevHome',
        redirect: '/dev/workbench'
      },

      {
        /**
         * Workbench del desarrollador
         * Vista principal de tareas asignadas y en progreso
         * Proporciona información rápida y fácil acceso a tareas
         */
        path: 'workbench',
        name: 'Workbench',
        component: () => import('@/views/dev/WorkbenchView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['DEVELOPER', 'TEAM_LEADER'],
          title: 'Mi Workbench - CoreStream'
        }
      },

      {
        /**
         * Vista de gestión de cargas/documentos
         * Subir, organizar y descargar archivos de proyecto
         */
        path: 'uploads',
        name: 'Uploads',
        component: () => import('@/views/dev/UploadsView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['DEVELOPER', 'TEAM_LEADER'],
          title: 'Mis Archivos - CoreStream'
        }
      },

      {
        path: 'settings',
        name: 'DevSettings',
        component: () => import('@/views/shared/SettingsView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['DEVELOPER', 'TEAM_LEADER'],
          title: 'Configuración - CoreStream'
        }
      },

      {
        /**
         * Vista de asignación de tareas del equipo
         * Solo disponible para líderes de grupo (TEAM_LEADER)
         * Permite asignar tareas a miembros del equipo
         */
        path: 'team-assignment',
        name: 'TeamAssignment',
        component: () => import('@/views/dev/TeamAssignmentView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['TEAM_LEADER'],
          title: 'Asignación de Equipo - CoreStream'
        }
      },

      {
        /**
         * Vista de tickets de soporte para Developer y Team Leader
         * Permite crear, ver y gestionar bugs de producción
         */
        path: 'support',
        name: 'DevSupport',
        component: () => import('@/views/dev/SupportView.vue'),
        meta: {
          requiresAuth: true,
          requiredRoles: ['DEVELOPER', 'TEAM_LEADER'],
          title: 'Soporte - CoreStream'
        }
      }
    ]
  },

  /**
   * ========================================
   * RUTAS 404
   * ========================================
   */
  {
    /**
     * Ruta catch-all para páginas no encontradas
     * Debe ser la última ruta definida
     */
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: {
      title: 'Página No Encontrada - CoreStream'
    }
  }
]

/**
 * Crea la instancia de Router
 * Configuración:
 * - Modo hash: URLs con # que no requieren configuración de servidor
 * - Base URL: '/' (raíz del dominio)
 */
const router = createRouter({
  /**
   * Modo hash: usa # en las URLs para routing sin requerer servidor especial
   * URLs se ven como /#/admin/builder
   * Esto funciona sin necesidad de reescritura de URL en servidor
   */
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
})

/**
 * ========================================
 * GUARDS DE NAVEGACIÓN
 * ========================================
 * 
 * Los guards se ejecutan antes de navegar a una ruta
 * Se utilizan para:
 * - Validar que el usuario está autenticado
 * - Validar que el usuario tiene los permisos necesarios
 * - Actualizar el título de la página
 * - Redirigir a login si no está autenticado
 */

/**
 * Guard global que se ejecuta antes de cada navegación
 * 
 * El orden es importante:
 * 1. Comprueba si la ruta requiere autenticación
 * 2. Comprueba si el usuario tiene el rol necesario
 * 3. Actualiza el título de la página
 * 4. Permite la navegación o redirige
 */
router.beforeEach(
  /**
   * @param to - Ruta destino hacia la que se intenta navegar
   * @param from - Ruta de origen desde la que se navega
   * @param next - Función para continuar la navegación
   */
  async (
    to: RouteLocationNormalized,
    from: RouteLocationNormalized,
    next: NavigationGuardNext
  ): Promise<void> => {
    /**
     * Valida que un token sea un JWT real
     */
    const isValidJWT = (token: string | null) => {
      if (!token) return false
      const parts = token.split('.')
      return parts.length === 3 && parts.every(part => part.length > 0)
    }

    /**
     * Obtiene el token de autenticación almacenado
     * Normalmente se guardaría en el store de Pinia
     * Aquí se simplifca extrayéndolo del localStorage
     */
    let token = localStorage.getItem('accessToken')
    let userRole = localStorage.getItem('userRole') as UserRole | null

    /**
     * Si hay un token pero NO es un JWT válido, lo limpia
     */
    if (token && !isValidJWT(token)) {
      console.warn('Invalid token detected in guard, clearing')
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userRole')
      localStorage.removeItem('userId')
      token = null
      userRole = null
    }

    /**
     * Meta información de la ruta
     */
    const requiresAuth = to.meta.requiresAuth as boolean | undefined
    const requiredRoles = to.meta.requiredRoles as string[] | undefined

    /**
     * CASO 1: Ruta requiere autenticación pero usuario no tiene token
     * Excepto para la ruta raíz que tiene su propio redirect()
     */
    if (requiresAuth && !token && to.path !== '/') {
      /**
       * Redirige a login y guarda la ruta destino para volver después
       */
      next({
        name: 'Login',
        /**
         * Parámetro query: ruta a la que ir después de autenticarse
         */
        query: { redirect: to.path }
      })
      return
    }

    /**
     * CASO 2: Usuario intenta acceder a login pero ya está autenticado
     */
    /**
     * CASO 3: Ruta requiere un rol específico y usuario no lo tiene
     */
    if (requiredRoles && userRole && !requiredRoles.includes(userRole)) {
      /**
       * Redirige a la página de acceso denegado o al dashboard principal
       */
      next({
        path: userRole === 'ADMIN' ? '/admin/builder' : '/dev/workbench'
      })
      return
    }

    /**
     * CASO 4: Actualiza el título de la página
     * Se toma del meta.title definido en cada ruta
     */
    const title = to.meta.title as string | undefined
    if (title) {
      document.title = title
    }

    /**
     * Continúa con la navegación
     */
    next()
  }
)

/**
 * Hook que se ejecuta después de cada navegación
 * Útil para logging, analytics, etc.
 */
router.afterEach((to: RouteLocationNormalized) => {
  /**
   * Scroll a la parte superior de la página en nuevas rutas
   */
  window.scrollTo(0, 0)

  /**
   * Aquí se podrían enviar eventos de analytics o logging
   * Ejemplo: trackPageView(to.path)
   */
})

/**
 * Exporta la instancia del router
 * Se utiliza en main.ts para instalar en la aplicación
 */
export default router
