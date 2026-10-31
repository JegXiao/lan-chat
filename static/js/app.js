let ws = null;
let username = '';
let nickname = '';
let ws_token = '';
let activeTab = 'chat';
let reconnectTimer = null;

document.addEventListener('DOMContentLoaded', function() {
    const meta = document.querySelector('meta[name="user-data"]');
    if (meta) {
        username = meta.getAttribute('data-username') || '';
        nickname = meta.getAttribute('data-nickname') || username;
        ws_token = meta.getAttribute('data-token') || '';
        connectWS();
    }
});

function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : '';
}

function getToken() {
    return getCookie('token');
}

// ─── Auth ───────────────────────────────────────────────────

async function login(event) {
    event.preventDefault();
    const form = event.target;
    const errEl = document.getElementById('errorMsg');
    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: form.username.value.trim(),
                password: form.password.value
            })
        });
        const data = await resp.json();
        if (resp.ok) {
            window.location.href = '/';
        } else {
            errEl.textContent = data.error;
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = '网络错误';
        errEl.style.display = 'block';
    }
}

async function register(event) {
    event.preventDefault();
    const form = event.target;
    const errEl = document.getElementById('errorMsg');
    if (form.password.value !== form.confirm.value) {
        errEl.textContent = '两次密码不一致';
        errEl.style.display = 'block';
        return;
    }
    try {
        const resp = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: form.username.value.trim(),
                password: form.password.value,
                nickname: form.nickname.value.trim(),
                email: form.email.value.trim()
            })
        });
        const data = await resp.json();
        if (resp.ok) {
            window.location.href = '/';
        } else {
            errEl.textContent = data.error;
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = '网络错误';
        errEl.style.display = 'block';
    }
}

async function logout() {
    if (!confirm('确定要退出登录吗？')) return;
    await fetch('/api/logout', {method: 'POST'});
    window.location.href = '/login';
}

// ─── Profile ────────────────────────────────────────────────

async function updateProfile(event) {
    event.preventDefault();
    const errEl = document.getElementById('profileError');
    const sucEl = document.getElementById('profileSuccess');
    if (errEl) errEl.style.display = 'none';
    if (sucEl) sucEl.style.display = 'none';
    try {
        const resp = await fetch('/api/profile', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nickname: document.getElementById('nickname').value.trim(),
                email: document.getElementById('email').value.trim()
            })
        });
        const data = await resp.json();
        if (resp.ok) {
            if (sucEl) { sucEl.textContent = '保存成功'; sucEl.style.display = 'block'; }
        } else {
            if (errEl) { errEl.textContent = data.error || '保存失败'; errEl.style.display = 'block'; }
        }
    } catch (e) {
        if (errEl) { errEl.textContent = '网络错误'; errEl.style.display = 'block'; }
    }
}

async function changePassword(event) {
    event.preventDefault();
    const errEl = document.getElementById('pwError');
    const sucEl = document.getElementById('pwSuccess');
    if (errEl) errEl.style.display = 'none';
    if (sucEl) sucEl.style.display = 'none';
    const oldPw = document.getElementById('oldPassword').value;
    const newPw = document.getElementById('newPassword').value;
    if (newPw.length < 6) {
        if (errEl) { errEl.textContent = '新密码至少6个字符'; errEl.style.display = 'block'; }
        return;
    }
    try {
        const resp = await fetch('/api/change-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({old_password: oldPw, new_password: newPw})
        });
        const data = await resp.json();
        if (resp.ok) {
            if (sucEl) { sucEl.textContent = '密码修改成功'; sucEl.style.display = 'block'; }
            document.getElementById('oldPassword').value = '';
            document.getElementById('newPassword').value = '';
        } else {
            if (errEl) { errEl.textContent = data.error; errEl.style.display = 'block'; }
        }
    } catch (e) {
        if (errEl) { errEl.textContent = '网络错误'; errEl.style.display = 'block'; }
    }
}

async function deleteAccount() {
    if (!confirm('确定要注销账号吗？此操作不可撤销！')) return;
    const pw = prompt('请输入密码确认注销：');
    if (!pw) return;
    try {
        const resp = await fetch('/api/account', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password: pw})
        });
        if (resp.ok) {
            alert('账号已注销');
            window.location.href = '/register';
        } else {
            const data = await resp.json();
            alert(data.error || '注销失败');
        }
    } catch (e) {
        alert('网络错误');
    }
}

// ─── Tab Switching ─────────────────────────────────────────

function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.querySelectorAll('.nav-btn, .nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });
    if (tab === 'online') fetchOnlineList();
}



// ─── WebSocket Chat ─────────────────────────────────────────

function connectWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    if (!ws_token) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = proto + '//' + window.location.host + '/ws?token=' + ws_token;
    ws = new WebSocket(url);

    ws.onopen = function() {
        setStatus(true);
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };

    ws.onclose = function(e) {
        setStatus(false);
        if (e.code !== 4001 && e.code !== 4003) {
            reconnectTimer = setTimeout(connectWS, 3000);
        }
        if (e.code === 4003) {
            alert('你的账号已被封禁或删除');
            logout();
        }
    };

    ws.onerror = function() {
        setStatus(false);
    };
}

function setStatus(online) {
    const el = document.getElementById('connStatus');
    if (el) {
        el.textContent = online ? '已连接' : '未连接';
        el.className = 'status ' + (online ? 'online' : 'offline');
    }
}

function handleWSMessage(data) {
    switch (data.type) {
        case 'history':
            const msgBox = document.getElementById('messages');
            if (msgBox) {
                msgBox.innerHTML = '';
                data.messages.forEach(m => appendMessage(m));
                scrollToBottom();
            }
            break;
        case 'message':
            appendMessage(data);
            scrollToBottom();
            break;
        case 'system':
            appendSystemMessage(data.content);
            scrollToBottom();
            break;
        case 'online_list':
            updateOnlineList(data.users);
            break;
        case 'error':
            alert(data.content);
            break;
        case 'pong':
            break;
    }
}

function appendMessage(msg) {
    const box = document.getElementById('messages');
    if (!box) return;
    const div = document.createElement('div');
    const isSelf = msg.username === username;
    div.className = 'msg ' + (isSelf ? 'self' : 'other');
    const time = new Date(msg.timestamp * 1000);
    const timeStr = time.getHours().toString().padStart(2,'0') + ':' + time.getMinutes().toString().padStart(2,'0');
    div.innerHTML = '<div class="msg-user">' + escapeHtml(msg.nickname || msg.username) + '</div>' +
        '<div class="msg-content">' + escapeHtml(msg.content) + '</div>' +
        '<div class="msg-time">' + timeStr + '</div>';
    box.appendChild(div);
}

function appendSystemMessage(content) {
    const box = document.getElementById('messages');
    if (!box) return;
    const div = document.createElement('div');
    div.className = 'msg-system';
    div.textContent = content;
    box.appendChild(div);
}

function sendMessage() {
    const input = document.getElementById('msgInput');
    if (!input) return;
    const content = input.value.trim();
    if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({type: 'message', content: content}));
    input.value = '';
    input.style.height = 'auto';
}

function scrollToBottom() {
    const box = document.getElementById('messages');
    if (box) box.scrollTop = box.scrollHeight;
}

// Auto-resize textarea
document.addEventListener('input', function(e) {
    if (e.target && e.target.id === 'msgInput') {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
    }
});

// ─── Online List ────────────────────────────────────────────

function updateOnlineList(users) {
    const list = document.getElementById('onlineList');
    const count = document.getElementById('onlineCount');
    const countM = document.getElementById('onlineCountMobile');
    if (count) count.textContent = users.length;
    if (countM) countM.textContent = users.length;
    if (!list) return;
    if (users.length === 0) {
        list.innerHTML = '<p class="empty-hint">暂无在线用户</p>';
        return;
    }
    list.innerHTML = users.map(u => {
        const active = u.username === username;
        return '<div class="online-user' + (active ? ' self' : '') + '">' +
            '<div class="online-dot"></div>' +
            '<div><div class="ol-nickname">' + escapeHtml(u.nickname || u.username) + '</div>' +
            '<div class="ol-username">@' + escapeHtml(u.username) + '</div></div></div>';
    }).join('');
}

async function fetchOnlineList() {
    // Online list comes via WebSocket, this is a fallback
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({type: 'ping'}));
    }
}

// ─── Helpers ────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
