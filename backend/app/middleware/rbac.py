"""
Utilidades RBAC para autorización por roles.

Este módulo define:
- Decorador de permisos para proteger endpoints FastAPI.
- RBACRole, que es un alias de UserRole (ver abajo).
"""

from enum import Enum
from functools import wraps
from inspect import isawaitable
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status

from app.models.role import UserRole

FuncT = TypeVar("FuncT", bound=Callable[..., Any])

# Alias, no un enum paralelo. Antes esto re-declaraba los roles a mano y la
# duplicación ya costó un bug: definía GROUP_LEADER mientras la base usaba
# TEAM_LEADER, así que el decorador denegaba a todos en silencio porque ningún
# usuario tenía jamás ese rol. Había un test de integración vigilando que las
# dos listas coincidieran; al añadir AUDITOR volvió a desincronizarse y el test
# lo detectó. Con el alias, desincronizarse es imposible.
RBACRole = UserRole

_ALLOWED_ROLES = {role.value for role in RBACRole}


def _normalize_role(role: Any) -> str:
    """Normaliza el rol recibido para comparaciones RBAC consistentes."""
    if isinstance(role, Enum):
        value = role.value
    else:
        value = role

    role_value = str(value).upper()
    if role_value not in _ALLOWED_ROLES:
        raise ValueError(f"Rol no soportado para configuración RBAC: {role_value}")
     
    return role_value


def _extract_current_role(current_user: Any) -> str:
    """Extrae el rol del usuario actual desde objeto o diccionario."""
    if current_user is None:
        raise RuntimeError(
            "El decorador RBAC requiere el parámetro 'current_user' en la ruta."
        )

    if isinstance(current_user, dict):
        role = current_user.get("role")
    else:
        role = getattr(current_user, "role", None)

    if role is None:
        raise RuntimeError(
            "No se pudo extraer 'role' desde current_user para validación RBAC."
        )

    return _normalize_role(role)


def require_permissions(*allowed_roles: str | RBACRole) -> Callable[[FuncT], FuncT]:
    """
    Decorador para proteger endpoints en función de roles permitidos.

    Requiere que la función decorada tenga un parámetro llamado current_user,
    normalmente inyectado por Depends(get_current_user).
    """
    if not allowed_roles:
        raise ValueError("require_permissions requiere al menos un rol permitido")

    normalized_allowed_roles = {_normalize_role(role) for role in allowed_roles}

    def decorator(func: FuncT) -> FuncT:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_role = _extract_current_role(kwargs.get("current_user"))

            if current_role not in normalized_allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Permisos insuficientes. "
                        f"Roles permitidos: {', '.join(sorted(normalized_allowed_roles))}"
                    ),
                )

            result = func(*args, **kwargs)
            if isawaitable(result):
                return await result
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
