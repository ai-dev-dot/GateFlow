from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
from app.database import get_db
from app.models import User, Role, Department
from app.schemas.user import UserCreate, UserUpdate, UserResponse, RoleResponse, DepartmentCreate, DepartmentResponse
from app.middleware.auth_middleware import require_admin
from app.utils.security import get_password_hash

router = APIRouter(prefix="/api/users", tags=["用户管理"])

@router.get("", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.post("", response_model=UserResponse)
async def create_user(request: UserCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    role_id = request.role_id
    if not role_id:
        result = await db.execute(select(Role).where(Role.name == "user"))
        user_role = result.scalar_one_or_none()
        if not user_role:
            user_role = Role(name="user", permissions={})
            db.add(user_role)
            await db.flush()
        role_id = user_role.id
    user = User(
        username=request.username, email=request.email,
        hashed_password=get_password_hash(request.password),
        department_id=request.department_id, role_id=role_id
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, request: UserUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}")
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.delete(user)
    await db.commit()
    return {"message": "用户已删除"}

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(Role))
    return result.scalars().all()

@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(Department))
    return result.scalars().all()

@router.post("/departments", response_model=DepartmentResponse)
async def create_department(request: DepartmentCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    department = Department(name=request.name, parent_id=request.parent_id)
    db.add(department)
    await db.commit()
    await db.refresh(department)
    return department


@router.delete("/departments/{department_id}")
async def delete_department(department_id: UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="部门不存在")
    await db.delete(department)
    await db.commit()
    return {"message": "部门已删除"}
