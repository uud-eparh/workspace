from fastapi import APIRouter, Request, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, and_, or_, func, String, cast
from sqlalchemy.dialects.postgresql import TEXT
from app.core.database import AsyncSessionLocal
from app.core.auth import get_current_user
from app.models import CommonDictionary
from typing import Optional
import uuid
import csv
from io import StringIO
import hashlib
import time
import logging

router = APIRouter(prefix="/dictionaries", tags=["Dictionaries"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

# Временное хранилище для файлов
temp_files = {}

# ===== Вспомогательные функции =====

def get_dictionary_type(type_name: str) -> dict:
    """Возвращает информацию о типе справочника"""
    types = {
        "units": {
            "name": "Единицы измерения",
            "icon": "📏",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
                {"name": "symbol", "label": "Символ", "required": False},
            ]
        },
        "currencies": {
            "name": "Валюты",
            "icon": "💱",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
                {"name": "symbol", "label": "Символ", "required": False},
            ]
        },
        "countries": {
            "name": "Страны",
            "icon": "🌍",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
            ]
        },
        "regions": {
            "name": "Регионы",
            "icon": "🗺️",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
            ]
        },
        "cities": {
            "name": "Города",
            "icon": "🏙️",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
            ]
        },
        "counterparties": {
            "name": "Контрагенты",
            "icon": "🏢",
            "fields": [
                {"name": "code", "label": "Код", "required": True},
                {"name": "name", "label": "Название", "required": True},
                {"name": "inn", "label": "ИНН", "required": False},
            ]
        }
    }
    return types.get(type_name)

def normalize_search_query(search: str) -> str:
    """Нормализует поисковый запрос: убирает лишние пробелы и приводит к нижнему регистру"""
    if not search:
        return ""
    return " ".join(search.split()).lower()

# ===== Главная страница справочников =====

@router.get("/", response_class=HTMLResponse)
async def dictionaries_list(request: Request):
    """Главная страница справочников"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries.html",
            {
                "request": request,
                "user": user,
                "version": "0.1.0",
            }
        )

# ===== Универсальные эндпоинты для справочников =====

@router.get("/{type_name}", response_class=HTMLResponse)
async def dictionary_list(
    request: Request,
    type_name: str,
    search: Optional[str] = Query(None, description="Поиск по всем текстовым полям"),
    sort_by: Optional[str] = Query("code", description="Поле для сортировки"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки (asc/desc)"),
    page: Optional[int] = Query(1, description="Номер страницы"),
    per_page: Optional[int] = Query(20, description="Количество записей на странице"),
):
    """Список записей справочника с поиском, сортировкой и пагинацией"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        # Базовый запрос
        query = select(CommonDictionary).where(CommonDictionary.type == type_name)
        
        # Поиск (регистронезависимый через lower())
        if search:
            normalized_search = normalize_search_query(search)
            if normalized_search:
                # Приводим и поле, и поисковый запрос к нижнему регистру
                search_filter = or_(
                    func.lower(CommonDictionary.code).contains(normalized_search),
                    func.lower(CommonDictionary.name).contains(normalized_search),
                    func.lower(CommonDictionary.symbol).contains(normalized_search)
                )
                query = query.where(search_filter)
        
        # Подсчет общего количества
        count_query = select(func.count()).select_from(CommonDictionary).where(CommonDictionary.type == type_name)
        if search and normalized_search:
            count_query = count_query.where(search_filter)
        total = await db.scalar(count_query)
        
        # Сортировка
        sort_field = getattr(CommonDictionary, sort_by, CommonDictionary.code)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        # Пагинация
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        # Вычисляем количество страниц
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return templates.TemplateResponse(
            "dictionaries/list.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "items": items,
                "search": search,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
                "version": "0.1.0",
            }
        )

@router.get("/{type_name}/create", response_class=HTMLResponse)
async def dictionary_create_page(request: Request, type_name: str, error: Optional[str] = None):
    """Страница создания записи"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/form.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "item": None,
                "error": error,
                "is_edit": False,
                "version": "0.1.0",
            }
        )

@router.get("/{type_name}/{item_id}/edit", response_class=HTMLResponse)
async def dictionary_edit_page(request: Request, type_name: str, item_id: str, error: Optional[str] = None):
    """Страница редактирования записи"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        try:
            item_uuid = uuid.UUID(item_id)
        except ValueError:
            return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)
        
        result = await db.execute(
            select(CommonDictionary).where(
                CommonDictionary.id == item_uuid,
                CommonDictionary.type == type_name
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/form.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "item": item,
                "error": error,
                "is_edit": True,
                "version": "0.1.0",
            }
        )

# ===== API эндпоинты =====

@router.post("/{type_name}")
async def dictionary_create(
    request: Request,
    type_name: str,
    code: str = Form(...),
    name: str = Form(...),
    symbol: Optional[str] = Form(None),
):
    """Создать запись в справочнике"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        # Проверяем уникальность кода
        result = await db.execute(
            select(CommonDictionary).where(
                CommonDictionary.type == type_name,
                CommonDictionary.code == code
            )
        )
        if result.scalar_one_or_none():
            return await dictionary_create_page(
                request,
                type_name,
                error=f"Запись с кодом '{code}' уже существует"
            )
        
        item = CommonDictionary(
            type=type_name,
            code=code,
            name=name,
            symbol=symbol
        )
        db.add(item)
        await db.commit()
        
        return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)

@router.post("/{type_name}/{item_id}")
async def dictionary_update(
    request: Request,
    type_name: str,
    item_id: str,
    code: str = Form(...),
    name: str = Form(...),
    symbol: Optional[str] = Form(None),
):
    """Обновить запись в справочнике"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        try:
            item_uuid = uuid.UUID(item_id)
        except ValueError:
            return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)
        
        result = await db.execute(
            select(CommonDictionary).where(
                CommonDictionary.id == item_uuid,
                CommonDictionary.type == type_name
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)
        
        # Проверяем уникальность кода (исключая текущую запись)
        result = await db.execute(
            select(CommonDictionary).where(
                CommonDictionary.type == type_name,
                CommonDictionary.code == code,
                CommonDictionary.id != item_uuid
            )
        )
        if result.scalar_one_or_none():
            return await dictionary_edit_page(
                request,
                type_name,
                item_id,
                error=f"Запись с кодом '{code}' уже существует"
            )
        
        item.code = code
        item.name = name
        item.symbol = symbol
        await db.commit()
        
        return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)

@router.post("/{type_name}/{item_id}/delete")
async def dictionary_delete(request: Request, type_name: str, item_id: str):
    """Удалить запись из справочника"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        try:
            item_uuid = uuid.UUID(item_id)
        except ValueError:
            return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)
        
        result = await db.execute(
            select(CommonDictionary).where(
                CommonDictionary.id == item_uuid,
                CommonDictionary.type == type_name
            )
        )
        item = result.scalar_one_or_none()
        if item:
            await db.delete(item)
            await db.commit()
        
        return RedirectResponse(url=f"/dictionaries/{type_name}", status_code=302)

# ===== Импорт из CSV =====

@router.get("/{type_name}/import", response_class=HTMLResponse)
async def dictionary_import_page(request: Request, type_name: str, error: Optional[str] = None):
    """Страница импорта CSV"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        return templates.TemplateResponse(
            "dictionaries/import.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "error": error,
                "version": "0.1.0",
            }
        )

@router.post("/{type_name}/import/preview")
async def dictionary_import_preview(
    request: Request,
    type_name: str,
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
):
    """Предпросмотр CSV-файла"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        content = await file.read()
        try:
            decoded = content.decode(encoding)
        except UnicodeDecodeError:
            return await dictionary_import_page(
                request,
                type_name,
                error=f"Не удалось декодировать файл с кодировкой {encoding}."
            )
        
        file_id = hashlib.md5(f"{user.id}{time.time()}".encode()).hexdigest()
        temp_files[file_id] = {
            "content": decoded,
            "filename": file.filename,
            "delimiter": delimiter,
            "encoding": encoding,
            "type": type_name,
            "created_at": time.time()
        }
        
        reader = csv.DictReader(StringIO(decoded), delimiter=delimiter)
        
        columns = reader.fieldnames if reader.fieldnames else []
        preview_data = []
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_data.append(row)
        
        if not preview_data:
            return await dictionary_import_page(
                request,
                type_name,
                error="Файл пуст или не содержит данных."
            )
        
        return templates.TemplateResponse(
            "dictionaries/import.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "columns": columns,
                "preview": preview_data,
                "filename": file.filename,
                "file_id": file_id,
                "delimiter": delimiter,
                "encoding": encoding,
                "version": "0.1.0",
            }
        )

@router.post("/{type_name}/import/execute")
async def dictionary_import_execute(
    request: Request,
    type_name: str,
    file_id: str = Form(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    mapping_code: Optional[str] = Form(None),
    mapping_name: Optional[str] = Form(None),
    mapping_symbol: Optional[str] = Form(None),
    skip_duplicates: bool = Form(True),
):
    """Выполнить импорт CSV"""
    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        dict_type = get_dictionary_type(type_name)
        if not dict_type:
            return RedirectResponse(url="/dictionaries", status_code=302)
        
        if not mapping_code or not mapping_name:
            return await dictionary_import_page(
                request,
                type_name,
                error="Необходимо указать соответствие для полей 'Код' и 'Название'."
            )
        
        if file_id not in temp_files:
            return await dictionary_import_page(
                request,
                type_name,
                error="Файл не найден. Попробуйте загрузить его снова."
            )
        
        file_data = temp_files[file_id]
        decoded = file_data["content"]
        
        reader = csv.DictReader(StringIO(decoded), delimiter=delimiter)
        
        imported = 0
        updated = 0
        skipped = 0
        
        for row in reader:
            code = row.get(mapping_code, "").strip()
            name = row.get(mapping_name, "").strip()
            symbol = row.get(mapping_symbol, "").strip() if mapping_symbol else ""
            
            if not code or not name:
                skipped += 1
                continue
            
            result = await db.execute(
                select(CommonDictionary).where(
                    CommonDictionary.type == type_name,
                    CommonDictionary.code == code
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                if skip_duplicates:
                    skipped += 1
                    continue
                else:
                    existing.name = name
                    if symbol:
                        existing.symbol = symbol
                    updated += 1
            else:
                item = CommonDictionary(
                    type=type_name,
                    code=code,
                    name=name,
                    symbol=symbol or None
                )
                db.add(item)
                imported += 1
        
        await db.commit()
        del temp_files[file_id]
        
        return templates.TemplateResponse(
            "dictionaries/import.html",
            {
                "request": request,
                "user": user,
                "type_name": type_name,
                "dict_type": dict_type,
                "import_result": {
                    "imported": imported,
                    "updated": updated,
                    "skipped": skipped,
                },
                "version": "0.1.0",
            }
        )
