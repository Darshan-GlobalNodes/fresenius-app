import asyncio
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    GOOGLE_CLIENT_ID,
    WHITELISTED_EMAILS,
    create_access_token,
    exchange_code_for_token,
    get_google_auth_url,
    get_user_info,
    verify_token,
)
from app.agent import create_session, run_agent, sessions, update_aws_credentials, get_aws_credentials
from app.database import setup_database, engine, get_patient, get_patient_count

app = FastAPI(title="Fresenius AI Assistant")

app.mount("/static", StaticFiles(directory="static"), name="static")

_thread_pool = ThreadPoolExecutor(max_workers=10)


@app.on_event("startup")
async def startup():
    setup_database()

# Initialize database on module load for Lambda cold starts
# This ensures the database is ready before the first request
import os
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    # Running in Lambda environment
    setup_database()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _html(path: str) -> HTMLResponse:
    with open(f"static/{path}") as f:
        return HTMLResponse(content=f.read())


def _require_auth(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        return None
    return verify_token(token)


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def root(request: Request):
    if _require_auth(request):
        return RedirectResponse(url="/chat")
    return _html("index.html")


@app.get("/chat")
async def chat_page(request: Request):
    if not _require_auth(request):
        return RedirectResponse(url="/")
    return _html("chat.html")


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/auth/google")
async def google_auth():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured on the server.")
    return RedirectResponse(url=get_google_auth_url())


@app.get("/auth/callback")
async def google_callback(request: Request, code: str = None, error: str = None):
    if error:
        return RedirectResponse(url=f"/?error={error}")
    if not code:
        return RedirectResponse(url="/")

    try:
        access_token = await exchange_code_for_token(code)
        user_info = await get_user_info(access_token)
        email = user_info.get("email", "").lower()

        if email not in WHITELISTED_EMAILS:
            return RedirectResponse(url=f"/?error=access_denied&email={email}")

        jwt_token = create_access_token({
            "email": email,
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
        })
        resp = RedirectResponse(url="/chat")
        resp.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            max_age=86400,
            samesite="lax",
        )
        return resp

    except Exception as exc:
        return RedirectResponse(url=f"/?error=auth_failed")


@app.get("/auth/logout")
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("access_token")
    return resp


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/user")
async def api_user(request: Request):
    user = _require_auth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"email": user.get("email"), "name": user.get("name"), "picture": user.get("picture")}


@app.get("/api/config")
async def api_config(request: Request):
    """Return app configuration the frontend needs (does NOT expose secrets)."""
    user = _require_auth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    import os
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    return {"llm_provider": provider}


@app.post("/api/aws-credentials")
async def api_aws_credentials(request: Request):
    """Update AWS credentials at runtime — no server restart required.
    Accepts JSON: {access_key_id, secret_access_key, session_token}.
    Credentials are held in memory only and are never written to disk.
    """
    user = _require_auth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    body = await request.json()
    key = body.get("access_key_id", "").strip()
    secret = body.get("secret_access_key", "").strip()
    token = body.get("session_token", "").strip()

    if not key or not secret or not token:
        raise HTTPException(
            status_code=400,
            detail="All three fields are required: access_key_id, secret_access_key, session_token.",
        )

    update_aws_credentials(key, secret, token)
    return {"status": "ok", "message": "AWS credentials updated. New credentials will be used on your next message."}


@app.get("/api/aws-credentials/status")
async def api_aws_credentials_status(request: Request):
    """Returns whether in-memory AWS credentials are currently set (values are never exposed)."""
    user = _require_auth(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    creds = get_aws_credentials()
    has_creds = bool(creds["access_key_id"] and creds["secret_access_key"] and creds["session_token"])
    # Show only the last 4 chars of the key so the user can confirm which credential set is active
    key_hint = ("…" + creds["access_key_id"][-4:]) if creds["access_key_id"] else "not set"
    return {"has_credentials": has_creds, "key_hint": key_hint}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()

    # Authenticate via cookie
    token = websocket.cookies.get("access_token")
    if not token or not verify_token(token):
        await websocket.send_json({"type": "error", "content": "Authentication required. Please log in."})
        await websocket.close(code=4001)
        return

    session_id: str | None = None
    loop = asyncio.get_event_loop()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ── Init: set up agent session ────────────────────────────────
            if msg_type == "init":
                role = data.get("role", "patient").lower()
                patient_id_raw = data.get("patient_id")
                session_id = str(uuid.uuid4())

                patient_info = None
                if role == "patient":
                    try:
                        patient_id = int(patient_id_raw)
                        total = get_patient_count()
                        if patient_id < 1 or patient_id > total:
                            raise ValueError
                    except (TypeError, ValueError):
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Invalid Patient ID. Please enter a number between 1 and 112.",
                        })
                        continue

                    patient_info = get_patient(patient_id)
                    if not patient_info:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Patient {patient_id} not found in the database.",
                        })
                        continue

                # Create agent (blocking — small overhead, run sync)
                try:
                    create_session(session_id, role, patient_info)
                    await websocket.send_json({"type": "ready", "session_id": session_id})
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Failed to initialize agent: {exc}",
                    })

            # ── Message: invoke agent ─────────────────────────────────────
            elif msg_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                if not session_id or session_id not in sessions:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Session not initialized. Please refresh the page.",
                    })
                    continue

                await websocket.send_json({"type": "thinking"})

                try:
                    result = await loop.run_in_executor(
                        _thread_pool,
                        lambda msg=content: run_agent(session_id, msg),
                    )
                    await websocket.send_json({
                        "type": "response",
                        "content": result["output"],
                        "steps": result["steps"],
                    })
                except Exception as exc:
                    traceback.print_exc()
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Agent error: {exc}",
                    })
                    print(f"Agent error [{session_id}]: {exc}")

    except WebSocketDisconnect:
        if session_id and session_id in sessions:
            del sessions[session_id]
    except Exception as exc:
        print(f"WebSocket error: {exc}")
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
