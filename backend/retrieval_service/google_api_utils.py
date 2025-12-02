from datetime import timedelta
import time
import io
import threading
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from email.utils import parsedate_to_datetime
from retrieval_service.openai_api_utils import summarize_doc, summarize
from retrieval_service.supabase_utils import (
    get_emails_by_thread,
    get_attachments_by_email,
    insert_embedding,
    batch_insert_embeddings,
    update_file_summary,
    update_attachment_summary,
    update_user_status
)
from retrieval_service.gemni_api_utils import embed_text
from retrieval_service.thread_pool_manager import get_thread_pool_manager

from retrieval_service.ocr_utils import extractOCR, isIMG
from retrieval_service.doc_utils import extractDOC, isDOC


# ======================================================
# Gmail: Fetch last 90 days emails (full pagination)
# ======================================================

async def fetch_gmail_messages(credentials, query="(category:primary OR label:sent) newer_than:90d", sleep_time=0.5, max_per_page=500):
    service = build("gmail", "v1", credentials=credentials)
    all_emails = []
    all_attachments = []
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

            email_id = msg.get("id")
            
            all_emails.append({
                "id": email_id,
                "thread_id": msg.get("threadId"),
                "snippet": msg.get("snippet", ""),
                "subject": get_header("Subject"),
                "from": get_header("From"),
                "to": get_header("To"),
                "cc": get_header("Cc"),
                "bcc": get_header("Bcc"),
                "date": iso_date,  # <-- FIXED
            })
            
            # Extract attachments
            attachments = extract_attachments(msg, email_id)
            all_attachments.extend(attachments)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

        time.sleep(sleep_time)

    return all_emails, all_attachments


def extract_attachments(message, email_id):
    """Extract attachment metadata from a Gmail message"""
    attachments = []
    
    def process_parts(parts, email_id):
        """Recursively process message parts to find attachments"""
        for part in parts:
            # Check if this part has nested parts
            if 'parts' in part:
                process_parts(part['parts'], email_id)
            
            # Check if this is an attachment
            filename = part.get('filename', '')
            if filename:
                attachment_id = part.get('body', {}).get('attachmentId')
                if attachment_id:
                    attachments.append({
                        'id': attachment_id,
                        'email_id': email_id,
                        'filename': filename,
                        'mime_type': part.get('mimeType', ''),
                        'size': part.get('body', {}).get('size', 0)
                    })
    
    # Process message payload
    payload = message.get('payload', {})
    if 'parts' in payload:
        process_parts(payload['parts'], email_id)
    
    return attachments


# ======================================================
# Calendar: Fetch ALL future events (max 2500)
# ======================================================

def fetch_calendar_events(credentials, max_results=2500):
    service = build("calendar", "v3", credentials=credentials)

    from datetime import datetime
    now = datetime.utcnow().isoformat() + "Z"
    two_weeks_ago = (now - timedelta(days=14)).isoformat() + "Z"

    resp = service.events().list(
        calendarId="primary",
        timeMin=two_weeks_ago,
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
        fields="files(id, name, mimeType, size, modifiedTime, parents, owners(displayName, emailAddress), ownedByMe, sharingUser(displayName, emailAddress))"
    ).execute()
    return result.get("files", [])


def fetch_drive_all_files(credentials, debug_mode=False):
    """
    Recursively traverse all Google Drive files (BFS).
    
    Args:
        credentials: Google OAuth credentials
        debug_mode: If True, only returns the latest 50 files (sorted by modified_time)
    
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
            # Debug: Log the raw API response for first few files
            if len(results) < 3:
                print(f"[DEBUG] File: {name}")
                print(f"[DEBUG] ownedByMe: {f.get('ownedByMe')}")
                print(f"[DEBUG] owners: {f.get('owners')}")
                print(f"[DEBUG] sharingUser: {f.get('sharingUser')}")
            
            owners = f.get("owners", [])
            owner_emails = ", ".join([o.get("emailAddress", "") for o in owners if o.get("emailAddress")])
            owner_names = ", ".join([o.get("displayName", "") for o in owners if o.get("displayName")])
            
            # If file is not owned by user, try to get sharing user info
            if not f.get("ownedByMe", True) and f.get("sharingUser"):
                sharing_user = f.get("sharingUser", {})
                sharing_email = sharing_user.get("emailAddress", "")
                sharing_name = sharing_user.get("displayName", "")
                if sharing_email:
                    owner_emails = sharing_email
                    owner_names = sharing_name
            
            # Collect metadata for richer information storage
            metadata = {
                "ownedByMe": f.get("ownedByMe"),
                "owners": f.get("owners", []),
                "sharingUser": f.get("sharingUser"),
                "mimeType": f.get("mimeType"),
                "webViewLink": f.get("webViewLink"),
                "iconLink": f.get("iconLink"),
                "thumbnailLink": f.get("thumbnailLink"),
                "createdTime": f.get("createdTime"),
                "modifiedByMeTime": f.get("modifiedByMeTime"),
                "viewedByMe": f.get("viewedByMe"),
                "viewedByMeTime": f.get("viewedByMeTime"),
            }

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
                "metadata": metadata,
            })

            if is_folder:
                queue.append((f["id"], current_path))

        time.sleep(0.2)
    
    # DEBUG mode: Sort by modified_time and limit to 50 most recent files
    if debug_mode:
        # Filter out folders and sort by modified_time (most recent first)
        files_only = [f for f in results if f["mime_type"] != "application/vnd.google-apps.folder"]
        files_only.sort(key=lambda x: x.get("modified_time", ""), reverse=True)
        results = files_only[:50]
        print(f"[DEBUG MODE] Limited to {len(results)} most recent files")

    return results


# ======================================================
# File Processing and Download
# ======================================================

def download_file_content(credentials, file_id, mime_type=None):
    """Download or export file content from Google Drive"""
    try:
        service = build("drive", "v3", credentials=credentials)
        
        # Check if it's a Google Workspace file that needs export
        google_workspace_types = {
            'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # Export as DOCX
            'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # Export as XLSX
            'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # Export as PPTX
            'application/vnd.google-apps.drawing': 'application/pdf',  # Export as PDF
        }
        
        print(f"[DEBUG] Downloading file {file_id}, mime_type: {mime_type}")
        
        # If mime_type not provided or it's a workspace file, check via API
        if not mime_type or mime_type in google_workspace_types:
            # Get file metadata to determine if export is needed
            file_metadata = service.files().get(fileId=file_id, fields='mimeType').execute()
            actual_mime_type = file_metadata.get('mimeType')
            print(f"[DEBUG] Actual mime_type from API: {actual_mime_type}")
            
            if actual_mime_type in google_workspace_types:
                export_mime_type = google_workspace_types[actual_mime_type]
                print(f"[DEBUG] Using export with mime_type: {export_mime_type}")
                request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            else:
                print(f"[DEBUG] Using regular download")
                request = service.files().get_media(fileId=file_id)
        else:
            # Regular binary file - use download
            print(f"[DEBUG] Using regular download (non-workspace file)")
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


def download_attachment_content(credentials, message_id, attachment_id):
    """Download attachment content from Gmail"""
    try:
        service = build("gmail", "v1", credentials=credentials)
        attachment = service.users().messages().attachments().get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        ).execute()
        
        import base64
        file_data = base64.urlsafe_b64decode(attachment['data'])
        return file_data
    except Exception as e:
        print(f"Error downloading attachment {attachment_id}: {e}")
        return None


def process_file_by_type(file_name: str, file_content: bytes) -> str:
    """
    Process file content and return summary.
    
    Args:
        file_name: Name of the file
        file_content: Raw bytes content of the file
    
    Returns:
        str: Summary of the file content
    """
    if isIMG(file_name):
        try:
            text = extractOCR(file_content)
            return "An image with following extracted text: " + text if text else "An image file with no extractable text."
        except Exception as e:
            return "An image file with no extractable text."
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
    Create embeddings for emails (3 types: email_sum, email_context, email_title) in parallel.
    Updates progress granularly as emails are processed.
    
    Args:
        user_id: User UUID
        emails: List of email dictionaries from database
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    print(f"[DEBUG] create_email_embeddings called with {len(emails)} emails")
    if not emails:
        print("[DEBUG] No emails to process, returning")
        return
    
    total_emails = len(emails)
    progress_range = end_progress - start_progress
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_email(email):
        """Process a single email and return embeddings"""
        email_id = email["id"]
        email_embeddings = []
        
        # Get attachments for this email
        attachments = get_attachments_by_email(user_id, email_id)
        attachment_info = ""
        if attachments:
            attachment_info = "\nAttachments:\n"
            for att in attachments:
                att_summary = att.get('summary', 'No summary')
                attachment_info += f"- {att.get('filename', 'unknown')}: {att_summary}\n"
        
        # 1. email_sum: Full email information including attachments
        email_sum_text = (
            f"An email from {email.get('from_user', 'unknown')} "
            f"to {email.get('to_user', 'unknown')} "
            f"at {email.get('date', 'unknown date')}. "
            f"Subject: {email.get('subject', 'No subject')}. "
            f"Content: {email.get('body', '')}"
            f"{attachment_info}"
        )
        try:
            email_sum_vector = embed_text(email_sum_text)
            email_embeddings.append({
                "id": f"{email_id}_sum",
                "user_id": user_id,
                "type": "email_sum",
                "vector": email_sum_vector,
                "email_id": email_id,
                "schedule_id": None,
                "file_id": None,
                "attachment_id": None
            })
        except Exception as e:
            print(f"Error embedding email_sum for {email_id}: {e}")
        
        # 2. email_context: Full thread context with summarization
        thread_id = email.get("thread_id")
        if thread_id:
            try:
                thread_emails = get_emails_by_thread(user_id, thread_id)
                thread_text = "Email thread:\n"
                for t_email in thread_emails:
                    # Get attachments for thread email
                    t_attachments = get_attachments_by_email(user_id, t_email["id"])
                    t_att_info = ""
                    if t_attachments:
                        t_att_info = " [Attachments: "
                        t_att_info += ", ".join([att.get('filename', 'unknown') for att in t_attachments])
                        t_att_info += "]"
                    
                    thread_text += (
                        f"From {t_email.get('from_user', 'unknown')} "
                        f"at {t_email.get('date', 'unknown')}: "
                        f"{t_email.get('subject', 'No subject')} - "
                        f"{t_email.get('body', '')}"
                        f"{t_att_info}\n"
                    )
                
                # Summarize thread if it's too long (> 8000 chars)
                if len(thread_text) > 8000:
                    print(f"[INFO] Thread {thread_id} is long ({len(thread_text)} chars), summarizing...")
                    thread_summary = summarize(thread_text, max_chars=8000)
                    thread_text = f"Email thread summary:\n{thread_summary}"
                
                email_context_vector = embed_text(thread_text)
                email_embeddings.append({
                    "id": f"{email_id}_context",
                    "user_id": user_id,
                    "type": "email_context",
                    "vector": email_context_vector,
                    "email_id": email_id,
                    "schedule_id": None,
                    "file_id": None,
                    "attachment_id": None
                })
            except Exception as e:
                print(f"Error embedding email_context for {email_id}: {e}")
        
        # 3. email_title: Subject and sender/receiver info only (no attachments)
        email_title_text = (
            f"An Email with subject: {email.get('subject', 'No subject')}. "
            f"From: {email.get('from_user', 'unknown')}. "
            f"To: {email.get('to_user', 'unknown')}. "
            f"CC: {email.get('cc', 'none')}. "
            f"BCC: {email.get('bcc', 'none')}."
        )
        try:
            email_title_vector = embed_text(email_title_text)
            email_embeddings.append({
                "id": f"{email_id}_title",
                "user_id": user_id,
                "type": "email_title",
                "vector": email_title_vector,
                "email_id": email_id,
                "schedule_id": None,
                "file_id": None,
                "attachment_id": None
            })
        except Exception as e:
            print(f"Error embedding email_title for {email_id}: {e}")
        
        # Update progress (thread-safe)
        with progress_lock:
            processed_count[0] += 1
            current_progress = start_progress + int(processed_count[0] / total_emails * progress_range)
            if current_progress - last_update_progress[0] >= 1:
                update_user_status(user_id, "processing", "embedding_emails", current_progress)
                last_update_progress[0] = current_progress
        
        return email_embeddings
    
    # Process emails in parallel
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, emails, process_single_email)
    
    # Flatten results and batch insert
    embeddings_to_insert = []
    for email_embeddings in results:
        if email_embeddings:
            embeddings_to_insert.extend(email_embeddings)
    
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


def create_schedule_embeddings(user_id: str, schedules: list, start_progress: int, end_progress: int):
    """
    Create embeddings for schedules in parallel.
    Updates progress granularly as schedules are processed.
    
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
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_schedule(schedule):
        """Process a single schedule and return embedding"""
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
            embedding = {
                "id": f"{schedule_id}_context",
                "user_id": user_id,
                "type": "schedule_context",
                "vector": schedule_vector,
                "email_id": None,
                "schedule_id": schedule_id,
                "file_id": None
            }
            
            # Update progress (thread-safe)
            with progress_lock:
                processed_count[0] += 1
                current_progress = start_progress + int(processed_count[0] / total_schedules * progress_range)
                if current_progress - last_update_progress[0] >= 1:
                    update_user_status(user_id, "processing", "embedding_schedules", current_progress)
                    last_update_progress[0] = current_progress
            
            return embedding
        except Exception as e:
            print(f"Error embedding schedule {schedule_id}: {e}")
            return None
    
    # Process schedules in parallel
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, schedules, process_single_schedule)
    
    # Filter out None results and batch insert
    embeddings_to_insert = [r for r in results if r is not None]
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


def create_file_embeddings(user_id: str, files: list, credentials, start_progress: int, end_progress: int):
    """
    Create embeddings for files (with file processing) in parallel.
    Updates progress granularly as files are processed.
    
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
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_file(file):
        """Process a single file and return embedding"""
        file_id = file["id"]
        file_name = file.get("name", "unknown")
        mime_type = file.get("mime_type")
        
        # Download and process file
        try:
            file_content = download_file_content(credentials, file_id, mime_type)
            if file_content:
                # Process file to get summary
                summary = process_file_by_type(file_name, file_content)
                
                # Update file summary in database
                update_file_summary(user_id, file_id, summary)
                
                # Create embedding with file metadata and summary
                metadata = file.get('metadata', {})
                file_text = (
                    f"User has the following file in Google Drive:\n"
                    f"File Name: {file_name}\n"
                    f"Type: {file.get('mime_type', 'unknown')}\n"
                    f"Path: {file.get('path', 'unknown')}\n"
                    f"Size: {file.get('size', 'unknown')} bytes\n"
                    f"Modified: {file.get('modified_time', 'unknown')}\n"
                    f"Owner: {file.get('owner_name', 'unknown')} ({file.get('owner_email', 'unknown')})\n"
                    f"Owned by me: {metadata.get('ownedByMe', 'unknown')}\n"
                    f"Created: {metadata.get('createdTime', 'unknown')}\n"
                    f"Last viewed by me: {metadata.get('viewedByMeTime', 'unknown')}\n"
                    f"Web view link: {metadata.get('webViewLink', 'N/A')}\n"
                    f"File Summary: {summary}"
                )
                
                file_vector = embed_text(file_text)
                embedding = {
                    "id": f"{file_id}_context",
                    "user_id": user_id,
                    "type": "file_context",
                    "vector": file_vector,
                    "email_id": None,
                    "schedule_id": None,
                    "file_id": file_id,
                    "attachment_id": None
                }
                
                # Update progress (thread-safe)
                with progress_lock:
                    processed_count[0] += 1
                    current_progress = start_progress + int(processed_count[0] / total_files * progress_range)
                    if current_progress - last_update_progress[0] >= 1:
                        update_user_status(user_id, "processing", "embedding_files", current_progress)
                        last_update_progress[0] = current_progress
                
                return embedding
        except Exception as e:
            print(f"Error processing/embedding file {file_id}: {e}")
            return None
    
    # Process files in parallel
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, files, process_single_file)
    
    # Filter out None results and batch insert
    embeddings_to_insert = [r for r in results if r is not None]
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


def create_attachment_embeddings(user_id: str, attachments: list, credentials, start_progress: int, end_progress: int):
    """
    Create embeddings for email attachments (with file processing) in parallel.
    Updates progress granularly as attachments are processed.
    
    Args:
        user_id: User UUID
        attachments: List of attachment dictionaries from database
        credentials: Google credentials for downloading attachments
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    if not attachments:
        return
    
    total_attachments = len(attachments)
    progress_range = end_progress - start_progress
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_attachment(attachment):
        """Process a single attachment and return embedding"""
        attachment_id = attachment["id"]
        email_id = attachment["email_id"]
        filename = attachment.get("filename", "unknown")
        
        # Get email information for context
        from retrieval_service.supabase_utils import supabase
        email_info = None
        try:
            email_response = supabase.table('emails').select('*').eq('user_id', user_id).eq('id', email_id).execute()
            if email_response.data:
                email_info = email_response.data[0]
        except Exception as e:
            print(f"Error fetching email info for attachment {attachment_id}: {e}")
        
        # Download and process attachment
        try:
            att_content = download_attachment_content(credentials, email_id, attachment_id)
            if att_content:
                # Process attachment to get summary
                summary = process_file_by_type(filename, att_content)
                
                # Update attachment summary in database
                update_attachment_summary(user_id, attachment_id, summary)
                
                # Create embedding with attachment metadata, email context, and summary
                att_text = f"Email attachment:\nFilename: {filename}\n"
                att_text += f"Type: {attachment.get('mime_type', 'unknown')}\n"
                att_text += f"Size: {attachment.get('size', 'unknown')} bytes\n"
                
                # Add email context
                if email_info:
                    att_text += f"From email sent by: {email_info.get('from_user', 'unknown')}\n"
                    att_text += f"To: {email_info.get('to_user', 'unknown')}\n"
                    if email_info.get('cc'):
                        att_text += f"CC: {email_info.get('cc')}\n"
                    if email_info.get('bcc'):
                        att_text += f"BCC: {email_info.get('bcc')}\n"
                    att_text += f"Email date: {email_info.get('date', 'unknown')}\n"
                    att_text += f"Email subject: {email_info.get('subject', 'No subject')}\n"
                    att_text += f"Email summary: {email_info.get('body', '')[:500]}\n"
                
                att_text += f"Attachment Summary: {summary}"
                
                att_vector = embed_text(att_text)
                embedding = {
                    "id": f"{attachment_id}_context",
                    "user_id": user_id,
                    "type": "attachment_context",
                    "vector": att_vector,
                    "email_id": None,
                    "schedule_id": None,
                    "file_id": None,
                    "attachment_id": attachment_id
                }
                
                # Update progress (thread-safe)
                with progress_lock:
                    processed_count[0] += 1
                    current_progress = start_progress + int(processed_count[0] / total_attachments * progress_range)
                    if current_progress - last_update_progress[0] >= 1:
                        update_user_status(user_id, "processing", "embedding_attachments", current_progress)
                        last_update_progress[0] = current_progress
                
                return embedding
        except Exception as e:
            print(f"Error processing/embedding attachment {attachment_id}: {e}")
            return None
    
    # Process attachments in parallel
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, attachments, process_single_attachment)
    
    # Filter out None results and batch insert
    embeddings_to_insert = [r for r in results if r is not None]
    if embeddings_to_insert:
        batch_insert_embeddings(embeddings_to_insert)


# ======================================================
# Main Initialization Function
# ======================================================

async def initialize_user_data(user_id: str, credentials, progress_callback=None, debug_mode=False):
    """
    Initialize user data: fetch emails, schedules, files, attachments and create embeddings.
    
    Args:
        user_id: User UUID
        credentials: Google OAuth credentials
        progress_callback: Optional callback function to update progress
        debug_mode: If True, only processes the latest 50 files to save API costs
    
    Returns:
        dict: Summary of initialization results
    """
    from retrieval_service.supabase_utils import insert_emails, insert_schedules, insert_files, insert_attachments
    
    results = {
        "emails_count": 0,
        "schedules_count": 0,
        "files_count": 0,
        "attachments_count": 0,
        "error": None
    }
    
    try:
        # Update status to processing
        update_user_status(user_id, "processing", "starting", 0)
        if progress_callback:
            progress_callback("starting", 0)
        
        # Step 1: Fetch and insert emails and attachments
        update_user_status(user_id, "processing", "fetching_emails", 10)
        if progress_callback:
            progress_callback("fetching_emails", 10)
        
        emails, attachments = await fetch_gmail_messages(credentials)
        inserted_emails = insert_emails(user_id, emails)
        inserted_attachments = insert_attachments(user_id, attachments)
        results["emails_count"] = len(inserted_emails)
        results["attachments_count"] = len(inserted_attachments)
        
        update_user_status(user_id, "processing", "emails_fetched", 20)
        if progress_callback:
            progress_callback("emails_fetched", 20)
        
        # Step 2: Fetch and insert schedules
        update_user_status(user_id, "processing", "fetching_schedules", 25)
        if progress_callback:
            progress_callback("fetching_schedules", 25)
        
        schedules = fetch_calendar_events(credentials)
        inserted_schedules = insert_schedules(user_id, schedules)
        results["schedules_count"] = len(inserted_schedules)
        
        update_user_status(user_id, "processing", "schedules_fetched", 30)
        if progress_callback:
            progress_callback("schedules_fetched", 30)
        
        # Step 3: Fetch and insert files
        update_user_status(user_id, "processing", "fetching_files", 35)
        if progress_callback:
            progress_callback("fetching_files", 35)
        
        files = fetch_drive_all_files(credentials, debug_mode=debug_mode)
        inserted_files = insert_files(user_id, files)
        results["files_count"] = len(inserted_files)
        
        update_user_status(user_id, "processing", "files_fetched", 40)
        if progress_callback:
            progress_callback("files_fetched", 40)
        
        # Step 4: Create embeddings for attachments (40-55%)
        create_attachment_embeddings(user_id, inserted_attachments, credentials, 40, 55)
        
        # Step 5: Create embeddings for emails (55-70%)
        create_email_embeddings(user_id, inserted_emails, 55, 70)
        
        # Step 6: Create embeddings for schedules (70-80%)
        create_schedule_embeddings(user_id, inserted_schedules, 70, 80)
        
        # Step 7: Create embeddings for files (80-100%)
        create_file_embeddings(user_id, inserted_files, credentials, 80, 100)
        
        # Step 8: Complete
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


#=======================================================
def get_drive_public_download_link(file):
    """
    Return a public, no-auth download/export URL for a Google Drive file.
    File metadata should include {id, mime_type}.
    """
    file_id = file.get("id")
    mime_type = file.get("mime_type")

    # Google Workspace Export MIME Types
    workspace_export_map = {
        "application/vnd.google-apps.document":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
        "application/vnd.google-apps.spreadsheet":
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",       # XLSX
        "application/vnd.google-apps.presentation":
            "application/vnd.openxmlformats-officedocument.presentationml.presentation", # PPTX
        "application/vnd.google-apps.drawing":
            "application/pdf"
    }

    # Workspace file → export URL
    if mime_type in workspace_export_map:
        export_type = workspace_export_map[mime_type]
        return (
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            f"?mimeType={export_type}"
        )

    # Binary file → direct download
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def get_gmail_attachment_download_link(message_id: str, attachment_id: str) -> str:
    """
    Return the public Gmail attachment download endpoint.
    Browser will use user's Gmail session cookies.
    No OAuth or API key required for GET request via browser.
    """
    return (
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
        f"{message_id}/attachments/{attachment_id}"
    )
