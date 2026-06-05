"""AgentType CRUD — admin-managed client/tool type enum."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_admin
from app.models import User
from app.models.agent_type import AgentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-types", tags=["Agent Types"])


class AgentTypeCreate(BaseModel):
    name: str


class AgentTypeUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.get("")
async def list_agent_types(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agent types (all users can access)."""
    result = await db.execute(
        select(AgentType).where(AgentType.is_active == True).order_by(AgentType.name)
    )
    types = result.scalars().all()
    return [
        {"id": str(t.id), "name": t.name, "is_active": t.is_active}
        for t in types
    ]


@router.post("")
async def create_agent_type(
    data: AgentTypeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent type (admin only)."""
    # Check for duplicate name
    result = await db.execute(
        select(AgentType).where(AgentType.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent type '{data.name}' already exists")

    agent_type = AgentType(name=data.name)
    db.add(agent_type)
    await db.commit()
    await db.refresh(agent_type)
    return {"id": str(agent_type.id), "name": agent_type.name, "is_active": agent_type.is_active}


@router.put("/{agent_type_id}")
async def update_agent_type(
    agent_type_id: UUID,
    data: AgentTypeUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an agent type (admin only)."""
    result = await db.execute(
        select(AgentType).where(AgentType.id == agent_type_id)
    )
    agent_type = result.scalar_one_or_none()
    if not agent_type:
        raise HTTPException(status_code=404, detail="Agent type not found")

    if data.name is not None:
        # Check for duplicate name
        dup = await db.execute(
            select(AgentType).where(AgentType.name == data.name, AgentType.id != agent_type_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Agent type '{data.name}' already exists")
        agent_type.name = data.name

    if data.is_active is not None:
        agent_type.is_active = data.is_active

    await db.commit()
    await db.refresh(agent_type)
    return {"id": str(agent_type.id), "name": agent_type.name, "is_active": agent_type.is_active}


@router.delete("/{agent_type_id}")
async def delete_agent_type(
    agent_type_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent type (admin only)."""
    result = await db.execute(
        select(AgentType).where(AgentType.id == agent_type_id)
    )
    agent_type = result.scalar_one_or_none()
    if not agent_type:
        raise HTTPException(status_code=404, detail="Agent type not found")

    await db.delete(agent_type)
    await db.commit()
    return {"detail": "Deleted"}
