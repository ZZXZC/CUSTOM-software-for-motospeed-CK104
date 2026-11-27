/*
 * hidprobe.c -- 32-bit diagnostic probe for the CK104.
 *
 * Build it into _capture\app\ so that `LoadLibrary("HID.dll")` resolves to our
 * logging proxy rather than System32.  That verifies the forwarding chain and,
 * because every HidD_* call is logged, leaves a trail in hid.log.
 *
 * Read-only: it never calls HidD_SetFeature / HidD_SetOutputReport.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <stdio.h>
#include <stdlib.h>

#pragma comment(lib, "setupapi.lib")
#pragma comment(lib, "hid.lib")

static const char* hexdump(const unsigned char* p, unsigned n, char* out, unsigned cap)
{
    static const char* h = "0123456789abcdef";
    unsigned i, o = 0;
    for (i = 0; i < n && o + 4 < cap; i++) {
        out[o++] = h[p[i] >> 4];
        out[o++] = h[p[i] & 0x0F];
        out[o++] = ' ';
    }
    out[o] = 0;
    return out;
}

static void wprint(const wchar_t* s)
{
    char buf[512];
    WideCharToMultiByte(CP_ACP, 0, s, -1, buf, sizeof buf, NULL, NULL);
    fputs(buf, stdout);
}

int main(void)
{
    char path[512], hx[1024];
    GUID hidGuid;
    DWORD i;
    HDEVINFO devs;
    SP_DEVICE_INTERFACE_DATA ifd;
    int n = 0;

    GetModuleFileNameA(NULL, path, sizeof path);
    printf("probe exe : %s\n", path);

    {
        HMODULE h = GetModuleHandleA("HID.dll");
        if (h) {
            GetModuleFileNameA(h, path, sizeof path);
            printf("HID.dll   : %s\n", path);
        } else {
            printf("HID.dll   : NOT LOADED (err=%lu)\n", GetLastError());
        }
    }
    printf("\n");

    HidD_GetHidGuid(&hidGuid);
    printf("hid GUID  : {%08lX-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}\n",
           hidGuid.Data1, hidGuid.Data2, hidGuid.Data3,
           hidGuid.Data4[0], hidGuid.Data4[1], hidGuid.Data4[2], hidGuid.Data4[3],
           hidGuid.Data4[4], hidGuid.Data4[5], hidGuid.Data4[6], hidGuid.Data4[7]);

    devs = SetupDiGetClassDevsW(&hidGuid, NULL, NULL,
                                DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (devs == INVALID_HANDLE_VALUE) {
        printf("SetupDiGetClassDevs failed: %lu\n", GetLastError());
        return 1;
    }

    for (i = 0; ; i++) {
        HANDLE h;
        HIDD_ATTRIBUTES attr;
        HIDP_CAPS caps;
        PHIDP_PREPARSED_DATA pp = NULL;
        wchar_t prod[256];
        WCHAR wpath[1024];
        DWORD need = 0;
        unsigned featLen, inLen, outLen;
        int openFailed = 0;

        ifd.cbSize = sizeof ifd;
        if (!SetupDiEnumDeviceInterfaces(devs, NULL, &hidGuid, i, &ifd)) {
            printf("enumeration stopped at index %lu (err=%lu)\n",
                   (unsigned long)i, GetLastError());
            break;
        }

        if (!SetupDiGetDeviceInterfaceDetailW(devs, &ifd, NULL, 0, &need, NULL) &&
            GetLastError() != ERROR_INSUFFICIENT_BUFFER) {
            printf("  [detail probe fail, err=%lu]\n", GetLastError());
            continue;
        }
        {
            /* cbSize must be the full struct size (8 on x86), not sizeof(DWORD). */
            SP_DEVICE_INTERFACE_DETAIL_DATA_W* det =
                (SP_DEVICE_INTERFACE_DETAIL_DATA_W*)calloc(1, need);
            if (!det) continue;
            det->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
            if (!SetupDiGetDeviceInterfaceDetailW(devs, &ifd, det, need, NULL, NULL)) {
                printf("  [detail fail, err=%lu] ", GetLastError());
                free(det);
                continue;
            }
            memcpy(wpath, det->DevicePath, sizeof wpath);
            free(det);
        }

        h = CreateFileW(wpath, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                        OPEN_EXISTING, 0, NULL);
        openFailed = (h == INVALID_HANDLE_VALUE);
        if (openFailed)
            h = CreateFileW(wpath, 0, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            NULL, OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE) {
            printf("  [unopenable] ");
            wprint(wpath);
            printf("\n");
            continue;
        }

        attr.Size = sizeof attr;
        if (!HidD_GetAttributes(h, &attr)) {
            printf("  [attrs fail, err=%lu] ", GetLastError());
            wprint(wpath);
            printf("\n");
            CloseHandle(h);
            continue;
        }
        if (attr.VendorID != 0x258A || attr.ProductID != 0x0016) {
            printf("  [skip %04X:%04X] ", attr.VendorID, attr.ProductID);
            wprint(wpath);
            printf("\n");
            CloseHandle(h);
            continue;
        }
        printf("  [open ok%s] ", openFailed ? " read-only" : "");

        n++;
        printf("---- device %d ----\n", n);
        printf("  path    : ");
        wprint(wpath);
        printf("\n  VID:PID : %04X:%04X  version=%04X\n",
               attr.VendorID, attr.ProductID, attr.VersionNumber);

        prod[0] = 0;
        if (HidD_GetProductString(h, prod, sizeof prod)) {
            printf("  product : ");
            wprint(prod);
            printf("\n");
        }

        if (HidD_GetPreparsedData(h, &pp) && pp) {
            if (HidP_GetCaps(pp, &caps) == HIDP_STATUS_SUCCESS) {
                printf("  usage   : page=%04X usage=%02X\n", caps.UsagePage, caps.Usage);
                printf("  lengths : in=%u out=%u feat=%u\n",
                       caps.InputReportByteLength, caps.OutputReportByteLength,
                       caps.FeatureReportByteLength);
                featLen = caps.FeatureReportByteLength;
                inLen = caps.InputReportByteLength;
                outLen = caps.OutputReportByteLength;

                if (featLen > 0) {
                    unsigned rid;
                    int found = 0;
                    printf("  feature report IDs that read back:\n");
                    for (rid = 0; rid < 256; rid++) {
                        unsigned char* b = calloc(1, featLen);
                        if (!b) break;
                        b[0] = (unsigned char)rid;
                        if (HidD_GetFeature(h, b, featLen)) {
                            printf("    rid=%-3u len=%-5u | %s\n", rid, featLen,
                                   hexdump(b, featLen > 64 ? 64 : featLen, hx, sizeof hx));
                            found++;
                        }
                        free(b);
                    }
                    if (!found)
                        printf("    (none accepted)\n");
                }
                (void)inLen; (void)outLen;
            }
            HidD_FreePreparsedData(pp);
        }
        printf("\n");
        CloseHandle(h);
    }

    SetupDiDestroyDeviceInfoList(devs);
    printf("matched %d CK104 interface(s)\n", n);
    fflush(stdout);
    return 0;
}
