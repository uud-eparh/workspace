from fastapi import APIRouter
router = APIRouter(prefix="/cities", tags=["Cities"])

@router.get("/")
async def cities_list():
    return {"message": "Cities list"}
