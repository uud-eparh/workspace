from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user
from app.models import GlobalUser, UserRole
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["Users"])
templates = Jinja2Templates(directory="app/templates")

# ===== HTML страницы =====

@router.get("/", response_class=HTMLResponse)
async def users_list_page(
    request: Request,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    """Страница списка пользователей"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user or user.role != UserRole.MASTER_ADMIN:
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
        if not user or user.role != UserRole.MASTER_ADMIN:
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
    user_id: int,
    error: Optional[str] = None,
):
    """Страница редактирования пользователя"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.MASTER_ADMIN:
            return RedirectResponse(url="/login", status_code=302)
        
        service = UserService(db)
        target_user = await service.get_user_by_id(user_id)
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

# ===== Эндпоинт для HTML-формы (БЕЗ Depends!) =====

@router.post("/form")
async def create_user_form(
    request: Request,
    username: str = Form(...),
    email: Optional[str] = Form(None),
    password: str = Form(...),
    role: str = Form("USER"),
    is_active: bool = Form(True),
):
    """Создать пользователя из HTML-формы"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if not current_user or current_user.role != UserRole.MASTER_ADMIN:
            return RedirectResponse(url="/admin/users", status_code=302)
        
        user_data = UserCreate(
            username=username,
            email=email,
            password=password,
            role=role,
            is_active=is_active
        )
        
        service = UserService(db)
        
        existing = await service.get_user_by_username(username)
        if existing:
            return RedirectResponse(
                url="/admin/users/new?error=Пользователь с таким именем уже существует",
                status_code=302
            )
        
        try:
            user = await service.create_user(user_data)
            return RedirectResponse(url="/admin/users", status_code=302)
        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return RedirectResponse(
                url=f"/admin/users/new?error=Ошибка при создании пользователя: {str(e)}",
                status_code=302
            )

# ===== API эндпоинты =====

@router.post("/", response_model=UserResponse)
async def create_user_api(
    user_data: UserCreate,
    request: Request,
):
    """Создать пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if current_user.role != UserRole.MASTER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        service = UserService(db)
        
        existing = await service.get_user_by_username(user_data.username)
        if existing:
            raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
        
        user = await service.create_user(user_data)
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
):
    """Обновить пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if current_user.role != UserRole.MASTER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        service = UserService(db)
        user = await service.update_user(user_id, user_data)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None
        )

@router.delete("/{user_id}", response_model=None)
async def delete_user(
    user_id: int,
    request: Request,
):
    """Удалить пользователя (API)"""
    async with AsyncSessionLocal() as db:
        current_user = await get_current_user(request, db)
        if current_user.role != UserRole.MASTER_ADMIN:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        if current_user.id == user_id:
            raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
        
        service = UserService(db)
        success = await service.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {"message": "Пользователь удален"}
