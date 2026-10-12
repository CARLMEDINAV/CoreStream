"""prueba la migracion en un esquema temporal de postgres, sin usar tablas existentes."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.skipif(not os.getenv("WEB17_POSTGRES_URL"), reason="requiere WEB17_POSTGRES_URL")
def test_migracion_conserva_datos_y_valida_enlaces():
    motor = sa.create_engine(os.environ["WEB17_POSTGRES_URL"])
    esquema = "web17_prueba_" + uuid4().hex
    archivo = Path(__file__).parents[1] / "alembic/versions/k7l8m9n0o1p2_incidentes_y_enlaces.py"
    especificacion = importlib.util.spec_from_file_location("migracion_incidencias", archivo)
    migracion = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(migracion)
    try:
        with motor.connect() as conexion:
            conexion.execute(sa.text(f'CREATE SCHEMA "{esquema}"'))
            conexion.execute(sa.text(f'SET search_path TO "{esquema}"'))
            conexion.execute(sa.text("""
                CREATE TYPE incident_status_enum AS ENUM ('REPORTED','INVESTIGATING','MITIGATED','RESOLVED');
                CREATE TYPE notification_type_enum AS ENUM (
                    'TICKET_ASSIGNED','STATUS_CHANGED','TICKET_REDIRECTED','TICKET_COMPLETED',
                    'QUESTION_RAISED','INCIDENT_REPORTED','INCIDENT_ASSIGNED','SYSTEM');
                CREATE TABLE clients (id uuid PRIMARY KEY);
                CREATE TABLE users (id uuid PRIMARY KEY);
                CREATE TABLE tickets (id uuid PRIMARY KEY);
                CREATE TABLE incidents (id uuid PRIMARY KEY, client_id uuid NOT NULL REFERENCES clients, status incident_status_enum NOT NULL);
                CREATE TABLE notifications (
                    id uuid PRIMARY KEY, type notification_type_enum NOT NULL, message text,
                    ticket_id uuid REFERENCES tickets ON DELETE SET NULL,
                    incident_id uuid REFERENCES incidents ON DELETE SET NULL);
            """))
            cliente, incidencia, ticket = uuid4(), uuid4(), uuid4()
            conexion.execute(sa.text("INSERT INTO clients VALUES (:cliente)"), {"cliente": cliente})
            conexion.execute(sa.text("INSERT INTO tickets VALUES (:ticket)"), {"ticket": ticket})
            conexion.execute(sa.text("INSERT INTO incidents VALUES (:incidencia, :cliente, 'REPORTED')"), {
                "incidencia": incidencia, "cliente": cliente,
            })
            for tipo, ti, inc in (
                ("INCIDENT_REPORTED", None, incidencia),
                ("TICKET_ASSIGNED", ticket, None),
                ("INCIDENT_ASSIGNED", None, None),
                ("INCIDENT_REPORTED", ticket, incidencia),
                ("SYSTEM", None, None),
            ):
                conexion.execute(sa.text("INSERT INTO notifications VALUES (:id, :tipo, 'texto conservado', :ticket, :incidencia)"), {
                    "id": uuid4(), "tipo": tipo, "ticket": ti, "incidencia": inc,
                })
            conexion.commit()

            def ejecutar(funcion):
                contexto = MigrationContext.configure(conexion)
                with contexto.begin_transaction():
                    with Operations.context(contexto):
                        funcion()

            ejecutar(migracion.upgrade)
            assert conexion.scalar(sa.text("SELECT count(*) FROM notifications")) == 5
            assert conexion.scalar(sa.text("SELECT count(*) FROM notifications WHERE message = 'texto conservado'")) == 5
            assert conexion.scalar(sa.text("SELECT count(*) FROM notifications WHERE type = 'SYSTEM'")) == 2
            assert conexion.scalar(sa.text("SELECT categoria FROM incidents")) == "general"
            assert conexion.scalar(sa.text("SELECT tipo FROM eventos_incidencia")) == "importacion"
            assert conexion.scalar(sa.text("SELECT autor_id FROM eventos_incidencia")) is None
            with pytest.raises(sa.exc.IntegrityError):
                with conexion.begin_nested():
                    conexion.execute(sa.text("INSERT INTO notifications (id, type) VALUES (:id, 'INCIDENT_ASSIGNED')"), {"id": uuid4()})
            conexion.execute(sa.text("UPDATE incidents SET status = 'IN_REVIEW'"))
            conexion.commit()
            ejecutar(migracion.downgrade)
            assert conexion.scalar(sa.text("SELECT status FROM incidents")) == "INVESTIGATING"
            assert "categoria" not in {columna["name"] for columna in sa.inspect(conexion).get_columns("incidents")}
            conexion.commit()
            ejecutar(migracion.upgrade)
            conexion.execute(sa.text("DELETE FROM incidents"))
            assert conexion.scalar(sa.text("SELECT count(*) FROM notifications WHERE incident_id IS NOT NULL")) == 0
            assert conexion.scalar(sa.text("SELECT count(*) FROM eventos_incidencia")) == 0
            conexion.commit()
    finally:
        with motor.begin() as conexion:
            conexion.execute(sa.text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        motor.dispose()

