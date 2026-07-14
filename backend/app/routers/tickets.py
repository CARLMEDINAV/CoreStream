"""
Router Principal de Tickets - Gestión del Ciclo de Vida Completo.

Este es el router más importante de CoreStream que maneja:
- CRUD de tickets (crear, leer, actualizar, eliminar)
- Transiciones de estado: TODO -> IN_PROGRESS -> COMPLETED
- Gestor de temporizador de trabajo (timer)
- Preguntas bloqueantes y resolución de preguntas
- Redirección de tickets a otros usuarios
- Historial de eventos de tickets
- Validación de pull requests antes de completar

Cada operación de cambio de estado utiliza la máquina de estados (ticket_state_machine)
para garantizar transiciones válidas y consistencia de datos.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.models import (
    Ticket, User, Epic, TicketStatus, TicketEvent,
    TicketEventType, Subtask, Role
)
from app.schemas.ticket import (
    TicketResponse, TicketCreate, TicketUpdate, TicketMoveEpic,
    TicketComplete, TicketQuestion, TicketRedirect, TicketResolveQuestion,
    TicketEventResponse, TicketReorder
)
from app.services.ticket_state_machine import ticket_state_machine
from app.services.timer_service import timer_service
from app.services.notification_service import (
    notify_status_changed,
    notify_ticket_completed,
    notify_question_raised,
    notify_ticket_redirected,
    flush_pending_notifications,
)
from app.middleware.auth import get_current_user
from app.redis_client import publish_message


# Router para tickets con prefijo y etiqueta
router = APIRouter(tags=["Tickets"])


async def _publish_ticket_status(ticket_id: UUID | str, new_status: str) -> None:
    """Publica cambio de estado al canal general tickets:updates (fire-and-forget)."""
    try:
        await publish_message("tickets:updates", {
            "type": "TICKET_STATUS_UPDATE",
            "ticket_id": str(ticket_id),
            "new_status": new_status,
        })
    except Exception:
        pass


def _require_non_admin(current_user: User) -> None:
    """Raises 403 if the authenticated user is an ADMIN.

    Complete/start/question/redirect actions belong to developers and team
    leaders. Admins manage the system but do not execute ticket work.
    """
    role_name = (
        current_user.role.name
        if hasattr(current_user.role, "name")
        else str(current_user.role)
    )
    if role_name == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los administradores no pueden ejecutar acciones de trabajo en tickets",
        )


@router.get(
    "/",
    response_model=List[TicketResponse],
    summary="Listar tickets con filtros",
    description="Lista tickets filtrados por aplicación, estado de asignación o asignado específico",
)
async def list_tickets(
    application_id: Optional[UUID] = Query(None),
    unassigned: Optional[bool] = Query(None),
    assignee_id: Optional[UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tickets with optional filtering by application, assignment status, or specific assignee."""
    query = select(Ticket).options(
        selectinload(Ticket.assignee).selectinload(User.role),
        selectinload(Ticket.epic).selectinload(Epic.application),
        selectinload(Ticket.subtasks),
    )
    if application_id is not None:
        query = query.join(Epic, Ticket.epic_id == Epic.id).where(
            Epic.application_id == application_id
        )
    if unassigned is True:
        query = query.where(Ticket.assignee_id.is_(None))
    elif assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.get(
    "/by-epic/{epic_id}",
    response_model=List[TicketResponse],
    summary="Listar tickets de una épica",
    description="Obtiene todos los tickets de una épica específica con sus detalles"
)
async def get_epic_tickets(
    epic_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filtrar por estado de ticket"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todos los tickets pertenecientes a una épica específica.

    Args:
        epic_id (int): ID de la épica
        skip (int): Número de registros a omitir
        limit (int): Máximo de registros a retornar
        status_filter (str): Filtro opcional por estado (TODO, IN_PROGRESS, COMPLETED)
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        List[TicketResponse]: Lista de tickets con información de asignación y estado

    Raises:
        HTTPException: Si la épica no existe (404)
    """
    # Verificar que la épica existe
    epic_check = await db.execute(
        select(Epic).where(Epic.id == epic_id)
    )
    if not epic_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Épica con ID {epic_id} no encontrada"
        )

    # Construir consulta base con carga eagre de epic.application para breadcrumbs
    query = (
        select(Ticket)
        .options(selectinload(Ticket.epic).selectinload(Epic.application))
        .where(Ticket.epic_id == epic_id)
    )

    # Aplicar filtro de estado si se proporciona
    if status_filter:
        query = query.where(Ticket.status == status_filter)

    # Ejecutar con paginación
    result = await db.execute(
        query.offset(skip).limit(limit)
    )
    tickets = result.scalars().all()

    return tickets


@router.get(
    "/my-workbench",
    response_model=List[TicketResponse],
    summary="Obtener banco de trabajo personal",
    description="Retorna todos los tickets asignados al usuario actual ordenados por prioridad"
)
async def get_my_workbench(
    status_filter: Optional[str] = Query(None),
    priority_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el banco de trabajo personal del usuario con tickets asignados.

    Args:
        status_filter (str): Filtro opcional por estado
        priority_filter (str): Filtro opcional por prioridad
        current_user (User): Usuario autenticado (obtenido de token)
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        List[TicketResponse]: Tickets asignados al usuario ordenados por prioridad
    """
    try:
        # Construir consulta para obtener tickets asignados
        query = (
            select(Ticket)
            .options(
                selectinload(Ticket.epic).selectinload(Epic.application),
                selectinload(Ticket.assignee).selectinload(User.role),
                selectinload(Ticket.subtasks),
            )
            .where(Ticket.assignee_id == current_user.id)
        )

        # Aplicar filtros si se proporcionan
        if status_filter:
            query = query.where(Ticket.status == status_filter)
        if priority_filter:
            query = query.where(Ticket.priority == priority_filter)

        # Ordenar por fecha de creación descendente
        result = await db.execute(
            query.order_by(Ticket.created_at.desc())
        )
        tickets = result.scalars().all()

        return tickets
    except Exception as e:
        import traceback
        print("ERROR en get_my_workbench:", traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo ticket",
    description="Crea un nuevo ticket en una épica específica"
)
async def create_ticket(
    ticket_data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea un nuevo ticket en una épica.

    Args:
        ticket_data (TicketCreate): Datos del nuevo ticket
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket creado

    Raises:
        HTTPException: Si la épica no existe (404) o hay error en creación (400)
    """
    # Verificar que la épica existe
    epic_check = await db.execute(
        select(Epic).where(Epic.id == ticket_data.epic_id)
    )
    if not epic_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Épica con ID {ticket_data.epic_id} no encontrada"
        )

    try:
        # Crear nuevo ticket con estado inicial TODO
        new_ticket = Ticket(
            **ticket_data.model_dump(),
            status=TicketStatus.TODO,
            created_by_id=current_user.id
        )
        db.add(new_ticket)
        await db.commit()
        await db.refresh(new_ticket)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al crear ticket: {str(e)}"
        )

    # Registrar evento de creación — fallo aquí no cancela el ticket ya guardado
    try:
        await ticket_state_machine.log_ticket_event(
            db, new_ticket.id, TicketEventType.CREATED,
            current_user.id, f"Ticket creado por {current_user.full_name}"
        )
    except Exception:
        pass

    # Recargar con relaciones (incluyendo epic para epic_title / app_name)
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == new_ticket.id)
        .options(
            selectinload(Ticket.epic).selectinload(Epic.application),
            selectinload(Ticket.subtasks),
            selectinload(Ticket.assignee).selectinload(User.role)
        )
    )
    return result.scalar_one()


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Obtener ticket por ID",
    description="Recupera todos los detalles de un ticket incluyendo subtareas y asignado"
)
async def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene los detalles completos de un ticket específico.

    Args:
        ticket_id (int): ID del ticket a obtener
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Datos del ticket con información de asignación y subtareas

    Raises:
        HTTPException: Si el ticket no existe (404)
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.epic).selectinload(Epic.application),
            selectinload(Ticket.subtasks),
            selectinload(Ticket.assignee).selectinload(User.role),
            selectinload(Ticket.created_by).selectinload(User.role),
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    return TicketResponse.model_validate(ticket)


@router.put(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Actualizar ticket",
    description="Modifica los datos de un ticket (título, descripción, prioridad)"
)
async def update_ticket(
    ticket_id: UUID,
    ticket_update: TicketUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza los datos de un ticket.

    Args:
        ticket_id (int): ID del ticket a actualizar
        ticket_update (TicketUpdate): Nuevos datos del ticket
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket actualizado

    Raises:
        HTTPException: Si el ticket no existe (404) o hay error en actualización (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    try:
        update_data = ticket_update.model_dump(exclude_unset=True)
        if 'assignee_id' in update_data and ticket.status in (TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED, TicketStatus.BLOCKED_QUESTION):
            update_data['status'] = TicketStatus.TODO
        for field, value in update_data.items():
            setattr(ticket, field, value)

        await db.commit()
        await db.refresh(ticket)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar ticket: {str(e)}"
        )

    # Registrar evento de actualización — fallo aquí no cancela la actualización ya guardada
    try:
        await ticket_state_machine.log_ticket_event(
            db, ticket_id, TicketEventType.UPDATED,
            current_user.id, "Ticket actualizado"
        )
    except Exception:
        pass

    # Volvemos a consultar el ticket pero incluyendo (selectinload) sus relaciones
    result_final = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.epic).selectinload(Epic.application),
            selectinload(Ticket.subtasks),
            selectinload(Ticket.assignee).selectinload(User.role)
        )
    )

    ticket_final = result_final.scalar_one()

    return ticket_final


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar ticket",
    description="Elimina un ticket del sistema de forma permanente"
)
async def delete_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina un ticket del sistema.

    Args:
        ticket_id (int): ID del ticket a eliminar
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Raises:
        HTTPException: Si el ticket no existe (404) o hay error en eliminación (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    try:
        # Detener temporizador si está activo
        await timer_service.stop_timer(ticket_id, db)

        # Eliminar ticket y sus relaciones en cascada
        await db.delete(ticket)
        await db.commit()

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al eliminar ticket: {str(e)}"
        )


@router.patch(
    "/{ticket_id}/move",
    response_model=TicketResponse,
    summary="Mover ticket a otra épica (VALIDADO)",
    description="Permite drag-drop de tickets SOLO dentro de la misma aplicación"
)
async def move_ticket_to_epic(
    ticket_id: UUID,
    move_data: TicketMoveEpic,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mueve un ticket de una épica a otra CON VALIDACIÓN de integridad jerárquica.
    
    RESTRICCIÓN CRÍTICA:
    - El ticket SOLO puede moverse a épicas de la MISMA aplicación
    - Previene violación de integridad referencial
    - Un ticket de App A NUNCA puede terminar en Epic de App B

    Args:
        ticket_id (UUID): ID del ticket a mover
        move_data (TicketMoveEpic): Contiene 'new_epic_id' con la épica destino
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket con épica actualizada

    Raises:
        HTTPException: Si ticket/épica no existen (404) o apps son diferentes (400)
    """
    
    # 1️⃣ CARGAR TICKET ACTUAL
    ticket_result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = ticket_result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    # 2️⃣ CARGAR ÉPICA ACTUAL (para obtener application_id)
    current_epic_result = await db.execute(
        select(Epic).where(Epic.id == ticket.epic_id)
    )
    current_epic = current_epic_result.scalar_one_or_none()

    if not current_epic:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Épica actual no encontrada (inconsistencia de BD)"
        )

    # 3️⃣ CARGAR ÉPICA DESTINO
    new_epic_result = await db.execute(
        select(Epic).where(Epic.id == move_data.new_epic_id)
    )
    new_epic = new_epic_result.scalar_one_or_none()

    if not new_epic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Épica destino con ID {move_data.new_epic_id} no encontrada"
        )

    # ═════════════════════════════════════════════════════════════════════
    # 🔒 VALIDACIÓN CRÍTICA #1: Verificar que ambas épicas están en la MISMA app
    # ═════════════════════════════════════════════════════════════════════
    if current_epic.application_id != new_epic.application_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"❌ Apps diferentes, movimiento rechazado. "
                f"Ticket está en App '{current_epic.application_id}', "
                f"pero destino está en App '{new_epic.application_id}'. "
            )
        )

    # 4️⃣ VALIDACIÓN ADICIONAL: Épica destino no debe estar archivada
    if hasattr(new_epic, 'is_archived') and new_epic.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede mover ticket a épica archivada"
        )

    # 5️⃣ VALIDACIÓN: Advertencia si movimiento de ticket completado
    if ticket.status == TicketStatus.COMPLETED:
        # Permitir pero loguear
        print(f"⚠️  Movimiento de ticket completado: {ticket_id} a {move_data.new_epic_id}")

    try:
        # 6️⃣ REALIZAR MOVIMIENTO
        old_epic_id = ticket.epic_id
        ticket.epic_id = move_data.new_epic_id

        await db.commit()
        await db.refresh(ticket)

        # 7️⃣ REGISTRAR EVENTO CON DETALLES
        await ticket_state_machine.log_ticket_event(
            db=db,
            ticket_id=ticket_id,
            event_type=TicketEventType.MOVED,
            user_id=current_user.id,
            detail={
                "from_epic_id": str(old_epic_id),
                "to_epic_id": str(move_data.new_epic_id),
                "from_app_id": str(current_epic.application_id),
                "to_app_id": str(new_epic.application_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        result_final = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.epic).selectinload(Epic.application),
                selectinload(Ticket.subtasks),
                selectinload(Ticket.assignee).selectinload(User.role),
            )
        )
        ticket_final = result_final.scalar_one()
        try:
            return TicketResponse.model_validate(ticket_final)
        except Exception as ser_err:
            import traceback
            print(f"[MOVE] Serialization error: {traceback.format_exc()}")
            return {"status": "ok", "id": str(ticket_id)}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al mover ticket: {str(e)}"
        )


@router.patch(
    "/{ticket_id}/reorder",
    response_model=TicketResponse,
    summary="Reordenar ticket dentro de épica",
    description="Cambia la posición de un ticket respecto a otros en la misma épica"
)
async def reorder_ticket(
    ticket_id: UUID,
    reorder_data: TicketReorder,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reordena un ticket dentro de su épica actual.

    Args:
        ticket_id (UUID): ID del ticket a reordenar
        reorder_data (TicketReorder): Contiene 'new_index' con la nueva posición
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket con order_index actualizado

    Raises:
        HTTPException: Si el ticket no existe (404) o hay error en actualización (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    try:
        old_index = ticket.order_index
        epic_id = ticket.epic_id
        new_index = reorder_data.new_index

        # Obtener todos los tickets de la épica ordenados por order_index
        tickets_in_epic_result = await db.execute(
            select(Ticket)
            .where(Ticket.epic_id == epic_id)
            .order_by(Ticket.order_index)
        )
        tickets_in_epic = tickets_in_epic_result.scalars().all()

        # Validar que new_index está en rango válido
        max_index = len(tickets_in_epic) - 1
        if new_index < 0 or new_index > max_index:
            raise ValueError(f"new_index debe estar entre 0 y {max_index}")

        # Si es el mismo índice, no hacer nada
        if old_index == new_index:
            return ticket

        # Recalcular índices: retirar el ticket y colocarlo en la nueva posición
        if old_index < new_index:
            # Movimiento hacia adelante: decrementar índices entre old y new
            for t in tickets_in_epic:
                if t.id != ticket_id and old_index < t.order_index <= new_index:
                    t.order_index -= 1
            ticket.order_index = new_index
        else:
            # Movimiento hacia atrás: incrementar índices entre new y old
            for t in tickets_in_epic:
                if t.id != ticket_id and new_index <= t.order_index < old_index:
                    t.order_index += 1
            ticket.order_index = new_index

        await db.commit()
        await db.refresh(ticket)

        # Registrar evento
        await ticket_state_machine.log_ticket_event(
            db, ticket_id, TicketEventType.UPDATED,
            current_user.id,
            f"Ticket reordenado de posición {old_index} a {new_index}"
        )

        return ticket

    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al reordenar ticket: {str(e)}"
        )


@router.post(
    "/{ticket_id}/start",
    response_model=TicketResponse,
    summary="Iniciar trabajo en ticket",
    description="Cambia estado TODO -> IN_PROGRESS e inicia el temporizador"
)
async def start_ticket_work(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Inicia el trabajo en un ticket (transición TODO -> IN_PROGRESS).

    Args:
        ticket_id (int): ID del ticket a iniciar
        current_user (User): Usuario autenticado (se convierte en asignado)
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket con estado actualizado a IN_PROGRESS

    Raises:
        HTTPException: Si el ticket no existe (404) o no está en TODO (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    _require_non_admin(current_user)

    print(f"[START] ticket={ticket_id} status={ticket.status!r} assignee={ticket.assignee_id} user={current_user.email!r}")

    # Validar que el ticket está en estado TODO
    if ticket.status != TicketStatus.TODO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede iniciar un ticket en estado TODO, actual: {ticket.status}"
        )

    try:
        # Utilizar máquina de estados para cambiar estado
        await ticket_state_machine.transition_to_in_progress(ticket, current_user, db)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al iniciar ticket: {str(e)}"
        )

    # Iniciar temporizador — fallo no bloquea la transición de estado
    try:
        await timer_service.start_timer(ticket_id, current_user.id, db)
    except Exception:
        pass

    # Commit del estado del ticket (SIEMPRE debe persistir)
    try:
        await db.commit()
        await db.refresh(ticket)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar estado del ticket: {str(e)}"
        )

    # Notificar en tiempo real al Constructor y otros clientes
    await _publish_ticket_status(ticket_id, "IN_PROGRESS")

    # Notificación — commit separado; si falla no revierte el estado
    try:
        if ticket.created_by_id:
            await notify_status_changed(
                db,
                ticket_id=ticket_id,
                owner_id=ticket.created_by_id,
                actor_name=current_user.full_name or current_user.email,
                ticket_title=ticket.title,
                new_status="IN_PROGRESS",
            )
        await db.commit()
        await flush_pending_notifications(db)
    except Exception:
        await db.rollback()

    result_final = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.epic).selectinload(Epic.application),
            selectinload(Ticket.subtasks),
            selectinload(Ticket.assignee).selectinload(User.role)
        )
    )
    started_ticket = result_final.scalar_one()
    return TicketResponse.model_validate(started_ticket)


@router.post(
    "/{ticket_id}/complete",
    response_model=TicketResponse,
    summary="Completar ticket",
    description="Cambia estado IN_PROGRESS -> COMPLETED (requiere pull request link válido)"
)
async def complete_ticket(
    ticket_id: UUID,
    completion_data: TicketComplete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Completa un ticket validando que hay un pull request link.

    Args:
        ticket_id (int): ID del ticket a completar
        completion_data (dict): Contiene 'pr_link' con el enlace al pull request
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket con estado actualizado a COMPLETED

    Raises:
        HTTPException: Si el ticket no existe (404), no está en IN_PROGRESS (400),
                      o no tiene PR link válido (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    _require_non_admin(current_user)

    if ticket.status != TicketStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede completar un ticket en IN_PROGRESS, actual: {ticket.status}"
        )

    try:
        # La state machine detiene el timer, setea pr_link, completed_at y el estado.
        await ticket_state_machine.transition_to_completed(
            ticket, current_user, completion_data.pr_link, db
        )

        # Notificar al creador del ticket (antes del commit)
        if ticket.created_by_id:
            await notify_ticket_completed(
                db,
                ticket_id=ticket_id,
                owner_id=ticket.created_by_id,
                developer_name=current_user.full_name or current_user.email,
                ticket_title=ticket.title,
            )

        await db.commit()
        await db.refresh(ticket)
        await flush_pending_notifications(db)

        # Notificar en tiempo real al Constructor y otros clientes
        await _publish_ticket_status(ticket_id, "COMPLETED")

        result_final = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.epic).selectinload(Epic.application),
                selectinload(Ticket.subtasks),
                selectinload(Ticket.assignee).selectinload(User.role)
            )
        )
        return result_final.scalar_one()

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al completar ticket: {str(e)}"
        )


@router.post(
    "/{ticket_id}/question",
    response_model=TicketResponse,
    summary="Plantear pregunta bloqueante",
    description="Pausa el trabajo bloqueando el ticket con una pregunta"
)
async def raise_ticket_question(
    ticket_id: UUID,
    question_data: TicketQuestion,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Plantea una pregunta bloqueante en un ticket (pausa el temporizador).

    Args:
        ticket_id (int): ID del ticket
        question_data (dict): Contiene 'question' con el texto de la pregunta
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket marcado como bloqueado por pregunta

    Raises:
        HTTPException: Si el ticket no existe (404) o no está en IN_PROGRESS (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    _require_non_admin(current_user)

    print(f"[QUESTION] ticket={ticket_id} status={ticket.status!r} assignee={ticket.assignee_id} user={current_user.email!r} q_len={len(question_data.question_text)}")

    if ticket.status != TicketStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede plantear pregunta en IN_PROGRESS, actual: {ticket.status}"
        )

    # La state machine pausa el timer, setea BLOCKED, block_reason y registra el evento.
    try:
        await ticket_state_machine.transition_to_blocked(
            ticket, current_user, question_data.question_text, db
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al bloquear ticket: {str(e)}"
        )

    # Commit del estado (SIEMPRE debe persistir)
    try:
        await db.commit()
        await db.refresh(ticket)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar estado del ticket: {str(e)}"
        )

    # Notificación — commit separado; si falla no revierte el estado
    # Notifica a TODOS los líderes/admins activos (no solo al creador del ticket)
    try:
        leaders_result = await db.execute(
            select(User)
            .join(User.role)
            .where(
                Role.name.in_(["TEAM_LEADER", "ADMIN"]),
                User.is_active.is_(True),
            )
        )
        leaders = leaders_result.scalars().all()

        # Construir conjunto de IDs únicos a notificar
        notify_ids = {u.id for u in leaders}
        if ticket.created_by_id:
            notify_ids.add(ticket.created_by_id)
        # No notificar al desarrollador que levantó la pregunta
        notify_ids.discard(current_user.id)

        for uid in notify_ids:
            await notify_question_raised(
                db,
                ticket_id=ticket_id,
                owner_id=uid,
                developer_name=current_user.full_name or current_user.email,
                ticket_title=ticket.title,
            )

        await db.commit()
        await flush_pending_notifications(db)
    except Exception:
        await db.rollback()

    # Notificar en tiempo real al Constructor y otros clientes
    await _publish_ticket_status(ticket_id, "BLOCKED_QUESTION")

    result_final = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.epic).selectinload(Epic.application),
            selectinload(Ticket.subtasks),
            selectinload(Ticket.assignee).selectinload(User.role)
        )
    )
    return result_final.scalar_one()


@router.post(
    "/{ticket_id}/resolve-question",
    response_model=TicketResponse,
    summary="Resolver pregunta bloqueante",
    description="Resuelve una pregunta y reanuda el temporizador"
)
async def resolve_ticket_question(
    ticket_id: UUID,
    resolution_data: TicketResolveQuestion,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Resuelve una pregunta bloqueante y reanuda el trabajo.

    Args:
        ticket_id (int): ID del ticket
        resolution_data (dict): Contiene 'resolution' con la respuesta
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket desbloqueado y temporizador reanudado

    Raises:
        HTTPException: Si el ticket no existe (404) o no está bloqueado (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    if ticket.status not in (TicketStatus.BLOCKED, TicketStatus.BLOCKED_QUESTION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ticket no está bloqueado por una pregunta"
        )

    try:
        # La state machine reanuda el timer, setea IN_PROGRESS, limpia block_reason
        # y registra el evento con timestamp preciso.
        await ticket_state_machine.transition_to_in_progress_from_blocked(
            ticket, current_user, resolution_data.resolution, db
        )

        await db.commit()

        # Notificar en tiempo real al Constructor y otros clientes
        await _publish_ticket_status(ticket_id, "IN_PROGRESS")

        result_final = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.epic).selectinload(Epic.application),
                selectinload(Ticket.subtasks),
                selectinload(Ticket.assignee).selectinload(User.role),
                selectinload(Ticket.created_by).selectinload(User.role),
            )
        )
        return result_final.scalar_one()

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al resolver pregunta: {str(e)}"
        )


@router.post(
    "/{ticket_id}/redirect",
    response_model=TicketResponse,
    summary="Redirigir ticket a otro usuario",
    description="Transfiere un ticket a otro usuario con motivo documentado"
)
async def redirect_ticket(
    ticket_id: UUID,
    redirect_data: TicketRedirect,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Redirige un ticket a otro usuario documentando el motivo.

    Args:
        ticket_id (int): ID del ticket a redirigir
        redirect_data (dict): Contiene 'target_user_id' y 'reason'
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        TicketResponse: Ticket reasignado

    Raises:
        HTTPException: Si el ticket o usuario destino no existen (404) o hay error (400)
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    _require_non_admin(current_user)

    target_user_id = redirect_data.to_user_id

    # Verificar que el usuario destino existe
    user_check = await db.execute(
        select(User).where(User.id == target_user_id)
    )
    if not user_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {target_user_id} no encontrado"
        )

    try:
        # La state machine pausa el timer (si IN_PROGRESS), reasigna el ticket,
        # setea TODO y registra el evento de redirección con timestamp preciso.
        await ticket_state_machine.transition_to_redirected(
            ticket, current_user, redirect_data.to_user_id, redirect_data.reason, db
        )

        # Notificar al nuevo asignado (antes del commit)
        await notify_ticket_redirected(
            db,
            ticket_id=ticket_id,
            new_assignee_id=redirect_data.to_user_id,
            redirector_name=current_user.full_name or current_user.email,
            ticket_title=ticket.title,
            justification=redirect_data.reason,
        )

        await db.commit()
        await db.refresh(ticket)
        await flush_pending_notifications(db)

        result_final = await db.execute(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.epic).selectinload(Epic.application),
                selectinload(Ticket.subtasks),
                selectinload(Ticket.assignee).selectinload(User.role)
            )
        )
        return result_final.scalar_one()

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al redirigir ticket: {str(e)}"
        )


@router.get(
    "/{ticket_id}/events",
    response_model=List[TicketEventResponse],
    summary="Obtener historial de eventos del ticket",
    description="Retorna todos los eventos registrados de un ticket (creación, cambios de estado, etc.)"
)
async def get_ticket_events(
    ticket_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[TicketEventResponse]:
    """
    Obtiene el historial de eventos de un ticket.

    Args:
        ticket_id (int): ID del ticket
        skip (int): Número de eventos a omitir
        limit (int): Máximo de eventos a retornar
        current_user (User): Usuario autenticado
        db (AsyncSession): Sesión asíncrona de base de datos

    Returns:
        List[TicketEventResponse]: Historial de eventos ordenado cronológicamente

    Raises:
        HTTPException: Si el ticket no existe (404)
    """
    # Verificar que el ticket existe
    ticket_check = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    if not ticket_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket con ID {ticket_id} no encontrado"
        )

    # Obtener eventos ordenados por fecha descendente
    # Cargar user y user.role eagerly para evitar MissingGreenlet durante serialización Pydantic
    result = await db.execute(
        select(TicketEvent)
        .options(selectinload(TicketEvent.user).selectinload(User.role))
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    events = result.scalars().all()

    return events
