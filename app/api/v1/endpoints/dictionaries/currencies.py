from fastapi import APIRouter
router = APIRouter(prefix="/currencies", tags=["Currencies"])

@router.get("/")
async def currencies_list():
    return {"message": "Currencies list"}
