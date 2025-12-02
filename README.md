# 
Simple Google OAuth authentication service with a FastAPI backend and a vanilla HTML/CSS/JavaScript frontend. Includes a full **user initialization flow** that fetches emails, schedules, files, and embeddings, with **parallel processing** and progress tracking.
Retrieval Service - Dual Mode RAG/Agent System

A powerful personal data retrieval system with Google OAuth authentication, featuring:
- **RAG Mode (Default)**: Fast, reliable retrieval using combined semantic, keyword, and fuzzy search
- **Agent Mode**: Smart ReAct agent with dynamic tool calling for complex queries
- Full user initialization flow with parallel processing
- Real-time streaming responses
- Support for Gmail, Google Calendar, and Google Drive

Simple Google OAuth authentication service with a FastAPI backend and a vanilla HTML/CSS/JavaScript frontend.
 Includes a full **user initialization flow** that fetches emails, schedules, files, and embeddings, with **parallel processing** and progress tracking.

------

## Setup

### Backend Setup

1. Navigate to the backend directory:

   ```
   cd backend
   ```

2. Create a virtual environment (Python 3.12):

   ```
   python3.12 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install UV:

   ```
   pip install uv
   ```

4. Install dependencies:

   ```
   uv pip install -e .
   ```

5. Ensure `.env` contains:

   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   REDIRECT_URI=http://localhost:8080/auth/google/callback
   
   # Parallel Processing
   MAX_WORKERS_PER_USER=5
   MAX_TOTAL_WORKERS=20
   DEBUG_MODE=true
   
   # Search Configuration
   SEARCH_TOP_K=5
   ```
   
   **SEARCH_TOP_K**: Number of top results to return from combined search (default: 5)

6. Run backend:

   ```
   uvicorn app:app --reload --port 8080
   ```

   Or:

   ```
   python app.py
   ```

------

### Frontend Setup

1. Navigate to frontend:

   ```
   cd frontend
   ```

2. Serve the UI:

   ```
   python3 serve.py
   # or
   python3 -m http.server 3000
   # or
   npx serve -p 3000
   ```

3. Open:

   ```
   http://localhost:3000
   ```

------

## Features

- Google OAuth (profile, Gmail, Calendar, Drive)
- Automatic **user initialization** on first sign-in
- Real-time **progress bar** (email → schedule → files → embeddings)
- Parallel background processing with global worker limits
- Minimal black/white/grey UI
- User profile display
- Success modal notification
- Placeholder search bar & API endpoints

------

# Initialization Flow

When a user signs in for the first time, the system automatically fetches and processes their Google data.

### High-Level Flow

```
User Sign In → OAuth → Check User → New? → Create User + Start Init
                                    Existing User → Continue
Status Check → Pending/Processing? → Show Progress UI → Active → Chat
```

------

## Components

### Backend (`backend/app.py`)

- After OAuth login:
  - New users → create DB entry (`status='pending'`) + start background init
  - Existing users → continue normally
- Background thread runs `initialize_user_data()` without blocking OAuth response
- `/api/auth/status` returns:
  - `status` (`pending`, `processing`, `active`, `error`)
  - `init_phase`
  - `init_progress`

------

## Initialization Steps (`google_api_utils.py`)

Each step updates `init_phase` and `init_progress` in the `users` table.

| Phase               | Progress | Description            |
| ------------------- | -------- | ---------------------- |
| not_started         | 0%       | Initial state          |
| fetching_emails     | 10%      | Gmail messages         |
| emails_fetched      | 20%      | Stored in DB           |
| fetching_schedules  | 30%      | Calendar events        |
| schedules_fetched   | 40%      | Stored in DB           |
| fetching_files      | 50%      | Google Drive tree      |
| files_fetched       | 60%      | Stored in DB           |
| embedding_emails    | 65%      | Email embeddings       |
| emails_embedded     | 75%      | Done                   |
| embedding_schedules | 80%      | Schedule embeddings    |
| schedules_embedded  | 85%      | Done                   |
| embedding_files     | 90%      | File embeddings        |
| files_embedded      | 95%      | Done                   |
| completed           | 100%     | Initialization success |
| failed              | 0%       | Error                  |

------

## Parallel Processing Architecture

### Global Thread Pool Manager

A singleton controller that enforces:

- **Per-user worker limit**: `MAX_WORKERS_PER_USER`
- **Global worker limit**: `MAX_TOTAL_WORKERS`
- Fully thread-safe worker acquisition/release
- Dynamic allocation per item
- Prevents any user from monopolizing the system

Used for:

- Email embeddings
- Schedule embeddings
- File downloads, extraction, summarization, embeddings

### DEBUG_MODE

When `DEBUG_MODE=true`:

- Processes **all emails**
- Processes **all calendar events**
- Processes **only 50 latest non-folder files**
- File traversal still reads full Drive structure

Message:

```
[DEBUG MODE ENABLED] Will process only latest 50 files
```

------

## Frontend (`script.js`, `chat.js`)

### Main Page

- On load:
  - Calls `/api/auth/status`
  - Shows initialization card if user is still processing
  - Polls backend every 2 sec for progress updates
  - Redirects to chat when complete

### Chat Page

- Only accessible when `status='active'`
- Redirects back otherwise

------

## Database Schema (Summary)

Important tables:

- `users`
  - `status`, `init_phase`, `init_progress`
- `emails`
- `schedules`
- `files`
- `embeddings`

------

## Retrieval Modes

The system supports two retrieval modes that can be toggled in the chat interface:

### RAG Mode (Default) - Fast & Reliable

**How it works:**
1. **Contextualizes follow-up questions**: If you have conversation history, automatically rewrites questions with pronouns (like "tell me more about it") into standalone search queries
2. Automatically performs combined search using:
   - **Semantic/Vector Search**: Finds results based on meaning and context
   - **Keyword Search**: Exact word matching for names, terms, etc.
   - **Fuzzy Search**: Handles typos and approximate matches
3. Deduplicates and ranks all results
4. Builds context from top results
5. Streams AI response with full context included

**Best for:**
- Quick queries about specific information
- When you know what you're looking for
- General questions about your data
- Most everyday use cases

**Advantages:**
- Faster response time
- More predictable results
- Always searches your data
- Lower token usage

### Agent Mode - Smart & Adaptive

**How it works:**
1. AI analyzes your question using ReAct (Reason + Act) framework
2. Decides which search tools to use (if any)
3. Can make multiple tool calls with different strategies
4. Refines search based on initial results
5. Streams response with reasoning visible

**Best for:**
- Complex multi-step queries
- When you need the AI to reason about what to search
- Questions requiring multiple data sources
- Exploratory searches

**Advantages:**
- Smarter search strategy selection
- Can handle complex queries better
- Shows its reasoning process
- Adapts search based on findings

### Switching Between Modes

Toggle between modes using the buttons at the top of the chat interface:
- **RAG (Fast)**: Default mode, always searches your data
- **Agent (Smart)**: AI decides when and how to search

## API Endpoints

- `GET /auth/google`
- `GET /auth/google/callback`
- `GET /api/auth/status`
- `GET /api/profile`
- `GET /api/email`
- `GET /api/calendar`
- `GET /api/drive`
- `POST /api/auth/logout`
- `POST /api/chat` (supports `mode` parameter: "rag" or "agent")
