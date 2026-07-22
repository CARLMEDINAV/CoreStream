"""
Servicio para gestionar carga de archivos de código y documentación.
Maneja almacenamiento, validación y metadatos de archivos.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile


# Configuración
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "storage" / "uploads"
ALLOWED_EXTENSIONS = {
    # Código
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".cs", ".rb", ".go", ".rs",
    # Documentación
    ".md", ".pdf", ".docx", ".txt", ".rst",
    # Datos
    ".json", ".yaml", ".yml", ".xml", ".sql", ".csv",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class FileService:
    """Servicio para gestionar uploads de archivos."""

    @staticmethod
    def _ensure_upload_dir() -> None:
        """Crear directorio de uploads si no existe."""
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_file(file: UploadFile) -> tuple[bool, Optional[str]]:
        """Validar archivo antes de guardarlo."""
        if not file.filename:
            return False, "Nombre de archivo no válido"

        # Validar extensión
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return False, f"Extensión no permitida. Permitidas: {allowed}"

        # Nota: La validación de tamaño se hace en el stream
        return True, None

    @staticmethod
    async def upload_file(file: UploadFile, user_id: str) -> dict:
        """
        Carga un archivo y retorna metadatos.

        Args:
            file: Archivo a cargar
            user_id: ID del usuario que carga el archivo

        Returns:
            Dict con metadatos del archivo guardado
        """
        FileService._ensure_upload_dir()

        # Validar archivo
        is_valid, error_msg = FileService._validate_file(file)
        if not is_valid:
            raise ValueError(error_msg)

        # Generar nombre único
        file_ext = Path(file.filename).suffix
        unique_id = str(uuid4())
        original_name = Path(file.filename).stem
        saved_filename = f"{unique_id}_{original_name}{file_ext}"

        file_path = UPLOAD_DIR / saved_filename

        # Guardar archivo con validación de tamaño
        try:
            bytes_written = 0
            with open(file_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break

                    bytes_written += len(chunk)
                    if bytes_written > MAX_FILE_SIZE:
                        # Limpiar archivo incompleto
                        file_path.unlink(missing_ok=True)
                        raise ValueError(
                            "Archivo excede tamaño máximo de 50 MB"
                        )

                    f.write(chunk)

        except Exception:
            # Limpiar en caso de error
            file_path.unlink(missing_ok=True)
            raise

        # Retornar metadatos
        return {
            "id": unique_id,
            "filename": file.filename,
            "saved_name": saved_filename,
            "size": bytes_written,
            "extension": file_ext,
            "uploaded_by": user_id,
            "uploaded_at": datetime.utcnow().isoformat(),
            "download_url": f"/api/uploads/download/{unique_id}",
        }

    @staticmethod
    def get_file_path(file_id: str) -> Optional[Path]:
        """Obtener ruta del archivo si existe."""
        FileService._ensure_upload_dir()

        # Buscar archivo que comienza con el ID
        for file in UPLOAD_DIR.glob(f"{file_id}_*"):
            if file.is_file():
                return file

        return None

    @staticmethod
    def delete_file(file_id: str) -> bool:
        """Eliminar archivo si existe."""
        file_path = FileService.get_file_path(file_id)
        if file_path:
            file_path.unlink()
            return True
        return False

    @staticmethod
    def list_files(user_id: Optional[str] = None) -> list[dict]:
        """Listar archivos cargados (todos o de un usuario específico)."""
        FileService._ensure_upload_dir()

        files_list = []
        for file in UPLOAD_DIR.glob("*_*"):
            if file.is_file():
                # Extraer ID del nombre (formato: uuid_name)
                file_id = file.name.split("_")[0]
                stat = file.stat()

                files_list.append({
                    "id": file_id,
                    "filename": file.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                })

        return files_list

    @staticmethod
    def get_file_info(file_id: str) -> Optional[dict]:
        """Obtener información sobre un archivo."""
        file_path = FileService.get_file_path(file_id)
        if not file_path:
            return None

        stat = file_path.stat()
        return {
            "id": file_id,
            "filename": file_path.name,
            "size": stat.st_size,
            "extension": file_path.suffix,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
