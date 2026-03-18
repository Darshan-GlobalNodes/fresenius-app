# Fresenius AI Assistant

An AI-powered medical chat assistant for dialysis patient management. Three role-based agents — **Patient**, **Doctor**, and **Nurse** — each with different permissions, tools, and knowledge. Powered by AWS Bedrock (Claude Sonnet 4), built on FastAPI + LangGraph, and secured with Google OAuth.

---

## What It Does

- **Patient** — Ask questions about your own dialysis records in plain language. Gets empathetic, educational answers. No clinical recommendations.
- **Doctor** — Query all 112 patient records via SQL, get evidence-based medical explanations, search PubMed for literature.
- **Nurse** — Identify patients by condition, get nursing education and care-planning support, full database access.

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Vanilla HTML + CSS + JavaScript | Login page and chat interface |
| Markdown | marked.js (CDN) | Renders AI responses with formatting |
| Backend | Python + FastAPI | Web framework and API routes |
| Server | Uvicorn (ASGI) | Runs the FastAPI application |
| Real-time chat | WebSocket | Live bidirectional communication |
| Authentication | Google OAuth2 + JWT | Secure login with email whitelist |
| AI Orchestration | LangGraph + LangChain | ReAct agent loop with memory |
| Language Model | AWS Bedrock — Claude Sonnet 4 | The core AI model |
| Search tools | PubMed, DuckDuckGo, Tavily | Agents use these to find information |
| Database | SQLite via SQLAlchemy | Patient data, built from Excel on startup |
| Data source | Excel (.xlsx) — 112 patients | Original Fresenius patient records |
| Hosting | Render.com | Free cloud deployment |

---

## Project Structure

```
fresenius-app/
│
├── app/
│   ├── main.py        ← FastAPI routes, WebSocket handler, API endpoints
│   ├── auth.py        ← Google OAuth2 flow + JWT token management
│   ├── agent.py       ← LangGraph ReAct agents, tools, system prompts
│   └── database.py    ← Reads Excel → creates SQLite on startup
│
├── static/
│   ├── index.html     ← Login page
│   └── chat.html      ← Chat interface (role selection, credential paste, messaging)
│
├── data/
│   ├── Fresenius Data.xlsx   ← Source patient data (112 patients, 32 columns)
│   └── fresenius.db          ← Auto-generated SQLite database (gitignored)
│
├── .env               ← Your secret keys (never committed to git)
├── .env.example       ← Template showing all required environment variables
├── .gitignore         ← Excludes .env, .db files, __pycache__, etc.
├── render.yaml        ← Render.com deployment configuration
└── requirements.txt   ← All Python dependencies
```

---

## How It Works — End to End

### 1. Server Startup

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- FastAPI loads all modules
- `setup_database()` runs automatically:
  - Reads `Fresenius Data.xlsx` (112 patients, 32 columns)
  - Creates `fresenius.db` (SQLite) with a table called `fresenius`
  - If the database already exists, skips this step
- Server is ready to accept requests

---

### 2. Login Page

User visits the app → sees `index.html`:
- Fresenius AI branding
- "Continue with Google" button
- Shows an error message if access is denied

---

### 3. Google Authentication (`auth.py`)

```
User clicks "Sign in with Google"
    → /auth/google  →  redirects to accounts.google.com
    ← Google redirects back with a one-time code
    → /auth/callback
        1. Exchanges code for Google access token
        2. Fetches user's email, name, picture from Google
        3. Checks email against WHITELISTED_EMAILS
        4. If denied → redirect to error page
        5. If allowed → creates a JWT (24-hour expiry)
        6. Sets JWT as httponly cookie
        7. Redirects to /chat
```

**JWT (JSON Web Token)** — A signed, tamper-proof ticket. The server verifies it on every request without touching a database.

---

### 4. Chat Page Loads (`chat.html`)

JavaScript runs three things immediately on page load:

1. `GET /api/user` — reads the JWT cookie → displays user name and avatar in header
2. `GET /api/config` — checks `LLM_PROVIDER` env var → if `bedrock`, shows the AWS credentials text box
3. Displays the **setup modal** with:
   - Role selection: Patient / Doctor / Nurse
   - AWS credentials text box (Bedrock mode only)
   - Patient ID input (Patient role only)

---

### 5. Credentials + Session Start

1. User pastes AWS temporary credentials into the text box
2. JavaScript parses the pasted text — handles both formats:
   ```bash
   export AWS_ACCESS_KEY_ID=ASIA...        # format 1
   aws_access_key_id = ASIA...             # format 2
   ```
3. User clicks **"Start Chat →"**
4. `POST /api/aws-credentials` — stores credentials **in server memory only** (never written to disk)
5. WebSocket connection opens: `wss://fresenius-app.onrender.com/ws/chat`
6. Sends `{"type": "init", "role": "doctor"}` → server registers the session
7. Server responds `{"type": "ready"}` → chat interface unlocks

---

### 6. Sending a Message

```
User types a message → JavaScript sends over WebSocket:
{"type": "message", "content": "What is the average haemoglobin score?"}

Server immediately replies: {"type": "thinking"}
→ Frontend shows pulsing "..." indicator

Server runs run_agent() in a thread pool (non-blocking)
→ AI agent processes the message
→ Server sends: {"type": "response", "content": "...", "steps": [...]}

Frontend:
  - Renders content through marked.js (markdown → HTML)
  - Shows collapsible "View Reasoning" section with tool calls used
  - Scrolls chat to bottom
```

---

### 7. The AI Agent — ReAct Loop (`agent.py`)

The agent follows the **ReAct pattern**: Reason → Act → Observe → repeat until a final answer is ready.

**`_ensure_graph()` — builds the agent (only when needed):**
- Skips rebuild if the graph already exists AND credentials haven't changed
- Rebuilds if it's the first message or AWS credentials were just updated
- Creates a `ChatBedrockConverse` client via boto3 with the pasted AWS credentials
- Builds tools based on role:

| Tool | Patient | Doctor | Nurse |
|---|---|---|---|
| DuckDuckGo Search | ✅ | ✅ | ✅ |
| PubMed | ✅ | ✅ | ✅ |
| Tavily Search | ✅ | ✅ | ✅ |
| SQL Database | ❌ | ✅ | ✅ |

- Sets the system prompt based on role:
  - **Patient** — empathetic, layman language, uses their specific patient record, no recommendations
  - **Doctor** — evidence-based education, full SQL access, cite sources with URLs
  - **Nurse** — nursing care focus, patient identification via SQL, no prescriptive advice
- Creates a `LangGraph` ReAct agent with `MemorySaver` for conversation history

**Example agent reasoning for Doctor:**
```
User: "Which patients have haemoglobin below 10?"

Agent thinks: I need to query the database.
Agent uses tool: sql_db_query → SELECT PT FROM fresenius WHERE ratingHaemoglobin < 10
Tool returns: [(3,), (7,), (12,), ...]
Agent thinks: I have the data. I can answer now.
Agent responds: "Patients 3, 7, 12... have haemoglobin ratings below 10..."
```

**Conversation memory** — `MemorySaver` stores the full history (all messages) keyed by session ID. Every new message has context from all previous turns.

---

### 8. AWS Token Refresh (Mid-Session)

AWS temporary credentials expire every 6 hours. The user can click **🔑 AWS Creds** in the header at any time:
- Paste new tokens → submit
- Calls `POST /api/aws-credentials` → updates in-memory credentials → increments version counter
- Next message triggers agent rebuild with fresh credentials
- Old conversation history is preserved across the rebuild

---

### 9. Session End

When the user closes the tab or disconnects:
- WebSocket disconnect event fires
- Server deletes the session from memory
- All conversation history is cleared (stored only in RAM, never persisted)

---

## The Three Roles — Differences

| Feature | Patient | Doctor | Nurse |
|---|---|---|---|
| SQL database access | ❌ | ✅ | ✅ |
| Sees own patient record | ✅ | ❌ | ❌ |
| Can give recommendations | ❌ | ❌ | ❌ |
| Internet + PubMed search | ✅ | ✅ | ✅ |
| System prompt tone | Empathetic, plain language | Clinical, evidence-based | Nursing-focused, care-planning |

---

## Patient Data Schema

The SQLite table `fresenius` contains 112 patients with 32 columns:

| Column | Description |
|---|---|
| `PT` | Patient ID (1–112) |
| `ItchScore` | Itching symptom score |
| `Fatigue` | Fatigue level |
| `Mental_Wellbeing` | Mental health score |
| `Difficulty_traveling` | Travel difficulty rating |
| `Difficulty_fluid_restrictions` | Fluid restriction difficulty |
| `Difficulty_Dietary` | Dietary difficulty |
| `IntraDialyticDistressScore` | Distress during dialysis |
| `ratingHaemoglobin` | Haemoglobin rating |
| `ratingAlbumin` | Albumin rating |
| `ratingPhosphate` | Phosphate rating |
| `ratingDiabetes` | Diabetes rating |
| `ratingVascularAccess` | Vascular access rating |
| `ratingHydration` | Hydration rating |
| `ratingPotassium` | Potassium rating |
| `ratingBicarbonate` | Bicarbonate rating |
| `ratingFerritin` | Ferritin rating |
| `ratingPth` | PTH (parathyroid hormone) rating |
| *(+ 14 more rating columns)* | Various clinical indicators |

---

## Security Design

| Concern | Solution |
|---|---|
| Who can log in | Google OAuth + `WHITELISTED_EMAILS` environment variable |
| Session security | httponly JWT cookie — JavaScript cannot access it |
| AWS credentials | In-memory only, never written to disk or logs |
| WebSocket auth | JWT cookie verified before accepting any WebSocket connection |
| Secrets in code | All keys in `.env` (gitignored), never committed to GitHub |
| Patient data isolation | Patient role has no SQL access, only sees their own record |

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- AWS account with Bedrock access
- Google Cloud project with OAuth credentials

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Darshan-GlobalNodes/fresenius-app.git
cd fresenius-app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in all required values

# 4. Run the server
uvicorn app.main:app --reload --port 8000

# 5. Open in browser
# http://localhost:8000
```

### Environment Variables (`.env`)

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Whitelisted users (comma-separated)
WHITELISTED_EMAILS=email1@example.com,email2@example.com

# Session security
SECRET_KEY=generate_with_python3_-c_"import secrets; print(secrets.token_hex(32))"

# AWS Bedrock
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_SERVICE_NAME=bedrock-runtime
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0

# Optional: Tavily for enhanced search
TAVILY_API_KEY=your_tavily_key
```

> **Note:** AWS temporary credentials (Access Key, Secret Key, Session Token) are NOT in `.env` — they are pasted directly in the app UI since they expire every 6 hours.

---

## Deployment Options

### Option 1: AWS Lambda (Serverless - Recommended)

Deploy as serverless AWS Lambda functions with API Gateway.

**Quick Start:**
```bash
./deploy.sh
```

**Benefits:**
- Automatic scaling
- Pay only for what you use
- No server management
- Native AWS Bedrock integration
- Can be invoked from other AWS services

**Documentation:**
- [Quick Start Guide](./QUICK_START_LAMBDA.md)
- [Full Deployment Guide](./LAMBDA_DEPLOYMENT.md)
- [Migration Summary](./LAMBDA_MIGRATION_SUMMARY.md)

### Option 2: Render.com (Traditional Server)

1. Push code to GitHub
2. Create a new **Web Service** on [render.com](https://render.com) from your GitHub repo
3. Set build and start commands:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables in the Render **Environment** tab
5. Add `https://your-app.onrender.com/auth/callback` to Google Cloud Console OAuth redirect URIs
6. Deploy — your app will be live at `https://your-app.onrender.com`

---

## Request Flow Diagram

```
Browser                     FastAPI Server                    External
───────                     ──────────────                    ────────
  │                               │
  ├── GET /          ────────────▶│ serves index.html
  ├── GET /auth/google ──────────▶│ redirects to Google ──────▶ Google OAuth
  │◀─ Google returns code ────────│◀─ /auth/callback ───────────┘
  │   (JWT cookie set)            │
  ├── GET /chat ─────────────────▶│ serves chat.html
  ├── GET /api/config ───────────▶│ returns {llm_provider}
  ├── POST /api/aws-credentials ─▶│ stores keys in memory
  ├── WS /ws/chat ───────────────▶│ WebSocket connected
  │    {type:"init"} ────────────▶│ create_session()
  │◀── {type:"ready"} ────────────│
  │    {type:"message"} ─────────▶│ run_agent() in thread pool
  │◀── {type:"thinking"} ─────────│
  │                               ├── boto3 ────────────────────▶ AWS Bedrock (LLM)
  │                               ├── SQL query ────────────────▶ SQLite DB
  │                               ├── HTTP ────────────────────▶ PubMed / DuckDuckGo
  │◀── {type:"response"} ─────────│◀───────────────────────────────┘
  │    marked.js renders markdown │
```

---

## Dependencies

```
fastapi, uvicorn          ← Web server
httpx, PyJWT              ← HTTP client and JWT tokens
python-dotenv             ← Load .env file
langchain, langchain-core ← AI framework base
langchain-community       ← DuckDuckGo, PubMed, SQL tools
langchain-anthropic       ← Anthropic LLM support (optional)
langchain-aws             ← AWS Bedrock support (ChatBedrockConverse)
langgraph                 ← ReAct agent orchestration with memory
langchain-tavily          ← Tavily search tool (optional)
boto3                     ← AWS SDK for Bedrock API calls
pandas, openpyxl          ← Read Excel data
sqlalchemy                ← SQLite database ORM
xmltodict                 ← PubMed XML parsing
duckduckgo-search         ← DuckDuckGo search API
```
