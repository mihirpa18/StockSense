from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import JournalCreate, JournalResponse
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from typing import List

router = APIRouter()

@router.post("/", response_model=JournalResponse)
async def create_entry(entry: JournalCreate, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    data = entry.dict()
    data["user_id"] = user_id   # set server-side, never trusted from the client
    if "purchase_date" in data and not isinstance(data["purchase_date"], str):
        data["purchase_date"] = data["purchase_date"].isoformat()
    result = supabase.table("journal_entries").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save journal entry")
    return result.data[0]

@router.get("/", response_model=List[JournalResponse])
async def get_entries(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    result = supabase.table("journal_entries")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("purchase_date", desc=True)\
        .execute()
    return result.data or []
