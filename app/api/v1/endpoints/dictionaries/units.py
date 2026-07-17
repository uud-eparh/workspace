from fastapi import APIRouter, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user
from app.models import UnitOfMeasure
from typing import Optional
import uuid
import csv
from io import StringIO
import hashlib
import time

router = APIRouter(prefix="/units", tags=["Units"])
templates = Jinja2Templates(directory="app/templates")

# Временное хранилище для файлов
temp_files = {}

# ===== Страницы =====

@router.get("/", response_class=HTMLResponse)
async def units_list(request: Request):
    """Список единиц измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        result = await db.execute(select(UnitOfMeasure).order_by(UnitOfMeasure.code))
        units = result.scalars().all()
        
        return templates.TemplateResponse(
            "dictionaries/units.html",
            {
                "request": request,
                "user": user,
                "units": units,
                "title": "Единицы измерения",
                "version": "0.1.0",
            }
        )

@router.get("/create", response_class=HTMLResponse)
async def units_create_page(request: Request, error: Optional[str] = None):
    """Страница создания единицы измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/unit_form.html",
            {
                "request": request,
                "user": user,
                "error": error,
                "is_edit": False,
                "title": "Создание единицы измерения",
                "version": "0.1.0",
            }
        )

@router.get("/{unit_id}/edit", response_class=HTMLResponse)
async def units_edit_page(request: Request, unit_id: str, error: Optional[str] = None):
    """Страница редактирования единицы измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        try:
            unit_uuid = uuid.UUID(unit_id)
        except ValueError:
            return RedirectResponse(url="/dictionaries/units", status_code=302)
        
        result = await db.execute(
            select(UnitOfMeasure).where(UnitOfMeasure.id == unit_uuid)
        )
        unit = result.scalar_one_or_none()
        if not unit:
            return RedirectResponse(url="/dictionaries/units", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/unit_form.html",
            {
                "request": request,
                "user": user,
                "unit": unit,
                "error": error,
                "is_edit": True,
                "title": "Редактирование единицы измерения",
                "version": "0.1.0",
            }
        )

# ===== Импорт из CSV =====

@router.get("/import", response_class=HTMLResponse)
async def units_import_page(request: Request, error: Optional[str] = None, preview: Optional[list] = None):
    """Страница импорта единиц измерения из CSV"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/unit_import.html",
            {
                "request": request,
                "user": user,
                "error": error,
                "preview": preview,
                "title": "Импорт единиц измерения",
                "version": "0.1.0",
            }
        )

@router.post("/import/preview")
async def units_import_preview(
    request: Request,
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
):
    """Предпросмотр CSV-файла перед импортом"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Сохраняем файл во временное хранилище
        content = await file.read()
        try:
            decoded = content.decode(encoding)
        except UnicodeDecodeError:
            return await units_import_page(
                request, 
                error=f"Не удалось декодировать файл с кодировкой {encoding}. Попробуйте другую кодировку."
            )
        
        # Сохраняем содержимое в памяти
        file_id = hashlib.md5(f"{user.id}{time.time()}".encode()).hexdigest()
        temp_files[file_id] = {
            "content": decoded,
            "filename": file.filename,
            "delimiter": delimiter,
            "encoding": encoding,
            "created_at": time.time()
        }
        
        # Парсим CSV
        reader = csv.DictReader(StringIO(decoded), delimiter=delimiter)
        
        columns = reader.fieldnames if reader.fieldnames else []
        preview_data = []
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_data.append(row)
        
        if not preview_data:
            return await units_import_page(
                request, 
                error="Файл пуст или не содержит данных. Проверьте разделитель и кодировку."
            )
        
        return templates.TemplateResponse(
            "dictionaries/unit_import.html",
            {
                "request": request,
                "user": user,
                "columns": columns,
                "preview": preview_data,
                "full_preview": preview_data,
                "filename": file.filename,
                "file_id": file_id,
                "delimiter": delimiter,
                "encoding": encoding,
                "title": "Импорт единиц измерения",
                "version": "0.1.0",
            }
        )

@router.post("/import/execute")
async def units_import_execute(
    request: Request,
    file_id: str = Form(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    mapping_code: Optional[str] = Form(None),
    mapping_name: Optional[str] = Form(None),
    mapping_symbol: Optional[str] = Form(None),
    skip_duplicates: bool = Form(True),
):
    """Выполнить импорт единиц измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Проверяем маппинг
        if not mapping_code or not mapping_name:
            return await units_import_page(
                request, 
                error="Необходимо указать соответствие для полей 'Код' и 'Название'."
            )
        
        # Получаем содержимое файла из временного хранилища
        if file_id not in temp_files:
            return await units_import_page(
                request, 
                error="Файл не найден. Попробуйте загрузить его снова."
            )
        
        file_data = temp_files[file_id]
        decoded = file_data["content"]
        
        # Парсим CSV
        reader = csv.DictReader(StringIO(decoded), delimiter=delimiter)
        
        # Импортируем
        imported = 0
        updated = 0
        skipped = 0
        errors = []
        
        for row in reader:
            code = row.get(mapping_code, "").strip()
            name = row.get(mapping_name, "").strip()
            symbol = row.get(mapping_symbol, "").strip() if mapping_symbol else ""
            
            if not code or not name:
                skipped += 1
                continue
            
            # Проверяем, существует ли уже
            result = await db.execute(
                select(UnitOfMeasure).where(UnitOfMeasure.code == code)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                if skip_duplicates:
                    skipped += 1
                    continue
                else:
                    # Обновляем существующую запись
                    existing.name = name
                    if symbol:
                        existing.symbol = symbol
                    updated += 1
            else:
                # Создаем новую запись
                unit = UnitOfMeasure(
                    code=code,
                    name=name,
                    symbol=symbol or None
                )
                db.add(unit)
                imported += 1
        
        await db.commit()
        
        # Удаляем временный файл
        del temp_files[file_id]
        
        # Возвращаем результат
        return templates.TemplateResponse(
            "dictionaries/unit_import.html",
            {
                "request": request,
                "user": user,
                "import_result": {
                    "imported": imported,
                    "updated": updated,
                    "skipped": skipped,
                    "errors": errors,
                },
                "title": "Импорт единиц измерения",
                "version": "0.1.0",
            }
        )

# ===== API =====

@router.post("/")
async def units_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    symbol: Optional[str] = Form(None),
):
    """Создать единицу измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Проверяем уникальность кода
        result = await db.execute(
            select(UnitOfMeasure).where(UnitOfMeasure.code == code)
        )
        if result.scalar_one_or_none():
            return await units_create_page(
                request, 
                error=f"Единица измерения с кодом '{code}' уже существует"
            )
        
        unit = UnitOfMeasure(
            code=code,
            name=name,
            symbol=symbol
        )
        db.add(unit)
        await db.commit()
        
        return RedirectResponse(url="/dictionaries/units", status_code=302)

@router.post("/{unit_id}")
async def units_update(
    request: Request,
    unit_id: str,
    code: str = Form(...),
    name: str = Form(...),
    symbol: Optional[str] = Form(None),
):
    """Обновить единицу измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        try:
            unit_uuid = uuid.UUID(unit_id)
        except ValueError:
            return RedirectResponse(url="/dictionaries/units", status_code=302)
        
        result = await db.execute(
            select(UnitOfMeasure).where(UnitOfMeasure.id == unit_uuid)
        )
        unit = result.scalar_one_or_none()
        if not unit:
            return RedirectResponse(url="/dictionaries/units", status_code=302)
        
        # Проверяем уникальность кода (исключая текущую запись)
        result = await db.execute(
            select(UnitOfMeasure).where(
                UnitOfMeasure.code == code,
                UnitOfMeasure.id != unit_uuid
            )
        )
        if result.scalar_one_or_none():
            return await units_edit_page(
                request,
                unit_id,
                error=f"Единица измерения с кодом '{code}' уже существует"
            )
        
        unit.code = code
        unit.name = name
        unit.symbol = symbol
        await db.commit()
        
        return RedirectResponse(url="/dictionaries/units", status_code=302)

@router.post("/{unit_id}/delete")
async def units_delete(request: Request, unit_id: str):
    """Удалить единицу измерения"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        try:
            unit_uuid = uuid.UUID(unit_id)
        except ValueError:
            return RedirectResponse(url="/dictionaries/units", status_code=302)
        
        result = await db.execute(
            select(UnitOfMeasure).where(UnitOfMeasure.id == unit_uuid)
        )
        unit = result.scalar_one_or_none()
        if unit:
            await db.delete(unit)
            await db.commit()
        
        return RedirectResponse(url="/dictionaries/units", status_code=302)
