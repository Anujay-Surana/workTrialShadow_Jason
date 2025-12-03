# Memory Retrieval Module

A backend memory retrieval service that provides context summaries from personal data (Gmail, Google Calendar, Google Drive). Designed as a microservice for AI agents to query user's personal information.

## Features

- **Google OAuth Authentication**: Secure access to Gmail, Calendar, and Drive
- **Automatic Data Indexing**: First-time initialization fetches and indexes all user data
- **Three Retrieval Modes**:
  - **RAG (Default)**: Fast, reliable context extraction using combined search
  - **Mixed**: RAG with optional AI tool calling
  - **ReAct Agent**: Full reasoning loop with dynamic search strategies
- **AI-Driven Reference Selection**: LLM intelligently selects relevant sources
- **Third-Person Context**: Outputs objective summaries, not conversational responses
- **Complete Reference Data**: Returns full database rows for maximum flexibility
- **Parallel Processing**: Efficient background indexing with worker limits
- **Batch Processing Optimization**: 99.87% reduction in API calls during initialization
- **Rate Limit Monitoring**: Real-time tracking with risk assessment and visualization
- **Automatic Retry Logic**: Exponential backoff for failed requests

## Architecture

```
┌─────────────┐
│   Client    │
│  (Agent)    │
└──────┬──────┘
       │
       │ POST /api/memory/retrieval
       │ { "query": "...", "mode": "rag" }
       ▼
┌─────────────────────┐
│  Memory Retrieval   │
│  Module (FastAPI)   │
└──────┬──────────────┘
       │
       ├─► Vector Search (Semantic)
       ├─► Keyword Search (Exact)
       ├─► Fuzzy Search (Typo-tolerant)
       │
       ▼
┌─────────────────────┐
│   Supabase DB       │
│  (PostgreSQL+pgvector)│
└─────────────────────┘
```

## Setup

### Prerequisites

- Python 3.12+
- Google Cloud Project with OAuth credentials
- Supabase account (or PostgreSQL with pgvector)
- OpenAI API key
- Google Gemini API key

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install UV package manager:
   ```bash
   pip install uv
   ```

4. Install dependencies:
   ```bash
   uv pip install -e .
   ```

5. Configure environment variables in `.env`:
   ```env
   # Google OAuth
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   REDIRECT_URI=http://localhost:8080/auth/google/callback
   
   # API Keys
   OPENAI_API_KEY=your_openai_key
   GEMINI_API_KEY=your_gemini_key
   
   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   
   # Parallel Processing
   MAX_WORKERS_PER_USER=5
   MAX_TOTAL_WORKERS=5
   
   # Debug Mode (process only 50 most recent files)
   DEBUG_MODE=true
   
   # Search Configuration
   SEARCH_TOP_K=10
   
   # Output Control
   VERBOSE_OUTPUT=false
   ```

6. Run the backend:
   ```bash
   uvicorn app:app --reload --port 8080
   ```

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Serve the UI:
   ```bash
   python3 serve.py
   # or
   python3 -m http.server 3000
   ```

3. Open browser:
   ```
   http://localhost:3000/login.html
   ```

### Frontend Pages

- **login.html** - Google OAuth authentication
- **onboarding.html** - Real-time initialization progress (auto-redirects)
- **index.html** - Main retrieval interface with delete account option
- **monitor.html** - API usage monitoring and risk dashboard

## API Usage

### Authentication

First, authenticate via Google OAuth:
```
GET http://localhost:8080/auth/google
```

### Memory Retrieval

```http
POST /api/memory/retrieval
Content-Type: application/json

{
  "query": "emails from John about project deadline",
  "mode": "rag"  // optional: "rag" | "mixed" | "react"
}
```

### Response Format

```json
{
  "content": "User has 2 emails from John about project X.\n- Deadline: Dec 15, 2024\n- Budget approved: $50K\n- Next meeting: Dec 10 at 3PM",
  "references": [
    {
      "type": "email",
      "id": "msg_123",
      "user_id": "uuid",
      "thread_id": "thread_456",
      "body": "Full email body...",
      "subject": "Project X Budget Approval",
      "from_user": "John Smith <john@company.com>",
      "to_user": "team@company.com",
      "cc": "manager@company.com",
      "bcc": null,
      "date": "2024-11-28T14:30:00Z"
    }
  ]
}
```

## Retrieval Modes

### RAG Mode (Default)
- **Speed**: Fastest (~1-2s)
- **Method**: Combined semantic + keyword + fuzzy search
- **Best for**: Most queries, production use
- **Output**: Short context summary with selected references

### Mixed Mode
- **Speed**: Medium (~1-3s)
- **Method**: RAG + optional AI tool calling
- **Best for**: Complex queries requiring reasoning
- **Output**: Context summary with tool-selected references

### ReAct Mode
- **Speed**: Slower (~2-5s)
- **Method**: Full Thought-Action-Observation loop
- **Best for**: Debugging, understanding retrieval process
- **Output**: Context summary with reasoning steps

## Initialization Flow

On first sign-in, the system automatically indexes user data:

```
User Sign In → OAuth → Create User → Background Initialization
                                    ↓
                        ┌───────────────────────────┐
                        │ 1. Fetch Gmail (10-20%)   │
                        │ 2. Fetch Calendar (30-40%)│
                        │ 3. Fetch Drive (50-60%)   │
                        │ 4. Embed Emails (65-75%)  │
                        │ 5. Embed Events (80-85%)  │
                        │ 6. Embed Files (90-95%)   │
                        │ 7. Complete (100%)        │
                        └───────────────────────────┘
                                    ↓
                        Status: active → Ready to use
```

Progress is tracked in real-time on the frontend.

## Batch Processing Optimization

The system uses advanced batch processing to minimize API calls and maximize performance:

### Standard Batch Processing (Initialization)

During user initialization, all embeddings are processed in batches:

- **Email embeddings**: 3N calls → ⌈3N/2048⌉ calls (99.95% reduction)
- **Schedule embeddings**: N calls → ⌈N/2048⌉ calls (99.95% reduction)
- **File embeddings**: N calls → ⌈N/2048⌉ calls (99.95% reduction)
- **Attachment embeddings**: N calls → ⌈N/2048⌉ calls (99.95% reduction)

**Example**: 1000 emails → 2 API calls instead of 3000 (99.93% reduction)

### Performance Impact

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| 1000 emails init | 3000 calls, 2 min | 2 calls, 10s | 12x faster |
| Rate limit risk | High | Minimal | Significant |



## Database Schema

### Core Tables

- **users**: User accounts and initialization status
- **emails**: Gmail messages with full metadata
- **schedules**: Google Calendar events
- **files**: Google Drive files with paths
- **attachments**: Email attachments
- **embeddings**: Vector embeddings for semantic search

See `docs/db_init.sql` for complete schema.

## Key Features

### Third-Person Context
Responses describe what exists in the data, not conversational answers:
- ✅ "User has 2 emails about project X"
- ❌ "I found 2 emails about project X"

### AI-Driven References
LLM selects which sources are actually relevant:
1. Search returns all potentially relevant documents
2. LLM receives full context
3. LLM outputs IDs of sources it used
4. System fetches complete metadata for those IDs only

### Complete Reference Data
Returns entire database rows, not just selected fields:
- All email fields (body, subject, from, to, cc, bcc, date, etc.)
- All calendar fields (summary, description, location, times, etc.)
- All file fields (name, path, size, modified_time, metadata, etc.)

### Parallel Processing
- Per-user worker limits prevent resource monopolization
- Global worker pool for efficient processing
- Thread-safe worker acquisition/release
- Configurable via `MAX_WORKERS_PER_USER` and `MAX_TOTAL_WORKERS`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VERBOSE_OUTPUT` | `false` | Enable detailed logging |
| `DEBUG_MODE` | `false` | Process only 50 most recent files |
| `SEARCH_TOP_K` | `10` | Number of search results to return |
| `MAX_WORKERS_PER_USER` | `5` | Max parallel workers per user |
| `MAX_TOTAL_WORKERS` | `5` | Max total parallel workers |

### Debug Mode

When `DEBUG_MODE=true`:
- Processes all emails and calendar events
- Processes only 50 most recent files (for faster testing)
- Full Drive structure is still traversed

## API Documentation

### Interactive API Docs

Once the backend is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs - Try out APIs directly in the browser
- **ReDoc**: http://localhost:8080/redoc - Clean, readable API reference

The documentation includes:
- Complete request/response schemas
- Example requests and responses
- Authentication requirements
- Error codes and descriptions
- Try-it-out functionality

### Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Simple health check ping |
| `/health/status` | GET | Detailed status with monitoring |
| `/auth/google` | GET | Initiate OAuth flow |
| `/auth/google/callback` | GET | OAuth callback |
| `/api/auth/status` | GET | Check auth status |
| `/api/auth/logout` | POST | Logout |
| `/api/memory/retrieval` | POST | Query user's memory |
| `/api/user/status` | GET | Get user status |
| `/api/user/delete` | DELETE | Delete user data |
| `/api/download/drive-direct/{file_id}` | GET | Download Drive file |
| `/api/download/attachment-direct/{attachment_id}` | GET | Download attachment |

## Example Queries

```
"emails from John about project deadline"
"calendar events this week"
"documents about budget planning"
"attachments from Sarah in November"
"meetings with the team next week"
```

## Response Examples

### With Results
```json
{
  "content": "User has 3 emails from John about project X.\n- Deadline: Dec 15, 2024\n- Budget approved: $50K\n- Next meeting: Dec 10 at 3PM",
  "references": [...]
}
```

### No Results
```json
{
  "content": "No relevant information exists in user's personal data.",
  "references": []
}
```

## Development

### Project Structure
```
.
├── backend/
│   ├── app.py                          # FastAPI application
│   ├── models.py                       # Pydantic models
│   ├── retrieval_service/
│   │   ├── __init__.py                 # Public interface exports
│   │   ├── core/                       # Core business logic
│   │   │   ├── agent.py                # Tool definitions and prompts
│   │   │   ├── rag.py                  # RAG retrieval logic
│   │   │   └── react.py                # ReAct agent implementation
│   │   ├── api/                        # External API integrations
│   │   │   ├── openai_client.py        # OpenAI API client
│   │   │   ├── gemini_client.py        # Gemini API client (embeddings)
│   │   │   └── google_client.py        # Google API client
│   │   ├── search/                     # Search and retrieval
│   │   │   ├── vector.py               # Vector search
│   │   │   ├── keyword.py              # Keyword search
│   │   │   ├── fuzzy.py                # Fuzzy search
│   │   │   └── reference.py            # Reference parsing
│   │   ├── data/                       # Data access layer
│   │   │   ├── database.py             # Supabase operations
│   │   │   └── initialization.py       # User data initialization
│   │   ├── processing/                 # Document processing
│   │   │   ├── documents.py            # Document summarization
│   │   │   ├── parsers.py              # Document parsing
│   │   │   └── ocr.py                  # OCR text extraction
│   │   ├── infrastructure/             # Infrastructure
│   │   │   ├── logging.py              # Unified logging system
│   │   │   ├── monitoring.py           # Rate limit monitoring
│   │   │   ├── batch.py                # Batch processing
│   │   │   └── threading.py            # Thread pool management
│   │   └── utils/                      # Common utilities
│   └── pyproject.toml
├── frontend/
│   ├── index.html                      # Landing page
│   ├── test.html                       # API test interface
│   ├── monitor.html                    # Rate limit monitoring
│   ├── script.js                       # Auth logic
│   ├── style.css                       # Minimalist styling
│   └── serve.py
├── docs/
│   └── db_init.sql                     # Database schema
└── README.md
```

### Module Organization

The `retrieval_service` package is organized by responsibility:

- **core/**: Core business logic (RAG, ReAct agents)
- **api/**: External API clients (OpenAI, Gemini, Google)
- **search/**: Search strategies (vector, keyword, fuzzy, reference)
- **data/**: Data access and initialization
- **processing/**: Document processing and parsing
- **infrastructure/**: Cross-cutting concerns (logging, monitoring, batch processing)
- **utils/**: Common utilities

### Import Examples

```python
# Core functionality
from retrieval_service.core.rag import combined_search, build_rag_prompt
from retrieval_service.core.react import react_agent_direct

# API clients
from retrieval_service.api.openai_client import rag_direct, chat_completion
from retrieval_service.api.gemini_client import embed_text
from retrieval_service.api.google_client import fetch_gmail_messages

# Search
from retrieval_service.search import execute_search_tool
from retrieval_service.search.vector import vector_search
from retrieval_service.search.reference import fetch_full_reference

# Data access
from retrieval_service.data.database import get_user_by_email, insert_emails
from retrieval_service.data.initialization import initialize_user_data

# Processing
from retrieval_service.processing.documents import summarize_doc
from retrieval_service.processing.parsers import extract_text_from_pdf
from retrieval_service.processing.ocr import extractOCR

# Infrastructure
from retrieval_service.infrastructure.logging import log_info, log_error
from retrieval_service.infrastructure.monitoring import monitor
from retrieval_service.infrastructure.batch import batch_embed_gemini
```

For detailed architecture documentation, see [docs/Architecture.md](docs/Architecture.md).

### Running Tests

Use the test interface at `http://localhost:3000/test.html` to:
- Test different retrieval modes
- View response times
- Inspect references and raw JSON
- Debug with process steps (when `VERBOSE_OUTPUT=true`)

## License

MIT

## Contributing

This is a personal project. Feel free to fork and adapt for your needs.
