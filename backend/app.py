import calendar
from fastapi import FastAPI, Response, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import os
from dotenv import load_dotenv
import json
import requests
from datetime import datetime, timedelta
import threading
import asyncio
from typing import Dict, Optional
import time
from fastapi.responses import StreamingResponse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import base64

from retrieval_service import openai_api_utils
from retrieval_service.agent import REACT_SYSTEM_PROMPT
from retrieval_service.google_api_utils import initialize_user_data
from retrieval_service.supabase_utils import get_user_by_email, create_user
from fastapi.responses import StreamingResponse
import json
from retrieval_service.ocr_utils import init_model

load_dotenv()
print("Loading OCR model...")
init_model(['en'])
print("OCR model loaded.")

app = FastAPI()

# User info cache to reduce Google API calls
# Structure: {token_hash: {"user_info": {...}, "expires_at": timestamp}}
user_info_cache: Dict[str, Dict] = {}
CACHE_DURATION = 60  # Cache user info for 60 seconds
cache_lock = threading.Lock()

def get_token_hash(token: str) -> str:
    """Create a hash of the token for cache key"""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()

def get_cached_user_info(token: str) -> Optional[dict]:
    """Get user info from cache if valid"""
    with cache_lock:
        token_hash = get_token_hash(token)
        if token_hash in user_info_cache:
            cache_entry = user_info_cache[token_hash]
            if cache_entry["expires_at"] > time.time():
                return cache_entry["user_info"]
            else:
                # Expired, remove from cache
                del user_info_cache[token_hash]
        return None

def set_cached_user_info(token: str, user_info: dict):
    """Cache user info with expiration"""
    with cache_lock:
        token_hash = get_token_hash(token)
        user_info_cache[token_hash] = {
            "user_info": user_info,
            "expires_at": time.time() + CACHE_DURATION
        }

def clear_cached_user_info(token: str):
    """Clear cached user info for a token"""
    with cache_lock:
        token_hash = get_token_hash(token)
        if token_hash in user_info_cache:
            del user_info_cache[token_hash]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth configuration
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8080/auth/google/callback")

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# OAuth flow configuration
def get_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


@app.get("/")
async def root():
    return {"message": "Retrieval Service API"}


@app.get("/auth/google")
async def google_auth():
    """Initiate Google OAuth flow"""
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    response = RedirectResponse(url=authorization_url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, samesite="lax")
    return response


def run_initialization_in_background(user_id: str, credentials, debug_mode: bool = False):
    """Run initialization in a background thread"""
    def run_async_init():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_user_data(user_id, credentials, debug_mode=debug_mode))
        finally:
            loop.close()
    
    thread = threading.Thread(target=run_async_init, daemon=True)
    thread.start()


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = None, state: str = None):
    """Handle Google OAuth callback"""
    try:
        if not code:
            return JSONResponse({"error": "Authorization code not provided"}, status_code=400)
            
        stored_state = request.cookies.get("oauth_state")
        if not state or state != stored_state:
            return JSONResponse(
                {"error": "Invalid state parameter"}, status_code=400
            )

        # Manually fetch token to avoid scope validation issues
        try:
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            }
            token_response = requests.post(token_url, data=token_data)
            
            if token_response.status_code != 200:
                error_detail = token_response.text
                error_code = None
                try:
                    error_json = token_response.json()
                    error_code = error_json.get("error", "unknown")
                    error_detail = error_json.get("error_description", error_json.get("error", error_detail))
                except:
                    pass
                
                if error_code == "invalid_grant":
                    return JSONResponse(
                        {
                            "error": "Authorization code has already been used or is invalid. Please try signing in again.",
                            "error_code": error_code,
                            "detail": error_detail
                        }, 
                        status_code=400
                    )
                
                return JSONResponse(
                    {
                        "error": f"Token exchange failed: {error_detail}",
                        "error_code": error_code,
                        "status_code": token_response.status_code,
                        "response_text": token_response.text[:500]
                    }, 
                    status_code=500
                )
            
            token_info = token_response.json()
            
            returned_scopes = token_info.get("scope", "").split() if token_info.get("scope") else SCOPES
            credentials = Credentials(
                token=token_info["access_token"],
                refresh_token=token_info.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                scopes=returned_scopes,
            )
            if "expires_in" in token_info:
                credentials.expiry = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])
        except Exception as token_error:
            import traceback
            return JSONResponse(
                {
                    "error": f"Failed to fetch token: {str(token_error)}",
                    "traceback": traceback.format_exc()
                }, 
                status_code=500
            )

        if not credentials:
            return JSONResponse({"error": "Failed to obtain credentials"}, status_code=500)

        # Get user info
        try:
            from googleapiclient.discovery import build
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            user_email = user_info.get("email")
            user_name = user_info.get("name")
            
            # Check if user exists in database
            existing_user = get_user_by_email(user_email)
            
            if not existing_user:
                # Create new user
                new_user = create_user(user_email, user_name)
                if new_user:
                    # Check DEBUG_MODE environment variable
                    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
                    if debug_mode:
                        print("[DEBUG MODE ENABLED] Will process only latest 50 files")
                    
                    # Start initialization in background thread
                    run_initialization_in_background(new_user["uuid"], credentials, debug_mode=debug_mode)
        except Exception as e:
            print(f"Error checking/creating user: {e}")

        # Store tokens in HTTP-only cookie
        response = RedirectResponse(url="http://localhost:3000/?auth=success")
        response.set_cookie(
            key="access_token",
            value=credentials.token,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        response.set_cookie(
            key="refresh_token",
            value=credentials.refresh_token if credentials.refresh_token else "",
            httponly=True,
            samesite="lax",
            secure=False,
        )
        response.set_cookie(
            key="token_expiry",
            value=str(credentials.expiry) if credentials.expiry else "",
            httponly=True,
            samesite="lax",
            secure=False,
        )

        return response
    except Exception as e:
        import traceback
        return JSONResponse(
            {"error": str(e), "traceback": traceback.format_exc()}, 
            status_code=500
        )


def get_credentials_from_cookies(request: Request) -> Credentials | None:
    """Get credentials from cookies"""
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    token_expiry = request.cookies.get("token_expiry")

    if not access_token:
        return None

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token if refresh_token else None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )

    if token_expiry:
        try:
            from datetime import datetime
            credentials.expiry = datetime.fromisoformat(token_expiry)
        except:
            pass

    # Refresh token if expired
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(GoogleRequest())
        except:
            return None

    return credentials


@app.get("/api/profile")
async def get_profile(request: Request):
    """Get user profile using stored access token (with caching)"""
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        # Check cache first
        cached_info = get_cached_user_info(credentials.token)
        if cached_info:
            return cached_info
        
        # Cache miss - fetch from Google
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        # Cache the result
        set_cached_user_info(credentials.token, user_info)
        
        return user_info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check authentication status and initialization progress (with caching)"""
    credentials = get_credentials_from_cookies(request)
    if credentials:
        try:
            # Check cache first to avoid frequent Google API calls
            user_info = get_cached_user_info(credentials.token)
            
            if not user_info:
                # Cache miss - fetch from Google
                from googleapiclient.discovery import build
                service = build("oauth2", "v2", credentials=credentials)
                user_info = service.userinfo().get().execute()
                
                # Cache the result
                set_cached_user_info(credentials.token, user_info)
            
            # Get user from database to check initialization status
            user_email = user_info.get("email")
            db_user = get_user_by_email(user_email)
            
            if db_user:
                return {
                    "authenticated": True,
                    "user": user_info,
                    "status": db_user.get("status", "pending"),
                    "init_phase": db_user.get("init_phase", "not_started"),
                    "init_progress": db_user.get("init_progress", 0)
                }
            else:
                # User authenticated but not in database yet
                return {
                    "authenticated": True,
                    "user": user_info,
                    "status": "pending",
                    "init_phase": "not_started",
                    "init_progress": 0
                }
        except:
            return {"authenticated": False}
    return {"authenticated": False}


@app.post("/api/auth/logout")
async def logout(request: Request):
    """Logout, revoke token, clear cache, and clear cookies"""
    credentials = get_credentials_from_cookies(request)
    
    # Clear cache for this token
    if credentials and credentials.token:
        clear_cached_user_info(credentials.token)
        
        # Revoke the token with Google
        try:
            revoke_url = "https://oauth2.googleapis.com/revoke"
            revoke_data = {
                "token": credentials.token
            }
            revoke_response = requests.post(revoke_url, data=revoke_data)
        except Exception as e:
            pass
    
    # Clear cookies
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("token_expiry")
    response.delete_cookie("oauth_state")
    return response

@app.post("/api/chat")
async def chat(request: Request):
    """
    Stream chat responses with either RAG mode (default) or ReAct agent mode.
    
    Request body:
        - message: User's message
        - history: Chat history
        - mode: "rag" (default) or "agent"
    """
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        user_info = get_cached_user_info(credentials.token)
        if not user_info:
            from googleapiclient.discovery import build
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            set_cached_user_info(credentials.token, user_info)

        user_email = user_info.get("email")
        db_user = get_user_by_email(user_email)
        if not db_user or db_user.get("status") != "active":
            return JSONResponse({"error": "User not initialized"}, status_code=400)

        user_id = db_user["uuid"]

        body = await request.json()
        user_message = body.get("message", "")
        history = body.get("history", [])
        mode = body.get("mode", "rag")  # Default to RAG mode

        if not user_message:
            return JSONResponse({"error": "No message provided"}, status_code=400)

        now = datetime.now()
        weekday_name = calendar.day_name[now.weekday()]
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

        # Build system message based on mode
        if mode == "agent":
            system_content = REACT_SYSTEM_PROMPT + (
                f"\n\nCurrent date and time: {current_datetime} ({weekday_name}).\n"
                f"User info JSON (for your reference, do NOT leak sensitive fields verbatim):\n{user_info}\n\n"
                f"When you want to provide download links, use the format: [Title](URL)\n"
                f"The download link can be obtained from the ids of attachments or drive files:\n"
                f"- For Google Drive files, use http://localhost:8080/api/download/drive-direct/{{file_db_id}}\n"
                f"- For Gmail attachments, use http://localhost:8080/api/download/attachment-direct/{{attachment_db_id}}\n"
            )
        else:
            # RAG mode uses a simpler system prompt
            system_content = (
                f"You are a helpful assistant with access to the user's personal data.\n"
                f"Current date and time: {current_datetime} ({weekday_name}).\n\n"
                f"When you want to provide download links, use the format: [Title](URL)\n"
                f"The download link can be obtained from the ids of attachments or drive files:\n"
                f"- For Google Drive files, use http://localhost:8080/api/download/drive-direct/{{file_db_id}}\n"
                f"- For Gmail attachments, use http://localhost:8080/api/download/attachment-direct/{{attachment_db_id}}\n"
            )

        system_message = {
            "role": "system",
            "content": system_content,
        }

        messages = [system_message]

        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        async def generate():
            try:
                if mode == "agent":
                    # Use ReAct agent with tool calling
                    async for event in openai_api_utils.react_with_tools_stream(messages, user_id):
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                        await asyncio.sleep(0)
                else:
                    # Use direct RAG mode (default)
                    async for event in openai_api_utils.rag_direct_stream(messages, user_id, user_message, user_info):
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                        await asyncio.sleep(0)
            except Exception as e:
                import traceback
                print(f"[CHAT ERROR] {e}")
                print(traceback.format_exc())
                err = {"type": "error", "error": str(e)}
                yield "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        import traceback
        return JSONResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status_code=500,
        )


@app.get("/api/download/drive-direct/{file_id}")
async def download_drive_file_direct(file_id: str, request: Request):
    """
    Server-side Google Drive download using user OAuth
    Works for Google Docs, Sheets, Slides, binary files.
    """
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        service = build("drive", "v3", credentials=credentials)

        # 1. Get metadata to check type
        meta = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType"
        ).execute()

        name = meta["name"]
        mime_type = meta["mimeType"]

        # 2. Handle Workspace exports
        export_map = {
            "application/vnd.google-apps.document":
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.google-apps.spreadsheet":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.presentation":
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }

        # 3. Download
        if mime_type in export_map:
            request_drive = service.files().export_media(
                fileId=file_id,
                mimeType=export_map[mime_type]
            )
            download_name = f"{name}.docx"
        else:
            request_drive = service.files().get_media(fileId=file_id)
            download_name = name

        file_bytes = io.BytesIO()
        downloader = MediaIoBaseDownload(file_bytes, request_drive)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_bytes.seek(0)

        return StreamingResponse(
            file_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"'
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/download/attachment-direct/{attachment_id}")
async def download_attachment_direct(attachment_id: str, request: Request):
    """
    Server-side Gmail attachment download.
    Works for ANY attachment (images, PDF, docx, zip...).
    """
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        # 1. Look up attachment metadata in DB
        from retrieval_service.supabase_utils import supabase
        resp = supabase.table("attachments").select("*").eq("id", attachment_id).execute()

        if not resp.data:
            return JSONResponse({"error": "Attachment not found"}, status_code=404)

        attachment = resp.data[0]
        message_id = attachment["email_id"]
        filename = attachment.get("filename", "attachment")

        # 2. Connect to Gmail API
        service = build("gmail", "v1", credentials=credentials)

        # 3. Fetch attachment data
        att = service.users().messages().attachments().get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        ).execute()

        raw_data = att.get("data")
        if not raw_data:
            return JSONResponse({"error": "Attachment contains no data"}, status_code=500)

        # 4. Decode base64 URL-safe data
        file_bytes = base64.urlsafe_b64decode(raw_data)

        # 5. Return as downloadable file
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
