# Retrieval Service

Simple Google OAuth authentication service with FastAPI backend and vanilla HTML/CSS/JavaScript frontend.

## Setup

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment with Python 3.12:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install UV (if not already installed):
   ```bash
   pip install uv
   ```

4. Install dependencies using UV:
   ```bash
   uv pip install -e .
   ```

5. Ensure your `.env` file in the root directory contains:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   REDIRECT_URI=http://localhost:8080/auth/google/callback
   ```

   **Important**: Make sure to configure the authorized redirect URI in your Google Cloud Console:
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Edit your OAuth 2.0 Client ID
   - Add `http://localhost:8080/auth/google/callback` to Authorized redirect URIs

6. Run the backend server:
   ```bash
   python app.py
   ```
   Or using uvicorn directly:
   ```bash
   uvicorn app:app --reload --port 8080
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Serve the frontend using a simple HTTP server:
   ```bash
   # Using Python
   python3 serve.py
   
   # Or using Python's built-in server
   python3 -m http.server 3000
   
   # Or using Node.js (if installed)
   npx serve -p 3000
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:3000
   ```

## Features

- Google OAuth authentication with scopes:
  - Profile access
  - Email read access
  - Calendar read access
  - Drive read access
- Minimal black/white/grey UI design
- User info display (top-right)
- Success notification modal (bottom-right)
- Clean minimalist search bar
- Placeholder API endpoints for future token usage

## API Endpoints

- `GET /auth/google` - Initiate Google OAuth flow
- `GET /auth/google/callback` - OAuth callback handler
- `GET /api/auth/status` - Check authentication status
- `GET /api/profile` - Get user profile
- `GET /api/email` - Placeholder for email access
- `GET /api/calendar` - Placeholder for calendar access
- `GET /api/drive` - Placeholder for drive access
- `POST /api/auth/logout` - Logout and clear cookies
