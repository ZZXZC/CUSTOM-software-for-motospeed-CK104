/*
 * hidproxy.c -- logging proxy for the 32-bit system HID.dll.
 *
 * The Motospeed CK104 vendor app (OemDrv.exe, 32-bit) talks to the keyboard
 * through Lowerdev.dll, which in turn calls HidD_* from HID.dll.  HID.dll is
 * NOT in the KnownDLLs list, so dropping this proxy next to OemDrv.exe makes
 * the loader bind Lowerdev.dll's HID imports to us instead of System32.
 *
 * The four protocol-carrying calls are implemented here and logged; every
 * other HID.dll export is forwarded verbatim through hidproxy.def to
 * hidreal.dll (an unchanged copy of SysWOW64\HID.dll).  Forwarders are
 * resolved by the loader, so they are signature-agnostic and transparent.
 *
 * Build: build.cmd
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <strsafe.h>

/*
 * Export forwarding for everything we do not intercept.
 *
 * link.exe does not honour `name=module.name` forwarders written in a .def
 * file, but it does honour them in a /EXPORT directive.  A forwarder is
 * resolved by the loader into a thunk that jumps straight into the real
 * function, so the callee's own stdcall stack cleanup applies unchanged --
 * no signature knowledge is required and the call is fully transparent.
 */
#pragma comment(linker, "/export:HidD_FlushQueue=hidreal.HidD_FlushQueue")
#pragma comment(linker, "/export:HidD_FreePreparsedData=hidreal.HidD_FreePreparsedData")
#pragma comment(linker, "/export:HidD_GetAttributes=hidreal.HidD_GetAttributes")
#pragma comment(linker, "/export:HidD_GetConfiguration=hidreal.HidD_GetConfiguration")
#pragma comment(linker, "/export:HidD_GetHidGuid=hidreal.HidD_GetHidGuid")
#pragma comment(linker, "/export:HidD_GetIndexedString=hidreal.HidD_GetIndexedString")
#pragma comment(linker, "/export:HidD_GetManufacturerString=hidreal.HidD_GetManufacturerString")
#pragma comment(linker, "/export:HidD_GetMsGenreDescriptor=hidreal.HidD_GetMsGenreDescriptor")
#pragma comment(linker, "/export:HidD_GetNumInputBuffers=hidreal.HidD_GetNumInputBuffers")
#pragma comment(linker, "/export:HidD_GetPhysicalDescriptor=hidreal.HidD_GetPhysicalDescriptor")
#pragma comment(linker, "/export:HidD_GetPreparsedData=hidreal.HidD_GetPreparsedData")
#pragma comment(linker, "/export:HidD_GetProductString=hidreal.HidD_GetProductString")
#pragma comment(linker, "/export:HidD_GetSerialNumberString=hidreal.HidD_GetSerialNumberString")
#pragma comment(linker, "/export:HidD_Hello=hidreal.HidD_Hello")
#pragma comment(linker, "/export:HidD_SetConfiguration=hidreal.HidD_SetConfiguration")
#pragma comment(linker, "/export:HidD_SetNumInputBuffers=hidreal.HidD_SetNumInputBuffers")
#pragma comment(linker, "/export:HidP_GetButtonCaps=hidreal.HidP_GetButtonCaps")
#pragma comment(linker, "/export:HidP_GetCaps=hidreal.HidP_GetCaps")
#pragma comment(linker, "/export:HidP_GetData=hidreal.HidP_GetData")
#pragma comment(linker, "/export:HidP_GetExtendedAttributes=hidreal.HidP_GetExtendedAttributes")
#pragma comment(linker, "/export:HidP_GetLinkCollectionNodes=hidreal.HidP_GetLinkCollectionNodes")
#pragma comment(linker, "/export:HidP_GetScaledUsageValue=hidreal.HidP_GetScaledUsageValue")
#pragma comment(linker, "/export:HidP_GetSpecificButtonCaps=hidreal.HidP_GetSpecificButtonCaps")
#pragma comment(linker, "/export:HidP_GetSpecificValueCaps=hidreal.HidP_GetSpecificValueCaps")
#pragma comment(linker, "/export:HidP_GetUsageValue=hidreal.HidP_GetUsageValue")
#pragma comment(linker, "/export:HidP_GetUsageValueArray=hidreal.HidP_GetUsageValueArray")
#pragma comment(linker, "/export:HidP_GetUsages=hidreal.HidP_GetUsages")
#pragma comment(linker, "/export:HidP_GetUsagesEx=hidreal.HidP_GetUsagesEx")
#pragma comment(linker, "/export:HidP_GetValueCaps=hidreal.HidP_GetValueCaps")
#pragma comment(linker, "/export:HidP_InitializeReportForID=hidreal.HidP_InitializeReportForID")
#pragma comment(linker, "/export:HidP_MaxDataListLength=hidreal.HidP_MaxDataListLength")
#pragma comment(linker, "/export:HidP_MaxUsageListLength=hidreal.HidP_MaxUsageListLength")
#pragma comment(linker, "/export:HidP_SetData=hidreal.HidP_SetData")
#pragma comment(linker, "/export:HidP_SetScaledUsageValue=hidreal.HidP_SetScaledUsageValue")
#pragma comment(linker, "/export:HidP_SetUsageValue=hidreal.HidP_SetUsageValue")
#pragma comment(linker, "/export:HidP_SetUsageValueArray=hidreal.HidP_SetUsageValueArray")
#pragma comment(linker, "/export:HidP_SetUsages=hidreal.HidP_SetUsages")
#pragma comment(linker, "/export:HidP_TranslateUsagesToI8042ScanCodes=hidreal.HidP_TranslateUsagesToI8042ScanCodes")
#pragma comment(linker, "/export:HidP_UnsetUsages=hidreal.HidP_UnsetUsages")
#pragma comment(linker, "/export:HidP_UsageListDifference=hidreal.HidP_UsageListDifference")

/* ------------------------------------------------------------------ types */

typedef unsigned short USHORT;

/* Local copy of HIDP_CAPS so this file needs no WDK/HID headers.
 * Only the leading fields are read. */
typedef struct _CK_CAPS {
    USHORT UsagePage;
    USHORT Usage;
    USHORT InputReportByteLength;
    USHORT OutputReportByteLength;
    USHORT FeatureReportByteLength;
    USHORT Reserved[17];
    USHORT NumberLinkCollectionNodes;
    USHORT NumberInputButtonCaps;
    USHORT NumberInputValueCaps;
    USHORT NumberInputDataIndices;
    USHORT NumberOutputButtonCaps;
    USHORT NumberOutputValueCaps;
    USHORT NumberOutputDataIndices;
    USHORT NumberFeatureButtonCaps;
    USHORT NumberFeatureValueCaps;
    USHORT NumberFeatureDataIndices;
} CK_CAPS;

typedef BOOL (WINAPI *PFN_HidD_GetPreparsedData)(HANDLE, PVOID*);
typedef BOOL (WINAPI *PFN_HidD_FreePreparsedData)(PVOID);
typedef long (WINAPI *PFN_HidP_GetCaps)(PVOID, CK_CAPS*);
typedef BOOL (WINAPI *PFN_Report)(HANDLE, PVOID, ULONG);

#define HIDP_STATUS_SUCCESS 0x00110000L
#define LOGCAP 4096
#define HEXCAP 768

/* ----------------------------------------------------------------- state */

static HMODULE              g_real;
static PFN_HidD_GetPreparsedData g_getPreparse;
static PFN_HidD_FreePreparsedData g_freePreparse;
static PFN_HidP_GetCaps     g_getCaps;
static PFN_Report           g_setFeature;
static PFN_Report           g_setOutput;
static PFN_Report           g_getFeature;
static PFN_Report           g_getInput;

static CRITICAL_SECTION     g_lock;
static HANDLE               g_log = INVALID_HANDLE_VALUE;
static ULONGLONG            g_start;
static LONG                 g_seq;

static BOOL load_real(void)
{
    if (g_real)
        return TRUE;
    /* Reached only from an API call, i.e. outside the loader lock. */
    g_real = LoadLibraryW(L"hidreal.dll");
    if (!g_real)
        return FALSE;
    g_getPreparse  = (PFN_HidD_GetPreparsedData)GetProcAddress(g_real, "HidD_GetPreparsedData");
    g_freePreparse = (PFN_HidD_FreePreparsedData)GetProcAddress(g_real, "HidD_FreePreparsedData");
    g_getCaps      = (PFN_HidP_GetCaps)GetProcAddress(g_real, "HidP_GetCaps");
    g_setFeature   = (PFN_Report)GetProcAddress(g_real, "HidD_SetFeature");
    g_setOutput    = (PFN_Report)GetProcAddress(g_real, "HidD_SetOutputReport");
    g_getFeature   = (PFN_Report)GetProcAddress(g_real, "HidD_GetFeature");
    g_getInput     = (PFN_Report)GetProcAddress(g_real, "HidD_GetInputReport");
    return g_getPreparse && g_getCaps && g_setFeature;
}

/* Describe which HID collection a handle belongs to. */
static void collection_of(HANDLE dev, char* out, size_t cap)
{
    PVOID pp = NULL;
    out[0] = 0;
    if (!g_real || !dev || !g_getPreparse || !g_getCaps) {
        StringCchPrintfA(out, cap, "coll=unknown");
        return;
    }
    if (!g_getPreparse(dev, &pp) || !pp) {
        StringCchPrintfA(out, cap, "coll=preparse-fail");
        return;
    }
    {
        CK_CAPS caps;
        long st = g_getCaps(pp, &caps);
        if (st == HIDP_STATUS_SUCCESS) {
            StringCchPrintfA(out, cap,
                "page=%04X usage=%02X in=%u out=%u feat=%u",
                caps.UsagePage, caps.Usage,
                caps.InputReportByteLength,
                caps.OutputReportByteLength,
                caps.FeatureReportByteLength);
        } else {
            StringCchPrintfA(out, cap, "coll=caps-fail(0x%08lX)", st);
        }
    }
    g_freePreparse(pp);
}

static void hexdump(const unsigned char* p, ULONG len, char* out, size_t cap)
{
    static const char hex[] = "0123456789abcdef";
    ULONG i, o = 0;
    ULONG limit = (len > 256) ? 256 : len;   /* keep log lines bounded */

    for (i = 0; i < limit && o + 4 < cap; i++) {
        out[o++] = hex[p[i] >> 4];
        out[o++] = hex[p[i] & 0x0F];
        out[o++] = ' ';
    }
    if (limit < len && o + 4 < cap) {
        out[o++] = '.'; out[o++] = '.'; out[o++] = '.';
    }
    out[o] = 0;
}

static void log_report(const char* what, HANDLE dev, const void* buf, ULONG len, BOOL ok)
{
    char line[LOGCAP];
    char hx[HEXCAP];
    char coll[96];
    ULONG written = 0;
    const unsigned char* b = (const unsigned char*)buf;

    collection_of(dev, coll, sizeof(coll));
    if (!b) {
        b = (const unsigned char*)"";
        len = 0;
        StringCchCatA(coll, sizeof(coll), " buf=NULL");
    }
    hexdump(b, len, hx, sizeof(hx));

    StringCchPrintfA(line, sizeof(line),
        "%9I64u seq=%5ld %-18s %s len=%u ok=%d | %s\r\n",
        GetTickCount64() - g_start,
        InterlockedIncrement(&g_seq),
        what, coll, len, (int)ok, hx);

    if (g_log == INVALID_HANDLE_VALUE)
        return;
    WriteFile(g_log, line, (DWORD)lstrlenA(line), &written, NULL);
    FlushFileBuffers(g_log);
}

/* ---------------------------- intercepted (logged) exports ---------------- */

BOOL WINAPI HidD_SetFeature(HANDLE dev, PVOID buf, ULONG len)
{
    BOOL ok;
    if (!load_real())
        return FALSE;
    ok = g_setFeature(dev, buf, len);
    log_report("SET_FEATURE", dev, buf, len, ok);
    return ok;
}

BOOL WINAPI HidD_SetOutputReport(HANDLE dev, PVOID buf, ULONG len)
{
    BOOL ok;
    if (!load_real())
        return FALSE;
    ok = g_setOutput(dev, buf, len);
    log_report("SET_OUTPUT", dev, buf, len, ok);
    return ok;
}

BOOL WINAPI HidD_GetFeature(HANDLE dev, PVOID buf, ULONG len)
{
    BOOL ok;
    if (!load_real())
        return FALSE;
    ok = g_getFeature(dev, buf, len);
    log_report("GET_FEATURE", dev, buf, len, ok);
    return ok;
}

BOOL WINAPI HidD_GetInputReport(HANDLE dev, PVOID buf, ULONG len)
{
    BOOL ok;
    if (!load_real())
        return FALSE;
    ok = g_getInput(dev, buf, len);
    log_report("GET_INPUT", dev, buf, len, ok);
    return ok;
}

/* ---------------------------------------------------------------- attach */

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved)
{
    WCHAR path[MAX_PATH];
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hinst);
        InitializeCriticalSection(&g_lock);
        g_start = GetTickCount64();

        GetModuleFileNameW(NULL, path, MAX_PATH);
        {
            WCHAR* next = path, * p;
            for (p = path; *p; p++)
                if (*p == L'\\' || *p == L'/')
                    next = p + 1;
            StringCchCopyW(next, MAX_PATH - (next - path), L"hid.log");
        }

        EnterCriticalSection(&g_lock);
        g_log = CreateFileW(path, FILE_APPEND_DATA,
                            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                            NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (g_log != INVALID_HANDLE_VALUE) {
            char line[256];
            ULONG wr;
            StringCchPrintfA(line, sizeof(line),
                "==== hidproxy attach pid=%lu ptr=%u ====\r\n",
                GetCurrentProcessId(), (unsigned)(sizeof(void*) * 8));
            WriteFile(g_log, line, (DWORD)lstrlenA(line), &wr, NULL);
        }
        LeaveCriticalSection(&g_lock);
    }
    return TRUE;
}
