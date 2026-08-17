# -*- coding: utf-8 -*-
"""
知行工作台 - 个人桌面工作台应用
Version: 2.5.7
Design: 扁平化 · 简约大气
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import threading
import hashlib
import base64
import os
import sys
import math
from datetime import datetime
from pathlib import Path

# ============================================================
# 应用常量
# ============================================================
APP_NAME = "知行工作台"
APP_VERSION = "3.1.0"
APP_SLOGAN = "致 虚 极 / 守 静 笃"
APP_DESC = "一个简约、可扩展的个人桌面工作台"
COPYRIGHT_OWNER = "知行工作室"
COPYRIGHT_SITE  = "w3b.pub"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# 数据加密模块
# ============================================================
def _derive_key(password: str, salt: bytes) -> bytes:
    """用密码和盐派生 32 字节密钥（PBKDF2-HMAC-SHA256）"""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=32)


def _keystream(key: bytes, length: int) -> bytes:
    """用 SHA-256 计数器模式生成密钥流"""
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    """XOR 加解密（对称）"""
    ks = _keystream(key, len(data))
    return bytes(a ^ b for a, b in zip(data, ks))


def encrypt_data(plaintext: str, password: str) -> tuple:
    """加密数据，返回 (enc_base64, salt_base64)"""
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    cipher = _xor_cipher(plaintext.encode("utf-8"), key)
    return base64.b64encode(cipher).decode("ascii"), base64.b64encode(salt).decode("ascii")


def decrypt_data(enc_b64: str, salt_b64: str, password: str) -> str:
    """解密数据，返回明文字符串"""
    cipher = base64.b64decode(enc_b64)
    salt = base64.b64decode(salt_b64)
    key = _derive_key(password, salt)
    plaintext = _xor_cipher(cipher, key)
    return plaintext.decode("utf-8")


# ============================================================
# 工具函数
# ============================================================
def center_window(window, width, height):
    """将窗口居中显示在屏幕上"""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_input_dialog(parent, title, prompt, initialvalue=""):
    """统一风格的输入对话框（替代 simpledialog.askstring）"""
    dlg = ctk.CTkToplevel(parent)
    dlg.title(title)
    dlg.geometry("400x220")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    # 居中在父窗口上方
    dlg.update_idletasks()
    pw = parent.winfo_toplevel()
    cx = pw.winfo_x() + pw.winfo_width() // 2 - 200
    cy = pw.winfo_y() + pw.winfo_height() // 2 - 110
    cx = max(0, min(cx, dlg.winfo_screenwidth() - 400))
    cy = max(0, min(cy, dlg.winfo_screenheight() - 220))
    dlg.geometry(f"+{cx}+{cy}")

    result = {"value": None}

    # 标题
    ctk.CTkLabel(
        dlg, text=title,
        font=ctk.CTkFont(family="微软雅黑", size=18, weight="bold"),
    ).pack(anchor="w", padx=25, pady=(20, 5))

    # 提示文字
    ctk.CTkLabel(
        dlg, text=prompt,
        font=ctk.CTkFont(family="微软雅黑", size=13),
        text_color=("gray40", "gray60"),
    ).pack(anchor="w", padx=25, pady=(0, 8))

    # 输入框
    entry = ctk.CTkEntry(
        dlg, height=38,
        font=ctk.CTkFont(family="微软雅黑", size=14),
    )
    entry.pack(fill="x", padx=25, pady=(0, 15))
    if initialvalue:
        entry.insert(0, initialvalue)
    entry.focus_set()

    # 按钮区
    btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_frame.pack(fill="x", padx=25, pady=(0, 20))

    def on_ok():
        result["value"] = entry.get()
        dlg.destroy()

    def on_cancel():
        dlg.destroy()

    ctk.CTkButton(
        btn_frame, text="取消", width=80, height=36,
        fg_color=("gray75", "gray26"),
        font=ctk.CTkFont(family="微软雅黑", size=13),
        command=on_cancel,
    ).pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        btn_frame, text="确定", width=80, height=36,
        font=ctk.CTkFont(family="微软雅黑", size=13),
        command=on_ok,
    ).pack(side="right")

    entry.bind("<Return>", lambda e: on_ok())
    entry.bind("<Escape>", lambda e: on_cancel())
    dlg.bind("<Escape>", lambda e: on_cancel())

    dlg.wait_window()
    return result["value"]


# ============================================================
# Overlay 扁平化滚动条 — 自动隐藏 · 覆盖式 · 优雅
# ============================================================
def _get_appearance():
    """获取当前外观模式"""
    try:
        return ctk.get_appearance_mode().lower()
    except Exception:
        return "dark"


class OverlayScrollbar(tk.Canvas):
    """
    覆盖式扁平滚动条：
    - 透明背景，覆盖在内容上方
    - 自动隐藏（滚动/悬停时显示，停止后渐隐）
    - 滑块高度精确匹配视口/内容比例
    - 主题自适应
    """

    _WIDTH = 7           # 滑块宽度
    _PADDING = 3         # 右侧内边距
    _THUMB_MIN = 28      # 最小滑块高度
    _RADIUS = 4          # 圆角半径
    _FADE_STEP = 0.12    # 渐变步长
    _FADE_INTERVAL = 12  # 渐变间隔(ms)
    _HIDE_DELAY = 800   # 自动隐藏延迟(ms)

    def __init__(self, parent, target_canvas, **kwargs):
        super().__init__(
            parent,
            width=self._WIDTH + self._PADDING * 2,
            highlightthickness=0, bd=0,
            **kwargs,
        )
        self.target_canvas = target_canvas
        self._theme = _get_appearance()

        # 状态
        self._thumb_y = 0
        self._thumb_h = self._THUMB_MIN
        self._first = 0.0
        self._last = 1.0
        self._dragging = False
        self._hover = False
        self._opacity = 0.0
        self._target_opacity = 0.0
        self._anim_id = None
        self._hide_timer = None
        self._draw_scheduled = False
        self._need_scroll = False  # 内容是否需要滚动

        # 背景透明 — 用父容器的颜色
        self._update_bg()

        # 事件
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda e: self._schedule_redraw())
        self.bind("<MouseWheel>", self._on_wheel)

        self.target_canvas.configure(yscrollcommand=self._on_scroll)
        self.target_canvas.bind("<MouseWheel>", self._on_target_wheel)
        self.target_canvas.bind("<Enter>", self._on_target_enter)
        self.target_canvas.bind("<Leave>", self._on_target_leave)

        # 绑定 Configure：canvas 大小变化时同步滚动条高度
        self.target_canvas.bind("<Configure>", self._on_canvas_configure)

    def destroy(self):
        """清理所有定时器，防止销毁后回调报错"""
        self._cancel_hide()
        if self._anim_id:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None
        super().destroy()

    def _update_bg(self):
        """更新背景色以匹配父容器（模拟透明）"""
        self._theme = _get_appearance()
        if self._theme == "dark":
            self._bg_rgb = (31, 31, 31)    # 匹配 gray12 = #1F1F1F
        else:
            self._bg_rgb = (235, 235, 235)  # 匹配 gray92 = #EBEBEB
        self.configure(bg="#%02x%02x%02x" % self._bg_rgb)

    def _on_canvas_configure(self, event):
        """Canvas 视口大小变化时，重新计算滑块位置"""
        self._schedule_redraw()

    def _thumb_colors(self):
        """获取当前主题下的滑块颜色 — 高对比度"""
        self._theme = _get_appearance()
        if self._theme == "dark":
            idle = (180, 180, 190)    # 更亮的灰色，确保在深色背景上可见
            hover = (100, 165, 235)   # 亮蓝色
            drag = (80, 145, 215)     # 亮蓝色
        else:
            idle = (90, 90, 100)     # 更深的灰色，确保在浅色背景上清晰可见
            hover = (40, 100, 175)   # 深蓝色
            drag = (20, 80, 155)      # 深蓝色
        return idle, hover, drag

    def _blend(self, fg_rgb, opacity):
        """前景色与背景混合，模拟透明度"""
        return "#%02x%02x%02x" % tuple(
            int(self._bg_rgb[i] + (fg_rgb[i] - self._bg_rgb[i]) * opacity)
            for i in range(3)
        )

    def _current_color(self):
        """获取当前滑块颜色"""
        idle, hover, drag = self._thumb_colors()
        if self._dragging:
            base = drag
        elif self._hover:
            base = hover
        else:
            base = idle
        # 透明度叠加：idle 时清晰可见，hover/drag 时完全不透明
        if self._dragging or self._hover:
            return self._blend(base, 0.95 * self._opacity + 0.05)
        return self._blend(base, 0.75 * self._opacity + 0.20)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        pts = []
        pts.extend([x1 + r, y1, x2 - r, y1])
        pts.extend([x2 - r, y1, x2, y1, x2, y1 + r])
        pts.extend([x2, y2 - r])
        pts.extend([x2, y2 - r, x2, y2, x2 - r, y2])
        pts.extend([x1 + r, y2])
        pts.extend([x1 + r, y2, x1, y2, x1, y2 - r])
        pts.extend([x1, y1 + r])
        pts.extend([x1, y1 + r, x1, y1, x1 + r, y1])
        return self.create_polygon(pts, smooth=True, **kw)

    def _calc_thumb(self):
        """精确计算滑块位置和大小"""
        ch = self.target_canvas.winfo_height()
        if ch <= 1:
            ch = self.winfo_height()
        content = self.target_canvas.bbox("all")
        if not content:
            self._need_scroll = False
            return

        total = content[3] - content[1]
        if total <= ch:
            self._need_scroll = False
            return

        self._need_scroll = True
        # 滑块高度 = 视口高 × (视口高 / 内容高)
        ratio = ch / total
        self._thumb_h = max(self._THUMB_MIN, int(ch * ratio))
        # 滑块位置
        scroll_range = max(0.001, 1 - self._last + self._first)
        self._thumb_y = int((ch - self._thumb_h) * self._first / scroll_range)
        # 边界保护
        self._thumb_y = max(0, min(ch - self._thumb_h, self._thumb_y))

    def _redraw(self):
        self.delete("all")
        self._update_bg()

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        self._calc_thumb()

        if not self._need_scroll or self._opacity < 0.01:
            return

        # 滑块位置（右对齐，留 padding）
        tx = cw - self._WIDTH - self._PADDING
        color = self._current_color()
        self._round_rect(
            tx, self._thumb_y, tx + self._WIDTH,
            self._thumb_y + self._thumb_h,
            self._RADIUS, fill=color, outline="",
        )

    # --- 滚动回调 ---
    def _on_scroll(self, first, last):
        self._first = float(first)
        self._last = float(last)
        if not self._dragging:
            self._schedule_redraw()

    def _schedule_redraw(self):
        if not self._draw_scheduled:
            self._draw_scheduled = True
            self.after_idle(self._do_redraw)

    def _do_redraw(self):
        self._draw_scheduled = False
        try:
            if self.winfo_exists():
                self._redraw()
        except Exception:
            pass

    # --- 显示/隐藏 ---
    def show(self):
        self._cancel_hide()
        self._target_opacity = 1.0
        self._animate_fade()

    def hide(self):
        self._target_opacity = 0.0
        self._animate_fade()

    def _cancel_hide(self):
        if self._hide_timer:
            try:
                self.after_cancel(self._hide_timer)
            except Exception:
                pass
            self._hide_timer = None

    def _schedule_hide(self):
        self._cancel_hide()
        self._hide_timer = self.after(self._HIDE_DELAY, self._check_hide)

    def _check_hide(self):
        try:
            if self.winfo_exists() and not self._hover and not self._dragging:
                self.hide()
        except Exception:
            pass

    def _animate_fade(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if self._anim_id:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

        if self._opacity < self._target_opacity:
            self._opacity = min(self._target_opacity, self._opacity + self._FADE_STEP)
        elif self._opacity > self._target_opacity:
            self._opacity = max(self._target_opacity, self._opacity - self._FADE_STEP)

        try:
            self._redraw()
        except Exception:
            return

        if abs(self._opacity - self._target_opacity) > 0.01:
            self._anim_id = self.after(self._FADE_INTERVAL, self._animate_fade)
        else:
            self._opacity = self._target_opacity
            if self._opacity < 0.01:
                try:
                    self.delete("all")
                except Exception:
                    pass

    # --- 鼠标交互 ---
    def _on_press(self, event):
        if not self._need_scroll:
            return
        self._calc_thumb()
        ch = self.winfo_height()
        # 确定滑块的实际位置
        ty = self._thumb_y
        th = self._thumb_h

        if ty <= event.y <= ty + th:
            # 点中滑块：拖动
            self._dragging = True
            self._drag_offset = event.y - ty
        elif event.y < ty:
            # 点击滑块上方的轨道 = 向上翻一页（Windows 标准）
            self.target_canvas.yview_scroll(-1, "pages")
            self._schedule_hide()
        else:
            # 点击滑块下方的轨道 = 向下翻一页（Windows 标准）
            self.target_canvas.yview_scroll(1, "pages")
            self._schedule_hide()

    def _on_drag(self, event):
        if not self._dragging:
            return
        ch = self.target_canvas.winfo_height()
        if ch <= 1:
            ch = self.winfo_height()
        new_y = event.y - self._drag_offset
        new_y = max(0, min(ch - self._thumb_h, new_y))
        scroll_range = max(0.001, 1 - self._last + self._first)
        ratio = new_y / max(1, ch - self._thumb_h)
        self.target_canvas.yview_moveto(ratio * scroll_range)

    def _on_release(self, event):
        self._dragging = False
        if not self._hover:
            self._schedule_hide()

    def _on_enter(self, event):
        self._hover = True
        self.show()

    def _on_leave(self, event):
        self._hover = False
        self._dragging = False
        self._schedule_hide()

    def _on_wheel(self, event):
        self.show()
        # 根据滚轮 delta 值计算滚动量，更流畅
        units = max(1, abs(event.delta) // 120)
        if event.delta > 0:
            self.target_canvas.yview_scroll(-units, "units")
        else:
            self.target_canvas.yview_scroll(units, "units")
        self._schedule_hide()

    def _on_target_wheel(self, event):
        self.show()
        units = max(1, abs(event.delta) // 120)
        if event.delta > 0:
            self.target_canvas.yview_scroll(-units, "units")
        else:
            self.target_canvas.yview_scroll(units, "units")
        self._schedule_hide()

    def _on_target_enter(self, event):
        self.show()

    def _on_target_leave(self, event):
        if not self._dragging:
            self._schedule_hide()


def apply_card_scrollbar(scrollable_frame, theme="dark"):
    """
    替换 CTkScrollableFrame 的原生滚动条为 Overlay 扁平滚动条。
    滚动条覆盖在内容右侧上方，不随内容滚动。
    使用 relheight=1.0 确保高度始终与视口匹配。
    """
    try:
        if not scrollable_frame.winfo_exists():
            return
    except Exception:
        return

    scrollable_frame.update_idletasks()

    try:
        canvas = scrollable_frame._parent_canvas
        old_scrollbar = scrollable_frame._scrollbar

        # 移除原生滚动条
        for method_name in ("grid_forget", "pack_forget"):
            try:
                getattr(old_scrollbar, method_name)()
                break
            except Exception:
                continue

        # 在 scrollable_frame 的父容器上创建滚动条（避免随内容滚动）
        total_w = OverlayScrollbar._WIDTH + OverlayScrollbar._PADDING * 2
        parent = scrollable_frame.master
        sb = OverlayScrollbar(parent, canvas)

        # 用 relheight=1.0 确保高度始终与 scrollable_frame 一致
        sb.place(
            in_=scrollable_frame,
            relx=1.0, rely=0.0,
            relheight=1.0,
            anchor="ne",
            width=total_w,
            bordermode="outside",
        )
        # 确保在最上层
        tk.Misc.tkraise(sb)

        scrollable_frame._scrollbar = sb
        scrollable_frame._overlay_scrollbar = sb

        # 创建后短暂显示，让用户知道滚动条位置
        sb.show()
        sb._schedule_hide()
    except Exception:
        pass


# ============================================================
# 配置管理器
# ============================================================
def get_portable_dir():
    """获取便携数据目录（EXE 同级 data/ 文件夹）。
    打包环境下尝试创建并写入测试，成功则返回便携路径，失败返回 None。
    """
    if not getattr(sys, 'frozen', False):
        return None  # 开发环境不启用便携模式
    exe_dir = Path(sys.executable).parent
    portable = exe_dir / "data"
    try:
        portable.mkdir(parents=True, exist_ok=True)
        test = portable / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return portable
    except Exception:
        return None


def get_base_dir():
    """获取应用基础目录：便携优先，回退到用户目录。"""
    portable = get_portable_dir()
    if portable:
        return portable
    return Path.home() / ".zhixing_workbench"


def _smart_sync_file(src_file: Path, dst_file: Path):
    """单向同步：若源较新/目标不存在则拷贝；目标有则先 .bak 备份。"""
    if not src_file.exists():
        return False
    if dst_file.exists():
        # 相同文件跳过
        try:
            if src_file.stat().st_size == dst_file.stat().st_size and \
               abs(src_file.stat().st_mtime - dst_file.stat().st_mtime) < 2:
                return False
        except Exception:
            pass
        # 较旧才覆盖（双向同步时双方都比较新的覆盖旧的）
        if src_file.stat().st_mtime <= dst_file.stat().st_mtime:
            return False
        try:
            dst_file.rename(str(dst_file) + ".bak")
        except Exception:
            pass
    import shutil
    try:
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_file), str(dst_file))
        return True
    except Exception:
        return False


def _sync_settings_clear_data_dir(src: Path, dst: Path):
    """同步 app_settings.json 并清理 data_dir（便携模式用相对路径）。"""
    try:
        import json as _json
        with open(src, "r", encoding="utf-8") as f:
            s = _json.load(f)
    except Exception:
        return False
    s.pop("data_dir", None)
    try:
        with open(dst, "w", encoding="utf-8") as f:
            _json.dump(s, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def migrate_to_portable(portable_dir):
    """便携模式每次启动时，智能在用户目录和便携目录间按修改时间同步。
    规则：对 config.json / app_settings.json / error.log，哪边文件更新就用哪边覆盖旧方，
    覆盖前自动留 .bak，防止覆盖丢失。
    """
    old_dir = Path.home() / ".zhixing_workbench"
    portable_dir = Path(portable_dir)
    if not old_dir.exists():
        return False
    import shutil as _shutil
    migrated = False
    for fn in ("config.json", "error.log"):
        sf = old_dir / fn
        df = portable_dir / fn
        # 双方向，取较新覆盖较旧
        migrated = _smart_sync_file(sf, df) or migrated
        migrated = _smart_sync_file(df, sf) or migrated
    # app_settings.json 分别处理（便携侧去除 data_dir 指向）
    old_s = old_dir / "app_settings.json"
    new_s = portable_dir / "app_settings.json"
    if old_s.exists():
        if not new_s.exists() or old_s.stat().st_mtime > new_s.stat().st_mtime:
            # 把旧设置同步到便携（去掉 data_dir）
            if new_s.exists():
                try:
                    new_s.rename(str(new_s) + ".bak")
                except Exception:
                    pass
            migrated = _sync_settings_clear_data_dir(old_s, new_s) or migrated
        elif new_s.exists() and new_s.stat().st_mtime > old_s.stat().st_mtime:
            # 便携侧较新 -> 覆盖旧侧（保持便携的全部字段）
            migrated = _smart_sync_file(new_s, old_s) or migrated
    elif new_s.exists():
        migrated = _smart_sync_file(new_s, old_s) or migrated
    return migrated


class ConfigManager:
    """管理应用数据的持久化存储（待办和笔记加密保存）"""

    # 基础目录：便携模式用 EXE 同级 data/，否则用用户目录
    _base_dir = get_base_dir()

    # 记录用户自定义数据位置的小文件
    SETTINGS_FILE = _base_dir / "app_settings.json"

    def __init__(self):
        self._app_dir = self._base_dir
        self._app_dir.mkdir(parents=True, exist_ok=True)
        self._save_lock = threading.Lock()
        self._save_thread = None
        self._save_pending = False  # v2.5.0 防抖：保存期间又有变更则补存

        # 便携模式（U 盘/绿色版）：零留痕原则 —— 不触碰主机任何目录
        # 既不把便携数据同步到主机 ~/.zhixing_workbench，也不读取主机已有内容
        if not get_portable_dir():
            # 非便携（安装版）：才允许把旧主机数据迁移到便携侧（按需）
            migrate_to_portable(self._app_dir)

        # 读取用户自定义的数据路径（如果有）
        self._data_dir = self._read_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self._data_dir / "config.json"
        self._password = None       # 登录后设置
        self._unlocked = False      # 数据是否已解密
        self.todos = []             # 内存中的明文数据
        self.notes = []
        self.shortcuts = []         # 快捷启动项
        self.load()

    def _read_data_dir(self):
        """读取数据目录：便携模式强制落 EXE 同级 data/（零留痕），非便携才允许自定义路径"""
        # 便携模式：忽略 app_settings.json 里的 data_dir，坚决不把数据写到别处
        if get_portable_dir():
            return self._app_dir
        try:
            if self.SETTINGS_FILE.exists():
                import json as _json
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = _json.load(f)
                custom = settings.get("data_dir")
                if custom and Path(custom).exists():
                    return Path(custom)
        except Exception:
            pass
        return self._app_dir  # 默认：~/.zhixing_workbench

    def _read_settings(self):
        """读取 app_settings.json 全部内容"""
        import json as _json
        try:
            if self.SETTINGS_FILE.exists():
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return _json.load(f)
        except Exception:
            pass
        return {}

    def _write_settings(self, settings):
        """写入 app_settings.json（合并已有字段）"""
        import json as _json
        old = self._read_settings()
        old.update(settings)
        with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
            _json.dump(old, f, ensure_ascii=False, indent=2)

    def _write_data_dir(self, path_str):
        """写入自定义数据目录到 app_settings.json"""
        self._write_settings({"data_dir": path_str})

    def get_remember_password(self):
        """是否记住密码"""
        return self._read_settings().get("remember_password", False)

    def get_saved_password(self):
        """获取保存的密码（明文，仅本地存储）"""
        return self._read_settings().get("saved_password", "")

    def set_remember_password(self, remember, password=""):
        """设置记住密码"""
        if remember and password:
            self._write_settings({"remember_password": True, "saved_password": password})
        else:
            self._write_settings({"remember_password": False, "saved_password": ""})

    def get_nav_drag_enabled(self):
        """是否允许导航栏拖拽排序（默认开启）"""
        return self._read_settings().get("nav_drag_enabled", True)

    def set_nav_drag_enabled(self, enabled):
        """设置是否允许导航栏拖拽排序"""
        self._write_settings({"nav_drag_enabled": bool(enabled)})

    # ============================================================
    # v3.0.1 快捷启动：分类记忆 + 重命名开关
    # ============================================================
    def get_last_view_category(self) -> str:
        """获取上次用户停留的分类选项卡（跨会话记忆，默认「全部」）"""
        try:
            s = self._read_settings()
            return str(s.get("last_view_category", "全部"))
        except Exception:
            return "全部"

    def set_last_view_category(self, cat: str):
        """切换分类时记住 — 下次启动直接回到这个分类"""
        try:
            self._write_settings({"last_view_category": str(cat)})
        except Exception:
            pass

    def get_category_rename_enabled(self) -> bool:
        """分类是否允许右键重命名/删除（总开关）"""
        try:
            s = self._read_settings()
            return bool(s.get("category_rename_enabled", True))
        except Exception:
            return True

    def set_category_rename_enabled(self, enabled: bool):
        try:
            self._write_settings({"category_rename_enabled": bool(enabled)})
        except Exception:
            pass

    def get_auto_dock_enabled(self):
        """窗口是否启用靠边自动收纳（类似 QQ），默认关"""
        return self._read_settings().get("auto_dock_enabled", False)

    def set_auto_dock_enabled(self, enabled):
        """设置窗口靠边自动收纳开关"""
        self._write_settings({"auto_dock_enabled": bool(enabled)})

    def get_auto_lock_minutes(self):
        """自动锁屏时间（分钟）：0 表示关闭"""
        return int(self._read_settings().get("auto_lock_minutes", 0) or 0)

    def set_auto_lock_minutes(self, minutes):
        """设置自动锁屏时间（分钟）：0 表示关闭"""
        self._write_settings({"auto_lock_minutes": max(0, int(minutes))})

    def get_data_dir(self):
        """返回当前数据目录"""
        return self._data_dir

    def is_custom_data_dir(self):
        """是否使用了自定义数据目录"""
        return self._data_dir != self._app_dir

    def migrate_data_dir(self, new_dir_str):
        """迁移数据到新目录，返回 (成功, 消息)"""
        new_dir = Path(new_dir_str)
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
            # 复制 config.json 到新位置
            if self.config_file.exists():
                import shutil
                shutil.copy2(str(self.config_file), str(new_dir / "config.json"))
            # 更新路径
            old_file = self.config_file
            self._data_dir = new_dir
            self.config_file = new_dir / "config.json"
            # 记录新路径
            self._write_data_dir(str(new_dir))
            return True, f"数据已迁移到：{new_dir}"
        except Exception as e:
            return False, f"迁移失败：{e}"

    def reset_data_dir(self):
        """恢复为默认数据目录"""
        try:
            self._write_data_dir(str(self._app_dir))
            return True, "已恢复默认数据路径"
        except Exception as e:
            return False, f"恢复失败：{e}"

    def _default_config(self):
        return {
            "password_hash": self._hash("868899"),
            "theme": "dark",
            "accent": "blue",
            "enc_data": "",          # 加密的 todos+notes
            "enc_salt": "",          # 加密盐
            "integrity_hmac": "",    # 篡改检测校验值
            "version": APP_VERSION,
            "created_at": datetime.now().isoformat(),
            # v3.0.1 全局持久化：上次停留在哪个快捷启动分类
            "last_view_category": "全部",
            # v3.0.1 分类重命名/删除 总开关（设置-导航设置里可切换）
            "category_rename_enabled": True,
            # v3.0.1 分类自定义顺序（不含「全部」）
            "category_order": [],
            # v3.1 窗口几何持久化："WxH+X+Y" 格式
            "window_geometry": "",
        }

    @staticmethod
    def _hash(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def _hmac(key_str: str, data: str) -> str:
        """生成 HMAC-SHA256 校验值"""
        import hmac as _hmac
        return _hmac.new(
            key_str.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def load(self):
        # .tmp 文件残留清理：如果 .tmp 存在且 .json 不存在或更旧，用 .tmp 恢复
        try:
            tmp_f = self.config_file.with_suffix(self.config_file.suffix + ".tmp")
            if tmp_f.exists():
                if not self.config_file.exists() or \
                   tmp_f.stat().st_mtime >= self.config_file.stat().st_mtime:
                    import shutil as _shutil
                    _shutil.move(str(tmp_f), str(self.config_file))
                else:
                    tmp_f.unlink()
        except Exception:
            pass

        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                # 确保所有字段存在
                defaults = self._default_config()
                for key, val in defaults.items():
                    if key not in self.config:
                        self.config[key] = val

                # 明文 t/n/s 读到内存里（未登录期已保存的数据）
                has_plain = ("todos" in self.config or
                             "notes" in self.config or
                             "shortcuts" in self.config)
                if has_plain:
                    self.todos = list(self.config.get("todos") or [])
                    self.notes = list(self.config.get("notes") or [])
                    self.shortcuts = list(self.config.get("shortcuts") or [])
                    self._needs_migration = True
                else:
                    self.todos = []
                    self.notes = []
                    self.shortcuts = []
                    self._needs_migration = False
            except (json.JSONDecodeError, KeyError):
                self.config = self._default_config()
                self.todos = []
                self.notes = []
                self.shortcuts = []
                self.save()
        else:
            self.config = self._default_config()
            self.todos = []
            self.notes = []
            self.shortcuts = []
            self.save()

    def unlock(self, password):
        """登录成功后调用：用密码解密数据；若有未登录期临时明文数据则合并。"""
        # 先记住明文缓存（未登录期新增的），解密后按 id 合并
        plain_todos = list(self.todos or [])
        plain_notes = list(self.notes or [])
        plain_shortcuts = list(self.shortcuts or [])
        needs_merge = bool(plain_todos or plain_notes or plain_shortcuts)

        self._password = password
        self._unlocked = True

        if getattr(self, "_needs_migration", False) and not self.config.get("enc_data"):
            # 纯明文数据，没有加密过：直接保存为加密格式
            self.save()
            self._needs_migration = False
        elif self.config.get("enc_data"):
            # 解密已有加密数据
            try:
                plain = decrypt_data(
                    self.config["enc_data"],
                    self.config["enc_salt"],
                    password,
                )
                data = json.loads(plain)
                self.todos = data.get("todos", [])
                self.notes = data.get("notes", [])
                self.shortcuts = data.get("shortcuts", [])
            except Exception:
                self.todos = []
                self.notes = []
                self.shortcuts = []
            # 未登录期有明文：按 id 合并（加密数据里没有的 id 才加进去）
            if needs_merge:
                def _merge(existing, incoming, key="id"):
                    ids = {x.get(key) for x in existing if isinstance(x, dict)}
                    for item in incoming:
                        if isinstance(item, dict) and item.get(key) not in ids:
                            existing.append(item)
                            ids.add(item.get(key))
                _merge(self.todos, plain_todos)
                _merge(self.notes, plain_notes)
                _merge(self.shortcuts, plain_shortcuts)
        # 合并完立即重存：明文副本会被清掉并重新写入 enc_data
        self.save()

    def save(self):
        """v2.5.0 防抖保存：后台线程写盘，不阻塞 UI
        若已有保存在进行中，标记 _save_pending，当前保存完成后自动补存最新状态，
        保证最后一次变更不丢失（替代旧的"忙碌即丢弃"策略）。
        """
        if self._save_lock.locked():
            self._save_pending = True
            return
        if not self._save_lock.acquire(blocking=False):
            self._save_pending = True
            return

        def _do_save():
            try:
                self._save_sync()
                while getattr(self, "_save_pending", False):
                    self._save_pending = False
                    self._save_sync()
            except Exception:
                self._log_save_error()
            finally:
                try:
                    self._save_lock.release()
                except Exception:
                    pass

        self._save_thread = threading.Thread(target=_do_save, daemon=True)
        self._save_thread.start()

    def _log_save_error(self):
        """v2.5.0 保存失败写入 error.log，避免静默吞掉数据丢失"""
        try:
            import traceback
            log_path = get_base_dir() / "error.log"
            log_path.parent.mkdir(exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n[%s] 保存失败:\n" % datetime.now().isoformat())
                f.write(traceback.format_exc())
        except Exception:
            pass

    def flush(self):
        """强制同步保存（退出时调用）
        v2.5.0：获取 _save_lock 后再写盘，避免与后台保存线程并发写同一文件。
        """
        self._save_lock.acquire()
        try:
            self._save_sync()
        except Exception:
            self._log_save_error()
        finally:
            try:
                self._save_lock.release()
            except Exception:
                pass

    def _save_sync(self):
        """实际同步保存（原 save 逻辑）

        保存配置：
        - 已登录解锁：加密存储（enc_data）+ 明文字段
        - 未登录：以明文保存 todos/notes/shortcuts，保证关机不丢；
          下次登录后会自动重新加密（加密后会自动清除明文字段）
        """
        # v2.5.0 快照：后台线程序列化期间 UI 线程可能修改列表，先浅拷贝避免并发修改异常
        todos_snap = list(self.todos)
        notes_snap = list(self.notes)
        shortcuts_snap = list(self.shortcuts)
        have_data = bool(todos_snap or notes_snap or shortcuts_snap)
        if self._unlocked and self._password:
            # 加密敏感数据
            payload = json.dumps(
                {"todos": todos_snap, "notes": notes_snap,
                 "shortcuts": shortcuts_snap},
                ensure_ascii=False,
            )
            enc, salt = encrypt_data(payload, self._password)
            self.config["enc_data"] = enc
            self.config["enc_salt"] = salt
            signed = self.config["password_hash"] + enc + salt
            self.config["integrity_hmac"] = self._hmac(
                self.config["password_hash"], signed
            )
            # 已加密，不再保留明文副本，避免解密/加密不一致
            self.config.pop("todos", None)
            self.config.pop("notes", None)
            self.config.pop("shortcuts", None)
            # 明文数据迁移标记清除
            self._needs_migration = False
        elif have_data:
            # ⚠️ 未登录但有内存数据：以明文临时保存到 config，
            # 防止程序关闭后丢失。登录后 unlock() 会合并并重新加密。
            self.config["todos"] = todos_snap
            self.config["notes"] = notes_snap
            self.config["shortcuts"] = shortcuts_snap
            self._needs_migration = True
        # 写出：除了安全排除项（明文冗余清理），其余原样保留
        if self._unlocked and self._password:
            safe_config = {k: v for k, v in self.config.items()
                           if k not in ("todos", "notes", "shortcuts")}
        else:
            safe_config = dict(self.config)
        # 原子写：先写 .tmp 再 fsync 再覆盖，防止写一半进程崩导致文件损坏
        import shutil as _shutil
        tmp_file = self.config_file.with_suffix(self.config_file.suffix + ".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(safe_config, f, ensure_ascii=False, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            _shutil.move(str(tmp_file), str(self.config_file))
        except Exception:
            # 回退：直接写原文件
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(safe_config, f, ensure_ascii=False, indent=2)
            except Exception:
                raise

    # --- 密码管理 ---
    def verify_password(self, password):
        """验证密码并检测篡改，返回 (通过, 错误类型)"""
        pw_hash = self._hash(password)
        stored_hash = self.config.get("password_hash", "")

        if pw_hash != stored_hash:
            return False, "wrong_password"

        # 密码正确，检查完整性
        enc_data = self.config.get("enc_data", "")
        enc_salt = self.config.get("enc_salt", "")
        stored_hmac = self.config.get("integrity_hmac", "")

        # 如果没有加密数据（首次使用或重置后），跳过校验
        if not enc_data or not stored_hmac:
            return True, "ok"

        # 重新计算 HMAC 并比较
        signed = stored_hash + enc_data + enc_salt
        expected_hmac = self._hmac(stored_hash, signed)

        if expected_hmac != stored_hmac:
            # 配置文件被篡改
            return False, "tampered"

        return True, "ok"

    def change_password(self, old_pw, new_pw, confirm_pw):
        ok, status = self.verify_password(old_pw)
        if not ok:
            if status == "tampered":
                return False, "配置文件已被篡改，无法修改密码"
            return False, "原密码错误"
        if len(new_pw) < 6:
            return False, "新密码长度不能少于6位"
        if new_pw != confirm_pw:
            return False, "两次输入的密码不一致"
        if new_pw == old_pw:
            return False, "新密码不能与原密码相同"
        # 更新密码哈希
        self.config["password_hash"] = self._hash(new_pw)
        # 用新密码重新加密数据
        self._password = new_pw
        self.save()
        return True, "密码修改成功"

    def is_first_run(self):
        """判断是否首次运行（密码仍为默认密码且无加密数据）"""
        default_hash = self._hash("868899")
        return (self.config.get("password_hash") == default_hash
                and not self.config.get("enc_data"))

    def set_initial_password(self, password):
        """首次设置密码（注册）"""
        self.config["password_hash"] = self._hash(password)
        self._password = password
        self._unlocked = True
        self.config["created_at"] = datetime.now().isoformat()
        self.save()

    # --- 待办事项 ---
    def add_todo(self, content, priority="normal"):
        todo = {
            "id": max([t["id"] for t in self.todos], default=0) + 1,
            "content": content,
            "priority": priority,
            "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.todos.append(todo)
        self.save()
        return todo

    def toggle_todo(self, todo_id):
        for t in self.todos:
            if t["id"] == todo_id:
                t["done"] = not t["done"]
                self.save()
                return t["done"]
        return None

    def delete_todo(self, todo_id):
        self.todos = [t for t in self.todos if t["id"] != todo_id]
        self.save()

    def update_todo(self, todo_id, content):
        """更新待办内容"""
        for t in self.todos:
            if t["id"] == todo_id:
                t["content"] = content
                self.save()
                return True
        return False

    # --- 笔记 ---
    def add_note(self, title, content):
        note = {
            "id": max([n["id"] for n in self.notes], default=0) + 1,
            "title": title,
            "content": content,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.notes.append(note)
        self.save()
        return note

    def delete_note(self, note_id):
        self.notes = [n for n in self.notes if n["id"] != note_id]
        self.save()

    def update_note(self, note_id, title, content):
        """更新笔记标题和内容"""
        for n in self.notes:
            if n["id"] == note_id:
                n["title"] = title
                n["content"] = content
                n["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.save()
                return True
        return False

    # --- 统计 ---
    def get_stats(self):
        return {
            "total_todos": len(self.todos),
            "done_todos": sum(1 for t in self.todos if t["done"]),
            "pending_todos": sum(1 for t in self.todos if not t["done"]),
            "total_notes": len(self.notes),
            "total_shortcuts": len(self.shortcuts),
        }

    # --- 快捷启动 ---
    def add_shortcut(self, name, stype, path, icon=None, category="默认"):
        sc = {
            "id": max([s["id"] for s in self.shortcuts], default=0) + 1,
            "name": name,
            "type": stype,       # "app" / "url" / "system"
            "path": path,
            "icon": icon,         # base64 PNG 或 None
            "category": category,
            "sort": len(self.shortcuts),
        }
        self.shortcuts.append(sc)
        self.save()
        return sc

    def update_shortcut(self, sc_id, **kwargs):
        for s in self.shortcuts:
            if s["id"] == sc_id:
                for k, v in kwargs.items():
                    s[k] = v
                self.save()
                return True
        return False

    def delete_shortcut(self, sc_id):
        self.shortcuts = [s for s in self.shortcuts if s["id"] != sc_id]
        self.save()

    def get_shortcut_categories(self):
        cats_raw = set(s.get("category", "默认") for s in self.shortcuts)
        if not cats_raw:
            return ["默认"]
        cats = list(cats_raw)
        try:
            order = self.get_cat_order()
        except Exception:
            order = []
        # 按已记录的顺序排前面；未记录的按字母序追加到后面
        ordered = [c for c in order if c in cats]
        rest = sorted([c for c in cats if c not in ordered])
        return ordered + rest if (ordered or not rest) else rest

    def get_cat_order(self):
        """获取分类自定义顺序（不包含「全部」）"""
        try:
            s = self._read_settings()
            return list(s.get("category_order", []))
        except Exception:
            return []

    def set_cat_order(self, order_list):
        """设置分类顺序（只接受不含「全部」的真实分类列表）"""
        try:
            filtered = [str(c) for c in order_list if str(c) != "全部"]
            self._write_settings({"category_order": filtered})
        except Exception:
            pass

    def swap_cat_order(self, cat_a, cat_b):
        """交换两个分类的位置（都不含「全部」）"""
        try:
            order = self.get_cat_order()
            # 确保 order 已包含所有当前分类（避免新分类不在列表里导致交换无效）
            cats_raw = set(s.get("category", "默认") for s in self.shortcuts)
            for c in cats_raw:
                if c not in order:
                    order.append(c)
            if cat_a in order and cat_b in order:
                ia, ib = order.index(cat_a), order.index(cat_b)
                order[ia], order[ib] = order[ib], order[ia]
                self.set_cat_order(order)
        except Exception:
            pass

    def rename_category(self, old_name, new_name):
        """重命名分类"""
        if old_name == new_name:
            return
        for s in self.shortcuts:
            if s.get("category", "默认") == old_name:
                s["category"] = new_name
        self.save()

    def delete_category(self, cat_name):
        """删除分类，其中的快捷方式归入'默认'"""
        for s in self.shortcuts:
            if s.get("category", "默认") == cat_name:
                s["category"] = "默认"
        self.save()

    def reorder_shortcuts(self, ordered_ids):
        """按给定的 id 顺序重新设置 sort 字段"""
        for i, sid in enumerate(ordered_ids):
            for s in self.shortcuts:
                if s["id"] == sid:
                    s["sort"] = i
                    break
        self.save()

    def sort_shortcuts(self, key_func, reverse=False):
        """按指定 key 函数对所有快捷方式进行排序并写入 sort 字段
        key_func: 接收 shortcut dict，返回可比较的 key
        reverse: 是否倒序
        注意：置顶项始终保持在前，其相对顺序也按 key 排序"""
        # 分两组：置顶 / 非置顶
        pinned = [s for s in self.shortcuts if s.get("pinned", False)]
        others = [s for s in self.shortcuts if not s.get("pinned", False)]
        pinned.sort(key=key_func, reverse=reverse)
        others.sort(key=key_func, reverse=reverse)
        ordered = pinned + others
        # 写回 sort 字段（同步内存顺序）
        for i, s in enumerate(ordered):
            s["sort"] = i
        # 同步 self.shortcuts 顺序
        self.shortcuts.sort(key=lambda s: s.get("sort", 0))
        self.save()

    def get_ordered_shortcuts(self):
        """返回排序后的快捷方式列表（置顶项优先，再按 sort）"""
        return sorted(self.shortcuts,
                       key=lambda s: (not s.get("pinned", False), s.get("sort", 0)))

    # --- 导航栏自定义 ---
    def get_nav_labels(self):
        """获取自定义导航标签（key=原始标签, value=自定义标签）"""
        return self.config.get("nav_labels", {})

    def set_nav_label(self, original_label, custom_label):
        """设置单个导航标签的自定义名称"""
        if "nav_labels" not in self.config:
            self.config["nav_labels"] = {}
        if custom_label and custom_label != original_label:
            self.config["nav_labels"][original_label] = custom_label
        elif original_label in self.config["nav_labels"]:
            del self.config["nav_labels"][original_label]
        self.save()

    def get_nav_order(self):
        """获取导航项排序（返回原始标签列表）"""
        return self.config.get("nav_order", [])

    def set_nav_order(self, order_list):
        """设置导航项排序"""
        self.config["nav_order"] = order_list
        self.save()

    def get_window_geometry(self) -> str:
        """v3.1 读取上次关闭前的窗口大小与位置，返回 "WxH+X+Y"；空字符串表示未记录"""
        try:
            return str(self.config.get("window_geometry", "") or "")
        except Exception:
            return ""

    def set_window_geometry(self, w: int, h: int, x: int, y: int):
        """v3.1 记录当前窗口大小与位置"""
        try:
            self.config["window_geometry"] = f"{int(w)}x{int(h)}+{int(x)}+{int(y)}"
            self.save()
        except Exception:
            pass


# ============================================================
# 登录界面
# ============================================================
class LoginFrame(ctk.CTkFrame):
    """登录界面"""

    def __init__(self, master, config, on_login_success):
        super().__init__(master)
        self.config = config
        self.on_login_success = on_login_success
        self._password = None
        self.configure(fg_color="transparent")
        self._build()

    def _build(self):
        # 居中容器
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # 应用标题
        title_label = ctk.CTkLabel(
            center,
            text=APP_NAME,
            font=ctk.CTkFont(family="微软雅黑", size=36, weight="bold"),
        )
        title_label.pack(pady=(0, 5))

        # 副标题
        slogan_label = ctk.CTkLabel(
            center,
            text=APP_SLOGAN,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            text_color="gray60",
        )
        slogan_label.pack(pady=(0, 40))

        # 密码输入
        self.pw_entry = ctk.CTkEntry(
            center,
            placeholder_text="请输入密码",
            show="*",
            width=280,
            height=42,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            border_width=2,
        )
        self.pw_entry.pack(pady=(0, 15))
        self.pw_entry.bind("<Return>", lambda e: self._on_login())
        self.pw_entry.focus_set()

        # 登录按钮
        self.login_btn = ctk.CTkButton(
            center,
            text="登 录",
            width=280,
            height=42,
            font=ctk.CTkFont(family="微软雅黑", size=15, weight="bold"),
            command=self._on_login,
        )
        self.login_btn.pack(pady=(0, 10))

        # 记住密码复选框
        self.remember_var = ctk.BooleanVar(value=self.config.get_remember_password())
        remember_cb = ctk.CTkCheckBox(
            center,
            text="记住密码",
            variable=self.remember_var,
            font=ctk.CTkFont(family="微软雅黑", size=12),
            height=20,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
        )
        remember_cb.pack(pady=(0, 5))

        # 如果记住密码，自动填充
        if self.remember_var.get():
            saved = self.config.get_saved_password()
            if saved:
                self.pw_entry.insert(0, saved)

        # 错误提示
        self.error_label = ctk.CTkLabel(
            center,
            text="",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="#e74c3c",
        )
        self.error_label.pack(pady=(5, 0))

        # 版本信息 + 版权（登录页辅助展示）
        _ver_box = ctk.CTkFrame(center, fg_color="transparent")
        _ver_box.pack(pady=(50, 0))
        ctk.CTkLabel(
            _ver_box, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=11, weight="bold"),
            text_color=("gray46", "gray56"),
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            _ver_box, text=f"© 2026 {COPYRIGHT_OWNER} · {COPYRIGHT_SITE}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=10),
            text_color=("gray42", "gray52"),
        ).pack()

    def _on_login(self):
        pw = self.pw_entry.get().strip()
        if not pw:
            self.error_label.configure(text="请输入密码")
            return
        ok, status = self.config.verify_password(pw)
        if ok:
            self.error_label.configure(text="")
            self._password = pw
            # 保存或清除记住的密码
            self.config.set_remember_password(self.remember_var.get(), pw)
            self.on_login_success()
        elif status == "tampered":
            from tkinter import messagebox
            self.error_label.configure(text="")
            messagebox.showerror(
                "安全警告",
                "检测到配置文件已被篡改！\n\n"
                "密码哈希或加密数据被修改，为保护数据安全，\n"
                "应用拒绝登录。\n\n"
                "如需重置，请删除配置文件后重新启动应用\n"
                "（注意：重置后所有数据将丢失）。",
            )
            self.pw_entry.delete(0, "end")
        else:
            self.error_label.configure(text="密码错误，请重新输入")
            self.pw_entry.delete(0, "end")

    def get_password(self):
        return self._password


# ============================================================
# 首次启动设置密码界面
# ============================================================
class SetupPasswordFrame(ctk.CTkFrame):
    """首次使用时引导用户设置密码"""

    def __init__(self, master, config, on_setup_success):
        super().__init__(master)
        self.config = config
        self.on_setup_success = on_setup_success
        self._password = None
        self.configure(fg_color="transparent")
        self._build()

    def _build(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # 欢迎标题
        title_label = ctk.CTkLabel(
            center,
            text="欢迎使用知行工作台",
            font=ctk.CTkFont(family="微软雅黑", size=32, weight="bold"),
        )
        title_label.pack(pady=(0, 5))

        # 副标题
        subtitle_label = ctk.CTkLabel(
            center,
            text="首次使用，请设置登录密码",
            font=ctk.CTkFont(family="微软雅黑", size=14),
            text_color="gray60",
        )
        subtitle_label.pack(pady=(0, 8))

        # 安全提示
        tip_label = ctk.CTkLabel(
            center,
            text="密码用于加密保护您的待办、笔记、快捷启动数据\n请牢记密码，遗忘后数据将无法恢复",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color=("gray50", "gray55"),
            justify="center",
        )
        tip_label.pack(pady=(0, 25))

        # 密码输入
        self.pw_entry = ctk.CTkEntry(
            center,
            placeholder_text="请设置密码（至少6位）",
            show="*",
            width=280,
            height=42,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            border_width=2,
        )
        self.pw_entry.pack(pady=(0, 12))
        self.pw_entry.focus_set()

        # 确认密码
        self.pw_confirm_entry = ctk.CTkEntry(
            center,
            placeholder_text="请再次输入密码",
            show="*",
            width=280,
            height=42,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            border_width=2,
        )
        self.pw_confirm_entry.pack(pady=(0, 15))
        self.pw_confirm_entry.bind("<Return>", lambda e: self._on_setup())

        # 设置按钮
        self.setup_btn = ctk.CTkButton(
            center,
            text="完成设置",
            width=280,
            height=42,
            font=ctk.CTkFont(family="微软雅黑", size=15, weight="bold"),
            command=self._on_setup,
        )
        self.setup_btn.pack(pady=(0, 10))

        # 错误提示
        self.error_label = ctk.CTkLabel(
            center,
            text="",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="#e74c3c",
        )
        self.error_label.pack(pady=(5, 0))

        # 版本信息 + 版权（设置密码页辅助展示）
        _setup_ver_box = ctk.CTkFrame(center, fg_color="transparent")
        _setup_ver_box.pack(pady=(40, 0))
        ctk.CTkLabel(
            _setup_ver_box, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=11, weight="bold"),
            text_color=("gray46", "gray56"),
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            _setup_ver_box, text=f"© 2026 {COPYRIGHT_OWNER} · {COPYRIGHT_SITE}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=10),
            text_color=("gray42", "gray52"),
        ).pack()

    def _on_setup(self):
        pw = self.pw_entry.get().strip()
        pw2 = self.pw_confirm_entry.get().strip()

        if not pw:
            self.error_label.configure(text="请输入密码")
            return
        if len(pw) < 6:
            self.error_label.configure(text="密码长度不能少于6位")
            return
        if pw != pw2:
            self.error_label.configure(text="两次输入的密码不一致")
            return

        self.error_label.configure(text="")
        self._password = pw
        self.on_setup_success(pw)

    def get_password(self):
        return self._password


# ============================================================
# 视图基类
# ============================================================
def _get_daily_quote(now=None):
    """根据日期取稳定的「每日金句」（同一天永远返回同一句，跨会话一致）
    中英双语版：返回 (cn_text, en_text, author)
    策略：以日期（年月日）为种子，对金句列表取模"""
    QUOTES = [
        # ---- 中国经典 / Chinese Classics ----
        ("千里之行，始于足下",
         "A journey of a thousand miles begins with a single step.",
         "老子《道德经》 / Laozi, Tao Te Ching"),
        ("合抱之木，生于毫末；九层之台，起于累土",
         "A tree so thick it takes two arms to embrace grows from a tiny sprout; a nine-story tower rises from a basket of earth.",
         "老子《道德经》 / Laozi, Tao Te Ching"),
        ("上善若水，水善利万物而不争",
         "The highest goodness is like water; water benefits all things and does not compete with them.",
         "老子《道德经》 / Laozi, Tao Te Ching"),
        ("不积跬步，无以至千里；不积小流，无以成江海",
         "Not accumulating small steps, you cannot reach a thousand miles; not gathering tiny streams, you cannot form a river or sea.",
         "荀子《劝学》 / Xunzi, Exhortation to Learning"),
        ("锲而舍之，朽木不折；锲而不舍，金石可镂",
         "If you chisel and give up, even rotten wood will not break; if you chisel without stopping, even metal and stone can be carved.",
         "荀子《劝学》 / Xunzi, Exhortation to Learning"),
        ("生于忧患，死于安乐",
         "Thrive in calamity and perish in soft living.",
         "孟子《告子下》 / Mencius"),
        ("天行健，君子以自强不息",
         "As heaven moves ever onward, so the noble person never ceases to strive for self-improvement.",
         "《周易·乾卦》 / I Ching, Hexagram Qian"),
        ("地势坤，君子以厚德载物",
         "The earth is vast and receptive; the noble person holds all things with profound virtue.",
         "《周易·坤卦》 / I Ching, Hexagram Kun"),
        ("苟日新，日日新，又日新",
         "If you can renew yourself one day, do so every day, and keep renewing day after day.",
         "《礼记·大学》 / Book of Rites, Great Learning"),
        ("博学之，审问之，慎思之，明辨之，笃行之",
         "Learn broadly, inquire thoroughly, think carefully, distinguish clearly, and practice firmly.",
         "《礼记·中庸》 / Book of Rites, Doctrine of the Mean"),
        ("路漫漫其修远兮，吾将上下而求索",
         "The road ahead is long and far; I will search high and low.",
         "屈原《离骚》 / Qu Yuan, Li Sao"),
        ("己所不欲，勿施于人",
         "Do not do to others what you would not want done to yourself.",
         "《论语·卫灵公》 / Analects, Duke Ling of Wei"),
        ("学而不思则罔，思而不学则殆",
         "Learning without thought is labor lost; thought without learning is perilous.",
         "《论语·为政》 / Analects, Government"),
        ("三人行，必有我师焉",
         "When I walk along with two others, they may serve me as my teachers.",
         "《论语·述而》 / Analects, No. 7"),
        ("士不可以不弘毅，任重而道远",
         "A gentleman must be resolute and enduring; his burden is heavy and his road is long.",
         "《论语·泰伯》 / Analects, No. 8"),
        ("非淡泊无以明志，非宁静无以致远",
         "Without tranquility one cannot have a clear purpose; without calm one cannot reach far.",
         "诸葛亮《诫子书》 / Zhuge Liang"),
        ("志当存高远",
         "Be ambitious and reach for the stars.",
         "诸葛亮《诫外甥书》 / Zhuge Liang"),
        ("业精于勤，荒于嬉；行成于思，毁于随",
         "Excellence in work comes from diligence; it is wasted through idle play. Actions succeed from reflection; they fail from blind conformity.",
         "韩愈《进学解》 / Han Yu"),
        ("读书破万卷，下笔如有神",
         "Having read ten thousand volumes, one writes as if guided by the gods.",
         "杜甫《奉赠韦左丞丈二十二韵》 / Du Fu"),
        ("会当凌绝顶，一览众山小",
         "One day I shall reach the highest summit and see all mountains shrink below.",
         "杜甫《望岳》 / Du Fu"),
        ("长风破浪会有时，直挂云帆济沧海",
         "A time will come to ride the wind and cleave the waves; I will set my cloud-white sail to cross the great sea.",
         "李白《行路难》 / Li Bai"),
        ("纸上得来终觉浅，绝知此事要躬行",
         "What you get from books is always shallow; true understanding comes only from doing it yourself.",
         "陆游《冬夜读书示子聿》 / Lu You"),
        ("山重水复疑无路，柳暗花明又一村",
         "Where hills bend and streams wind, the road seems to end; past willow shade and bright blooms, another village appears.",
         "陆游《游山西村》 / Lu You"),
        ("问渠那得清如许，为有源头活水来",
         "Why is the channel so clear? Because fresh water flows from its source.",
         "朱熹《观书有感》 / Zhu Xi"),
        ("宝剑锋从磨砺出，梅花香自苦寒来",
         "A sword\'s sharp edge comes from grinding; a plum blossom\'s fragrance comes from bitter cold.",
         "《警世贤文》 / Ancient Proverbs"),
        ("海纳百川，有容乃大；壁立千仞，无欲则刚",
         "The ocean embraces all rivers; with tolerance comes greatness. A cliff stands a thousand feet tall; without desire, one is strong.",
         "林则徐 / Lin Zexu"),
        ("天下兴亡，匹夫有责",
         "The rise and fall of the nation is every person\'s responsibility.",
         "顾炎武 / Gu Yanwu"),
        ("时间就像海绵里的水，只要愿挤，总还是有的",
         "Time is like water in a sponge; if you are willing to squeeze, there is always some.",
         "鲁迅 / Lu Xun"),
        # ---- 西方经典 / Western Classics ----
        ("种一棵树最好的时间是十年前，其次是现在",
         "The best time to plant a tree was 20 years ago. The second best time is now.",
         "丹比萨·莫约 / Dambisa Moyo"),
        ("世界上只有一种真正的英雄主义，那就是在认清生活的真相之后依然热爱生活",
         "There is only one true heroism in the world: to see the world as it is and to love it anyway.",
         "罗曼·罗兰 / Romain Rolland"),
        ("我思故我在",
         "I think, therefore I am.",
         "笛卡尔 / René Descartes"),
        ("认识你自己",
         "Know thyself.",
         "苏格拉底 / Socrates"),
        ("不要因为走得太远，而忘记为什么出发",
         "Do not go so far that you forget why you started.",
         "纪伯伦 / Kahlil Gibran"),
        ("行动是治愈恐惧的良药，而犹豫拖延将不断滋养恐惧",
         "Action is the antidote to fear; hesitation and procrastination feed it.",
         "戴尔·卡耐基 / Dale Carnegie"),
        ("教育的根是苦的，但其果实是甜的",
         "The roots of education are bitter, but the fruit is sweet.",
         "亚里士多德 / Aristotle"),
        ("优于别人并不高贵，真正的高贵应该是优于过去的自己",
         "There is nothing noble in being superior to your fellow man. True nobility is in being superior to your former self.",
         "海明威 / Ernest Hemingway"),
        ("逻辑会带你从A到B，想象力能带你去任何地方",
         "Logic will get you from A to B. Imagination will take you everywhere.",
         "爱因斯坦 / Albert Einstein"),
        ("天才是百分之一的灵感加百分之九十九的汗水",
         "Genius is one percent inspiration and ninety-nine percent perspiration.",
         "爱迪生 / Thomas Edison"),
        ("合理安排时间，就等于节约时间",
         "To choose time is to save time.",
         "培根 / Francis Bacon"),
        ("罗马不是一天建成的",
         "Rome was not built in a day.",
         "西方谚语 / Western Proverb"),
    ]
    if now is None:
        from datetime import datetime
        now = datetime.now()
    seed = now.year * 10000 + now.month * 100 + now.day
    idx = seed % len(QUOTES)
    return QUOTES[idx]



class BaseView(ctk.CTkFrame):
    """所有视图的基类，支持扩展"""

    def __init__(self, master, config, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.configure(fg_color="transparent")
        self._build()

    def _build(self):
        """子类实现此方法构建界面"""
        pass

    def refresh(self):
        """子类实现此方法刷新数据"""
        pass


# ============================================================
# 首页视图
# ============================================================
class HomeView(BaseView):
    """首页 - 概览仪表板"""

    def _build(self):
        # 顶部欢迎
        now = datetime.now()
        hour = now.hour
        if hour < 6:
            greeting = "凌晨好"
        elif hour < 12:
            greeting = "早上好"
        elif hour < 14:
            greeting = "中午好"
        elif hour < 18:
            greeting = "下午好"
        else:
            greeting = "晚上好"

        # 星期强制中文（不依赖系统 locale，避免出现 Sunday/Monday 英文）
        weekdays_cn = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
        date_str = now.strftime("%Y年%m月%d日 ") + weekdays_cn[now.weekday()]

        # ============ 欢迎条：扁平化 两栏式 一体卡（左=问候+金句，右=时钟+日期）============
        welcome_frame = ctk.CTkFrame(self, fg_color=("gray92", "gray15"), corner_radius=20,
                                     border_width=1, border_color=("gray85", "gray22"))
        welcome_frame.pack(fill="x", padx=30, pady=(30, 20))

        # 左栏：问候 + 金句
        left_pane = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        left_pane.pack(side="left", fill="both", expand=True, padx=(32, 20), pady=28)

        # 右栏：时钟 + 日期（右对齐）
        right_pane = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        right_pane.pack(side="right", anchor="e", padx=(0, 32), pady=28)

        # --- 左栏 ---
        ctk.CTkLabel(
            left_pane,
            text=f"{greeting}！",
            anchor="w",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=24, weight="bold"),
        ).pack(side="top", anchor="w", pady=(0, 14))

        # 中英双语金句
        quote_cn, quote_en, quote_author = _get_daily_quote(now)
        ctk.CTkLabel(
            left_pane, text="Daily Quote  ·  每日金句",
            anchor="w",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=12, weight="bold"),
            text_color=("gray55", "gray65"),
        ).pack(anchor="w", pady=(6, 10))

        quote_cn_label = ctk.CTkLabel(
            left_pane,
            text=f"{quote_cn}",
            anchor="w", justify="left",
            font=ctk.CTkFont(family=("微软雅黑", "Segoe UI Variable"), size=15, weight="bold"),
            text_color=("gray20", "gray90"),
            wraplength=520,
        )
        quote_cn_label.pack(anchor="w", pady=(0, 6), fill="x")

        quote_en_label = ctk.CTkLabel(
            left_pane,
            text=f"{quote_en}",
            anchor="w", justify="left",
            font=ctk.CTkFont(family=("Segoe UI Variable", "Segoe UI"), size=13),
            text_color=("gray50", "gray62"),
            wraplength=520,
        )
        quote_en_label.pack(anchor="w", pady=(0, 10), fill="x")

        ctk.CTkLabel(
            left_pane,
            text=f"— {quote_author}",
            anchor="w", justify="left",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=11),
            text_color=("gray50", "gray60"),
        ).pack(anchor="w")

        # --- 右栏：时钟上，日期下（Win11 风格，蓝色大号字体，右对齐）---
        clock_label = ctk.CTkLabel(
            right_pane,
            text="",
            anchor="e", justify="right",
            font=ctk.CTkFont(family=("Segoe UI Variable", "Microsoft YaHei UI"), size=36, weight="bold"),
            text_color=("#2563EB", "#60A5FA"),
        )
        clock_label.pack(side="top", anchor="e")

        date_label = ctk.CTkLabel(
            right_pane,
            text=f"{date_str}",
            anchor="e", justify="right",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=13),
            text_color=("gray50", "gray62"),
        )
        date_label.pack(side="top", anchor="e", pady=(4, 0))

        # 实时时钟
        clock_label._welcome_clock_after = None
        def _tick_welcome_clock():
            try:
                if not clock_label.winfo_exists():
                    return
                tm = datetime.now()
                clock_label.configure(text=tm.strftime("%H:%M:%S"))
                date_label.configure(text=tm.strftime("%Y年%m月%d日 ") + weekdays_cn[tm.weekday()])
                clock_label._welcome_clock_after = clock_label.after(1000, _tick_welcome_clock)
            except Exception:
                pass
        def _stop_welcome_clock(_e=None):
            try:
                if clock_label._welcome_clock_after:
                    clock_label.after_cancel(clock_label._welcome_clock_after)
                    clock_label._welcome_clock_after = None
            except Exception:
                pass
        _tick_welcome_clock()
        welcome_frame.bind("<Destroy>", _stop_welcome_clock, add="+")

        # 金句响应式换行
        def _resize_welcome(e=None):
            try:
                w = left_pane.winfo_width() - 8
                if w > 200:
                    quote_cn_label.configure(wraplength=w)
                    quote_en_label.configure(wraplength=w)
            except Exception:
                pass
        left_pane.bind("<Configure>", lambda e: _resize_welcome())

        # 统计卡片
        stats = self.config.get_stats()
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=30, pady=10)

        card_data = [
            ("待办总数", str(stats["total_todos"]), "#4a90d9"),
            ("已完成", str(stats["done_todos"]), "#2fae73"),
            ("笔记数", str(stats["total_notes"]), "#9b7ec0"),
            ("快捷方式", str(stats.get("total_shortcuts", 0)), "#d96666"),
        ]

        for i, (label, value, color) in enumerate(card_data):
            card = ctk.CTkFrame(cards_frame, fg_color=("gray90", "gray14"), corner_radius=14,
                                 border_width=1, border_color=("gray83", "gray20"))
            card.grid(row=0, column=i, padx=8, pady=10, sticky="nsew")
            cards_frame.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(
                card, text=value,
                font=ctk.CTkFont(family="微软雅黑", size=32, weight="bold"),
                text_color=color,
            ).pack(pady=(20, 5))

            ctk.CTkLabel(
                card, text=label,
                font=ctk.CTkFont(family="微软雅黑", size=13),
                text_color=("gray50", "gray58"),
            ).pack(pady=(0, 20))

        # 快捷区域
        quick_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=16,
                                   border_width=1, border_color=("gray83", "gray20"))
        quick_frame.pack(fill="both", expand=True, padx=30, pady=(10, 30))

        ctk.CTkLabel(
            quick_frame, text="  应用功能",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=20, pady=(15, 10))

        features = [
            "✅  待办事项管理 — 轻松记录和追踪每日任务",
            "📝  笔记功能 — 随手记录灵感与想法",
            "🚀  快捷启动 — 管理软件、网址和系统功能",
            "🔒  密码保护 — 安全的个人空间，支持修改密码",
            "🎨  主题切换 — 深色/浅色主题自由切换",
            "📦  模块化设计 — 可扩展的架构，方便后续功能升级",
        ]

        for feat in features:
            ctk.CTkLabel(
                quick_frame, text=f"  {feat}",
                font=ctk.CTkFont(family="微软雅黑", size=13),
                text_color=("gray48", "gray58"),
            ).pack(anchor="w", padx=25, pady=4)


# ============================================================
# 番茄钟组件
# ============================================================
class PomodoroTimer:
    """v2.5.0 番茄钟计时器（wall-clock 绝对时间戳，抗锁屏/最小化/切页/加任务延迟）
    不再每秒 decrement，而是记录 _end_at 绝对时间戳，剩余秒数用 now 差值得到，
    即使切页销毁控件、锁屏让 after 延迟，恢复后 remaining 也是真实值。
    提供 snapshot()/restore() 跨 _refresh_list 持久化。"""

    WORK_MINUTES = 25
    BREAK_MINUTES = 5

    def __init__(self, on_tick=None, on_complete=None):
        import time as _t
        self._time = _t.time
        self._stage_total = self.WORK_MINUTES * 60
        self.remaining = self._stage_total
        self.is_break = False
        self.is_running = False
        self.cycles_completed = 0
        self._timer_id = None
        self._end_at = None
        self.auto_continue_next = False
        self._on_tick = on_tick
        self._on_complete = on_complete

    def snapshot(self):
        if self.is_running and self._end_at is not None:
            self.remaining = max(0, int(round(self._end_at - self._time())))
        return {
            "remaining": self.remaining,
            "is_break": self.is_break,
            "is_running": self.is_running,
            "cycles_completed": self.cycles_completed,
            "stage_total": self._stage_total,
            "end_at": self._end_at,
        }

    def restore(self, snap):
        if not snap:
            return
        self.is_break = bool(snap.get("is_break", False))
        self.cycles_completed = int(snap.get("cycles_completed", 0))
        self._stage_total = int(snap.get("stage_total",
                                          self.BREAK_MINUTES * 60 if self.is_break else self.WORK_MINUTES * 60))
        self.remaining = max(0, int(snap.get("remaining", self._stage_total)))
        if bool(snap.get("is_running", False)) and self.remaining > 0:
            end_at = snap.get("end_at")
            if end_at is None:
                end_at = self._time() + self.remaining
            self._end_at = end_at
            self.is_running = True
            self._schedule_tick()
        else:
            self.is_running = False
            self._end_at = None

    def start(self):
        if self.is_running:
            return
        if self.remaining <= 0:
            self.is_break = not self.is_break
            self._stage_total = self.BREAK_MINUTES * 60 if self.is_break else self.WORK_MINUTES * 60
            self.remaining = self._stage_total
        self.is_running = True
        self._end_at = self._time() + self.remaining
        self._schedule_tick()
        if self._on_tick:
            try:
                self._on_tick(self)
            except Exception:
                pass

    def pause(self):
        if self.is_running and self._end_at is not None:
            self.remaining = max(0, int(round(self._end_at - self._time())))
        self.is_running = False
        self._end_at = None
        if self._timer_id is not None:
            try:
                self._after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def reset(self):
        self.pause()
        self.is_break = False
        self.cycles_completed = 0
        self._stage_total = self.WORK_MINUTES * 60
        self.remaining = self.WORK_MINUTES * 60
        if self._on_tick:
            try:
                self._on_tick(self)
            except Exception:
                pass

    def _schedule_tick(self):
        try:
            self._timer_id = self._after(900, self._tick)
        except Exception:
            self._timer_id = None

    def _tick(self):
        self._timer_id = None
        if not self.is_running:
            return
        self.remaining = max(0, int(round(self._end_at - self._time()))) if self._end_at else 0
        if self.remaining <= 0:
            self.is_running = False
            self._end_at = None
            self.cycles_completed += 1
            self.is_break = not self.is_break
            self._stage_total = self.BREAK_MINUTES * 60 if self.is_break else self.WORK_MINUTES * 60
            self.remaining = self._stage_total
            if self._on_complete:
                try:
                    self._on_complete(self)
                except Exception:
                    pass
            if self.auto_continue_next:
                def _cont():
                    if not self.is_running and self.remaining > 0:
                        self.start()
                try:
                    self._after(1000, _cont)
                except Exception:
                    pass
            return
        if self._on_tick:
            try:
                self._on_tick(self)
            except Exception:
                pass
        self._schedule_tick()

    def format_time(self):
        if self.is_running and self._end_at is not None:
            self.remaining = max(0, int(round(self._end_at - self._time())))
        m, s = divmod(max(0, self.remaining), 60)
        return f"{m:02d}:{s:02d}"

    def status_text(self):
        return "休息中" if self.is_break else "工作中"

    def _after(self, ms, callback):
        import tkinter as _tk
        if _tk._default_root is not None:
            return _tk._default_root.after(ms, callback)
        return None

    def _after_cancel(self, tid):
        if tid is None:
            return
        import tkinter as _tk
        try:
            if _tk._default_root is not None:
                _tk._default_root.after_cancel(tid)
        except Exception:
            pass


# ============================================================
# 待办事项视图
# ============================================================
class TodoView(BaseView):
    """待办事项管理（集成番茄钟）"""

    def _build(self):
        # 标题
        ctk.CTkLabel(
            self, text="待办事项",
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(anchor="w", padx=30, pady=(30, 15))

        # 输入区域
        input_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        input_frame.pack(fill="x", padx=30, pady=(0, 15))

        self.todo_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="输入新的待办事项...",
            height=40,
            font=ctk.CTkFont(family="微软雅黑", size=14),
        )
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        self.todo_entry.bind("<Return>", lambda e: self._add_todo())

        ctk.CTkButton(
            input_frame, text="添加", width=80, height=40,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            command=self._add_todo,
        ).pack(side="right", padx=(0, 15), pady=15)

        # 番茄钟说明栏
        pomo_info = ctk.CTkFrame(self, fg_color=("gray89", "gray15"), corner_radius=12,
                               border_width=1, border_color=("gray83", "gray20"))
        pomo_info.pack(fill="x", padx=30, pady=(0, 10))
        ctk.CTkLabel(
            pomo_info,
            text="🍅  番茄钟  ·  专注25分钟 → 休息5分钟  ·  点击待办右侧番茄图标启动  ·  ⏸ 暂停 / ▶ 继续",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color=("gray45", "gray55"),
        ).pack(padx=15, pady=8)

        # 列表区域
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            label_text="",
        )
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._pomodoro_timers = {}  # todo_id -> PomodoroTimer
        self._active_tooltips = []  # 防止 tooltip 残留
        self._refresh_list()
        self.after(100, lambda: apply_card_scrollbar(self.list_frame, "dark"))

    def _bind_tip(self, widget, text):
        """极简 hover 提示（延迟 350ms 显示，移出立即隐藏）"""
        tip_win = {"win": None, "show_job": None}
        show_delay_ms = 350

        def _show(e):
            _cancel_show()
            tip_win["show_job"] = widget.after(show_delay_ms, lambda: _show_now(e))

        def _show_now(e):
            if tip_win["win"]:
                return
            try:
                is_dark = _get_appearance() == "dark"
                bg = "#2b2b2b" if is_dark else "#f0f0f0"
                fg = "#ffffff" if is_dark else "#333333"
                tip_win["win"] = tk.Toplevel(self)
                tip_win["win"].wm_overrideredirect(True)
                tip_win["win"].configure(bg=bg)
                tk.Label(
                    tip_win["win"], text=text, justify="left",
                    bg=bg, fg=fg, relief="flat", bd=0,
                    font=("微软雅黑", 10), padx=8, pady=4,
                ).pack()
                tx = min(e.x_root + 12, self.winfo_screenwidth() - 250)
                ty = min(e.y_root + 12, self.winfo_screenheight() - 40)
                tip_win["win"].wm_geometry(f"+{tx}+{ty}")
                self._active_tooltips.append(tip_win["win"])
            except Exception:
                pass

        def _hide(e=None):
            _cancel_show()
            if tip_win["win"]:
                try:
                    if tip_win["win"] in self._active_tooltips:
                        self._active_tooltips.remove(tip_win["win"])
                except Exception:
                    pass
                try:
                    tip_win["win"].destroy()
                except Exception:
                    pass
                tip_win["win"] = None

        def _cancel_show():
            if tip_win["show_job"]:
                try:
                    widget.after_cancel(tip_win["show_job"])
                except Exception:
                    pass
                tip_win["show_job"] = None

        widget.bind("<Enter>", _show)
        widget.bind("<Leave>", _hide)
        widget.bind("<Button-1>", _hide, add="+")
        widget.bind("<Unmap>", _hide)

    def _add_todo(self):
        content = self.todo_entry.get().strip()
        if not content:
            return
        self.config.add_todo(content)
        self.todo_entry.delete(0, "end")
        self._refresh_list()

    def _refresh_list(self):
        """v2.5.0 支持番茄钟运行状态跨刷新保留（快照 → 销毁 → 还原）"""
        states_snapshot = {}
        for tid, info in list(self._pomodoro_timers.items()):
            snap = {"expanded": bool(info.get("expanded"))}
            t = info.get("timer")
            snap["timer_snap"] = t.snapshot() if t is not None else None
            states_snapshot[tid] = snap

        # 停掉所有 Tk after，防止销毁控件后回调抛错
        for info in self._pomodoro_timers.values():
            t = info.get("timer")
            if t is not None:
                try:
                    if getattr(t, "_timer_id", None) is not None:
                        t._after_cancel(t._timer_id)
                        t._timer_id = None
                except Exception:
                    pass
                t.is_running = False
                t._end_at = None

        for widget in self.list_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        active_ids = set(t["id"] for t in self.config.todos)
        for tid in list(self._pomodoro_timers.keys()):
            if tid not in active_ids:
                self._pomodoro_timers.pop(tid, None)
                states_snapshot.pop(tid, None)

        if not self.config.todos:
            ctk.CTkLabel(
                self.list_frame, text="暂无待办事项，添加一个吧！",
                font=ctk.CTkFont(family="微软雅黑", size=14),
                text_color="gray60",
            ).pack(pady=50)
            for info in self._pomodoro_timers.values():
                info["frame"] = None
                info["time_label"] = None
                info["toggle_btn"] = None
                info["reset_btn"] = None
                info["expanded"] = False
            return

        for todo in reversed(self.config.todos):
            self._build_todo_item(todo)

        for tid, info in self._pomodoro_timers.items():
            snap = states_snapshot.get(tid)
            if not snap:
                continue
            t = info.get("timer")
            if t is not None and snap.get("timer_snap"):
                t.restore(snap["timer_snap"])
            if snap.get("expanded"):
                self._expand_pomodoro_from_snapshot(tid)
            if t is not None and info.get("time_label"):
                try:
                    self._update_pomodoro_display(tid, t)
                except Exception:
                    pass

    def _expand_pomodoro_from_snapshot(self, todo_id):
        """还原展开态：创建新 inner/time_label/ctrl pack 垂直居中 56 高"""
        info = self._pomodoro_timers.get(todo_id)
        if not info or not info.get("frame") or not info["frame"].winfo_exists():
            return
        for ch in info["frame"].winfo_children():
            try: ch.destroy()
            except Exception: pass
        timer = info["timer"]
        inner = ctk.CTkFrame(info["frame"], fg_color="transparent", height=56)
        inner.pack(fill="x", padx=5, pady=(4, 4))
        inner.pack_propagate(False)

        ctrl_frame = ctk.CTkFrame(inner, fg_color="transparent", height=56, width=140)
        ctrl_frame.pack(side="right", fill="y", padx=(0, 8))
        ctrl_frame.pack_propagate(False)
        ctrl_center = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        ctrl_center.pack(expand=True, fill="none")

        toggle_btn = ctk.CTkButton(
            ctrl_center, text="暂停", width=76, height=32, corner_radius=16,
                fg_color=("#e57373", "#b85450"), hover_color=("#ef5350", "#c62828"),
                text_color="white", font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._toggle_pomo_start(todo_id),
        )
        toggle_btn.pack(side="left", padx=(0, 6))
        info["toggle_btn"] = toggle_btn
        # 快照还原后立即同步按钮外观（暂停态显示▶继续，运行态显示⏸暂停）
        self.after(20, lambda: self._update_pomodoro_display(todo_id, timer))
        reset_btn = ctk.CTkButton(
            ctrl_center, text="↺", width=32, height=32, corner_radius=16,
            fg_color=("gray75", "gray26"), hover_color=("gray68", "gray22"),
            text_color=("gray30", "gray85"), font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._reset_pomodoro(todo_id),
        )
        reset_btn.pack(side="left")
        info["reset_btn"] = reset_btn
        left_wrap = ctk.CTkFrame(inner, fg_color="transparent", height=56)
        left_wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        left_wrap.pack_propagate(False)
        time_label = ctk.CTkLabel(
            left_wrap, text=f"  {timer.format_time()}   │   {timer.status_text()}  ",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color=("#b03a2e", "#ff6b6b"), anchor="w", justify="left",
        )
        time_label.pack(side="left", fill="y", anchor="w", padx=(16, 8))
        info["time_label"] = time_label



        info["frame"].pack(fill="x", padx=15, pady=(0, 10), before=None)
        info["expanded"] = True
        if info.get("btn"):
            info["btn"].configure(hover_color=("#f2a4a4", "#a83c3c"),
                                  fg_color=("#f3b5b5", "#c24141"))


    def _build_todo_item(self, todo):
        """构建单条待办项（含番茄钟）"""
        item = ctk.CTkFrame(self.list_frame, fg_color=("gray87", "gray17"), corner_radius=12,
                                border_width=1, border_color=("gray82", "gray22"))
        item.pack(fill="x", padx=5, pady=5)

        # 完成状态复选框
        check_var = ctk.StringVar(value="✓" if todo["done"] else "○")
        check_btn = ctk.CTkButton(
            item, textvariable=check_var,
            width=36, height=36,
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
            font=ctk.CTkFont(size=18),
            text_color=("#2fae73", "#52c49a") if todo["done"] else ("gray48", "gray58"),
            command=lambda tid=todo["id"], v=check_var: self._toggle_todo(tid, v),
        )
        check_btn.pack(side="left", padx=(10, 5), pady=10)

        # 内容（双击可编辑，hover 时轻微变色提示可交互）
        done_flag = todo["done"]
        normal_color = ("gray55", "gray50") if done_flag else ("gray10", "gray90")
        hover_color = ("#2980b9", "#3498db") if not done_flag else normal_color

        content_label = ctk.CTkLabel(
            item, text=todo["content"],
            anchor="w", justify="left",
            font=ctk.CTkFont(
                family="微软雅黑", size=14,
                overstrike=done_flag
            ),
            text_color=normal_color,
        )
        content_label.pack(side="left", fill="x", expand=True, padx=5, pady=12)
        content_label.bind("<Double-Button-1>",
                           lambda e, tid=todo["id"], txt=todo["content"]: self._edit_todo(tid, txt))
        content_label.bind("<Enter>",
                           lambda e, w=content_label, nc=normal_color, hc=hover_color, df=done_flag:
                           w.configure(text_color=hc) if not df else None)
        content_label.bind("<Leave>",
                           lambda e, w=content_label, nc=normal_color:
                           w.configure(text_color=nc))
        content_label.configure(cursor="hand2")
        if not done_flag:
            # 小提示（不打扰完成的待办）
            self._bind_tip(content_label, "双击即可编辑")

        # 日期
        ctk.CTkLabel(
            item, text=todo.get("created", ""),
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color=("gray50", "gray55"),
        ).pack(side="left", padx=10, pady=12)

        # 番茄钟按钮（浅色：深红 tomato 图标，深色：亮红）
        pomo_btn = ctk.CTkButton(
            item, text="🍅", width=30, height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=("#ffeded", "#3a2222"),
            font=ctk.CTkFont(size=14),
            text_color=("#c0392b", "#ff6b6b"),
            command=lambda tid=todo["id"]: self._toggle_pomodoro(tid),
        )
        pomo_btn.pack(side="right", padx=(0, 12), pady=8)
        pomo_btn.configure(cursor="hand2")
        self._bind_tip(pomo_btn, "开启番茄钟 (25/5 循环)")

        # 编辑按钮（胶囊造型，放在删除和番茄钟之间）
        edit_btn = ctk.CTkButton(
            item, text="✒", width=26, height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=("#5a9ee0", "#3a7bb5"),
            text_color=("gray60", "gray55"),
            font=ctk.CTkFont(family="Consolas", size=15),
            command=lambda tid=todo["id"], txt=todo["content"]: self._edit_todo(tid, txt),
        )
        edit_btn.pack(side="right", padx=(0, 2), pady=8)
        edit_btn.configure(cursor="hand2")
        self._bind_tip(edit_btn, "编辑")

        # 删除按钮（胶囊造型，统一风格）
        del_btn = ctk.CTkButton(
            item, text="×", width=26, height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=("#e08080", "#b05555"),
            text_color=("gray60", "gray55"),
            font=ctk.CTkFont(family="Consolas", size=15),
            command=lambda tid=todo["id"]: self._delete_todo(tid),
        )
        del_btn.pack(side="right", padx=(0, 2), pady=8)
        del_btn.configure(cursor="hand2")
        self._bind_tip(del_btn, "删除")

        # 番茄钟显示区域（默认隐藏，启动后展开）
        pomo_frame = ctk.CTkFrame(item, fg_color="transparent")
        # 不 pack，点击番茄按钮时展开

        # 存储引用（v2.5.1：刷新重建时也要更新 frame/btn 为新控件，
        # 否则旧引用失效导致 _expand_pomodoro_from_snapshot 还原失败，番茄钟 UI 中断）
        if todo["id"] not in self._pomodoro_timers:
            self._pomodoro_timers[todo["id"]] = {
                "timer": None,
                "frame": pomo_frame,
                "btn": pomo_btn,
                "expanded": False,
            }
        else:
            info = self._pomodoro_timers[todo["id"]]
            info["frame"] = pomo_frame
            info["btn"] = pomo_btn

    def _toggle_pomodoro(self, todo_id):
        """v2.5.0 切换面板展开（56 高 + pack fill=y 垂直居中，不再 rely=0.45）"""
        info = self._pomodoro_timers.get(todo_id)
        if not info:
            return
        if not info["expanded"]:
            info["expanded"] = True
            frame = info["frame"]
            if info["timer"] is None:
                timer = PomodoroTimer(
                    on_tick=lambda t: self._update_pomodoro_display(todo_id, t),
                    on_complete=lambda t: self._on_pomodoro_complete(todo_id, t),
                )
                timer._after = lambda ms, cb: self.after(ms, cb)
                timer._after_cancel = lambda tid: self.after_cancel(tid)
                info["timer"] = timer
            timer = info["timer"]
            for ch in frame.winfo_children():
                try: ch.destroy()
                except Exception: pass
            inner = ctk.CTkFrame(frame, fg_color="transparent", height=56)
            inner.pack(fill="x", padx=5, pady=(4, 4))
            inner.pack_propagate(False)

            ctrl_frame = ctk.CTkFrame(inner, fg_color="transparent", height=56, width=140)
            ctrl_frame.pack(side="right", fill="y", padx=(0, 8))
            ctrl_frame.pack_propagate(False)
            ctrl_center = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
            ctrl_center.pack(expand=True, fill="none")

            toggle_btn = ctk.CTkButton(
                ctrl_center, text="暂停", width=76, height=32, corner_radius=16,
                fg_color=("#e57373", "#b85450"), hover_color=("#ef5350", "#c62828"),
                text_color="white", font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self._toggle_pomo_start(todo_id),
            )
            toggle_btn.pack(side="left", padx=(0, 6))
            info["toggle_btn"] = toggle_btn
            # 首次展开后立即同步按钮外观（如快照恢复时是暂停态，按钮应为 ▶ 继续）
            self.after(20, lambda: self._update_pomodoro_display(todo_id, timer))
            reset_btn = ctk.CTkButton(
                ctrl_center, text="↺", width=32, height=32, corner_radius=16,
                fg_color=("gray75", "gray26"), hover_color=("gray68", "gray22"),
                text_color=("gray30", "gray85"), font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self._reset_pomodoro(todo_id),
            )
            reset_btn.pack(side="left")
            info["reset_btn"] = reset_btn
            left_wrap = ctk.CTkFrame(inner, fg_color="transparent", height=56)
            left_wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
            left_wrap.pack_propagate(False)
            time_label = ctk.CTkLabel(
            left_wrap, text=f"  {timer.format_time()}   │   {timer.status_text()}  ",
                font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
                text_color=("#b03a2e", "#ff6b6b"), anchor="w", justify="left",
            )
            time_label.pack(side="left", fill="y", anchor="w", padx=(16, 8))
            info["time_label"] = time_label



            frame.pack(fill="x", padx=15, pady=(0, 10), before=None)
            if info.get("btn"):
                info["btn"].configure(hover_color=("#f2a4a4", "#a83c3c"),
                                      fg_color=("#f3b5b5", "#c24141"))
            if (not timer.is_running) and timer.remaining > 0 and not getattr(timer, "_restored", False):
                timer.start()
            try: del timer._restored
            except Exception: pass
        else:
            self._collapse_pomodoro(todo_id)

    def _collapse_pomodoro(self, todo_id):
        info = self._pomodoro_timers.get(todo_id)
        if info and info["timer"]:
            info["timer"].pause()
        if info and info["frame"].winfo_exists():
            info["frame"].pack_forget()
            for child in info["frame"].winfo_children():
                child.destroy()
        if info:
            info["expanded"] = False
            info["timer"] = None

    def _toggle_pomo_start(self, todo_id):
        """开始/暂停 合并切换"""
        info = self._pomodoro_timers.get(todo_id)
        if info and info["timer"]:
            t = info["timer"]
            if t.is_running:
                t.pause()
            else:
                t.start()
            self._update_pomodoro_display(todo_id, t)

    def _reset_pomodoro(self, todo_id):
        info = self._pomodoro_timers.get(todo_id)
        if info and info["timer"]:
            info["timer"].reset()
            self._update_pomodoro_display(todo_id, info["timer"])

    def _update_pomodoro_display(self, todo_id, timer):
        info = self._pomodoro_timers.get(todo_id)
        if not info or not info.get("time_label"):
            return
        if not info["time_label"].winfo_exists():
            return
        icon = "🍅" if not timer.is_break else "☕"
        # v2.3.16 工作态：浅色深酒红 / 深色亮红；休息态：温和绿
        if timer.is_break:
            status_color = ("#1e8449", "#52c49a")
        else:
            status_color = ("#b03a2e", "#ff6b6b")
        info["time_label"].configure(
            text=f"  {timer.format_time()}   │   {timer.status_text()}  ",
            text_color=status_color,
        )
        # 更新切换按钮：暂停时显示▶继续(青绿)，运行中显示⏸暂停(深红)
        toggle_btn = info.get("toggle_btn")
        reset_btn = info.get("reset_btn")
        if toggle_btn and toggle_btn.winfo_exists():
            if timer.is_running:
                # 运行中：深红 + 文字「⏸ 暂停」
                toggle_btn.configure(
                    text="暂停",
                    fg_color=("#e57373", "#b85450"),
                    hover_color=("#ef5350", "#c62828"),
                )
            else:
                # 暂停/未开始：青绿 + 文字「▶ 继续」（用户一眼能看懂）
                toggle_btn.configure(
                    text="继续",
                    fg_color=("#4dab9a", "#2e7d6e"),
                    hover_color=("#26a69a", "#1b6b5d"),
                )
        # 重置按钮根据状态点亮：未开始时半透明，进行中清晰
        if reset_btn and reset_btn.winfo_exists():
            total = timer.BREAK_MINUTES * 60 if timer.is_break else timer.WORK_MINUTES * 60
            if timer.remaining < total:
                reset_btn.configure(
                    text="↺",
                    fg_color=("gray60", "gray30"),
                    hover_color=("#e08080", "#b05555"),
                    text_color=("gray20", "gray85"),
                )
            else:
                reset_btn.configure(
                    text="",
                    fg_color=("gray75", "gray26"),
                    hover_color=("gray68", "gray22"),
                    text_color=("gray30", "gray85"),
                )

    def _on_pomodoro_complete(self, todo_id, timer):
        """v2.5.0 阶段完成：① 声音 2 短 1 长 ② 右下角 toast ③ 托盘气泡 ④ 30s 自动继续"""
        import time as _t
        next_is_break = bool(timer.is_break)
        if next_is_break:
            title, main, sub, icon_txt = "🍅 专注完成", "专注 25 分钟完成", "准备进入 5 分钟休息 ☕", "🍅"
        else:
            title, main, sub, icon_txt = "☕ 休息完成", "休息 5 分钟结束", "准备开始下一个番茄钟 🍅", "☕"

        # ① winsound 叮-叮-咚（不依赖 GUI 可见）
        try:
            import winsound
            for freq, dur in [(880, 120), (880, 120), (660, 420)]:
                try: winsound.Beep(freq, dur)
                except Exception: pass
                _t.sleep(0.04)
        except Exception: pass

        # ② 右下角 toast 浮窗（锁屏 withdraw 也能作为独立 Toplevel 弹出）
        started_next = {"v": False}
        def _start_next_and_close(toast_tl, do_tick=True):
            if started_next["v"]: return
            started_next["v"] = True
            try: toast_tl.destroy()
            except Exception: pass
            try:
                timer._after = lambda ms, cb: self.after(ms, cb)
                timer._after_cancel = lambda tid: self.after_cancel(tid)
                timer.start()
                self._update_pomodoro_display(todo_id, timer)
            except Exception: pass
        try:
            import tkinter as _tk
            try: root = self.winfo_toplevel()
            except Exception: root = None
            tl = _tk.Toplevel(root) if root else _tk.Tk()
            tl.withdraw(); tl.overrideredirect(True); tl.attributes("-topmost", True)
            try: tl.attributes("-alpha", 0.96)
            except Exception: pass
            tl.configure(bg="#1e2a38")
            W, H = 360, 170
            sw = tl.winfo_screenwidth(); sh = tl.winfo_screenheight()
            tl.geometry(f"{W}x{H}+{sw-W-30}+{sh-H-70}")
            card = _tk.Frame(tl, bg=("#ffffff", "#263446"),
                             highlightbackground=("#4a90d9", "#3a7fc6"),
                             highlightthickness=2)
            card.pack(fill="both", expand=True, padx=5, pady=5)
            _tk.Label(card, text=icon_txt, font=("Segoe UI Emoji", 26),
                      bg=("#ffffff", "#263446"), fg="#222").place(x=14, y=18)
            _tk.Label(card, text=title, font=("微软雅黑", 12, "bold"),
                      bg=("#ffffff", "#263446"), fg=("#0b3d91", "#6cb3ff")).place(x=64, y=12)
            _tk.Label(card, text=main, font=("微软雅黑", 11),
                      bg=("#ffffff", "#263446"), fg=("#222", "#ddd")).place(x=64, y=34)
            _tk.Label(card, text=sub, font=("微软雅黑", 10),
                      bg=("#ffffff", "#263446"), fg=("#666", "#aab")).place(x=64, y=56)
            # v2.5.3 三按钮：立即继续 / 跳过此阶段 / 延后 5 分钟
            def _skip_phase():
                if started_next["v"]: return
                started_next["v"] = True
                try: toast_tl.destroy()
                except Exception: pass
                try:
                    timer._after = lambda ms, cb: self.after(ms, cb)
                    timer._after_cancel = lambda tid: self.after_cancel(tid)
                    timer.is_break = not timer.is_break
                    timer._stage_total = timer.BREAK_MINUTES*60 if timer.is_break else timer.WORK_MINUTES*60
                    timer.remaining = timer._stage_total
                    timer.is_running = False
                    timer._end_at = None
                    self._update_pomodoro_display(todo_id, timer)
                except Exception: pass
            def _snooze():
                if started_next["v"]: return
                started_next["v"] = True
                try: toast_tl.destroy()
                except Exception: pass
                try:
                    timer._after = lambda ms, cb: self.after(ms, cb)
                    timer._after_cancel = lambda tid: self.after_cancel(tid)
                    timer.remaining = 5 * 60
                    timer.is_running = False
                    timer._end_at = None
                    self._update_pomodoro_display(todo_id, timer)
                except Exception: pass
            btn_main = _tk.Button(card, text="立即继续", font=("微软雅黑", 9, "bold"),
                             bg=("#4a90d9", "#3a7fc6"), fg="white", bd=0, relief="flat",
                             activebackground=("#5a9ee6", "#4d8ed1"), activeforeground="white",
                             padx=10, pady=4, cursor="hand2",
                             command=lambda: _start_next_and_close(tl))
            btn_main.place(x=64, y=86)
            btn_skip = _tk.Button(card, text="跳过", font=("微软雅黑", 9),
                             bg=("#78909c", "#455a64"), fg="white", bd=0, relief="flat",
                             activebackground=("#90a4ae", "#607d8b"), activeforeground="white",
                             padx=10, pady=4, cursor="hand2", command=_skip_phase)
            btn_skip.place(x=168, y=86)
            btn_snooze = _tk.Button(card, text="延后5分钟", font=("微软雅黑", 9),
                             bg=("#ffb74d", "#e65100"), fg="white", bd=0, relief="flat",
                             activebackground=("#ffcc80", "#ef6c00"), activeforeground="white",
                             padx=10, pady=4, cursor="hand2", command=_snooze)
            btn_snooze.place(x=232, y=86)
            _tk.Label(card, text="30s 后自动继续", font=("微软雅黑", 8),
                      bg=("#ffffff", "#263446"), fg=("#999", "#789")).place(x=64, y=120)
            # 闪烁 3 轮（淡入淡出）
            def _flash(n=0):
                try:
                    if n >= 6 or started_next["v"]: tl.attributes("-alpha", 0.96); return
                    tl.attributes("-alpha", 0.3 + 0.66 * ((n % 2) == 1))
                    tl.after(260, lambda: _flash(n + 1))
                except Exception: pass
            tl.after(50, _flash)
            # 30 秒自动继续
            def _auto_cont():
                if not started_next["v"]:
                    _start_next_and_close(tl, do_tick=True)
            tl.after(30000, _auto_cont)
            tl.deiconify(); tl.lift()
        except Exception as _e:
            # toast 创建失败 fallback messagebox
            try:
                from tkinter import messagebox as _mb
                _mb.showinfo(title, f"{main}\n{sub}")
            except Exception: pass
            _start_next_and_close(None)

        # ③ 托盘冒泡（可选：TrayManager 如果有 notify 方法则使用）
        try:
            tl_app = self.winfo_toplevel()
            tray = getattr(tl_app, "_attached_tray", None)
            if tray and getattr(tray, "notify", None):
                try: tray.notify(title, f"{main} — {sub}")
                except Exception: pass
        except Exception: pass

        self._update_pomodoro_display(todo_id, timer)

    def _edit_todo(self, todo_id, current_text):
        """编辑待办内容"""
        new_text = show_input_dialog(
            self, "编辑待办", "修改待办内容：", initialvalue=current_text
        )
        if new_text and new_text.strip():
            self.config.update_todo(todo_id, new_text.strip())
            self._refresh_list()

    def _toggle_todo(self, todo_id, check_var):
        done = self.config.toggle_todo(todo_id)
        if done is not None:
            self._refresh_list()

    def _delete_todo(self, todo_id):
        # 停止番茄钟
        self._collapse_pomodoro(todo_id)
        self.config.delete_todo(todo_id)
        self._refresh_list()

    def refresh(self):
        self._refresh_list()


# ============================================================
# 笔记视图
# ============================================================
class NotesView(BaseView):
    """笔记管理"""

    def _build(self):
        ctk.CTkLabel(
            self, text="笔记",
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(anchor="w", padx=30, pady=(30, 15))

        # 输入区域
        input_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        input_frame.pack(fill="x", padx=30, pady=(0, 15))

        self.note_title = ctk.CTkEntry(
            input_frame, placeholder_text="笔记标题...",
            height=36, font=ctk.CTkFont(family="微软雅黑", size=14),
        )
        self.note_title.pack(fill="x", padx=15, pady=(15, 5))

        self.note_content = ctk.CTkTextbox(
            input_frame, height=80,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            border_width=1, border_color=("gray70", "gray30"),
        )
        self.note_content.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkButton(
            input_frame, text="保存笔记", height=36, width=100,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            command=self._add_note,
        ).pack(side="right", padx=(0, 15), pady=(0, 15))

        # 输入区可随窗口拉伸：保存按钮单独成行，内容框占满剩余空间
        # （保留上方固定 80px 作为最小高度）
        self._note_input_frame = input_frame

        # 笔记列表
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="")
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._refresh_list()
        self.after(100, lambda: apply_card_scrollbar(self.list_frame, "dark"))

        # 窗口尺寸变化时刷新预览（防抖：避免拖动过程中频繁刷新）
        self._note_resize_timer = None
        def _on_resize(e):
            # 只响应主窗口的尺寸变化
            if e.widget is not self.winfo_toplevel():
                return
            if self._note_resize_timer:
                self.after_cancel(self._note_resize_timer)
            self._note_resize_timer = self.after(200, self._refresh_list)
        self.winfo_toplevel().bind("<Configure>", _on_resize, add="+")

    def _add_note(self):
        title = self.note_title.get().strip()
        content = self.note_content.get("1.0", "end").strip()
        if not title and not content:
            return
        if not title:
            title = "无标题"
        self.config.add_note(title, content)
        self.note_title.delete(0, "end")
        self.note_content.delete("1.0", "end")
        self._refresh_list()

    @staticmethod
    def _truncate_to_lines(text, wrap_width, max_lines, font_size=13, weight="normal"):
        """将文本截断到指定行数（按 wrap_width 估算每行字数）
        中文按 1 字 ≈ font_size px，英文按 0.55*font_size px 估算宽度
        返回截断后的文本（超出部分用 … 代替）"""
        if not text:
            return ""
        # 将换行符统一为空格，避免预览中出现真实换行
        text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        # 估算每行字符容量：中文约 wrap_width/font_size，英文约 wrap_width/(0.55*font_size)
        # 取折中值，并保留余量
        chars_per_line = max(8, int(wrap_width / (font_size * 0.85)))
        max_chars = chars_per_line * max_lines
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 1].rstrip() + "…"

    def _refresh_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        notes = self.config.notes
        if not notes:
            ctk.CTkLabel(
                self.list_frame, text="还没有笔记，写一条吧！",
                font=ctk.CTkFont(family="微软雅黑", size=14),
                text_color="gray60",
            ).pack(pady=50)
            return

        # 计算响应式 wraplength：基于主窗口宽度，预留边距
        try:
            win_w = self.winfo_toplevel().winfo_width()
        except Exception:
            win_w = 1024
        # 列表区 padx=30*2 + 卡片 padx=5*2 + 内容 padx=15*2 ≈ 100
        wrap_w = max(220, win_w - 110)

        for note in reversed(notes):
            item = ctk.CTkFrame(self.list_frame, fg_color=("gray87", "gray17"), corner_radius=12,
                                border_width=1, border_color=("gray82", "gray22"))
            item.pack(fill="x", padx=5, pady=5)

            # 长标题换行 + 最多 2 行
            title_text = self._truncate_to_lines(note["title"], wrap_w, 2,
                                                  font_size=15, weight="bold")
            title_label = ctk.CTkLabel(
                item, text=title_text,
                font=ctk.CTkFont(family="微软雅黑", size=15, weight="bold"),
                wraplength=wrap_w,
                justify="left",
            )
            title_label.pack(anchor="w", padx=15, pady=(12, 2))

            # 内容预览：最多 2 行，响应式宽度
            content_preview = self._truncate_to_lines(
                note["content"], wrap_w, 2, font_size=13
            )
            content_label = ctk.CTkLabel(
                item, text=content_preview,
                font=ctk.CTkFont(family="微软雅黑", size=13),
                text_color=("gray55", "gray60"),
                wraplength=wrap_w,
                justify="left",
            )
            content_label.pack(anchor="w", padx=15, pady=(0, 4))

            bottom_row = ctk.CTkFrame(item, fg_color="transparent")
            bottom_row.pack(fill="x", padx=15, pady=(0, 10))

            ctk.CTkLabel(
                bottom_row, text=note.get("created", ""),
                font=ctk.CTkFont(family="微软雅黑", size=11),
                text_color=("gray50", "gray55"),
            ).pack(side="left")

            ctk.CTkButton(
                bottom_row, text="删除", width=50, height=26,
                fg_color="transparent",
                hover_color=("#e08080", "#b05555"),
                text_color=("gray50", "gray60"),
                font=ctk.CTkFont(family="微软雅黑", size=12),
                command=lambda nid=note["id"]: self._delete_note(nid),
            ).pack(side="right")

            ctk.CTkButton(
                bottom_row, text="编辑", width=50, height=26,
                fg_color="transparent",
                hover_color=("#5a9ee0", "#3a7bb5"),
                text_color=("gray50", "gray60"),
                font=ctk.CTkFont(family="微软雅黑", size=12),
                command=lambda nid=note["id"]: self._show_edit_note_dialog(nid),
            ).pack(side="right", padx=(0, 5))

            # 点击卡片也可以编辑
            nid = note["id"]
            for w in (item, title_label, content_label):
                w.bind("<Button-1>", lambda e, n=nid: self._show_edit_note_dialog(n))
                w.configure(cursor="hand2")

    def _delete_note(self, note_id):
        self.config.delete_note(note_id)
        self._refresh_list()

    def _show_edit_note_dialog(self, note_id):
        """编辑笔记弹窗"""
        note = None
        for n in self.config.notes:
            if n["id"] == note_id:
                note = n
                break
        if not note:
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("编辑笔记")
        dlg.geometry("500x440")
        dlg.resizable(True, True)
        dlg.minsize(400, 360)
        dlg.transient(self)
        dlg.grab_set()

        # 居中显示在父窗口上方
        dlg.update_idletasks()
        parent = self.winfo_toplevel()
        cx = parent.winfo_x() + parent.winfo_width() // 2 - 250
        cy = parent.winfo_y() + parent.winfo_height() // 2 - 220
        cx = max(0, min(cx, dlg.winfo_screenwidth() - 500))
        cy = max(0, min(cy, dlg.winfo_screenheight() - 440))
        dlg.geometry(f"+{cx}+{cy}")

        ctk.CTkLabel(
            dlg, text="编辑笔记",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
        ).pack(anchor="w", padx=25, pady=(20, 10))

        title_entry = ctk.CTkEntry(
            dlg, height=38,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            placeholder_text="笔记标题...",
        )
        title_entry.pack(fill="x", padx=25, pady=(0, 10))
        title_entry.insert(0, note.get("title", ""))

        content_box = ctk.CTkTextbox(
            dlg, height=200,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            border_width=1, border_color=("gray70", "gray30"),
        )
        content_box.pack(fill="both", expand=True, padx=25, pady=(0, 10))
        content_box.insert("1.0", note.get("content", ""))

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(0, 20))

        def save_edit():
            title = title_entry.get().strip()
            content = content_box.get("1.0", "end").strip()
            if not title and not content:
                messagebox.showwarning("提示", "请输入标题或内容", parent=dlg)
                return
            if not title:
                title = "无标题"
            self.config.update_note(note_id, title, content)
            dlg.destroy()
            self._refresh_list()

        ctk.CTkButton(
            btn_frame, text="保存", width=100, height=38,
            font=ctk.CTkFont(family="微软雅黑", size=14, weight="bold"),
            command=save_edit,
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="取消", width=100, height=38,
            fg_color=("gray75", "gray26"),
            font=ctk.CTkFont(family="微软雅黑", size=14),
            command=dlg.destroy,
        ).pack(side="right")

        title_entry.focus_set()

    def refresh(self):
        self._refresh_list()


# ============================================================
# 设置视图
# ============================================================
class SettingsView(BaseView):
    """设置界面"""

    def _build(self):
        ctk.CTkLabel(
            self, text="设置",
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(anchor="w", padx=30, pady=(30, 15))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="")
        scroll.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self._scroll = scroll
        self.after(100, lambda: apply_card_scrollbar(self._scroll, "dark"))

        # === 密码修改区域 ===
        pw_section = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        pw_section.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            pw_section, text="  修改密码",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            pw_section, text="  请输入当前密码和新密码来完成修改",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="gray60",
        ).pack(anchor="w", padx=15, pady=(0, 15))

        self.old_pw = ctk.CTkEntry(pw_section, placeholder_text="当前密码", show="*", height=38,
                                   font=ctk.CTkFont(family="微软雅黑", size=14))
        self.old_pw.pack(fill="x", padx=20, pady=(0, 8))

        self.new_pw = ctk.CTkEntry(pw_section, placeholder_text="新密码（至少6位）", show="*", height=38,
                                   font=ctk.CTkFont(family="微软雅黑", size=14))
        self.new_pw.pack(fill="x", padx=20, pady=(0, 8))

        self.confirm_pw = ctk.CTkEntry(pw_section, placeholder_text="确认新密码", show="*", height=38,
                                       font=ctk.CTkFont(family="微软雅黑", size=14))
        self.confirm_pw.pack(fill="x", padx=20, pady=(0, 12))

        self.pw_msg = ctk.CTkLabel(
            pw_section, text="", font=ctk.CTkFont(family="微软雅黑", size=12))
        self.pw_msg.pack(anchor="w", padx=20, pady=(0, 5))

        ctk.CTkButton(
            pw_section, text="确认修改", height=38, width=120,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            command=self._change_password,
        ).pack(anchor="w", padx=20, pady=(0, 20))

        # === 外观设置 ===
        appearance_section = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        appearance_section.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            appearance_section, text="  外观设置",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            appearance_section, text="  主题模式",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.theme_seg = ctk.CTkSegmentedButton(
            appearance_section,
            values=["深色", "浅色", "跟随系统"],
            command=self._change_theme,
            font=ctk.CTkFont(family="微软雅黑", size=13),
        )
        current_theme = self.config.config.get("theme", "dark")
        theme_map = {"dark": "深色", "light": "浅色", "system": "跟随系统"}
        self.theme_seg.set(theme_map.get(current_theme, "深色"))
        self.theme_seg.pack(anchor="w", padx=20, pady=(0, 18))

        ctk.CTkLabel(
            appearance_section, text="  窗口停靠",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.auto_dock_switch = ctk.CTkSwitch(
            appearance_section,
            text="拖到屏幕边缘自动收纳（类似 QQ）",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._toggle_auto_dock,
        )
        self.auto_dock_switch.pack(anchor="w", padx=20, pady=(0, 20))
        if self.config.get_auto_dock_enabled():
            self.auto_dock_switch.select()

        # === 自动锁屏设置 ===
        lock_section = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        lock_section.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            lock_section, text="  自动锁屏",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            lock_section,
            text="  无操作多少分钟后自动锁定（防止走开被人偷看）。锁屏后主窗口自动收纳至托盘。",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="gray60",
            justify="left",
            wraplength=620,
        ).pack(anchor="w", padx=15, pady=(0, 10))

        row = ctk.CTkFrame(lock_section, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(
            row, text="时间：",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(side="left", padx=(0, 8))

        lock_opts = ["关闭", "1 分钟", "3 分钟", "5 分钟", "10 分钟"]
        lock_valmap = {"关闭": 0, "1 分钟": 1, "3 分钟": 3, "5 分钟": 5, "10 分钟": 10}
        lock_rev = {v: k for k, v in lock_valmap.items()}
        current_lock_min = self.config.get_auto_lock_minutes()
        self._lock_seg = ctk.CTkSegmentedButton(
            row, values=lock_opts, height=32,
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=self._change_auto_lock,
        )
        self._lock_seg.set(lock_rev.get(current_lock_min, "关闭"))
        self._lock_seg.pack(side="left")

        self._lock_hint = ctk.CTkLabel(
            lock_section, text="",
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color=("gray50", "gray58"),
        )
        self._lock_hint.pack(anchor="w", padx=20, pady=(0, 15))
        self.after(50, self._refresh_lock_hint)

        # === 导航设置 ===
        nav_section = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        nav_section.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            nav_section, text="  导航设置",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            nav_section, text="  导航拖拽",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.nav_drag_switch = ctk.CTkSwitch(
            nav_section,
            text="允许非固定项拖拽排序（首页/设置/关于已固定）",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._toggle_nav_drag,
        )
        self.nav_drag_switch.pack(anchor="w", padx=20, pady=(0, 8))
        if self.config.get_nav_drag_enabled():
            self.nav_drag_switch.select()

        # v3.0.1 更名总开关（控制：卡片双击重命名、卡片右键重命名、分类右键重命名/删除、分类管理弹窗、导航项重命名）
        ctk.CTkLabel(
            nav_section, text="  更名设置",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(10, 8))
        self.cat_rename_switch = ctk.CTkSwitch(
            nav_section,
            text="允许重命名操作（关闭后卡片双击/右键、分类、导航项更名均禁用）",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._toggle_cat_rename,
        )
        self.cat_rename_switch.pack(anchor="w", padx=20, pady=(0, 20))
        if self.config.get_category_rename_enabled():
            self.cat_rename_switch.select()

        # === 方法：自动锁屏 ===
    def _change_auto_lock(self, choice):
        """切换自动锁屏时间"""
        lock_valmap = {"关闭": 0, "1 分钟": 1, "3 分钟": 3, "5 分钟": 5, "10 分钟": 10}
        minutes = lock_valmap.get(choice, 0)
        self.config.set_auto_lock_minutes(minutes)
        # 通知主窗口刷新 idle timer
        main = self.winfo_toplevel()
        try:
            if hasattr(main, "_reset_idle_timer"):
                main._reset_idle_timer()
        except Exception:
            pass
        self._refresh_lock_hint()
        from tkinter import messagebox
        # 仅首次开启提示一次
        if minutes > 0 and not getattr(self, "_lock_tip_shown", False):
            self._lock_tip_shown = True

    def _refresh_lock_hint(self):
        try:
            m = self.config.get_auto_lock_minutes()
            if m <= 0:
                self._lock_hint.configure(text="  未启用自动锁屏")
            else:
                self._lock_hint.configure(text=f"  空闲 {m} 分钟后，主窗口将自动收纳至托盘，并需要密码解锁。")
        except Exception:
            pass

        # === 数据管理 ===
        data_section = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=14, border_width=1, border_color=("gray83", "gray20"))
        data_section.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            data_section, text="  数据管理",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
            text_color=("gray18", "gray88"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # 数据存储位置
        ctk.CTkLabel(
            data_section, text="  数据存储位置",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(anchor="w", padx=20, pady=(0, 5))

        data_dir = self.config.get_data_dir()
        self.data_dir_label = ctk.CTkLabel(
            data_section,
            text=f"  {data_dir}",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="gray50",
            wraplength=600,
        )
        self.data_dir_label.pack(anchor="w", padx=20, pady=(0, 8))

        # 更改位置 + 恢复默认 两个按钮并排
        btn_row = ctk.CTkFrame(data_section, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 10))

        self._change_data_btn = ctk.CTkButton(
            btn_row, text="更改位置", height=34, width=110,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._change_data_dir,
        )
        self._change_data_btn.pack(side="left", padx=(0, 10))

        self._reset_data_btn = ctk.CTkButton(
            btn_row, text="恢复默认位置", height=34, width=120,
            fg_color=("gray70", "gray20"),
            border_width=2,
            border_color=("gray50", "gray40"),
            text_color=("gray5", "gray90"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._reset_data_dir,
        )
        self._reset_data_btn.pack(side="left")

        # v3.0.1 便携（绿色）版零留痕设计：数据固定在 EXE 同级 data/，不可更改
        _is_portable = False
        try:
            import sys as _sys, os as _os
            if getattr(_sys, "frozen", False):
                _base = Path(_sys.executable).parent
                _p = _base / "data"
                _test = _p / ".portable_write_test"
                try:
                    _p.mkdir(parents=True, exist_ok=True)
                    _test.write_text("1", encoding="utf-8")
                    _test.unlink(missing_ok=True)
                    _is_portable = True
                except Exception:
                    _is_portable = False
        except Exception:
            _is_portable = False
        if _is_portable:
            from customtkinter import DISABLED as _DSB
            self._change_data_btn.configure(state=_DSB, fg_color=("gray80", "gray28"),
                                            text_color=("gray55", "gray65"), hover=False)
            self._reset_data_btn.configure(state=_DSB, text_color=("gray55", "gray65"), hover=False)
            ctk.CTkLabel(
                data_section,
                text="  * 便携（绿色）版零留痕设计：数据固定在 EXE 同级 data/，不可更改",
                font=ctk.CTkFont(family="微软雅黑", size=11),
                text_color="#d68910",
            ).pack(anchor="w", padx=20, pady=(0, 5))

        # 迁移结果提示
        self.data_dir_msg = ctk.CTkLabel(
            data_section, text="",
            font=ctk.CTkFont(family="微软雅黑", size=12),
        )
        self.data_dir_msg.pack(anchor="w", padx=20, pady=(0, 5))

        # 重置所有数据按钮
        ctk.CTkButton(
            data_section, text="重置所有数据", height=36, width=130,
            fg_color="transparent",
            border_width=1,
            border_color=("#e74c3c", "#c0392b"),
            text_color=("#e74c3c", "#e74c3c"),
            hover_color=("#fadbd8", "#922b21"),
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._reset_data,
        ).pack(anchor="w", padx=20, pady=(5, 20))

    def _change_password(self):
        old = self.old_pw.get().strip()
        new = self.new_pw.get().strip()
        confirm = self.confirm_pw.get().strip()
        ok, msg = self.config.change_password(old, new, confirm)
        color = "#27ae60" if ok else "#e74c3c"
        self.pw_msg.configure(text=msg, text_color=color)
        if ok:
            self.old_pw.delete(0, "end")
            self.new_pw.delete(0, "end")
            self.confirm_pw.delete(0, "end")

    def _change_theme(self, choice):
        theme_map = {"深色": "dark", "浅色": "light", "跟随系统": "system"}
        mode = theme_map.get(choice, "dark")
        self.config.config["theme"] = mode
        self.config.save()
        ctk.set_appearance_mode(mode)

        # 获取主窗口引用
        main_win = self.winfo_toplevel()

        # 延迟刷新：先刷新滚动条，再重建当前视图
        def _do_refresh():
            if hasattr(main_win, 'refresh_current_view'):
                main_win.refresh_current_view()
            else:
                self._refresh_overlay_scrollbars()

        self.after(300, _do_refresh)

    def _toggle_auto_dock(self):
        """切换窗口靠边自动收纳开关（开关变化立即生效，无需重启）"""
        enabled = self.auto_dock_switch.get() == 1
        self.config.set_auto_dock_enabled(enabled)
        main_win = self.winfo_toplevel()
        if enabled:
            # 关→开：若主窗口还没注册则立即注册
            if not getattr(main_win, "_dock_state", None):
                try:
                    from __main__ import install_dock_feature
                    main_win._dock_state = install_dock_feature(main_win,
                        enabled_getter=lambda: self.config.get_auto_dock_enabled())
                except Exception:
                    pass
            else:
                main_win._dock_state["enabled"] = True
                # 从收起状态恢复（防止之前关闭开关时卡在收起态）
                try:
                    ds = main_win._dock_state
                    if ds.get("collapsed") and ds.get("normal_geom"):
                        x, y, w, h = ds["normal_geom"]
                        ds["collapsed"] = False
                        main_win.geometry(f"{w}x{h}+{x}+{y}")
                except Exception:
                    pass
        else:
            # 开→关：恢复正常尺寸位置并关闭轮询
            ds = getattr(main_win, "_dock_state", None)
            if ds:
                ds["enabled"] = False
                try:
                    if ds.get("collapsed") and ds.get("normal_geom"):
                        x, y, w, h = ds["normal_geom"]
                        ds["collapsed"] = False
                        main_win.geometry(f"{w}x{h}+{x}+{y}")
                    ds["docked_side"] = None
                    ds["normal_geom"] = None
                except Exception:
                    pass

    def _toggle_nav_drag(self):
        """切换导航拖拽开关"""
        enabled = self.nav_drag_switch.get() == 1
        self.config.set_nav_drag_enabled(enabled)
        # 重建导航按钮以应用新设置
        main_win = self.winfo_toplevel()
        if hasattr(main_win, "_rebuild_nav_buttons"):
            main_win._rebuild_nav_buttons()

    def _toggle_cat_rename(self):
        """v3.0.1 切换分类重命名/删除总开关"""
        enabled = self.cat_rename_switch.get() == 1
        self.config.set_category_rename_enabled(enabled)

    def _refresh_overlay_scrollbars(self):
        """主题切换后刷新所有 OverlayScrollbar 的颜色和背景"""
        def _find_and_refresh(widget):
            for child in widget.winfo_children():
                if isinstance(child, OverlayScrollbar):
                    child._update_bg()
                    child._redraw()
                _find_and_refresh(child)
        _find_and_refresh(self.winfo_toplevel())

    def _change_data_dir(self):
        """更改数据存储位置"""
        from tkinter import filedialog, messagebox
        new_dir = filedialog.askdirectory(title="选择数据存储文件夹")
        if not new_dir:
            return
        # 确认迁移
        result = messagebox.askyesno(
            "确认迁移",
            f"将把所有数据迁移到：\n{new_dir}\n\n"
            f"迁移后，原位置的数据文件会保留作为备份。\n"
            f"下次启动应用将自动从新位置加载数据。\n\n"
            f"确认迁移吗？",
        )
        if not result:
            return
        ok, msg = self.config.migrate_data_dir(new_dir)
        color = "#27ae60" if ok else "#e74c3c"
        self.data_dir_msg.configure(text=msg, text_color=color)
        if ok:
            # 更新路径显示
            self.data_dir_label.configure(text=f"  {self.config.get_data_dir()}")
            messagebox.showinfo(
                "迁移成功",
                f"数据已迁移到：\n{new_dir}\n\n建议重启应用以确保所有功能正常。",
            )

    def _reset_data_dir(self):
        """恢复默认数据存储位置"""
        from tkinter import messagebox
        if not self.config.is_custom_data_dir():
            self.data_dir_msg.configure(text="当前已是默认位置", text_color="gray60")
            return
        result = messagebox.askyesno(
            "确认恢复",
            "将恢复为默认数据位置。\n\n"
            "当前自定义位置的数据文件不会删除，但应用将不再读取它。\n\n"
            "确认恢复吗？",
        )
        if not result:
            return
        ok, msg = self.config.reset_data_dir()
        color = "#27ae60" if ok else "#e74c3c"
        self.data_dir_msg.configure(text=msg, text_color=color)
        if ok:
            messagebox.showinfo("恢复成功", "已恢复默认数据位置，建议重启应用。")

    def _reset_data(self):
        from tkinter import messagebox
        result = messagebox.askyesno(
            "确认重置",
            "确定要重置所有数据吗？\n这将清空所有待办事项、笔记，并将密码恢复为默认值。\n此操作不可撤销！",
        )
        if result:
            self.config.config = self.config._default_config()
            self.config.todos = []
            self.config.notes = []
            self.config.shortcuts = []
            self.config.save()
            messagebox.showinfo("重置成功", "所有数据已重置，请重新登录。")
            sys.exit(0)


# ============================================================
# 关于视图
# ============================================================
class AboutView(BaseView):
    """关于页面（无滚动条，依赖主窗口有足够的高度）"""

    def _build(self):
        ctk.CTkLabel(
            self, text="关于",
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(anchor="w", padx=30, pady=(25, 10))

        # 应用信息卡片（padding 缩小以更紧凑）
        info_card = ctk.CTkFrame(self, fg_color=("gray88", "gray17"), corner_radius=16)
        info_card.pack(fill="x", padx=30, pady=(0, 10))

        ctk.CTkLabel(
            info_card, text=APP_NAME,
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(pady=(18, 3))

        ctk.CTkLabel(
            info_card, text=APP_SLOGAN,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            info_card, text=f"版本 v{APP_VERSION}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=13, weight="bold"),
            text_color="#3498db",
        ).pack(pady=(0, 3))

        ctk.CTkLabel(
            info_card, text=f"© 2026 {COPYRIGHT_OWNER} · All rights reserved. · {COPYRIGHT_SITE}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=12),
            text_color=("gray58", "gray58"),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            info_card, text=APP_DESC,
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="gray60",
        ).pack(pady=(0, 18))

        # 功能特性（同样更紧凑）
        feat_card = ctk.CTkFrame(self, fg_color=("gray88", "gray17"), corner_radius=16)
        feat_card.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        ctk.CTkLabel(
            feat_card, text="  功能特性",
            font=ctk.CTkFont(family="微软雅黑", size=15, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(12, 6))

        features = [
            ("🔒", "密码登录", "安全的密码保护机制，支持自定义修改密码"),
            ("✅", "待办管理", "高效的任务管理工具，支持完成状态切换"),
            ("📝", "笔记记录", "随手记录灵感和想法，方便随时查阅"),
            ("🚀", "快捷启动", "管理软件、网址和系统功能，一键直达"),
            ("🎨", "主题切换", "深色/浅色主题自由切换，保护视力"),
            ("📦", "模块化架构", "可扩展的视图系统，方便后续功能升级"),
            ("💾", "本地存储", "数据安全保存在本地，隐私无忧"),
        ]

        for icon, name, desc in features:
            row = ctk.CTkFrame(feat_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)

            ctk.CTkLabel(
                row, text=f"  {icon}  {name}",
                font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
            ).pack(side="left", pady=3)

            ctk.CTkLabel(
                row, text=desc,
                font=ctk.CTkFont(family="微软雅黑", size=12),
                text_color="gray60",
            ).pack(side="left", padx=15, pady=3)

        # 更新检查按钮（更紧凑）
        ctk.CTkButton(
            self, text="检查更新", height=38, width=150,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._check_update,
        ).pack(pady=(0, 20))

    def _check_update(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "版本更新",
            f"当前版本：v{APP_VERSION}\n\n"
            f"您的应用已是最新版本。\n\n"
            f"如需升级，请替换新版本的 EXE 文件即可，\n"
            f"您的数据将自动保留并兼容新版本。"
        )


# ============================================================
# 快捷启动 — 图标提取 / 启动器 / 视图
# ============================================================

# --- Windows API 图标提取 ---
import ctypes
import ctypes.wintypes
import subprocess
import webbrowser
from io import BytesIO


class IconExtractor:
    """从 EXE/DLL 提取图标并转为 Base64 PNG"""

    _cache = {}  # 内存缓存：path → base64

    # 已知系统命令 → 真实 EXE / 资源 DLL 的映射（无法通过 where.exe 解析的特殊命令）
    _SYSTEM_CMD_ALIASES = {
        "explorer": r"C:\Windows\explorer.exe",
        "notepad":  r"C:\Windows\System32\notepad.exe",
        "calc":     r"C:\Windows\System32\calc.exe",
        "mspaint":  r"C:\Windows\System32\mspaint.exe",
        "taskmgr":  r"C:\Windows\System32\taskmgr.exe",
        "control":  r"C:\Windows\System32\control.exe",
        "cmd":      r"C:\Windows\System32\cmd.exe",
        "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "pwsh":     r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "regedit":  r"C:\Windows\regedit.exe",
        "msinfo32": r"C:\Windows\System32\msinfo32.exe",
        # .msc / .cpl 文件所在的实际模块
        "devmgmt.msc":   r"C:\Windows\System32\mmc.exe",
        "diskmgmt.msc":  r"C:\Windows\System32\mmc.exe",
        "services.msc":  r"C:\Windows\System32\mmc.exe",
        "eventvwr.msc":  r"C:\Windows\System32\mmc.exe",
        "powercfg.cpl":  r"C:\Windows\System32\powercfg.cpl",
        "ncpa.cpl":      r"C:\Windows\System32\ncpa.cpl",
        "appwiz.cpl":    r"C:\Windows\System32\appwiz.cpl",
        "firewall.cpl":  r"C:\Windows\System32\FirewallControlPanel.dll",
        "main.cpl":      r"C:\Windows\System32\main.cpl",
        "mmsys.cpl":     r"C:\Windows\System32\mmsys.cpl",
        "timedate.cpl":  r"C:\Windows\System32\timedate.cpl",
        # URI 协议 — 用 System32 下的默认图标源
        "ms-settings:":          r"C:\Windows\ImmersiveControlPanel\SettingsUXAsset.png",
        "ms-settings:clipboard": r"C:\Windows\ImmersiveControlPanel\SettingsUXAsset.png",
        "ms-screenclip:":        r"C:\Windows\System32\SnippingTool.exe",
    }

    @classmethod
    def resolve_system_cmd_path(cls, cmd: str) -> str | None:
        """把系统命令解析为真实可执行文件路径，供提取图标使用。返回 None 表示无法解析。"""
        if not cmd:
            return None
        low = cmd.strip().lower().split()[0]

        # 1) 命中别名表
        if low in cls._SYSTEM_CMD_ALIASES:
            p = cls._SYSTEM_CMD_ALIASES[low]
            if os.path.exists(p):
                return p

        # 2) 如果是 .msc / .cpl / .exe 等绝对/相对路径，直接返回存在的项
        if os.path.isabs(low) and os.path.exists(low):
            return low

        # 3) 如果已经带扩展（.exe/.msc/.cpl/.dll/.ocx）在 System32 中
        sys32 = r"C:\Windows\System32"
        if low.endswith((".msc", ".cpl", ".exe", ".dll", ".ocx")):
            p = os.path.join(sys32, os.path.basename(low))
            if os.path.exists(p):
                return p

        # 4) 尝试 where.exe 解析（兼容 cmd / powershell / calc 等）
        try:
            res = subprocess.run(
                ["where.exe", low],
                capture_output=True, text=True, timeout=3,
                creationflags=0x08000000,
            )
            if res.returncode == 0 and res.stdout.strip():
                first = res.stdout.strip().splitlines()[0].strip()
                if os.path.exists(first):
                    return first
        except Exception:
            pass

        # 5) fallback: 尝试在 System32 自动加 .exe
        p = os.path.join(sys32, low + ".exe")
        if os.path.exists(p):
            return p
        return None

    @classmethod
    def extract_from_exe(cls, exe_path: str, size: int = 48) -> str:
        """从 EXE 提取图标，返回 base64 编码的 PNG 字符串"""
        if exe_path in cls._cache:
            return cls._cache[exe_path]

        try:
            import PIL.Image as PILImage
            import tempfile

            icon_b64 = None

            # 使用 PowerShell System.Drawing.Icon 提取（可靠且不依赖 win32api）
            try:
                tmp_ico = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, mode="w+b"
                )
                tmp_path = tmp_ico.name
                tmp_ico.close()

                # 转义路径中的单引号（PowerShell 安全）
                safe_path = exe_path.replace("'", "''")
                safe_tmp = tmp_path.replace("'", "''")

                ps_script = (
                    f'Add-Type -AssemblyName System.Drawing;'
                    f'try {{'
                    f'  $icon = [System.Drawing.Icon]::ExtractAssociatedIcon("{safe_path}");'
                    f'  if ($icon) {{'
                    f'    $bmp = $icon.ToBitmap();'
                    f'    $bmp.Save("{safe_tmp}", [System.Drawing.Imaging.ImageFormat]::Png);'
                    f'    $icon.Dispose(); $bmp.Dispose();'
                    f'  }}'
                    f'}} catch {{ exit 1 }}'
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True, timeout=10,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
                if result.returncode == 0 and os.path.exists(tmp_path):
                    with open(tmp_path, "rb") as f:
                        img_data = f.read()
                    if img_data and len(img_data) > 100:
                        img = PILImage.open(BytesIO(img_data))
                        img = img.convert("RGBA")
                        img = img.resize((size, size), PILImage.LANCZOS)
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        icon_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            except Exception:
                pass

            # 默认占位图标
            if icon_b64 is None:
                icon_b64 = cls._default_icon()

            cls._cache[exe_path] = icon_b64
            return icon_b64

        except Exception:
            return cls._default_icon()

    @classmethod
    def extract_from_url(cls, url: str, size: int = 48) -> str:
        """从网址获取 favicon，返回 base64 PNG"""
        if url in cls._cache:
            return cls._cache[url]

        try:
            import urllib.request
            from urllib.parse import urlparse
            import ssl

            parsed = urlparse(url if "://" in url else f"http://{url}")
            domain = parsed.netloc or parsed.path

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 多个 favicon 服务备选（Google 可能在国内无法访问）
            favicon_urls = [
                f"https://www.google.com/s2/favicons?domain={domain}&sz={size}",
                f"https://favicon.im/{domain}",
                f"https://api.iowen.cn/favicon/{domain}.png",
            ]

            img_data = None
            for favicon_url in favicon_urls:
                try:
                    req = urllib.request.Request(favicon_url, headers={
                        "User-Agent": "Mozilla/5.0"
                    })
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        img_data = resp.read()
                    if img_data and len(img_data) > 100:
                        break
                except Exception:
                    continue

            if img_data and len(img_data) > 100:
                import PIL.Image as PILImage
                img = PILImage.open(BytesIO(img_data))
                img = img.convert("RGBA")
                img = img.resize((size, size), PILImage.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="PNG")
                icon_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                cls._cache[url] = icon_b64
                return icon_b64
        except Exception:
            pass

        return cls._default_icon()

    @staticmethod
    def _default_icon() -> str:
        """默认占位图标（蓝色圆角方块 + 白色 Z 字母）"""
        try:
            import PIL.Image as PILImage
            import PIL.ImageDraw as ImageDraw
            import PIL.ImageFont as ImageFont

            img = PILImage.new("RGBA", (48, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # 蓝色圆角背景
            draw.rounded_rectangle([2, 2, 46, 46], radius=10,
                                   fill=(59, 142, 224, 255))
            # 白色 Z 字母
            try:
                font = ImageFont.truetype("arial.ttf", 28)
            except Exception:
                font = None
            bbox = draw.textbbox((0, 0), "Z", font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((48 - tw) / 2 - bbox[0], (48 - th) / 2 - bbox[1]),
                "Z", fill="white", font=font,
            )
            buf = BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            # 最终后备：1x1 透明像素
            return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    @staticmethod
    def _preset_icon(name: str, theme: str = "dark") -> str:
        """v2.3.15 预设图标：透明背景 + 主题自适应颜色
        theme: 'dark' 返回浅色图标(用于深色卡片), 'light' 返回深色图标(用于浅色卡片)
        """
        try:
            import PIL.Image as PILImage
            import PIL.ImageDraw as ImageDraw
            import PIL.ImageFont as ImageFont

            img = PILImage.new("RGBA", (48, 48), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # v2.3.15: 透明背景，无蓝色圆角圈
            if theme == "dark":
                fg = (255, 255, 255, 255)       # 深色卡片上用白色
                fg_secondary = (200, 200, 200, 255)
            else:
                fg = (50, 50, 50, 255)          # 浅色卡片上用深灰
                fg_secondary = (100, 100, 100, 255)
            white = fg
            blue = (59, 142, 224, 255)  # 品牌蓝：在深浅背景上都好看
            dark_white = fg_secondary

            # 字体
            try:
                font_small = ImageFont.truetype("arial.ttf", 12)
                font_med = ImageFont.truetype("arial.ttf", 16)
                font_large = ImageFont.truetype("arial.ttf", 24)
            except Exception:
                font_small = font_med = font_large = None

            if not name:
                name = ""

            # --- 系统信息（必须在通用系统之前匹配）---
            if "系统信息" in name:
                draw.ellipse([10, 10, 38, 38], outline=white, width=3)
                if font_large:
                    bbox = draw.textbbox((0, 0), "i", font=font_large)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.text(((48 - tw) / 2 - bbox[0], (48 - th) / 2 - bbox[1]),
                              "i", fill=white, font=font_large)
                else:
                    draw.text((22, 14), "i", fill=white)

            elif "计算" in name:
                # 计算器
                draw.rounded_rectangle([14, 8, 34, 40], radius=3, outline=white, width=2)
                draw.rectangle([16, 12, 32, 18], fill=white)
                for r in range(3):
                    for c in range(3):
                        cx = 18 + c * 5
                        cy = 22 + r * 5
                        draw.rectangle([cx, cy, cx + 3, cy + 3], fill=white)

            elif "记事" in name or "文本" in name:
                # 记事本/文档
                draw.polygon([(14, 8), (30, 8), (34, 12), (34, 40), (14, 40)], fill=white)
                draw.polygon([(30, 8), (30, 12), (34, 12)], fill=dark_white)
                for i in range(4):
                    y = 18 + i * 5
                    draw.line([(18, y), (30, y)], fill=blue, width=1)

            elif "画" in name:
                # 画图：画笔
                draw.line([(14, 36), (30, 20)], fill=white, width=3)
                draw.ellipse([28, 16, 36, 24], fill=white)
                draw.polygon([(12, 38), (16, 34), (18, 36), (14, 40)], fill=white)

            elif "命令" in name or "cmd" in name.lower():
                # 命令提示符
                if font_med:
                    draw.text((12, 14), ">_", fill=white, font=font_med)
                else:
                    draw.text((12, 14), ">_", fill=white)

            elif "资源" in name or "文件" in name:
                # 文件夹
                draw.polygon([(10, 14), (20, 14), (23, 10), (34, 10), (34, 38), (10, 38)], fill=white)
                draw.rectangle([10, 16, 34, 18], fill=blue)

            elif "设备" in name:
                # 设备管理器：显示器
                draw.rounded_rectangle([10, 10, 38, 32], radius=2, outline=white, width=2)
                draw.rectangle([20, 34, 28, 38], fill=white)
                draw.line([(14, 40), (34, 40)], fill=white, width=2)

            elif "磁盘" in name:
                # 磁盘管理
                draw.ellipse([12, 12, 36, 36], outline=white, width=2)
                draw.ellipse([20, 20, 28, 28], fill=white)

            elif "服务" in name:
                # 服务：齿轮
                cx, cy = 24, 24
                draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=white, width=3)
                draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=blue, outline=white, width=2)
                for angle in range(0, 360, 45):
                    rad = math.radians(angle)
                    x1 = cx + int(10 * math.cos(rad))
                    y1 = cy + int(10 * math.sin(rad))
                    x2 = cx + int(14 * math.cos(rad))
                    y2 = cy + int(14 * math.sin(rad))
                    draw.line([(x1, y1), (x2, y2)], fill=white, width=3)

            elif "事件" in name:
                # 事件查看器：日志
                draw.rounded_rectangle([12, 8, 36, 40], radius=2, outline=white, width=2)
                for i in range(4):
                    y = 14 + i * 6
                    draw.line([(16, y), (32, y)], fill=white, width=1)

            elif "电源" in name:
                # 电源
                draw.arc([10, 10, 38, 38], start=30, end=330, fill=white, width=3)
                draw.line([(24, 10), (24, 22)], fill=white, width=3)

            elif "网络" in name:
                # 网络
                draw.ellipse([18, 8, 30, 20], outline=white, width=2)
                draw.ellipse([8, 28, 20, 40], outline=white, width=2)
                draw.ellipse([28, 28, 40, 40], outline=white, width=2)
                draw.line([(24, 20), (14, 28)], fill=white, width=2)
                draw.line([(24, 20), (34, 28)], fill=white, width=2)

            elif "程序" in name:
                # 程序列表
                for i in range(4):
                    y = 12 + i * 8
                    draw.ellipse([12, y, 16, y + 4], fill=white)
                    draw.line([(20, y + 2), (36, y + 2)], fill=white, width=2)

            elif "防火墙" in name:
                # 盾牌
                draw.polygon([(24, 6), (38, 12), (38, 24), (24, 42), (10, 24), (10, 12)], fill=white)
                draw.line([(18, 24), (22, 28), (30, 18)], fill=blue, width=3)

            elif "剪贴" in name:
                # 剪贴板
                draw.rounded_rectangle([12, 12, 36, 42], radius=2, outline=white, width=2)
                draw.rectangle([18, 8, 30, 14], fill=white)
                for i in range(3):
                    y = 20 + i * 6
                    draw.line([(16, y), (32, y)], fill=white, width=1)

            elif "截图" in name:
                # 截图：相机
                draw.rounded_rectangle([10, 16, 38, 36], radius=3, outline=white, width=2)
                draw.ellipse([16, 20, 32, 34], outline=white, width=2)
                draw.rectangle([22, 12, 26, 16], fill=white)

            elif "面板" in name or "控制" in name:
                # 控制面板：滑块
                draw.rounded_rectangle([10, 10, 38, 38], radius=3, outline=white, width=2)
                draw.line([(14, 18), (34, 18)], fill=white, width=2)
                draw.ellipse([20, 15, 26, 21], fill=blue, outline=white, width=2)
                draw.line([(14, 28), (34, 28)], fill=white, width=2)
                draw.ellipse([28, 25, 34, 31], fill=blue, outline=white, width=2)

            elif "任务" in name:
                # 任务管理器：柱状图
                for i, h in enumerate([10, 18, 14, 22]):
                    x = 12 + i * 8
                    draw.rectangle([x, 40 - h, x + 5, 38], fill=white)

            elif "注册" in name:
                # 注册表：树形
                draw.ellipse([10, 10, 18, 18], outline=white, width=2)
                draw.ellipse([10, 22, 18, 30], outline=white, width=2)
                draw.ellipse([10, 34, 18, 42], outline=white, width=2)
                draw.line([(18, 14), (30, 14)], fill=white, width=2)
                draw.line([(18, 26), (30, 26)], fill=white, width=2)
                draw.line([(18, 38), (30, 38)], fill=white, width=2)

            elif "设置" in name:
                # 设置：齿轮
                cx, cy = 24, 24
                draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=white, width=3)
                draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=blue, outline=white, width=2)
                for angle in range(0, 360, 45):
                    rad = math.radians(angle)
                    x1 = cx + int(10 * math.cos(rad))
                    y1 = cy + int(10 * math.sin(rad))
                    x2 = cx + int(14 * math.cos(rad))
                    y2 = cy + int(14 * math.sin(rad))
                    draw.line([(x1, y1), (x2, y2)], fill=white, width=3)

            else:
                # 默认：Z 字母
                if font_large:
                    bbox = draw.textbbox((0, 0), "Z", font=font_large)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.text(((48 - tw) / 2 - bbox[0], (48 - th) / 2 - bbox[1]),
                              "Z", fill=white, font=font_large)
                else:
                    draw.text((16, 12), "Z", fill=white)

            buf = BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            return IconExtractor._default_icon()

    @staticmethod
    def _crop_transparent_border(img, pad=2):
        """v2.3.19 去白底/浅灰背景板：flood-fill 但防误伤（大面积被删则跳过透明化）
        策略：
        1) 提高"背景色"判定亮度阈值（>=235 纯白才无条件；215~235 必须同时低饱和）
        2) 种子 flood-fill 后若被移除像素占比 > 55% → 说明图本身是浅色内容，跳过透明化
        3) 边缘脱色只针对"与种子连通域直接相邻"的真边界像素
        """
        try:
            w, h = img.size
            if w <= 4 or h <= 4:
                return img
            px = img.load()

            # ---- 更保守的背景判定：避免误伤浅色图标内容 ----
            def is_bg(r, g, b, a):
                if a == 0:
                    return True
                brightness = (r + g + b) / 3.0
                sat = max(r, g, b) - min(r, g, b)
                # A) 几乎纯白（>=235）→ 无条件视为背景
                if brightness >= 235 and sat <= 25:
                    return True
                # B) 很亮 + 低饱和（典型浅灰背景板）
                if brightness >= 220 and sat <= 18:
                    return True
                # C) 中等亮 + 极低饱和（中性浅灰）
                if brightness >= 205 and sat <= 8:
                    return True
                return False

            # ---- STEP 1: 种子 flood-fill 找外围背景连通域 ----
            visited = [[False] * h for _ in range(w)]
            bg_set = set()
            queue = []
            seeds = [
                (0, 0), (w-1, 0), (0, h-1), (w-1, h-1),
                (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2),
            ]
            for sx, sy in seeds:
                if 0 <= sx < w and 0 <= sy < h and not visited[sx][sy]:
                    r, g, b, a = px[sx, sy]
                    if is_bg(r, g, b, a):
                        queue.append((sx, sy))
                        visited[sx][sy] = True

            while queue:
                x, y = queue.pop(0)
                r, g, b, a = px[x, y]
                if is_bg(r, g, b, a):
                    bg_set.add((x, y))
                    for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                        if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                            visited[nx][ny] = True
                            nr, ng, nb, na = px[nx, ny]
                            if is_bg(nr, ng, nb, na):
                                queue.append((nx, ny))

            total = w * h
            ratio = len(bg_set) / total if total else 0

            # ---- 关键：如果被判定为背景的像素超过 55%，
            #      说明这张图本身就是浅色为主（如白字图标、浅色插画）
            #      此时跳过透明化，只按原始 alpha bbox 裁剪 ----
            if ratio <= 0.55 and len(bg_set) > 0:
                # STEP 2: 把识别出的背景设为完全透明
                for (x, y) in bg_set:
                    r, g, b, a = px[x, y]
                    px[x, y] = (r, g, b, 0)

                # STEP 3: 边缘脱色 — 仅处理紧邻 bg_set 的真正边界像素，防抗锯齿雾边
                # 先构建 bg_set 快速查询集合
                bg_or_trans = set(bg_set)
                # 把原本就是透明的也加进来
                for yy in range(h):
                    for xx in range(w):
                        if px[xx, yy][3] == 0:
                            bg_or_trans.add((xx, yy))
                edge_pixels = []
                for yy in range(h):
                    for xx in range(w):
                        if (xx, yy) in bg_or_trans:
                            continue
                        # 8 邻域内至少有 1 个属于背景/透明
                        near_bg = False
                        for nx in range(max(0,xx-1), min(w,xx+2)):
                            for ny in range(max(0,yy-1), min(h,yy+2)):
                                if (nx, ny) in bg_or_trans:
                                    near_bg = True
                                    break
                            if near_bg:
                                break
                        if near_bg:
                            rr, gg, bb, aa = px[xx, yy]
                            if (rr + gg + bb) / 3.0 >= 190:
                                edge_pixels.append((xx, yy, rr, gg, bb, aa))
                for (xx, yy, rr, gg, bb, aa) in edge_pixels:
                    # 脱色：RGB 降 35%，alpha 降约 25，保留渐变关系
                    factor = 0.55
                    new_a = max(0, aa - 28)
                    px[xx, yy] = (int(rr * factor), int(gg * factor), int(bb * factor), new_a)

            # STEP 4: 按 alpha 裁剪（无论是否做了透明化都做）
            # v2.5.7：先对 alpha 阈值化（alpha >= 2 视为内容）——把抗锯齿边缘
            # 的半透明像素全部纳入 bbox，避免它们被排除后导致最终内容被切边
            alpha = img.split()[-1]
            try:
                import PIL.Image as PILImage
                import PIL.ImageChops as ImageChops
                # threshold: alpha >= 2 -> 255; else 0
                th_alpha = alpha.point(lambda a: 255 if a >= 2 else 0, mode="L")
                bbox = th_alpha.getbbox()
            except Exception:
                bbox = alpha.getbbox()
            if not bbox:
                bbox = alpha.getbbox()
            if not bbox:
                return img
            x0, y0, x1, y1 = bbox
            x0 = max(0, x0 - pad)
            y0 = max(0, y0 - pad)
            x1 = min(w, x1 + pad)
            y1 = min(h, y1 + pad)
            return img.crop((x0, y0, x1, y1))
        except Exception:
            pass
        return img

    @staticmethod
    def base64_to_ctkimage(b64: str, size: int = 48, dark_b64: str = None):
        """v2.3.15 将 base64 PNG 转为 CTkImage，支持 light/dark 双版本
        dark_b64: 深色模式专用图标(可选)，不传则复用 b64
        """
        def _decode(b64_str):
            if not b64_str:
                b64_str = IconExtractor._default_icon()
            for attempt in range(2):
                try:
                    import PIL.Image as PILImage
                    img_data = base64.b64decode(b64_str)
                    img = PILImage.open(BytesIO(img_data))
                    img = img.convert("RGBA")
                    # v2.5.7 pad 1 -> 4：避免抗锯齿边缘像素被误裁，导致卡片圆角再裁切
                    # 时内容被切掉一块（如 Edge "e" 字的左边缘被切）
                    img = IconExtractor._crop_transparent_border(img, pad=4)
                    img = img.resize((size, size), PILImage.LANCZOS)
                    # v2.5.7 外包一层 size x size 透明画布并居中粘贴：
                    #   —— 防止裁剪框小于原始画布时 CTk/resize 再次重采样落边
                    if img.size != (size, size):
                        canvas = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
                        ox = max(0, (size - img.width) // 2)
                        oy = max(0, (size - img.height) // 2)
                        canvas.paste(img, (ox, oy), img)
                        img = canvas
                    return img
                except Exception:
                    b64_str = IconExtractor._default_icon()
            try:
                import PIL.Image as PILImage
                return PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
            except Exception:
                return None

        light_img = _decode(b64)
        dark_img = _decode(dark_b64) if dark_b64 else light_img

        if light_img and dark_img:
            return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))
        elif light_img:
            return ctk.CTkImage(light_image=light_img, dark_image=light_img, size=(size, size))
        else:
            return None

    @classmethod
    def extract_async(cls, stype: str, path: str, callback):
        """异步提取图标，完成后在主线程调用 callback(base64_str)"""
        import threading

        def worker():
            if stype == "app":
                result = cls.extract_from_exe(path)
            elif stype == "url":
                result = cls.extract_from_url(path)
            else:
                result = cls._default_icon()
            # 在主线程调用回调，检查 root 是否仍然存在
            try:
                import tkinter as _tk
                root = _tk._default_root
                if root is not None and root.winfo_exists():
                    root.after_idle(lambda: callback(result))
            except Exception:
                pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# --- 系统功能预设 ---
SYSTEM_PRESETS = [
    {"name": "任务管理器", "path": "taskmgr", "type": "system", "category": "系统工具"},
    {"name": "控制面板", "path": "control", "type": "system", "category": "系统工具"},
    {"name": "计算器", "path": "calc", "type": "system", "category": "系统工具"},
    {"name": "记事本", "path": "notepad", "type": "system", "category": "系统工具"},
    {"name": "画图", "path": "mspaint", "type": "system", "category": "系统工具"},
    {"name": "截图工具", "path": "ms-screenclip:", "type": "system", "category": "系统工具"},
    {"name": "命令提示符", "path": "cmd", "type": "system", "category": "系统工具"},
    {"name": "PowerShell", "path": "powershell", "type": "system", "category": "系统工具"},
    {"name": "注册表编辑器", "path": "regedit", "type": "system", "category": "系统工具"},
    {"name": "资源管理器", "path": "explorer", "type": "system", "category": "系统工具"},
    {"name": "Windows 设置", "path": "ms-settings:", "type": "system", "category": "系统工具"},
    {"name": "剪贴板历史", "path": "ms-settings:clipboard", "type": "system", "category": "系统工具"},
    {"name": "设备管理器", "path": "devmgmt.msc", "type": "system", "category": "管理工具"},
    {"name": "磁盘管理", "path": "diskmgmt.msc", "type": "system", "category": "管理工具"},
    {"name": "服务", "path": "services.msc", "type": "system", "category": "管理工具"},
    {"name": "事件查看器", "path": "eventvwr.msc", "type": "system", "category": "管理工具"},
    {"name": "系统信息", "path": "msinfo32", "type": "system", "category": "管理工具"},
    {"name": "电源选项", "path": "powercfg.cpl", "type": "system", "category": "管理工具"},
    {"name": "网络连接", "path": "ncpa.cpl", "type": "system", "category": "管理工具"},
    {"name": "程序和功能", "path": "appwiz.cpl", "type": "system", "category": "管理工具"},
    {"name": "防火墙", "path": "firewall.cpl", "type": "system", "category": "系统工具"},
    {"name": "鼠标属性", "path": "main.cpl", "type": "system", "category": "管理工具"},
    {"name": "声音", "path": "mmsys.cpl", "type": "system", "category": "管理工具"},
    {"name": "日期和时间", "path": "timedate.cpl", "type": "system", "category": "管理工具"},
]


class Launcher:
    """统一启动器：处理 app / url / system 三种类型"""

    # 需要控制台窗口的系统命令
    _CONSOLE_COMMANDS = {"cmd", "cmd.exe", "powershell", "powershell.exe",
                         "pwsh", "pwsh.exe", "ipconfig", "netstat", "ping",
                         "systeminfo", "tracert", "netsh", "diskpart"}

    @staticmethod
    def launch(shortcut: dict):
        """启动一个快捷方式"""
        stype = shortcut.get("type", "app")
        path = shortcut.get("path", "")
        name = shortcut.get("name", "")

        if not path:
            return False, "路径为空"

        try:
            if stype == "app":
                if not os.path.exists(path):
                    return False, f"文件不存在：\n{path}"
                os.startfile(path)
                return True, f"已启动 {name}"

            elif stype == "url":
                url = path if "://" in path else f"https://{path}"
                webbrowser.open(url)
                return True, f"已打开 {name}"

            elif stype == "system":
                # Win10/Win11 兼容启动策略
                cmd_base = os.path.splitext(path.lower().strip().split()[0])[0]

                if cmd_base in Launcher._CONSOLE_COMMANDS:
                    # 需要控制台窗口的命令（cmd、powershell 等）
                    # 在窗口化（console=False）PyInstaller 打包中，
                    # subprocess + CREATE_NEW_CONSOLE 可能静默失败，
                    # 改用 ShellExecuteW 确保控制台窗口正常弹出
                    import ctypes
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None, "open", path, None, None, 1  # SW_SHOWNORMAL
                    )
                    if result <= 32:
                        return False, f"启动失败: ShellExecute 返回码 {result}"
                else:
                    # GUI 程序和 .msc / .cpl / URI 命令
                    # 优先用 os.startfile（最兼容 Win10/Win11）
                    try:
                        os.startfile(path)
                    except Exception:
                        # 回退到 subprocess（不抑制窗口）
                        subprocess.Popen(path, shell=True)
                return True, f"已执行 {name}"

            else:
                return False, f"未知类型: {stype}"
        except Exception as e:
            return False, f"启动失败: {e}"


class QuickLaunchView(BaseView):
    """快捷启动视图 — 图标网格 + 分类标签 + 添加/编辑"""

    SIZE_PRESETS = {
        "small":  {"icon": 32, "card": 70,  "cols": 9, "font": 10},
        "medium": {"icon": 48, "card": 90,  "cols": 7, "font": 11},
        "large":  {"icon": 64, "card": 110, "cols": 5, "font": 12},
    }

    def _build(self):
        # v3.0.1 记住上次视图大小
        try:
            _saved_size = self.config._read_settings().get("last_view_size", "medium")
        except Exception:
            _saved_size = "medium"
        self._view_size = _saved_size if _saved_size in ("small", "medium", "large") else "medium"

        # 顶部标题栏
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=30, pady=(25, 10))

        ctk.CTkLabel(
            top, text="快捷启动",
            font=ctk.CTkFont(family="微软雅黑", size=24, weight="bold"),
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            top, text=f"  ({len(self.config.shortcuts)} 个项目)",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        )
        self.count_label.pack(side="left", pady=(6, 0))

        # 右侧按钮区
        right_btns = ctk.CTkFrame(top, fg_color="transparent")
        right_btns.pack(side="right")

        # 视图大小切换
        size_frame = ctk.CTkFrame(right_btns, fg_color="transparent")
        size_frame.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            size_frame, text="视图",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="gray60",
        ).pack(side="left", padx=(0, 6))

        self.size_seg = ctk.CTkSegmentedButton(
            size_frame, values=["小", "中", "大"],
            width=110, height=30,
            font=ctk.CTkFont(family="微软雅黑", size=11),
            command=self._toggle_view_size,
        )
        # v3.0.1 恢复上次视图大小选择
        _size_label_map = {"small": "小", "medium": "中", "large": "大"}
        self.size_seg.set(_size_label_map.get(self._view_size, "中"))
        self.size_seg.pack(side="left")

        # 排序按钮（弹出排序菜单）
        ctk.CTkButton(
            right_btns, text="↕ 排序", width=90, height=34,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._show_sort_menu,
        ).pack(side="left", padx=(0, 12))

        # 系统预设按钮
        ctk.CTkButton(
            right_btns, text="系统预设", width=100, height=34,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._show_presets,
        ).pack(side="left", padx=(0, 12))

        # 添加按钮
        ctk.CTkButton(
            right_btns, text="+ 新增项目", width=110, height=34,
            fg_color=("#3b8ee0", "#1f6aa5"),
            hover_color=("#2d7bc7", "#1a5a8a"),
            text_color="white",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=self._show_add_dialog,
        ).pack(side="left")

        # 分类标签栏（含管理按钮）
        cat_bar = ctk.CTkFrame(self, fg_color="transparent")
        cat_bar.pack(fill="x", padx=30, pady=(5, 10))

        self.cat_frame = ctk.CTkFrame(cat_bar, fg_color="transparent")
        self.cat_frame.pack(side="left", fill="x", expand=True)
        self.cat_frame.bind("<Configure>", self._on_cat_frame_resize)
        self._cat_layout_job = None

        # 管理分类按钮
        ctk.CTkButton(
            cat_bar, text="⚙", width=34, height=30,
            fg_color=("gray80", "gray22"),
            hover_color=("gray70", "gray30"),
            text_color=("gray15", "gray85"),
            corner_radius=15,
            font=ctk.CTkFont(size=16),
            command=self._show_category_manager,
        ).pack(side="right")

        self.cat_buttons = {}
        # v3.0.1 跨会话恢复上次选中的分类（不在分类列表则兜底为「全部」）
        persisted = None
        try:
            persisted = self.config.get_last_view_category()
        except Exception:
            persisted = None
        all_cats_here = ["全部"] + self.config.get_shortcut_categories()
        self._current_cat = persisted if (persisted and persisted in all_cats_here) else "全部"
        # v3.0.1 分类拖拽排序：临时状态
        self._cat_drag_active_cat = None  # 拖拽中的分类名（非「全部」）
        self._cat_drag_timer = None

        self._rebuild_cat_buttons()

        # 滚动内容区
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self.scroll.pack(fill="both", expand=True, padx=30, pady=(0, 25))

        # 应用 Overlay 滚动条
        self.after(100, lambda: apply_card_scrollbar(self.scroll))

        # v2.5.5 分类名迁移（数据层旧分类统一为新命名）
        self._migrate_category_names()

        # 拖拽状态
        self._drag_data = None

        self._grid_frame = None
        self._build_grid()

    def _cleanup_tooltips(self):
        """销毁所有残留的 tooltip 窗口"""
        for child in self.winfo_children():
            try:
                if isinstance(child, tk.Toplevel) and child.wm_overrideredirect():
                    child.destroy()
            except Exception:
                pass

    def _calc_cols(self):
        """v2.3.14 响应式列数：根据窗口宽度 + 卡片宽度计算"""
        preset = self.SIZE_PRESETS[self._view_size]
        card_w = preset["card"]
        gap = 12
        try:
            container_w = self._grid_frame.winfo_width()
        except Exception:
            container_w = 0
        if container_w < 50:
            try:
                container_w = self.scroll.winfo_width() - 20
            except Exception:
                container_w = 0
        if container_w < 50:
            return preset["cols"]
        cols = max(1, (container_w + gap) // (card_w + gap))
        cols = min(cols, preset["cols"])
        cols = max(cols, 1)
        return cols

    def _build_grid(self, force=False):
        """v2.3.17 构建图标网格：列数变化或 force=True 才重建，否则重排，避免整帧 destroy 闪屏"""
        preset = self.SIZE_PRESETS[self._view_size]
        cols = self._calc_cols()

        # 筛选
        all_items = self.config.get_ordered_shortcuts()
        if self._current_cat == "全部":
            items = all_items
        else:
            items = [s for s in all_items
                     if s.get("category", "默认") == self._current_cat]

        # 决策：是否需要完整重建
        need_rebuild = force
        if not self._grid_frame or not self._grid_frame.winfo_exists():
            need_rebuild = True
        if getattr(self, '_last_grid_cols', -1) != cols:
            need_rebuild = True
        if hasattr(self, '_last_grid_items_key'):
            key = (self._current_cat, len(items), self._view_size)
            if getattr(self, '_last_grid_items_key', None) != key:
                need_rebuild = True
        else:
            need_rebuild = True

        if need_rebuild:
            # 清理 tooltip
            self._cleanup_tooltips()
            if self._grid_frame:
                try: self._grid_frame.destroy()
                except Exception: pass
            self._grid_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
            self._grid_frame.pack(fill="both", expand=True)
            for c in range(cols):
                self._grid_frame.grid_columnconfigure(c, weight=1)

            if not items:
                ctk.CTkLabel(
                    self._grid_frame,
                    text="暂无项目，点击右上角「+ 新增项目」创建",
                    font=ctk.CTkFont(family="微软雅黑", size=14),
                    text_color="gray50",
                ).pack(expand=True, pady=60)
                self._last_grid_cols = cols
                self._last_grid_items_key = (self._current_cat, 0, self._view_size)
                return

            self._grid_cards = []
            for i, sc in enumerate(items):
                row = i // cols
                col = i % cols
                card = self._make_card(sc, i)
                card.grid(row=row, column=col, padx=4, pady=4, sticky='n')
                self._grid_cards.append(card)
            self._last_grid_cols = cols
            self._last_grid_items_key = (self._current_cat, len(items), self._view_size)
        else:
            # 不需要重建，只更新列权重（列数没变，但布局可能需要刷新）
            pass

    def _make_card(self, sc: dict, index: int = 0) -> ctk.CTkFrame:
        """创建单个快捷方式卡片"""
        preset = self.SIZE_PRESETS[self._view_size]
        icon_size = preset["icon"]
        card_size = preset["card"]
        font_size = preset["font"]

        # v2.3.15: 卡片背景自适应 — 浅色浅灰, 深色深灰
        card = ctk.CTkFrame(
            self._grid_frame,
            width=card_size, height=card_size,
            corner_radius=12,
            fg_color=("gray88", "gray20"),
            border_width=0,
            cursor="hand2",
        )
        card.grid_propagate(False)

        # v2.3.15 图标：自定义图标用原样，预设图标生成深浅双版本
        icon_b64 = sc.get("icon")
        dark_icon_b64 = None
        if not icon_b64:
            name = sc.get("name", "")
            icon_b64 = IconExtractor._preset_icon(name, theme="light")
            dark_icon_b64 = IconExtractor._preset_icon(name, theme="dark")
        ctk_img = IconExtractor.base64_to_ctkimage(icon_b64, icon_size, dark_icon_b64)

        icon_label = ctk.CTkLabel(card, image=ctk_img, text="", fg_color="transparent", bg_color="transparent")
        icon_label.pack(pady=(12, 2))
        icon_label.image = ctk_img  # 防止被垃圾回收

        # 名称
        name = sc.get("name", "")
        display_name = name if len(name) <= 8 else name[:7] + "…"
        name_label = ctk.CTkLabel(
            card, text=display_name,
            font=ctk.CTkFont(family="微软雅黑", size=font_size),
            text_color=("gray10", "gray80"),
        )
        name_label.pack(pady=(0, 8))

        # 置顶/锁定 徽标
        if sc.get("pinned", False):
            ctk.CTkLabel(
                card, text="📌",
                font=ctk.CTkFont(size=11),
            ).place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=2)
        if sc.get("locked", False):
            ctk.CTkLabel(
                card, text="🔒",
                font=ctk.CTkFont(size=11),
            ).place(relx=0.0, rely=0.0, anchor="nw", x=4, y=2)

        # 事件状态
        click_timer = [None]
        drag_state = {
            "active": False, "start_x": 0, "start_y": 0,
            "sc_id": sc["id"],
        }

        def on_button_press(e):
            """按下：记录位置，启动单击延迟"""
            drag_state["start_x"] = e.x_root
            drag_state["start_y"] = e.y_root
            drag_state["active"] = False
            if click_timer[0]:
                self.after_cancel(click_timer[0])
            click_timer[0] = self.after(
                250, lambda: self._safe_card_click(sc)
            )

        def on_motion(e):
            """移动：检测是否进入拖拽模式"""
            if drag_state["active"]:
                return
            # 锁定项禁止拖拽
            if sc.get("locked", False):
                return
            dx = abs(e.x_root - drag_state["start_x"])
            dy = abs(e.y_root - drag_state["start_y"])
            if dx > 8 or dy > 8:
                if click_timer[0]:
                    self.after_cancel(click_timer[0])
                    click_timer[0] = None
                drag_state["active"] = True
                card.configure(fg_color=("#3b8ee0", "#1f6aa5"))
                hide_tooltip()

        def on_button_release(e):
            """释放：拖拽中则重排"""
            if drag_state["active"]:
                drag_state["active"] = False
                card.configure(fg_color=("gray92", "gray18"))
                self._handle_drop(drag_state["sc_id"], e)
            else:
                if click_timer[0]:
                    pass  # 单击定时器会处理

        def on_double_click():
            """双击：取消单击，打开编辑"""
            if click_timer[0]:
                self.after_cancel(click_timer[0])
                click_timer[0] = None
            drag_state["active"] = False
            self._on_card_double(sc)

        # 悬停效果 — 使用计数器防止子控件间切换时闪烁
        hover_count = [0]

        def on_enter(e):
            hover_count[0] += 1
            if not drag_state["active"]:
                card.configure(fg_color=("gray82", "gray22"))
            if len(name) > 8:
                show_tooltip(e)

        def on_leave(e):
            hover_count[0] -= 1
            if hover_count[0] <= 0:
                hover_count[0] = 0
                if not drag_state["active"]:
                    card.configure(fg_color=("gray92", "gray18"))
                hide_tooltip()

        # Tooltip 函数（仅在名称截断时显示）
        tooltip_win = [None]

        def show_tooltip(e):
            if len(name) <= 8:
                return
            if tooltip_win[0]:
                return
            tooltip_win[0] = tk.Toplevel(self)
            tooltip_win[0].wm_overrideredirect(True)
            # 主题自适应：深色背景配白色文字，浅色背景配深色文字
            is_dark = _get_appearance() == "dark"
            bg_color = "#2b2b2b" if is_dark else "#f0f0f0"
            fg_color = "#ffffff" if is_dark else "#333333"
            tooltip_win[0].configure(bg=bg_color)
            tk.Label(
                tooltip_win[0], text=name, justify="left",
                bg=bg_color, fg=fg_color, relief="flat",
                font=("微软雅黑", 10), padx=6, pady=3,
            ).pack()
            # 边界保护：确保 tooltip 不超出屏幕
            tx = min(e.x_root + 10, self.winfo_screenwidth() - 200)
            ty = min(e.y_root + 10, self.winfo_screenheight() - 40)
            tooltip_win[0].wm_geometry(f"+{tx}+{ty}")

        def hide_tooltip():
            if tooltip_win[0]:
                tooltip_win[0].destroy()
                tooltip_win[0] = None

        for w in (card, icon_label, name_label):
            w.bind("<Button-1>", on_button_press)
            w.bind("<B1-Motion>", on_motion)
            w.bind("<ButtonRelease-1>", on_button_release)
            w.bind("<Button-3>", lambda e, s=sc: self._on_card_rightclick(e, s))
            w.bind("<Double-Button-1>", lambda e: on_double_click())
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return card

    def _handle_drop(self, source_id, event):
        """处理拖拽放置：重新排序（锁定项保持原位）"""
        all_items = self.config.get_ordered_shortcuts()
        if self._current_cat == "全部":
            visible_items = all_items
        else:
            visible_items = [s for s in all_items
                             if s.get("category", "默认") == self._current_cat]

        if len(visible_items) <= 1:
            return

        # 锁定项不可拖动
        source_sc = next((s for s in visible_items if s["id"] == source_id), None)
        if source_sc is None or source_sc.get("locked", False):
            return

        source_idx = None
        for i, s in enumerate(visible_items):
            if s["id"] == source_id:
                source_idx = i
                break
        if source_idx is None:
            return

        # 计算目标位置
        try:
            grid_x = self._grid_frame.winfo_rootx()
            grid_y = self._grid_frame.winfo_rooty()
            mouse_x = event.x_root - grid_x
            mouse_y = event.y_root - grid_y
        except Exception:
            return

        preset = self.SIZE_PRESETS[self._view_size]
        cols = preset["cols"]
        card_w = preset["card"] + 12
        card_h = preset["card"] + 12

        target_col = int(mouse_x // card_w) if card_w > 0 else 0
        target_row = int(mouse_y // card_h) if card_h > 0 else 0
        target_idx = target_row * cols + target_col
        target_idx = max(0, min(len(visible_items) - 1, target_idx))

        # 锁定项保持原位：仅在可移动项之间重排
        locked_slots = {i: s["id"] for i, s in enumerate(visible_items)
                        if s.get("locked", False)}
        movable_ids = [s["id"] for s in visible_items
                       if not s.get("locked", False)]
        if source_id not in movable_ids:
            return
        m_source_idx = movable_ids.index(source_id)

        # 目标在可移动序列中的索引（跳过锁定槽）
        m_target_idx = target_idx
        for li in sorted(locked_slots):
            if li < target_idx:
                m_target_idx -= 1
            elif li == target_idx:
                # 落在锁定槽：吸附到上一个可移动位置
                m_target_idx -= 1
            else:
                break
        m_target_idx = max(0, min(len(movable_ids) - 1, m_target_idx))

        if m_source_idx == m_target_idx:
            return

        # 重排可移动项
        moved_id = movable_ids.pop(m_source_idx)
        movable_ids.insert(m_target_idx, moved_id)

        # 合并：锁定槽保持原位，可移动项依次填入其余槽
        visible_ids = []
        mi = 0
        for i in range(len(visible_items)):
            if i in locked_slots:
                visible_ids.append(locked_slots[i])
            else:
                if mi < len(movable_ids):
                    visible_ids.append(movable_ids[mi])
                    mi += 1

        # 构建完整排序列表
        if self._current_cat == "全部":
            full_ordered = visible_ids
        else:
            visible_set = set(visible_ids)
            vis_iter = iter(visible_ids)
            full_ordered = []
            for s in all_items:
                if s["id"] in visible_set:
                    full_ordered.append(next(vis_iter))
                else:
                    full_ordered.append(s["id"])

        self.config.reorder_shortcuts(full_ordered)
        self._refresh()


    def _migrate_category_names(self):
        """v2.5.5 启动时迁移分类名：避免 UI 已改名为「新增项目」但数据里仍保留旧名「添加快捷方式」"""
        changed = False
        for s in self.config.shortcuts:
            old_cat = s.get("category", "默认")
            if old_cat == "添加快捷方式":
                s["category"] = "新增项目"
                changed = True
        if changed:
            self.config.save()

    def _toggle_view_size(self, choice):
        """切换视图大小"""
        size_map = {"小": "small", "中": "medium", "大": "large"}
        self._view_size = size_map.get(choice, "medium")
        # v3.0.1 持久化视图大小
        try:
            self.config._write_settings({"last_view_size": self._view_size})
        except Exception:
            pass
        self._build_grid(force=True)

    # ---------------------- 批量图标操作 ----------------------
    def _batch_refresh_icons(self):
        """一键按类型批量刷新图标：
            app    → 从真实EXE提取
            system → 解析真实 EXE 路径再提取（解析失败则退回预设简笔画）
            url    → 尝试拉取 favicon（提取失败保留默认图标）
        """
        shortcuts = list(self.config.shortcuts)
        if not shortcuts:
            messagebox.showinfo("提示", "当前还没有项目，无需刷新图标", parent=self)
            return

        total = len(shortcuts)
        if not messagebox.askyesno(
            "确认刷新图标",
            f"将对 {total} 个快捷项按类型重新提取图标：\n\n"
            "  • App：从 EXE/DLL 提取真实图标\n"
            "  • System：解析命令→系统 EXE 后提取（失败退回预设简笔画）\n"
            "  • URL：在线拉取 favicon（失败保留默认图标）\n\n"
            "完成后，所有提取不到的会用'预设简笔画 / 默认 Z'兜底。\n是否继续？",
            parent=self,
        ):
            return

        # 恢复进度条反馈（内联到弹窗的简单进度提示）
        self._refresh_status = ctk.CTkLabel(
            self, text=f"准备刷新 {total} 个图标…",
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color="gray50",
        )
        self._refresh_status.pack(anchor="e", padx=30, pady=(0, 0))
        self.update_idletasks()

        import threading
        cancelled = {"v": False}
        succeeded = {"v": 0}     # 提取成功（拿到了真实图标，非默认）
        fallback = {"v": 0}      # 提取失败，使用了兜底（预设/默认）
        errors = {"v": 0}

        # 先清空 EXTRACTOR 内存缓存，确保拿到最新的
        IconExtractor._cache.clear()

        def worker():
            for idx, sc in enumerate(shortcuts, start=1):
                if cancelled["v"] or not self.winfo_exists():
                    break
                sid = sc["id"]
                stype = sc.get("type", "app")
                pval = sc.get("path", "")
                name = sc.get("name", "")

                try:
                    if stype == "system":
                        # 解析真实 EXE 路径后提取
                        real_path = IconExtractor.resolve_system_cmd_path(pval)
                        if real_path:
                            new_b64 = IconExtractor.extract_from_exe(real_path)
                            # 判断是不是默认图标兜底
                            if new_b64 and new_b64 != IconExtractor._default_icon():
                                succeeded["v"] += 1
                            else:
                                # 提取结果 == 默认图标，改用预设简笔画更合适
                                new_b64 = IconExtractor._preset_icon(name)
                                fallback["v"] += 1
                        else:
                            # 无法解析，退回预设简笔画
                            new_b64 = IconExtractor._preset_icon(name)
                            fallback["v"] += 1

                    elif stype == "app":
                        if pval and os.path.exists(pval):
                            new_b64 = IconExtractor.extract_from_exe(pval)
                            if new_b64 and new_b64 != IconExtractor._default_icon():
                                succeeded["v"] += 1
                            else:
                                fallback["v"] += 1
                        else:
                            new_b64 = IconExtractor._default_icon()
                            fallback["v"] += 1

                    elif stype == "url":
                        new_b64 = IconExtractor.extract_from_url(pval)
                        if new_b64 and new_b64 != IconExtractor._default_icon():
                            succeeded["v"] += 1
                        else:
                            fallback["v"] += 1

                    else:
                        new_b64 = IconExtractor._default_icon()
                        fallback["v"] += 1

                    # 写回（UI 线程内）
                    if self.winfo_exists():
                        def _apply(sid=sid, new_b64=new_b64):
                            try:
                                self.config.update_shortcut(sid, icon=new_b64)
                                self._refresh()
                            except Exception:
                                errors["v"] += 1
                        self.after(0, _apply)

                except Exception:
                    errors["v"] += 1

                # 更新状态文字
                def _progress(i=idx, n=name, t=stype):
                    if not self.winfo_exists():
                        return
                    try:
                        self._refresh_status.configure(
                            text=f"[{i}/{total}] 正在刷新「{n}」（{t}）…"
                        )
                    except Exception:
                        pass
                self.after(0, _progress)

            # 全部完成 — 汇总提示
            def _done():
                if not self.winfo_exists():
                    return
                msg = (
                    f"✅ 刷新完成！共 {total} 项：\n\n"
                    f"  • 成功提取真实图标：{succeeded['v']} 项\n"
                    f"  • 兜底（预设简笔画/Z）：{fallback['v']} 项\n"
                    f"  • 异常：{errors['v']} 项\n\n"
                    f"提取失败的（兜底）可以稍后在该卡片右键「重新提取图标」重试。"
                )
                try:
                    self._refresh_status.configure(text=f"刷新完成！成功{succeeded['v']} / 兜底{fallback['v']}")
                    # 3 秒后清除状态
                    self.after(3000, lambda: self._refresh_status.configure(text=""))
                except Exception:
                    pass
                messagebox.showinfo("完成", msg, parent=self)
            self.after(0, _done)

        threading.Thread(target=worker, daemon=True).start()

    def _safe_card_click(self, sc: dict):
        """安全的卡片点击：检查视图是否存在"""
        try:
            if self.winfo_exists():
                self._on_card_click(sc)
        except Exception:
            pass

    def _on_card_click(self, sc: dict):
        """单击：启动"""
        ok, msg = Launcher.launch(sc)
        if not ok:
            messagebox.showerror("启动失败", msg, parent=self)

    def _on_card_double(self, sc: dict):
        """双击：快速重命名"""
        # v3.0.1 更名总开关关闭时拦截
        try:
            if not self.config.get_category_rename_enabled():
                from tkinter import messagebox as _mb
                _mb.showinfo("更名已关闭", "更名操作已被关闭。\n如需开启，请到 设置 → 导航设置 → 更名设置。", parent=self)
                return
        except Exception:
            pass
        new_name = show_input_dialog(
            self, "重命名", "输入新的名称：", initialvalue=sc["name"]
        )
        if new_name and new_name.strip():
            self.config.update_shortcut(sc["id"], name=new_name.strip())
            self._refresh()

    def _toggle_pin(self, sc: dict):
        """切换置顶：置顶项始终排在最前"""
        sc_id = sc["id"]
        new_pinned = not sc.get("pinned", False)
        all_items = self.config.get_ordered_shortcuts()
        self.config.update_shortcut(sc_id, pinned=new_pinned)
        if new_pinned:
            # 置顶：移到最前
            ordered = [sc_id] + [s["id"] for s in all_items if s["id"] != sc_id]
        else:
            # 取消置顶：放到置顶组之后
            pinned_others = [s["id"] for s in all_items
                             if s.get("pinned", False) and s["id"] != sc_id]
            rest = [s["id"] for s in all_items
                    if not s.get("pinned", False) and s["id"] != sc_id]
            ordered = pinned_others + [sc_id] + rest
        self.config.reorder_shortcuts(ordered)
        self._refresh()

    def _toggle_lock(self, sc: dict):
        """切换锁定：锁定项不可拖动"""
        new_locked = not sc.get("locked", False)
        self.config.update_shortcut(sc["id"], locked=new_locked)
        self._refresh()

    # ---------------------- 快速排序 ----------------------
    def _show_sort_menu(self):
        """弹出排序菜单：提供多种快速排序方式"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="按名称 A → Z", command=lambda: self._apply_sort("name_asc"))
        menu.add_command(label="按名称 Z → A", command=lambda: self._apply_sort("name_desc"))
        menu.add_command(label="按类型分组", command=lambda: self._apply_sort("type"))
        menu.add_command(label="按分类分组", command=lambda: self._apply_sort("category"))
        menu.add_command(label="按添加时间（旧 → 新）", command=lambda: self._apply_sort("id_asc"))
        menu.add_command(label="按添加时间（新 → 旧）", command=lambda: self._apply_sort("id_desc"))
        menu.add_separator()
        menu.add_command(label="随机打乱", command=lambda: self._apply_sort("random"))
        try:
            # 在按钮下方弹出
            btn = None
            for w in self.winfo_children():
                pass
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery() + 10)
        finally:
            menu.grab_release()

    def _apply_sort(self, mode: str):
        """执行排序：根据 mode 调用 config.sort_shortcuts"""
        import random as _random
        # 分类优先级：app / url / system
        type_order = {"app": 0, "url": 1, "system": 2}

        if mode == "name_asc":
            self.config.sort_shortcuts(lambda s: self._pinyin_key(s.get("name", "")))
        elif mode == "name_desc":
            self.config.sort_shortcuts(lambda s: self._pinyin_key(s.get("name", "")), reverse=True)
        elif mode == "type":
            self.config.sort_shortcuts(
                lambda s: (type_order.get(s.get("type", ""), 9), self._pinyin_key(s.get("name", "")))
            )
        elif mode == "category":
            self.config.sort_shortcuts(
                lambda s: (s.get("category", "默认"), self._pinyin_key(s.get("name", "")))
            )
        elif mode == "id_asc":
            self.config.sort_shortcuts(lambda s: s.get("id", 0))
        elif mode == "id_desc":
            self.config.sort_shortcuts(lambda s: s.get("id", 0), reverse=True)
        elif mode == "random":
            # 随机排序：为每项生成随机 key
            rnd_map = {s["id"]: _random.random() for s in self.config.shortcuts}
            self.config.sort_shortcuts(lambda s: rnd_map.get(s["id"], 0))
        self._refresh()

    @staticmethod
    def _pinyin_key(text: str):
        """中文按拼音排序的 key：中文转拼音首字母，非中文保持原样"""
        if not text:
            return ("", "")
        try:
            import pypinyin
            # 返回 (全拼, 首字母)，确保中文与英文混排时中文在前
            full = "".join(item[0] for item in pypinyin.lazy_pinyin(text))
            first = "".join(item[0][0] if item and item[0] else ""
                            for item in pypinyin.lazy_pinyin(text))
            return (full.lower(), first.lower())
        except Exception:
            # 无 pypinyin 库时回退到字符串比较
            return (str(text).lower(), str(text).lower())

    def _move_to_edge(self, sc: dict, edge: str):
        """将单项移到最前/最后（在所属分组内：置顶组 或 非置顶组）"""
        sc_id = sc["id"]
        all_items = self.config.get_ordered_shortcuts()
        if sc.get("pinned", False):
            # 置顶组内移动
            group = [s["id"] for s in all_items if s.get("pinned", False)]
            rest = [s["id"] for s in all_items if not s.get("pinned", False)]
        else:
            pinned_others = [s["id"] for s in all_items if s.get("pinned", False)]
            rest = [s["id"] for s in all_items if not s.get("pinned", False)]
            group = rest
            rest = pinned_others
        # 从 group 中移除目标
        if sc_id in group:
            group.remove(sc_id)
        if edge == "front":
            group.insert(0, sc_id)
        else:
            group.append(sc_id)
        # 重组：置顶组在前
        if sc.get("pinned", False):
            ordered = group + rest
        else:
            ordered = rest + group  # rest 是置顶组
        self.config.reorder_shortcuts(ordered)
        self._refresh()

    def _on_card_rightclick(self, event, sc: dict):
        """右键：菜单"""
        # v3.0.1 更名总开关
        _ren_on = True
        try:
            _ren_on = self.config.get_category_rename_enabled()
        except Exception:
            pass
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="打开", command=lambda: self._on_card_click(sc))
        if _ren_on:
            menu.add_command(label="重命名", command=lambda: self._on_card_double(sc))
        else:
            menu.add_command(label="重命名（已关闭）", state="disabled")
        menu.add_command(label="编辑详情", command=lambda: self._show_edit_dialog(sc))
        menu.add_separator()
        is_pinned = sc.get("pinned", False)
        is_locked = sc.get("locked", False)
        menu.add_command(
            label="取消置顶" if is_pinned else "置顶",
            command=lambda: self._toggle_pin(sc),
        )
        menu.add_command(
            label="解锁位置" if is_locked else "锁定位置（禁止拖动）",
            command=lambda: self._toggle_lock(sc),
        )
        menu.add_command(label="移到最前", command=lambda: self._move_to_edge(sc, "front"))
        menu.add_command(label="移到最后", command=lambda: self._move_to_edge(sc, "back"))
        menu.add_separator()
        menu.add_command(
            label="重新提取图标（从路径/EXE）",
            command=lambda: self._reextract_icon(sc),
        )
        menu.add_command(
            label="重置为默认图标",
            command=lambda: self._reset_icon(sc),
        )
        menu.add_separator()
        menu.add_command(label="删除", command=lambda: self._delete_shortcut(sc))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _reextract_icon(self, sc: dict):
        """重新从路径/URL/系统命令提取真实图标，异步更新"""
        sc_id = sc["id"]
        stype = sc.get("type", "app")
        pval = sc.get("path", "")
        if not pval:
            return

        def on_done(b64):
            final = b64
            if not final:
                if stype == "system":
                    final = IconExtractor._preset_icon(sc.get("name", ""))
                else:
                    final = IconExtractor._default_icon()

            def apply():
                if not self.winfo_exists():
                    return
                self.config.update_shortcut(sc_id, icon=final)
                self._refresh()
            try:
                self.after(0, apply)
            except Exception:
                pass

        # 先放默认占位，避免视觉无变化
        self.config.update_shortcut(
            sc_id, icon=IconExtractor._default_icon()
        )
        self._refresh()
        IconExtractor.extract_async(stype, pval, on_done)

    def _reset_icon(self, sc: dict):
        """重置为默认图标：system 用预设简笔画，其它按类型重走默认/提取"""
        sc_id = sc["id"]
        stype = sc.get("type", "app")
        if stype == "system":
            final = IconExtractor._preset_icon(sc.get("name", ""))
            self.config.update_shortcut(sc_id, icon=final)
            self._refresh()
        else:
            # app/url: 先放默认，同时异步重提取
            self.config.update_shortcut(
                sc_id, icon=IconExtractor._default_icon()
            )
            self._refresh()

            def on_done(b64):
                final = b64 or IconExtractor._default_icon()

                def apply():
                    if not self.winfo_exists():
                        return
                    self.config.update_shortcut(sc_id, icon=final)
                    self._refresh()
                try:
                    self.after(0, apply)
                except Exception:
                    pass

            IconExtractor.extract_async(stype, sc.get("path", ""), on_done)

    def _delete_shortcut(self, sc: dict):
        if messagebox.askyesno("确认删除", f"确定删除「{sc['name']}」？", parent=self):
            self.config.delete_shortcut(sc["id"])
            self._refresh()

    def _filter_category(self, cat: str):
        self._current_cat = cat
        # v3.0.1 跨会话记住用户停留在哪个分类选项卡
        try:
            self.config.set_last_view_category(cat)
        except Exception:
            pass
        self._update_cat_buttons()
        self._build_grid(force=True)

    def _update_cat_buttons(self):
        """v2.3.15 选中态 = 浅蓝底 + 蓝字 + 加粗（无底部横线）"""
        active_bg   = ("#e5f0ff", "#1a3752")
        active_fg   = ("#2d7bc7", "#6bb2ff")
        inactive_bg = "transparent"
        inactive_fg = ("gray30", "gray82")
        hover_bg    = ("#eef5ff", "#243a55")

        for cat, info in self.cat_buttons.items():
            btn = info.get("btn")
            if not btn:
                continue
            is_active = (cat == self._current_cat)
            if is_active:
                btn.configure(fg_color=active_bg, hover_color=active_bg,
                              text_color=active_fg,
                              font=ctk.CTkFont(family="微软雅黑", size=12, weight="bold"))
            else:
                btn.configure(fg_color=inactive_bg, hover_color=hover_bg,
                              text_color=inactive_fg,
                              font=ctk.CTkFont(family="微软雅黑", size=12))

    def _bg_of(self, widget):
        """v2.3.14 获取控件背景色（兜底：根据主题返回默认色）"""
        try:
            return widget.cget("bg") or widget.cget("fg_color") or "transparent"
        except Exception:
            pass
        try:
            return widget.winfo_toplevel().cget("bg") or "transparent"
        except Exception:
            pass
        return "#f2f2f2" if _get_appearance() == "light" else "#1a1a1a"

    def _rebuild_cat_buttons(self):
        """v3.0 分类标签重建：双保险清空 + 正确取 btn 对象 destroy，避免添加分类后旧按钮残留叠加错位
        v3.0.1 新增：非「全部」项绑定拖拽排序；更名开关关闭时锁定（cursor=arrow + 不绑拖拽）"""
        # 双保险 1：清空 cat_frame 里所有子控件（解决幽灵按钮残留叠加）
        for child in self.cat_frame.winfo_children():
            try: child.destroy()
            except Exception: pass
        # 双保险 2：正确取出 btn 对象 destroy（之前 dict.value 是 {btn:} 而非 btn，dict.destroy AttributeError 被吞导致残留）
        for info in self.cat_buttons.values():
            try: info["btn"].destroy()
            except Exception: pass
        self.cat_buttons = {}
        # v3.0.1 更名开关：关闭时所有非全部项 cursor=arrow 且不绑定拖拽
        try:
            _rename_on = self.config.get_category_rename_enabled()
        except Exception:
            _rename_on = True
        cats = ["全部"] + self.config.get_shortcut_categories()
        for idx, cat in enumerate(cats):
            btn = ctk.CTkButton(
                self.cat_frame, text=f"  {cat}  ", height=30,
                fg_color="transparent",
                hover_color=("gray70", "gray30"),
                text_color=("gray30", "gray82"),
                corner_radius=99,
                font=ctk.CTkFont(family="微软雅黑", size=12),
                # 关闭更名开关时，所有非全部项取消 command（避免短按触发切换也被当作拖拽？）
                command=lambda c=cat: self._filter_category(c),
            )
            if cat == "全部":
                # 「全部」：固定项，不允许拖拽
                btn.configure(cursor="hand2")
            else:
                if _rename_on:
                    btn.configure(cursor="hand2")
                    btn.bind("<Button-3>", lambda e, c=cat: self._cat_rightclick(e, c), add="+")
                    # v3.0.1 绑定拖拽（短按切换分类，长按/拖移 拖拽排序）
                    self._bind_cat_drag(btn, cat, idx)
                else:
                    # 更名开关关闭 → 锁定：cursor arrow、无右键、无拖拽
                    btn.configure(cursor="arrow")
            self.cat_buttons[cat] = {"btn": btn}
        self._layout_cat_buttons()
        self._update_cat_buttons()

    def _layout_cat_buttons(self):
        """v2.3.17 分类按钮自适应：用实际渲染宽度计算，自然布局，无循环"""
        pad_x = 6
        cats = list(self.cat_buttons.keys())
        if not cats:
            return
        try:
            frame_w = self.cat_frame.winfo_width()
        except Exception:
            frame_w = 0
        if frame_w < 50:
            # 初次渲染未完成时用顶层窗口宽度估算
            try:
                frame_w = self.cat_frame.winfo_toplevel().winfo_width() - 120
            except Exception:
                frame_w = 800
            if frame_w < 50:
                frame_w = 800

        # 先测量每个按钮的实际渲染宽度（update 后 winfo_reqwidth 才准确）
        try:
            self.cat_frame.update_idletasks()
        except Exception:
            pass
        cat_widths = []
        for cat in cats:
            btn = self.cat_buttons[cat]["btn"]
            try:
                w = btn.winfo_reqwidth()
                # 文本最小合理宽度：中文每字至少 12px，英文 7px；如「管理工具」4 字最少 48px
                # 若测量值明显小于该阈值（如只剩 14px 只够一个字），直接走文本宽度兜底
                min_reasonable = max(30, sum(12 if ord(ch) > 127 else 7 for ch in cat))
                if w < min_reasonable:
                    est = 0
                    for ch in cat:
                        est += 14 if ord(ch) > 127 else 8
                    w = max(56, est + 24)
            except Exception:
                w = 80
            cat_widths.append(w)

        # 逐行贪心
        rows = [[]]
        row_w = 0
        for i, (cat, bw) in enumerate(zip(cats, cat_widths)):
            needed = bw + pad_x
            if row_w + needed <= frame_w or len(rows[-1]) == 0:
                rows[-1].append(i)
                row_w += needed
            else:
                rows.append([i])
                row_w = needed

        # 清除旧 grid 配置（避免闪烁）
        for cat in cats:
            btn = self.cat_buttons[cat]["btn"]
            btn.configure(width=0)  # 让其自然宽度生效，不要强行设置像素级宽度
            try:
                btn.grid_remove()
            except Exception:
                pass

        # grid 摆放
        for r, row_indices in enumerate(rows):
            for local_c, cat_idx in enumerate(row_indices):
                cat = cats[cat_idx]
                btn = self.cat_buttons[cat]["btn"]
                btn.grid(row=r, column=local_c, padx=pad_x//2, pady=2, sticky="w")

    def _on_cat_frame_resize(self, event=None):
        """v2.3.17 防循环：只在顶层大窗口宽度真的变化时才重排，且节流 200ms"""
        if event and hasattr(event, 'widget') and event.widget is not self.cat_frame:
            return
        try:
            cur_w = self.winfo_toplevel().winfo_width()
        except Exception:
            cur_w = 0
        # 窗口宽度没变化就跳过（只子部件大小变化不重排，避免循环）
        if hasattr(self, '_last_top_w') and abs(getattr(self, '_last_top_w', 0) - cur_w) < 5:
            return
        self._last_top_w = cur_w
        if self._cat_layout_job:
            try:
                self.after_cancel(self._cat_layout_job)
            except Exception:
                pass
        self._cat_layout_job = self.after(200, self._layout_cat_buttons)


    def _cat_rightclick(self, event, cat):
        """分类标签右键菜单"""
        _ren_on = True
        try:
            _ren_on = self.config.get_category_rename_enabled()
        except Exception:
            pass
        menu = tk.Menu(self, tearoff=0)
        if _ren_on:
            menu.add_command(label="重命名", command=lambda: self._rename_category(cat))
            menu.add_command(label="删除", command=lambda: self._delete_category(cat))
        else:
            menu.add_command(label="重命名（已关闭）", state="disabled")
            menu.add_command(label="删除（已关闭）", state="disabled")
            menu.add_separator()
            menu.add_command(label="请到 设置 → 导航设置 → 更名设置 开启", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _rename_category(self, old_name):
        """重命名分类"""
        new_name = show_input_dialog(
            self, "重命名分类", "输入新的分类名称：", initialvalue=old_name
        )
        if new_name and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            # 检查是否与已有分类重名
            existing = self.config.get_shortcut_categories()
            if new_name in existing:
                messagebox.showwarning("提示", f"分类「{new_name}」已存在", parent=self)
                return
            self.config.rename_category(old_name, new_name)
            if self._current_cat == old_name:
                self._current_cat = new_name
            self._refresh()

    def _delete_category(self, cat_name):
        """删除分类"""
        count = sum(1 for s in self.config.shortcuts
                    if s.get("category", "默认") == cat_name)
        if messagebox.askyesno(
            "确认删除",
            f"确定删除分类「{cat_name}」？\n"
            f"该分类下有 {count} 个快捷方式，将自动归入「默认」分类。",
            parent=self,
        ):
            self.config.delete_category(cat_name)
            if self._current_cat == cat_name:
                self._current_cat = "全部"
            self._refresh()

    def _bind_cat_drag(self, btn, cat_name, index):
        """可拖拽分类按钮：短按切换分类，长按/拖移 拖拽排序（与导航栏交互一致）
        - 更名开关关闭时 _rebuild_cat_buttons 不调用本方法（天然锁定）
        - 「全部」不绑定（天然固定）"""
        state = {
            "pressed": False,
            "dragging": False,
            "start_x": 0,
            "start_y": 0,
            "cat": cat_name,
            "press_time": 0,
        }

        def on_press(e):
            state["pressed"] = True
            state["dragging"] = False
            state["start_x"] = e.x_root
            state["start_y"] = e.y_root
            import time
            state["press_time"] = time.time()

        def on_motion(e):
            if not state["pressed"] or state["dragging"]:
                if state["dragging"]:
                    self._highlight_cat_drop(e.x_root, e.y_root)
                return
            dx = abs(e.x_root - state["start_x"])
            dy = abs(e.y_root - state["start_y"])
            if max(dx, dy) > 12:
                state["dragging"] = True
                try:
                    btn.configure(fg_color=("#e5f0ff", "#1a3752"),
                                  text_color=("#2d7bc7", "#6bb2ff"),
                                  cursor="fleur")
                except Exception:
                    pass

        def on_release(e):
            if not state["pressed"]:
                return
            state["pressed"] = False
            if state["dragging"]:
                state["dragging"] = False
                try:
                    btn.configure(fg_color="transparent", cursor="hand2")
                except Exception:
                    pass
                self._clear_cat_drop_highlight()
                self._handle_cat_drop(state["cat"], e.x_root, e.y_root)
            else:
                import time
                try:
                    elapsed = time.time() - state["press_time"]
                except Exception:
                    elapsed = 0
                if elapsed < 0.4:
                    # 短按 → 切换分类（这里不再调用 command，防止重复触发，使用显式 _filter_category）
                    self._filter_category(state["cat"])

        # 禁用 button 自带的 command（避免按下即触发；短按在 on_release 里判断）
        try:
            btn.configure(command=None)
        except Exception:
            pass
        widgets = [btn]
        if hasattr(btn, "_canvas"):
            widgets.append(btn._canvas)
        if hasattr(btn, "_text_label"):
            widgets.append(btn._text_label)
        for w in widgets:
            w.bind("<Button-1>", on_press, add="+")
            w.bind("<B1-Motion>", on_motion, add="+")
            w.bind("<ButtonRelease-1>", on_release, add="+")

    def _highlight_cat_drop(self, x_root, y_root):
        """分类拖拽时高亮目标位置（离鼠标最近的非全部/非源分类）"""
        for cat, info in self.cat_buttons.items():
            btn = info.get("btn")
            if not btn or cat == "全部":
                continue
            try:
                bx = btn.winfo_rootx()
                by = btn.winfo_rooty()
                bw = btn.winfo_width()
                bh = btn.winfo_height()
                cx = bx + bw / 2
                cy = by + bh / 2
                # 距离判断：以按钮中心点为目标
                dist = ((x_root - cx)**2 + (y_root - cy)**2) ** 0.5
                if dist < max(bw, bh) * 0.9:
                    btn.configure(text_color=("#2d7bc7", "#6bb2ff"),
                                  font=ctk.CTkFont(family="微软雅黑", size=12, weight="bold"))
                else:
                    btn.configure(text_color=("gray30", "gray82"),
                                  font=ctk.CTkFont(family="微软雅黑", size=12))
            except Exception:
                continue

    def _clear_cat_drop_highlight(self):
        for cat, info in self.cat_buttons.items():
            btn = info.get("btn")
            if not btn:
                continue
            try:
                btn.configure(text_color=("gray30", "gray82"),
                              font=ctk.CTkFont(family="微软雅黑", size=12))
            except Exception:
                continue

    def _handle_cat_drop(self, source_cat, x_root, y_root):
        """分类拖拽放落：找到离鼠标最近的目标分类，交换两者顺序"""
        if not source_cat or source_cat == "全部":
            self._update_cat_buttons()
            return
        # 找离鼠标最近的非「全部」且非源分类
        target_cat = None
        best_dist = float("inf")
        for cat, info in self.cat_buttons.items():
            btn = info.get("btn")
            if not btn or cat == "全部" or cat == source_cat:
                continue
            try:
                bx = btn.winfo_rootx()
                by = btn.winfo_rooty()
                bw = btn.winfo_width()
                bh = btn.winfo_height()
                cx = bx + bw / 2
                cy = by + bh / 2
                dist = ((x_root - cx)**2 + (y_root - cy)**2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    target_cat = cat
            except Exception:
                continue
        if not target_cat or target_cat == source_cat:
            self._update_cat_buttons()
            return
        # 交换顺序并写入配置
        self.config.swap_cat_order(source_cat, target_cat)
        # 记住当前分类（重建后恢复）
        _old_current = self._current_cat
        # 重建
        self._rebuild_cat_buttons()
        # 恢复当前选中
        all_cats_after = ["全部"] + self.config.get_shortcut_categories()
        if _old_current in all_cats_after:
            self._current_cat = _old_current
            self._update_cat_buttons()
            self._build_grid(force=True)

    def _show_category_manager(self):
        """分类管理弹窗"""
        dlg = ctk.CTkToplevel(self)
        dlg.title("管理分类")
        dlg.geometry("420x420")
        dlg.resizable(True, True)
        dlg.minsize(380, 350)
        dlg.transient(self)
        dlg.grab_set()

        dlg.update_idletasks()
        parent = self.winfo_toplevel()
        cx = parent.winfo_x() + parent.winfo_width() // 2 - 210
        cy = parent.winfo_y() + parent.winfo_height() // 2 - 210
        cx = max(0, min(cx, dlg.winfo_screenwidth() - 420))
        cy = max(0, min(cy, dlg.winfo_screenheight() - 420))
        dlg.geometry(f"+{cx}+{cy}")

        ctk.CTkLabel(
            dlg, text="管理分类",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 10))

        # v3.0.1 分类重命名/删除总开关
        _ren_on = True
        try:
            _ren_on = self.config.get_category_rename_enabled()
        except Exception:
            pass
        _disabled_fg = ("gray65", "gray55")

        if _ren_on:
            ctk.CTkLabel(
                dlg, text="右键分类标签可快速重命名或删除",
                font=ctk.CTkFont(family="微软雅黑", size=11),
                text_color="gray50",
            ).pack(anchor="w", padx=20, pady=(0, 10))
        else:
            ctk.CTkLabel(
                dlg, text="更名已关闭（请到 设置 → 导航设置 → 更名设置 开启）",
                font=ctk.CTkFont(family="微软雅黑", size=11),
                text_color="#d68910",
            ).pack(anchor="w", padx=20, pady=(0, 10))

        scroll_area = ctk.CTkScrollableFrame(
            dlg, fg_color="transparent", label_text="",
        )
        scroll_area.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.after(100, lambda: apply_card_scrollbar(scroll_area))

        self._populate_cat_manager(scroll_area, dlg, _ren_on, _disabled_fg)

        ctk.CTkButton(
            dlg, text="关闭", width=100, height=36,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=lambda: (dlg.destroy(), self._refresh()),
        ).pack(pady=(0, 15))

    def _populate_cat_manager(self, scroll_area, dlg, _ren_on=True, _disabled_fg=("gray65", "gray55")):
        """填充分类管理列表"""
        for w in scroll_area.winfo_children():
            w.destroy()

        cats = self.config.get_shortcut_categories()
        if not cats:
            ctk.CTkLabel(
                scroll_area, text="暂无自定义分类",
                font=ctk.CTkFont(family="微软雅黑", size=13),
                text_color="gray50",
            ).pack(pady=30)
            return

        for cat in cats:
            count = sum(1 for s in self.config.shortcuts
                        if s.get("category", "默认") == cat)
            row = ctk.CTkFrame(scroll_area, fg_color=("gray88", "gray17"), corner_radius=8)
            row.pack(fill="x", padx=5, pady=3)

            ctk.CTkLabel(
                row, text=f"{cat}  ({count} 项)",
                font=ctk.CTkFont(family="微软雅黑", size=13),
            ).pack(side="left", padx=15, pady=8)

            _btn_state = "normal" if _ren_on else "disabled"
            ctk.CTkButton(
                row, text="重命名", width=60, height=28,
                font=ctk.CTkFont(family="微软雅黑", size=12),
                state=_btn_state,
                text_color=_disabled_fg if not _ren_on else None,
                fg_color=("gray80", "gray28") if not _ren_on else None,
                command=lambda c=cat: self._rename_category_from_manager(c, dlg, scroll_area),
            ).pack(side="right", padx=(5, 10), pady=5)

            ctk.CTkButton(
                row, text="删除", width=50, height=28,
                fg_color="transparent",
                hover_color=("#e08080", "#b05555"),
                text_color=_disabled_fg if not _ren_on else ("#e74c3c", "#e74c3c"),
                font=ctk.CTkFont(family="微软雅黑", size=12),
                state=_btn_state,
                command=lambda c=cat: self._delete_category_from_manager(c, dlg, scroll_area),
            ).pack(side="right", pady=5)

    def _rename_category_from_manager(self, cat, dlg, scroll_area):
        old_name = cat
        new_name = show_input_dialog(
            dlg, "重命名分类", "输入新的分类名称：", initialvalue=old_name
        )
        if new_name and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            existing = self.config.get_shortcut_categories()
            if new_name in existing:
                messagebox.showwarning("提示", f"分类「{new_name}」已存在", parent=dlg)
                return
            self.config.rename_category(old_name, new_name)
            self._refresh()
            self._populate_cat_manager(scroll_area, dlg)

    def _delete_category_from_manager(self, cat, dlg, scroll_area):
        count = sum(1 for s in self.config.shortcuts
                    if s.get("category", "默认") == cat)
        if messagebox.askyesno(
            "确认删除",
            f"确定删除分类「{cat}」？\n"
            f"该分类下有 {count} 个快捷方式，将自动归入「默认」分类。",
            parent=dlg,
        ):
            self.config.delete_category(cat)
            self._refresh()
            self._populate_cat_manager(scroll_area, dlg)

    def _refresh(self):
        """刷新整个视图，保留当前分类选择（强制重建 grid）"""
        cats = ["全部"] + self.config.get_shortcut_categories()
        if self._current_cat not in cats:
            self._current_cat = "全部"
        self._rebuild_cat_buttons()
        if hasattr(self, 'count_label'):
            self.count_label.configure(
                text=f"  ({len(self.config.shortcuts)} 个项目)"
            )
        self._build_grid(force=True)

    def _show_add_dialog(self):
        self._show_dialog(mode="add")

    def _show_edit_dialog(self, sc: dict):
        self._show_dialog(mode="edit", shortcut=sc)

    def _show_dialog(self, mode="add", shortcut=None):
        """添加/编辑弹窗"""
        dlg = ctk.CTkToplevel(self)
        dlg.title("新增项目" if mode == "add" else "编辑项目")
        dlg.geometry("500x620")
        dlg.resizable(True, True)
        dlg.minsize(480, 600)
        dlg.transient(self)
        dlg.grab_set()

        # 居中显示在父窗口上方
        dlg.update_idletasks()
        parent = self.winfo_toplevel()
        cx = parent.winfo_x() + parent.winfo_width() // 2 - 250
        cy = parent.winfo_y() + parent.winfo_height() // 2 - 320
        cx = max(0, min(cx, dlg.winfo_screenwidth() - 540))
        cy = max(0, min(cy, dlg.winfo_screenheight() - 660))
        dlg.geometry(f"+{cx}+{cy}")

        # 类型选择
        ctk.CTkLabel(
            dlg, text="类型",
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
        ).pack(anchor="w", padx=25, pady=(15, 5))

        # v3.0.1 记住上次新增项目时选择的类型
        if shortcut:
            _init_type = shortcut["type"]
        else:
            try:
                _init_type = self.config._read_settings().get("last_shortcut_type", "app")
            except Exception:
                _init_type = "app"
        type_var = ctk.StringVar(value=_init_type)
        type_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        type_frame.pack(fill="x", padx=25, pady=(0, 8))

        for t, label in [("app", "软件"), ("url", "网址"), ("system", "系统命令")]:
            ctk.CTkRadioButton(
                type_frame, text=label, variable=type_var, value=t,
                font=ctk.CTkFont(family="微软雅黑", size=13),
            ).pack(side="left", padx=(0, 20))

        # 名称
        ctk.CTkLabel(
            dlg, text="名称",
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
        ).pack(anchor="w", padx=25, pady=(5, 5))

        name_entry = ctk.CTkEntry(
            dlg, height=36,
            font=ctk.CTkFont(family="微软雅黑", size=13),
        )
        name_entry.pack(fill="x", padx=25, pady=(0, 8))
        if shortcut:
            name_entry.insert(0, shortcut.get("name", ""))

        # 路径
        ctk.CTkLabel(
            dlg, text="路径 / 网址 / 命令",
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
        ).pack(anchor="w", padx=25, pady=(5, 5))

        path_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        path_frame.pack(fill="x", padx=25, pady=(0, 8))

        path_entry = ctk.CTkEntry(
            path_frame, height=36,
            font=ctk.CTkFont(family="微软雅黑", size=13),
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if shortcut:
            path_entry.insert(0, shortcut.get("path", ""))

        def browse():
            filepath = filedialog.askopenfilename(
                title="选择程序",
                filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
                parent=dlg,
            )
            if filepath:
                path_entry.delete(0, "end")
                path_entry.insert(0, filepath)
                if not name_entry.get():
                    name_entry.insert(0, os.path.splitext(
                        os.path.basename(filepath))[0])

        browse_btn = ctk.CTkButton(
            path_frame, text="浏览…", width=65, height=36,
            fg_color=("gray75", "gray26"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=browse,
        )
        browse_btn.pack(side="right")

        # 分类：已有分类下拉 + 可手动输入 + 记住上次选择
        ctk.CTkLabel(
            dlg, text="分类",
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
        ).pack(anchor="w", padx=25, pady=(5, 5))

        existing_cats = self.config.get_shortcut_categories()
        # 获取上次使用的分类（仅 add 模式下）
        last_cat = self.config._read_settings().get("last_shortcut_category", "默认")
        if shortcut:
            default_cat = shortcut.get("category", "默认")
        elif "默认" in existing_cats:
            default_cat = last_cat if last_cat in existing_cats + ["默认"] else "默认"
        else:
            default_cat = last_cat
        # 组装下拉值：上次的放第一位，随后是其余分类
        dropdown_cats = list(dict.fromkeys(
            [c for c in [default_cat, "默认", *existing_cats] if c and c != default_cat or c == default_cat]
        ))
        # 简化：默认放首位，接着按已有分类排序
        ordered = []
        if default_cat and default_cat not in ordered:
            ordered.append(default_cat)
        for c in existing_cats:
            if c and c not in ordered:
                ordered.append(c)
        if "默认" not in ordered:
            ordered.append("默认")

        cat_entry = ctk.CTkComboBox(
            dlg, height=36,
            values=ordered,
            font=ctk.CTkFont(family="微软雅黑", size=13),
            button_color=("gray80", "gray30"),
            button_hover_color=("gray65", "gray40"),
        )
        cat_entry.set(default_cat)
        cat_entry.pack(fill="x", padx=25, pady=(0, 8))

        # --- 自定义图标区域 ---
        icon_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        icon_frame.pack(fill="x", padx=25, pady=(5, 8))

        # 存储自定义图标
        custom_icon_b64 = [None]

        # 初始化预览图标
        if shortcut and shortcut.get("icon"):
            current_icon_b64 = shortcut["icon"]
        elif shortcut:
            current_icon_b64 = IconExtractor._preset_icon(shortcut.get("name", ""))
        else:
            current_icon_b64 = IconExtractor._default_icon()

        preview_img = IconExtractor.base64_to_ctkimage(current_icon_b64, 48)
        icon_preview = ctk.CTkLabel(
            icon_frame, image=preview_img, text="",
            width=60, height=60,
        )
        icon_preview.pack(side="left", padx=(0, 15))
        icon_preview.image = preview_img

        icon_info = ctk.CTkFrame(icon_frame, fg_color="transparent")
        icon_info.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            icon_info, text="图标",
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
        ).pack(anchor="w")

        def choose_custom_icon():
            filepath = filedialog.askopenfilename(
                title="选择图标图片",
                filetypes=[
                    ("图片文件", "*.png *.ico *.jpg *.jpeg"),
                    ("所有文件", "*.*"),
                ],
                parent=dlg,
            )
            if filepath:
                try:
                    import PIL.Image as PILImage
                    img = PILImage.open(filepath)
                    img = img.convert("RGBA")
                    img = img.resize((48, 48), PILImage.LANCZOS)
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    custom_icon_b64[0] = b64
                    new_img = IconExtractor.base64_to_ctkimage(b64, 48)
                    icon_preview.configure(image=new_img)
                    icon_preview.image = new_img
                except Exception as e:
                    messagebox.showerror("错误", f"无法加载图片：{e}", parent=dlg)

        btns_row = ctk.CTkFrame(icon_info, fg_color="transparent")
        btns_row.pack(anchor="w", pady=(5, 0))

        ctk.CTkButton(
            btns_row, text="自定义图标…", width=110, height=30,
            fg_color=("gray75", "gray26"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=choose_custom_icon,
        ).pack(side="left", padx=(0, 6))

        def refresh_extract_icon():
            """从当前路径/URL/命令重新提取真实图标"""
            stype = type_var.get()
            pval = path_entry.get().strip()
            if not pval:
                messagebox.showinfo("提示", "请先填写路径/URL/系统命令", parent=dlg)
                return

            def apply_extracted(b64):
                extracted = b64
                # system 类型提取失败则退回预设简笔画
                if not extracted and stype == "system":
                    extracted = IconExtractor._preset_icon(name_entry.get().strip() or pval)
                if not extracted:
                    extracted = IconExtractor._default_icon()

                def apply_in_ui():
                    if not dlg.winfo_exists():
                        return
                    custom_icon_b64[0] = extracted
                    new_img = IconExtractor.base64_to_ctkimage(extracted, 48)
                    icon_preview.configure(image=new_img)
                    icon_preview.image = new_img

                # callback 可能来自线程，安全回到主线程
                try:
                    self.after(0, apply_in_ui)
                except Exception:
                    pass

            IconExtractor.extract_async(stype, pval, apply_extracted)

        ctk.CTkButton(
            btns_row, text="提取路径图标", width=110, height=30,
            fg_color=("#3b8ee0", "#1f6aa5"),
            hover_color=("#2d7bc7", "#1a5a8a"),
            text_color="white",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=refresh_extract_icon,
        ).pack(side="left", padx=(0, 6))

        def reset_to_default():
            """重置为默认图标（按路径/类型自动决定）"""
            stype = type_var.get()
            pname = name_entry.get().strip()
            if stype == "system":
                fallback = IconExtractor._preset_icon(pname)
            else:
                fallback = IconExtractor._default_icon()
            custom_icon_b64[0] = None  # 清除自定义标记，让保存时走自动流程
            new_img = IconExtractor.base64_to_ctkimage(fallback, 48)
            icon_preview.configure(image=new_img)
            icon_preview.image = new_img

        ctk.CTkButton(
            btns_row, text="重置为默认", width=100, height=30,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=reset_to_default,
        ).pack(side="left")

        ctk.CTkLabel(
            icon_info,
            text="支持 PNG/ICO/JPG，自动缩放为 48x48\n「提取路径图标」可从 EXE/系统命令直接获取真实图标",
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color="gray50",
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # 按钮区
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(10, 15))

        def save():
            name = name_entry.get().strip()
            path_val = path_entry.get().strip()
            stype = type_var.get()
            cat = cat_entry.get().strip() or "默认"
            # 记住上次使用的分类和类型
            if mode == "add":
                try:
                    self.config._write_settings({"last_shortcut_category": cat, "last_shortcut_type": stype})
                except Exception:
                    pass

            if not name:
                messagebox.showwarning("提示", "请输入名称", parent=dlg)
                return
            if not path_val:
                messagebox.showwarning("提示", "请输入路径", parent=dlg)
                return

            # 确定 icon
            has_custom_icon = custom_icon_b64[0] is not None

            if mode == "add":
                if has_custom_icon:
                    final_icon = custom_icon_b64[0]
                elif stype == "system":
                    final_icon = IconExtractor._preset_icon(name)
                else:
                    final_icon = IconExtractor._default_icon()

                sc = self.config.add_shortcut(
                    name, stype, path_val, final_icon, cat,
                )
                dlg.destroy()
                self._refresh()

                # 异步提取图标（仅当没有自定义图标时）
                if not has_custom_icon and stype in ("app", "url"):
                    def on_icon_ready(icon_b64, sid=sc["id"]):
                        try:
                            if self.winfo_exists():
                                self.config.update_shortcut(sid, icon=icon_b64)
                                self._refresh()
                        except Exception:
                            pass

                    IconExtractor.extract_async(stype, path_val, on_icon_ready)
            else:
                old_path = shortcut.get("path", "")
                old_type = shortcut.get("type", "")
                path_changed = (path_val != old_path or stype != old_type)

                if has_custom_icon:
                    # 用户选了自定义图标，直接使用
                    self.config.update_shortcut(
                        shortcut["id"],
                        name=name, type=stype, path=path_val,
                        icon=custom_icon_b64[0], category=cat,
                    )
                    dlg.destroy()
                    self._refresh()
                elif path_changed and stype in ("app", "url"):
                    # 路径变了，需要重新提取图标
                    self.config.update_shortcut(
                        shortcut["id"],
                        name=name, type=stype, path=path_val,
                        icon=IconExtractor._default_icon(), category=cat,
                    )
                    sc_id = shortcut["id"]
                    dlg.destroy()
                    self._refresh()

                    def on_icon_ready(icon_b64, sid=sc_id):
                        try:
                            if self.winfo_exists():
                                self.config.update_shortcut(sid, icon=icon_b64)
                                self._refresh()
                        except Exception:
                            pass

                    IconExtractor.extract_async(stype, path_val, on_icon_ready)
                elif path_changed and stype == "system":
                    # 类型变为系统命令，使用预设图标
                    self.config.update_shortcut(
                        shortcut["id"],
                        name=name, type=stype, path=path_val,
                        icon=IconExtractor._preset_icon(name), category=cat,
                    )
                    dlg.destroy()
                    self._refresh()
                else:
                    # 路径没变，保留原图标
                    self.config.update_shortcut(
                        shortcut["id"],
                        name=name, type=stype, path=path_val,
                        category=cat,
                    )
                    dlg.destroy()
                    self._refresh()

        ctk.CTkButton(
            btn_frame, text="保存", width=100, height=38,
            font=ctk.CTkFont(family="微软雅黑", size=14, weight="bold"),
            command=save,
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="取消", width=100, height=38,
            fg_color=("gray75", "gray26"),
            font=ctk.CTkFont(family="微软雅黑", size=14),
            command=dlg.destroy,
        ).pack(side="right")

    def _show_presets(self):
        """系统预设弹窗（多选勾选 + 取消可逆 + 批量异步提取真实图标 + 批量删除）"""
        dlg = ctk.CTkToplevel(self)
        dlg.title("系统功能预设")
        dlg.geometry("460x520")
        dlg.resizable(True, True)
        dlg.minsize(480, 520)
        dlg.transient(self)
        dlg.grab_set()

        # 居中显示
        dlg.update_idletasks()
        parent = self.winfo_toplevel()
        cx = parent.winfo_x() + parent.winfo_width() // 2 - 260
        cy = parent.winfo_y() + parent.winfo_height() // 2 - 300
        cx = max(0, min(cx, dlg.winfo_screenwidth() - 520))
        cy = max(0, min(cy, dlg.winfo_screenheight() - 600))
        dlg.geometry(f"+{cx}+{cy}")

        # ---- 标题栏（含全选勾选框）----
        header = ctk.CTkFrame(dlg, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))

        ctk.CTkLabel(
            header, text="选择要添加的系统功能",
            font=ctk.CTkFont(family="微软雅黑", size=16, weight="bold"),
        ).pack(side="left")

        row_widgets_ref = []  # [(preset, cb_var, row_frame, existing_flag)]
        cancelled_flag = {"v": False}  # 用户取消标记

        def select_all():
            """全选（仅未添加的项）"""
            for (preset, cb_var, row_frame, existing) in row_widgets_ref:
                if not existing:
                    cb_var.set(True)

        def select_none():
            """全不选"""
            for (preset, cb_var, row_frame, existing) in row_widgets_ref:
                cb_var.set(False)

        def select_invert():
            """反选（已添加的保持不动）"""
            for (preset, cb_var, row_frame, existing) in row_widgets_ref:
                if not existing:
                    cb_var.set(not cb_var.get())

        # 三个选择按钮放在 header 右侧
        ctk.CTkButton(
            header, text="全选", width=60, height=26,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=select_all,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header, text="全不选", width=60, height=26,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=select_none,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header, text="反选", width=60, height=26,
            fg_color=("gray75", "gray26"),
            hover_color=("gray60", "gray30"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=select_invert,
        ).pack(side="right", padx=(6, 0))

        # ---- 分类 & 可滚动列表 ----
        list_wrap = ctk.CTkFrame(dlg, fg_color="transparent")
        list_wrap.pack(fill="both", expand=True, padx=15, pady=(0, 8))

        scroll_area = ctk.CTkScrollableFrame(
            list_wrap, fg_color="transparent", label_text="",
        )
        scroll_area.pack(fill="both", expand=True)
        self.after(100, lambda: apply_card_scrollbar(scroll_area))

        # ---- 填充列表（按分类分组 + 勾选框）----
        def populate_list():
            for w in scroll_area.winfo_children():
                w.destroy()
            row_widgets_ref.clear()

            # 按分类分组展示
            cats_seen = []
            for p in SYSTEM_PRESETS:
                c = p.get("category", "系统工具")
                if c not in cats_seen:
                    cats_seen.append(c)

            for cat in cats_seen:
                cat_label = ctk.CTkLabel(
                    scroll_area, text=f"  {cat}",
                    font=ctk.CTkFont(family="微软雅黑", size=11, weight="bold"),
                    text_color=("#2d7bc7", "#5dade2"),
                    anchor="w",
                )
                cat_label.pack(fill="x", pady=(10, 2), padx=8)

                for p in SYSTEM_PRESETS:
                    if p.get("category", "系统工具") != cat:
                        continue
                    existing = any(
                        s["path"] == p["path"] and s["type"] == "system"
                        for s in self.config.shortcuts
                    )
                    row = ctk.CTkFrame(
                        scroll_area,
                        fg_color=("gray88", "gray17") if not existing
                                 else ("gray93", "gray14"),
                        corner_radius=8,
                    )
                    row.pack(fill="x", padx=8, pady=2)

                    cb_var = ctk.BooleanVar(value=False)
                    if not existing:
                        cb = ctk.CTkCheckBox(
                            row, text="", variable=cb_var,
                            width=26, height=26, corner_radius=6,
                        )
                        cb.pack(side="left", padx=(12, 4), pady=6)
                        cb.configure(state="normal")
                    else:
                        cb = ctk.CTkCheckBox(
                            row, text="", variable=cb_var,
                            width=26, height=26, corner_radius=6,
                        )
                        cb.pack(side="left", padx=(12, 4), pady=6)
                        cb.configure(state="disabled", text_color_disabled="gray50")
                        cb_var.set(True)  # 已添加的用勾选标记展示，不可变

                    name_lbl = ctk.CTkLabel(
                        row, text=p["name"],
                        font=ctk.CTkFont(family="微软雅黑", size=13),
                        text_color=("gray10", "gray90") if not existing else "gray50",
                    )
                    name_lbl.pack(side="left", padx=(6, 0), pady=6, fill="x", expand=True)

                    # ---- 关键修复：整行单击切换勾选（符合 Windows 列表勾选习惯）----
                    # 这样即使 CTkScrollableFrame 拦截了 Canvas 点击，
                    # 用户点到 row / name_lbl 等任意空白处都能切换勾选
                    if not existing:
                        def _toggle_row(*_a, _cv=cb_var):
                            _cv.set(not _cv.get())
                        # 把点击切换绑定到整行的所有子控件
                        for w in (row, name_lbl):
                            try:
                                w.bind("<Button-1>", _toggle_row, add="+")
                                w.bind("<ButtonRelease-1>",
                                       lambda e, _w=w: _w.event_generate(
                                           "<Configure>"), add="+")
                            except Exception:
                                pass
                        # Checkbutton 自己处理自己的点击（避免 double-toggle）
                        try:
                            cb.bindtags(
                                tuple(t for t in cb.bindtags() if t != row._canvas)
                                if hasattr(row, "_canvas") else cb.bindtags()
                            )
                        except Exception:
                            pass

                    status_txt = "已添加" if existing else f"{p['path']}"
                    ctk.CTkLabel(
                        row, text=status_txt,
                        font=ctk.CTkFont(family="微软雅黑", size=10),
                        text_color="gray50",
                    ).pack(side="right", padx=(0, 14), pady=6)

                    row_widgets_ref.append((p, cb_var, row, existing))

            # 初始化 "全选未添加" 勾选状态（初始未添加）
            # 清除旧选择状态
            pass

        populate_list()

        # ---- 进度条（提取图标时友好显示）----
        progress = ctk.CTkProgressBar(dlg, mode="indeterminate", height=6)
        # 初始不显示，等确认后再启动

        status_lbl = ctk.CTkLabel(
            dlg, text="勾选要添加的项后点击「确认添加」",
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color="gray50",
        )
        status_lbl.pack(fill="x", padx=20, pady=(0, 2))

        # ---- 底部按钮区 ----
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(4, 18))

        def remove_all_added_presets():
            """撤销 — 移除所有已添加的系统预设项（完全可逆）"""
            total = len(self.config.shortcuts)
            preset_paths = set(p["path"] for p in SYSTEM_PRESETS)
            kept = []
            removed = 0
            for s in self.config.shortcuts:
                if s.get("type") == "system" and s.get("path") in preset_paths:
                    removed += 1
                else:
                    kept.append(s)
            if removed == 0:
                messagebox.showinfo("提示", "当前还没有添加任何系统预设项", parent=dlg)
                return
            if not messagebox.askyesno(
                "确认撤销",
                f"将移除已添加的 {removed} 个系统预设项\n此操作可通过重新添加恢复。是否继续？",
                parent=dlg,
            ):
                return
            self.config.shortcuts = kept
            self.config.save()
            self._refresh()
            populate_list()
            messagebox.showinfo("已撤销", f"已移除 {removed} 个系统预设项", parent=dlg)

        def confirm_add_selected():
            """确认添加：勾选的项才写入 → 异步批量提取真实EXE图标 → 每个完成就刷新一次"""
            # 1. 收集勾选的未添加项
            picked = []
            for (preset, cb_var, row, existing) in row_widgets_ref:
                if not existing and cb_var.get():
                    picked.append(preset)

            if not picked:
                messagebox.showinfo("提示", "请先勾选要添加的项", parent=dlg)
                return

            # 记录写入前的旧快照（用于"取消"时回滚 — 虽然对话框关闭就不可逆，
            # 但我们在 UI 提供了"移除已添加预设"按钮，全程可逆）
            progress.pack(fill="x", padx=20, pady=(0, 4))
            progress.start()
            status_lbl.configure(
                text=f"正在添加 {len(picked)} 项，并异步提取真实 EXE 图标…"
            )

            # 2. 先把所有选中项写入（默认使用预设简笔画图标作占位）
            added_ids = []
            for p in picked:
                sc = self.config.add_shortcut(
                    name=p["name"], stype="system",
                    path=p["path"],
                    icon=IconExtractor._preset_icon(p["name"]),
                    category=p.get("category", "默认"),
                )
                added_ids.append((sc["id"], p))

            self._refresh()

            # 3. 异步批量逐个提取真实 EXE 图标 — 完成一个更新一个
            total_jobs = len(added_ids)
            remaining = [total_jobs]  # 用 list 避免闭包作用域问题

            def on_one_done(sc_id, pname, fallback_b64):
                def apply(b64):
                    final_b64 = b64 or IconExtractor._preset_icon(pname)
                    if not self.winfo_exists():
                        return
                    try:
                        self.config.update_shortcut(sc_id, icon=final_b64)
                        self._refresh()
                    except Exception:
                        pass
                    # 全局计数
                    remaining[0] -= 1
                    if remaining[0] <= 0 and dlg.winfo_exists():
                        try:
                            progress.stop()
                            progress.pack_forget()
                            done_count = total_jobs
                            status_lbl.configure(
                                text=f"✅ 已添加 {done_count} 项，图标提取完成"
                            )
                        except Exception:
                            pass

                def schedule():
                    # 因为 extract_async 的 callback 可能不在主线程，我们一律走 after 0
                    apply(fallback_b64)

                schedule()

            import threading
            def async_extract_job():
                for (sc_id, p) in added_ids:
                    if cancelled_flag["v"]:
                        break
                    pname = p["name"]
                    pval = p["path"]
                    real_path = IconExtractor.resolve_system_cmd_path(pval)
                    if real_path:
                        try:
                            b64 = IconExtractor.extract_from_exe(real_path)
                        except Exception:
                            b64 = None
                    else:
                        b64 = None
                    # 回到主线程更新
                    self.after(0, lambda sid=sc_id, nm=pname, fb=b64: on_one_done(sid, nm, fb))

            threading.Thread(target=async_extract_job, daemon=True).start()

            # 4. 重新刷列表（勾选框位置现在显示"已添加"）
            populate_list()

            # 5. 温和提示
            messagebox.showinfo(
                "已写入",
                f"已添加 {len(picked)} 项\n\n真实 EXE 图标正在后台提取，完成后会自动更新。\n关闭窗口前都可以随时关闭。",
                parent=dlg,
            )

        # 「移除所有已添加预设」— 左侧红灰按钮
        ctk.CTkButton(
            btn_frame, text="移除已添加预设", width=150, height=36,
            fg_color=("gray75", "gray26"),
            hover_color=("#c0392b", "#a93226"),
            font=ctk.CTkFont(family="微软雅黑", size=12),
            command=remove_all_added_presets,
        ).pack(side="left", padx=(0, 10))

        # 右侧：取消 + 确认
        ctk.CTkButton(
            btn_frame, text="取消", width=100, height=36,
            fg_color=("gray75", "gray26"),
            font=ctk.CTkFont(family="微软雅黑", size=13),
            command=lambda: (
                cancelled_flag.__setitem__("v", True),
                dlg.destroy(),
                self._refresh(),
            ),
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="确认添加", width=110, height=36,
            font=ctk.CTkFont(family="微软雅黑", size=13, weight="bold"),
            command=confirm_add_selected,
        ).pack(side="right")

    def refresh(self):
        self._refresh()


# ============================================================
# 主应用窗口
# ============================================================
APP_USER_MODEL_ID = "ZhixingStudio.Workbench.v3"


def set_process_app_user_model_id(appid=APP_USER_MODEL_ID):
    """v2.5.8 进程级 Shell AppUserModelID 关联
    修复「右键固定到任务栏」后显示 Python 徽标 / 名字变 Python GUI / 重 2 层图标的问题。
    失败静默（Win7 前不支持该 API，非关键路径）。
    """
    try:
        import ctypes
        from ctypes import wintypes
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        try:
            proc = getattr(shell32, "SetCurrentProcessExplicitAppUserModelID")
        except AttributeError:
            return False
        proc.argtypes = [wintypes.LPCWSTR]
        proc.restype = ctypes.c_long
        return proc(appid) == 0
    except Exception:
        return False


def set_window_app_user_model_id(hwnd, appid=APP_USER_MODEL_ID):
    """v2.5.8 窗口级 AppUserModelID 写入（SHGetPropertyStoreForWindow + IPropertyStore）
    进程级设置之后创建的窗口会继承 APPID，但部分 Tk/DWM 组合需要对已创建窗口
    再显式写一次 PropertyStore，Shell 才真正把它认成同一个 App。
    失败静默。
    """
    try:
        import ctypes
        from ctypes import wintypes, byref, POINTER, Structure, HRESULT, c_void_p
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        class PROPVARIANT(Structure):
            _fields_ = [
                ("vt", ctypes.c_ushort),
                ("r1", ctypes.c_ushort),
                ("r2", ctypes.c_ushort),
                ("r3", ctypes.c_ubyte * 4),
                ("pwszVal", ctypes.c_wchar_p),
            ]
        class PROPERTYKEY(Structure):
            _fields_ = [("fmtid", ctypes.c_byte * 16), ("pid", wintypes.DWORD)]
        PKEY_AUID_FMTID = bytes.fromhex("55284C9F799F394BA8D0E1D42DE1D5F3")
        pkey = PROPERTYKEY(); ctypes.memmove(byref(pkey.fmtid), PKEY_AUID_FMTID, 16); pkey.pid = 5

        try:
            _sh_get = getattr(shell32, "SHGetPropertyStoreForWindow")
        except AttributeError:
            return False
        class GUID(Structure):
            _fields_ = [("D1", wintypes.DWORD), ("D2", wintypes.WORD), ("D3", wintypes.WORD), ("D4", ctypes.c_ubyte * 8)]
        IID_IPS = bytes.fromhex("eb8e6d88f28c46448d02cdba1dbdcf99")
        riid = GUID(); ctypes.memmove(byref(riid), IID_IPS, len(IID_IPS))

        _sh_get.argtypes = [wintypes.HWND, ctypes.c_void_p, POINTER(c_void_p)]
        _sh_get.restype = HRESULT
        ppv = ctypes.c_void_p()
        hr = _sh_get(hwnd, byref(riid), byref(ppv))
        if hr != 0 or not ppv:
            return False
        try:
            vt_ppv = ctypes.cast(ppv, POINTER(c_void_p))
            vtable = ctypes.cast(vt_ppv[0], POINTER(c_void_p))
            SetValue = ctypes.cast(vtable[5], ctypes.WINFUNCTYPE(
                HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT)))
            pv = PROPVARIANT(); pv.vt = 31; pv.pwszVal = appid
            if SetValue(ppv, byref(pkey), byref(pv)) != 0:
                return False
            Commit = ctypes.cast(vtable[6], ctypes.WINFUNCTYPE(HRESULT, c_void_p))
            return Commit(ppv) == 0
        finally:
            vt_ppv = ctypes.cast(ppv, POINTER(c_void_p))
            vtable = ctypes.cast(vt_ppv[0], POINTER(c_void_p))
            Release = ctypes.cast(vtable[2], ctypes.WINFUNCTYPE(wintypes.ULONG, c_void_p))
            Release(ppv)
    except Exception:
        return False



class WorkbenchApp(ctk.CTk):
    """主应用窗口"""

    # 导航项定义（可扩展：在此添加新的导航项即可）
    NAV_ITEMS = [
        ("首页", HomeView, "🏠"),
        ("快捷启动", QuickLaunchView, "🚀"),
        ("待办事项", TodoView, "📋"),
        ("笔记", NotesView, "📝"),
        ("设置", SettingsView, "⚙"),
        ("关于", AboutView, "ℹ"),
    ]
    # 固定导航项（不可拖拽，始终保持在原位）
    NAV_FIXED_LABELS = {"首页", "设置", "关于"}
    # 原始标签 → (视图类, 图标) 的快速查找表
    _NAV_DICT = {label: (vc, ic) for label, vc, ic in NAV_ITEMS}

    def __init__(self, config):
        super().__init__()
        # 防闪屏：创建后立即隐藏，所有布局/居中完成后再显示
        self.withdraw()
        self.attributes("-alpha", 0.0)
        self.config = config
        self._locked = False

        # 应用主题
        theme = config.config.get("theme", "dark")
        ctk.set_appearance_mode(theme)

        # 窗口设置
        self.title(f"{APP_NAME} - v{APP_VERSION}")
        self.minsize(1100, 840)      # 最小尺寸：完整展示首页+待办输入框+番茄钟说明+应用功能卡片
        self.maxsize(1600, 1000)    # v2.3.19 最大尺寸限制，避免设置界面被拉得过大
        self.configure(fg_color=("gray93", "gray10"))
        # v3.1 恢复上次窗口大小与位置（带有效性校验：尺寸在 [minsize,maxsize] 内，XY 落在屏幕可见区）
        MIN_W, MIN_H, MAX_W, MAX_H = 1100, 840, 1600, 1000
        _geom_used = False
        try:
            _geom = self.config.get_window_geometry()
            if _geom and "x" in _geom and "+" in _geom:
                import re as _re
                _m = _re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", _geom)
                if _m:
                    W, H, X, Y = int(_m.group(1)), int(_m.group(2)), int(_m.group(3)), int(_m.group(4))
                    if MIN_W <= W <= MAX_W and MIN_H <= H <= MAX_H:
                        sw = self.winfo_screenwidth()
                        sh = self.winfo_screenheight()
                        # XY 合理性：窗口左上角必须在屏幕内，且至少 100×100 可见
                        if -W + 100 <= X <= sw - 100 and -H + 100 <= Y <= sh - 100:
                            self.geometry(f"{W}x{H}+{X}+{Y}")
                            _geom_used = True
        except Exception:
            _geom_used = False
        if not _geom_used:
            self.geometry("1200x860")    # 兜底：Win11 风格，1080p 居中展示全部内容
            center_window(self, 1200, 860)
        # 在 withdraw 前设置图标，确保首次 deiconify 时任务栏图标正确
        set_window_icon(self)
        # v2.5.8+：窗口级 AppID — 让 Shell/Taskbar 把主窗口识别为知行工作台 App
        try:
            set_window_app_user_model_id(int(self.winfo_id()))
        except Exception:
            pass

        # ====== v2.3.18 自动锁屏：idle 计时 + 键鼠监听 ======
        self._idle_seconds = 0
        self._idle_lock_running = True
        self._idle_after_id = None
        self._bind_idle_listeners()
        self.after(500, self._tick_idle_timer)
        # ====== end 自动锁屏 ======

        # 当前视图
        self.current_view = None
        self.current_view_index = 0
        self._active_original_label = None
        self.nav_buttons = {}
        self._nav_click_timer = None  # 导航单击延迟定时器

        # 导航顺序（从配置加载或使用默认）
        saved_order = config.get_nav_order()
        all_labels = [label for label, _, _ in self.NAV_ITEMS]
        if saved_order and set(saved_order) == set(all_labels):
            self._nav_order = saved_order[:]
        else:
            self._nav_order = all_labels[:]
        # 规范化：首页固定第一位，设置倒数第二位，关于最后一位
        self._nav_order = self._normalize_nav_order(self._nav_order)

        # 构建界面
        self._build_layout()

        # 默认显示首页
        self._switch_view(0)

        # 居中显示主窗口
        self.update_idletasks()
        center_window(self, 1200, 860)
        # 防闪屏：所有布局完成后才显示窗口
        self.deiconify()
        self.update_idletasks()
        self.attributes("-alpha", 1.0)
        # 窗口可见后再设置图标，确保 Windows 任务栏正确显示
        set_window_icon(self)
        # v2.5.8+：窗口可见后再写一次 AppID PropertyStore（DWM 刷新后仍生效）
        try:
            set_window_app_user_model_id(int(self.winfo_id()))
        except Exception:
            pass

        # 托盘：拦截关闭按钮 → 隐藏到托盘而非退出
        self._allow_destroy = False
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        # 最小化事件处理：也可选择最小化到托盘
        self._minimize_to_tray = True

    def _on_close_request(self):
        """点击窗口 X：隐藏到托盘"""
        if getattr(self, "_allow_destroy", False):
            # 托盘退出菜单已经设置了 _allow_destroy，真正销毁
            try:
                super().destroy()
            except Exception:
                pass
            return
        # 否则隐藏到托盘
        try:
            self.withdraw()
        except Exception:
            pass

    def _build_layout(self):
        # 侧边栏
        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0,
                                    fg_color=("gray89", "gray13"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # 应用名称（Logo 区）— 双击触发锁屏
        logo_label = ctk.CTkLabel(
            self.sidebar, text=APP_NAME,
            font=ctk.CTkFont(family="微软雅黑", size=20, weight="bold"),
            cursor="hand2",
        )
        logo_label.pack(pady=(25, 5))
        logo_label.bind("<Double-Button-1>", lambda e: self._show_lock_screen())

        slogan_label = ctk.CTkLabel(
            self.sidebar, text=APP_SLOGAN,
            font=ctk.CTkFont(family="微软雅黑", size=11),
            text_color=("gray52", "gray58"),
            cursor="hand2",
        )
        slogan_label.pack(pady=(0, 25))
        slogan_label.bind("<Double-Button-1>", lambda e: self._show_lock_screen())

        # 分隔线
        ctk.CTkFrame(self.sidebar, height=1, fg_color=("gray76", "gray28")).pack(
            fill="x", padx=20, pady=(0, 15))

        # 导航按钮容器
        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="both", expand=True)

        # 构建导航按钮
        self._rebuild_nav_buttons()

        # 底部版本信息
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=15)

        ctk.CTkFrame(bottom_frame, height=1, fg_color=("gray76", "gray28")).pack(
            fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            bottom_frame, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=11, weight="bold"),
            text_color=("gray46", "gray56"),
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            bottom_frame, text=f"© 2026 {COPYRIGHT_OWNER} · {COPYRIGHT_SITE}",
            font=ctk.CTkFont(family=("Segoe UI Variable", "微软雅黑"), size=10),
            text_color=("gray42", "gray52"),
        ).pack()

        # 内容区域
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")

        # 网格配置
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _normalize_nav_order(self, order):
        """规范化导航顺序：首页第一位，设置倒数第二位，关于最后一位"""
        default = [label for label, _, _ in self.NAV_ITEMS]
        if not order:
            return default
        # 非固定项保持相对顺序
        movable = [lbl for lbl in order if lbl not in self.NAV_FIXED_LABELS]
        # 补齐缺失的非固定项
        for label in default:
            if label not in self.NAV_FIXED_LABELS and label not in movable:
                movable.append(label)
        return ["首页"] + movable + ["设置", "关于"]

    def _rebuild_nav_buttons(self):
        """重建导航按钮（保留当前选中状态）"""
        for btn in self.nav_buttons.values():
            btn.destroy()
        self.nav_buttons = {}

        custom_labels = self.config.get_nav_labels()
        for i, original_label in enumerate(self._nav_order):
            _, icon = self._NAV_DICT[original_label]
            display_label = custom_labels.get(original_label, original_label)
            is_fixed = original_label in self.NAV_FIXED_LABELS
            drag_enabled = self.config.get_nav_drag_enabled()
            # 固定项 或 拖拽关闭时：使用 command 切换
            use_command = is_fixed or not drag_enabled
            btn = ctk.CTkButton(
                self.nav_container,
                text=f"  {icon}  {display_label}",
                height=44,
                anchor="w",
                fg_color="transparent",
                hover_color=("gray80", "gray24"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(family="微软雅黑", size=14),
                command=(lambda idx=i: self._delayed_switch(idx)) if use_command else None,
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[i] = btn

            # 右键菜单（重命名 / 恢复默认）
            btn.bind("<Button-3>",
                     lambda e, ol=original_label, b=btn: self._show_nav_menu(e, ol, b))
            # 双击重命名
            btn.bind("<Double-Button-1>",
                     lambda e, ol=original_label: self._rename_nav(ol))

            if not is_fixed and drag_enabled:
                # 可拖拽项：手动处理点击 + 长按拖拽
                self._bind_nav_drag(btn, i, original_label)
                btn.configure(cursor="hand2")
            else:
                btn.configure(cursor="arrow" if is_fixed else "hand2")

        self._update_nav_styles()

    def _show_nav_menu(self, event, original_label, btn):
        """导航按钮右键菜单"""
        _ren_on = True
        try:
            _ren_on = self.config.get_category_rename_enabled()
        except Exception:
            pass
        menu = tk.Menu(self, tearoff=0)
        current = self.config.get_nav_labels().get(original_label, original_label)
        if _ren_on:
            menu.add_command(label=f"重命名「{current}」", command=lambda: self._rename_nav(original_label))
        else:
            menu.add_command(label=f"重命名「{current}」（已关闭）", state="disabled")
        if original_label in self.config.get_nav_labels():
            menu.add_command(label="恢复默认名称", command=lambda: self._reset_nav_name(original_label))
        menu.add_separator()
        if _ren_on:
            menu.add_command(label="提示：双击也可重命名", state="disabled")
        else:
            menu.add_command(label="更名已关闭（设置 → 导航设置 → 更名设置）", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _reset_nav_name(self, original_label):
        """恢复导航项默认名称"""
        self.config.set_nav_label(original_label, original_label)
        self._rebuild_nav_buttons()

    def _rename_nav(self, original_label):
        """双击重命名导航项 — 仅当前激活页面可重命名"""
        # 非当前页面：不处理，让延迟切换继续
        if original_label != self._active_original_label:
            return
        # v3.0.1 更名总开关关闭时拦截
        try:
            if not self.config.get_category_rename_enabled():
                from tkinter import messagebox as _mb
                _mb.showinfo("更名已关闭", "更名操作已被关闭。\n如需开启，请到 设置 → 导航设置 → 更名设置。")
                return
        except Exception:
            pass
        # 取消延迟切换
        if self._nav_click_timer:
            self.after_cancel(self._nav_click_timer)
            self._nav_click_timer = None
        current = self.config.get_nav_labels().get(original_label, original_label)
        new_name = show_input_dialog(
            self, "重命名", "输入新的名称：", initialvalue=current
        )
        if new_name and new_name.strip():
            new_name = new_name.strip()
            self.config.set_nav_label(original_label, new_name)
            self._rebuild_nav_buttons()

    def _bind_nav_drag(self, btn, index, original_label):
        """可拖拽导航按钮：短按切换页面，长按拖拽排序"""
        state = {
            "pressed": False,       # 是否按下
            "dragging": False,      # 是否正在拖拽
            "start_y": 0,           # 按下 y 坐标
            "index": index,
            "press_time": 0,        # 按下时间戳
        }

        def on_press(e):
            state["pressed"] = True
            state["dragging"] = False
            state["start_y"] = e.y_root
            import time
            state["press_time"] = time.time()

        def on_motion(e):
            if not state["pressed"] or state["dragging"]:
                if state["dragging"]:
                    # 拖拽中：实时高亮目标位置
                    self._highlight_drop_target(e.y_root)
                return
            dy = abs(e.y_root - state["start_y"])
            if dy > 12:
                # 进入拖拽模式
                state["dragging"] = True
                btn.configure(fg_color=("#3b8ee0", "#1f6aa5"))
                btn.configure(cursor="size")

        def on_release(e):
            if not state["pressed"]:
                return
            state["pressed"] = False

            if state["dragging"]:
                state["dragging"] = False
                btn.configure(fg_color="transparent")
                btn.configure(cursor="hand2")
                self._clear_drop_highlight()
                self._handle_nav_drop(state["index"], e.y_root)
            else:
                # 短按 → 切换页面
                import time
                elapsed = time.time() - state["press_time"]
                if elapsed < 0.4:
                    self._delayed_switch(state["index"])

        # 绑定到 CTkButton 所有内部组件
        widgets = [btn]
        if hasattr(btn, "_canvas"):
            widgets.append(btn._canvas)
        if hasattr(btn, "_text_label"):
            widgets.append(btn._text_label)
        for w in widgets:
            w.bind("<Button-1>", on_press, add="+")
            w.bind("<B1-Motion>", on_motion, add="+")
            w.bind("<ButtonRelease-1>", on_release, add="+")

    def _highlight_drop_target(self, y_pos):
        """拖拽时高亮目标位置"""
        for i, btn in self.nav_buttons.items():
            try:
                by = btn.winfo_rooty()
                bh = btn.winfo_height()
                center_y = by + bh / 2
                # 非固定项且离鼠标最近的 → 高亮
                label = self._nav_order[i]
                if label in self.NAV_FIXED_LABELS:
                    continue
                if abs(y_pos - center_y) < bh / 2:
                    btn.configure(text_color=("#3b8ee0", "#5dade2"))
                else:
                    btn.configure(text_color=("gray10", "gray90"))
            except Exception:
                continue

    def _clear_drop_highlight(self):
        """清除拖拽高亮"""
        for i, btn in self.nav_buttons.items():
            try:
                btn.configure(text_color=("gray10", "gray90"))
            except Exception:
                continue

    def _handle_nav_drop(self, source_index, y_pos):
        """处理导航拖拽放置 — 仅非固定项可移动"""
        source_label = self._nav_order[source_index]
        # 固定项不允许拖拽（理论上不会触发，防御性检查）
        if source_label in self.NAV_FIXED_LABELS:
            self._update_nav_styles()
            return

        # 收集所有非固定项的索引（按当前顺序）
        movable_indices = [i for i, lbl in enumerate(self._nav_order)
                           if lbl not in self.NAV_FIXED_LABELS]

        # 在非固定项中找到离拖放位置最近的目标
        target_movable_idx = None
        best_dist = float("inf")
        for mi in movable_indices:
            btn = self.nav_buttons.get(mi)
            if not btn:
                continue
            try:
                by = btn.winfo_rooty()
                bh = btn.winfo_height()
                center_y = by + bh / 2
                dist = abs(y_pos - center_y)
                if dist < best_dist:
                    best_dist = dist
                    target_movable_idx = mi
            except Exception:
                continue

        if target_movable_idx is None or source_index == target_movable_idx:
            self._update_nav_styles()
            return

        # 在 _nav_order 中交换两个非固定项的位置
        src_idx_in_order = source_index
        tgt_idx_in_order = target_movable_idx
        self._nav_order[src_idx_in_order], self._nav_order[tgt_idx_in_order] = \
            self._nav_order[tgt_idx_in_order], self._nav_order[src_idx_in_order]
        self.config.set_nav_order(self._nav_order)

        # 记住当前激活的原始标签
        active_label = self._active_original_label

        # 重建按钮
        self._rebuild_nav_buttons()

        # 恢复到之前激活的视图
        if active_label and active_label in self._nav_order:
            new_idx = self._nav_order.index(active_label)
            self._switch_view(new_idx)
        else:
            self._switch_view(0)

    def _update_nav_styles(self):
        """更新导航按钮样式（高亮 + 左侧强调条）"""
        for i, btn in self.nav_buttons.items():
            active = (i == self.current_view_index)
            # 清理旧 accent bar
            for child in btn.winfo_children():
                if getattr(child, "_is_accent", False):
                    try:
                        child.destroy()
                    except Exception:
                        pass
            if active:
                bg = ("gray80", "gray22")
                accent = ctk.CTkFrame(btn, width=3, corner_radius=0,
                                      fg_color=("#4a90d9", "#63a6e0"))
                accent._is_accent = True
                accent.place(relx=0.0, rely=0.12, relheight=0.76, anchor="nw")
            else:
                bg = "transparent"
            try:
                btn.configure(fg_color=bg)
            except Exception:
                pass

    def _delayed_switch(self, index):
        """延迟切换视图（让双击事件先被处理）"""
        if self._nav_click_timer:
            self.after_cancel(self._nav_click_timer)
        self._nav_click_timer = self.after(220, lambda: self._do_switch(index))

    def _do_switch(self, index):
        """实际执行视图切换"""
        self._nav_click_timer = None
        self._switch_view(index)

    def _switch_view(self, index):
        self.current_view_index = index
        self._active_original_label = self._nav_order[index]

        self._update_nav_styles()

        # 清理残留 tooltip 窗口
        for child in self.winfo_children():
            try:
                if isinstance(child, tk.Toplevel) and child.wm_overrideredirect():
                    child.destroy()
            except Exception:
                pass

        # 销毁旧视图
        if self.current_view:
            self.current_view.destroy()

        # 创建新视图
        original_label = self._nav_order[index]
        view_cls, _ = self._NAV_DICT[original_label]
        self.current_view = view_cls(self.content, self.config)
        self.current_view.pack(fill="both", expand=True)

    def refresh_current_view(self):
        if self.current_view and hasattr(self.current_view, "refresh"):
            self.current_view.refresh()

    # --- 锁屏功能 ---
    # ---------------- v2.3.18 自动锁屏 idle 计时 ----------------
    def _bind_idle_listeners(self):
        """监听所有鼠标/键盘交互，重置 idle 计时"""
        def _reset(e=None):
            self._reset_idle_timer()
        try:
            self.bind_all("<Button-1>", _reset, add="+")
            self.bind_all("<Key>", _reset, add="+")
            self.bind_all("<Motion>", _reset, add="+")
            self.bind_all("<MouseWheel>", _reset, add="+")
        except Exception:
            pass

    def _reset_idle_timer(self):
        """交互发生 → 重置计时器"""
        self._idle_seconds = 0

    def _tick_idle_timer(self):
        """每 30 秒 tick 一次，检查是否超过阈值"""
        if getattr(self, "_idle_lock_running", True):
            try:
                limit_min = int(self.config.get_auto_lock_minutes())
            except Exception:
                limit_min = 0
            if limit_min > 0:
                self._idle_seconds += 30
                limit_sec = limit_min * 60
                if self._idle_seconds >= limit_sec and not getattr(self, "_locked", False):
                    self._idle_lock_now()
        self._idle_after_id = self.after(30000, self._tick_idle_timer)

    def _idle_lock_now(self):
        """达到阈值：自动锁屏 + 主窗口收纳至托盘"""
        # 如果之前已经锁了，不要重复操作
        if getattr(self, "_locked", False):
            return
        try:
            self._show_lock_screen()
            # 锁屏同时：最小化 → 窗口隐藏到任务栏下方；或用户偏好直接进托盘
            # 这里采用：锁屏后保留锁屏界面但让主窗口最小化（仍在任务栏可见，但必须输入密码才能进入）
            # 若用户设置了自动收纳，则直接 withdraw 至托盘
            try:
                if self.config.get_auto_dock_enabled():
                    self.withdraw()
                    # 托盘图标保持可见（由 TrayManager 管理）
            except Exception:
                pass
        except Exception:
            pass

    def _show_lock_screen(self):
        """锁屏：隐藏主界面，显示锁屏界面"""
        if self._locked:
            return
        self._locked = True
        # idle 复位
        self._reset_idle_timer()

        # 隐藏侧边栏和内容
        self.sidebar.grid_forget()
        self.content.grid_forget()

        # 创建锁屏界面
        self.lock_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.lock_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        center = ctk.CTkFrame(self.lock_frame, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # 锁图标
        ctk.CTkLabel(
            center, text="🔒",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(0, 20))

        # 应用名称
        ctk.CTkLabel(
            center, text=APP_NAME,
            font=ctk.CTkFont(family="微软雅黑", size=28, weight="bold"),
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            center, text="已锁定，请输入密码解锁",
            font=ctk.CTkFont(family="微软雅黑", size=13),
            text_color="gray60",
        ).pack(pady=(0, 30))

        # 密码输入
        pw_entry = ctk.CTkEntry(
            center, placeholder_text="请输入密码", show="*",
            width=280, height=42,
            font=ctk.CTkFont(family="微软雅黑", size=14),
            border_width=2,
        )
        pw_entry.pack(pady=(0, 15))
        pw_entry.bind("<Return>", lambda e: do_unlock())
        pw_entry.focus_set()

        # 错误提示
        error_label = ctk.CTkLabel(
            center, text="",
            font=ctk.CTkFont(family="微软雅黑", size=12),
            text_color="#e74c3c",
        )
        error_label.pack(pady=(5, 0))

        def do_unlock():
            pw = pw_entry.get().strip()
            if not pw:
                error_label.configure(text="请输入密码")
                return
            ok, status = self.config.verify_password(pw)
            if ok:
                self._hide_lock_screen()
            else:
                error_label.configure(text="密码错误，请重新输入")
                pw_entry.delete(0, "end")

        ctk.CTkButton(
            center, text="解 锁", width=280, height=42,
            font=ctk.CTkFont(family="微软雅黑", size=15, weight="bold"),
            command=do_unlock,
        ).pack(pady=(0, 10))

    def _hide_lock_screen(self):
        """解锁：恢复主界面"""
        if hasattr(self, "lock_frame") and self.lock_frame:
            self.lock_frame.destroy()
            self.lock_frame = None
        self._locked = False

        # 恢复侧边栏和内容
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 刷新当前视图
        self.refresh_current_view()


# ============================================================
# 应用入口
# ============================================================
class Application:
    """应用主控制器"""

    def __init__(self):
        # v2.5.8+：进程级 Shell AppUserModelID（"固定到任务栏"关联根因修复）
        #   —— 关联"运行中的窗口 / 固定到任务栏 / 快捷方式 / 跳转列表"，
        #   防止固定后图标变成 Python 徽标 / 名字变 Python GUI / 固定再开重 2 层。
        set_process_app_user_model_id()
        self.config = ConfigManager()
        self.logged_in = False
        self.theme = self.config.config.get("theme", "dark")
        self.tray = None
        self.app = None

    def run(self):
        """启动应用：先登录，成功后进入主界面"""
        self._show_login()
        if self.logged_in:
            self._run_main()

    def _show_login(self):
        """显示登录窗口（首次使用时为设置密码界面）"""
        self.login_window = ctk.CTk()
        self.login_window.minsize(400, 400)
        self.login_window.configure(fg_color=("gray92", "gray12"))
        self.login_window.resizable(False, False)
        set_window_icon(self.login_window)
        # v2.5.8+：窗口级 AppID — 让 Shell/Taskbar 把登录窗口也识别为"知行工作台"
        try:
            set_window_app_user_model_id(int(self.login_window.winfo_id()))
        except Exception:
            pass

        if self.config.is_first_run():
            # 首次使用：显示设置密码界面
            self.login_window.title(f"{APP_NAME} - 设置密码")
            self._login_frame = SetupPasswordFrame(
                self.login_window,
                self.config,
                on_setup_success=self._on_setup_success,
            )
        else:
            # 已有密码：显示登录界面
            self.login_window.title(f"{APP_NAME} - 登录")
            self._login_frame = LoginFrame(
                self.login_window,
                self.config,
                on_login_success=self._on_login_success,
            )
        self._login_frame.pack(fill="both", expand=True)

        # 居中显示
        self.login_window.update_idletasks()
        w = max(500, self.login_window.winfo_reqwidth())
        h = max(500, self.login_window.winfo_reqheight())
        center_window(self.login_window, w, h)

        # Auto-login for testing/screenshots
        if getattr(self, '_auto_login', False):
            self.login_window.after(1500, self._do_auto_login)

        self.login_window.mainloop()

    def _do_auto_login(self):
        """自动登录（测试/截图用）"""
        if hasattr(self, '_login_frame') and self._login_frame:
            self._login_frame.pw_entry.insert(0, "868899")
            self._login_frame._on_login()

    def _on_login_success(self):
        """登录成功回调：解锁数据并进入主界面"""
        self.logged_in = True
        password = self._login_frame.get_password()
        self.config.unlock(password)
        self.login_window.destroy()

    def _on_setup_success(self, password):
        """首次设置密码成功回调：保存密码并进入主界面"""
        self.logged_in = True
        self.config.set_initial_password(password)
        self.login_window.destroy()

    def _run_main(self):
        """运行主窗口"""
        # 先启动托盘线程，再创建主窗口（pystray 需要主线程之外运行）
        self.tray = TrayManager(
            app_ref_getter=lambda: getattr(self, "app", None),
            lock_func=self._tray_lock,
        )
        self.tray.start()

        self.app = WorkbenchApp(self.config)
        # 确保主窗口可见并置顶
        self.app.deiconify()
        self.app.lift()
        # 延迟绑定 <Unmap>，避免启动时 withdraw/deiconify 产生的 <Unmap> 事件误触发托盘隐藏
        self.app.after(500, self._bind_minimize)
        # 注册 QQ 式靠边停靠功能（主窗口创建后才能绑定）
        # 开关读取：app_settings.json 的 auto_dock_enabled 字段
        self.app._dock_state = None
        try:
            self.app._dock_state = install_dock_feature(
                self.app,
                enabled_getter=lambda: self.config.get_auto_dock_enabled(),
            )
        except Exception:
            pass
        # 启动时如果开关关着，立即停住轮询
        try:
            if self.app._dock_state and not self.config.get_auto_dock_enabled():
                self.app._dock_state["enabled"] = False
        except Exception:
            pass
        self.app.mainloop()

        # 主循环结束后，确保托盘也关闭
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass

    def _tray_lock(self):
        """托盘菜单触发的「锁定窗口」：回到主线程执行锁屏"""
        app = self.app
        if app is None:
            return
        # 取消隐藏并置顶
        try:
            app.deiconify()
            app.lift()
            app.focus_force()
            app.attributes("-topmost", True)
            app.after(200, lambda: app.attributes("-topmost", False))
        except Exception:
            pass
        # 触发锁屏
        try:
            app._show_lock_screen()
        except Exception:
            pass

    def _bind_minimize(self):
        """延迟绑定最小化事件，确保启动期间的 <Unmap> 不被捕获"""
        try:
            self.app.bind("<Unmap>", lambda e: self._on_minimize())
        except Exception:
            pass

    def _on_minimize(self):
        """最小化事件：可选隐藏到托盘"""
        app = self.app
        if app is None:
            return
        if not getattr(app, "_minimize_to_tray", False):
            return
        try:
            state = app.state()
            if state == "iconic":
                app.withdraw()
        except Exception:
            pass


# Windows 单实例锁：基于命名 Mutex 防止多开导致的数据冲突
_single_instance_mutex = None  # 全局引用，防止 GC 释放 Mutex




def ensure_single_instance():
    """确保只运行一个实例。返回 True 表示是首个实例，False 表示已有实例在运行。"""
    global _single_instance_mutex
    if sys.platform != "win32":
        return True  # 非 Windows 不做单实例限制
    try:
        import ctypes
        from ctypes import wintypes
        ERROR_ALREADY_EXISTS = 183
        # Mutex 名建议加 GUID 后缀避免与其他程序冲突
        mutex_name = "ZhixingWorkbench_SingleInstance_A7F3E2B1"
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        last_err = ctypes.get_last_error()
        if last_err == ERROR_ALREADY_EXISTS:
            # 已有实例运行，激活已有窗口
            _activate_existing_window()
            return False
        # 保存 Mutex 引用，避免对象被 GC 后 Mutex 释放
        _single_instance_mutex = handle
        return True
    except Exception:
        # 任何异常都放行（最坏情况是多开，但比无法启动好）
        return True


def _activate_existing_window():
    """找到已运行的知行工作台窗口并激活到前台。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        # FindWindowW(class_name, window_name) — class_name 用 Tk 的 "Tk" 类
        # 标题可能是 "知行工作台 - 登录" 或 "知行工作台 - v{APP_VERSION}"
        titles_to_try = [
            f"{APP_NAME} - v{APP_VERSION}",
            f"{APP_NAME} - 登录",
            APP_NAME,
        ]
        hwnd = None
        for title in titles_to_try:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                break
        if not hwnd:
            # 找不到窗口（可能被托盘隐藏），提示用户从托盘恢复
            from tkinter import Tk, messagebox
            r = Tk(); r.withdraw()
            messagebox.showinfo(APP_NAME, f"{APP_NAME} 已经在运行中。\n\n请检查系统托盘（右下角）的图标，双击即可恢复窗口。")
            r.destroy()
            return
        # 恢复最小化/隐藏的窗口
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        # 置顶
        user32.SetForegroundWindow(hwnd)
    except Exception:
        # 静默失败，不影响主流程
        pass


def resource_path(relative_path):
    """获取资源路径（兼容PyInstaller打包）"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def _make_app_icon_pil(size=(64, 64)):
    """v2.5.4 应用级图标的**唯一真源**
    任务栏 / 标题栏 / Explorer / 快捷方式 全都基于此函数 + ICO 文件绘制。
    在任意 N x N 像素尺寸下重新栅格化：蓝圆角矩形 + 居中白色「Z」字母
    （与快捷方式默认占位图标、托盘图标同款 Z 字符样式）
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = int(size[0]), int(size[1])
        if W < 8 or H < 8:
            W, H = 16, 16
        img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # 背景蓝圆角矩形 — 内边距按尺寸自适应
        pad = max(2, W // 12)
        radius = max(3, W // 4)
        draw.rounded_rectangle(
            (pad, pad, W - pad, H - pad),
            radius=radius,
            fill=(59, 142, 224, 255),
        )

        # 字体大小：按画布宽度的 0.7 倍缩放
        font_size = max(8, int(W * 0.66))
        # 字体选择：Z 是 ASCII 字符，优先 Arial（与快捷方式默认图标一致），雅黑兜底
        font_candidates = [
            ("arial.ttf", font_size),
            ("arialbd.ttf", font_size),
            ("C:\\Windows\\Fonts\\arial.ttf", font_size),
            ("C:\\Windows\\Fonts\\arialbd.ttf", font_size),
            ("msyhbd.ttc", font_size),
            ("msyh.ttc", font_size),
            ("simhei.ttf", font_size),
        ]
        font = None
        last_err = None
        for fpath, fsz in font_candidates:
            try:
                font = ImageFont.truetype(fpath, fsz)
                break
            except Exception as _e:
                last_err = _e
                font = None
        if font is None:
            # 真的所有字体都失败了（罕见）——绘制白色居中十字占位
            cx, cy = W // 2, H // 2
            l = max(2, W // 4)
            thick = max(1, W // 12)
            draw.rectangle([cx - l, cy - thick // 2, cx + l, cy + thick // 2], fill=(255, 255, 255, 255))
            draw.rectangle([cx - thick // 2, cy - l, cx + thick // 2, cy + l], fill=(255, 255, 255, 255))
            return img

        # 计算「知」字精确边界并严格居中
        text = "Z"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ox, oy = bbox[0], bbox[1]  # 字形原点偏移
        except Exception:
            tw, th = int(W * 0.7), int(H * 0.7)
            ox, oy = 0, 0
        # 真·居中：画布中心 - (字形宽高)/2 - 字形偏移
        tx = (W - tw) / 2 - ox
        ty = (H - th) / 2 - oy
        draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)
        return img
    except Exception as e:
        # 任何异常：至少返回蓝底白方块兜底，绝不让其它字符（Z/乱码）出现
        try:
            from PIL import Image, ImageDraw
            W, H = max(16, int(size[0])), max(16, int(size[1]))
            img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            p = max(2, W // 12)
            d.rounded_rectangle((p, p, W - p, H - p), radius=max(3, W // 4), fill=(59, 142, 224, 255))
            return img
        except Exception:
            return None


def _get_app_ico_path():
    """v2.5.5 生成多尺寸应用 ICO（任务栏/标题栏 Win32 LoadImageW 使用）
    策略：**永远动态生成**（与 load_tray_image / _make_app_icon_pil 同源，
    保证 Explorer ico、任务栏、标题栏、托盘 四处字形/颜色/圆角 100% 统一）。
    缓存文件名带版本号（zhixing_app_v255.ico），避免旧版本（v241/v240 「知」字）
    缓存命中导致窗口/任务栏仍显示旧图标。启动时自动清理旧版本缓存。
    仅在动态生成失败（极端，PIL 坏了）时，才兜底用随包 app_icon.ico。
    """
    import tempfile
    # 清旧版本缓存（v241/v240 「知」字版）
    _cleanup_old_icon_caches()
    cache = getattr(_get_app_ico_path, "_cache", None)
    if cache and os.path.exists(cache):
        return cache
    try:
        master = _make_app_icon_pil(size=(256, 256))
        if master is None:
            raise RuntimeError("_make_app_icon_pil 返回 None")
        tmp_dir = tempfile.gettempdir()
        # v2.5.5 缓存文件名带版本号，避免旧缓存命中
        out = os.path.join(tmp_dir, "zhixing_app_v255.ico")
        master.save(
            out,
            format="ICO",
            sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                   (48, 48), (64, 64), (96, 96), (128, 128), (256, 256)],
        )
        _get_app_ico_path._cache = out
        return out
    except Exception:
        # 终极兜底：随包 app_icon.ico（构建期已用统一代码重写过，也一致）
        bundled = resource_path("app_icon.ico")
        if os.path.exists(bundled):
            _get_app_ico_path._cache = bundled
            return bundled
        return bundled  # 不存在也返回字符串，由调用者判断


def _cleanup_old_icon_caches():
    """v2.5.5 删除 %TEMP% 下 v241/v240 等旧版本图标缓存，
    防止窗口/任务栏仍命中旧「知」字图标。"""
    import tempfile, glob
    tmp = tempfile.gettempdir()
    for pat in ["zhixing_app_v24*.ico", "zhixing_app_v23*.ico", "zhixing_app_v22*.ico",
                "zhixing_app_v20*.ico", "zhixing_app_v21*.ico"]:
        for f in glob.glob(os.path.join(tmp, pat)):
            try: os.remove(f)
            except Exception: pass


def set_window_icon(window):
    """v2.5.5 设置窗口图标（任务栏 + 标题栏）
    三路策略，保证 Z 字符图标必定生效：
    ① Win32 SendMessageW + WM_SETICON（主路径，64×32）
    ② Tk wm_iconphoto（用 PIL 生成 64/32 PhotoImage 兜底）
    ③ Tk wm_iconbitmap（.ico 文件路径兜底）
    任一成功即可，任务栏/标题栏都能看到 Z 字符图标。"""
    ico_path = _get_app_ico_path()

    # ① Win32 WM_SETICON 主路径
    if ico_path and os.path.exists(ico_path):
        try:
            import ctypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.LoadImageW.restype = ctypes.c_void_p
            user32.LoadImageW.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ]
            # LR_LOADFROMFILE = 0x10, IMAGE_ICON = 1
            hIconBig = user32.LoadImageW(None, ico_path, 1, 64, 64, 0x10)
            hIconSmall = user32.LoadImageW(None, ico_path, 1, 32, 32, 0x10)
            hwnd = window.winfo_id()
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.SendMessageW.argtypes = [
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
            ]
            # WM_SETICON=0x0080 ; ICON_BIG=1（任务栏） ; ICON_SMALL=0（标题栏）
            if hIconBig:
                user32.SendMessageW(hwnd, 0x0080, 1, hIconBig)
            if hIconSmall:
                user32.SendMessageW(hwnd, 0x0080, 0, hIconSmall)
            window._win32_icon_handles = (hIconBig, hIconSmall)
        except Exception:
            pass

    # ② Tk wm_iconphoto 兜底（用 PIL 生成 PhotoImage）
    try:
        from PIL import Image, ImageTk
        big = _make_app_icon_pil(size=(64, 64))
        small = _make_app_icon_pil(size=(32, 32))
        if big and small:
            try:
                tk_big = ImageTk.PhotoImage(big)
                tk_small = ImageTk.PhotoImage(small)
                window.wm_iconphoto(True, tk_big, tk_small)
                window._tk_photo_icons = (tk_big, tk_small)  # 防止 GC
            except Exception:
                pass
    except Exception:
        pass

    # ③ Tk wm_iconbitmap 最后兜底
    if ico_path and os.path.exists(ico_path):
        try:
            window.wm_iconbitmap(ico_path)
        except Exception:
            pass


def _make_z_icon_pil(size=(32, 32)):
    """v2.5.3 绘制蓝圆角方块 + 白色 Z 字母（与快捷方式默认占位图标同款样式）
    用于系统托盘：与 IconExtractor._default_icon 视觉一致。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = int(size[0]), int(size[1])
        if W < 8 or H < 8:
            W, H = 16, 16
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # 蓝色圆角背景（与 _default_icon 同色 #3B8EE0）
        pad = max(2, W // 24)
        radius = max(3, W // 5)
        draw.rounded_rectangle([pad, pad, W - pad, H - pad], radius=radius,
                               fill=(59, 142, 224, 255))
        # 白色 Z 字母（优先 Arial，按尺寸缩放）
        font_size = max(8, int(W * 0.58))
        font = None
        for fpath in ["arial.ttf", "C:\\Windows\\Fonts\\arial.ttf",
                      "arialbd.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"]:
            try:
                font = ImageFont.truetype(fpath, font_size)
                break
            except Exception:
                pass
        try:
            bbox = draw.textbbox((0, 0), "Z", font=font)
            tw, th, ox, oy = bbox[2]-bbox[0], bbox[3]-bbox[1], bbox[0], bbox[1]
        except Exception:
            tw, th, ox, oy = int(W*0.5), int(H*0.6), 0, 0
        draw.text(((W - tw) / 2 - ox, (H - th) / 2 - oy), "Z",
                  fill=(255, 255, 255, 255), font=font)
        return img
    except Exception:
        return None


def load_tray_image():
    """v2.5.3 托盘图标 — 蓝圆角方块 + 白色 Z 字母
    与快捷方式默认占位图标（IconExtractor._default_icon）同款样式，
    使用系统托盘标准 32x32 尺寸绘制。"""
    img = _make_z_icon_pil(size=(32, 32))
    if img is not None:
        return img
    # 终极兜底：简单蓝方块（无 Z）
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((3, 3, 29, 29), radius=6, fill=(59, 142, 224, 255))
        return img
    except Exception:
        return None


class TrayManager:
    """系统托盘管理器：独立线程运行 pystray，通过 after 回调操作主线程 UI"""

    def __init__(self, app_ref_getter, lock_func):
        """
        app_ref_getter: 无参函数，返回 WorkbenchApp 实例（可能为 None，未创建）
        lock_func: 无参函数，触发锁定窗口
        """
        self._get_app = app_ref_getter
        self._lock_func = lock_func
        self._icon = None
        self._thread = None
        self._exiting = False
        self._tray_image = load_tray_image()

    # ---------------------- 菜单动作 ----------------------
    def _show_window(self, icon=None, item=None):
        """托盘菜单：显示主窗口"""
        app = self._get_app()
        if app is None:
            return
        try:
            app.after(0, self._show_window_ui)
        except Exception:
            pass

    def _show_window_ui(self):
        app = self._get_app()
        if app is None:
            return
        try:
            app.deiconify()
            app.lift()
            app.focus_force()
            app.attributes("-topmost", True)
            app.after(200, lambda: app.attributes("-topmost", False))
        except Exception:
            pass

    def _lock_window(self, icon=None, item=None):
        """托盘菜单：锁定窗口"""
        app = self._get_app()
        if app is None:
            return
        try:
            app.after(0, self._lock_func)
        except Exception:
            pass

    def _hide_window(self, icon=None, item=None):
        """托盘菜单：隐藏到托盘"""
        app = self._get_app()
        if app is None:
            return
        try:
            app.after(0, self._hide_window_ui)
        except Exception:
            pass

    def _hide_window_ui(self):
        app = self._get_app()
        if app is None:
            return
        try:
            app.withdraw()
        except Exception:
            pass

    def _quit_app(self, icon=None, item=None):
        """托盘菜单：退出程序"""
        self._exiting = True
        app = self._get_app()
        if app is not None:
            try:
                app.after(0, self._quit_app_ui)
            except Exception:
                # Tk 可能已销毁，直接退出进程
                import os, sys
                os._exit(0)
        else:
            import os, sys
            os._exit(0)

    def _quit_app_ui(self):
        app = self._get_app()
        if app is None:
            import os
            os._exit(0)
            return
        # v2.5.0：退出前强制同步落盘，防止后台防抖保存线程被硬终止丢数据
        try:
            if hasattr(app, "config") and app.config is not None:
                app.config.flush()
        except Exception:
            pass
        # v3.1 退出前保存窗口大小与位置（仅正常展开态，排除停靠/最小化/隐藏态）
        try:
            if app is not None and app.winfo_exists():
                # 只保存可见且正常展开的状态：withdrawn/iconified 直接跳过
                _state = app.state()
                if _state in ("normal", "zoomed"):
                    try:
                        W = app.winfo_width()
                        H = app.winfo_height()
                        X = app.winfo_x()
                        Y = app.winfo_y()
                        # 排除停靠态（宽度只有 PEEK_PX 约 6~14px）或尺寸不足 minsize
                        if W >= 1100 and H >= 840:
                            app.config.set_window_geometry(W, H, X, Y)
                            # 立即落盘，避免 destroy 时后台线程丢数据
                            app.config.flush()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            # 停止托盘
            self.stop()
        except Exception:
            pass
        try:
            # 真正关闭窗口，触发 destroy
            app._allow_destroy = True
            app.destroy()
        except Exception:
            import os
            os._exit(0)

    def _on_double_click(self, icon, item):
        """双击托盘图标：切换显示/隐藏"""
        app = self._get_app()
        if app is None:
            return
        try:
            visible = bool(app.winfo_viewable())
            if visible:
                self._hide_window()
            else:
                self._show_window()
        except Exception:
            self._show_window()

    # ---------------------- 生命周期 ----------------------
    def start(self):
        """启动托盘线程（pystray 必须在后台线程运行，否则阻塞 Tk 主循环）"""
        try:
            import pystray
            from pystray import Menu, MenuItem
        except Exception:
            print("[Tray] pystray unavailable, tray disabled")
            return
        if self._tray_image is None:
            print("[Tray] tray image unavailable, tray disabled")
            return

        menu = Menu(
            MenuItem("显示主窗口", self._show_window, default=True),
            MenuItem("隐藏到托盘", self._hide_window),
            MenuItem("锁定窗口", self._lock_window),
            Menu.SEPARATOR,
            MenuItem("退出程序", self._quit_app),
        )
        self._icon = pystray.Icon(
            "zhixing_workbench",
            self._tray_image,
            f"{APP_NAME} v{APP_VERSION}",
            menu,
        )

        def _run():
            try:
                self._icon.run()
            except Exception:
                pass

        import threading
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        """停止托盘线程（退出前清理）"""
        try:
            if self._icon:
                self._icon.stop()
        except Exception:
            pass
        self._icon = None
        self._thread = None


# --- QQ式靠边停靠功能 ---
def install_dock_feature(root, enabled_getter=None):
    """QQ 式靠边自动收纳（v2 可靠版）
    行为：把窗口拖到屏幕左/右边缘 ≤12px → 停住后鼠标离开窗口 400ms
         → 窗口宽度收缩成 6px 一条边贴在屏幕边缘；
         鼠标碰到这条边（或边缘 24px 内）→ 200ms 后展开；
         展开后若把窗口拖离边缘（x > 18px 或 x+w < sw-18px）
         → 取消停靠。
    enabled_getter: 每次轮询读取，若返回 False 则不做任何停靠动作，
                    已收起的会在关闭瞬间被主 UI 代码复位。
    """
    if enabled_getter is None:
        enabled_getter = lambda: True

    state = {
        "docked_side": None,    # "left" / "right" / None
        "collapsed": False,
        "normal_geom": None,    # 收起前/最近一次正常尺寸 (x,y,w,h)
        "last_move_tick": 0,    # 位置稳定计数
        "enabled": True,        # UI 可直接改这个字段快速开关
        "last_x": -99999,
        "last_y": -99999,
    }

    EDGE_PX = 14           # 距边缘多少像素判定停靠
    PEEK_PX = 6            # 收起后窗口宽度（露出来的一条边）
    UNFOLD_DELAY_MS = 180  # 鼠标停在收起边多久展开
    FOLD_DELAY_MS = 400    # 鼠标离开窗口多久收起
    UNDOCK_PX = 28         # 展开后距边缘多少像素算"用户主动拖离"

    _unfold_timer = [None]
    _fold_timer = [None]

    def sw_sh():
        return root.winfo_screenwidth(), root.winfo_screenheight()

    def geom():
        # update_idletasks 保证值是最新的（避免 Tk 几何缓存过期）
        try:
            root.update_idletasks()
        except Exception:
            pass
        return (root.winfo_x(), root.winfo_y(),
                root.winfo_width(), root.winfo_height())

    def _cancel(which):
        if which[0] is not None:
            try:
                root.after_cancel(which[0])
            except Exception:
                pass
            which[0] = None

    def do_collapse():
        if state["collapsed"] or not state["docked_side"]:
            return
        x, y, _w, h = geom()
        # 记录正常几何（展开时用），注意不能在已经 collapsed 时记
        state["normal_geom"] = (x, y, _w, h)
        sw, _sh = sw_sh()
        side = state["docked_side"]
        state["collapsed"] = True
        try:
            if side == "left":
                root.geometry(f"{PEEK_PX}x{h}+{0}+{y}")
            elif side == "right":
                root.geometry(f"{PEEK_PX}x{h}+{sw - PEEK_PX}+{y}")
            root.update_idletasks()
        except Exception:
            pass

    def do_expand():
        if not state["collapsed"]:
            return
        if not state["normal_geom"]:
            # 没记录就取当前位置展开为默认尺寸
            state["collapsed"] = False
            return
        x, y, w, h = state["normal_geom"]
        state["collapsed"] = False
        try:
            root.geometry(f"{w}x{h}+{x}+{y}")
            root.update_idletasks()
        except Exception:
            pass

    def poll():
        # 开关：外部两种方式（getter 回调 / state.enabled 字段）
        try:
            if not enabled_getter() or not state["enabled"]:
                root.after(220, poll)
                return
        except Exception:
            pass

        # 跳过最小化/图标化
        try:
            if root.state() == "iconic" or root.state() == "zoomed":
                root.after(220, poll)
                return
        except Exception:
            pass

        try:
            sw, _sh = sw_sh()
            mx = root.winfo_pointerx()
            my = root.winfo_pointery()
            x, y, w, h = geom()

            # 刚移动过的位置不稳定：等 1 轮
            moved = (x != state["last_x"]) or (y != state["last_y"])
            state["last_x"], state["last_y"] = x, y
            if moved:
                state["last_move_tick"] = 0
            else:
                state["last_move_tick"] += 1

            if not state["collapsed"]:
                # 正常状态：检测靠近边缘 + 稳定后 → 鼠标离开就收
                at_left  = x <= EDGE_PX
                at_right = (x + w) >= (sw - EDGE_PX)

                if at_left:
                    state["docked_side"] = "left"
                elif at_right:
                    state["docked_side"] = "right"
                else:
                    # 离边缘很远了
                    if state["docked_side"] is not None:
                        far = x > UNDOCK_PX and (x + w) < (sw - UNDOCK_PX)
                        if far:
                            state["docked_side"] = None
                            state["normal_geom"] = None
                    _cancel(_fold_timer)

                # 已停靠边 & 位置已经稳定 & 鼠标真不在窗口内 → 延迟收起
                if state["docked_side"] is not None and state["last_move_tick"] >= 1:
                    inside_win = (x <= mx <= x + w) and (y <= my <= y + h)
                    if not inside_win:
                        if _fold_timer[0] is None:
                            _fold_timer[0] = root.after(FOLD_DELAY_MS, do_collapse)
                    else:
                        _cancel(_fold_timer)

            else:
                # 收起状态：鼠标移到屏幕边缘附近 → 展开
                side = state["docked_side"]
                if side == "left":
                    zone = PEEK_PX + 22  # 左边缘 28px 内
                    triggered = mx <= zone
                elif side == "right":
                    zone = sw - PEEK_PX - 22
                    triggered = mx >= zone
                else:
                    triggered = False

                if triggered:
                    # 也允许鼠标正好落在窄条窗口范围内
                    inside_win = (x <= mx <= x + w) and (y <= my <= y + h)
                    if inside_win or triggered:
                        if _unfold_timer[0] is None:
                            _unfold_timer[0] = root.after(UNFOLD_DELAY_MS, do_expand)
                else:
                    _cancel(_unfold_timer)
                    # 收起后若鼠标还挨着窗口就算离开窗口？不需要，等展开再说

        except Exception:
            import traceback as _tb
            try:
                print("[dock] poll error:", _tb.format_exc(limit=1))
            except Exception:
                pass

        root.after(160, poll)

    poll()
    return state



if __name__ == "__main__":
    # 单实例检查：阻止多开导致数据冲突
    if not ensure_single_instance():
        sys.exit(0)  # 已有实例运行，本进程直接退出
    try:
        app = Application()
        # Auto-login mode for screenshots/testing — 仅源码运行可用，打包后禁用（避免隐藏调试入口）
        if "--auto-login" in sys.argv and not getattr(sys, "frozen", False):
            app._auto_login = True
        app.run()
    except Exception as e:
        # 错误日志写入文件，方便排查
        import traceback
        log_path = get_base_dir() / "error.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"知行工作台错误日志\n")
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"版本: {APP_VERSION}\n")
            f.write(f"错误:\n{traceback.format_exc()}\n")
        from tkinter import messagebox
        messagebox.showerror(
            "知行工作台 - 错误",
            f"应用启动失败：\n\n{e}\n\n"
            f"错误日志已保存到：\n{log_path}",
        )
