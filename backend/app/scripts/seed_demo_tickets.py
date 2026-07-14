"""
Inicializa tickets de demostración para QA testing.

Este script crea 6 tickets de prueba asignados a los usuarios de demostración
para permitir la prueba completa del workbench.
"""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime

import psycopg2

from app.config import get_settings


def _to_sync_database_url(database_url: str) -> str:
    """Convierte URL async de SQLAlchemy a URL compatible con psycopg2."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def seed_demo_tickets() -> None:
    """Crea tickets de demostración si no existen."""
    settings = get_settings()
    db_url = _to_sync_database_url(settings.DATABASE_URL)

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Get or create application
        app_id = None
        cursor.execute(
            "SELECT id FROM applications WHERE name = %s",
            ("CoreStream Demo",)
        )
        row = cursor.fetchone()

        if row:
            app_id = str(row[0])
        else:
            app_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO applications (id, name, description, is_active)
                VALUES (%s, %s, %s, %s)
                """,
                (app_id, "CoreStream Demo", "Aplicación demo para pruebas", True),
            )

        # Get or create epic
        epic_id = None
        cursor.execute(
            "SELECT id FROM epics WHERE title = %s",
            ("Sprint Demo",)
        )
        row = cursor.fetchone()

        if row:
            epic_id = str(row[0])
        else:
            epic_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO epics
                  (id, title, description, application_id, is_collapsed, order_index)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (epic_id, "Sprint Demo", "Épica demo para testing de QA", app_id, False, 0),
            )

        # Get user IDs
        cursor.execute("SELECT id FROM users WHERE email = %s", ("userdev@example.com",))
        dev_row = cursor.fetchone()
        dev_id = str(dev_row[0]) if dev_row else None

        cursor.execute("SELECT id FROM users WHERE email = %s", ("leader@example.com",))
        leader_row = cursor.fetchone()
        leader_id = str(leader_row[0]) if leader_row else None

        if not dev_id or not leader_id:
            raise ValueError("Required users not found. Please run seed_persistent_users first.")

        # Define tickets to create
        tickets_to_create = [
            {
                "title": "Implementar autenticación de usuario",
                "description": "Agregar sistema de autenticación basado en tokens JWT",
                "priority": "HIGH",
                "status": "TODO",
                "assignee_id": dev_id,
            },
            {
                "title": "Configurar esquema de base de datos",
                "description": "Crear el esquema inicial de PostgreSQL con todas las tablas requeridas",
                "priority": "HIGH",
                "status": "IN_PROGRESS",
                "assignee_id": dev_id,
            },
            {
                "title": "Corregir tiempo de respuesta de API",
                "description": (
                    "La API presenta timeout en algunos endpoints. "
                    "Investigar y corregir los problemas de rendimiento."
                ),
                "priority": "URGENT",
                "status": "TODO",
                "assignee_id": dev_id,
            },
            {
                "title": "Optimizar filtrado de tickets",
                "description": "Implementar mejor filtrado y búsqueda de tickets",
                "priority": "MEDIUM",
                "status": "TODO",
                "assignee_id": dev_id,
            },
            {
                "title": "Crear documentación del proyecto",
                "description": (
                    "Redactar documentación completa para la configuración "
                    "y arquitectura del proyecto"
                ),
                "priority": "MEDIUM",
                "status": "TODO",
                "assignee_id": leader_id,
            },
            {
                "title": "Revisar métricas de rendimiento del equipo",
                "description": (
                    "Analizar y revisar las métricas de rendimiento del equipo "
                    "para el último sprint"
                ),
                "priority": "LOW",
                "status": "IN_PROGRESS",
                "assignee_id": leader_id,
            },
        ]

        # Create tickets
        for i, ticket_data in enumerate(tickets_to_create):
            # Check if ticket already exists
            cursor.execute(
                "SELECT id FROM tickets WHERE title = %s",
                (ticket_data["title"],)
            )
            if cursor.fetchone():
                continue

            ticket_id = str(uuid4())

            cursor.execute(
                """
                INSERT INTO tickets
                (id, title, description, priority, status, epic_id, assignee_id,
                 order_index, time_spent_seconds, blocked_time_seconds, estimated_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticket_id,
                    ticket_data["title"],
                    ticket_data["description"],
                    ticket_data["priority"],
                    ticket_data["status"],
                    epic_id,
                    ticket_data["assignee_id"],
                    i,
                    0,  # time_spent_seconds
                    0,  # blocked_time_seconds
                    0,  # estimated_time_seconds
                ),
            )

        conn.commit()
        print("✅ Demo tickets created successfully")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error creating demo tickets: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    seed_demo_tickets()
