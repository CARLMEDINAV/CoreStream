/**
 * Textos del panel de seguridad (2FA personal + política de la organización).
 * Cinco idiomas (es, en, pt, fr, de), igual que el selector de la app.
 */

export type SecurityKey =
  | 'title'
  | 'desc'
  | 'statusOn'
  | 'statusOff'
  | 'codesLeft'
  | 'codesLow'
  | 'orgRequires'
  | 'activate'
  | 'disable'
  | 'regenerate'
  | 'scanHint'
  | 'cantScan'
  | 'loadingQr'
  | 'codeLabel'
  | 'confirm'
  | 'cancel'
  | 'working'
  | 'codesTitle'
  | 'codesHint'
  | 'copy'
  | 'copied'
  | 'download'
  | 'savedCheck'
  | 'done'
  | 'disableTitle'
  | 'regenerateTitle'
  | 'disableHint'
  | 'regenerateHint'
  | 'passwordLabel'
  | 'appCodeLabel'
  | 'noticeEnabled'
  | 'noticeDisabled'
  | 'noticeCodes'
  | 'loadError'
  | 'retry'
  | 'loading'
  | 'policyTitle'
  | 'policyDesc'
  | 'policyLabel'
  | 'policyNeedOwn'
  | 'policyWarn'
  | 'policyConfirmQ'
  | 'adminManaged'
  | 'policyOnNotice'
  | 'policyOffNotice'
  | 'tooMany'
  | 'genericError'

type Messages = Record<SecurityKey, string>

const es: Messages = {
  title: 'Verificación en dos pasos',
  desc: 'Protege tu cuenta con un código temporal de tu app autenticadora, además de tu contraseña.',
  statusOn: 'Activada',
  statusOff: 'Desactivada',
  codesLeft: 'Códigos de recuperación restantes',
  codesLow: 'Te quedan pocos códigos de recuperación. Genera un lote nuevo.',
  orgRequires: 'Tu organización exige la verificación en dos pasos, por lo que no se puede desactivar.',
  activate: 'Activar',
  disable: 'Desactivar',
  regenerate: 'Regenerar códigos',
  scanHint:
    'Escanea el código QR con tu app autenticadora (Google Authenticator, Microsoft Authenticator, Authy...) e ingresa el código que muestra.',
  cantScan: '¿No puedes escanear? Ingresa esta clave manualmente:',
  loadingQr: 'Generando código QR...',
  codeLabel: 'Código de 6 dígitos',
  confirm: 'Confirmar',
  cancel: 'Cancelar',
  working: 'Procesando...',
  codesTitle: 'Guarda tus códigos de recuperación',
  codesHint: 'Cada código sirve una sola vez si pierdes acceso a tu app. No volverás a verlos.',
  copy: 'Copiar',
  copied: '¡Copiado!',
  download: 'Descargar',
  savedCheck: 'He guardado mis códigos en un lugar seguro',
  done: 'Listo',
  disableTitle: 'Desactivar la verificación en dos pasos',
  regenerateTitle: 'Regenerar códigos de recuperación',
  disableHint: 'Confirma tu contraseña y un código de tu app para desactivarla.',
  regenerateHint: 'Confirma tu contraseña y un código de tu app. Se generará un lote nuevo.',
  passwordLabel: 'Contraseña actual',
  appCodeLabel: 'Código de tu app',
  noticeEnabled: 'Verificación en dos pasos activada.',
  noticeDisabled: 'Verificación en dos pasos desactivada.',
  noticeCodes: 'Códigos de recuperación actualizados.',
  loadError: 'No se pudo cargar el estado de seguridad.',
  retry: 'Reintentar',
  loading: 'Cargando...',
  policyTitle: 'Política de la organización',
  policyDesc: 'Exige a todos los usuarios de tu organización usar la verificación en dos pasos.',
  policyLabel: 'Exigir verificación en dos pasos a todos',
  policyNeedOwn: 'Para exigirla, primero activa tu propia verificación en dos pasos.',
  policyWarn:
    'Quienes no la tengan deberán configurarla en su próximo inicio de sesión. Las sesiones ya abiertas se mantienen hasta que caduquen.',
  policyConfirmQ: '¿Exigir la verificación en dos pasos a todos los usuarios?',
  adminManaged: 'Tu administrador controla la activación de la verificación en dos pasos.',
  policyOnNotice: 'La verificación en dos pasos ahora es obligatoria.',
  policyOffNotice: 'La verificación en dos pasos ya no es obligatoria.',
  tooMany: 'Demasiados intentos. Espera unos minutos antes de volver a intentarlo.',
  genericError: 'Ocurrió un error. Inténtalo de nuevo.',
}

const en: Messages = {
  title: 'Two-step verification',
  desc: 'Protect your account with a temporary code from your authenticator app, in addition to your password.',
  statusOn: 'Enabled',
  statusOff: 'Disabled',
  codesLeft: 'Recovery codes remaining',
  codesLow: 'You are running low on recovery codes. Generate a new set.',
  orgRequires: 'Your organization requires two-step verification, so it cannot be disabled.',
  activate: 'Enable',
  disable: 'Disable',
  regenerate: 'Regenerate codes',
  scanHint:
    'Scan the QR code with your authenticator app (Google Authenticator, Microsoft Authenticator, Authy...) and enter the code it shows.',
  cantScan: "Can't scan? Enter this key manually:",
  loadingQr: 'Generating QR code...',
  codeLabel: '6-digit code',
  confirm: 'Confirm',
  cancel: 'Cancel',
  working: 'Working...',
  codesTitle: 'Save your recovery codes',
  codesHint: 'Each code works only once if you lose access to your app. You will not see them again.',
  copy: 'Copy',
  copied: 'Copied!',
  download: 'Download',
  savedCheck: "I've saved my codes in a safe place",
  done: 'Done',
  disableTitle: 'Disable two-step verification',
  regenerateTitle: 'Regenerate recovery codes',
  disableHint: 'Confirm your password and a code from your app to disable it.',
  regenerateHint: 'Confirm your password and a code from your app. A new set will be generated.',
  passwordLabel: 'Current password',
  appCodeLabel: 'Code from your app',
  noticeEnabled: 'Two-step verification enabled.',
  noticeDisabled: 'Two-step verification disabled.',
  noticeCodes: 'Recovery codes updated.',
  loadError: 'Could not load the security status.',
  retry: 'Retry',
  loading: 'Loading...',
  policyTitle: 'Organization policy',
  policyDesc: 'Require every user in your organization to use two-step verification.',
  policyLabel: 'Require two-step verification for everyone',
  policyNeedOwn: 'To require it, first enable your own two-step verification.',
  policyWarn:
    'Users without it will have to set it up at their next sign-in. Sessions that are already open stay valid until they expire.',
  policyConfirmQ: 'Require two-step verification for all users?',
  adminManaged: 'Your administrator controls whether two-step verification is enabled.',
  policyOnNotice: 'Two-step verification is now required.',
  policyOffNotice: 'Two-step verification is no longer required.',
  tooMany: 'Too many attempts. Wait a few minutes before trying again.',
  genericError: 'Something went wrong. Please try again.',
}

const pt: Messages = {
  title: 'Verificação em duas etapas',
  desc: 'Proteja sua conta com um código temporário do seu app autenticador, além da sua senha.',
  statusOn: 'Ativada',
  statusOff: 'Desativada',
  codesLeft: 'Códigos de recuperação restantes',
  codesLow: 'Restam poucos códigos de recuperação. Gere um novo conjunto.',
  orgRequires: 'Sua organização exige a verificação em duas etapas, por isso ela não pode ser desativada.',
  activate: 'Ativar',
  disable: 'Desativar',
  regenerate: 'Regenerar códigos',
  scanHint:
    'Escaneie o código QR com seu app autenticador (Google Authenticator, Microsoft Authenticator, Authy...) e digite o código exibido.',
  cantScan: 'Não consegue escanear? Digite esta chave manualmente:',
  loadingQr: 'Gerando código QR...',
  codeLabel: 'Código de 6 dígitos',
  confirm: 'Confirmar',
  cancel: 'Cancelar',
  working: 'Processando...',
  codesTitle: 'Guarde seus códigos de recuperação',
  codesHint: 'Cada código só funciona uma vez, caso você perca o acesso ao seu app. Você não os verá novamente.',
  copy: 'Copiar',
  copied: 'Copiado!',
  download: 'Baixar',
  savedCheck: 'Guardei meus códigos em um lugar seguro',
  done: 'Concluir',
  disableTitle: 'Desativar a verificação em duas etapas',
  regenerateTitle: 'Regenerar códigos de recuperação',
  disableHint: 'Confirme sua senha e um código do seu app para desativá-la.',
  regenerateHint: 'Confirme sua senha e um código do seu app. Um novo conjunto será gerado.',
  passwordLabel: 'Senha atual',
  appCodeLabel: 'Código do seu app',
  noticeEnabled: 'Verificação em duas etapas ativada.',
  noticeDisabled: 'Verificação em duas etapas desativada.',
  noticeCodes: 'Códigos de recuperação atualizados.',
  loadError: 'Não foi possível carregar o estado de segurança.',
  retry: 'Tentar novamente',
  loading: 'Carregando...',
  policyTitle: 'Política da organização',
  policyDesc: 'Exija que todos os usuários da sua organização usem a verificação em duas etapas.',
  policyLabel: 'Exigir verificação em duas etapas de todos',
  policyNeedOwn: 'Para exigi-la, primeiro ative a sua própria verificação em duas etapas.',
  policyWarn:
    'Quem não a tiver deverá configurá-la no próximo login. As sessões já abertas continuam válidas até expirarem.',
  policyConfirmQ: 'Exigir a verificação em duas etapas de todos os usuários?',
  adminManaged: 'Seu administrador controla a ativação da verificação em duas etapas.',
  policyOnNotice: 'A verificação em duas etapas agora é obrigatória.',
  policyOffNotice: 'A verificação em duas etapas não é mais obrigatória.',
  tooMany: 'Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.',
  genericError: 'Ocorreu um erro. Tente novamente.',
}

const fr: Messages = {
  title: 'Vérification en deux étapes',
  desc: "Protégez votre compte avec un code temporaire de votre application d'authentification, en plus de votre mot de passe.",
  statusOn: 'Activée',
  statusOff: 'Désactivée',
  codesLeft: 'Codes de récupération restants',
  codesLow: 'Il vous reste peu de codes de récupération. Générez un nouveau lot.',
  orgRequires: "Votre organisation exige la vérification en deux étapes, elle ne peut donc pas être désactivée.",
  activate: 'Activer',
  disable: 'Désactiver',
  regenerate: 'Régénérer les codes',
  scanHint:
    "Scannez le code QR avec votre application d'authentification (Google Authenticator, Microsoft Authenticator, Authy...) et saisissez le code affiché.",
  cantScan: 'Impossible de scanner ? Saisissez cette clé manuellement :',
  loadingQr: 'Génération du code QR...',
  codeLabel: 'Code à 6 chiffres',
  confirm: 'Confirmer',
  cancel: 'Annuler',
  working: 'Traitement...',
  codesTitle: 'Conservez vos codes de récupération',
  codesHint:
    "Chaque code n'est valable qu'une seule fois si vous perdez l'accès à votre application. Vous ne les reverrez plus.",
  copy: 'Copier',
  copied: 'Copié !',
  download: 'Télécharger',
  savedCheck: "J'ai conservé mes codes en lieu sûr",
  done: 'Terminé',
  disableTitle: 'Désactiver la vérification en deux étapes',
  regenerateTitle: 'Régénérer les codes de récupération',
  disableHint: "Confirmez votre mot de passe et un code de votre application pour la désactiver.",
  regenerateHint: 'Confirmez votre mot de passe et un code de votre application. Un nouveau lot sera généré.',
  passwordLabel: 'Mot de passe actuel',
  appCodeLabel: "Code de votre application",
  noticeEnabled: 'Vérification en deux étapes activée.',
  noticeDisabled: 'Vérification en deux étapes désactivée.',
  noticeCodes: 'Codes de récupération mis à jour.',
  loadError: "Impossible de charger l'état de sécurité.",
  retry: 'Réessayer',
  loading: 'Chargement...',
  policyTitle: "Politique de l'organisation",
  policyDesc: "Exigez que tous les utilisateurs de votre organisation utilisent la vérification en deux étapes.",
  policyLabel: 'Exiger la vérification en deux étapes pour tous',
  policyNeedOwn: "Pour l'exiger, activez d'abord votre propre vérification en deux étapes.",
  policyWarn:
    "Ceux qui ne l'ont pas devront la configurer à leur prochaine connexion. Les sessions déjà ouvertes restent valides jusqu'à leur expiration.",
  policyConfirmQ: 'Exiger la vérification en deux étapes pour tous les utilisateurs ?',
  adminManaged: "Votre administrateur contrôle l'activation de la vérification en deux étapes.",
  policyOnNotice: 'La vérification en deux étapes est désormais obligatoire.',
  policyOffNotice: "La vérification en deux étapes n'est plus obligatoire.",
  tooMany: 'Trop de tentatives. Attendez quelques minutes avant de réessayer.',
  genericError: 'Une erreur est survenue. Veuillez réessayer.',
}

const de: Messages = {
  title: 'Bestätigung in zwei Schritten',
  desc: 'Schütze dein Konto zusätzlich zum Passwort mit einem temporären Code aus deiner Authenticator-App.',
  statusOn: 'Aktiviert',
  statusOff: 'Deaktiviert',
  codesLeft: 'Verbleibende Wiederherstellungscodes',
  codesLow: 'Du hast nur noch wenige Wiederherstellungscodes. Erstelle einen neuen Satz.',
  orgRequires: 'Deine Organisation verlangt die Bestätigung in zwei Schritten, daher kann sie nicht deaktiviert werden.',
  activate: 'Aktivieren',
  disable: 'Deaktivieren',
  regenerate: 'Codes neu erstellen',
  scanHint:
    'Scanne den QR-Code mit deiner Authenticator-App (Google Authenticator, Microsoft Authenticator, Authy...) und gib den angezeigten Code ein.',
  cantScan: 'Scannen nicht möglich? Gib diesen Schlüssel manuell ein:',
  loadingQr: 'QR-Code wird erstellt...',
  codeLabel: '6-stelliger Code',
  confirm: 'Bestätigen',
  cancel: 'Abbrechen',
  working: 'Wird verarbeitet...',
  codesTitle: 'Speichere deine Wiederherstellungscodes',
  codesHint: 'Jeder Code funktioniert nur einmal, falls du den Zugriff auf deine App verlierst. Du siehst sie nicht erneut.',
  copy: 'Kopieren',
  copied: 'Kopiert!',
  download: 'Herunterladen',
  savedCheck: 'Ich habe meine Codes sicher gespeichert',
  done: 'Fertig',
  disableTitle: 'Bestätigung in zwei Schritten deaktivieren',
  regenerateTitle: 'Wiederherstellungscodes neu erstellen',
  disableHint: 'Bestätige dein Passwort und einen Code aus deiner App, um sie zu deaktivieren.',
  regenerateHint: 'Bestätige dein Passwort und einen Code aus deiner App. Ein neuer Satz wird erstellt.',
  passwordLabel: 'Aktuelles Passwort',
  appCodeLabel: 'Code aus deiner App',
  noticeEnabled: 'Bestätigung in zwei Schritten aktiviert.',
  noticeDisabled: 'Bestätigung in zwei Schritten deaktiviert.',
  noticeCodes: 'Wiederherstellungscodes aktualisiert.',
  loadError: 'Der Sicherheitsstatus konnte nicht geladen werden.',
  retry: 'Erneut versuchen',
  loading: 'Wird geladen...',
  policyTitle: 'Richtlinie der Organisation',
  policyDesc: 'Verlange von allen Nutzern deiner Organisation die Bestätigung in zwei Schritten.',
  policyLabel: 'Bestätigung in zwei Schritten für alle verlangen',
  policyNeedOwn: 'Um sie zu verlangen, aktiviere zuerst deine eigene Bestätigung in zwei Schritten.',
  policyWarn:
    'Wer sie nicht hat, muss sie bei der nächsten Anmeldung einrichten. Bereits geöffnete Sitzungen bleiben bis zum Ablauf gültig.',
  policyConfirmQ: 'Bestätigung in zwei Schritten für alle Nutzer verlangen?',
  adminManaged: 'Dein Administrator steuert, ob die Bestätigung in zwei Schritten aktiviert ist.',
  policyOnNotice: 'Die Bestätigung in zwei Schritten ist jetzt verpflichtend.',
  policyOffNotice: 'Die Bestätigung in zwei Schritten ist nicht mehr verpflichtend.',
  tooMany: 'Zu viele Versuche. Warte einige Minuten, bevor du es erneut versuchst.',
  genericError: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
}

export const securityMessages: Record<string, Messages> = { es, en, pt, fr, de }
