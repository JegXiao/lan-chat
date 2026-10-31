import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import urllib.request
import urllib.error
import socket
import ssl
import time
import threading
import ctypes
import platform

if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

BASE = "https://127.0.0.1:5000"
ADMIN_TOKEN = None


def _req(method, path, data=None):
    global ADMIN_TOKEN
    urls = [f"https://127.0.0.1:5000{path}", f"http://127.0.0.1:5000{path}"]
    headers = {"Content-Type": "application/json"}
    if ADMIN_TOKEN:
        headers["Cookie"] = f"admin_token={ADMIN_TOKEN}"
    if data is not None:
        pay = json.dumps(data).encode("utf-8")
    else:
        pay = None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for url in urls:
        req = urllib.request.Request(url, data=pay, headers=headers, method=method)
        try:
            if url.startswith("https"):
                resp = urllib.request.urlopen(req, context=ctx, timeout=5)
            else:
                resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except:
                continue
        except Exception:
            continue
    return {"error": "无法连接服务器"}


class AdminTool:
    def __init__(self):
        self.root = tk.Tk()
        self._online_set = set()
        self.root.title("06_联机聊天 - 超级管理员工具")
        try:
            dpi = self.root.winfo_fpixels('1i')
            scale = dpi / 72
            if abs(scale - 1.0) > 0.1:
                self.root.tk.call('tk', 'scaling', scale)
        except:
            pass
        self.root.geometry("900x600")
        self.root.minsize(700, 400)
        self.token = None
        self._show_login()

    def _show_login(self):
        self.root.geometry("400x250")
        f = ttk.Frame(self.root, padding=30)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="超级管理员工具", font=("", 16)).pack(pady=(0, 20))
        ttk.Label(f, text="管理员密码").pack(anchor="w")
        self.pw_entry = ttk.Entry(f, show="*", width=30)
        self.pw_entry.pack(fill="x", pady=(0, 10))
        self.pw_entry.bind("<Return>", lambda e: self._do_login())
        ttk.Button(f, text="进入", command=self._do_login).pack(fill="x", pady=5)
        self.login_err = ttk.Label(f, text="", foreground="red")
        self.login_err.pack()

    def _do_login(self):
        pw = self.pw_entry.get()
        global ADMIN_TOKEN
        res = _req("POST", "/api/admin/py-login", {"password": pw})
        if res.get("ok"):
            ADMIN_TOKEN = self.token = res.get("token", "")
            self._show_main()
        else:
            self.login_err.config(text=res.get("error", "登录失败"))

    def _show_main(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("900x600")
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=5, pady=5)
        self._build_users_tab(nb)
        self._build_logs_tab(nb)
        self._build_online_tab(nb)
        self._build_settings_tab(nb)

    def _build_users_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="用户管理")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=5)
        ttk.Button(top, text="刷新", command=self._refresh_users).pack(side="left", padx=2)
        self.user_search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.user_search_var, width=30).pack(side="left", padx=5)
        ttk.Button(top, text="搜索", command=self._refresh_users).pack(side="left", padx=2)
        self.user_sort_col = "id"
        self.user_sort_asc = True
        cols = ("ID", "用户名", "昵称", "邮箱", "状态", "注册时间")
        self.utree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        sort_keys = {"ID": "id", "用户名": "username", "昵称": "nickname", "状态": "status"}
        for c in cols:
            self.utree.heading(c, text=c, command=lambda col=c: self._sort_users(col))
            self.utree.column(c, width=80)
        self.utree.column("ID", width=40)
        self.utree.column("用户名", width=100)
        self.utree.column("昵称", width=100)
        self.utree.column("邮箱", width=120)
        self.utree.column("状态", width=80)
        self.utree.column("注册时间", width=140)
        self.utree.pack(fill="both", expand=True)
        btnf = ttk.Frame(f)
        btnf.pack(fill="x", pady=5)
        ttk.Button(btnf, text="封禁", command=self._ban_user).pack(side="left", padx=2)
        ttk.Button(btnf, text="解封", command=self._unban_user).pack(side="left", padx=2)
        ttk.Button(btnf, text="重置密码", command=self._reset_pw).pack(side="left", padx=2)
        ttk.Button(btnf, text="删除用户", command=self._delete_user).pack(side="left", padx=2)
        self._refresh_online_set()
        self._refresh_users()

    def _refresh_online_set(self):
        res = _req("GET", "/api/admin/online")
        if isinstance(res, list):
            self._online_set = {u["username"] for u in res}
        self.root.after(3000, self._refresh_online_set)

    def _sort_users(self, col):
        key_map = {"ID": "id", "用户名": "username", "昵称": "nickname", "状态": "status"}
        k = key_map.get(col, "id")
        if self.user_sort_col == k:
            self.user_sort_asc = not self.user_sort_asc
        else:
            self.user_sort_col = k
            self.user_sort_asc = True
        self._refresh_users()

    def _get_selected_user(self):
        sel = self.utree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个用户")
            return None
        vals = self.utree.item(sel[0], "values")
        return {"id": int(vals[0]), "username": vals[1]}

    def _refresh_users(self):
        res = _req("GET", "/api/admin/users")
        if "error" in res:
            messagebox.showerror("错误", res["error"])
            return
        kw = self.user_search_var.get().lower()
        users = [u for u in res if not kw or kw in u["username"].lower() or kw in u.get("nickname", "").lower()]
        users.sort(key=lambda u: (
            u.get(self.user_sort_col) if self.user_sort_col in ("id",) else
            (u.get("is_banned", 0) * 10 + (0 if u["username"] in self._online_set else 1))
            if self.user_sort_col == "status" else
            (u.get(self.user_sort_col) or "").lower()
        ), reverse=not self.user_sort_asc)
        for row in self.utree.get_children():
            self.utree.delete(row)
        for u in users:
            if u.get("is_banned"):
                status = "封禁"
            elif u["username"] in self._online_set:
                status = "● 在线"
            else:
                status = "○ 离线"
            self.utree.insert("", "end", values=(
                u["id"], u["username"], u.get("nickname", ""), u.get("email", ""),
                status, u.get("created_at", "")
            ))

    def _ban_user(self):
        u = self._get_selected_user()
        if not u: return
        if messagebox.askyesno("确认", f"封禁用户 {u['username']}？"):
            res = _req("POST", f"/api/admin/ban/{u['id']}")
            if res.get("ok"): self._refresh_users()
            else: messagebox.showerror("错误", res.get("error", "失败"))

    def _unban_user(self):
        u = self._get_selected_user()
        if not u: return
        res = _req("POST", f"/api/admin/unban/{u['id']}")
        if res.get("ok"): self._refresh_users()
        else: messagebox.showerror("错误", res.get("error", "失败"))

    def _reset_pw(self):
        u = self._get_selected_user()
        if not u: return
        pw = tk.simpledialog.askstring("重置密码", f"为 {u['username']} 设置新密码（至少6位）：", parent=self.root)
        if not pw or len(pw) < 6:
            messagebox.showwarning("提示", "密码至少6位")
            return
        res = _req("POST", f"/api/admin/reset-password/{u['id']}", {"new_password": pw})
        if res.get("ok"):
            messagebox.showinfo("成功", f"密码已重置为: {res['new_password']}")
        else:
            messagebox.showerror("错误", res.get("error", "失败"))

    def _delete_user(self):
        u = self._get_selected_user()
        if not u: return
        if messagebox.askyesno("确认", f"永久删除用户 {u['username']}？不可恢复！"):
            res = _req("DELETE", f"/api/admin/user/{u['id']}")
            if res.get("ok"): self._refresh_users()
            else: messagebox.showerror("错误", res.get("error", "失败"))

    def _build_logs_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="聊天记录")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=5)
        ttk.Button(top, text="刷新", command=self._refresh_logs).pack(side="left", padx=2)
        ttk.Button(top, text="导出", command=self._export_logs).pack(side="left", padx=2)
        self.logs_text = scrolledtext.ScrolledText(f, state="disabled", font=("Consolas", 10))
        self.logs_text.pack(fill="both", expand=True)
        self._last_log_count = 0
        self._refresh_logs()
        self._poll_logs()

    def _poll_logs(self):
        self._refresh_logs()
        self.root.after(3000, self._poll_logs)

    def _refresh_logs(self):
        res = _req("GET", "/api/admin/chat-logs")
        if isinstance(res, list):
            if len(res) == self._last_log_count:
                return
            self._last_log_count = len(res)
            self.logs_text.config(state="normal")
            self.logs_text.delete("1.0", "end")
            for m in res:
                ts = time.strftime("%m-%d %H:%M:%S", time.localtime(m.get("timestamp", 0)))
                line = f"[{ts}] {m.get('nickname','') or m.get('username','')}: {m.get('content','')}\n"
                self.logs_text.insert("end", line)
            self.logs_text.see("end")
            self.logs_text.config(state="disabled")
            self.logs_text.config(state="disabled")

    def _export_logs(self):
        import webbrowser
        webbrowser.open(f"{BASE}/api/admin/chat-logs/export")

    def _build_online_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="在线用户")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=5)
        ttk.Button(top, text="刷新", command=self._refresh_online).pack(side="left", padx=2)
        self.online_listbox = tk.Listbox(f, font=("Consolas", 12))
        self.online_listbox.pack(fill="both", expand=True)
        self._refresh_online()

    def _refresh_online(self):
        res = _req("GET", "/api/admin/online")
        self.online_listbox.delete(0, "end")
        if isinstance(res, list):
            for u in res:
                self.online_listbox.insert("end", f"  {u.get('nickname','') or u.get('username','')} (@{u.get('username','')})")
        if self.online_listbox.size() == 0:
            self.online_listbox.insert("end", "  (暂无在线用户)")

    def _build_settings_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="修改密码")
        ttk.Label(f, text="修改管理员密码", font=("", 14)).pack(anchor="w", pady=(0, 20))
        ttk.Label(f, text="原密码").pack(anchor="w")
        self.old_pw = ttk.Entry(f, show="*", width=30)
        self.old_pw.pack(fill="x", pady=(0, 10))
        ttk.Label(f, text="新密码（至少6位）").pack(anchor="w")
        self.new_pw = ttk.Entry(f, show="*", width=30)
        self.new_pw.pack(fill="x", pady=(0, 10))
        ttk.Button(f, text="修改密码", command=self._change_admin_pw).pack(fill="x", pady=5)
        self.settings_err = ttk.Label(f, text="", foreground="red")
        self.settings_err.pack()
        self.settings_ok = ttk.Label(f, text="", foreground="green")
        self.settings_ok.pack()

    def _change_admin_pw(self):
        old = self.old_pw.get()
        new = self.new_pw.get()
        self.settings_err.config(text="")
        self.settings_ok.config(text="")
        if len(new) < 6:
            self.settings_err.config(text="新密码至少6位")
            return
        res = _req("POST", "/api/admin/py-change-password", {"old_password": old, "new_password": new})
        if res.get("ok"):
            self.settings_ok.config(text="管理员密码已修改")
            self.old_pw.delete(0, "end")
            self.new_pw.delete(0, "end")
        else:
            self.settings_err.config(text=res.get("error", "修改失败"))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import tkinter.simpledialog
    AdminTool().run()
