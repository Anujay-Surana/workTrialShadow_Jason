"""
Google API client for Gmail, Calendar, and Drive operations.

This module provides functions to interact with Google APIs:
- Gmail: Fetch messages and attachments
- Calendar: Fetch calendar events
- Drive: Fetch files and download content
"""

import time
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from retrieval_service.infrastructure.logging import log_info, log_error, log_debug
from retrieval_service.infrastructure.monitoring import monitor


# ======================================================
# Gmail: Fetch last 90 days emails (full pagination)
# ======================================================

async def fetch_gmail_messages(credentials, query="(category:primary OR label:sent) newer_than:90d", sleep_time=0.5, max_per_page=500):
    """
    Fetch Gmail messages with full pagination.
    
    Args:
        credentials: Google OAuth credentials
        query: Gmail search query
        sleep_time: Sleep time between API calls
        max_per_page: Maximum results per page
        
    Returns:
        tuple: (emails list, attachments list)
    """
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
            # Fetch individual message with monitoring and retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    msg = service.users().messages().get(
                        userId="me",
                        id=ref["id"]
                    ).execute()
                    monitor.log_request('google', 'messages_get', 'success', attempt)
                    break
                except Exception as e:
                    error_str = str(e)
                    is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "timeout", "rate_limit"])
                    
                    if attempt < max_retries - 1 and is_retryable:
                        wait_time = 1 * (2 ** attempt)
                        log_debug(f"Google API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        monitor.log_request('google', 'messages_get', 'retry', attempt)
                        time.sleep(wait_time)
                    else:
                        log_error(f"Google API error after {max_retries} attempts: {e}")
                        monitor.log_request('google', 'messages_get', 'error', attempt)
                        raise

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
                "date": iso_date,
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
    """
    Extract attachment metadata from a Gmail message.
    
    Args:
        message: Gmail message object
        email_id: Email ID
        
    Returns:
        list: List of attachment dictionaries
    """
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


def download_attachment_content(credentials, message_id, attachment_id):
    """
    Download attachment content from Gmail with retry logic.
    
    Args:
        credentials: Google OAuth credentials
        message_id: Gmail message ID
        attachment_id: Attachment ID
        
    Returns:
        bytes: Attachment content or None if error
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            service = build("gmail", "v1", credentials=credentials)
            attachment = service.users().messages().attachments().get(
                userId="me",
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            monitor.log_request('google', 'attachment_get', 'success', attempt)
            
            import base64
            file_data = base64.urlsafe_b64decode(attachment['data'])
            return file_data
            
        except Exception as e:
            error_str = str(e).lower()
            # Check for retryable errors including ConnectionTerminated
            is_retryable = any(keyword in error_str for keyword in [
                "504", "503", "429", "500", "timeout", "rate_limit",
                "connectionterminated", "connection", "deadline", "unavailable"
            ])
            
            if attempt < max_retries - 1 and is_retryable:
                wait_time = 2 * (2 ** attempt)  # 2s, 4s, 8s
                log_debug(f"Google attachment download error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                monitor.log_request('google', 'attachment_get', 'retry', attempt)
                time.sleep(wait_time)
            else:
                log_error(f"Error downloading attachment {attachment_id} after {max_retries} attempts: {e}")
                monitor.log_request('google', 'attachment_get', 'error', attempt)
                return None


# ======================================================
# Calendar: Fetch ALL future events (max 2500)
# ======================================================

def fetch_calendar_events(credentials, max_results=2500):
    """
    Fetch calendar events from Google Calendar.
    
    Args:
        credentials: Google OAuth credentials
        max_results: Maximum number of events to fetch
        
    Returns:
        list: List of calendar event dictionaries
    """
    service = build("calendar", "v3", credentials=credentials)
    
    now_dt = datetime.now(timezone.utc)
    two_weeks_ago_dt = now_dt - timedelta(days=14)

    now = now_dt.isoformat().replace("+00:00", "Z")
    two_weeks_ago = two_weeks_ago_dt.isoformat().replace("+00:00", "Z")

    # Fetch calendar events with monitoring and retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = service.events().list(
                calendarId="primary",
                timeMin=two_weeks_ago,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            monitor.log_request('google', 'calendar_events_list', 'success', attempt)
            break
        except Exception as e:
            error_str = str(e)
            is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "timeout", "rate_limit"])
            
            if attempt < max_retries - 1 and is_retryable:
                wait_time = 1 * (2 ** attempt)
                log_debug(f"Google Calendar API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                monitor.log_request('google', 'calendar_events_list', 'retry', attempt)
                time.sleep(wait_time)
            else:
                log_error(f"Google Calendar API error after {max_retries} attempts: {e}")
                monitor.log_request('google', 'calendar_events_list', 'error', attempt)
                raise

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
    """
    List children of a Google Drive folder.
    
    Args:
        service: Google Drive service object
        folder_id: Folder ID
        
    Returns:
        list: List of file dictionaries
    """
    # Fetch Drive files with monitoring and retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType, size, modifiedTime, parents, owners(displayName, emailAddress), ownedByMe, sharingUser(displayName, emailAddress))"
            ).execute()
            monitor.log_request('google', 'drive_files_list', 'success', attempt)
            return result.get("files", [])
        except Exception as e:
            error_str = str(e)
            is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "timeout", "rate_limit"])
            
            if attempt < max_retries - 1 and is_retryable:
                wait_time = 1 * (2 ** attempt)
                log_debug(f"Google Drive API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                monitor.log_request('google', 'drive_files_list', 'retry', attempt)
                time.sleep(wait_time)
            else:
                log_error(f"Google Drive API error after {max_retries} attempts: {e}")
                monitor.log_request('google', 'drive_files_list', 'error', attempt)
                raise


def fetch_drive_all_files(credentials, debug_mode=False):
    """
    Recursively traverse all Google Drive files (BFS).
    
    Args:
        credentials: Google OAuth credentials
        debug_mode: If True, only returns the latest 50 files (sorted by modified_time)
    
    Returns:
        list: List of file dictionaries with metadata
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
                log_debug(f"File: {name}")
                log_debug(f"ownedByMe: {f.get('ownedByMe')}")
                log_debug(f"owners: {f.get('owners')}")
                log_debug(f"sharingUser: {f.get('sharingUser')}")
            
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
        log_info(f"[DEBUG MODE] Limited to {len(results)} most recent files")

    return results


# ======================================================
# File Processing and Download
# ======================================================

def download_file_content(credentials, file_id, mime_type=None):
    """
    Download or export file content from Google Drive with retry logic.
    
    Args:
        credentials: Google OAuth credentials
        file_id: Drive file ID
        mime_type: File MIME type (optional)
        
    Returns:
        bytes: File content or None if error
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            service = build("drive", "v3", credentials=credentials)
            
            # Check if it's a Google Workspace file that needs export
            google_workspace_types = {
                'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # Export as DOCX
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # Export as XLSX
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # Export as PPTX
                'application/vnd.google-apps.drawing': 'application/pdf',  # Export as PDF
                'application/vnd.google.colaboratory': 'application/x-ipynb+json',  # Export Colab as Jupyter Notebook
            }
            
            log_debug(f"Downloading file {file_id}, mime_type: {mime_type}")
            
            # Always check actual mime_type from API to handle Google Workspace files correctly
            file_metadata = service.files().get(fileId=file_id, fields='mimeType').execute()
            actual_mime_type = file_metadata.get('mimeType')
            log_debug(f"Actual mime_type from API: {actual_mime_type}")
            
            if actual_mime_type in google_workspace_types:
                # Google Workspace file - use export
                export_mime_type = google_workspace_types[actual_mime_type]
                log_debug(f"Google Workspace file detected, using export with mime_type: {export_mime_type}")
                request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            else:
                # Regular binary file - use download
                log_debug("Regular binary file, using download")
                request = service.files().get_media(fileId=file_id)
            
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            monitor.log_request('google', 'drive_download', 'success', attempt)
            return file_content.read()
            
        except Exception as e:
            error_str = str(e).lower()
            # Check for retryable errors (but not fileNotDownloadable which is a logic error we fixed)
            is_retryable = any(keyword in error_str for keyword in [
                "504", "503", "429", "500", "timeout", "rate_limit",
                "connectionterminated", "connection", "deadline", "unavailable"
            ]) and "filenotdownloadable" not in error_str
            
            if attempt < max_retries - 1 and is_retryable:
                wait_time = 2 * (2 ** attempt)  # 2s, 4s, 8s
                log_debug(f"Google Drive download error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                monitor.log_request('google', 'drive_download', 'retry', attempt)
                time.sleep(wait_time)
            else:
                log_error(f"Error downloading file {file_id} after {max_retries} attempts: {e}")
                monitor.log_request('google', 'drive_download', 'error', attempt)
                return None


# ======================================================
# Public Download Links
# ======================================================

def get_drive_public_download_link(file):
    """
    Return a public, no-auth download/export URL for a Google Drive file.
    
    Args:
        file: File metadata dictionary with {id, mime_type}
        
    Returns:
        str: Public download URL
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
    
    Args:
        message_id: Gmail message ID
        attachment_id: Attachment ID
        
    Returns:
        str: Public download URL
    """
    return (
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
        f"{message_id}/attachments/{attachment_id}"
    )
