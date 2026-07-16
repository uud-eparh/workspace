from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
from app.core.config import settings
from app.core.init_super_admin import init_super_admin
from app.core.auth import (
    authenticate_user, create_access_token,
    get_current_user, get_current_tenant
)
from app.core.security import get_password_hash, verify_password
from app.models import GlobalUser, Membership
from app.api.v1.endpoints import users
from app.api.v1.endpoints import tenant
from sqlalchemy import select
import logging
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting OpenLedger...")
    async with engine.begin() as conn:
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        await init_super_admin(db)
    
    yield
    logger.info("🛑 Shutting down OpenLedger...")
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Регистрируем роутеры
app.include_router(users.router)
app.include_router(tenant.router)

# ===== Routes =====

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
    
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    db_status = "✅ Подключено"
    db_version = "N/A"
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT version()"))
            db_version = result.scalar()
    except Exception as e:
        db_status = f"❌ Ошибка: {str(e)}"
    
    redis_status = "✅ Подключено"
    try:
        redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
    except Exception as e:
        redis_status = f"❌ Ошибка: {str(e)}"
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "db_status": db_status,
            "db_version": db_version,
            "redis_status": redis_status,
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, message: str = None):
    """Страница входа"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
    
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error, "message": message}
    )

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка входа"""
    async with AsyncSessionLocal() as db:
        user, tenant_id, error = await authenticate_user(db, username, password)
        
        if error or not user:
            return await login_page(request, error=error or "Неверный логин или пароль")
        
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(tenant_id)
            }
        )
        logger.info(f"🔑 Created token for user {user.id} (tenant: {tenant_id})")
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"
        )
        return response

@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Дашборд"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        logger.info(f"📊 Dashboard user: {user is not None}, tenant: {tenant_id}")
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant_id
        )
    )
    membership = result.scalar_one_or_none()
    
    is_temp_password = False
    if membership:
        temp_hash = get_password_hash("admin123")
        is_temp_password = (membership.layer_access_hash == temp_hash)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "tenant_id": tenant_id,
            "version": settings.VERSION,
            "show_change_password": is_temp_password
        }
    )

@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, error: str = None, success: str = None):
    """Страница смены пароля"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request,
            "user": user,
            "error": error,
            "success": success,
            "version": settings.VERSION,
        }
    )

@app.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Обработка смены пароля"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        tenant_id = await get_current_tenant(request)
        
        if not user or not tenant_id:
            return RedirectResponse(url="/login", status_code=302)
        
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_id
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            return RedirectResponse(url="/login", status_code=302)
        
        if not verify_password(current_password, membership.layer_access_hash):
            return await change_password_page(
                request, 
                error="Неверный текущий пароль"
            )
        
        if len(new_password) < 8:
            return await change_password_page(
                request,
                error="Пароль должен содержать минимум 8 символов"
            )
        
        if new_password != confirm_password:
            return await change_password_page(
                request,
                error="Пароли не совпадают"
            )
        
        membership.layer_access_hash = get_password_hash(new_password)
        await db.commit()
        
        return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/health")
async def health():
    """Проверка здоровья системы"""
    return {"status": "healthy", "version": settings.VERSION}

@app.get("/api/status")
async def status():
    """Детальный статус системы"""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "debug": settings.DEBUG,
    }
from app.api.v1.endpoints import tenant
app.include_router(tenant.router)
