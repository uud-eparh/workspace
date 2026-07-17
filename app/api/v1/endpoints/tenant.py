from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, not_
from sqlalchemy.orm import joinedload
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user, get_current_tenant, create_access_token
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.models import GlobalUser, TenantLayer, Membership, UserRole
from typing import Optional, List
import uuid
import secrets
import string
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenant", tags=["Tenant"])
templates = Jinja2Templates(directory="app/templates")

# ===== Вспомогательные функции =====

def generate_simple_password(length: int = 8) -> str:
    """Генерирует простой пароль"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

async def get_tenant_users(db, tenant_id: uuid.UUID) -> List[dict]:
    """Получает список пользователей компании с их ролями"""
    result = await db.execute(
        select(Membership, GlobalUser)
        .join(GlobalUser, Membership.user_id == GlobalUser.id)
        .where(Membership.tenant_id == tenant_id)
    )
    users = []
    for membership, user in result:
        users.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": membership.role,
            "is_active": membership.is_active,
            "membership_id": membership.id
        })
    return users

async def get_available_users_for_tenant(db, tenant_id: uuid.UUID) -> List[GlobalUser]:
    """Получает список пользователей, которых можно добавить в компанию"""
    # Пользователи, уже имеющие доступ к этой компании
    result = await db.execute(
        select(Membership.user_id).where(Membership.tenant_id == tenant_id)
    )
    existing_user_ids = [row[0] for row in result]
    
    # Все пользователи, кроме SUPER_ADMIN и тех, кто уже в компании
    query = select(GlobalUser).where(
        GlobalUser.role != UserRole.SUPER_ADMIN,
        GlobalUser.id.notin_(existing_user_ids) if existing_user_ids else True
    )
    result = await db.execute(query)
    return result.scalars().all()

async def get_chief_companies(db, user_id: uuid.UUID) -> List[dict]:
    """Получает список компаний, где пользователь является chief"""
    result = await db.execute(
        select(Membership, TenantLayer)
        .join(TenantLayer, Membership.tenant_id == TenantLayer.id)
        .where(
            Membership.user_id == user_id,
            Membership.role == "chief",
            Membership.tenant_id.isnot(None)
        )
    )
    companies = []
    for membership, tenant in result:
        companies.append({
            "id": tenant.id,
            "name": tenant.name,
            "description": tenant.description,
            "is_active": tenant.is_active
        })
    return companies

# ===== Страницы =====

@router.get("/create", response_class=HTMLResponse)
async def tenant_create_page(request: Request, error: Optional[str] = None):
    """Страница создания компании"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        if user.role != UserRole.CHIEF:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse(
            "tenant/create.html",
            {
                "request": request,
                "user": user,
                "error": error,
                "version": "0.1.0",
            }
        )

@router.get("/companies", response_class=HTMLResponse)
async def chief_companies(request: Request):
    """Список компаний руководителя"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user or user.role != UserRole.CHIEF:
            return RedirectResponse(url="/login", status_code=302)
        
        companies = await get_chief_companies(db, user.id)
        
        return templates.TemplateResponse(
            "chief_dashboard.html",
            {
                "request": request,
                "user": user,
                "companies": companies,
                "version": "0.1.0",
            }
        )

@router.get("/manage", response_class=HTMLResponse)
async def tenant_manage_page(request: Request):
    """Страница управления пользователями компании"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not user or not tenant_id:
            return RedirectResponse(url="/login", status_code=302)
        
        # Проверяем, что пользователь имеет роль chief в этом слое
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        # Получаем информацию о слое
        result = await db.execute(
            select(TenantLayer).where(TenantLayer.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        # Получаем список пользователей компании
        users = await get_tenant_users(db, tenant_id)
        
        return templates.TemplateResponse(
            "tenant/manage.html",
            {
                "request": request,
                "user": user,
                "tenant": tenant,
                "users": users,
                "version": "0.1.0",
            }
        )

@router.post("/create")
async def tenant_create(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    password: str = Form(...),
):
    """Создание компании"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user or user.role != UserRole.CHIEF:
            return RedirectResponse(url="/login", status_code=302)
        
        if len(password) < 8:
            return templates.TemplateResponse(
                "tenant/create.html",
                {
                    "request": request,
                    "user": user,
                    "error": "Пароль должен содержать минимум 8 символов",
                    "version": "0.1.0",
                }
            )
        
        # Проверяем, не использует ли пользователь этот пароль для другой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id.isnot(None)
            )
        )
        existing_memberships = result.scalars().all()
        
        for membership in existing_memberships:
            if verify_password(password, membership.layer_access_hash):
                return templates.TemplateResponse(
                    "tenant/create.html",
                    {
                        "request": request,
                        "user": user,
                        "error": "Этот пароль уже используется для другой компании. Пожалуйста, выберите другой.",
                        "version": "0.1.0",
                    }
                )
        
        # Хешируем пароль
        password_hash = get_password_hash(password)
        
        # Создаем слой (компанию)
        tenant = TenantLayer(
            name=name,
            description=description or "",
            master_key_hash="temporary",
            is_active=True,
            created_by=user.id
        )
        db.add(tenant)
        await db.flush()
        
        # Добавляем создателя в компанию с ролью chief
        membership = Membership(
            user_id=user.id,
            tenant_id=tenant.id,
            role="chief",
            layer_access_hash=password_hash,
            is_active=True
        )
        db.add(membership)
        
        await db.commit()
        
        # Создаем новый токен с tenant_id
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(tenant.id)
            }
        )
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"
        )
        return response

# ===== API для управления пользователями =====

@router.get("/api/users")
async def get_company_users(request: Request):
    """Получить список пользователей компании (API)"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        users = await get_tenant_users(db, tenant_id)
        return JSONResponse(users)

@router.get("/api/available-users")
async def get_available_users(request: Request):
    """Получить список пользователей, доступных для добавления в компанию"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        available_users = await get_available_users_for_tenant(db, tenant_id)
        return JSONResponse([
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value
            }
            for u in available_users
        ])

@router.post("/api/users")
async def add_user_to_company(request: Request):
    """Добавить пользователя в компанию"""
    async with AsyncSessionLocal() as db:
        data = await request.json()
        user_id = data.get("user_id")
        role = data.get("role")
        
        if not user_id or not role:
            return JSONResponse({"error": "Необходимо указать пользователя и роль"}, status_code=400)
        
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return JSONResponse({"error": "Неверный ID пользователя"}, status_code=400)
        
        current_user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not current_user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Проверяем, что пользователь существует
        result = await db.execute(
            select(GlobalUser).where(GlobalUser.id == user_uuid)
        )
        target_user = result.scalar_one_or_none()
        if not target_user:
            return JSONResponse({"error": "Пользователь не найден"}, status_code=404)
        
        # Проверяем, что пользователь уже не в компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user_uuid,
                Membership.tenant_id == tenant_id
            )
        )
        if result.scalar_one_or_none():
            return JSONResponse({"error": "Пользователь уже имеет доступ к этой компании"}, status_code=400)
        
        # Генерируем пароль
        password = generate_simple_password()
        password_hash = get_password_hash(password)
        
        # Добавляем пользователя
        membership = Membership(
            user_id=user_uuid,
            tenant_id=tenant_id,
            role=role,
            layer_access_hash=password_hash,
            is_active=True
        )
        db.add(membership)
        await db.commit()
        
        return JSONResponse({
            "message": "Пользователь добавлен",
            "user_id": str(user_uuid),
            "password": password
        })

@router.put("/api/users/{user_id}/role")
async def change_user_role(user_id: str, request: Request):
    """Изменить роль пользователя в компании"""
    async with AsyncSessionLocal() as db:
        data = await request.json()
        new_role = data.get("role")
        
        if not new_role:
            return JSONResponse({"error": "Необходимо указать роль"}, status_code=400)
        
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return JSONResponse({"error": "Неверный ID пользователя"}, status_code=400)
        
        current_user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not current_user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Находим membership пользователя в этой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user_uuid,
                Membership.tenant_id == tenant_id
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            return JSONResponse({"error": "Пользователь не найден в этой компании"}, status_code=404)
        
        membership.role = new_role
        await db.commit()
        
        return JSONResponse({"message": "Роль изменена"})

@router.post("/api/users/{user_id}/toggle")
async def toggle_user_access(user_id: str, request: Request):
    """Заблокировать/разблокировать доступ пользователя к компании"""
    async with AsyncSessionLocal() as db:
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return JSONResponse({"error": "Неверный ID пользователя"}, status_code=400)
        
        current_user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not current_user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Находим membership пользователя в этой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user_uuid,
                Membership.tenant_id == tenant_id
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            return JSONResponse({"error": "Пользователь не найден в этой компании"}, status_code=404)
        
        membership.is_active = not membership.is_active
        await db.commit()
        
        return JSONResponse({
            "message": "Доступ обновлен",
            "is_active": membership.is_active
        })

@router.post("/api/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, request: Request):
    """Сбросить пароль пользователя для доступа к компании"""
    async with AsyncSessionLocal() as db:
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return JSONResponse({"error": "Неверный ID пользователя"}, status_code=400)
        
        current_user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not current_user or not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Проверяем права
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.tenant_id == tenant_id,
                Membership.role == "chief"
            )
        )
        if not result.scalar_one_or_none():
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Находим membership пользователя в этой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user_uuid,
                Membership.tenant_id == tenant_id
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            return JSONResponse({"error": "Пользователь не найден в этой компании"}, status_code=404)
        
        # Генерируем новый пароль
        new_password = generate_simple_password(10)
        membership.layer_access_hash = get_password_hash(new_password)
        await db.commit()
        
        return JSONResponse({
            "message": "Пароль сброшен",
            "new_password": new_password
        })

@router.post("/generate-password/{tenant_id}")
async def generate_password(tenant_id: str, request: Request):
    """Генерирует новый пароль для компании"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user or user.role != UserRole.CHIEF:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный ID компании")
        
        # Проверяем, что пользователь является chief в этой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_uuid,
                Membership.role == "chief"
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(status_code=403, detail="У вас нет прав на управление этой компанией")
        
        # Генерируем новый пароль
        new_password = generate_simple_password(10)
        
        # Обновляем хеш пароля
        membership.layer_access_hash = get_password_hash(new_password)
        await db.commit()
        
        return {"password": new_password}

@router.post("/switch/{tenant_id}")
async def switch_tenant(tenant_id: str, request: Request):
    """Переключиться на другую компанию"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный ID компании")
        
        # Проверяем, что пользователь имеет доступ к этой компании
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_uuid,
                Membership.is_active == True
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(status_code=403, detail="У вас нет доступа к этой компании")
        
        # Создаем новый токен с tenant_id
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(tenant_uuid)
            }
        )
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"
        )
        return response
