"""Capture a window to PNG so the UI can be inspected.

Usage:
    python tools/snap.py                 # main 'CK104 Keyboard' window
    python tools/snap.py --pid 13996
    python tools/snap.py --out shot.png
"""

import argparse
import ctypes
import sys
from ctypes import wintypes

import PIL.Image  # noqa: F401  (fail early if Pillow is missing)

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = wintypes.HDC
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int,
                         wintypes.DWORD]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                            wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
PRF_CLIENT = 0x00000004
PRF_CHILDREN = 0x00000010
PRF_OWNED = 0x00000020
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def find_window(title: str, pid: int | None = None) -> int:
    if pid is None:
        h = user32.FindWindowW(None, title)
        if not h:
            raise SystemExit(f"window {title!r} not found")
        return h
    # walk top-level windows and match on pid
    result = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(out))
        if out.value == pid and user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, buf, 512)
            if buf.value:
                result.append((h, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    if not result:
        raise SystemExit(f"no visible window for pid {pid}")
    return result[0][0]


def capture(hwnd: int, out: str, use_screen: bool = True) -> None:
    if use_screen:
        # Put the target on top, otherwise the screen grab records whatever
        # happens to be covering it.
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(hwnd)
        import time
        time.sleep(0.35)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise SystemExit("degenerate window rect")

    if use_screen:
        # A plain screen grab is the most faithful option: it includes the
        # composited background image that PrintWindow often misses.
        screen_dc = user32.GetDC(0)
        hdc = screen_dc
        src_x, src_y = rect.left, rect.top
    else:
        screen_dc = None
        hdc = user32.GetWindowDC(hwnd)
        src_x, src_y = rect.left, rect.top

    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)

    if not use_screen:
        # Try PrintWindow first for occluded windows, then fall back to BitBlt.
        ok = user32.PrintWindow(hwnd, mem, PRF_CLIENT | PRF_CHILDREN | PRF_OWNED)
        if not ok:
            gdi32.BitBlt(mem, 0, 0, w, h, hdc, rect.left, rect.top, SRCCOPY)
    else:
        gdi32.BitBlt(mem, 0, 0, w, h, hdc, src_x, src_y, SRCCOPY)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    if screen_dc is not None:
        user32.ReleaseDC(0, screen_dc)

    import PIL.Image
    # Raw decoder 'BGRX' = 4 bytes/pixel little-endian BGRA, X ignored;
    # output mode is plain RGB.  GetDIBits returns top-down rows because we
    # request a negative biHeight, so ystep=+1 reads them in order.
    img = PIL.Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)
    img.save(out)
    print(f"saved {out} ({w}x{h})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="CK104 Keyboard")
    ap.add_argument("--pid", type=int)
    ap.add_argument("--out", default="_capture/shot.png")
    ap.add_argument("--printwindow", action="store_true",
                    help="use PrintWindow instead of a screen grab")
    a = ap.parse_args()
    hwnd = find_window(a.title, a.pid)
    capture(hwnd, a.out, use_screen=not a.printwindow)
    return 0


if __name__ == "__main__":
    sys.exit(main())
