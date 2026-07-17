from fastapi import APIRouter
router = APIRouter(prefix="/countries", tags=["Countries"])

@router.get("/")
async def countries_list():
    return {"message": "Countries list"}
