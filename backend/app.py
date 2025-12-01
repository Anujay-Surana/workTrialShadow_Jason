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

from retrieval_service.google_api_utils import initialize_user_data
from retrieval_service.supabase_utils import get_user_by_email, create_user, update_user_status
from retrieval_service.search_utils import combined_search, get_context_from_results
from retrieval_service.openai_api_utils import chat_stream, summarize
from fastapi.responses import StreamingResponse
import json
from retrieval_service.ocr_utils import init_model

load_dotenv()
print("Loading OCR model...")
init_model(['en'])
print("OCR model loaded.")

app = FastAPI()

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


def run_initialization_in_background(user_id: str, credentials):
    """Run initialization in a background thread"""
    def run_async_init():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_user_data(user_id, credentials))
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
                    # Start initialization in background thread
                    run_initialization_in_background(new_user["uuid"], credentials)
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
    """Get user profile using stored access token"""
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check authentication status and initialization progress"""
    credentials = get_credentials_from_cookies(request)
    if credentials:
        try:
            from googleapiclient.discovery import build
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            
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
    """Logout, revoke token, and clear cookies"""
    credentials = get_credentials_from_cookies(request)
    
    # Revoke the token with Google if we have credentials
    if credentials and credentials.token:
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
    Stream chat responses with RAG (Retrieval Augmented Generation).
    Expects JSON: { "message": str, "history": [ {role: str, content: str}, ... ] }
    """
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        # Get user info
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        user_email = user_info.get("email")
        
        # Get user from database
        db_user = get_user_by_email(user_email)
        if not db_user or db_user.get("status") != "active":
            return JSONResponse({"error": "User not initialized"}, status_code=400)
        
        user_id = db_user["uuid"]
        
        # Parse request body
        body = await request.json()
        user_message = body.get("message", "")
        history = body.get("history", [])
        
        if not user_message:
            return JSONResponse({"error": "No message provided"}, status_code=400)
        
        # Build search query
        search_query = user_message
        
        # If there's history, summarize it as context
        if history:
            # Get last few messages for context
            recent_history = history[-4:] if len(history) > 4 else history
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
            try:
                context_summary = summarize(history_text, max_chars=2000)
                search_query = f"{context_summary}\n\nNew message: {user_message}"
            except:
                # If summarization fails, just use the user message
                pass
        
        # Perform combined search (vector only, not keyword/fuzzy for chat)
        search_results = combined_search(
            user_id=user_id,
            query=search_query,
            vector_weight=1.0,
            keyword_weight=0.0,
            fuzzy_weight=0.0,
            top_k=5
        )
        
        # Get context and references from search results
        context_str, references = get_context_from_results(user_id, search_results)
        
        # Get current date and time
        from datetime import datetime
        import calendar
        now = datetime.now()
        weekday_name = calendar.day_name[now.weekday()]
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Build system message with context
        system_message = {
            "role": "system",
            "content": (
                f"You are a helpful assistant with access to the user's emails, calendar events, and files. "
                f"Current date and time: {current_datetime} ({weekday_name}). "
                f"Use the provided context to answer questions accurately. "
                f"If the context doesn't contain relevant information, say so honestly."
            )
        }
        
        # Build user message with context
        enhanced_user_message = user_message
        if context_str:
            enhanced_user_message = f"Context:\n{context_str}\n\n---\n\nUser question: {user_message}"
        
        # Build messages for chat
        messages = [system_message]
        
        # Add history (without context, as it's already in the enhanced message)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current enhanced user message
        messages.append({"role": "user", "content": enhanced_user_message})
        
        # Stream response
        async def generate():
            try:
                # Stream chat response
                for chunk in chat_stream(messages):
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                
                # Send references at the end
                if references:
                    yield f"data: {json.dumps({'type': 'references', 'references': references})}\n\n"
                
                # Send done signal
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    except Exception as e:
        import traceback
        return JSONResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
