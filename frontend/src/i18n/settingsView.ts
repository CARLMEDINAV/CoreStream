/**
 * Textos de la página de Configuración (SettingsView.vue) en 5 idiomas,
 * igual que el selector de la app. Mismo patrón que securitySettings.ts.
 * Los mensajes de error que devuelve el servidor (detail) llegan en el idioma
 * del backend y no se traducen aquí.
 */

export type SettingsViewKey =
  | 'pageTitle'
  | 'pageSubtitle'
  | 'profileTitle'
  | 'firstName'
  | 'lastName'
  | 'email'
  | 'specialty'
  | 'specialtyPlaceholder'
  | 'saving'
  | 'saveProfile'
  | 'securityTitle'
  | 'currentPassword'
  | 'newPassword'
  | 'confirmPassword'
  | 'pwMismatch'
  | 'pwUpdated'
  | 'updating'
  | 'changePassword'
  | 'prefsTitle'
  | 'darkMode'
  | 'darkModeDesc'
  | 'language'
  | 'languageDesc'
  | 'cancel'
  | 'savePrefs'
  | 'errSave'
  | 'errPassword'

type Messages = Record<SettingsViewKey, string>

const es: Messages = {
  pageTitle: 'Configuración',
  pageSubtitle: 'Gestiona tu perfil, seguridad y preferencias',
  profileTitle: 'Perfil',
  firstName: 'Nombre',
  lastName: 'Apellido',
  email: 'Email',
  specialty: 'Especialidad',
  specialtyPlaceholder: 'Ej: Frontend, Backend, DevOps…',
  saving: 'Guardando…',
  saveProfile: 'Guardar perfil',
  securityTitle: 'Seguridad',
  currentPassword: 'Contraseña Actual',
  newPassword: 'Nueva Contraseña',
  confirmPassword: 'Confirmar Nueva Contraseña',
  pwMismatch: 'Las contraseñas no coinciden',
  pwUpdated: 'Contraseña actualizada',
  updating: 'Actualizando…',
  changePassword: 'Cambiar contraseña',
  prefsTitle: 'Preferencias',
  darkMode: 'Modo oscuro',
  darkModeDesc: 'Cambia entre tema claro y oscuro',
  language: 'Idioma',
  languageDesc: 'Idioma de la interfaz',
  cancel: 'Cancelar',
  savePrefs: 'Guardar preferencias',
  errSave: 'Error al guardar: ',
  errPassword: 'Error al cambiar contraseña',
}

const en: Messages = {
  pageTitle: 'Settings',
  pageSubtitle: 'Manage your profile, security and preferences',
  profileTitle: 'Profile',
  firstName: 'First name',
  lastName: 'Last name',
  email: 'Email',
  specialty: 'Specialty',
  specialtyPlaceholder: 'E.g.: Frontend, Backend, DevOps…',
  saving: 'Saving…',
  saveProfile: 'Save profile',
  securityTitle: 'Security',
  currentPassword: 'Current Password',
  newPassword: 'New Password',
  confirmPassword: 'Confirm New Password',
  pwMismatch: 'Passwords do not match',
  pwUpdated: 'Password updated',
  updating: 'Updating…',
  changePassword: 'Change password',
  prefsTitle: 'Preferences',
  darkMode: 'Dark mode',
  darkModeDesc: 'Switch between light and dark theme',
  language: 'Language',
  languageDesc: 'Interface language',
  cancel: 'Cancel',
  savePrefs: 'Save preferences',
  errSave: 'Error saving: ',
  errPassword: 'Error changing password',
}

const pt: Messages = {
  pageTitle: 'Configurações',
  pageSubtitle: 'Gerencie seu perfil, segurança e preferências',
  profileTitle: 'Perfil',
  firstName: 'Nome',
  lastName: 'Sobrenome',
  email: 'E-mail',
  specialty: 'Especialidade',
  specialtyPlaceholder: 'Ex.: Frontend, Backend, DevOps…',
  saving: 'Salvando…',
  saveProfile: 'Salvar perfil',
  securityTitle: 'Segurança',
  currentPassword: 'Senha Atual',
  newPassword: 'Nova Senha',
  confirmPassword: 'Confirmar Nova Senha',
  pwMismatch: 'As senhas não coincidem',
  pwUpdated: 'Senha atualizada',
  updating: 'Atualizando…',
  changePassword: 'Alterar senha',
  prefsTitle: 'Preferências',
  darkMode: 'Modo escuro',
  darkModeDesc: 'Alterne entre tema claro e escuro',
  language: 'Idioma',
  languageDesc: 'Idioma da interface',
  cancel: 'Cancelar',
  savePrefs: 'Salvar preferências',
  errSave: 'Erro ao salvar: ',
  errPassword: 'Erro ao alterar a senha',
}

const fr: Messages = {
  pageTitle: 'Paramètres',
  pageSubtitle: 'Gérez votre profil, votre sécurité et vos préférences',
  profileTitle: 'Profil',
  firstName: 'Prénom',
  lastName: 'Nom',
  email: 'E-mail',
  specialty: 'Spécialité',
  specialtyPlaceholder: 'Ex. : Frontend, Backend, DevOps…',
  saving: 'Enregistrement…',
  saveProfile: 'Enregistrer le profil',
  securityTitle: 'Sécurité',
  currentPassword: 'Mot de passe actuel',
  newPassword: 'Nouveau mot de passe',
  confirmPassword: 'Confirmer le nouveau mot de passe',
  pwMismatch: 'Les mots de passe ne correspondent pas',
  pwUpdated: 'Mot de passe mis à jour',
  updating: 'Mise à jour…',
  changePassword: 'Changer le mot de passe',
  prefsTitle: 'Préférences',
  darkMode: 'Mode sombre',
  darkModeDesc: 'Basculez entre le thème clair et le thème sombre',
  language: 'Langue',
  languageDesc: "Langue de l'interface",
  cancel: 'Annuler',
  savePrefs: 'Enregistrer les préférences',
  errSave: "Erreur lors de l'enregistrement : ",
  errPassword: 'Erreur lors du changement de mot de passe',
}

const de: Messages = {
  pageTitle: 'Einstellungen',
  pageSubtitle: 'Verwalte dein Profil, deine Sicherheit und deine Präferenzen',
  profileTitle: 'Profil',
  firstName: 'Vorname',
  lastName: 'Nachname',
  email: 'E-Mail',
  specialty: 'Fachgebiet',
  specialtyPlaceholder: 'z. B. Frontend, Backend, DevOps…',
  saving: 'Wird gespeichert…',
  saveProfile: 'Profil speichern',
  securityTitle: 'Sicherheit',
  currentPassword: 'Aktuelles Passwort',
  newPassword: 'Neues Passwort',
  confirmPassword: 'Neues Passwort bestätigen',
  pwMismatch: 'Die Passwörter stimmen nicht überein',
  pwUpdated: 'Passwort aktualisiert',
  updating: 'Wird aktualisiert…',
  changePassword: 'Passwort ändern',
  prefsTitle: 'Präferenzen',
  darkMode: 'Dunkelmodus',
  darkModeDesc: 'Zwischen hellem und dunklem Design wechseln',
  language: 'Sprache',
  languageDesc: 'Sprache der Oberfläche',
  cancel: 'Abbrechen',
  savePrefs: 'Präferenzen speichern',
  errSave: 'Fehler beim Speichern: ',
  errPassword: 'Fehler beim Ändern des Passworts',
}

export const settingsViewMessages: Record<string, Messages> = { es, en, pt, fr, de }
