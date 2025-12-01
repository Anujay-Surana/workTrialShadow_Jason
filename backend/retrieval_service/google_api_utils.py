import time
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from email.utils import parsedate_to_datetime
from retrieval_service.openai_api_utils import summarize_doc
from retrieval_service.supabase_utils import (
    get_emails_by_thread,
    insert_embedding,
    batch_insert_embeddings,
    update_file_summary,
    update_user_status
)
from retrieval_service.gemni_api_utils import embed_text

from retrieval_service.ocr_utils import extractOCR, isIMG
from retrieval_service.doc_utils import extractDOC, isDOC


# ======================================================
# Gmail: Fetch last 90 days emails (full pagination)
# ======================================================

async def fetch_gmail_messages(credentials, query="category:primary newer_than:90d", sleep_time=0.5, max_per_page=500):
    service = build("gmail", "v1", credentials=credentials)
    all_emails = []
    next_page_token = None

    while True:
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_per_page,
            pageToken=next_page_token
        ).execute()

        refs = response.get("messages", [])

        for ref in refs:
            msg = service.users().messages().get(
                userId="me",
                id=ref["id"]
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            def get_header(name):
                return next((h["value"] for h in headers if h["name"] == name), "")

            # Parse Gmail Date safely
            raw_date = get_header("Date")
            try:
                dt = parsedate_to_datetime(raw_date)
                iso_date = dt.isoformat()
            except Exception:
                iso_date = None

            all_emails.append({
                "id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "snippet": msg.get("snippet", ""),
                "subject": get_header("Subject"),
                "from": get_header("From"),
                "to": get_header("To"),
                "cc": get_header("Cc"),
                "bcc": get_header("Bcc"),
                "date": iso_date,  # <-- FIXED
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

        time.sleep(sleep_time)

    return all_emails


# ======================================================
# Calendar: Fetch ALL future events (max 2500)
# ======================================================

def fetch_calendar_events(credentials, max_results=2500):
    service = build("calendar", "v3", credentials=credentials)

    from datetime import datetime
    now = datetime.utcnow().isoformat() + "Z"

    resp = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    items = resp.get("items", [])

    events = []
    for e in items:
        events.append({
            "id": e.get("id"),
            "summary": e.get("summary"),
            "description": e.get("description"),
            "location": e.get("location"),
            "start": e.get("start"),
            "end": e.get("end"),

            # new metadata
            "creator_email": e.get("creator", {}).get("email"),
            "organizer_email": e.get("organizer", {}).get("email"),
            "html_link": e.get("htmlLink"),
            "updated": e.get("updated"),
        })

    return events


# ======================================================
# Drive: BFS recursive traversal (+path +parents)
# ======================================================

def list_folder_children(service, folder_id):
    result = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType, size, modifiedTime, parents, owners(displayName, emailAddress))"
    ).execute()
    return result.get("files", [])


def fetch_drive_all_files(credentials):
    """
    Recursively traverse all Google Drive files (BFS).
    Returns:
    {
        id, name, mime_type, size, modified_time, path, parents
    }
    """
    service = build("drive", "v3", credentials=credentials)

    root_id = "root"
    queue = [(root_id, "/")]
    results = []

    while queue:
        parent_id, parent_path = queue.pop(0)
        children = list_folder_children(service, parent_id)

        for f in children:
            name = f["name"]
            mime_type = f.get("mimeType", "")
            is_folder = mime_type == "application/vnd.google-apps.folder"

            # Build path
            current_path = (
                parent_path.rstrip("/") + "/" + name
                if parent_path != "/"
                else "/" + name
            )
            
            # Extract owner information
            owners = f.get("owners", [])
            owner_emails = ", ".join([o.get("emailAddress", "") for o in owners if o.get("emailAddress")])
            owner_names = ", ".join([o.get("displayName", "") for o in owners if o.get("displayName")])

            results.append({
                "id": f["id"],
                "name": name,
                "mime_type": mime_type,
                "size": f.get("size"),
                "modified_time": f.get("modifiedTime"),
                "path": current_path,
                "parents": f.get("parents", []),
                "owner_email": owner_emails,
                "owner_name": owner_names,
            })

            if is_folder:
                queue.append((f["id"], current_path))

        time.sleep(0.2)

    return results


# ======================================================
# File Processing and Download
# ======================================================

def download_file_content(credentials, file_id):
    """Download file content from Google Drive"""
    try:
        service = build("drive", "v3", credentials=credentials)
        request = service.files().get_media(fileId=file_id)
        
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_content.seek(0)
        return file_content.read()
    except Exception as e:
        print(f"Error downloading file {file_id}: {e}")
        return None


def process_file_by_type(file_name: str, file_content: bytes) -> str:
    """
    Placeholder function to process file content and return summary.
    Will be implemented later with actual file processing logic.
    
    Args:
        file_name: Name of the file
        file_content: Raw bytes content of the file
    
    Returns:
        str: Summary of the file content
    """
    if isIMG(file_name):
        try:
            text = extractOCR(file_content)
            return "A image with following extracted text:" + text if text else "A image file with no extractable text."
        except Exception as e:
            return "A image file with no extractable text."
    if isDOC(file_name):
        try:
            text = extractDOC(file_content, filename=file_name)
            return summarize_doc(text, filename=file_name)
        except Exception as e:
            return "A document file with no extractable text."
    return "A file of unsupported type for extraction named `" + file_name + "`."
    


# ======================================================
# Embedding Functions
# ======================================================

def create_email_embeddings(user_id: str, emails: list, start_progress: int, end_progress: int):
    """
    Create embeddings for emails (3 types: email_sum, email_context, email_title)
    Updates progress granularly as each email is processed.
    
    Args:
        user_id: User UUID
        emails: List of email dictionaries
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    if not emails:
        return
    
    total_emails = len(emails)
    progress_range = end_progress - start_progress
    embeddings_to_insert = []
    last_update_progress = start_progress
    
    for idx, email in enumerate(emails):
        email_id = email["id"]
        
        # 1. email_sum: Full email information
        email_sum_text = (
            f"An email from {email.get('from_user', 'unknown')} "
            f"to {email.get('to_user', 'unknown')} "
            f"at {email.get('date', 'unknown date')}. "
            f"Subject: {email.get('subject', 'No subject')}. "
            f"Content: {email.get('body', '')}"
        )
        try:
            email_sum_vector = embed_text(email_sum_text)
            embeddings_to_insert.append({
                "id": f"{email_id}_sum",
                "user_id": user_id,
                "type": "email_sum",
                "vector": email_sum_vector,
                "email_id": email_id,
                "schedule_id": None,
                "file_id": None
            })
        except Exception as e:
            print(f"Error embedding email_sum for {email_id}: {e}")
        
        # 2. email_context: Full thread context
        thread_id = email.get("thread_id")
        if thread_id:
            try:
                thread_emails = get_emails_by_thread(user_id, thread_id)
                thread_text = "Email thread:\n"
                for t_email in thread_emails:
                    thread_text += (
                        f"From {t_email.get('from_user', 'unknown')} "
                        f"at {t_email.get('date', 'unknown')}: "
                        f"{t_email.get('subject', 'No subject')} - "
                        f"{t_email.get('body', '')}\n"
                    )
                
                email_context_vector = embed_text(thread_text)
                embeddings_to_insert.append({
                    "id": f"{email_id}_context",
                    "user_id": user_id,
                    "type": "email_context",
                    "vector": email_context_vector,
                    "email_id": email_id,
                    "schedule_id": None,
                    "file_id": None
                })
            except Exception as e:
                print(f"Error embedding email_context for {email_id}: {e}")
        
        # 3. email_title: Subject and sender/receiver info
        email_title_text = (
            f"An Email with subject: {email.get('subject', 'No subject')}. "
            f"From: {email.get('from_user', 'unknown')}. "
            f"To: {email.get('to_user', 'unknown')}."
            f"CC: {email.get('cc', 'none')}."
            f"BCC: {email.get('bcc', 'none')}."
        )
        try:
            email_title_vector = embed_text(email_title_text)
            embeddings_to_insert.append({
                "id": f"{email_id}_title",
                "user_id": user_id,
                "type": "email_title",
                "vector": email_title_vector,
                "email_id": email_id,
                "schedule_id": None,
                "file_id": None
            })
        except Exception as e:
            print(f"Error embedding email_title for {email_id}: {e}")
        
        # Update progress if at least 1% increase
        current_progress = start_progress + int((idx + 1) / total_emails * progress_range)
        if current_progress - last_update_progress >= 1:
            update_user_status(user_id, "processing", "embedding_emails", current_progress)
            last_update_progress = current_progress
    
    # Batch insert all embeddings
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


def create_schedule_embeddings(user_id: str, schedules: list, start_progress: int, end_progress: int):
    """
    Create embeddings for schedules
    Updates progress granularly as each schedule is processed.
    
    Args:
        user_id: User UUID
        schedules: List of schedule dictionaries from database
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    if not schedules:
        return
    
    total_schedules = len(schedules)
    progress_range = end_progress - start_progress
    embeddings_to_insert = []
    last_update_progress = start_progress
    
    for idx, schedule in enumerate(schedules):
        schedule_id = schedule["id"]
        
        # schedule_context: Full schedule information
        schedule_text = (
            f"A calendar schedule:"
            f"Calendar event: {schedule.get('summary', 'No title')}. "
            f"Description: {schedule.get('description', 'No description')}. "
            f"Location: {schedule.get('location', 'No location')}. "
            f"Start time: {schedule.get('start_time', 'unknown')}. "
            f"End time: {schedule.get('end_time', 'unknown')}. "
            f"Organizer: {schedule.get('organizer_email', 'unknown')}."
        )
        
        try:
            schedule_vector = embed_text(schedule_text)
            embeddings_to_insert.append({
                "id": f"{schedule_id}_context",
                "user_id": user_id,
                "type": "schedule_context",
                "vector": schedule_vector,
                "email_id": None,
                "schedule_id": schedule_id,
                "file_id": None
            })
        except Exception as e:
            print(f"Error embedding schedule {schedule_id}: {e}")
        
        # Update progress if at least 1% increase
        current_progress = start_progress + int((idx + 1) / total_schedules * progress_range)
        if current_progress - last_update_progress >= 1:
            update_user_status(user_id, "processing", "embedding_schedules", current_progress)
            last_update_progress = current_progress
    
    # Batch insert all embeddings
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


def create_file_embeddings(user_id: str, files: list, credentials, start_progress: int, end_progress: int):
    """
    Create embeddings for files (with file processing)
    Updates progress granularly as each file is processed.
    
    Args:
        user_id: User UUID
        files: List of file dictionaries from database
        credentials: Google credentials for downloading files
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    if not files:
        return
    
    total_files = len(files)
    progress_range = end_progress - start_progress
    embeddings_to_insert = []
    last_update_progress = start_progress
    
    for idx, file in enumerate(files):
        file_id = file["id"]
        file_name = file.get("name", "unknown")
        
        # Download and process file
        try:
            file_content = download_file_content(credentials, file_id)
            if file_content:
                # Process file to get summary
                summary = process_file_by_type(file_name, file_content)
                
                # Update file summary in database
                update_file_summary(user_id, file_id, summary)
                
                # Create embedding with file metadata and summary
                file_text = (
                    f"User has the following file in Google Drive:"
                    f"File: {file_name}. "
                    f"Type: {file.get('mime_type', 'unknown')}. "
                    f"Path: {file.get('path', 'unknown')}. "
                    f"Modified: {file.get('modified_time', 'unknown')}. "
                    f"File Summary: {summary}"
                )
                
                file_vector = embed_text(file_text)
                embeddings_to_insert.append({
                    "id": f"{file_id}_context",
                    "user_id": user_id,
                    "type": "file_context",
                    "vector": file_vector,
                    "email_id": None,
                    "schedule_id": None,
                    "file_id": file_id
                })
        except Exception as e:
            print(f"Error processing/embedding file {file_id}: {e}")
        
        # Update progress if at least 1% increase
        current_progress = start_progress + int((idx + 1) / total_files * progress_range)
        if current_progress - last_update_progress >= 1:
            update_user_status(user_id, "processing", "embedding_files", current_progress)
            last_update_progress = current_progress
    
    # Batch insert all embeddings
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


# ======================================================
# Main Initialization Function
# ======================================================

async def initialize_user_data(user_id: str, credentials, progress_callback=None):
    """
    Initialize user data: fetch emails, schedules, files, and create embeddings.
    
    Args:
        user_id: User UUID
        credentials: Google OAuth credentials
        progress_callback: Optional callback function to update progress
    
    Returns:
        dict: Summary of initialization results
    """
    from retrieval_service.supabase_utils import insert_emails, insert_schedules, insert_files
    
    results = {
        "emails_count": 0,
        "schedules_count": 0,
        "files_count": 0,
        "error": None
    }
    
    try:
        # Update status to processing
        update_user_status(user_id, "processing", "starting", 0)
        if progress_callback:
            progress_callback("starting", 0)
        
        # Step 1: Fetch and insert emails (33% progress)
        update_user_status(user_id, "processing", "fetching_emails", 10)
        if progress_callback:
            progress_callback("fetching_emails", 10)
        
        emails = await fetch_gmail_messages(credentials)
        inserted_emails = insert_emails(user_id, emails)
        results["emails_count"] = len(inserted_emails)
        
        update_user_status(user_id, "processing", "emails_fetched", 20)
        if progress_callback:
            progress_callback("emails_fetched", 20)
        
        # Step 2: Fetch and insert schedules (33% progress)
        update_user_status(user_id, "processing", "fetching_schedules", 30)
        if progress_callback:
            progress_callback("fetching_schedules", 30)
        
        schedules = fetch_calendar_events(credentials)
        inserted_schedules = insert_schedules(user_id, schedules)
        results["schedules_count"] = len(inserted_schedules)
        
        update_user_status(user_id, "processing", "schedules_fetched", 40)
        if progress_callback:
            progress_callback("schedules_fetched", 40)
        
        # Step 3: Fetch and insert files (34% progress)
        update_user_status(user_id, "processing", "fetching_files", 50)
        if progress_callback:
            progress_callback("fetching_files", 50)
        
        files = fetch_drive_all_files(credentials)
        inserted_files = insert_files(user_id, files)
        results["files_count"] = len(inserted_files)
        
        update_user_status(user_id, "processing", "files_fetched", 60)
        if progress_callback:
            progress_callback("files_fetched", 60)
        
        # Step 4: Create embeddings for emails (60-75%)
        create_email_embeddings(user_id, inserted_emails, 60, 75)
        
        # Step 5: Create embeddings for schedules (75-85%)
        create_schedule_embeddings(user_id, inserted_schedules, 75, 85)
        
        # Step 6: Create embeddings for files (85-100%)
        create_file_embeddings(user_id, inserted_files, credentials, 85, 100)
        
        # Step 7: Complete
        update_user_status(user_id, "active", "completed", 100)
        if progress_callback:
            progress_callback("completed", 100)
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        results["error"] = str(e)
        update_user_status(user_id, "error", "failed", 0)
        if progress_callback:
            progress_callback("failed", 0)
    
    return results
