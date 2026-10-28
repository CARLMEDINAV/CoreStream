/**
 * Textos del login con SSO (NEW-08): botones y mensajes de error.
 * Los códigos de error (sso_error) los define el backend en routers/sso.py.
 * Los errores de validación del token (firma, nonce, issuer, tenant) comparten
 * mensaje a propósito: al usuario no le sirve el detalle, y no se filtra
 * información sobre cómo se valida.
 */

export const SSO_ERROR_CODES = [
  'no_account',
  'inactive',
  'state_invalid',
  'exchange_failed',
  'provider_denied',
  'provider_unknown',
  'provider_unreachable',
  'token_invalid',
  'nonce_invalid',
  'issuer_invalid',
  'tenant_invalid',
] as const

export type LoginSsoKey =
  | 'or'
  | 'continueWith'
  | 'sessionFailed'
  | 'genericError'
  | (typeof SSO_ERROR_CODES)[number]

type Messages = Record<LoginSsoKey, string>

const es: Messages = {
  or: 'o',
  continueWith: 'Continuar con',
  sessionFailed: 'No se pudo completar el inicio de sesión. Inténtalo de nuevo.',
  genericError: 'No se pudo iniciar sesión con el proveedor. Inténtalo de nuevo.',
  no_account:
    'No existe una cuenta de CoreStream con ese correo. Pide a tu administrador que te invite.',
  inactive: 'Tu cuenta está desactivada. Contacta a tu administrador.',
  state_invalid: 'La solicitud de inicio de sesión expiró o no es válida. Inténtalo de nuevo.',
  exchange_failed: 'No se pudo completar el inicio de sesión con el proveedor. Inténtalo de nuevo.',
  provider_denied: 'Cancelaste el acceso o el proveedor lo denegó.',
  provider_unknown: 'Ese proveedor de inicio de sesión no está disponible.',
  provider_unreachable: 'No se pudo contactar al proveedor. Inténtalo más tarde.',
  token_invalid: 'No se pudo verificar tu identidad con el proveedor. Inténtalo de nuevo.',
  nonce_invalid: 'No se pudo verificar tu identidad con el proveedor. Inténtalo de nuevo.',
  issuer_invalid: 'No se pudo verificar tu identidad con el proveedor. Inténtalo de nuevo.',
  tenant_invalid: 'No se pudo verificar tu identidad con el proveedor. Inténtalo de nuevo.',
}

const en: Messages = {
  or: 'or',
  continueWith: 'Continue with',
  sessionFailed: 'Sign-in could not be completed. Please try again.',
  genericError: 'Could not sign in with the provider. Please try again.',
  no_account:
    'There is no CoreStream account with that email. Ask your administrator to invite you.',
  inactive: 'Your account is disabled. Contact your administrator.',
  state_invalid: 'The sign-in request expired or is not valid. Please try again.',
  exchange_failed: 'Sign-in with the provider could not be completed. Please try again.',
  provider_denied: 'You cancelled access or the provider denied it.',
  provider_unknown: 'That sign-in provider is not available.',
  provider_unreachable: 'The provider could not be reached. Please try again later.',
  token_invalid: 'Your identity could not be verified with the provider. Please try again.',
  nonce_invalid: 'Your identity could not be verified with the provider. Please try again.',
  issuer_invalid: 'Your identity could not be verified with the provider. Please try again.',
  tenant_invalid: 'Your identity could not be verified with the provider. Please try again.',
}

const pt: Messages = {
  or: 'ou',
  continueWith: 'Continuar com',
  sessionFailed: 'Não foi possível concluir o login. Tente novamente.',
  genericError: 'Não foi possível entrar com o provedor. Tente novamente.',
  no_account:
    'Não existe uma conta do CoreStream com esse e-mail. Peça ao seu administrador que o convide.',
  inactive: 'Sua conta está desativada. Entre em contato com seu administrador.',
  state_invalid: 'A solicitação de login expirou ou não é válida. Tente novamente.',
  exchange_failed: 'Não foi possível concluir o login com o provedor. Tente novamente.',
  provider_denied: 'Você cancelou o acesso ou o provedor o negou.',
  provider_unknown: 'Esse provedor de login não está disponível.',
  provider_unreachable: 'Não foi possível contatar o provedor. Tente mais tarde.',
  token_invalid: 'Não foi possível verificar sua identidade com o provedor. Tente novamente.',
  nonce_invalid: 'Não foi possível verificar sua identidade com o provedor. Tente novamente.',
  issuer_invalid: 'Não foi possível verificar sua identidade com o provedor. Tente novamente.',
  tenant_invalid: 'Não foi possível verificar sua identidade com o provedor. Tente novamente.',
}

const fr: Messages = {
  or: 'ou',
  continueWith: 'Continuer avec',
  sessionFailed: "La connexion n'a pas pu être finalisée. Veuillez réessayer.",
  genericError: 'Connexion impossible avec le fournisseur. Veuillez réessayer.',
  no_account:
    "Aucun compte CoreStream n'existe pour cet e-mail. Demandez à votre administrateur de vous inviter.",
  inactive: 'Votre compte est désactivé. Contactez votre administrateur.',
  state_invalid: 'La demande de connexion a expiré ou n’est pas valide. Veuillez réessayer.',
  exchange_failed: "La connexion avec le fournisseur n'a pas pu être finalisée. Veuillez réessayer.",
  provider_denied: "Vous avez annulé l'accès ou le fournisseur l'a refusé.",
  provider_unknown: "Ce fournisseur de connexion n'est pas disponible.",
  provider_unreachable: 'Impossible de joindre le fournisseur. Réessayez plus tard.',
  token_invalid: "Votre identité n'a pas pu être vérifiée auprès du fournisseur. Veuillez réessayer.",
  nonce_invalid: "Votre identité n'a pas pu être vérifiée auprès du fournisseur. Veuillez réessayer.",
  issuer_invalid: "Votre identité n'a pas pu être vérifiée auprès du fournisseur. Veuillez réessayer.",
  tenant_invalid: "Votre identité n'a pas pu être vérifiée auprès du fournisseur. Veuillez réessayer.",
}

const de: Messages = {
  or: 'oder',
  continueWith: 'Weiter mit',
  sessionFailed: 'Die Anmeldung konnte nicht abgeschlossen werden. Bitte versuche es erneut.',
  genericError: 'Anmeldung beim Anbieter nicht möglich. Bitte versuche es erneut.',
  no_account:
    'Für diese E-Mail-Adresse gibt es kein CoreStream-Konto. Bitte deinen Administrator, dich einzuladen.',
  inactive: 'Dein Konto ist deaktiviert. Wende dich an deinen Administrator.',
  state_invalid: 'Die Anmeldeanfrage ist abgelaufen oder ungültig. Bitte versuche es erneut.',
  exchange_failed: 'Die Anmeldung beim Anbieter konnte nicht abgeschlossen werden. Bitte versuche es erneut.',
  provider_denied: 'Du hast den Zugriff abgebrochen oder der Anbieter hat ihn verweigert.',
  provider_unknown: 'Dieser Anmeldeanbieter ist nicht verfügbar.',
  provider_unreachable: 'Der Anbieter ist nicht erreichbar. Bitte versuche es später erneut.',
  token_invalid: 'Deine Identität konnte beim Anbieter nicht bestätigt werden. Bitte versuche es erneut.',
  nonce_invalid: 'Deine Identität konnte beim Anbieter nicht bestätigt werden. Bitte versuche es erneut.',
  issuer_invalid: 'Deine Identität konnte beim Anbieter nicht bestätigt werden. Bitte versuche es erneut.',
  tenant_invalid: 'Deine Identität konnte beim Anbieter nicht bestätigt werden. Bitte versuche es erneut.',
}

export const loginSsoMessages: Record<string, Messages> = { es, en, pt, fr, de }
