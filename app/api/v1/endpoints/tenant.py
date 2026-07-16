from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user, get_current_tenant, create_access_token
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.models import GlobalUser, TenantLayer, Membership, UserRole
from typing import Optional
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenant", tags=["Tenant"])
templates = Jinja2Templates(directory="app/templates")

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
        
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        if user.role != UserRole.CHIEF:
            return RedirectResponse(url="/dashboard", status_code=302)
        
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
                Membership.tenant_id.isnot(None)  # Только компании, не глобальный доступ
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

@router.get("/companies", response_class=HTMLResponse)
async def chief_companies(request: Request):
    """Список компаний руководителя"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user or user.role != UserRole.CHIEF:
            return RedirectResponse(url="/login", status_code=302)
        
        # Находим все компании, где пользователь является chief
        result = await db.execute(
            select(Membership, TenantLayer)
            .join(TenantLayer, Membership.tenant_id == TenantLayer.id)
            .where(
                Membership.user_id == user.id,
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
        
        return templates.TemplateResponse(
            "chief_dashboard.html",
            {
                "request": request,
                "user": user,
                "companies": companies,
                "version": "0.1.0",
            }
        )

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
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        
        # Обновляем хеш пароля
        from app.core.security import get_password_hash
        membership.layer_access_hash = get_password_hash(new_password)
        await db.commit()
        
        # В реальном проекте здесь должна быть отправка email
        return {"password": new_password}
