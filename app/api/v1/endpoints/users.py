from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user, get_current_tenant
from app.models import GlobalUser, UserRole
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from typing import Optional
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])
templates = Jinja2Templates(directory="app/templates")

# ===== HTML страницы =====

@router.get("/", response_class=HTMLResponse)
async def users_list_page(
    request: Request,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    """Страница списка пользователей (только для SUPER_ADMIN)"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user or user.role != UserRole.SUPER_ADMIN:
            return RedirectResponse(url="/login", status_code=302)
        
        service = UserService(db)
        skip = (page - 1) * per_page
        users, total = await service.get_users(skip=skip, limit=per_page, search=search)
        
        return templates.TemplateResponse(
            "admin/users.html",
            {
                "request": request,
                "users": users,
                "search": search,
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
                "user": user,
            }
        )

@router.get("/new", response_class=HTMLResponse)
async def user_create_page(
    request: Request,
    error: Optional[str] = None,
):
    """Страница создания пользователя"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user or user.role != UserRole.SUPER_ADMIN:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse(
            "admin/user_form.html",
            {
                "request": request,
                "user": user,
                "error": error,
                "is_edit": False,
            }
        )

@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def user_edit_page(
    request: Request,
    user_id: str,
    error: Optional[str] = None,
):
    """Страница редактирования пользователя"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.SUPER_ADMIN:
            return RedirectResponse(url="/login", status_code=302)
        
        service = UserService(db)
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return RedirectResponse(url="/admin/users", status_code=302)
        
        target_user = await service.get_user_by_id(user_uuid)
        if not target_user:
            return RedirectResponse(url="/admin/users", status_code=302)
        
        return templates.TemplateResponse(
            "admin/user_form.html",
            {
                "request": request,
                "user": current_user,
                "target_user": target_user,
                "error": error,
                "is_edit": True,
            }
        )

# ===== API эндпоинты =====

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    request: Request,
):
    """Создать пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        service = UserService(db)
        try:
            user = await service.create_user(user_data)
            return UserResponse.model_validate(user)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    request: Request,
):
    """Обновить пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        service = UserService(db)
        try:
            user = await service.update_user(user_uuid, user_data)
            if not user:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            return UserResponse.model_validate(user)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
):
    """Удалить пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат ID")
        
        if current_user.id == user_uuid:
            raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
        
        service = UserService(db)
        user = await service.toggle_user_active(user_uuid)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {"message": f"Пользователь {'заблокирован' if not user.is_active else 'разблокирован'}"}
