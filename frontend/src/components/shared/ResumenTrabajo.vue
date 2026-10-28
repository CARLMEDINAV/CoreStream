<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ConteosTrabajo, ResumenTrabajo } from '@/types'

defineProps<{ resumen: ResumenTrabajo }>()
const { t } = useI18n()
const campos: (keyof ConteosTrabajo)[] = ['active', 'in_progress', 'blocked', 'completed_last_7_days']
</script>

<template>
  <div>
    <dl class="grid grid-cols-2 xl:grid-cols-4 gap-3">
      <div v-for="campo in campos" :key="campo" class="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4">
        <dt class="text-sm text-[var(--text-secondary)]">{{ t('trabajo.' + campo) }}</dt>
        <dd class="mt-2 text-2xl font-bold text-[var(--text-primary)]">{{ resumen.total[campo] }}</dd>
        <dd class="mt-1 text-xs text-[var(--text-muted)]">
          {{ t('trabajo.tickets') }}: {{ resumen.tickets[campo] }} ·
          {{ t('trabajo.incidents') }}: {{ resumen.incidents[campo] }}
        </dd>
      </div>
    </dl>
    <p class="mt-3 text-xs text-[var(--text-muted)]">{{ t('trabajo.reglas') }}</p>
  </div>
</template>
