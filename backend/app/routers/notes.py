from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import NoteCreate, NoteResponse
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from typing import List

router = APIRouter()

@router.get("/{company_id}", response_model=List[NoteResponse])
async def get_notes(company_id: str, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    result = supabase.table("notes")\
        .select("*")\
        .eq("company_id", company_id)\
        .eq("user_id", user_id)\
        .order("updated_at", desc=True)\
        .execute()
    return result.data or []

@router.post("/", response_model=NoteResponse)
async def save_note(note: NoteCreate, user_id: str = Depends(get_current_user_id)):
    import datetime
    supabase = get_supabase()
    data = note.dict()
    data["user_id"] = user_id
    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    note_id = data.pop("id", None)
    if note_id:
        result = supabase.table("notes").update(data).eq("id", note_id).eq("user_id", user_id).execute()
    else:
        result = supabase.table("notes").insert(data).execute()
        
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save note")
    return result.data[0]
