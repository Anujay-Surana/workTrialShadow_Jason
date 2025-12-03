# Memory Retrieval API - Architecture

## Overview

A personal memory retrieval system that indexes and searches across your emails, calendar events, and files using semantic search and AI-powered context generation.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Login   │→ │  Onboarding  │→ │   Main App (Index)   │  │
│  │  Page    │  │   Progress   │  │  - Retrieval UI      │  │
│  └──────────┘  └──────────────┘  │  - Delete Account    │  │
│                                   └──────────────────────┘  │
│                                   ┌──────────────────────┐  │
│                                   │   Monitor Dashboard  │  │
│                                   │  - API Usage Stats   │  │
│                                   │  - Risk Monitoring   │  │
│                                   └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  API Endpoints                        │   │
│  │  /auth/google          - OAuth login                 │   │
│  │  /api/auth/status      - Check auth & init status   │   │
│  │  /api/auth/logout      - Logout                      │   │
│  │  /api/auth/account     - Delete account (DELETE)    │   │
│  │  /api/memory/retrieval - Query personal data        │   │
│  │  /health/status        - Health & monitoring         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│   Google     │  │    Supabase      │  │   AI APIs    │
│   APIs       │  │    Database      │  │              │
│              │  │                  │  │              │
│ - Gmail      │  │ - Users          │  │ - OpenAI     │
│ - Calendar   │  │ - Emails         │  │   (GPT-4o)   │
│ - Drive      │  │ - Schedules      │  │              │
│              │  │ - Files          │  │ - Gemini     │
│              │  │ - Attachments    │  │   (Embedding)│
│              │  │ - Embeddings     │  │              │
└──────────────┘  └──────────────────┘  └──────────────┘
```

## Core Components

### 1. Authentication & User Management

**OAuth Flow:**
1. User clicks "Sign in with Google"
2. Redirects to Google OAuth consent screen
3. Callback receives authorization code
4. Exchange for access/refresh tokens
5. Store tokens in HTTP-only cookies
6. Create user record in database

**User States:**
- `pending` - User created, initialization not started
- `processing` - Data fetching and embedding in progress
- `active` - Ready to use
- `error` - Initialization failed

### 2. Data Initialization Pipeline

**Process Flow:**
```
User Login → Create User → Background Thread
                              ↓
                    ┌─────────────────────┐
                    │  Fetch from Google  │
                    │  - Emails (Gmail)   │
                    │  - Events (Calendar)│
                    │  - Files (Drive)    │
                    └─────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  Process Content    │
                    │  - OCR for images   │
                    │  - Parse documents  │
                    │  - Extract text     │
                    └─────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  Batch Embedding    │
                    │  - Gemini API       │
                    │  - 1536 dimensions  │
                    │  - 100 texts/batch  │
                    └─────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  Store in Database  │
                    │  - Batch insert     │
                    │  - 1000 records/batch│
                    └─────────────────────┘
```

**Optimization Techniques:**
- **Parallel Processing**: ThreadPoolExecutor for I/O operations
- **Batch Embedding**: 100 texts per Gemini API call
- **Batch Database Insert**: 1000 records per Supabase call
- **Batch Email Queries**: Single query for all email info
- **Progress Tracking**: Real-time updates every 1-2%

### 3. Retrieval Modes

#### RAG Mode (Fast)
```
Query → Embedding → Vector Search → Top-K Results
                                         ↓
                              Build Context Summary
                                         ↓
                              LLM Generates Response
                                         ↓
                              Return Content + References
```

#### Mixed Mode (Flexible)
```
Query → LLM with Tools
         ↓
    ┌────┴────┐
    │ Tool    │ (Multiple iterations)
    │ Calls   │
    └────┬────┘
         ↓
    Search Tools:
    - vector_search
    - keyword_search
    - fuzzy_search
         ↓
    Aggregate Results
         ↓
    LLM Final Response
         ↓
    Return Content + References
```

#### ReAct Mode (Reasoning)
```
Query → ReAct Agent
         ↓
    Thought → Action → Observation
         ↓         ↓         ↓
    Reasoning  Execute   Results
         ↓      Tool      ↓
    Loop until Answer Found
         ↓
    Final Response
         ↓
    Return Content + Process Steps
```

### 4. Search System

**Vector Search:**
- Embedding model: `gemini-embedding-001` (1536 dimensions)
- Similarity: Cosine similarity via Supabase pgvector
- Top-K: Configurable (default 5)

**Keyword Search:**
- PostgreSQL full-text search
- Supports: emails, schedules, files
- Ranking by relevance

**Fuzzy Search:**
- Levenshtein distance
- Handles typos and variations
- Configurable threshold

**Reference Search:**
- Direct lookup by ID
- Supports all data types

### 5. Database Schema

**Users Table:**
```sql
- uuid (PK)
- email
- name
- status (pending/processing/active/error)
- init_phase (current initialization step)
- init_progress (0-100)
- created_at
```

**Emails Table:**
```sql
- id (PK)
- user_id (FK)
- thread_id
- subject
- body
- from_user
- to_user
- cc, bcc
- date
```

**Schedules Table:**
```sql
- id (PK)
- user_id (FK)
- summary
- description
- location
- start_time
- end_time
- creator_email
- organizer_email
```

**Files Table:**
```sql
- id (PK)
- user_id (FK)
- name
- path
- mime_type
- size
- modified_time
- summary
```

**Attachments Table:**
```sql
- id (PK)
- user_id (FK)
- email_id (FK)
- filename
- mime_type
- size
- summary
```

**Embeddings Table:**
```sql
- id (PK)
- user_id (FK)
- type (email_sum/email_context/email_title/schedule/file/attachment)
- vector (1536 dimensions)
- email_id (FK, nullable)
- schedule_id (FK, nullable)
- file_id (FK, nullable)
- attachment_id (FK, nullable)
```

### 6. Monitoring System

**Metrics Tracked:**
- Total requests per API (OpenAI, Google, Gemini, Supabase)
- Error count and rate
- Retry count and rate
- Request timeline (20 buckets per time range)

**Risk Calculation:**
```
Risk = Error Risk (0-40) + Retry Risk (0-30) + Volume Risk (0-30)

Error Risk = min(40, error_rate × 100)
Retry Risk = min(30, retry_rate × 60)
Volume Risk = API-specific thresholds
```

**Time Ranges:**
- 10 minutes (primary for risk)
- 1 hour
- 1 day
- 1 week
- 1 month
- 1 year

### 7. Error Handling & Retry Logic

**Retry Strategy:**
- Exponential backoff: 2s, 4s, 8s
- Max retries: 3 attempts
- Retryable errors:
  - Connection errors (timeout, disconnected)
  - Server errors (503, 504)
  - Rate limits (429)

**Applied To:**
- Google API calls (Gmail, Calendar, Drive)
- Gemini API calls (embeddings)
- Supabase database operations
- OpenAI API calls (chat completions)

### 8. File Processing

**Supported File Types:**

**Google Workspace Files (Export):**
- Google Docs → DOCX
- Google Sheets → XLSX
- Google Slides → PPTX
- Google Drawings → PDF
- Google Colab → Jupyter Notebook (.ipynb)

**Binary Files (Download):**
- Images: PNG, JPG, GIF (OCR with EasyOCR)
- Documents: PDF, DOCX, TXT
- Spreadsheets: XLSX, CSV
- Others: Direct download

**Processing Pipeline:**
1. Detect file type (mime_type)
2. Download or export appropriately
3. Extract text content
4. Generate summary (if needed)
5. Create embedding
6. Store in database

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: Supabase (PostgreSQL + pgvector)
- **AI Models**:
  - OpenAI GPT-4o (text generation)
  - Google Gemini (embeddings, 1536d)
- **APIs**: Google OAuth, Gmail, Calendar, Drive
- **Processing**: EasyOCR, python-docx, PyPDF2

### Frontend
- **HTML/CSS/JavaScript** (Vanilla)
- **Pages**:
  - login.html - Authentication
  - onboarding.html - Initialization progress
  - index.html - Main retrieval interface
  - monitor.html - API monitoring dashboard

### Infrastructure
- **Logging**: Custom logging system with file rotation
- **Monitoring**: CSV-based metrics tracking
- **Threading**: ThreadPoolExecutor for parallel processing
- **Batch Processing**: Custom batch utilities

## Security

**Authentication:**
- OAuth 2.0 with Google
- HTTP-only cookies for token storage
- Token refresh on expiry

**Data Privacy:**
- User data isolated by user_id
- All queries filtered by authenticated user
- Account deletion removes all associated data

**API Keys:**
- Stored in `.env` file (not committed)
- Required keys:
  - GOOGLE_CLIENT_ID
  - GOOGLE_CLIENT_SECRET
  - OPENAI_API_KEY
  - GEMINI_API_KEY
  - SUPABASE_URL
  - SUPABASE_KEY

## Performance Optimizations

1. **Batch Operations**: Reduce API calls by 99%
2. **Parallel Processing**: Concurrent I/O operations
3. **Connection Pooling**: Reuse database connections
4. **Caching**: User info cached during session
5. **Lazy Loading**: Load data only when needed
6. **Progress Tracking**: Efficient status updates

## Deployment Considerations

**Environment Variables:**
- All sensitive data in `.env`
- Example provided in `.env.example`

**Database Setup:**
- Run `docs/db_init.sql` to create schema
- Enable pgvector extension
- Configure connection pooling

**API Limits:**
- OpenAI: ~3500 requests/minute
- Google: ~10000 requests/minute
- Gemini: Monitor via risk system

**Scaling:**
- Horizontal: Multiple backend instances
- Vertical: Increase worker threads
- Database: Supabase auto-scales

## Future Enhancements

- [ ] Real-time sync with Google services
- [ ] Support for more file types
- [ ] Advanced search filters
- [ ] Conversation history
- [ ] Multi-language support
- [ ] Mobile app
- [ ] Webhook notifications
- [ ] Export functionality
