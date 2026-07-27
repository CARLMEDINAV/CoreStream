"""
Router de Autenticación y Autorización.

Gestiona todos los endpoints relacionados con:
- Registro de nuevos usuarios
- Login y generación de tokens JWT
- Refresco de tokens de acceso
- Gestión del perfil del usuario actual
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Role
# ANTES: from app.schemas import UserResponse, TokenResponse, UserRegister, UserLogin, UserUpdate
# CAMBIO (2026-04-07): Se reemplaza UserRegister por UserCreate para consistencia con schemas/user.py
from app.schemas import UserResponse, TokenResponse, UserCreate, UserLogin, UserUpdate, RefreshRequest
from app.schemas.user import PasswordChange
from app.services.auth_service import AuthService
from app.middleware.auth import get_current_user
from app.redis_client import publish_message

# Creación del router con prefijo y etiqueta para documentación automática
router = APIRouter(tags=["Autenticación"])


async def _to_user_response(db: AsyncSession, user: User) -> UserResponse:
    """Construye UserResponse evitando lazy-load async de user.role."""
    role_name = "DEVELOPER"
    if user.role_id:
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_name = role.name

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        specialty=user.specialty,
        role=role_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        created_at=user.created_at,
        preferences=user.preferences,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description="Crea una nueva cuenta de usuario con email y contraseña"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Registra un nuevo usuario en el sistema.

    Args:
        user_data (UserCreate): Datos del usuario a registrar (email, contraseña, nombre)
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        UserResponse: Objeto con los datos del usuario creado

    Raises:
        HTTPException: Si el email ya existe (estado 409)
    """
    # Normalizar email a minúsculas para evitar problemas de duplicados por capitalización
    user_data.email = user_data.email.lower()

    # Verificar si el usuario ya existe en la base de datos
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado"
        )

    # Crear nuevo usuario con contraseña hasheada
    new_user = await AuthService.create_user(db, user_data)
    await db.commit()
    await db.refresh(new_user)

    # --- INTEGRACIÓN REDIS: SISTEMA DE COLAS (Tarea 16) ---
    try:
        # Publicamos un mensaje en la cola 'new_users' al registrarse
        await publish_message("new_users", {
            "user_id": str(new_user.id),
            "email": new_user.email,
            "event": "registration_complete"
        })
    except Exception as e:
        print(f"Error preventivo en cola Redis: {e}")

    return await _to_user_response(db, new_user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
    description="Autentica un usuario y devuelve tokens JWT"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Autentica un usuario y genera tokens de acceso.

    Args:
        credentials (UserLogin): Email y contraseña del usuario
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TokenResponse: Contiene access_token y refresh_token

    Raises:
        HTTPException: Si las credenciales son inválidas (estado 401)
    """
    # Normalizar email para la búsqueda (insensible a mayúsculas)
    email_search = credentials.email.lower()

    # Buscar el usuario por email con role relationship
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.email == email_search)
    )
    user = result.unique().scalar_one_or_none()

    # Validar que el usuario existe y la contraseña es correcta
    if not user or not AuthService.verify_password(
        credentials.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract role from user.role relationship
    role_name = user.role.name if user.role else "DEVELOPER"

    # 3. Generar tokens JWT
    try:
        access_token = AuthService.create_access_token(user, role_name=role_name)
        refresh_token = AuthService.create_refresh_token(user)
    except Exception as e:
        print(f"Error generando tokens: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar tokens de autenticación"
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refrescar token de acceso",
    description="Genera un nuevo access_token usando un refresh_token válido"
)
async def refresh_token(
    token_data: RefreshRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Refresca el token de acceso usando un refresh_token.

    Args:
        token_data (dict): Contiene el refresh_token
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TokenResponse: Nuevo access_token

    Raises:
        HTTPException: Si el refresh_token es inválido (estado 401)
    """
    # Validar y extraer información del refresh_token
    user_id = await AuthService.verify_refresh_token(token_data.refresh_token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Verificar que el usuario aún existe
    result = await db.execute(
        select(User, Role.name)
        .join(Role, User.role_id == Role.id)
        .where(User.id == user_id)
    )
    row = result.first()
    user = row[0] if row else None
    role_name = row[1] if row else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )

    # Generar nuevo access_token
    new_access_token = AuthService.create_access_token(user, role_name=role_name)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=token_data.refresh_token,
        token_type="bearer",
        expires_in=3600
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener perfil del usuario actual",
    description="Devuelve los datos del usuario autenticado"
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Obtiene el perfil del usuario autenticado actualmente.

    Args:
        current_user (User): Usuario autenticado (inyectado por dependencia)

    Returns:
        UserResponse: Datos del usuario autenticado
    """
    # Refrescar datos del usuario desde la BD para garantizar información actualizada
    await db.refresh(current_user)
    return await _to_user_response(db, current_user)





@router.put(
    "/me",
    response_model=UserResponse,
    summary="Actualizar perfil del usuario actual",
    description="Permite al usuario modificar su propia información (nombre, avatar, etc.)"
)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Actualiza el perfil del usuario autenticado.

    Args:
        user_update (UserUpdate): Datos a actualizar (nombre, avatar, etc.)
        current_user (User): Usuario autenticado (inyectado por dependencia)
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        UserResponse: Datos actualizados del usuario

    Raises:
        HTTPException: Si la actualización falla (estado 400)
    """
    try:
        update_data = user_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(current_user, field, value)

        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

        return await _to_user_response(db, current_user)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar el perfil: {str(e)}"
        )

@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Cambiar contraseña",
    description="Permite al usuario autenticado cambiar su propia contraseña"
)
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Cambia la contraseña del usuario actual.

    Args:
        payload (PasswordChange): Contraseña actual y nueva
        current_user (User): Usuario autenticado (inyectado)
        db (AsyncSession): Sesión de base de datos

    Returns:
        dict: Mensaje de éxito
    """
    await AuthService.change_password(
        db=db,
        user_id=str(current_user.id),
        old_password=payload.old_password,
        new_password=payload.new_password
    )
    return {"message": "Contraseña actualizada exitosamente"}