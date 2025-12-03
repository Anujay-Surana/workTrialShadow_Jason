"""
User data initialization module.

This module handles the initialization of user data from Google services:
- Fetching emails, schedules, files, and attachments
- Creating embeddings for all data types
- Updating user status during initialization
"""

import threading
from retrieval_service.api.google_client import (
    fetch_gmail_messages,
    fetch_calendar_events,
    fetch_drive_all_files,
    download_file_content,
    download_attachment_content
)
from retrieval_service.api.gemini_client import embed_text
from retrieval_service.data.database import (
    insert_emails,
    insert_schedules,
    insert_files,
    insert_attachments,
    get_emails_by_thread,
    get_attachments_by_email,
    update_file_summary,
    update_attachment_summary,
    update_user_status
)
from retrieval_service.processing import summarize_doc, summarize, process_file_by_type
from retrieval_service.infrastructure.batch import batch_embed_gemini, batch_insert_supabase
from retrieval_service.infrastructure.threading import get_thread_pool_manager
from retrieval_service.infrastructure.logging import log_info, log_error, log_warning, log_debug


# ======================================================
# Embedding Functions
# ======================================================

async def create_email_embeddings(user_id: str, emails: list, start_progress: int, end_progress: int):
    """
    Create embeddings for emails (3 types: email_sum, email_context, email_title) using batch processing.
    Updates progress granularly as emails are processed.
    
    Args:
        user_id: User UUID
        emails: List of email dictionaries from database
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    from retrieval_service.data import supabase
    
    log_debug(f"create_email_embeddings called with {len(emails)} emails")
    if not emails:
        log_debug("No emails to process, returning")
        return
    
    # Step 1: Prepare all texts for batch embedding
    all_texts = []
    text_metadata = []  # Track which text belongs to which email and type
    
    for email in emails:
        email_id = email["id"]
        
        # Get attachments for this email
        attachments = get_attachments_by_email(user_id, email_id)
        attachment_info = ""
        if attachments:
            attachment_info = "\nAttachments:\n"
            for att in attachments:
                att_summary = att.get('summary', 'No summary')
                attachment_info += f"- {att.get('filename', 'unknown')}: {att_summary}\n"
        
        # 1. email_sum text
        email_sum_text = (
            f"An email from {email.get('from_user', 'unknown')} "
            f"to {email.get('to_user', 'unknown')} "
            f"at {email.get('date', 'unknown date')}. "
            f"Subject: {email.get('subject', 'No subject')}. "
            f"Content: {email.get('body', '')}"
            f"{attachment_info}"
        )
        all_texts.append(email_sum_text)
        text_metadata.append({"email_id": email_id, "type": "email_sum"})
        
        # 2. email_context text
        thread_id = email.get("thread_id")
        if thread_id:
            thread_emails = get_emails_by_thread(user_id, thread_id)
            thread_text = "Email thread:\n"
            for t_email in thread_emails:
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
            
            # Summarize thread if too long
            if len(thread_text) > 8000:
                log_info(f"Thread {thread_id} is long ({len(thread_text)} chars), summarizing...")
                thread_summary = summarize(thread_text, max_chars=8000)
                thread_text = f"Email thread summary:\n{thread_summary}"
            
            all_texts.append(thread_text)
            text_metadata.append({"email_id": email_id, "type": "email_context"})
        
        # 3. email_title text
        email_title_text = (
            f"An Email with subject: {email.get('subject', 'No subject')}. "
            f"From: {email.get('from_user', 'unknown')}. "
            f"To: {email.get('to_user', 'unknown')}. "
            f"CC: {email.get('cc', 'none')}. "
            f"BCC: {email.get('bcc', 'none')}."
        )
        all_texts.append(email_title_text)
        text_metadata.append({"email_id": email_id, "type": "email_title"})
    
    update_user_status(user_id, "processing", "embedding_emails", start_progress + 5)
    
    # Step 2: Batch embed all texts
    log_info(f"Batch embedding {len(all_texts)} email texts...")
    try:
        embeddings = await batch_embed_gemini(all_texts)
        
        update_user_status(user_id, "processing", "embedding_emails", start_progress + 10)
        
        # Step 3: Prepare records for batch insert
        records = []
        for i, metadata in enumerate(text_metadata):
            records.append({
                "id": f"{metadata['email_id']}_{metadata['type'].replace('email_', '')}",
                "user_id": user_id,
                "type": metadata["type"],
                "vector": embeddings[i],
                "email_id": metadata["email_id"],
                "schedule_id": None,
                "file_id": None,
                "attachment_id": None
            })
        
        # Step 4: Batch insert all embeddings
        log_info(f"Batch inserting {len(records)} email embeddings...")
        batch_insert_supabase(supabase.table('embeddings'), records)
        
        log_info(f"Successfully created embeddings for {len(emails)} emails")
        update_user_status(user_id, "processing", "embedding_emails", end_progress)
        
    except Exception as e:
        log_error(f"Error in batch email embedding: {e}")
        raise


async def create_schedule_embeddings(user_id: str, schedules: list, start_progress: int, end_progress: int):
    """
    Create embeddings for schedules using batch processing.
    Updates progress granularly as schedules are processed.
    
    Args:
        user_id: User UUID
        schedules: List of schedule dictionaries from database
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    from retrieval_service.data import supabase
    
    if not schedules:
        return
    
    # Step 1: Prepare all texts for batch embedding
    all_texts = []
    schedule_ids = []
    
    for schedule in schedules:
        schedule_id = schedule["id"]
        schedule_ids.append(schedule_id)
        
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
        all_texts.append(schedule_text)
    
    update_user_status(user_id, "processing", "embedding_schedules", start_progress + 2)
    
    # Step 2: Batch embed all texts
    log_info(f"Batch embedding {len(all_texts)} schedule texts...")
    try:
        embeddings = await batch_embed_gemini(all_texts)
        
        update_user_status(user_id, "processing", "embedding_schedules", start_progress + 5)
        
        # Step 3: Prepare records for batch insert
        records = []
        for i, schedule_id in enumerate(schedule_ids):
            records.append({
                "id": f"{schedule_id}_context",
                "user_id": user_id,
                "type": "schedule_context",
                "vector": embeddings[i],
                "email_id": None,
                "schedule_id": schedule_id,
                "file_id": None,
                "attachment_id": None
            })
        
        # Step 4: Batch insert all embeddings
        log_info(f"Batch inserting {len(records)} schedule embeddings...")
        batch_insert_supabase(supabase.table('embeddings'), records)
        
        log_info(f"Successfully created embeddings for {len(schedules)} schedules")
        update_user_status(user_id, "processing", "embedding_schedules", end_progress)
        
    except Exception as e:
        log_error(f"Error in batch schedule embedding: {e}")
        raise


async def create_file_embeddings(user_id: str, files: list, credentials, start_progress: int, end_progress: int):
    """
    Create embeddings for files with parallel processing and batch embedding.
    Downloads/processes files in parallel, then batch embeds all texts.
    
    Args:
        user_id: User UUID
        files: List of file dictionaries from database
        credentials: Google credentials for downloading files
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    from retrieval_service.data import supabase
    
    if not files:
        return
    
    total_files = len(files)
    progress_range = end_progress - start_progress
    download_progress = int(progress_range * 0.7)  # 70% for downloading/processing
    embed_progress = progress_range - download_progress  # 30% for embedding
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_file(file):
        """Download and process a single file, return text and metadata"""
        file_id = file["id"]
        file_name = file.get("name", "unknown")
        mime_type = file.get("mime_type")
        
        try:
            file_content = download_file_content(credentials, file_id, mime_type)
            if file_content:
                # Process file to get summary
                summary = process_file_by_type(file_name, file_content)
                
                # Update file summary in database
                update_file_summary(user_id, file_id, summary)
                
                # Create text for embedding
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
                
                # Update progress (thread-safe)
                with progress_lock:
                    processed_count[0] += 1
                    current_progress = start_progress + int(processed_count[0] / total_files * download_progress)
                    if current_progress - last_update_progress[0] >= 1:
                        update_user_status(user_id, "processing", "processing_files", current_progress)
                        last_update_progress[0] = current_progress
                
                return {"file_id": file_id, "text": file_text}
        except Exception as e:
            log_error(f"Error processing file {file_id}: {e}")
            return None
    
    # Step 1: Process files in parallel (download + extract text)
    log_info(f"Processing {total_files} files in parallel...")
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, files, process_single_file)
    
    # Filter out None results
    processed_files = [r for r in results if r is not None]
    
    if not processed_files:
        log_warning("No files were successfully processed")
        return
    
    # Step 2: Batch embed all file texts
    log_info(f"Batch embedding {len(processed_files)} file texts...")
    update_user_status(user_id, "processing", "embedding_files", start_progress + download_progress)
    
    try:
        all_texts = [f["text"] for f in processed_files]
        embeddings = await batch_embed_gemini(all_texts)
        
        # Step 3: Prepare records for batch insert
        records = []
        for i, file_data in enumerate(processed_files):
            records.append({
                "id": f"{file_data['file_id']}_context",
                "user_id": user_id,
                "type": "file_context",
                "vector": embeddings[i],
                "email_id": None,
                "schedule_id": None,
                "file_id": file_data["file_id"],
                "attachment_id": None
            })
        
        # Step 4: Batch insert all embeddings
        log_info(f"Batch inserting {len(records)} file embeddings...")
        batch_insert_supabase(supabase.table('embeddings'), records)
        
        log_info(f"Successfully created embeddings for {len(processed_files)} files")
        update_user_status(user_id, "processing", "embedding_files", end_progress)
        
    except Exception as e:
        log_error(f"Error in batch file embedding: {e}")
        raise


async def create_attachment_embeddings(user_id: str, attachments: list, credentials, start_progress: int, end_progress: int):
    """
    Create embeddings for email attachments with parallel processing and batch embedding.
    Downloads/processes attachments in parallel, then batch embeds all texts.
    
    Args:
        user_id: User UUID
        attachments: List of attachment dictionaries from database
        credentials: Google credentials for downloading attachments
        start_progress: Starting progress percentage
        end_progress: Ending progress percentage
    """
    from retrieval_service.data import supabase
    import time
    
    if not attachments:
        return
    
    total_attachments = len(attachments)
    progress_range = end_progress - start_progress
    download_progress = int(progress_range * 0.7)  # 70% for downloading/processing
    embed_progress = progress_range - download_progress  # 30% for embedding
    
    # Batch fetch all email info upfront to avoid repeated queries
    log_info(f"Batch fetching email info for {total_attachments} attachments...")
    email_ids = list(set([att["email_id"] for att in attachments]))
    email_info_map = {}
    
    try:
        # Batch query with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                email_response = supabase.table('emails').select('*').eq('user_id', user_id).in_('id', email_ids).execute()
                if email_response.data:
                    email_info_map = {email['id']: email for email in email_response.data}
                log_info(f"Fetched info for {len(email_info_map)} emails")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 * (2 ** attempt)
                    log_warning(f"Error fetching email info (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    log_error(f"Failed to fetch email info after {max_retries} attempts: {e}")
    except Exception as e:
        log_error(f"Error in batch email fetch: {e}")
    
    # Thread-safe progress tracking
    progress_lock = threading.Lock()
    processed_count = [0]
    last_update_progress = [start_progress]
    
    def process_single_attachment(attachment):
        """Download and process a single attachment, return text and metadata"""
        attachment_id = attachment["id"]
        email_id = attachment["email_id"]
        filename = attachment.get("filename", "unknown")
        
        # Get email information from pre-fetched map
        email_info = email_info_map.get(email_id)
        
        try:
            att_content = download_attachment_content(credentials, email_id, attachment_id)
            if att_content:
                # Process attachment to get summary
                summary = process_file_by_type(filename, att_content)
                
                # Update attachment summary in database
                update_attachment_summary(user_id, attachment_id, summary)
                
                # Create text for embedding
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
                
                # Update progress (thread-safe)
                with progress_lock:
                    processed_count[0] += 1
                    current_progress = start_progress + int(processed_count[0] / total_attachments * download_progress)
                    if current_progress - last_update_progress[0] >= 1:
                        update_user_status(user_id, "processing", "processing_attachments", current_progress)
                        last_update_progress[0] = current_progress
                
                return {"attachment_id": attachment_id, "text": att_text}
        except Exception as e:
            log_error(f"Error processing attachment {attachment_id}: {e}")
            return None
    
    # Step 1: Process attachments in parallel (download + extract text)
    log_info(f"Processing {total_attachments} attachments in parallel...")
    thread_pool = get_thread_pool_manager()
    results = thread_pool.process_parallel(user_id, attachments, process_single_attachment)
    
    # Filter out None results
    processed_attachments = [r for r in results if r is not None]
    
    if not processed_attachments:
        log_warning("No attachments were successfully processed")
        return
    
    # Step 2: Batch embed all attachment texts
    log_info(f"Batch embedding {len(processed_attachments)} attachment texts...")
    update_user_status(user_id, "processing", "embedding_attachments", start_progress + download_progress)
    
    try:
        all_texts = [a["text"] for a in processed_attachments]
        embeddings = await batch_embed_gemini(all_texts)
        
        # Step 3: Prepare records for batch insert
        records = []
        for i, att_data in enumerate(processed_attachments):
            records.append({
                "id": f"{att_data['attachment_id']}_context",
                "user_id": user_id,
                "type": "attachment_context",
                "vector": embeddings[i],
                "email_id": None,
                "schedule_id": None,
                "file_id": None,
                "attachment_id": att_data["attachment_id"]
            })
        
        # Step 4: Batch insert all embeddings
        log_info(f"Batch inserting {len(records)} attachment embeddings...")
        batch_insert_supabase(supabase.table('embeddings'), records)
        
        log_info(f"Successfully created embeddings for {len(processed_attachments)} attachments")
        update_user_status(user_id, "processing", "embedding_attachments", end_progress)
        
    except Exception as e:
        log_error(f"Error in batch attachment embedding: {e}")
        raise


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
        
        # Step 4: Create embeddings for attachments (40-55%) - BATCH OPTIMIZED
        await create_attachment_embeddings(user_id, inserted_attachments, credentials, 40, 55)
        
        # Step 5: Create embeddings for emails (55-70%) - BATCH OPTIMIZED
        await create_email_embeddings(user_id, inserted_emails, 55, 70)
        
        # Step 6: Create embeddings for schedules (70-80%) - BATCH OPTIMIZED
        await create_schedule_embeddings(user_id, inserted_schedules, 70, 80)
        
        # Step 7: Create embeddings for files (80-100%) - BATCH OPTIMIZED
        await create_file_embeddings(user_id, inserted_files, credentials, 80, 100)
        
        # Step 8: Complete
        update_user_status(user_id, "active", "completed", 100)
        if progress_callback:
            progress_callback("completed", 100)
        
    except Exception as e:
        log_error(f"Error during initialization: {e}")
        results["error"] = str(e)
        update_user_status(user_id, "error", "failed", 0)
        if progress_callback:
            progress_callback("failed", 0)
    
    return results
