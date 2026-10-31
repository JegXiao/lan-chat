import sys, json, time, uuid, hashlib, asyncio, socket, logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import bcrypt

from config import *
from database import init_db, create_user, get_user_by_username, get_user_by_id, update_user, delete_user, get_all_users, create_session, get_session, delete_session, save_message, get_recent_messages, get_chat_logs, export_chat_logs
import cert_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chat")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

online_users = {}
ws_connections = {}
_admin_password = None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

def make_token():
    return uuid.uuid4().hex + uuid.uuid4().hex

def hash_password(password, salt=None):
    if salt is None:
        salt = uuid.uuid4().hex
    intermediate = hashlib.sha256((password + salt).encode()).hexdigest()
    hashed = bcrypt.hashpw(intermediate.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode(), salt

def verify_password(password, salt, stored_hash):
    intermediate = hashlib.sha256((password + salt).encode()).hexdigest()
    return bcrypt.checkpw(intermediate.encode(), stored_hash.encode())

# ─── Admin Password System ─────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print()
        print("=" * 60)
        print("  错误: 未找到管理员配置文件 data/config.json")
        print("  请创建该文件，格式参考：")
        print('  {"py_admin": "密码", "web_admin": "密码"}')
        print("=" * 60)
        print()
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def verify_py_admin(password):
    cfg = load_config()
    return cfg.get("py_admin") == password

def verify_web_admin(password):
    cfg = load_config()
    return cfg.get("web_admin") == password

# ─── Admin Auth Helpers ───────────────────────────────────────

_admin_tokens = set()

def is_local_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")

def make_admin_token():
    t = uuid.uuid4().hex + uuid.uuid4().hex
    _admin_tokens.add(t)
    return t

def verify_admin_token(request: Request) -> bool:
    token = request.cookies.get("admin_token")
    return token in _admin_tokens

# ─── User Auth (for chat) ─────────────────────────────────────

async def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        return None
    session = get_session(token)
    if not session:
        return None
    return get_user_by_id(session["user_id"])

def get_user_from_token(token):
    if not token:
        return None
    session = get_session(token)
    if not session:
        return None
    return get_user_by_id(session["user_id"])

@app.on_event("startup")
async def startup():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHAT_LOGS_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    init_db()
    load_config()

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)

# ─── Page Routes ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse(request, "login.html", {"error": None})
    ws_token = request.cookies.get("token", "")
    return templates.TemplateResponse(request, "chat.html", {"user": user, "ws_token": ws_token})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return templates.TemplateResponse(request, "chat.html", {"user": user})
    return templates.TemplateResponse(request, "login.html", {"error": None})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = await get_current_user(request)
    if user:
        return templates.TemplateResponse(request, "chat.html", {"user": user})
    return templates.TemplateResponse(request, "register.html", {"error": None})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return templates.TemplateResponse(request, "login.html", {"error": None})
    return templates.TemplateResponse(request, "profile.html", {"user": user, "error": None, "success": None})

# ─── Auth API ──────────────────────────────────────────────────

@app.post("/api/register")
async def api_register(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    nickname = data.get("nickname", "").strip() or username
    email = data.get("email", "").strip()

    if len(username) < 2 or len(username) > 20:
        return JSONResponse({"error": "用户名长度2-20个字符"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "密码至少6个字符"}, status_code=400)

    existing = get_user_by_username(username)
    if existing:
        return JSONResponse({"error": "用户名已存在"}, status_code=400)

    password_hash, salt = hash_password(password)
    uid, _ = create_user(username, password_hash, salt, nickname, email)
    if uid is None:
        return JSONResponse({"error": "注册失败"}, status_code=400)

    token = make_token()
    create_session(uid, token)

    resp = JSONResponse({"ok": True})
    resp.set_cookie(key="token", value=token, max_age=TOKEN_EXPIRE_DAYS * 86400, samesite="lax")
    return resp

@app.post("/api/login")
async def api_login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = get_user_by_username(username)
    if not user:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)

    if user["is_banned"]:
        return JSONResponse({"error": "账号已被封禁，请联系管理员"}, status_code=403)

    if not verify_password(password, user["salt"], user["password_hash"]):
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)

    token = make_token()
    create_session(user["id"], token)

    resp = JSONResponse({"ok": True})
    resp.set_cookie(key="token", value=token, max_age=TOKEN_EXPIRE_DAYS * 86400, samesite="lax")
    return resp

@app.post("/api/logout")
async def api_logout(request: Request):
    token = request.cookies.get("token")
    if token:
        delete_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token")
    return resp

@app.get("/api/profile")
async def api_get_profile(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "未登录")
    return {
        "username": user["username"],
        "nickname": user["nickname"],
        "email": user["email"],
        "is_banned": bool(user["is_banned"]),
        "created_at": user["created_at"]
    }

@app.put("/api/profile")
async def api_update_profile(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "未登录")
    data = await request.json()
    nickname = data.get("nickname", "").strip()
    email = data.get("email", "").strip()

    updates = {}
    if nickname and nickname != user["nickname"]:
        updates["nickname"] = nickname
    if email != user["email"]:
        updates["email"] = email

    if updates:
        update_user(user["id"], **updates)
    return {"ok": True}

@app.post("/api/change-password")
async def api_change_password(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "未登录")
    data = await request.json()
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")

    if len(new_pw) < 6:
        return JSONResponse({"error": "新密码至少6个字符"}, status_code=400)
    if not verify_password(old_pw, user["salt"], user["password_hash"]):
        return JSONResponse({"error": "原密码错误"}, status_code=400)

    password_hash, salt = hash_password(new_pw)
    update_user(user["id"], password_hash=password_hash, salt=salt)
    return {"ok": True}

@app.delete("/api/account")
async def api_delete_account(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "未登录")
    data = await request.json()
    pw = data.get("password", "")
    if not verify_password(pw, user["salt"], user["password_hash"]):
        return JSONResponse({"error": "密码错误"}, status_code=400)
    delete_user(user["id"])
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token")
    return resp

# ─── Chat WebSocket ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    user = get_user_from_token(token)
    if not user:
        await websocket.close(code=4001)
        return
    if user["is_banned"]:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    username = user["username"]
    nickname = user["nickname"] or username
    uid = user["id"]

    ws_connections[username] = websocket
    online_users[username] = {"username": username, "nickname": nickname, "uid": uid}

    recent = get_recent_messages(30)
    history = []
    for m in recent:
        history.append({
            "type": "message",
            "username": m["username"],
            "nickname": m["nickname"],
            "content": m["content"],
            "timestamp": m["timestamp"]
        })
    await websocket.send_json({"type": "history", "messages": history})

    await broadcast_online_list()
    await broadcast_system(f"{nickname} 进入了聊天室", "join")

    last_send_time = 0

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg.get("type") == "message":
                now = time.time()
                if now - last_send_time < 1.0 / MAX_MESSAGE_RATE:
                    await websocket.send_json({"type": "error", "content": "发送过快，请稍候"})
                    continue

                content = msg.get("content", "").strip()
                if not content:
                    continue
                if len(content) > MAX_MESSAGE_LENGTH:
                    content = content[:MAX_MESSAGE_LENGTH]

                last_send_time = now
                timestamp = now
                save_message(uid, username, nickname, content, timestamp)

                broadcast = {
                    "type": "message",
                    "username": username,
                    "nickname": nickname,
                    "content": content,
                    "timestamp": timestamp
                }
                await broadcast_to_all(broadcast)

    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.pop(username, None)
        online_users.pop(username, None)
        await broadcast_online_list()
        await broadcast_system(f"{nickname} 离开了聊天室", "leave")

async def broadcast_to_all(data):
    disconnected = []
    for uname, ws in ws_connections.items():
        try:
            await ws.send_json(data)
        except:
            disconnected.append(uname)
    for uname in disconnected:
        ws_connections.pop(uname, None)
        online_users.pop(uname, None)

async def broadcast_system(content, action=""):
    await broadcast_to_all({"type": "system", "content": content, "action": action, "timestamp": time.time()})

async def broadcast_online_list():
    users = [{"username": u["username"], "nickname": u["nickname"]} for u in online_users.values()]
    await broadcast_to_all({"type": "online_list", "users": users})

# ─── Admin Panel (Password-protected, no user login needed) ────

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not is_local_request(request):
        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
    authed = verify_admin_token(request)
    return templates.TemplateResponse(request, "admin.html", {"authed": authed})

@app.post("/api/admin/login")
async def admin_login(request: Request):
    if not is_local_request(request):
        return JSONResponse({"error": "Not Found"}, status_code=404)
    data = await request.json()
    password = data.get("password", "")
    if not verify_web_admin(password):
        return JSONResponse({"error": "密码错误"}, status_code=401)
    token = make_admin_token()
    resp = JSONResponse({"ok": True, "token": token})
    resp.set_cookie(key="admin_token", value=token, max_age=86400, samesite="lax")
    return resp

@app.post("/api/admin/change-password")
async def admin_change_password(request: Request):
    if not is_local_request(request) or not verify_admin_token(request):
        return JSONResponse({"error": "Not Found"}, status_code=404)
    data = await request.json()
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if len(new_pw) < 6:
        return JSONResponse({"error": "密码至少6个字符"}, status_code=400)
    cfg = load_config()
    if cfg.get("web_admin") != old_pw:
        return JSONResponse({"error": "原密码错误"}, status_code=400)
    cfg["web_admin"] = new_pw
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"ok": True}

@app.post("/api/admin/py-login")
async def admin_py_login(request: Request):
    if not is_local_request(request):
        return JSONResponse({"error": "Not Found"}, status_code=404)
    data = await request.json()
    password = data.get("password", "")
    if not verify_py_admin(password):
        return JSONResponse({"error": "密码错误"}, status_code=401)
    token = make_admin_token()
    return JSONResponse({"ok": True, "token": token})

@app.post("/api/admin/py-change-password")
async def admin_py_change_password(request: Request):
    if not is_local_request(request) or not verify_admin_token(request):
        return JSONResponse({"error": "Not Found"}, status_code=404)
    data = await request.json()
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if len(new_pw) < 6:
        return JSONResponse({"error": "密码至少6个字符"}, status_code=400)
    cfg = load_config()
    if cfg.get("py_admin") != old_pw:
        return JSONResponse({"error": "原密码错误"}, status_code=400)
    cfg["py_admin"] = new_pw
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"ok": True}

def require_admin_api(request: Request):
    if not is_local_request(request):
        raise HTTPException(404, "Not Found")
    if not verify_admin_token(request):
        raise HTTPException(403, "拒绝访问")

@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    require_admin_api(request)
    return get_all_users()

@app.post("/api/admin/ban/{uid}")
async def admin_ban_user(uid: int, request: Request):
    require_admin_api(request)
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(404, "用户不存在")
    update_user(uid, is_banned=1)
    uname = user["username"]
    ws = ws_connections.get(uname)
    if ws:
        try:
            await ws.send_json({"type": "system", "content": "你已被管理员封禁"})
            await ws.close(code=4003)
        except:
            pass
    return {"ok": True}

@app.post("/api/admin/unban/{uid}")
async def admin_unban_user(uid: int, request: Request):
    require_admin_api(request)
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(404, "用户不存在")
    update_user(uid, is_banned=0)
    return {"ok": True}

@app.delete("/api/admin/user/{uid}")
async def admin_delete_user(uid: int, request: Request):
    require_admin_api(request)
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(404, "用户不存在")
    uname = user["username"]
    ws = ws_connections.get(uname)
    if ws:
        try:
            await ws.send_json({"type": "system", "content": "你的账号已被管理员删除"})
            await ws.close(code=4003)
        except:
            pass
    delete_user(uid)
    return {"ok": True}

@app.post("/api/admin/reset-password/{uid}")
async def admin_reset_password(uid: int, request: Request):
    require_admin_api(request)
    data = await request.json()
    new_pw = data.get("new_password", "")
    if len(new_pw) < 6:
        return JSONResponse({"error": "密码至少6个字符"}, status_code=400)
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(404, "用户不存在")
    password_hash, salt = hash_password(new_pw)
    update_user(uid, password_hash=password_hash, salt=salt)
    return {"ok": True, "new_password": new_pw}

@app.get("/api/admin/chat-logs")
async def admin_chat_logs(request: Request, date: str = None):
    require_admin_api(request)
    return get_chat_logs(date)

@app.get("/api/admin/chat-logs/export")
async def admin_export_logs(request: Request):
    require_admin_api(request)
    logs = export_chat_logs()
    lines = [json.dumps(m, ensure_ascii=False) for m in logs]
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=chat_logs_export.jsonl"})

@app.get("/api/admin/online")
async def admin_online_users(request: Request):
    require_admin_api(request)
    return [{"username": u["username"], "nickname": u["nickname"]} for u in online_users.values()]

# ─── Server Entry ───────────────────────────────────────────────

def print_banner(local_ip, port, use_https):
    proto = "https" if use_https else "http"
    print()
    print("=" * 60)
    print("  LAN 联机聊天平台".center(58))
    print("=" * 60)
    print()
    print(f"  本地访问: {proto}://localhost:{port} 或 {proto}://127.0.0.1:{port}")
    print(f"  手机访问: {proto}://{local_ip}:{port}")
    print()
    print(f"  管理面板: {proto}://localhost:{port}/admin")
    print(f"  管理面板需输入管理员账号密码，仅本机可访问")
    print("=" * 60)
    print()

if __name__ == "__main__":
    import uvicorn

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    local_ip = get_local_ip()
    port = PORT

    cert_ready = cert_generator.generate_self_signed_cert(CERT_PATH, KEY_PATH)
    use_https = cert_ready

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
            }
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
        },
    }

    print_banner(local_ip, port, use_https)

    run_args = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": port,
        "log_config": LOGGING_CONFIG,
        "reload": False,
    }

    if use_https:
        run_args["ssl_keyfile"] = KEY_PATH
        run_args["ssl_certfile"] = CERT_PATH

    uvicorn.run(**run_args)
