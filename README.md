# 局域网聊天 | LAN Chat

> 带注册登录的局域网聊天室：FastAPI + WebSocket 实时公聊，配网页管理面板与桌面超级管理员工具。仅供可信局域网使用。

**中文** · [ English](#english)

---

## 功能特性

- **聊天室**：注册/登录（bcrypt 加盐存储）、WebSocket 实时公聊、进房推送最近 30 条历史、进出系统消息、在线列表；限速 3 条/秒、单条上限 2000 字。
- **网页管理面板 `/admin`**（仅服务器本机可访问，其他来源一律 404）：用户列表/封禁/解封/删除/重置密码、在线用户、聊天记录查看与导出。
- **桌面超级管理员工具 `admin_tool.py`**：Tkinter GUI，用户管理 + 聊天记录实时滚动 + 修改超级管理员密码，走独立的 `py_admin` 密码体系。
- **自动 HTTPS**：启动时自动生成自签证书（含本机局域网 IP，10 年有效）；失败则降级 HTTP。

## 快速开始

```bash
pip install -r requirements.txt

# 首次运行前：在 data/ 下创建 config.json（否则启动会给出提示并退出）
# {
#   "py_admin": "你的超级管理员密码",
#   "web_admin": "你的网页管理面板密码"
# }

python main.py
```

浏览器访问 `https://<服务器IP>:5000`；管理面板在 `/admin`（本机打开）。

## 配置

| 项 | 位置 |
|---|---|
| 端口 | `config.py` 的 `PORT`（默认 5000） |
| 管理密码 | `data/config.json`（`py_admin`/`web_admin`） |
| 会话有效期 | `config.py` 的 `TOKEN_EXPIRE_DAYS`（默认 7 天） |

## 说明

- `data/`（用户、消息、会话、日志、管理员密码）整目录已被 `.gitignore` 忽略，**永远不会上传**。
- 仓库中没有默认密码；`config.json` 由使用者自行创建并自行保管。
- 仅公聊（无私聊）；`ssl/` 证书自动生成、已 gitignore。仅供可信局域网使用。

---

# English

> A LAN chat room with registration and login: real-time public chat over FastAPI + WebSocket, plus a web admin panel and a desktop super-admin tool. For trusted LANs only.

## Features

- **Chat room**: register/login (salted bcrypt), real-time public chat over WebSocket, last-30-message history on join, join/leave system messages, online list; rate-limited to 3 msgs/s, 2000 chars each.
- **Web admin panel `/admin`** (accessible only from the server machine; others get 404): user list/ban/unban/delete/reset password, online users, chat log viewing & export.
- **Desktop super-admin tool `admin_tool.py`**: a Tkinter GUI with user management, live chat log streaming and super-admin password change, using the separate `py_admin` password.
- **Automatic HTTPS**: a self-signed certificate (LAN IP in SAN, 10-year validity) is generated at startup; falls back to HTTP on failure.

## Quick Start

```bash
pip install -r requirements.txt

# Before first run: create data/config.json (or the server exits with a hint)
# {
#   "py_admin": "your super-admin password",
#   "web_admin": "your web admin panel password"
# }

python main.py
```

Open `https://<server-IP>:5000`; the admin panel lives at `/admin` (from the server machine).

## Configuration

| Item | Location |
|---|---|
| Port | `PORT` in `config.py` (default 5000) |
| Admin passwords | `data/config.json` (`py_admin`/`web_admin`) |
| Session lifetime | `TOKEN_EXPIRE_DAYS` in `config.py` (default 7 days) |

## Notes

- The whole `data/` folder (users, messages, sessions, logs, admin passwords) is gitignored and **never leaves your machine**.
- No default passwords ship with the repo; you create and keep `config.json` yourself.
- Public chat only (no private messages); `ssl/` certificates are auto-generated and gitignored. Trusted LANs only.
