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

load_dotenv()

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
        # The flow.fetch_token() method validates scopes strictly and raises errors
        # when Google returns additional previously-granted scopes
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
            
            # Check for errors and provide detailed error message
            if token_response.status_code != 200:
                error_detail = token_response.text
                error_code = None
                try:
                    error_json = token_response.json()
                    error_code = error_json.get("error", "unknown")
                    error_detail = error_json.get("error_description", error_json.get("error", error_detail))
                except:
                    pass
                
                # If it's an invalid_grant error, the code might have been used already
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
                        "response_text": token_response.text[:500]  # First 500 chars of response
                    }, 
                    status_code=500
                )
            
            token_info = token_response.json()
            
            # Create credentials from token response, accepting all returned scopes
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

        # Store tokens in HTTP-only cookie
        response = RedirectResponse(url="http://localhost:3000/?auth=success")
        response.set_cookie(
            key="access_token",
            value=credentials.token,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
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
            # Update cookies with new token
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


@app.get("/api/email")
async def get_email(request: Request):
    """Placeholder endpoint for email access"""
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # TODO: Implement email access using credentials
    return {"message": "Email access endpoint - to be implemented", "authenticated": True}


@app.get("/api/calendar")
async def get_calendar(request: Request):
    """Placeholder endpoint for calendar access"""
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # TODO: Implement calendar access using credentials
    return {"message": "Calendar access endpoint - to be implemented", "authenticated": True}


@app.get("/api/drive")
async def get_drive(request: Request):
    """Placeholder endpoint for drive access"""
    credentials = get_credentials_from_cookies(request)
    if not credentials:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # TODO: Implement drive access using credentials
    return {"message": "Drive access endpoint - to be implemented", "authenticated": True}


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check authentication status"""
    credentials = get_credentials_from_cookies(request)
    if credentials:
        try:
            from googleapiclient.discovery import build
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            return {"authenticated": True, "user": user_info}
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
            # Note: Google returns 200 even if token was already revoked
        except Exception as e:
            # Log error but continue with logout
            pass
    
    # Clear cookies
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("token_expiry")
    response.delete_cookie("oauth_state")
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

