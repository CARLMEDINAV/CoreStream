const es = {
  entry: 'Administración de plataforma',
  title: 'Planes y funciones', back: 'Volver', client: 'Cliente', plan: 'Plan',
  inherit: 'Según plan', enabled: 'Activada', disabled: 'Desactivada', save: 'Guardar',
  saved: 'Cambios guardados', error: 'No se pudo completar la operación', loading: 'Cargando…',
  usage: 'Peticiones premium exitosas', since: 'Desde', days: 'Días', refresh: 'Consultar',
  changes: 'Últimos 50 cambios', previous: 'Anterior', next: 'Siguiente', empty: 'Sin registros',
  inactive: 'Cliente inactivo', effective: 'Acceso efectivo', before: 'Antes', after: 'Después',
  note: 'Conteo desde la implementación, limitado por la retención de auditoría. No es facturación.',
}
type Textos = typeof es
const en: Textos = {
  entry: 'Platform administration',
  title: 'Plans and features', back: 'Back', client: 'Client', plan: 'Plan',
  inherit: 'Plan default', enabled: 'Enabled', disabled: 'Disabled', save: 'Save',
  saved: 'Changes saved', error: 'Could not complete the operation', loading: 'Loading…',
  usage: 'Successful premium requests', since: 'Since', days: 'Days', refresh: 'Refresh',
  changes: 'Last 50 changes', previous: 'Previous', next: 'Next', empty: 'No records',
  inactive: 'Inactive client', effective: 'Effective access', before: 'Before', after: 'After',
  note: 'Counted since implementation, limited by audit retention. Not billing.',
}
const pt: Textos = {
  entry: 'Administração da plataforma',
  title: 'Planos e funções', back: 'Voltar', client: 'Cliente', plan: 'Plano',
  inherit: 'Conforme plano', enabled: 'Ativada', disabled: 'Desativada', save: 'Salvar',
  saved: 'Alterações salvas', error: 'Não foi possível concluir a operação', loading: 'Carregando…',
  usage: 'Solicitações premium bem-sucedidas', since: 'Desde', days: 'Dias', refresh: 'Consultar',
  changes: 'Últimas 50 alterações', previous: 'Anterior', next: 'Seguinte', empty: 'Sem registros',
  inactive: 'Cliente inativo', effective: 'Acesso efetivo', before: 'Antes', after: 'Depois',
  note: 'Contagem desde a implementação, limitada pela retenção de auditoria. Não é faturamento.',
}
const fr: Textos = {
  entry: 'Administration de la plateforme',
  title: 'Offres et fonctions', back: 'Retour', client: 'Client', plan: 'Offre',
  inherit: 'Selon l’offre', enabled: 'Activée', disabled: 'Désactivée', save: 'Enregistrer',
  saved: 'Modifications enregistrées', error: 'Impossible de terminer l’opération', loading: 'Chargement…',
  usage: 'Requêtes premium réussies', since: 'Depuis', days: 'Jours', refresh: 'Actualiser',
  changes: '50 dernières modifications', previous: 'Précédent', next: 'Suivant', empty: 'Aucun résultat',
  inactive: 'Client inactif', effective: 'Accès effectif', before: 'Avant', after: 'Après',
  note: 'Comptage depuis l’implémentation, limité par la rétention d’audit. Ce n’est pas de la facturation.',
}
const de: Textos = {
  entry: 'Plattformverwaltung',
  title: 'Tarife und Funktionen', back: 'Zurück', client: 'Kunde', plan: 'Tarif',
  inherit: 'Laut Tarif', enabled: 'Aktiviert', disabled: 'Deaktiviert', save: 'Speichern',
  saved: 'Änderungen gespeichert', error: 'Vorgang konnte nicht abgeschlossen werden', loading: 'Laden…',
  usage: 'Erfolgreiche Premium-Anfragen', since: 'Seit', days: 'Tage', refresh: 'Aktualisieren',
  changes: 'Letzte 50 Änderungen', previous: 'Zurück', next: 'Weiter', empty: 'Keine Einträge',
  inactive: 'Inaktiver Kunde', effective: 'Effektiver Zugriff', before: 'Vorher', after: 'Nachher',
  note: 'Zählung seit Implementierung, begrenzt durch Audit-Aufbewahrung. Keine Abrechnung.',
}
export const platformMessages: Record<string, Textos> = { es, en, pt, fr, de }
