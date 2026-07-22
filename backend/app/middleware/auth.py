# Archivo de autenticación y autorización
# Proporciona funciones para crear tokens JWT, verificarlos y usar como dependencias FastAPI

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User

from app.config import get_settings
from app.schemas import TokenPayload

# Configurar contexto de contraseñas con bcrypt para hash seguro
# bcrypt es el algoritmo recomendado para almacenar contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de seguridad Bearer para extraer tokens JWT del header Authorization
security = HTTPBearer()


def hash_password(password: str) -> str:
    """
    Hash una contraseña en texto plano usando bcrypt.
    
    Las contraseñas jamás se almacenan en texto plano en la base de datos.
    En su lugar, se almacena el hash que se puede verificar sin exponer la contraseña.
    
    Args:
        password: Contraseña en texto plano a hashear
        
    Returns:
        str: Hash seguro de la contraseña con salt
        
    Ejemplo:
        hashed = hash_password("miContraseña123")
        # Resultado: $2b$12$...hash...
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica que una contraseña en texto plano coincida con su hash.
    
    Utiliza la función verify segura que evita timing attacks.
    
    Args:
        plain_password: Contraseña en texto plano a verificar
        hashed_password: Hash almacenado en la base de datos
        
    Returns:
        bool: True si la contraseña es correcta, False en caso contrario
        
    Ejemplo:
        if verify_password("miContraseña123", hashed_password):
            # Contraseña correcta
            pass
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea un token JWT de acceso firmado.
    
    El token contiene los datos proporcionados y una fecha de expiración.
    Se utiliza para autenticar solicitudes a endpoints protegidos.
    
    Args:
        data: Diccionario con datos a incluir en el token (ej: {"sub": user_id, "role": "admin"})
        expires_delta: Duración del token desde ahora (si es None, usa el valor por defecto de configuración)
        
    Returns:
        str: Token JWT codificado en formato string
        
    Raises:
        ValueError: Si los parámetros son inválidos
        
    Ejemplo:
        token = create_access_token(
            data={"sub": "user_id_123", "role": "admin"},
            expires_delta=timedelta(minutes=30)
        )
        # Retorna: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    settings = get_settings()
    
    # Copiar datos para no modificar el diccionario original
    to_encode = data.copy()
    
    # Calcular tiempo de expiración
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Agregar tiempo de expiración al payload
    to_encode.update({"exp": expire})
    
    # Firmar el token con la clave secreta
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Crea un token JWT de refresco con duración más larga.
    
    Los tokens de refresco se utilizan para obtener nuevos access tokens
    sin requerer que el usuario vuelva a proporcionar sus credenciales.
    
    Args:
        data: Diccionario con datos a incluir en el token (ej: {"sub": user_id})
        
    Returns:
        str: Token JWT de refresco codificado
        
    Ejemplo:
        refresh_token = create_refresh_token({"sub": "user_id_123"})
        # Se puede usar para obtener un nuevo access_token
    """
    settings = get_settings()
    
    # Copiar datos para no modificar el diccionario original
    to_encode = data.copy()
    
    # Calcular tiempo de expiración más largo para refresh tokens
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    # Agregar tiempo de expiración al payload
    to_encode.update({"exp": expire})
    
    # Firmar el token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> TokenPayload:
    """
    Verifica y decodifica un token JWT.
    
    Valida la firma del token usando la clave secreta y extrae su contenido.
    
    Args:
        token: Token JWT a verificar
        
    Returns:
        TokenPayload: Datos extraídos del token (sub, role, exp)
        
    Raises:
        HTTPException: Si el token es inválido, expirado o no puede decodificarse
        JWTError: Si hay error en la decodificación
        
    Ejemplo:
        token_data = verify_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        user_id = token_data.sub
        user_role = token_data.role
    """
    settings = get_settings()
    
    try:
        # Decodificar y verificar el token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Extraer datos esperados del payload
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        exp: int = payload.get("exp")
        
        # Validar que los datos requeridos estén presentes
        if sub is None or role is None or exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: faltan campos requeridos"
            )
        
        # Crear objeto TokenPayload con los datos
        token_data = TokenPayload(sub=sub, role=role, exp=exp)
        
        return token_data
        
    except JWTError:
        # Capturar errores específicos de JWT (expiración, firma inválida, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar el token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependencia FastAPI que extrae y valida el usuario actual desde el token JWT,
    y lo busca en la base de datos para retornar el objeto User completo.
    
    Se utiliza en endpoints protegidos para verificar autenticación.
    Extrae el token del header Authorization, valida su firma, y busca al usuario
    correspondiente en la base de datos.
    
    Args:
        credentials: Credenciales Bearer extraídas del header Authorization
        db: Sesión asíncrona de base de datos para buscar el usuario
        
    Returns:
        User: Objeto completo del usuario autenticado desde la base de datos
        
    Raises:
        HTTPException 401: Si el token es inválido, expirado o no está presente
        HTTPException 401: Si el usuario del token no existe en la base de datos
        
    Ejemplo en un endpoint:
        @app.get("/profile")
        async def get_profile(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id, "role": current_user.role}
    """
    from uuid import UUID
    
    # Verificar y decodificar el token JWT
    token_data = verify_token(credentials.credentials)

    # Buscar el usuario en la base de datos usando el ID del token (sub)
    try:
        user_id = UUID(token_data.sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: ID de usuario mal formado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.unique().scalar_one_or_none()

    # Validar que el usuario aún existe en el sistema
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


def _normalize_role_value(role: object) -> str:
    """Normaliza diferentes representaciones de rol a texto en mayúsculas."""
    if role is None:
        return ""

    if hasattr(role, "name"):
        value = getattr(role, "name")
    elif hasattr(role, "value"):
        value = getattr(role, "value")
    else:
        value = role

    return str(value).upper()


def require_role(required_roles: list[str] | str):
    """
    Factory que crea una dependencia para verificar que el usuario tiene uno de los roles requeridos.
    
    Se utiliza para autorización basada en roles (RBAC).
    
    Args:
        required_roles: Lista de roles aceptados (ej: ["admin", "manager"])
        
    Returns:
        async function: Función que se puede usar como dependencia FastAPI
        
    Raises:
        HTTPException: Si el usuario no tiene ninguno de los roles requeridos
        
    Ejemplo:
        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: UUID,
            current_user: TokenPayload = Depends(get_current_user),
            _: None = Depends(require_role(["admin"]))
        ):
            # Solo usuarios con rol "admin" pueden ejecutar esta función
            return {"message": "Usuario eliminado"}
    """
    normalized_required_roles = {
        _normalize_role_value(role)
        for role in (required_roles if isinstance(required_roles, (list, tuple, set)) else [required_roles])
    }

    async def verify_role(
        current_user: User = Depends(get_current_user)
    ) -> User:
        """
        Verifica que el usuario actual tenga uno de los roles requeridos.
        
        Args:
            current_user: Datos del usuario extraídos del token JWT
            
        Returns:
            User: Los datos del usuario si tiene permisos
            
        Raises:
            HTTPException: Si el usuario no tiene el rol requerido
        """
        # Extraer el valor del rol de forma segura (soporta Enums, Modelos con 'name' o strings)
        role_obj = getattr(current_user, "role", None)
        if role_obj is None:
            user_role = ""
        elif hasattr(role_obj, 'value'):
            user_role = str(role_obj.value)
        elif hasattr(role_obj, 'name'):
            user_role = str(role_obj.name)
        else:
            user_role = str(role_obj)

        # Asegurar que required_roles sea una colección para evitar el TypeError
        # y problemas de coincidencia parcial si se pasa un string por error
        roles_to_check = [required_roles] if isinstance(required_roles, str) else required_roles

        if user_role not in roles_to_check:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Se requiere uno de estos roles: "
                    + ", ".join(sorted(normalized_required_roles))
                )
            )
        
        return current_user
    
    return verify_role
