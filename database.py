import os, json, time, uuid, threading
from config import DATA_DIR, CHAT_LOGS_DIR, USERS_PATH, SESSIONS_PATH, MESSAGES_PATH

_lock = threading.Lock()

def _load(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _next_id(data):
    return max((d["id"] for d in data), default=0) + 1

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHAT_LOGS_DIR, exist_ok=True)
    for p in [USERS_PATH, SESSIONS_PATH, MESSAGES_PATH]:
        if not os.path.exists(p):
            _save(p, [])

def create_user(username, password_hash, salt, nickname="", email=""):
    with _lock:
        users = _load(USERS_PATH)
        if any(u["username"] == username for u in users):
            return None, None
        user = {
            "id": _next_id(users),
            "username": username,
            "password_hash": password_hash,
            "salt": salt,
            "nickname": nickname,
            "email": email,
            "is_admin": 0,
            "is_banned": 0,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        users.append(user)
        _save(USERS_PATH, users)
        return user["id"], 0

def get_user_by_username(username):
    users = _load(USERS_PATH)
    for u in users:
        if u["username"] == username:
            return u
    return None

def get_user_by_id(uid):
    users = _load(USERS_PATH)
    for u in users:
        if u["id"] == uid:
            return u
    return None

def update_user(uid, **kwargs):
    allowed = {"nickname", "email", "password_hash", "salt", "is_banned"}
    with _lock:
        users = _load(USERS_PATH)
        for u in users:
            if u["id"] == uid:
                for k, v in kwargs.items():
                    if k in allowed:
                        u[k] = v
                break
        _save(USERS_PATH, users)

def delete_user(uid):
    with _lock:
        users = _load(USERS_PATH)
        users = [u for u in users if u["id"] != uid]
        _save(USERS_PATH, users)
        sessions = _load(SESSIONS_PATH)
        sessions = [s for s in sessions if s["user_id"] != uid]
        _save(SESSIONS_PATH, sessions)
        msgs = _load(MESSAGES_PATH)
        msgs = [m for m in msgs if m["user_id"] != uid]
        _save(MESSAGES_PATH, msgs)

def get_all_users():
    users = _load(USERS_PATH)
    result = []
    for u in users:
        result.append({
            "id": u["id"], "username": u["username"],
            "nickname": u.get("nickname", ""), "email": u.get("email", ""),
            "is_banned": u.get("is_banned", 0),
            "created_at": u.get("created_at", "")
        })
    return result

def create_session(user_id, token):
    with _lock:
        sessions = _load(SESSIONS_PATH)
        sessions = [s for s in sessions if s["user_id"] != user_id]
        sessions.append({
            "id": _next_id(sessions),
            "user_id": user_id,
            "token": token,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        _save(SESSIONS_PATH, sessions)

def get_session(token):
    sessions = _load(SESSIONS_PATH)
    for s in sessions:
        if s["token"] == token:
            return s
    return None

def delete_session(token):
    with _lock:
        sessions = _load(SESSIONS_PATH)
        sessions = [s for s in sessions if s["token"] != token]
        _save(SESSIONS_PATH, sessions)

def save_message(user_id, username, nickname, content, timestamp):
    msg_id = None
    with _lock:
        msgs = _load(MESSAGES_PATH)
        msg = {
            "id": _next_id(msgs),
            "user_id": user_id, "username": username,
            "nickname": nickname, "content": content,
            "timestamp": timestamp
        }
        msgs.append(msg)
        _save(MESSAGES_PATH, msgs)
        msg_id = msg["id"]
    save_message_to_file(user_id, username, nickname, content, timestamp)
    return msg_id

def get_recent_messages(limit=50):
    msgs = _load(MESSAGES_PATH)
    msgs.sort(key=lambda m: m["timestamp"])
    return msgs[-limit:]

def save_message_to_file(user_id, username, nickname, content, timestamp):
    os.makedirs(CHAT_LOGS_DIR, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
    filepath = os.path.join(CHAT_LOGS_DIR, f"{date_str}.jsonl")
    entry = json.dumps({
        "user_id": user_id, "username": username,
        "nickname": nickname, "content": content,
        "timestamp": timestamp
    }, ensure_ascii=False)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def get_chat_logs(date=None):
    os.makedirs(CHAT_LOGS_DIR, exist_ok=True)
    logs = []
    try:
        files = sorted(os.listdir(CHAT_LOGS_DIR))
    except FileNotFoundError:
        return logs
    if date:
        files = [f for f in files if date in f]
    for fname in files:
        fpath = os.path.join(CHAT_LOGS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        except:
            pass
    return logs

def export_chat_logs():
    os.makedirs(CHAT_LOGS_DIR, exist_ok=True)
    all_msgs = []
    try:
        files = sorted(os.listdir(CHAT_LOGS_DIR))
    except FileNotFoundError:
        return all_msgs
    for fname in files:
        fpath = os.path.join(CHAT_LOGS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_msgs.append(json.loads(line))
        except:
            pass
    return all_msgs
