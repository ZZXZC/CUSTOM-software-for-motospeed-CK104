"""
Enumerate HID devices and dump descriptors/capabilities for the Motospeed CK104
(VID 0x258A / PID 0x0016).

Pure ctypes: no third-party packages required.

Usage:
    python tools/hid_dump.py
    python tools/hid_dump.py --descriptor   # also dump raw report descriptors
"""

import argparse
import ctypes
import struct
import sys
from ctypes import wintypes

hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")
kernel32 = ctypes.WinDLL("kernel32.dll")

# ---------------------------------------------------------------- constants
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

# ---------------------------------------------------------------- structs


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __str__(self):
        d = self.Data4
        return (
            "{%08X-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}"
            % (
                self.Data1,
                self.Data2,
                self.Data3,
                d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7],
            )
        )


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wintypes.USHORT),
        ("Usage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class COLLECTION_NODE(ctypes.Structure):
    _fields_ = [
        ("ConnectionType", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("Parent", wintypes.USHORT),
        ("NumberOfChildren", wintypes.USHORT),
        ("Next", wintypes.USHORT),
    ]


# ---------------------------------------------------------------- prototypes
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
for fn in (
    "HidD_GetProductString",
    "HidD_GetManufacturerString",
    "HidD_GetSerialNumberString",
    "HidD_GetIndexedString",
):
    f = getattr(hid, fn)
    # BOOL XxxString(HANDLE, PVOID Buffer, ULONG BufferLength)
    # (HidD_GetIndexedString takes a ULONG StringIndex between the two.)
    f.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
    f.restype = wintypes.BOOLEAN
hid.HidD_GetIndexedString.argtypes = [
    wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG
]
hid.HidD_GetIndexedString.restype = wintypes.BOOLEAN

hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOLEAN
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = wintypes.ULONG  # NTSTATUS
hid.HidD_GetReportDescriptor = getattr(hid, "HidD_GetReportDescriptor", None)
if hid.HidD_GetReportDescriptor:
    hid.HidD_GetReportDescriptor.argtypes = [
        wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG)
    ]
    hid.HidD_GetReportDescriptor.restype = wintypes.BOOLEAN

setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD
]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOLEAN
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOLEAN
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


# ---------------------------------------------------------------- helpers
def get_simple_string(h: int, fn) -> str:
    buf = ctypes.create_unicode_buffer(512)
    if fn(h, buf, ctypes.sizeof(buf)):
        return buf.value
    return ""


# HIDP_STATUS_SUCCESS
NTSTATUS_SUCCESS = 0x00110000


def items_gen(desc: bytes):
    i = 0
    size_map = {0: 0, 1: 1, 2: 2, 3: 4}
    while i < len(desc):
        b = desc[i]
        i += 1
        if b == 0xFE:
            if i + 1 >= len(desc):
                return
            n = desc[i + 1]
            data = desc[i + 2:i + 2 + n]
            i += 2 + n
            yield ("long", 0, data)
            continue
        tag = (b >> 4) & 0x0F
        typ = (b >> 2) & 0x03
        size = size_map[b & 0x03]
        data = desc[i:i + size]
        i += size
        yield (typ, tag, data)


def summarize_descriptor(desc: bytes) -> str:
    """Walk a report descriptor and print report IDs with byte lengths and usages."""
    report_size = 0
    report_count = 0
    usage_page = 0
    usage = None
    rid = 0
    depth = 0
    prefix = ""
    lines = []
    type_names = {0: "Main", 1: "Global", 2: "Local", 3: "Reserved"}

    for typ, tag, data in items_gen(desc):
        if typ == "long":
            lines.append(f"  <long item {tag} {len(data)} bytes>")
            continue
        val = int.from_bytes(data, "little") if data else 0

        if typ == 0:  # Main
            if tag == 8:  # Input
                bits = report_size * report_count
                lines.append(
                    f"{prefix}INPUT   id={rid:<3} {bits:>4} bits = {(bits+7)//8:<3} bytes "
                    f"| page=0x{usage_page:04X} usage=0x{usage:02X}"
                    f" {'constant' if val & 1 else 'data'}"
                )
            elif tag == 9:  # Output
                bits = report_size * report_count
                lines.append(
                    f"{prefix}OUTPUT  id={rid:<3} {bits:>4} bits = {(bits+7)//8:<3} bytes "
                    f"| page=0x{usage_page:04X} usage=0x{usage:02X}"
                )
            elif tag == 11:  # Feature
                bits = report_size * report_count
                lines.append(
                    f"{prefix}FEATURE id={rid:<3} {bits:>4} bits = {(bits+7)//8:<3} bytes "
                    f"| page=0x{usage_page:04X} usage=0x{usage:02X}"
                )
            elif tag == 10:  # Collection
                lines.append(f"{prefix}COLLECTION page=0x{usage_page:04X} usage=0x{usage:02X}")
                prefix += "  "
                depth += 1
            elif tag == 12:  # End Collection
                if depth:
                    depth -= 1
                    prefix = prefix[2:]
                lines.append(f"{prefix}END COLLECTION")
        elif typ == 1:  # Global
            if tag == 0:
                usage_page = val
                lines.append(f"{prefix}usage_page  0x{val:04X}")
            elif tag == 1:
                lines.append(f"{prefix}logical_min {val}")
            elif tag == 2:
                lines.append(f"{prefix}logical_max {val}")
            elif tag == 7:
                report_size = val
            elif tag == 8:
                report_count = val
            elif tag == 9:
                rid = val
                lines.append(f"{prefix}*** report_id {val} ***")
        elif typ == 2:  # Local
            if tag == 0:
                usage = val
            elif tag == 1:
                lines.append(f"{prefix}usage_min {val}")
            elif tag == 2:
                lines.append(f"{prefix}usage_max {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------- enumeration
def enumerate_hid():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    devs = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if devs in (None, INVALID_HANDLE_VALUE):
        raise OSError("SetupDiGetClassDevsW failed")

    results = []
    idx = 0
    try:
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA()
            ifd.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                devs, None, ctypes.byref(guid), idx, ctypes.byref(ifd)
            ):
                break
            idx += 1

            need = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                devs, ctypes.byref(ifd), None, 0, ctypes.byref(need), None
            )
            class Detail(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD),
                            ("DevicePath", wintypes.WCHAR * 1024)]

            detail = Detail()
            # Windows requires cbSize == sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)
            # *without* the path buffer, aligned to 4 bytes -> 8. Passing
            # ctypes.sizeof(Detail) (buffer included) silently fails here.
            detail.cbSize = (ctypes.sizeof(wintypes.DWORD) + 2 + 3) & ~3
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                devs, ctypes.byref(ifd), ctypes.byref(detail), need, None, None
            ):
                continue
            results.append(detail.DevicePath)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)
    return results


def inspect(path: str, want_descriptor: bool):
    h = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if h == INVALID_HANDLE_VALUE:
        h = kernel32.CreateFileW(
            path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
        )
    if h == INVALID_HANDLE_VALUE:
        print(f"  !! could not open: {path}")
        return None

    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
        hid.HidD_GetAttributes(h, ctypes.byref(attrs))

        product = get_simple_string(h, hid.HidD_GetProductString)
        mfr = get_simple_string(h, hid.HidD_GetManufacturerString)
        serial = get_simple_string(h, hid.HidD_GetSerialNumberString)

        caps = HIDP_CAPS()
        pp = ctypes.c_void_p()
        caps_ok = False
        if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            caps_ok = hid.HidP_GetCaps(pp, ctypes.byref(caps)) == NTSTATUS_SUCCESS

        print(f"  path     : {path}")
        print(f"  VID:PID  : 0x{attrs.VendorID:04X}:0x{attrs.ProductID:04X}"
              f"  version=0x{attrs.VersionNumber:04X}")
        print(f"  product  : {product!r}")
        print(f"  vendor   : {mfr!r}")
        print(f"  serial   : {serial!r}")
        if caps_ok:
            print(f"  usage    : page=0x{caps.UsagePage:04X} usage=0x{caps.Usage:02X}")
            print(f"  lengths  : input={caps.InputReportByteLength} "
                  f"output={caps.OutputReportByteLength} "
                  f"feature={caps.FeatureReportByteLength}")
            print(f"  elements : inBtn={caps.NumberInputButtonCaps} "
                  f"inVal={caps.NumberInputValueCaps} "
                  f"outVal={caps.NumberOutputValueCaps} "
                  f"featVal={caps.NumberFeatureValueCaps} "
                  f"featBtn={caps.NumberFeatureButtonCaps} "
                  f"links={caps.NumberLinkCollectionNodes}")

        if want_descriptor and hid.HidD_GetReportDescriptor:
            need = wintypes.ULONG(0)
            hid.HidD_GetReportDescriptor(h, 0, None, ctypes.byref(need))
            if need.value:
                buf = ctypes.create_string_buffer(need.value)
                got = wintypes.ULONG(0)
                if hid.HidD_GetReportDescriptor(h, need, buf, ctypes.byref(got)):
                    desc = buf.raw[:got.value]
                    print(f"  descriptor ({got.value} bytes):")
                    print(summarize_descriptor(desc))

        if pp:
            hid.HidD_FreePreparsedData(pp)
        return {"path": path, "vid": attrs.VendorID, "pid": attrs.ProductID}
    finally:
        kernel32.CloseHandle(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--descriptor", action="store_true", help="dump raw report descriptors")
    ap.add_argument("--all", action="store_true", help="inspect every HID device, not just the CK104")
    args = ap.parse_args()

    paths = enumerate_hid()
    print(f"found {len(paths)} HID interfaces\n")
    for p in paths:
        if not args.all and ("258A" not in p.upper() and "258A" not in p):
            # device paths contain VID_xxxx&PID_xxxx
            if "vid_258a" not in p.lower():
                continue
        print("-" * 78)
        inspect(p, args.descriptor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
