from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine
from app.core.config import settings
from app.core.init_db import init_master_admin
from app.core.auth import authenticate_user, create_access_token, get_current_user
from app.core.security import get_password_hash, verify_password
from app.api.v1.endpoints import users
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
        await init_master_admin(db)
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

# ===== Routes =====

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
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
    async with AsyncSessionLocal() as db:
        user = await authenticate_user(db, username, password)
        
        if not user:
            return await login_page(request, error="Неверный логин или пароль")
        
        access_token = create_access_token(data={"sub": str(user.id)})
        logger.info(f"🔑 Created token for user {user.id}")
        
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
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        logger.info(f"📊 Dashboard user: {user is not None}")
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    is_default_password = verify_password("admin123", user.password_hash)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "version": settings.VERSION,
            "show_change_password": is_default_password
        }
    )

@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, error: str = None, success: str = None):
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
    
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "error": error, "success": success}
    )

@app.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        if not verify_password(current_password, user.password_hash):
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
        
        user.password_hash = get_password_hash(new_password)
        await db.commit()
        
        return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.VERSION}

@app.get("/api/status")
async def status():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "debug": settings.DEBUG,
    }

@app.post("/test-form")
async def test_form(
    username: str = Form(...),
    password: str = Form(...),
):
    return {"username": username, "password": password}
