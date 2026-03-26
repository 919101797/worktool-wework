from __future__ import annotations

import logging
from typing import Any

from AppKit import NSRunningApplication, NSWorkspace  # type: ignore[import-untyped]
from ApplicationServices import AXUIElementCreateApplication, kAXErrorSuccess  # type: ignore[import-untyped]
import ApplicationServices as AppSvc  # type: ignore[import-untyped]

from ax_core import (
    ax_attr,
    ax_rect,
    collect_row_texts,
    current_conversation,
    find_bottom_input,
    get_rows,
)
from ax_core.input import (
    clear_and_type,
    key_stroke,
    restore_clipboard,
    sleep_ms,
)

logger = logging.getLogger(__name__)


class WeChatService:
    def __init__(self, delay_activate=700, delay_send=1200):
        self.delay_activate = delay_activate
        self.delay_send = delay_send

    def _find_app(self) -> NSRunningApplication | None:
        workspace = NSWorkspace.sharedWorkspace()
        running_apps = workspace.runningApplications()

        for app in running_apps:
            bundle_id = app.bundleIdentifier() or ""
            name = app.localizedName() or ""
            if bundle_id == "com.tencent.xinWeChat" or name in ["微信", "WeChat"]:
                return app
        return None

    def _app_element(self) -> Any | None:
        app = self._find_app()
        if app is None:
            return None
        return AppSvc.AXUIElementCreateApplication(app.processIdentifier())

    def _focused_ui_element(self) -> Any | None:
        app_el = self._app_element()
        if app_el is None:
            return None
        return ax_attr(app_el, "AXFocusedUIElement")

    def _get_main_window(self) -> Any | None:
        app_el = self._app_element()
        if app_el is None:
            return None
        focused = ax_attr(app_el, "AXFocusedWindow")
        if focused is not None:
            return focused
        main = ax_attr(app_el, "AXMainWindow")
        if main is not None:
            return main
        windows = ax_attr(app_el, "AXWindows", [])
        return windows[0] if windows else None

    def _activate(self) -> bool:
        app = self._find_app()
        if app is None:
            return False
        app.activateWithOptions_(1 << 1)
        sleep_ms(self.delay_activate)
        return self._get_main_window() is not None

    def _ensure_ready(self) -> dict:
        if not self._activate():
            return {"ok": False, "message": "未找到应用程序，请先打开"}
        win = None
        for _ in range(6):
            win = self._get_main_window()
            if win is not None:
                return {"ok": True, "win": win}
            sleep_ms(300)
        return {"ok": False, "message": "未拿到主窗口，请点击聊天窗口后重试"}

    def _set_value(self, element: Any, value: str) -> bool:
        if element is None:
            return False
        try:
            err = AppSvc.AXUIElementSetAttributeValue(element, "AXValue", value)
        except Exception:
            return False
        return err == kAXErrorSuccess

    def _reset_ui_state(self) -> None:
        for _ in range(3):
            key_stroke("escape")
            sleep_ms(200)
        self._activate()
        sleep_ms(250)

    def _open_search_input(self) -> dict:
        self._reset_ui_state()
        key_stroke("f", ["cmd"])
        sleep_ms(700)
        search = self._focused_ui_element()
        if search is None:
            return {"ok": False, "message": "未拿到搜索框焦点"}
        role = str(ax_attr(search, "AXRole", "") or "")
        rect = ax_rect(search)
        if role != "AXTextField" or rect is None:
            return {"ok": False, "message": "搜索框焦点异常"}
        return {"ok": True, "search": search, "rect": rect}

    def _search_popup_window(self) -> Any | None:
        app_el = self._app_element()
        if app_el is None:
            return None
        for win in ax_attr(app_el, "AXWindows", []) or []:
            if str(ax_attr(win, "AXSubrole", "") or "") == "AXDialog":
                return win
        return None

    def _search_result_table(self) -> Any | None:
        popup = self._search_popup_window()
        if popup is None:
            return None
        children = ax_attr(popup, "AXChildren", []) or []
        scroll = next((child for child in children if str(ax_attr(child, "AXRole", "") or "") == "AXScrollArea"), None)
        if scroll is None:
            return None
        contents = ax_attr(scroll, "AXContents", []) or []
        table = next((child for child in contents if str(ax_attr(child, "AXRole", "") or "") == "AXTable"), None)
        if table is not None:
            return table
        direct_children = ax_attr(scroll, "AXChildren", []) or []
        return next((child for child in direct_children if str(ax_attr(child, "AXRole", "") or "") == "AXTable"), None)

    def _find_search_result_row(self, title: str) -> tuple[Any | None, list[str]]:
        table = self._search_result_table()
        if table is None:
            return None, []
        rows = ax_attr(table, "AXRows", []) or []
        for row in rows:
            texts = collect_row_texts(row)
            if texts and texts[0] == title:
                return row, texts
        return None, []

    def _confirm_result_row(self, row: Any) -> bool:
        table = ax_attr(row, "AXParent")
        if table is None:
            return False
        try:
            AppSvc.AXUIElementSetAttributeValue(table, "AXSelectedRows", [row])
        except Exception:
            pass
        try:
            AppSvc.AXUIElementSetAttributeValue(row, "AXSelected", True)
        except Exception:
            pass

        for sequence in (("tab", "return"), ("return",)):
            for key in sequence:
                key_stroke(key)
                sleep_ms(220)
            sleep_ms(900)
            if self._search_popup_window() is None:
                return True
        return False

    def _message_editor(self) -> Any | None:
        focused = self._focused_ui_element()
        main = self._get_main_window()
        win_rect = ax_rect(main) if main is not None else None
        focused_rect = ax_rect(focused) if focused is not None else None
        role = str(ax_attr(focused, "AXRole", "") or "") if focused is not None else ""

        if (
            focused is not None
            and role in ("AXTextArea", "AXTextField")
            and focused_rect is not None
            and win_rect is not None
            and focused_rect.y >= int(win_rect.y + win_rect.h * 0.55)
            and focused_rect.w >= 450
        ):
            return focused

        if main is None:
            return None
        return find_bottom_input(main)

    def list_sessions(self, limit: int = 0) -> dict:
        ready = self._ensure_ready()
        if not ready["ok"]:
            return ready
        rows = get_rows(ready["win"])
        if rows is None:
            return {"ok": False, "message": "未找到左侧会话列表"}
        sessions = []
        for i, row in enumerate(rows):
            texts = collect_row_texts(row)
            if texts:
                sessions.append({"index": i + 1, "title": texts[0], "texts": texts})
        if limit > 0:
            sessions = sessions[:limit]
        return {"ok": True, "message": f"共 {len(sessions)} 个会话", "sessions": sessions}

    def get_current_conversation(self) -> dict:
        ready = self._ensure_ready()
        if not ready["ok"]:
            return ready
        title = current_conversation(ready["win"])
        return {"ok": True, "message": "获取成功", "title": title}

    def send_current_chat(self, message: str) -> dict:
        ready = self._ensure_ready()
        if not ready["ok"]:
            return ready

        win = ready["win"]
        active = current_conversation(win) or "未知会话"
        input_el = find_bottom_input(win)
        if input_el is None:
            return {"ok": False, "message": "未找到消息输入框"}

        before = str(ax_attr(input_el, "AXValue", "") or "")
        if before:
            return {"ok": False, "message": "输入框非空", "data": {"before": before}}

        old_clipboard = clear_and_type(input_el, message)
        typed = str(ax_attr(input_el, "AXValue", "") or "")
        if typed != message:
            restore_clipboard(old_clipboard)
            return {"ok": False, "message": "消息写入失败"}

        key_stroke("return")
        sleep_ms(self.delay_send)

        after = str(ax_attr(input_el, "AXValue", "") or "")
        restore_clipboard(old_clipboard)

        return {"ok": True, "message": "已发送消息", "data": {"title": active, "after": after}}

    def send_by_title(self, title: str, message: str) -> dict:
        ready = self._ensure_ready()
        if not ready["ok"]:
            return ready

        opened = self._open_search_input()
        if not opened["ok"]:
            return opened

        search = opened["search"]
        if not self._set_value(search, title):
            return {"ok": False, "message": "搜索词写入失败"}
        sleep_ms(800)

        row, texts = self._find_search_result_row(title)
        if row is None:
            return {"ok": False, "message": f"未找到目标会话: {title}"}
        if not self._confirm_result_row(row):
            return {"ok": False, "message": "纯无障碍确认失败"}

        sleep_ms(900)
        editor = self._message_editor()
        if editor is None:
            return {"ok": False, "message": "未找到消息输入框"}

        if not self._set_value(editor, message):
            return {"ok": False, "message": "消息写入失败"}

        key_stroke("return")
        sleep_ms(900)

        return {"ok": True, "message": f"已向 [{title}] 发送消息", "data": {"title": title}}
