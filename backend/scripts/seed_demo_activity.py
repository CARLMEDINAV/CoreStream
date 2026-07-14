"""
seed_demo_activity.py — Poblar datos históricos para heatmap y burndown.

Toma tickets existentes en la BD, los pone en estado DONE con completed_at
distribuido en los últimos 7 días, y crea ticket_events de STATUS_CHANGED
con timestamps variados para que el heatmap y burndown muestren datos.

Uso desde Railway Shell:
    python scripts/seed_demo_activity.py
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings
from app.models import Ticket, TicketEvent, TicketStatus, TicketEventType


async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.now(timezone.utc)

    async with Session() as db:
        # Obtener hasta 30 tickets que no estén ya completados
        result = await db.execute(
            select(Ticket)
            .where(Ticket.status != TicketStatus.COMPLETED)
            .limit(30)
        )
        tickets = result.scalars().all()

        if not tickets:
            print("No hay tickets pendientes para convertir en demo. Obteniendo todos...")
            result = await db.execute(select(Ticket).limit(30))
            tickets = result.scalars().all()

        if not tickets:
            print("La BD está vacía — ejecuta seed_users.py primero.")
            return

        updated = 0
        for ticket in tickets:
            # Asignar un completed_at aleatorio en los últimos 7 días
            days_ago = random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            completed_at = now - timedelta(days=days_ago, hours=hours_ago)

            ticket.status = TicketStatus.COMPLETED
            ticket.completed_at = completed_at

            # Crear evento de cambio de estado
            event = TicketEvent(
                ticket_id=ticket.id,
                event_type=TicketEventType.STATUS_CHANGED,
                user_id=ticket.assignee_id or ticket.created_by_id,
                detail={
                    "from": "IN_PROGRESS",
                    "to": "COMPLETED",
                    "demo": True,
                },
                created_at=completed_at,
            )
            db.add(event)
            updated += 1

        await db.commit()
        print(f"✅ {updated} tickets marcados como COMPLETED con fechas de los últimos 7 días.")
        print("   El heatmap y burndown ahora mostrarán datos de actividad.")


if __name__ == "__main__":
    asyncio.run(seed())
