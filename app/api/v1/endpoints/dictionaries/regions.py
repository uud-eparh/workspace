from fastapi import APIRouter
router = APIRouter(prefix="/regions", tags=["Regions"])

@router.get("/")
async def regions_list():
    return {"message": "Regions list"}
