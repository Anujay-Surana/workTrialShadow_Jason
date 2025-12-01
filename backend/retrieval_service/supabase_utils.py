import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ======================================================
# User Management
# ======================================================

def get_user_by_email(email: str):
    """Get user by email"""
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None


def create_user(email: str, name: str = None):
    """Create a new user with pending status"""
    try:
        response = supabase.table("users").insert({
            "email": email,
            "name": name,
            "status": "pending",
            "init_phase": "not_started",
            "init_progress": 0
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating user: {e}")
        return None


def update_user_status(user_id: str, status: str, init_phase: str = None, init_progress: int = None):
    """Update user initialization status"""
    try:
        update_data = {"status": status}
        if init_phase is not None:
            update_data["init_phase"] = init_phase
        if init_progress is not None:
            update_data["init_progress"] = init_progress
        
        response = supabase.table("users").update(update_data).eq("uuid", user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating user status: {e}")
        return None


# ======================================================
# Email Management
# ======================================================

def insert_emails(user_id: str, emails: list):
    """Batch insert emails for a user"""
    try:
        if not emails:
            return []
        
        # Prepare email records
        records = []
        for email in emails:
            records.append({
                "id": email["id"],
                "user_id": user_id,
                "thread_id": email.get("thread_id"),
                "body": email.get("snippet", ""),
                "subject": email.get("subject"),
                "from_user": email.get("from"),
                "to_user": email.get("to"),
                "cc": email.get("cc"),
                "bcc": email.get("bcc"),
                "date": email.get("date")
            })
        
        # Batch insert with upsert
        response = supabase.table("emails").upsert(records).execute()
        return response.data
    except Exception as e:
        print(f"Error inserting emails: {e}")
        return []


def get_emails_by_thread(user_id: str, thread_id: str):
    """Get all emails in a thread"""
    try:
        response = supabase.table("emails").select("*").eq("user_id", user_id).eq("thread_id", thread_id).order("date").execute()
        return response.data
    except Exception as e:
        print(f"Error getting emails by thread: {e}")
        return []


# ======================================================
# Schedule Management
# ======================================================

def insert_schedules(user_id: str, schedules: list):
    """Batch insert schedules for a user"""
    try:
        if not schedules:
            return []
        
        # Prepare schedule records
        records = []
        for schedule in schedules:
            # Parse start and end times
            start = schedule.get("start", {})
            end = schedule.get("end", {})
            start_time = start.get("dateTime") or start.get("date")
            end_time = end.get("dateTime") or end.get("date")
            
            records.append({
                "id": schedule["id"],
                "user_id": user_id,
                "summary": schedule.get("summary"),
                "description": schedule.get("description"),
                "location": schedule.get("location"),
                "start_time": start_time,
                "end_time": end_time,
                "creator_email": schedule.get("creator_email"),
                "organizer_email": schedule.get("organizer_email"),
                "html_link": schedule.get("html_link"),
                "updated": schedule.get("updated")
            })
        
        # Batch insert with upsert
        response = supabase.table("schedules").upsert(records).execute()
        return response.data
    except Exception as e:
        print(f"Error inserting schedules: {e}")
        return []


# ======================================================
# File Management
# ======================================================

def insert_files(user_id: str, files: list):
    """Batch insert files for a user"""
    try:
        if not files:
            return []
        
        # Prepare file records
        records = []
        for file in files:
            records.append({
                "id": file["id"],
                "user_id": user_id,
                "owner_email": file.get("owner_email"),
                "owner_name": file.get("owner_name"),
                "path": file.get("path"),
                "name": file.get("name"),
                "mime_type": file.get("mime_type"),
                "size": file.get("size"),
                "modified_time": file.get("modified_time"),
                "parents": file.get("parents", []),
                "summary": None  # Will be filled during processing
            })
        
        # Batch insert with upsert
        response = supabase.table("files").upsert(records).execute()
        return response.data
    except Exception as e:
        print(f"Error inserting files: {e}")
        return []


def update_file_summary(user_id: str, file_id: str, summary: str):
    """Update file summary after processing"""
    try:
        response = supabase.table("files").update({"summary": summary}).eq("user_id", user_id).eq("id", file_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating file summary: {e}")
        return None


# ======================================================
# Embedding Management
# ======================================================

def insert_embedding(user_id: str, embedding_id: str, embedding_type: str, vector: list, 
                     email_id: str = None, schedule_id: str = None, file_id: str = None):
    """Insert a single embedding"""
    try:
        record = {
            "id": embedding_id,
            "user_id": user_id,
            "type": embedding_type,
            "vector": vector,
            "email_id": email_id,
            "schedule_id": schedule_id,
            "file_id": file_id
        }
        
        response = supabase.table("embeddings").upsert(record).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error inserting embedding: {e}")
        return None


def batch_insert_embeddings(embeddings: list):
    """Batch insert embeddings"""
    try:
        if not embeddings:
            return []
        
        response = supabase.table("embeddings").upsert(embeddings).execute()
        return response.data
    except Exception as e:
        print(f"Error batch inserting embeddings: {e}")
        return []
