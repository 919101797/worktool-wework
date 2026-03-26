"""
Input Simulation (CGEvent & Pasteboard)
"""

from __future__ import annotations

import math
import time
from typing import Any

import Quartz  # type: ignore[import-untyped]
from AppKit import NSPasteboard, NSStringPboardType  # type: ignore[import-untyped]

from ax_core import Rect, ax_rect


def sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000.0)


def click_at(x: int, y: int) -> None:
    point = Quartz.CGPointMake(x, y)
    event_down = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventLeftMouseDown, point, Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
    sleep_ms(50)
    event_up = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventLeftMouseUp, point, Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)


def click_center(element: Any, y_offset: int | None = None) -> bool:
    rect = ax_rect(element)
    if rect is None:
        return False
    x = math.floor(rect.x + rect.w / 2)
    y = math.floor(rect.y + (y_offset if y_offset is not None else rect.h / 2))
    click_at(x, y)
    return True


_KEY_CODES: dict[str, int] = {
    "return": 0x24,
    "delete": 0x33,
    "escape": 0x35,
    "tab": 0x30,
    "space": 0x31,
    "a": 0x00,
    "c": 0x08,
    "v": 0x09,
    "f": 0x03,
    "x": 0x07,
    "z": 0x06,
}

_MODIFIER_FLAGS: dict[str, int] = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
}


def key_stroke(key: str, modifiers: list[str] | None = None) -> None:
    key_code = _KEY_CODES.get(key.lower())
    if key_code is None:
        raise ValueError(f"Unknown key: {key}")

    flags = 0
    for mod in modifiers or []:
        flag = _MODIFIER_FLAGS.get(mod.lower())
        if flag is not None:
            flags |= flag

    import os
    if key_code == 0x24:
        os.system('osascript -e \'tell application "System Events" to keystroke return\'')
    elif key_code == 0x30:
        os.system('osascript -e \'tell application "System Events" to keystroke tab\'')
    elif key_code == 0x33:
        os.system('osascript -e \'tell application "System Events" to key code 51\'') # delete
    elif key_code == 0x35:
        os.system('osascript -e \'tell application "System Events" to key code 53\'') # escape
    else:
        # Fallback to Quartz since it could be letters
        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        event_down = Quartz.CGEventCreateKeyboardEvent(source, key_code, True)
        if flags:
            Quartz.CGEventSetFlags(event_down, flags)
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, event_down)
        sleep_ms(200)
        event_up = Quartz.CGEventCreateKeyboardEvent(source, key_code, False)
        if flags:
            Quartz.CGEventSetFlags(event_up, flags)
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, event_up)

    sleep_ms(50)


def clipboard_read() -> str | None:
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSStringPboardType)


def clipboard_write(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSStringPboardType)


def clipboard_clear() -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()


def clear_and_type(element: Any, text: str, delay_click: int = 250, delay_type: int = 400) -> str | None:
    old_clipboard = clipboard_read()

    click_center(element, y_offset=30)
    sleep_ms(delay_click)

    key_stroke("a", ["cmd"])
    sleep_ms(100)
    key_stroke("delete")
    sleep_ms(150)

    clipboard_write(text)
    sleep_ms(120)
    key_stroke("v", ["cmd"])
    sleep_ms(delay_type)

    return old_clipboard


def restore_clipboard(old_content: str | None) -> None:
    if old_content is not None:
        clipboard_write(old_content)
    else:
        clipboard_clear()
