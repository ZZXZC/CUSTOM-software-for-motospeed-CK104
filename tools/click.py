"""Send real mouse/keyboard input to the vendor app (or anything else).

Coordinate systems:
    --client x y   x/y relative to the CK104 window's client area (0,0 = its
                   top-left), converted via ClientToScreen. This is what the
                   screenshot maps to.
    --screen x y   absolute screen coordinates.

Examples:
    python tools/click.py --client 941 560          # press "Apply"
    python tools/click.py --client 190 267          # open the Light combo
    python tools/click.py --client 190 267 --list   # print items instead
    python tools/click.py --client 41 459           # pick the colour swatch
    python tools/click.py --key ESC
"""

import argparse
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
g32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# Common virtual-key codes for convenience.
KEYS = {
    "ESC": 0x1B, "TAB": 0x09, "ENTER": 0x0D, "SPACE": 0x20,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
    "DELETE": 0x2E, "BACKSPACE": 0x08, "HOME": 0x24, "END": 0x23,
    "PGUP": 0x21, "PGDN": 0x22,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t)]


class INPUTUNION(ctypes.Structure):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]


user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SW_RESTORE = 9
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040

# Where we park the target so client->screen maths is predictable.
# The dialog is exactly 1000x640 with no non-client frame, and the work
# area is 1280x984, so this keeps the whole window on screen.
PARK_X, PARK_Y = 100, 60
WORK_W, WORK_H = 1280, 984


def find_ck104() -> int:
    h = user32.FindWindowW(None, "CK104 Keyboard")
    if not h:
        raise SystemExit("CK104 Keyboard window not found")
    return h


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def pin_on_top(hwnd: int) -> None:
    """Force the target above every other window and park it on screen.

    Two separate problems this solves:

    1. Z-order.  Without this the click lands on whatever is on top --
       usually the agent's own editor window -- and silently does nothing.
    2. Position.  ShowWindow(SW_RESTORE) was making this dialog jump around
       (it ended up at y=851, i.e. mostly below the 1024px screen), so we
       move it explicitly instead of asking it to restore itself.
    """
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    me = kernel32.GetCurrentThreadId()
    attached = user32.AttachThreadInput(me, tid, True)

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    # TOPMOST keeps it above us even while our own windows repaint.
    user32.SetWindowPos(hwnd, HWND_TOPMOST, PARK_X, PARK_Y, 0, 0,
                        SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    if attached:
        user32.AttachThreadInput(me, tid, False)
    time.sleep(0.3)

    l, t, r, b = window_rect(hwnd)
    if not (0 <= l and 0 <= t and r <= WORK_W and b <= WORK_H):
        raise SystemExit(f"window still off-screen: ({l},{t})-({r},{b})")


def client_to_screen(hwnd: int, x: int, y: int) -> tuple[int, int]:
    pt = wintypes.POINT(x, y)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        raise SystemExit("ClientToScreen failed")
    return pt.x, pt.y


def send_mouse(flags, data=0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dwFlags = flags
    inp.union.mi.mouseData = data
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def click(sx: int, sy: int, delay: float = 0.04):
    user32.SetCursorPos(sx, sy)
    time.sleep(delay)
    send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(delay)
    send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(0.12)


def key_down_up(vk: int):
    send_key(vk, True)
    time.sleep(0.03)
    send_key(vk, False)


def send_key(vk: int, down: bool):
    inp = INPUT()
    inp.type = 1  # INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = 0 if down else 0x0002  # KEYEVENTF_KEYUP
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def type_text(text: str):
    for ch in text:
        if ch == "\n":
            key_down_up(0x0D)
        elif ch == "\t":
            key_down_up(0x09)
        else:
            vk = ord(ch.upper()) if ch.isalpha() else ord(ch)
            key_down_up(vk)
        time.sleep(0.02)


def dump_combobox(hwnd: int, sx: int, sy: int):
    """Open a ComboBox and print its item strings (needs a message pump)."""
    # We can't read a foreign combobox's list directly without UIA, so we
    # simply report where it is and let the caller screenshot afterwards.
    print(f"combobox at screen ({sx},{sy})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", nargs=2, type=int, metavar=("X", "Y"))
    ap.add_argument("--screen", nargs=2, type=int, metavar=("X", "Y"))
    ap.add_argument("--key", type=str)
    ap.add_argument("--type", type=str, dest="text")
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--wait", type=float, default=0.4, help="seconds to wait after input")
    ap.add_argument("--pin-only", action="store_true",
                    help="just bring the app to the top and exit")
    a = ap.parse_args()

    hwnd = find_ck104()
    pin_on_top(hwnd)
    if a.pin_only:
        print(f"pinned hwnd=0x{hwnd:X}")
        return 0

    if a.key:
        vk = KEYS.get(a.key.upper())
        if vk is None and len(a.key) == 1:
            vk = ord(a.key.upper())
        if vk is None:
            raise SystemExit(f"unknown key {a.key!r}")
        key_down_up(vk)
    elif a.text:
        type_text(a.text)

    if a.client or a.screen:
        if a.client:
            sx, sy = client_to_screen(hwnd, a.client[0], a.client[1])
        else:
            sx, sy = a.screen
        # Refuse to click into the void: an off-screen point just gets
        # clamped by SetCursorPos and lands on whatever is there.
        if not (0 <= sx < WORK_W and 0 <= sy < WORK_H):
            raise SystemExit(f"click point ({sx},{sy}) is off the {WORK_W}x{WORK_H} screen")
        click(sx, sy)
        if a.double:
            time.sleep(0.1)
            click(sx, sy)
        print(f"clicked screen ({sx},{sy})")

    time.sleep(a.wait)
    return 0


if __name__ == "__main__":
    sys.exit(main())
