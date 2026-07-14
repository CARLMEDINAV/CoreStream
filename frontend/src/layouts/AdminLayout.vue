<!--
  Layout para sección de administración

  Proporciona navegación sidebar y estructura común para todas las vistas admin.
-->
<template>
  <div class="flex h-screen bg-[var(--bg-app)] overflow-hidden">
    <!-- Overlay para móvil -->
    <div v-if="isSidebarOpen" @click="toggleSidebar" class="fixed inset-0 bg-black/50 z-40 md:hidden"></div>

    <!-- Sidebar -->
    <aside :class="[
      'bg-[var(--bg-sidebar)] border-r border-[var(--border-subtle)] z-50 fixed md:relative h-full transition-transform duration-300 w-64',
      isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
    ]">
      <nav class="p-6 space-y-4">
        <h2 class="font-bold text-lg text-[var(--text-primary)] mb-6">
          {{ t('nav.administration') }}
        </h2>

        <router-link
          to="/admin/builder"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
        >
          {{ t('nav.builder') }}
        </router-link>

        <router-link
          to="/admin/analytics"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
        >
          {{ t('nav.analytics') }}
        </router-link>

        <router-link
          to="/admin/code-docs"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
        >
          {{ t('nav.documentation') }}
        </router-link>

        <router-link
          to="/admin/team"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
        >
          {{ t('nav.team') }}
        </router-link>

        <router-link
          to="/admin/support"
          class="block px-4 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-panel)]"
        >
          {{ t('nav.support') }}
        </router-link>

      </nav>
    </aside>

    <!-- Contenido principal -->
    <main class="flex-1 overflow-auto">
      <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-header)_80%,transparent)] backdrop-blur">
        <div class="flex items-center gap-4">
          <button @click="toggleSidebar" class="md:hidden p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-800 text-[var(--text-primary)]">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
          </button>
          <div>
            <p class="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">CoreStream</p>
            <h1 class="text-lg font-semibold text-[var(--text-primary)]">{{ t('nav.adminPanel') }}</h1>
          </div>
        </div>
        <button
          type="button"
          @click="logout"
          class="px-4 py-2 rounded-lg bg-[var(--priority-urg-bg)] text-white hover:opacity-90 transition-colors"
        >
          {{ t('header.logout') }}
        </button>
      </div>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * AdminLayout - Componente de estructura para vistas de administración
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const isSidebarOpen = ref(false)
const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const logout = async () => {
  await authStore.logout()
  await router.push('/login')
}
</script>
