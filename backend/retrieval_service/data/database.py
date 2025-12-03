"""
Database operations for Supabase.

This module provides all database operations for the Memory Retrieval Service,
including user management, email/schedule/file storage, and embedding management.
All operations use the Supabase client with proper error handling and logging.
"""

import os
import time
from functools import wraps
from supabase import create_client, Client
from dotenv import load_dotenv
from ..infrastructure.logging import log_debug, log_info, log_warning, log_error

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ======================================================
# Retry Decorator for Database Operations
# ======================================================

def retry_on_disconnect(max_retries=3, backoff_factor=2):
    """
    Decorator to retry database operations on connection errors.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = any(keyword in error_str for keyword in [
                        'server disconnected', 'connection', 'timeout',
                        'temporarily unavailable', '503', '504', '429'
                    ])
                    
                    if attempt < max_retries - 1 and is_retryable:
                        wait_time = backoff_factor * (2 ** attempt)
                        log_warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        # Last attempt or non-retryable error
                        log_error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
            return None
        return wrapper
    return decorator


# ======================================================
# User Management
# ======================================================

@retry_on_disconnect(max_retries=3, backoff_factor=2)
def get_user_by_email(email: str):
    """Get user by email with automatic retry on connection errors"""
    response = supabase.table("users").select("*").eq("email", email).execute()
    return response.data[0] if response.data else None


@retry_on_disconnect(max_retries=3, backoff_factor=2)
def create_user(email: str, name: str = None):
    """Create a new user with pending status, with automatic retry on connection errors"""
    response = supabase.table("users").insert({
        "email": email,
        "name": name,
        "status": "pending",
        "init_phase": "not_started",
        "init_progress": 0
    }).execute()
    return response.data[0] if response.data else None


@retry_on_disconnect(max_retries=3, backoff_factor=2)
def update_user_status(user_id: str, status: str, init_phase: str = None, init_progress: int = None):
    """Update user initialization status with automatic retry on connection errors"""
    update_data = {"status": status}
    if init_phase is not None:
        update_data["init_phase"] = init_phase
    if init_progress is not None:
        update_data["init_progress"] = init_progress
    
    response = supabase.table("users").update(update_data).eq("uuid", user_id).execute()
    return response.data[0] if response.data else None


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
        log_error(f"Error inserting emails: {e}")
        return []


def get_emails_by_thread(user_id: str, thread_id: str, max_retries: int = 3):
    """Get all emails in a thread with retry logic"""
    import time
    
    for attempt in range(max_retries):
        try:
            response = supabase.table("emails").select("*").eq("user_id", user_id).eq("thread_id", thread_id).order("date").execute()
            return response.data
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 0.5s, 1s, 2s
                wait_time = 0.5 * (2 ** attempt)
                log_warning(f"Error getting emails by thread (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                log_error(f"Error getting emails by thread after {max_retries} attempts: {e}")
                return []
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
        log_error(f"Error inserting schedules: {e}")
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
                "summary": None,  # Will be filled during processing
                "metadata": file.get("metadata")  # Store rich metadata from Google Drive API
            })
        
        # Batch insert with upsert
        response = supabase.table("files").upsert(records).execute()
        return response.data
    except Exception as e:
        log_error(f"Error inserting files: {e}")
        return []


def update_file_summary(user_id: str, file_id: str, summary: str):
    """Update file summary after processing"""
    try:
        response = supabase.table("files").update({"summary": summary}).eq("user_id", user_id).eq("id", file_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_error(f"Error updating file summary: {e}")
        return None


# ======================================================
# Attachment Management
# ======================================================

def insert_attachments(user_id: str, attachments: list):
    """Batch insert attachments for a user"""
    try:
        if not attachments:
            return []
        
        # Prepare attachment records
        records = []
        for attachment in attachments:
            records.append({
                "id": attachment["id"],
                "user_id": user_id,
                "email_id": attachment["email_id"],
                "filename": attachment.get("filename"),
                "mime_type": attachment.get("mime_type"),
                "size": attachment.get("size"),
                "summary": None  # Will be filled during processing
            })
        
        # Batch insert with upsert
        response = supabase.table("attachments").upsert(records).execute()
        return response.data
    except Exception as e:
        log_error(f"Error inserting attachments: {e}")
        return []


def update_attachment_summary(user_id: str, attachment_id: str, summary: str):
    """Update attachment summary after processing"""
    try:
        response = supabase.table("attachments").update({"summary": summary}).eq("user_id", user_id).eq("id", attachment_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_error(f"Error updating attachment summary: {e}")
        return None


@retry_on_disconnect(max_retries=3, backoff_factor=2)
def get_attachments_by_email(user_id: str, email_id: str):
    """Get all attachments for an email with automatic retry on connection errors"""
    response = supabase.table("attachments").select("*").eq("user_id", user_id).eq("email_id", email_id).execute()
    return response.data if response.data else []


# ======================================================
# Embedding Management
# ======================================================

def insert_embedding(user_id: str, embedding_id: str, embedding_type: str, vector: list, 
                     email_id: str = None, schedule_id: str = None, file_id: str = None, attachment_id: str = None):
    """Insert a single embedding"""
    try:
        record = {
            "id": embedding_id,
            "user_id": user_id,
            "type": embedding_type,
            "vector": vector,
            "email_id": email_id,
            "schedule_id": schedule_id,
            "file_id": file_id,
            "attachment_id": attachment_id
        }
        
        response = supabase.table("embeddings").upsert(record).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_error(f"Error inserting embedding: {e}")
        return None


def batch_insert_embeddings(embeddings: list):
    """Batch insert embeddings"""
    try:
        if not embeddings:
            return []
        
        response = supabase.table("embeddings").upsert(embeddings).execute()
        return response.data
    except Exception as e:
        log_error(f"Error batch inserting embeddings: {e}")
        return []

def delete_user_and_all_data(user_id: str):
    """Delete user and all associated data in the correct order."""
    try:
        # 1. Delete embeddings
        supabase.table("embeddings").delete().eq("user_id", user_id).execute()

        # 2. Delete attachments
        supabase.table("attachments").delete().eq("user_id", user_id).execute()

        # 3. Delete emails
        supabase.table("emails").delete().eq("user_id", user_id).execute()

        # 4. Delete schedules
        supabase.table("schedules").delete().eq("user_id", user_id).execute()

        # 5. Delete files
        supabase.table("files").delete().eq("user_id", user_id).execute()

        # 6. Finally delete user itself
        supabase.table("users").delete().eq("uuid", user_id).execute()

        log_info(f"Successfully deleted user {user_id} and all related data.")
        return True

    except Exception as e:
        log_error(f"Error deleting user and related data: {e}")
        return False
