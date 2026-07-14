"""
Endpoint de login simplificado sin async/greenlet issues
"""
import psycopg2
from fastapi import APIRouter, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.config import get_settings
from app.schemas import TokenResponse, UserLogin
from app.services.auth_service import AuthService

router = APIRouter(tags=["Auth-Simple"])
settings = get_settings()
security = HTTPBearer()

def get_db_connection():
    """Conectar a PostgreSQL con psycopg2 sync usando DATABASE_URL"""
    db_url = settings.DATABASE_URL
    # Strip async driver prefix so psycopg2 can parse the URL
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return psycopg2.connect(sync_url)

@router.post("/login-simple", response_model=TokenResponse)
def login_simple(credentials: UserLogin) -> TokenResponse:
    """Login simple sin async/greenlet issues"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar usuario
        cursor.execute(
            """
            SELECT u.id, u.hashed_password, r.name 
            FROM users u 
            JOIN roles r ON u.role_id = r.id 
            WHERE u.email = %s
            """,
            (credentials.email,)
        )
        
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos"
            )

        user_id, hashed_password, role = result

        # psycopg2 puede devolver bytes/memoryview en algunos entornos
        if isinstance(hashed_password, (bytes, memoryview)):
            hashed_password = bytes(hashed_password).decode("utf-8")
        hashed_password = str(hashed_password).strip()

        # Verificar contraseña
        if not AuthService.verify_password(credentials.password, hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos"
            )
        
        # Generar tokens
        now = datetime.now(timezone.utc)
        access_exp = now + timedelta(minutes=30)
        refresh_exp = now + timedelta(days=7)
        
        access_token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "exp": int(access_exp.timestamp())
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        refresh_token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "exp": int(refresh_exp.timestamp())
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600
        )
    
    except psycopg2.Error as e:
        print(f"DB Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno"
        )


@router.post("/refresh", response_model=TokenResponse, include_in_schema=False)
def refresh_token_simple(body: dict) -> TokenResponse:
    """Renueva el access token usando un refresh token válido (sin async)."""
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token requerido"
        )
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role", "DEVELOPER")
        if not user_id:
            raise ValueError("sub missing")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado"
        )

    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(minutes=30)
    new_access_token = jwt.encode(
        {"sub": user_id, "role": role, "exp": int(access_exp.timestamp())},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600
    )


@router.get("/me", include_in_schema=False)
def get_current_user_profile(
    authorization: str = Header(None)
):
    """Get current user profile using token - simple sync version"""
    try:
        # Extraer token del header Authorization
        if not authorization or not authorization.startswith("Bearer "):
            print(f"Missing or invalid Authorization header: {authorization}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token requerido"
            )
        
        token = authorization.replace("Bearer ", "")
        
        # Validar token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        # Buscar usuario en BD
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT u.id, u.email, u.full_name, u.specialty, u.avatar_url, u.is_active, u.created_at, r.name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
            """,
            (user_id,)
        )

        result = cursor.fetchone()

        if not result:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )

        user_id, email, full_name, specialty, avatar_url, is_active, created_at, role = result

        preferences = {}
        try:
            cursor.execute("SELECT preferences FROM users WHERE id = %s", (str(user_id),))
            pref_row = cursor.fetchone()
            if pref_row and pref_row[0] is not None:
                preferences = pref_row[0]
        except Exception:
            pass

        conn.close()

        response_data = {
            "id": str(user_id),
            "email": email,
            "fullName": full_name,
            "specialty": specialty,
            "avatarUrl": avatar_url,
            "isActive": is_active,
            "createdAt": created_at.isoformat() if created_at else None,
            "role": role,
            "preferences": preferences
        }
        return response_data
    
    except psycopg2.Error as e:
        print(f"DB Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        print(f"Error in get_current_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )
