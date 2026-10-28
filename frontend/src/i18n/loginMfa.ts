/**
 * Textos del flujo 2FA de la pantalla de login (NEW-08).
 * Se mantienen fuera de los archivos de traducción principales para no
 * tocarlos; LoginView.vue elige el idioma según i18n.locale.
 */

export type LoginMfaKey =
  | 'verifyTitle'
  | 'verifyHint'
  | 'recoveryHint'
  | 'codeLabel'
  | 'recoveryLabel'
  | 'verifySubmit'
  | 'verifying'
  | 'useRecovery'
  | 'useTotp'
  | 'back'
  | 'setupTitle'
  | 'setupHint'
  | 'cantScan'
  | 'loadingQr'
  | 'confirmLabel'
  | 'confirmSubmit'
  | 'codesTitle'
  | 'codesHint'
  | 'copy'
  | 'copied'
  | 'download'
  | 'savedCheck'
  | 'continue'
  | 'finishError'

type Messages = Record<LoginMfaKey, string>

const es: Messages = {
  verifyTitle: 'Verificación en dos pasos',
  verifyHint: 'Ingresa el código de 6 dígitos de tu app autenticadora.',
  recoveryHint: 'Ingresa uno de tus códigos de recuperación.',
  codeLabel: 'Código',
  recoveryLabel: 'Código de recuperación',
  verifySubmit: 'Verificar',
  verifying: 'Verificando...',
  useRecovery: 'Usar un código de recuperación',
  useTotp: 'Usar el código de la app',
  back: 'Volver al inicio de sesión',
  setupTitle: 'Configura la verificación en dos pasos',
  setupHint:
    'Tu organización exige verificación en dos pasos. Escanea el código QR con una app autenticadora (Google Authenticator, Microsoft Authenticator, Authy...) e ingresa el código que muestra.',
  cantScan: '¿No puedes escanear? Ingresa esta clave manualmente:',
  loadingQr: 'Generando código QR...',
  confirmLabel: 'Código de 6 dígitos',
  confirmSubmit: 'Activar',
  codesTitle: 'Guarda tus códigos de recuperación',
  codesHint:
    'Cada código sirve una sola vez si pierdes acceso a tu app. No volverás a verlos.',
  copy: 'Copiar',
  copied: '¡Copiado!',
  download: 'Descargar',
  savedCheck: 'He guardado mis códigos en un lugar seguro',
  continue: 'Continuar',
  finishError: 'No se pudo abrir la sesión. Vuelve a iniciar sesión.',
}

const en: Messages = {
  verifyTitle: 'Two-step verification',
  verifyHint: 'Enter the 6-digit code from your authenticator app.',
  recoveryHint: 'Enter one of your recovery codes.',
  codeLabel: 'Code',
  recoveryLabel: 'Recovery code',
  verifySubmit: 'Verify',
  verifying: 'Verifying...',
  useRecovery: 'Use a recovery code',
  useTotp: 'Use the app code',
  back: 'Back to sign in',
  setupTitle: 'Set up two-step verification',
  setupHint:
    'Your organization requires two-step verification. Scan the QR code with an authenticator app (Google Authenticator, Microsoft Authenticator, Authy...) and enter the code it shows.',
  cantScan: "Can't scan? Enter this key manually:",
  loadingQr: 'Generating QR code...',
  confirmLabel: '6-digit code',
  confirmSubmit: 'Activate',
  codesTitle: 'Save your recovery codes',
  codesHint:
    'Each code works only once if you lose access to your app. You will not see them again.',
  copy: 'Copy',
  copied: 'Copied!',
  download: 'Download',
  savedCheck: "I've saved my codes in a safe place",
  continue: 'Continue',
  finishError: 'Could not start the session. Please sign in again.',
}

const pt: Messages = {
  verifyTitle: 'Verificação em duas etapas',
  verifyHint: 'Digite o código de 6 dígitos do seu app autenticador.',
  recoveryHint: 'Digite um dos seus códigos de recuperação.',
  codeLabel: 'Código',
  recoveryLabel: 'Código de recuperação',
  verifySubmit: 'Verificar',
  verifying: 'Verificando...',
  useRecovery: 'Usar um código de recuperação',
  useTotp: 'Usar o código do app',
  back: 'Voltar ao login',
  setupTitle: 'Configure a verificação em duas etapas',
  setupHint:
    'Sua organização exige verificação em duas etapas. Escaneie o código QR com um app autenticador (Google Authenticator, Microsoft Authenticator, Authy...) e digite o código exibido.',
  cantScan: 'Não consegue escanear? Digite esta chave manualmente:',
  loadingQr: 'Gerando código QR...',
  confirmLabel: 'Código de 6 dígitos',
  confirmSubmit: 'Ativar',
  codesTitle: 'Guarde seus códigos de recuperação',
  codesHint:
    'Cada código só funciona uma vez, caso você perca o acesso ao seu app. Você não os verá novamente.',
  copy: 'Copiar',
  copied: 'Copiado!',
  download: 'Baixar',
  savedCheck: 'Guardei meus códigos em um lugar seguro',
  continue: 'Continuar',
  finishError: 'Não foi possível iniciar a sessão. Faça login novamente.',
}

const fr: Messages = {
  verifyTitle: 'Vérification en deux étapes',
  verifyHint: "Saisissez le code à 6 chiffres de votre application d'authentification.",
  recoveryHint: 'Saisissez l’un de vos codes de récupération.',
  codeLabel: 'Code',
  recoveryLabel: 'Code de récupération',
  verifySubmit: 'Vérifier',
  verifying: 'Vérification...',
  useRecovery: 'Utiliser un code de récupération',
  useTotp: "Utiliser le code de l'application",
  back: 'Retour à la connexion',
  setupTitle: 'Configurez la vérification en deux étapes',
  setupHint:
    "Votre organisation exige la vérification en deux étapes. Scannez le code QR avec une application d'authentification (Google Authenticator, Microsoft Authenticator, Authy...) et saisissez le code affiché.",
  cantScan: 'Impossible de scanner ? Saisissez cette clé manuellement :',
  loadingQr: 'Génération du code QR...',
  confirmLabel: 'Code à 6 chiffres',
  confirmSubmit: 'Activer',
  codesTitle: 'Conservez vos codes de récupération',
  codesHint:
    "Chaque code n'est valable qu'une seule fois si vous perdez l'accès à votre application. Vous ne les reverrez plus.",
  copy: 'Copier',
  copied: 'Copié !',
  download: 'Télécharger',
  savedCheck: "J'ai conservé mes codes en lieu sûr",
  continue: 'Continuer',
  finishError: "Impossible d'ouvrir la session. Veuillez vous reconnecter.",
}

const de: Messages = {
  verifyTitle: 'Bestätigung in zwei Schritten',
  verifyHint: 'Gib den 6-stelligen Code deiner Authenticator-App ein.',
  recoveryHint: 'Gib einen deiner Wiederherstellungscodes ein.',
  codeLabel: 'Code',
  recoveryLabel: 'Wiederherstellungscode',
  verifySubmit: 'Bestätigen',
  verifying: 'Wird geprüft...',
  useRecovery: 'Wiederherstellungscode verwenden',
  useTotp: 'App-Code verwenden',
  back: 'Zurück zur Anmeldung',
  setupTitle: 'Bestätigung in zwei Schritten einrichten',
  setupHint:
    'Deine Organisation verlangt die Bestätigung in zwei Schritten. Scanne den QR-Code mit einer Authenticator-App (Google Authenticator, Microsoft Authenticator, Authy...) und gib den angezeigten Code ein.',
  cantScan: 'Scannen nicht möglich? Gib diesen Schlüssel manuell ein:',
  loadingQr: 'QR-Code wird erstellt...',
  confirmLabel: '6-stelliger Code',
  confirmSubmit: 'Aktivieren',
  codesTitle: 'Speichere deine Wiederherstellungscodes',
  codesHint:
    'Jeder Code funktioniert nur einmal, falls du den Zugriff auf deine App verlierst. Du siehst sie nicht erneut.',
  copy: 'Kopieren',
  copied: 'Kopiert!',
  download: 'Herunterladen',
  savedCheck: 'Ich habe meine Codes sicher gespeichert',
  continue: 'Weiter',
  finishError: 'Die Sitzung konnte nicht gestartet werden. Bitte melde dich erneut an.',
}

export const loginMfaMessages: Record<string, Messages> = { es, en, pt, fr, de }
