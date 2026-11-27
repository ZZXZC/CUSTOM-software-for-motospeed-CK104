"""Diagnose why injected clicks are not reaching the target window.

For a given client coordinate it reports:
  * where ClientToScreen puts it
  * the cursor position after SetCursorPos
  * which window/process WindowFromPoint says owns that pixel
  * the current foreground window
  * whether SendInput reports success
"""

import argparse
import ctypes
import sys
import time
from ctypes import wintypes

import click as C  # reuse the pin/coordinate helpers


def raw_click(flags: int) -> int:
    inp = C.INPUT()
    inp.type = C.INPUT_MOUSE
    inp.union.mi.dwFlags = flags
    return C.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def describe(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    C.user32.GetWindowTextW(hwnd, buf, 512)
    cls = ctypes.create_unicode_buffer(256)
    C.user32.GetClassNameW(hwnd, cls, 256)
    out = wintypes.DWORD()
    C.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(out))
    return (f"hwnd=0x{hwnd:X} pid={out.value} "
            f"class={cls.value!r} title={buf.value!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", nargs=2, type=int, required=True)
    a = ap.parse_args()

    hwnd = C.find_ck104()
    C.pin_on_top(hwnd)

    sx, sy = C.client_to_screen(hwnd, a.client[0], a.client[1])
    print(f"client {tuple(a.client)} -> screen ({sx},{sy})")

    if not C.user32.SetCursorPos(sx, sy):
        print(f"SetCursorPos FAILED err={ctypes.get_last_error()}")
    time.sleep(0.25)

    pt = wintypes.POINT()
    C.user32.GetCursorPos(ctypes.byref(pt))
    print(f"cursor now at ({pt.x},{pt.y})")

    under = C.user32.WindowFromPoint(wintypes.POINT(sx, sy))
    if under:
        root = C.user32.GetAncestor(under, 2) or under  # GA_ROOT
        print(f"under cursor : {describe(root)}")
        print(f"  is target  : {root == hwnd}")

    fg = C.user32.GetForegroundWindow()
    print(f"foreground   : {describe(fg) if fg else 'none'}")
    print(f"  is target  : {fg == hwnd}")

    print(f"target enabled : {bool(C.user32.IsWindowEnabled(hwnd))} "
          f"(False = a modal dialog owns it, clicks are swallowed)")
    print(f"target visible : {bool(C.user32.IsWindowVisible(hwnd))}")
    print(f"target topmost : {bool(C.user32.GetWindowLongW(hwnd, -8) & 0x8)}")
    print(f"target style   : 0x{C.user32.GetWindowLongW(hwnd, -16):08X}")

    n_down = raw_click(C.MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.05)
    n_up = raw_click(C.MOUSEEVENTF_LEFTUP)
    print(f"SendInput down/up: {n_down}/{n_up} "
          f"(0 = blocked, err={ctypes.get_last_error()})")

    time.sleep(0.5)
    C.user32.GetCursorPos(ctypes.byref(pt))
    print(f"cursor after click: ({pt.x},{pt.y})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
