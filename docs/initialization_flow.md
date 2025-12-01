# Initialization Flow Documentation

## Overview
This document describes the user initialization flow implemented for the Retrieval Service. When a user first signs in with Google, their emails, calendar events, and files are automatically fetched and processed.

## Flow Diagram

```
User Sign In → Google OAuth → Check User in DB → New User? → Create User → Start Background Init
                                                  ↓
                                            Existing User → Continue to App
                                                  ↓
                                            Status Check → Pending/Processing? → Show Progress UI
                                                  ↓
                                            Active? → Redirect to Chat
```

## Components

### Backend (`backend/app.py`)

1. **OAuth Callback Enhancement**
   - After successful Google OAuth, checks if user exists in Supabase
   - If new user: creates user record with `status='pending'` and starts background initialization
   - If existing user: proceeds normally

2. **Background Initialization Thread**
   - Runs `initialize_user_data()` in a separate daemon thread
   - Prevents blocking the OAuth callback response
   - Updates progress in database throughout the process

3. **Enhanced `/api/auth/status` Endpoint**
   - Returns authentication status
   - Includes initialization status: `status`, `init_phase`, `init_progress`
   - Frontend polls this endpoint to track progress

### Initialization Logic (`backend/retrieval_service/google_api_utils.py`)

The `initialize_user_data()` function performs the following steps:

1. **Fetch Emails** (0-20%)
   - Fetches last 90 days of emails from Gmail
   - Inserts into `emails` table

2. **Fetch Schedules** (20-40%)
   - Fetches all future calendar events
   - Inserts into `schedules` table

3. **Fetch Files** (40-60%)
   - Recursively traverses Google Drive
   - Inserts into `files` table

4. **Embed Emails** (60-75%)
   - Creates 3 types of embeddings per email:
     - `email_sum`: Full email information
     - `email_context`: Thread context
     - `email_title`: Subject and sender/receiver info
   - Stores in `embeddings` table

5. **Embed Schedules** (75-85%)
   - Creates `schedule_context` embeddings
   - Includes event details, location, time

6. **Embed Files** (85-100%)
   - Downloads each file temporarily
   - Calls `process_file_by_type()` (placeholder for now)
   - Creates `file_context` embeddings with file summary
   - Updates file summary in database

Each step updates the `init_phase` and `init_progress` columns in the `users` table.

### Database Schema (`docs/db_init.sql`)

Key tables:
- `users`: Stores user info and initialization status
  - `status`: 'pending', 'processing', 'active', 'error'
  - `init_phase`: Current phase name
  - `init_progress`: 0-100 percentage
- `emails`, `schedules`, `files`: Store fetched data
- `embeddings`: Store all embeddings with type and references

### Frontend (`frontend/script.js`, `frontend/chat.js`)

1. **Main Page (`index.html`)**
   - On load, checks auth status
   - If authenticated and `status='pending'` or `'processing'`:
     - Shows initialization UI with progress bar
     - Polls `/api/auth/status` every 2 seconds
     - Updates progress bar and phase message
   - If `status='active'`: Redirects to chat page
   - If `status='error'`: Shows error message

2. **Chat Page (`chat.html`)**
   - Checks auth status on load
   - Only allows access if `status='active'`
   - Redirects to main page if not initialized
   - Currently shows placeholder for chat functionality

### Styling (`frontend/style.css`)

Added styles for:
- `.initialization-section`: Container for init UI
- `.init-card`: Card displaying progress
- `.progress-bar` and `.progress-fill`: Visual progress indicator
- `.init-phase`: Current phase message
- Error states with red styling

## User Experience

### First-Time User
1. User clicks "Sign in with Google"
2. Completes Google OAuth
3. Redirected to main page with success notification
4. Initialization UI appears automatically
5. Progress bar shows real-time progress (0-100%)
6. Phase messages update: "Fetching emails...", "Processing files...", etc.
7. When complete (100%), automatically redirects to chat page

### Returning User
1. User clicks "Sign in with Google"
2. Completes Google OAuth
3. System checks status
4. If `active`: Immediately redirects to chat page
5. If still `processing`: Shows current progress
6. If `error`: Shows error with option to sign out and retry

## Progress Phases

| Phase | Progress | Description |
|-------|----------|-------------|
| `not_started` | 0% | Initial state |
| `starting` | 0% | Beginning initialization |
| `fetching_emails` | 10% | Fetching Gmail messages |
| `emails_fetched` | 20% | Emails retrieved |
| `fetching_schedules` | 30% | Fetching calendar events |
| `schedules_fetched` | 40% | Events retrieved |
| `fetching_files` | 50% | Fetching Drive files |
| `files_fetched` | 60% | Files retrieved |
| `embedding_emails` | 65% | Creating email embeddings |
| `emails_embedded` | 75% | Email embeddings complete |
| `embedding_schedules` | 80% | Creating schedule embeddings |
| `schedules_embedded` | 85% | Schedule embeddings complete |
| `embedding_files` | 90% | Creating file embeddings |
| `files_embedded` | 95% | File embeddings complete |
| `completed` | 100% | Initialization successful |
| `failed` | 0% | Error occurred |

## Error Handling

- Network errors during fetch: Logged, initialization marked as `error`
- Embedding errors: Logged and skipped, doesn't halt process
- File download errors: Logged and skipped
- User can sign out and retry if initialization fails

## Future Enhancements

1. **Resume capability**: Allow resuming interrupted initialization
2. **Incremental updates**: Fetch only new data after initial load
3. **Background refresh**: Periodic updates in the background
4. **File processing**: Implement actual file content extraction and summarization
5. **Progress notifications**: Real-time push notifications
6. **Initialization controls**: Pause/resume initialization

## Testing

To test the initialization flow:

1. Ensure database schema is applied
2. Start backend: `cd backend && uvicorn app:app --reload --port 8080`
3. Start frontend: `cd frontend && python serve.py`
4. Sign in with a new Google account
5. Observe initialization progress
6. Verify redirect to chat page upon completion
7. Check database for populated data

## Troubleshooting

**Initialization stuck at certain phase:**
- Check backend logs for errors
- Verify Google API credentials and scopes
- Check Supabase connection

**Progress not updating:**
- Verify frontend is polling `/api/auth/status`
- Check network tab for failed requests
- Verify user status in database

**Redirect not working:**
- Check `status` field in database
- Verify frontend redirect logic
- Check browser console for errors
