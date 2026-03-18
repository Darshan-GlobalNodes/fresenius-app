import os
import inspect
import traceback
from typing import Optional

from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchRun
from langchain_community.tools.pubmed.tool import PubmedQueryRun
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.database import engine

# Per-WebSocket session storage
sessions: dict = {}

# In-memory AWS credential store — updated at runtime via /api/aws-credentials.
# ONLY these in-memory values are used; .env AWS vars are intentionally ignored.
_aws_credentials: dict = {
    "access_key_id": "",
    "secret_access_key": "",
    "session_token": "",
}

# Incremented every time credentials are updated so _ensure_graph knows to rebuild.
_credential_version: int = 0


def update_aws_credentials(access_key_id: str, secret_access_key: str, session_token: str) -> None:
    """Replace the in-memory AWS credentials and bump the version counter."""
    global _credential_version
    _aws_credentials["access_key_id"] = access_key_id.strip()
    _aws_credentials["secret_access_key"] = secret_access_key.strip()
    _aws_credentials["session_token"] = session_token.strip()
    _credential_version += 1
    print(f"[credentials] Updated — version {_credential_version}, "
          f"key ends …{access_key_id.strip()[-4:] if access_key_id.strip() else '?'}")


def get_aws_credentials() -> dict:
    """Return ONLY the in-memory credentials — never falls back to .env values."""
    return {
        "access_key_id": _aws_credentials["access_key_id"],
        "secret_access_key": _aws_credentials["secret_access_key"],
        "session_token": _aws_credentials["session_token"],
    }


# ── LLM factory ───────────────────────────────────────────────────────────────

def get_llm():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider == "bedrock":
        creds = get_aws_credentials()
        if not creds["access_key_id"] or not creds["secret_access_key"] or not creds["session_token"]:
            raise RuntimeError(
                "AWS credentials are not set. Please paste your temporary credentials "
                "using the 🔑 AWS Creds button before sending a message."
            )

        import boto3
        bedrock_client = boto3.client(
            service_name=os.getenv("AWS_SERVICE_NAME", "bedrock-runtime"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id=creds["access_key_id"],
            aws_secret_access_key=creds["secret_access_key"],
            aws_session_token=creds["session_token"],
        )
        # Claude 3.5 Sonnet v2 requires a cross-region inference profile (us./eu./ap. prefix).
        # On-demand invocation with the bare model ID is no longer supported by AWS.
        model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

        # Prefer langchain_aws (better LangGraph tool-calling support via Converse API).
        try:
            from langchain_aws import ChatBedrockConverse
            print(f"[llm] Using ChatBedrockConverse with model {model_id}")
            return ChatBedrockConverse(client=bedrock_client, model=model_id)
        except ImportError:
            pass
        except Exception as e:
            print(f"[llm] ChatBedrockConverse failed ({e}), trying ChatBedrock …")

        try:
            from langchain_aws import ChatBedrock
            print(f"[llm] Using ChatBedrock with model {model_id}")
            return ChatBedrock(client=bedrock_client, model_id=model_id)
        except ImportError:
            pass
        except Exception as e:
            print(f"[llm] ChatBedrock failed ({e}), falling back to BedrockChat …")

        # Last resort — langchain_community BedrockChat
        from langchain_community.chat_models.bedrock import BedrockChat
        print(f"[llm] Using BedrockChat with model {model_id}")
        return BedrockChat(client=bedrock_client, model_id=model_id)

    from langchain_anthropic import ChatAnthropic
    print(f"[llm] Using ChatAnthropic model {os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')}")
    return ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0,
    )


# ── LangGraph version-safe agent builder ─────────────────────────────────────
# create_react_agent's system-prompt parameter name changed across versions:
#   0.2.x early  → messages_modifier
#   0.2.x later  → state_modifier
#   0.3.x+       → prompt
# Detect once at import time so every call is fast.

_CRA_PARAMS = set(inspect.signature(create_react_agent).parameters)
print(f"[langgraph] create_react_agent params: {_CRA_PARAMS}")


def _create_agent_graph(llm, tools, system_prompt: str, checkpointer):
    """Create a ReAct agent graph that works regardless of LangGraph version."""
    kwargs: dict = {"model": llm, "tools": tools, "checkpointer": checkpointer}

    if "prompt" in _CRA_PARAMS:
        kwargs["prompt"] = system_prompt
    elif "state_modifier" in _CRA_PARAMS:
        kwargs["state_modifier"] = system_prompt
    elif "messages_modifier" in _CRA_PARAMS:
        kwargs["messages_modifier"] = system_prompt
    else:
        print("[langgraph] WARNING: no system-prompt parameter found in create_react_agent")

    return create_react_agent(**kwargs)


# ── Tool builder ──────────────────────────────────────────────────────────────

def _build_tools(include_sql: bool = False, llm=None) -> list:
    tools = []

    try:
        search = DuckDuckGoSearchRun()
        tools.append(Tool(
            name="Search",
            func=search.invoke,
            description="Search the internet for information. Use when PubMed cannot provide relevant results.",
        ))
    except Exception as e:
        print(f"Warning: DuckDuckGo not available: {e}")

    try:
        pubmed = PubmedQueryRun()
        tools.append(Tool(
            name="PubMed",
            func=pubmed.invoke,
            description=(
                "Search peer-reviewed biomedical literature via PubMed. "
                "Prioritise: meta-analyses & clinical guidelines > RCTs > real-world evidence > expert opinion."
            ),
        ))
    except Exception as e:
        print(f"Warning: PubMed not available: {e}")

    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from langchain_tavily import TavilySearch
            os.environ["TAVILY_API_KEY"] = tavily_key
            tavily = TavilySearch(max_results=5)
            tools.append(Tool(
                name="TavilySearch",
                func=tavily.invoke,
                description="Real-time web search via Tavily. Use only when PubMed and Search both fail or error.",
            ))
        except Exception as e:
            print(f"Warning: Tavily not available: {e}")

    if include_sql and llm is not None:
        try:
            db = SQLDatabase(engine=engine)
            sql_toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            tools.extend(sql_toolkit.get_tools())
        except Exception as e:
            print(f"Warning: SQL toolkit not available: {e}")

    return tools


# ── System prompts ────────────────────────────────────────────────────────────

def _patient_system(patient_info: list) -> str:
    return f"""You are a helpful AI assistant for a dialysis patient. Answer questions clearly and compassionately.

Patient information from their medical record:
{patient_info}

Rules:
- Audience: Patient.
- Do NOT give clinical recommendations. If asked for specific medical advice, say you cannot provide that and redirect to their care team.
- You may share educational information and provide URLs to reliable resources when helpful.
- Only use search tools when you cannot answer from your knowledge or the patient record above."""


DOCTOR_SYSTEM = """You are an AI assistant for a physician managing dialysis patients.

Rules:
- Audience: Doctor.
- Provide evidence-based, educational explanations only.
- Do NOT give direct care orders or prescriptive recommendations.
- For patient-specific queries (summaries, reports, patient lists), use the SQL database tools.
- The SQL database has a table called 'fresenius' with 112 patients. Columns include: PT (patient ID 1-112), ItchScore, Fatigue, Mental_Wellbeing, Difficulty_traveling, Difficulty_fluid_restrictions, Difficulty_Dietary, IntraDialyticDistressScore, and many 'rating...' columns. NULL values may be present.
- When citing sources, print full URLs — do NOT use inline citations."""


NURSE_SYSTEM = """You are an AI assistant for a dialysis nurse.

Rules:
- Audience: Nurse.
- Help identify patients with specific conditions using the SQL database tools.
- Provide evidence-based nursing education and care-planning support.
- Do NOT give direct patient-care orders or prescriptive advice.
- The SQL database has a table called 'fresenius' with 112 patients. Columns include: PT (patient ID 1-112), ItchScore, Fatigue, Mental_Wellbeing, Difficulty_traveling, Difficulty_fluid_restrictions, Difficulty_Dietary, IntraDialyticDistressScore, and many 'rating...' columns. NULL values may be present.
- When citing sources, print full URLs — do NOT use inline citations."""


# ── Session management ────────────────────────────────────────────────────────

def create_session(session_id: str, role: str, patient_info: Optional[list] = None) -> dict:
    """Register a session. The LangGraph agent is built lazily on the first message."""
    if role not in ("patient", "doctor", "nurse"):
        raise ValueError(f"Unknown role: {role}")

    sessions[session_id] = {
        "graph": None,           # built lazily in _ensure_graph()
        "config": {"configurable": {"thread_id": session_id}},
        "role": role,
        "patient_info": patient_info,
        "cred_version": -1,      # -1 forces a build on the first message
    }
    return sessions[session_id]


def _ensure_graph(session_id: str) -> None:
    """Build (or rebuild) the LangGraph agent for a session.

    The graph is only rebuilt when:
      - It has never been built yet (first message), OR
      - Credentials were updated since the last build.

    This avoids creating a new MemorySaver (and losing history) on every message.
    """
    session = sessions[session_id]

    # Fast path: graph already built and credentials haven't changed
    if session.get("graph") is not None and session.get("cred_version") == _credential_version:
        return

    role = session["role"]
    patient_info = session.get("patient_info")

    print(f"[agent] Building graph for session {session_id[:8]}… (role={role}, cred_v={_credential_version})")

    llm = get_llm()  # raises a clear error if misconfigured

    if role == "patient":
        tools = _build_tools(include_sql=False, llm=llm)
        system_prompt = _patient_system(patient_info)
    else:
        tools = _build_tools(include_sql=True, llm=llm)
        system_prompt = DOCTOR_SYSTEM if role == "doctor" else NURSE_SYSTEM

    # Snapshot existing messages so we can restore them after a credential refresh
    old_messages: list = []
    if session.get("graph") is not None:
        try:
            state = session["graph"].get_state(session["config"])
            old_messages = state.values.get("messages", [])
            print(f"[agent] Preserving {len(old_messages)} messages across credential refresh")
        except Exception as e:
            print(f"[agent] Could not snapshot old messages: {e}")

    checkpointer = MemorySaver()
    graph = _create_agent_graph(llm, tools, system_prompt, checkpointer)

    # Restore conversation history after a credential-triggered rebuild
    if old_messages:
        try:
            graph.update_state(session["config"], {"messages": old_messages})
        except Exception as e:
            print(f"Warning: could not restore message history: {e}")

    session["graph"] = graph
    session["cred_version"] = _credential_version
    print(f"[agent] Graph ready for session {session_id[:8]}…")


def refresh_session_llm(session_id: str) -> None:
    """Kept for API compatibility — logic is now inside _ensure_graph."""
    pass


def run_agent(session_id: str, user_message: str) -> dict:
    """Synchronous agent invocation — run inside a thread pool executor."""
    _ensure_graph(session_id)

    session = sessions[session_id]
    graph = session["graph"]
    config = session["config"]

    # Record message count before this turn so we can isolate new messages
    try:
        state_before = graph.get_state(config)
        msg_count_before = len(state_before.values.get("messages", []))
    except Exception:
        msg_count_before = 0

    print(f"[agent] Invoking graph (session {session_id[:8]}…, {msg_count_before} prior messages)")

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
        )
    except Exception:
        print(f"[agent] graph.invoke() FAILED for session {session_id[:8]}…:")
        traceback.print_exc()
        raise

    all_messages = result.get("messages", [])
    print(f"[agent] Got {len(all_messages)} total messages after invoke")

    # ── Extract final AI response ─────────────────────────────────────────────
    # Walk messages in reverse; skip any AIMessage that still has pending tool_calls
    # (those are intermediate reasoning steps, not the final answer).
    output = ""
    for msg in reversed(all_messages):
        if not isinstance(msg, AIMessage):
            continue
        if getattr(msg, "tool_calls", None):
            # Intermediate tool-calling step — skip
            continue

        if isinstance(msg.content, str):
            candidate = msg.content
        elif isinstance(msg.content, list):
            # Anthropic / Bedrock Converse returns a list of content blocks
            candidate = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in msg.content
            )
        else:
            candidate = str(msg.content)

        if candidate.strip():
            output = candidate
            break

    # Fallback: if every AIMessage had tool_calls (unusual), grab the very last one
    if not output:
        for msg in reversed(all_messages):
            if isinstance(msg, AIMessage):
                if isinstance(msg.content, str):
                    candidate = msg.content
                elif isinstance(msg.content, list):
                    candidate = " ".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in msg.content
                    )
                else:
                    candidate = str(msg.content)
                if candidate.strip():
                    output = candidate
                    break

    if not output:
        print(f"[agent] WARNING: empty output! Message types: "
              f"{[type(m).__name__ for m in all_messages]}")

    # ── Extract intermediate steps (new messages from this turn only) ─────────
    new_messages = all_messages[msg_count_before:]
    steps = []
    step_idx = 1
    pending: dict = {}  # tool_call_id → step list index

    for msg in new_messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                idx = len(steps)
                steps.append({
                    "step": step_idx,
                    "tool": tc.get("name", "tool"),
                    "input": str(tc.get("args", ""))[:400],
                    "output": "",
                })
                pending[tc.get("id", "")] = idx
                step_idx += 1

        elif isinstance(msg, ToolMessage):
            idx = pending.get(msg.tool_call_id)
            if idx is not None:
                steps[idx]["output"] = str(msg.content)[:600]

    return {"output": output, "steps": steps}
