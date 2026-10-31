let adminUsers = [];
let onlineUsers = [];
let monitorWS = null;
let sortColumn = 'id';
let sortAsc = true;

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('adminApp')) {
        refreshUsers();
        refreshOnline();
        connectMonitor();
        loadLogs();
        setInterval(refreshOnline, 3000);
        setInterval(loadLogs, 5000);
    }
});

function switchAdminTab(tab) {
    document.querySelectorAll('.admin-tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
    document.querySelectorAll('.admin-tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById('admin-tab-' + tab).classList.add('active');
    if (tab === 'logs') loadLogs();
    if (tab === 'online') refreshOnline();
}

// ─── Admin Login ──────────────────────────────────────────────

async function adminLogin(event) {
    event.preventDefault();
    const pw = document.getElementById('adminPw').value;
    const errEl = document.getElementById('adminLoginError');
    try {
        const resp = await fetch('/api/admin/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password: pw})
        });
        if (resp.ok) {
            location.reload();
        } else {
            const data = await resp.json();
            errEl.textContent = data.error || '密码错误';
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = '网络错误';
        errEl.style.display = 'block';
    }
}

async function changeAdminPassword(event) {
    event.preventDefault();
    const oldPw = document.getElementById('oldAdminPw').value;
    const newPw = document.getElementById('newAdminPw').value;
    const errEl = document.getElementById('adminPwError');
    const sucEl = document.getElementById('adminPwSuccess');
    errEl.style.display = 'none';
    sucEl.style.display = 'none';
    if (newPw.length < 6) {
        errEl.textContent = '新密码至少6位';
        errEl.style.display = 'block';
        return;
    }
    try {
        const resp = await fetch('/api/admin/change-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({old_password: oldPw, new_password: newPw})
        });
        const data = await resp.json();
        if (resp.ok) {
            sucEl.textContent = '管理密码已修改';
            sucEl.style.display = 'block';
            document.getElementById('oldAdminPw').value = '';
            document.getElementById('newAdminPw').value = '';
        } else {
            errEl.textContent = data.error || '修改失败';
            errEl.style.display = 'block';
        }
    } catch (e) {
        errEl.textContent = '网络错误';
        errEl.style.display = 'block';
    }
}

// ─── Online + Sort Helpers ──────────────────────────────────

async function refreshOnline() {
    try {
        const resp = await fetch('/api/admin/online');
        if (resp.ok) onlineUsers = await resp.json();
    } catch(e) {}
    renderUsers();
}

function isUserOnline(username) {
    return onlineUsers.some(u => u.username === username);
}

function sortBy(column) {
    if (sortColumn === column) {
        sortAsc = !sortAsc;
    } else {
        sortColumn = column;
        sortAsc = true;
    }
    renderUsers();
}

function getSortIcon(column) {
    if (sortColumn !== column) return '';
    return sortAsc ? ' ▲' : ' ▼';
}

// ─── User Management ────────────────────────────────────────

async function refreshUsers() {
    try {
        const resp = await fetch('/api/admin/users');
        if (!resp.ok) throw new Error('权限不足');
        adminUsers = await resp.json();
        renderUsers();
    } catch (e) {
        document.getElementById('userTableBody').innerHTML = '<tr><td colspan="7" style="color:#ef4444">加载失败: ' + e.message + '</td></tr>';
    }
}

function renderUsers() {
    const tbody = document.getElementById('userTableBody');
    const search = (document.getElementById('userSearch')?.value || '').toLowerCase();

    adminUsers.sort((a, b) => {
        let va, vb;
        switch (sortColumn) {
            case 'id': va = a.id; vb = b.id; break;
            case 'username': va = a.username; vb = b.username; break;
            case 'nickname': va = (a.nickname || ''); vb = (b.nickname || ''); break;
            case 'status': va = a.is_banned ? 2 : (isUserOnline(a.username) ? 0 : 1); vb = b.is_banned ? 2 : (isUserOnline(b.username) ? 0 : 1); break;
            default: va = a.id; vb = b.id;
        }
        if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        return sortAsc ? va - vb : vb - va;
    });

    const filtered = search ? adminUsers.filter(u =>
        u.username.toLowerCase().includes(search) ||
        (u.nickname && u.nickname.toLowerCase().includes(search))
    ) : adminUsers;

    tbody.innerHTML = filtered.map(u => {
        const online = isUserOnline(u.username);
        const statusHtml = u.is_banned
            ? '<span style="color:#ef4444">封禁</span>'
            : (online ? '<span style="color:#10b981">● 在线</span>' : '<span style="color:#6b7280">○ 离线</span>');
        return '<tr>' +
            '<td>' + u.id + '</td>' +
            '<td>' + escapeHtml(u.username) + '</td>' +
            '<td>' + escapeHtml(u.nickname || '-') + '</td>' +
            '<td>' + escapeHtml(u.email || '-') + '</td>' +
            '<td>' + statusHtml + '</td>' +
            '<td>' + (u.created_at || '-') + '</td>' +
            '<td class="actions">' +
            (u.is_banned
                ? '<button class="action-btn unban" onclick="unbanUser(' + u.id + ')">解封</button>'
                : '<button class="action-btn ban" onclick="banUser(' + u.id + ')">封禁</button>'
            ) +
            '<button class="action-btn reset" onclick="resetPassword(' + u.id + ')">重置密码</button>' +
            '<button class="action-btn delete" onclick="deleteUser(' + u.id + ')">删除</button>' +
            '</td>' +
            '</tr>';
    }).join('');
}

function filterUsers() { renderUsers(); }

async function banUser(uid) {
    if (!confirm('确定封禁该用户？')) return;
    const resp = await fetch('/api/admin/ban/' + uid, {method: 'POST'});
    const data = await resp.json();
    if (data.ok) refreshUsers();
    else alert(data.error);
}

async function unbanUser(uid) {
    const resp = await fetch('/api/admin/unban/' + uid, {method: 'POST'});
    const data = await resp.json();
    if (data.ok) refreshUsers();
    else alert(data.error);
}

async function deleteUser(uid) {
    if (!confirm('确定永久删除该用户？（不可恢复）')) return;
    const resp = await fetch('/api/admin/user/' + uid, {method: 'DELETE'});
    const data = await resp.json();
    if (data.ok) refreshUsers();
    else alert(data.error);
}

async function resetPassword(uid) {
    const newPw = prompt('输入新密码（至少6位）：');
    if (!newPw || newPw.length < 6) { alert('密码至少6位'); return; }
    const resp = await fetch('/api/admin/reset-password/' + uid, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({new_password: newPw})
    });
    const data = await resp.json();
    if (data.ok) {
        alert('密码已重置为: ' + data.new_password);
    } else {
        alert(data.error);
    }
}

// ─── Chat Monitor ──────────────────────────────────────────

function connectMonitor() {
    const token = getCookie('admin_token');
    if (!token) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = proto + '//' + window.location.host + '/ws?token=' + token;
    try {
        monitorWS = new WebSocket(url);
    } catch(e) { return; }
    monitorWS.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'message') {
            appendLogMsg(data);
        }
    };
    monitorWS.onclose = function() {
        setTimeout(connectMonitor, 3000);
    };
}

// ─── Chat Logs (all history + real-time) ────────────────────

async function loadLogs() {
    try {
        const resp = await fetch('/api/admin/chat-logs');
        if (!resp.ok) return;
        const logs = await resp.json();
        const box = document.getElementById('logMessages');
        if (!box) return;
        if (logs.length === 0) {
            box.innerHTML = '<p style="color:#6b7280;text-align:center;padding:20px">暂无聊天记录</p>';
            box._loaded = true;
            return;
        }
        if (box._lastCount === logs.length) return;
        box._lastCount = logs.length;
        const html = logs.map(m => {
            const time = new Date(m.timestamp * 1000);
            const timeStr = time.toLocaleTimeString();
            const dateStr = time.toLocaleDateString();
            return '<div class="monitor-msg"><span class="monitor-time">' + dateStr + ' ' + timeStr + '</span> <span class="monitor-user">[' + escapeHtml(m.nickname || m.username) + ']</span> ' +
                escapeHtml(m.content) + '</div>';
        }).join('');
        box.innerHTML = html;
        box.scrollTop = box.scrollHeight;
        box._loaded = true;
    } catch (e) {}
}

function appendLogMsg(msg) {
    const box = document.getElementById('logMessages');
    if (!box || !box._loaded) return;
    const time = new Date(msg.timestamp * 1000);
    const timeStr = time.toLocaleTimeString();
    const dateStr = time.toLocaleDateString();
    const div = document.createElement('div');
    div.className = 'monitor-msg';
    div.innerHTML = '<span class="monitor-time">' + dateStr + ' ' + timeStr + '</span> <span class="monitor-user">[' + escapeHtml(msg.nickname || msg.username) + ']</span> ' +
        escapeHtml(msg.content) + '</div>';
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

async function exportLogs() {
    try {
        const resp = await fetch('/api/admin/chat-logs/export');
        if (!resp.ok) throw new Error('导出失败');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'chat_logs_' + new Date().toISOString().slice(0,10) + '.jsonl';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('导出失败: ' + e.message);
    }
}

// ─── Online Users ──────────────────────────────────────────

function refreshOnlineTab() {
    const box = document.getElementById('onlineUsers');
    if (!box) return;
    if (onlineUsers.length === 0) {
        box.innerHTML = '<p style="color:#6b7280;text-align:center;padding:20px;grid-column:1/-1">暂无在线用户</p>';
        return;
    }
    box.innerHTML = onlineUsers.map(u => {
        return '<div class="online-card">' +
            '<div class="oc-dot"></div>' +
            '<div class="oc-name">' + escapeHtml(u.nickname || u.username) + '</div>' +
            '<div class="oc-user">@' + escapeHtml(u.username) + '</div>' +
            '</div>';
    }).join('');
}

// Override the tab switch to also refresh online display
const origSwitch = switchAdminTab;
switchAdminTab = function(tab) {
    document.querySelectorAll('.admin-tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
    document.querySelectorAll('.admin-tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById('admin-tab-' + tab).classList.add('active');
    if (tab === 'logs') loadLogs();
    if (tab === 'online') { refreshOnline(); refreshOnlineTab(); }
};

// ─── Helper ─────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : '';
}
