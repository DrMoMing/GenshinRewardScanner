// Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// AI-generated project code: written and modified with OpenAI Codex.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>
#include <objidl.h>
#include <gdiplus.h>
#include <dwmapi.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <dcomp.h>
#include <wrl/client.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include <cwctype>

namespace fs = std::filesystem;
using namespace Gdiplus;
using Microsoft::WRL::ComPtr;
constexpr wchar_t WindowClass[] = L"DomainOverlayExperiment";
constexpr int HotkeyId = 1;
constexpr int MinWidth = 320;
constexpr int MinHeight = 180;
constexpr UINT_PTR StateTimer = 10;
constexpr UINT VisualControlMessage = WM_APP + 37;

std::wstring FormatShortcut(std::wstring text) {
    std::wistringstream parts(text);
    std::wstring part, result;
    while (std::getline(parts, part, L'+')) {
        std::transform(part.begin(),part.end(),part.begin(),[](wchar_t c) { return static_cast<wchar_t>(std::towupper(c)); });
        if (part == L"CTRL") part = L"Ctrl";
        else if (part == L"ALT") part = L"Alt";
        else if (part == L"SHIFT") part = L"Shift";
        else if (part == L"WIN") part = L"Win";
        if (!result.empty()) result += L"+";
        result += part;
    }
    return result;
}

struct Surface {
    HDC dc = CreateCompatibleDC(nullptr);
    HBITMAP bitmap = nullptr;
    HGDIOBJ original = nullptr;
    void* pixels = nullptr;
    int width = 0;
    int height = 0;

    ~Surface() {
        if (bitmap) {
            SelectObject(dc, original);
            DeleteObject(bitmap);
        }
        DeleteDC(dc);
    }

    bool Resize(int w, int h) {
        if (w == width && h == height && bitmap) return true;
        if (bitmap) {
            SelectObject(dc, original);
            DeleteObject(bitmap);
            bitmap = nullptr;
        }
        BITMAPINFO info{};
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = w;
        info.bmiHeader.biHeight = -h;
        info.bmiHeader.biPlanes = 1;
        info.bmiHeader.biBitCount = 32;
        info.bmiHeader.biCompression = BI_RGB;
        bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &pixels, nullptr, 0);
        if (!bitmap) return false;
        original = SelectObject(dc, bitmap);
        width = w;
        height = h;
        return true;
    }
};

struct Presentation {
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDXGISwapChain1> swap;
    ComPtr<IDCompositionDevice> composition;
    ComPtr<IDCompositionTarget> target;
    ComPtr<IDCompositionVisual> visual;
    int width = 0, height = 0;

    HRESULT Initialize(HWND window, int w, int h) {
        HRESULT result = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0, D3D11_SDK_VERSION, &device, nullptr, &context);
        if (FAILED(result)) result = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_WARP, nullptr,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0, D3D11_SDK_VERSION, &device, nullptr, &context);
        if (FAILED(result)) return result;
        ComPtr<IDXGIDevice> dxgi;
        ComPtr<IDXGIAdapter> adapter;
        ComPtr<IDXGIFactory2> factory;
        if (FAILED(result = device.As(&dxgi))) return result;
        if (FAILED(result = dxgi->GetAdapter(&adapter))) return result;
        if (FAILED(result = adapter->GetParent(IID_PPV_ARGS(&factory)))) return result;
        DXGI_SWAP_CHAIN_DESC1 desc{};
        desc.Width = w; desc.Height = h;
        desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
        desc.SampleDesc.Count = 1;
        desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
        desc.BufferCount = 2;
        desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL;
        desc.AlphaMode = DXGI_ALPHA_MODE_PREMULTIPLIED;
        if (FAILED(result = factory->CreateSwapChainForComposition(device.Get(), &desc, nullptr, &swap))) return result;
        if (FAILED(result = DCompositionCreateDevice(dxgi.Get(), IID_PPV_ARGS(&composition)))) return result;
        if (FAILED(result = composition->CreateTargetForHwnd(window, TRUE, &target))) return result;
        if (FAILED(result = composition->CreateVisual(&visual))) return result;
        if (FAILED(result = visual->SetContent(swap.Get()))) return result;
        if (FAILED(result = target->SetRoot(visual.Get()))) return result;
        width = w; height = h;
        return composition->Commit();
    }

    HRESULT Present(HWND window, const Surface& surface) {
        HRESULT result = S_OK;
        if (!swap && FAILED(result = Initialize(window, surface.width, surface.height))) return result;
        if (width != surface.width || height != surface.height) {
            if (FAILED(result = swap->ResizeBuffers(0, surface.width, surface.height, DXGI_FORMAT_UNKNOWN, 0))) return result;
            width = surface.width; height = surface.height;
        }
        ComPtr<ID3D11Texture2D> texture;
        if (FAILED(result = swap->GetBuffer(0, IID_PPV_ARGS(&texture)))) return result;
        context->UpdateSubresource(texture.Get(), 0, nullptr, surface.pixels, surface.width * 4, 0);
        return swap->Present(0, 0);
    }
};

int ReadNumber(const fs::path& path, const wchar_t* key, int fallback) {
    wchar_t buffer[64]{};
    GetPrivateProfileStringW(L"window", key, L"", buffer, 64, path.c_str());
    wchar_t* end = nullptr;
    const long value = wcstol(buffer, &end, 10);
    if (end == buffer || *end != L'\0') return fallback;
    return static_cast<int>(value);
}

RECT VisiblePlacement(RECT rect) {
    MONITORINFO monitor{sizeof(MONITORINFO)};
    GetMonitorInfoW(MonitorFromRect(&rect, MONITOR_DEFAULTTONEAREST), &monitor);
    const RECT work = monitor.rcWork;
    const int workWidth = work.right - work.left;
    const int workHeight = work.bottom - work.top;
    const int width = std::clamp<int>(rect.right - rect.left, std::min(MinWidth, workWidth), workWidth);
    const int height = std::clamp<int>(rect.bottom - rect.top, std::min(MinHeight, workHeight), workHeight);
    const int left = std::clamp<int>(rect.left, work.left, work.right - width);
    const int top = std::clamp<int>(rect.top, work.top, work.bottom - height);
    return {left, top, left + width, top + height};
}

struct Overlay {
    HWND hwnd = nullptr;
    HWND returnFocus = nullptr;
    fs::path layoutPath;
    Surface surface;
    Presentation presentation;
    UINT dpi = 96;
    bool locked = false;
    bool hotkeyAvailable = false;
    bool saveFailed = false;
    bool renderFailed = false;
    int pressedButton = 0;
    int opacity = 72;
    bool optionsOpen = false;
    bool sliderDown = false;
    int scroll = 0;
    int maxScroll = 0;
    fs::path statePath;
    HANDLE owner = nullptr;
    std::map<std::wstring, std::wstring> state;
    ULONGLONG lastHeartbeat = 0;
    bool staleSeen = false;
    bool hiddenTest = false;
    bool excludeFromCapture = true;
    bool captureSettingFailed = false;
    std::wstring appliedControl;
    bool visualSavePending = false;
    DWORD captureError = 0;
    DWORD captureActual = 0;
    UINT shortcutModifiers = MOD_CONTROL | MOD_ALT;
    UINT shortcutKey = 'O';
    int shortcutId = HotkeyId;
    std::wstring shortcutError;
    HWND lastForeground = nullptr;
    DWORD lastForegroundPid = 0;
    bool foregroundIsGame = false;
    ULONGLONG lastLayerCheck = 0;
    bool taskRunning = false;
    bool temporaryTaskLock = false;
    bool autoTaskLock = true;
    std::wstring appliedLockControl;

    void ApplyTaskLock(bool running) {
        if (running == taskRunning) return;
        taskRunning = running;
        if (running) {
            temporaryTaskLock = autoTaskLock && !locked;
            if (temporaryTaskLock) Lock(true,false);
        } else if (temporaryTaskLock) {
            temporaryTaskLock = false;
            Lock(false,false);
        }
    }

    void RaiseWithoutActivation() const {
        SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }

    bool EnsureAbove(HWND game) const {
        // The game can change mode and Z order without changing foreground HWND.
        HWND previous = GetWindow(game, GW_HWNDPREV);
        for (int count=0; previous && count<256; ++count) {
            if (previous == hwnd) return false;
            previous = GetWindow(previous, GW_HWNDPREV);
        }
        RaiseWithoutActivation();
        return true;
    }

    void FollowGameActivation() {
        HWND foreground = GetForegroundWindow();
        const ULONGLONG now = GetTickCount64();
        const bool changed = foreground != lastForeground;
        if (!changed && now-lastLayerCheck<1000) return;
        lastLayerCheck = now;
        DWORD pid = 0;
        GetWindowThreadProcessId(foreground, &pid);
        if (!changed && pid == lastForegroundPid) {
            if (foregroundIsGame && IsWindowVisible(hwnd)) EnsureAbove(foreground);
            return;
        }
        lastForeground = foreground;
        lastForegroundPid = pid;
        foregroundIsGame = false;
        HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
        if (!process) return;
        wchar_t image[32768]{};
        DWORD size = static_cast<DWORD>(std::size(image));
        const bool queried = QueryFullProcessImageNameW(process, 0, image, &size) != FALSE;
        CloseHandle(process);
        if (!queried) return;
        const auto name = fs::path(image).filename().wstring();
        foregroundIsGame = _wcsicmp(name.c_str(), L"YuanShen.exe") == 0 || _wcsicmp(name.c_str(), L"GenshinImpact.exe") == 0;
        if (foregroundIsGame && IsWindowVisible(hwnd)) EnsureAbove(foreground);
    }

    std::wstring ShortcutText() const {
        std::wstring text;
        if (shortcutModifiers & MOD_CONTROL) text += L"Ctrl+";
        if (shortcutModifiers & MOD_ALT) text += L"Alt+";
        if (shortcutModifiers & MOD_SHIFT) text += L"Shift+";
        if (shortcutModifiers & MOD_WIN) text += L"Win+";
        if ((shortcutKey >= '0' && shortcutKey <= '9') || (shortcutKey >= 'A' && shortcutKey <= 'Z'))
            return text + static_cast<wchar_t>(shortcutKey);
        if (shortcutKey >= VK_F1 && shortcutKey <= VK_F24) return text + L"F" + std::to_wstring(shortcutKey - VK_F1 + 1);
        wchar_t name[64]{};
        const UINT scan = MapVirtualKeyW(shortcutKey, MAPVK_VK_TO_VSC_EX);
        LONG code = static_cast<LONG>((scan & 255) << 16);
        if (scan & 0xff00) code |= 1 << 24;
        if (GetKeyNameTextW(code, name, 64)) return FormatShortcut(text + name);
        return text + L"VK" + std::to_wstring(shortcutKey);
    }

    bool SetShortcut(UINT modifiers, UINT key) {
        if (hotkeyAvailable && shortcutModifiers == modifiers && shortcutKey == key) return true;
        const int nextId = shortcutId == 1 ? 2 : 1;
        if (!RegisterHotKey(hwnd, nextId, modifiers | MOD_NOREPEAT, key)) {
            shortcutError = L"快捷键已占用，请重新录入";
            return false;
        }
        if (hotkeyAvailable) UnregisterHotKey(hwnd, shortcutId);
        shortcutId = nextId; shortcutModifiers = modifiers; shortcutKey = key;
        hotkeyAvailable = true; shortcutError.clear();
        return true;
    }

    int FixedBottom() const {
        return 150 + (Value(L"perf_cpu").empty() ? 0 : 64) + (Value(L"loading").empty() ? 0 : 76);
    }
    int MinimumHeight() const { return MinHeight + FixedBottom() - 128; }

    void ApplyCaptureSetting() {
        SetLastError(0);
        const BOOL accepted = SetWindowDisplayAffinity(hwnd, excludeFromCapture ? 0x00000011 : 0);
        captureError = accepted ? 0 : GetLastError();
        captureActual = 0;
        const BOOL queried = GetWindowDisplayAffinity(hwnd, &captureActual);
        captureSettingFailed = !accepted || !queried || captureActual != (excludeFromCapture ? 0x11u : 0u);
        BOOL composed = FALSE;
        const HRESULT compositionResult = DwmIsCompositionEnabled(&composed);
        std::ofstream diagnostic(layoutPath.parent_path() / L"窗口诊断.jsonl", std::ios::app);
        diagnostic << "{\"capture_exclusion\":" << (excludeFromCapture ? "true" : "false")
            << ",\"set_ok\":" << (accepted ? "true" : "false") << ",\"error\":" << captureError
            << ",\"read_ok\":" << (queried ? "true" : "false") << ",\"actual\":" << captureActual
            << ",\"dwm_ok\":" << (SUCCEEDED(compositionResult) ? "true" : "false")
            << ",\"dwm_composed\":" << (composed ? "true" : "false")
            << ",\"has_surface\":" << (surface.bitmap ? "true" : "false") << "}\n";
    }

    std::wstring Value(const wchar_t* key, const wchar_t* fallback = L"") const {
        const auto found = state.find(key);
        return found == state.end() ? fallback : found->second;
    }

    bool PollState() {
        if (statePath.empty()) return false;
        HANDLE file = CreateFileW(statePath.c_str(), GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE) return false;
        char buffer[65536];
        DWORD count = 0;
        const bool read = ReadFile(file, buffer, sizeof(buffer), &count, nullptr) != FALSE;
        CloseHandle(file);
        if (!read || !count || count >= sizeof(buffer)) return false;
        const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, buffer, count, nullptr, 0);
        if (!length) return false;
        std::wstring text(length, L'\0');
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, buffer, count, text.data(), length);
        std::map<std::wstring, std::wstring> next;
        std::wistringstream lines(text);
        std::wstring line;
        while (std::getline(lines, line)) {
            if (!line.empty() && line.back() == L'\r') line.pop_back();
            const auto separator = line.find(L'=');
            if (separator != std::wstring::npos) next[line.substr(0, separator)] = line.substr(separator + 1);
        }
        if (next[L"closed"] == L"1") {
            // A rapid off/on may briefly leave the previous closing snapshot.
            if (state.empty() && GetTickCount64() - lastHeartbeat < 1000) return false;
            SendMessageW(hwnd, WM_CLOSE, 0, 0);
            return false;
        }
        if (next[L"heartbeat"] != Value(L"heartbeat")) lastHeartbeat = GetTickCount64();
        if (next.count(L"unlock_key") && next.count(L"unlock_modifiers")) {
            const auto key=wcstoul(next[L"unlock_key"].c_str(),nullptr,10);
            const auto modifiers=wcstoul(next[L"unlock_modifiers"].c_str(),nullptr,10);
            if (key>0 && key<255 && modifiers<16 && (key!=shortcutKey || modifiers!=shortcutModifiers || !hotkeyAvailable)) {
                if (SetShortcut(static_cast<UINT>(modifiers),static_cast<UINT>(key))) SavePlacement();
            }
        }
        if (next.count(L"control_sequence")) {
            ApplyVisualControl(_wcstoui64(next[L"control_sequence"].c_str(),nullptr,10),
                next.count(L"control_opacity") ? _wtoi(next[L"control_opacity"].c_str()) : opacity,
                next.count(L"control_exclude") ? next[L"control_exclude"]==L"1" : excludeFromCapture);
        }
        if (next.count(L"control_lock_sequence") && next[L"control_lock_sequence"] != appliedLockControl) {
            appliedLockControl=next[L"control_lock_sequence"];
            if (next.count(L"control_auto_lock")) autoTaskLock=next[L"control_auto_lock"]==L"1";
            if (next.count(L"control_locked")) Lock(next[L"control_locked"]==L"1",false);
            SavePlacement();
        }
        ApplyTaskLock(next.count(L"pending") && wcstoul(next[L"pending"].c_str(),nullptr,10)>0);
        auto prior = state;
        prior.erase(L"heartbeat");
        auto compared = next;
        compared.erase(L"heartbeat");
        const bool changed = compared != prior;
        state = std::move(next);
        return changed;
    }

    int Scale(int value) const { return MulDiv(value, static_cast<int>(dpi), 96); }

    RECT ButtonRect(int button) const {
        RECT rect{};
        GetClientRect(hwnd, &rect);
        if (button == 4) return {rect.right - Scale(228), Scale(98), rect.right - Scale(24), Scale(126)};
        const int right = rect.right - Scale(button == 1 ? 42 : button == 2 ? 10 : 98);
        return {right - Scale(button == 2 ? 26 : 50), Scale(7), right, Scale(33)};
    }

    int ButtonAt(POINT point) const {
        for (int button : {1, 2, 3}) {
            RECT rect = ButtonRect(button);
            if (PtInRect(&rect, point)) return button;
        }
        if (optionsOpen && !locked) {
            for (int button : {4}) {
                RECT area = ButtonRect(button);
                if (PtInRect(&area, point)) return button;
            }
        }
        return 0;
    }

    LRESULT HitTest(POINT screen) const {
        if (locked) return HTTRANSPARENT;
        RECT rect{};
        GetWindowRect(hwnd, &rect);
        const int x = screen.x - rect.left;
        const int y = screen.y - rect.top;
        const int width = rect.right - rect.left;
        const int height = rect.bottom - rect.top;
        const int grip = Scale(9);
        const bool left = x < grip;
        const bool right = x >= width - grip;
        const bool top = y < grip;
        const bool bottom = y >= height - grip;
        if (top && left) return HTTOPLEFT;
        if (top && right) return HTTOPRIGHT;
        if (bottom && left) return HTBOTTOMLEFT;
        if (bottom && right) return HTBOTTOMRIGHT;
        if (left) return HTLEFT;
        if (right) return HTRIGHT;
        if (top) return HTTOP;
        if (bottom) return HTBOTTOM;
        if (y < Scale(40) && !ButtonAt({x, y})) return HTCAPTION;
        return HTCLIENT;
    }

    REAL WrappedText(Graphics& graphics, const std::wstring& text, REAL x, REAL y, REAL width,
                     float size, Color color) const {
        Font font(L"Microsoft YaHei UI", size * dpi / 96.0f, FontStyleRegular, UnitPixel);
        SolidBrush brush(color);
        StringFormat format;
        RectF bounds;
        graphics.MeasureString(text.c_str(), -1, &font, RectF(x, y, width, 10000), &format, &bounds);
        const REAL height = std::max(bounds.Height, static_cast<REAL>(Scale(20)));
        graphics.DrawString(text.c_str(), -1, &font, RectF(x, y, width, height + Scale(2)), &format, &brush);
        return height;
    }

    RectF SliderRect(int width) const {
        return RectF(static_cast<REAL>(width - Scale(224)), static_cast<REAL>(Scale(70)),
                     static_cast<REAL>(Scale(190)), static_cast<REAL>(Scale(20)));
    }

    void SetOpacity(int x) {
        RECT rect{};
        GetClientRect(hwnd, &rect);
        const auto slider = SliderRect(rect.right);
        const int next = std::clamp(20 + static_cast<int>((x - slider.X) * 75 / slider.Width), 20, 95);
        SetOpacityValue(next);
    }

    void SetOpacityValue(int value) {
        const int next=std::clamp(value,20,95);
        if(next!=opacity){opacity=next;visualSavePending=true;Render();}
    }

    bool ApplyVisualControl(ULONGLONG sequence,int value,bool exclude) {
        if(sequence<=_wcstoui64(appliedControl.c_str(),nullptr,10)) return false;
        appliedControl=std::to_wstring(sequence);
        if(excludeFromCapture!=exclude){excludeFromCapture=exclude;ApplyCaptureSetting();}
        SetOpacityValue(value);
        visualSavePending=true;
        return true;
    }

    void Text(Graphics& graphics, const wchar_t* text, RectF area, float size, Color color, bool centered = false) const {
        Font font(L"Microsoft YaHei UI", size * dpi / 96.0f, FontStyleRegular, UnitPixel);
        SolidBrush brush(color);
        StringFormat format;
        format.SetLineAlignment(StringAlignmentCenter);
        format.SetTrimming(StringTrimmingEllipsisCharacter);
        format.SetFormatFlags(StringFormatFlagsNoWrap);
        if (centered) format.SetAlignment(StringAlignmentCenter);
        graphics.DrawString(text, -1, &font, area, &format, &brush);
    }

    bool Render() {
        RECT rect{};
        GetWindowRect(hwnd, &rect);
        const int width = rect.right - rect.left;
        const int height = rect.bottom - rect.top;
        if (width <= 0 || height <= 0 || !surface.Resize(width, height)) return false;
        Bitmap bitmap(width, height, width * 4, PixelFormat32bppPARGB, static_cast<BYTE*>(surface.pixels));
        {
            Graphics graphics(&bitmap);
            graphics.Clear(Color(0, 0, 0, 0));
            graphics.SetSmoothingMode(SmoothingModeAntiAlias);
            graphics.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
            SolidBrush background(Color(static_cast<BYTE>(opacity * 255 / 100), 18, 24, 33));
            SolidBrush header(Color(static_cast<BYTE>(opacity * 255 / 100), 25, 34, 46));
            graphics.FillRectangle(&background, 0, 0, width, height);
            const bool performance = !Value(L"perf_cpu").empty();
            const int fixedBottom = FixedBottom();
            graphics.FillRectangle(&header, 0, 0, width, Scale(fixedBottom));
            Pen border(Color(130, 90, 121, 144), static_cast<REAL>(Scale(1)));
            graphics.DrawRectangle(&border, 1, 1, width - 3, height - 3);
            const Color primary(255, 243, 247, 252), secondary(255, 182, 195, 211), muted(255, 127, 142, 163);
            Color accent(255, 111, 211, 224);
            if (Value(L"task_state") == L"已失败") accent = Color(255, 255, 133, 133);
            else if (Value(L"task_state") == L"已完成") accent = Color(255, 116, 214, 163);
            else if (Value(L"scanner") == L"加载中" || Value(L"task_state") == L"已中止") accent = Color(255, 228, 181, 103);
            std::wstring scanner = Value(L"scanner", L"等待连接扫描器");
            if (!statePath.empty() && GetTickCount64() - lastHeartbeat > 8000) scanner = L"扫描器状态连接中断";
            Text(graphics, scanner.c_str(), RectF(static_cast<REAL>(Scale(14)), 0,
                static_cast<REAL>(width - Scale(166)), static_cast<REAL>(Scale(40))), 13, accent);
            if (!locked) {
                for (int button : {1, 2, 3}) {
                    RECT area = ButtonRect(button);
                    SolidBrush fill(Color(pressedButton == button ? 235 : 180, 61, 79, 105));
                    graphics.FillRectangle(&fill, Rect(area.left, area.top, area.right - area.left, area.bottom - area.top));
                    const std::wstring label = button == 1 ? L"锁定" : button == 2 ? L"×" : std::to_wstring(opacity) + L"%";
                    Text(graphics, label.c_str(), RectF(static_cast<REAL>(area.left), static_cast<REAL>(area.top),
                        static_cast<REAL>(area.right - area.left), static_cast<REAL>(area.bottom - area.top)),
                        button == 2 ? 18.0f : 11.0f, primary, true);
                }
            }
            auto line = [&](const std::wstring& text, int y, int x = 14, int w = 0) {
                Text(graphics, text.c_str(), RectF(static_cast<REAL>(Scale(x)), static_cast<REAL>(Scale(y)),
                    static_cast<REAL>(w ? w : width - Scale(28)), static_cast<REAL>(Scale(22))), 11, secondary);
            };
            line(L"识别路数  请求 " + Value(L"requested", L"—") + L" · 实际 " + Value(L"actual", L"—"), 39);
            const int column = (width - Scale(28)) / 2;
            line(L"整趟  " + FormatShortcut(Value(L"scan_key", L"—")), 61, 14, column);
            line(L"拼图  " + FormatShortcut(Value(L"montage_key", L"—")), 61, 14 + column * 96 / dpi, column);
            line(L"单卡  " + FormatShortcut(Value(L"single_key", L"—")), 81, 14, column);
            line(L"中止  " + FormatShortcut(Value(L"stop_key", L"—")), 81, 14 + column * 96 / dpi, column);
            line(L"锁定/解锁  " + ShortcutText(), 101, 14, column);
            line(L"中止任务  " + FormatShortcut(Value(L"cancel_key", L"Ctrl+Alt+X")), 101, 14 + column * 96 / dpi, column);
            line(L"扫描星级  " + Value(L"stars", L"—") + L"    横排读字 " + Value(L"row_info", L"关"), 123);
            if (performance) {
                const int metricWidth = (width - Scale(28)) / 3;
                const wchar_t* names[] = {L"CPU", L"GPU", L"内存"};
                const wchar_t* keys[] = {L"perf_cpu", L"perf_gpu", L"perf_memory"};
                for (int index = 0; index < 3; ++index) {
                    const int left = Scale(14) + index * metricWidth;
                    Text(graphics, names[index], RectF(static_cast<REAL>(left), static_cast<REAL>(Scale(150)),
                        static_cast<REAL>(metricWidth), static_cast<REAL>(Scale(20))), 11, muted);
                    Text(graphics, Value(keys[index]).c_str(), RectF(static_cast<REAL>(left), static_cast<REAL>(Scale(170)),
                        static_cast<REAL>(metricWidth), static_cast<REAL>(Scale(20))), 11, primary);
                }
                line(L"扫描器 / 系统 · 含后台进程", 191);
            }
            if (!Value(L"loading").empty()) {
                const int loadingTop = performance ? 220 : 156;
                line(Value(L"loading"), loadingTop);
                if (!Value(L"loaded").empty()) line(L"正在加载第 " + Value(L"loaded") + L" 路模型", loadingTop + 22);
                SolidBrush track(Color(110, 91, 109, 132)), progress(accent);
                const REAL trackWidth = static_cast<REAL>(width - Scale(28));
                const REAL trackY = static_cast<REAL>(Scale(loadingTop + 52));
                graphics.FillRectangle(&track, static_cast<REAL>(Scale(14)), trackY, trackWidth, static_cast<REAL>(Scale(3)));
                const REAL segment = trackWidth / 4;
                const REAL position = static_cast<REAL>((GetTickCount64() / 40) % 200) / 200 * (trackWidth - segment);
                graphics.FillRectangle(&progress, Scale(14) + position, trackY, segment, static_cast<REAL>(Scale(3)));
            }
            Pen divider(Color(100, 127, 142, 163));
            graphics.DrawLine(&divider, Scale(14), Scale(fixedBottom + 1), width - Scale(14), Scale(fixedBottom + 1));
            const int contentTop = Scale(fixedBottom + 10), contentBottom = std::max(contentTop, height - Scale(32));
            const auto saved = graphics.Save();
            graphics.SetClip(Rect(Scale(10), contentTop, width - Scale(20), contentBottom - contentTop));
            REAL y = static_cast<REAL>(contentTop - scroll);
            const REAL x = static_cast<REAL>(Scale(18)), textWidth = static_cast<REAL>(width - Scale(42));
            auto body = [&](const std::wstring& text, Color color, float size = 12) {
                y += WrappedText(graphics, text, x, y, textWidth, size, color) + Scale(3);
            };
            if (!Value(L"task_number").empty()) {
                const auto number = Value(L"task_number");
                body(L"第" + number + L"次任务已启动", primary, 13);
                body(L"指令   " + Value(L"receipt"), secondary);
                body(L"任务   " + Value(L"task_name"), primary);
                body((Value(L"ended") == L"1" ? L"阶段   " : L"阶段   当前正在") + Value(L"phase"), primary);
                body(L"状态   " + Value(L"task_state") + (Value(L"error").empty() ? L"" : L" · " + Value(L"error")), accent);
                if (Value(L"ended") == L"1") body(L"第" + number + L"次任务已结束", muted, 11);
                for (const auto* key : {L"history0", L"history1"})
                    if (!Value(key).empty()) body(Value(key), muted, 11);
            } else if (Value(L"loading").empty()) body(L"等待用户指令", muted);
            if (!Value(L"notice").empty()) body(Value(L"notice"), Color(255, 228, 181, 103), 11);
            maxScroll = std::max(0, static_cast<int>(y) + scroll - contentBottom);
            graphics.Restore(saved);
            std::wstring hint = locked ? (taskRunning ? L"任务进行中 · 结束后恢复原锁定状态" : ShortcutText() + L" 解锁编辑") : L"拖动标题 · 边缘缩放 · 滚轮查看";
            if (!hotkeyAvailable) hint = locked ? L"快捷键不可用，请在扫描器设置中解锁" : L"快捷键不可用，锁定后可在扫描器设置中解锁";
            if (saveFailed) hint = L"布局保存失败，请检查所在目录权限";
            if (captureSettingFailed) hint = L"截屏排除失败 · Windows错误 " + std::to_wstring(captureError);
            if (!shortcutError.empty()) hint = shortcutError;
            Text(graphics, hint.c_str(), RectF(static_cast<REAL>(Scale(14)), static_cast<REAL>(height - Scale(29)),
                static_cast<REAL>(width - Scale(28)), static_cast<REAL>(Scale(22))), 11,
                saveFailed ? Color(255, 255, 143, 143) : Color(255, 181, 204, 230));
            if (optionsOpen && !locked) {
                const int left = width - Scale(240);
                SolidBrush panel(Color(250, 32, 43, 57));
                graphics.FillRectangle(&panel, left, Scale(38), Scale(226), Scale(126));
                Text(graphics, (L"背景不透明度  " + std::to_wstring(opacity) + L"%").c_str(),
                    RectF(static_cast<REAL>(left + Scale(14)), static_cast<REAL>(Scale(42)),
                        static_cast<REAL>(Scale(200)), static_cast<REAL>(Scale(24))), 12, primary);
                const auto slider = SliderRect(width);
                Pen track(Color(255, 98, 116, 137), static_cast<REAL>(Scale(3)));
                const REAL centerY = slider.Y + slider.Height / 2;
                graphics.DrawLine(&track, slider.X, centerY, slider.X + slider.Width, centerY);
                SolidBrush knob(accent);
                const REAL knobX = slider.X + slider.Width * (opacity - 20) / 75;
                graphics.FillEllipse(&knob, knobX - Scale(6), centerY - Scale(6), static_cast<REAL>(Scale(12)), static_cast<REAL>(Scale(12)));
                Text(graphics, excludeFromCapture ? L"☑ 从截屏 / 录屏中排除" : L"☐ 从截屏 / 录屏中排除",
                    RectF(static_cast<REAL>(left + Scale(14)), static_cast<REAL>(Scale(99)),
                        static_cast<REAL>(Scale(202)), static_cast<REAL>(Scale(26))), 11, primary);
                Text(graphics, L"解锁键可在扫描器中录入",
                    RectF(static_cast<REAL>(left + Scale(14)), static_cast<REAL>(Scale(129)),
                        static_cast<REAL>(Scale(202)), static_cast<REAL>(Scale(26))), 11, primary);
            }
        }
        renderFailed = FAILED(presentation.Present(hwnd, surface));
        return !renderFailed;
    }

    RECT ReadPlacement() const {
        RECT work{};
        SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
        const int left = ReadNumber(layoutPath, L"left", work.right - Scale(480));
        const int top = ReadNumber(layoutPath, L"top", work.top + Scale(80));
        const int savedDpi = std::clamp(ReadNumber(layoutPath, L"dpi", dpi), 48, 768);
        const int savedWidth = std::clamp(ReadNumber(layoutPath, L"width", MulDiv(460, savedDpi, 96)), MinWidth, 16384);
        const int savedHeight = std::clamp(ReadNumber(layoutPath, L"height", MulDiv(400, savedDpi, 96)), MinHeight, 16384);
        const int width = std::max(Scale(MinWidth), MulDiv(savedWidth, dpi, savedDpi));
        const int height = std::max(Scale(MinHeight), MulDiv(savedHeight, dpi, savedDpi));
        // Clamp malformed/extreme coordinates before adding dimensions.
        const int safeLeft = std::clamp(left, -100000, 100000);
        const int safeTop = std::clamp(top, -100000, 100000);
        return VisiblePlacement({safeLeft, safeTop, safeLeft + width, safeTop + height});
    }

    bool SavePlacement() {
        RECT rect{};
        GetWindowRect(hwnd, &rect);
        bool ok = true;
        const wchar_t* keys[] = {L"left", L"top", L"width", L"height", L"dpi", L"opacity", L"exclude_capture", L"shortcut_modifiers", L"shortcut_key",L"locked"};
        const int values[] = {rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, static_cast<int>(dpi), opacity, excludeFromCapture ? 1 : 0, static_cast<int>(shortcutModifiers), static_cast<int>(shortcutKey),locked ? 1 : 0};
        for (int index = 0; index < 10; ++index) {
            const std::wstring value = std::to_wstring(values[index]);
            if (!WritePrivateProfileStringW(L"window", keys[index], value.c_str(), layoutPath.c_str())) ok = false;
        }
        saveFailed = !ok;
        WritePrivateProfileStringW(L"window",L"control_lock_sequence",appliedLockControl.c_str(),layoutPath.c_str());
        WritePrivateProfileStringW(L"window",L"control_sequence",appliedControl.c_str(),layoutPath.c_str());
        return ok;
    }

    void Lock(bool enabled, bool activate = true) {
        optionsOpen = false;
        LONG_PTR style = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        if (enabled) style |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE;
        else style &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE);
        SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style);
        locked = enabled;
        SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED);
        Render();
        SavePlacement();
        if (!activate) return;
        if (!enabled) {
            HWND previous = GetForegroundWindow();
            if (previous != hwnd) returnFocus = previous;
            SetForegroundWindow(hwnd);
        } else if (GetForegroundWindow() == hwnd && IsWindow(returnFocus)) {
            SetForegroundWindow(returnFocus);
        }
    }

    static LRESULT CALLBACK Procedure(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
        auto* self = reinterpret_cast<Overlay*>(GetWindowLongPtrW(window, GWLP_USERDATA));
        if (message == WM_NCCREATE) {
            self = static_cast<Overlay*>(reinterpret_cast<CREATESTRUCTW*>(lParam)->lpCreateParams);
            self->hwnd = window;
            SetWindowLongPtrW(window, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
        }
        if (!self) return DefWindowProcW(window, message, wParam, lParam);
        switch (message) {
        case VisualControlMessage:
            self->ApplyVisualControl(static_cast<ULONGLONG>(lParam),static_cast<int>(wParam & 0xff),(wParam & 0x100)!=0);
            return 0;
        case WM_CREATE:
            self->dpi = GetDpiForWindow(window);
            SetLayeredWindowAttributes(window, 0, 255, LWA_ALPHA);
            self->hotkeyAvailable = RegisterHotKey(window, self->shortcutId, self->shortcutModifiers | MOD_NOREPEAT, self->shortcutKey) != FALSE;
            SetTimer(window, StateTimer, 200, nullptr);
            return 0;
        case WM_TIMER:
            if (wParam == StateTimer) {
                if (self->owner && WaitForSingleObject(self->owner, 0) == WAIT_OBJECT_0) {
                    SendMessageW(window, WM_CLOSE, 0, 0);
                    return 0;
                }
                self->FollowGameActivation();
                const auto task = self->Value(L"task_number");
                const bool changed = self->PollState();
                if (!IsWindow(window)) return 0;
                if(self->visualSavePending){self->SavePlacement();self->visualSavePending=false;}
                RECT rect{};
                GetWindowRect(window, &rect);
                if (rect.bottom - rect.top < self->Scale(self->MinimumHeight()))
                    SetWindowPos(window, nullptr, 0, 0, rect.right - rect.left, self->Scale(self->MinimumHeight()), SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
                if (task != self->Value(L"task_number")) self->scroll = 0;
                const bool stale = !self->statePath.empty() && GetTickCount64() - self->lastHeartbeat > 8000;
                if (changed || stale != self->staleSeen || !self->Value(L"loading").empty()) self->Render();
                self->staleSeen = stale;
            }
            return 0;
        case WM_NCCALCSIZE:
            return 0;
        case WM_NCHITTEST:
            return self->HitTest({GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)});
        case WM_GETMINMAXINFO: {
            auto* sizes = reinterpret_cast<MINMAXINFO*>(lParam);
            sizes->ptMinTrackSize = {self->Scale(MinWidth), self->Scale(self->MinimumHeight())};
            return 0;
        }
        case WM_SIZE:
            self->scroll = 0;
            self->Render();
            return 0;
        case WM_PAINT: {
            PAINTSTRUCT paint{};
            BeginPaint(window, &paint);
            EndPaint(window, &paint);
            self->Render();
            return 0;
        }
        case WM_ERASEBKGND:
            return 1;
        case WM_EXITSIZEMOVE:
            self->SavePlacement();
            self->Render();
            return 0;
        case WM_DPICHANGED: {
            self->dpi = HIWORD(wParam);
            const RECT rect = *reinterpret_cast<RECT*>(lParam);
            SetWindowPos(window, nullptr, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, SWP_NOZORDER | SWP_NOACTIVATE);
            self->Render();
            return 0;
        }
        case WM_DISPLAYCHANGE: {
            RECT rect{};
            GetWindowRect(window, &rect);
            rect = VisiblePlacement(rect);
            SetWindowPos(window, HWND_TOPMOST, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, SWP_NOACTIVATE);
            return 0;
        }
        case WM_HOTKEY:
            if (wParam == static_cast<WPARAM>(self->shortcutId) && !self->taskRunning) self->Lock(!self->locked, false);
            return 0;
        case WM_ACTIVATE:
            if (LOWORD(wParam) != WA_INACTIVE && lParam && reinterpret_cast<HWND>(lParam) != window) {
                self->returnFocus = reinterpret_cast<HWND>(lParam);
            }
            break;
        case WM_LBUTTONDOWN:
            if (self->optionsOpen) {
                RECT rect{};
                GetClientRect(window, &rect);
                const auto slider = self->SliderRect(rect.right);
                if (slider.Contains(static_cast<REAL>(GET_X_LPARAM(lParam)), static_cast<REAL>(GET_Y_LPARAM(lParam)))) {
                    self->sliderDown = true;
                    SetCapture(window);
                    self->SetOpacity(GET_X_LPARAM(lParam));
                    return 0;
                }
            }
            self->pressedButton = self->ButtonAt({GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)});
            if (self->pressedButton) SetCapture(window);
            else self->optionsOpen = false;
            self->Render();
            return 0;
        case WM_MOUSEMOVE:
            if (self->sliderDown) self->SetOpacity(GET_X_LPARAM(lParam));
            return 0;
        case WM_MOUSEWHEEL:
            self->scroll = std::clamp(self->scroll - GET_WHEEL_DELTA_WPARAM(wParam) * self->Scale(44) / WHEEL_DELTA, 0, self->maxScroll);
            self->Render();
            return 0;
        case WM_LBUTTONUP: {
            const int pressed = self->pressedButton;
            self->pressedButton = 0;
            const bool adjusted = self->sliderDown;
            self->sliderDown = false;
            ReleaseCapture();
            if (adjusted) { self->SavePlacement(); self->Render(); return 0; }
            if (pressed && pressed == self->ButtonAt({GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)})) {
                if (pressed == 2) SendMessageW(window, WM_CLOSE, 0, 0);
                else if (pressed == 3) { self->optionsOpen = !self->optionsOpen; self->Render(); }
                else if (pressed == 4) {
                    self->excludeFromCapture = !self->excludeFromCapture;
                    self->ApplyCaptureSetting(); self->SavePlacement(); self->Render();
                }
                else self->Lock(true);
            } else self->Render();
            return 0;
        }
        case WM_CAPTURECHANGED:
            self->pressedButton = 0;
            self->sliderDown = false;
            return 0;
        case WM_CLOSE:
            self->SavePlacement();
            DestroyWindow(window);
            return 0;
        case WM_DESTROY:
            KillTimer(window, StateTimer);
            if (self->owner) { CloseHandle(self->owner); self->owner = nullptr; }
            if (self->hotkeyAvailable) UnregisterHotKey(window, self->shortcutId);
            PostQuitMessage(0);
            return 0;
        }
        return DefWindowProcW(window, message, wParam, lParam);
    }
};

int SelfTest(Overlay& app, const fs::path& folder) {
    app.ApplyTaskLock(false);
    bool ok = app.Render();
    if (!ok || !app.surface.pixels) {
        std::ofstream(folder / L"selftest.json") << "{\"ok\":false,\"error\":\"layered render failed\"}";
        return 1;
    }
    RECT rect{};
    GetWindowRect(app.hwnd, &rect);
    const int width = rect.right - rect.left;
    const int height = rect.bottom - rect.top;
    UINT encoderCount = 0;
    UINT encoderBytes = 0;
    GetImageEncodersSize(&encoderCount, &encoderBytes);
    std::vector<BYTE> encoderBuffer(encoderBytes);
    auto* encoders = reinterpret_cast<ImageCodecInfo*>(encoderBuffer.data());
    GetImageEncoders(encoderCount, encoderBytes, encoders);
    bool previewSaved = false;
    for (UINT index = 0; index < encoderCount; ++index) {
        if (wcscmp(encoders[index].MimeType, L"image/png") == 0) {
            Bitmap preview(width, height, width * 4, PixelFormat32bppPARGB, static_cast<BYTE*>(app.surface.pixels));
            previewSaved = preview.Save((folder / L"窗口预览.png").c_str(), &encoders[index].Clsid) == Ok;
        }
    }
    const POINT points[] = {{2, 2}, {width - 2, 2}, {2, height - 2}, {width - 2, height - 2},
        {2, height / 2}, {width - 2, height / 2}, {width / 2, 2}, {width / 2, height - 2}, {80, 24}};
    const LRESULT expected[] = {HTTOPLEFT, HTTOPRIGHT, HTBOTTOMLEFT, HTBOTTOMRIGHT, HTLEFT, HTRIGHT, HTTOP, HTBOTTOM, HTCAPTION};
    bool hitTests = true;
    for (size_t index = 0; index < std::size(points); ++index) {
        const POINT point{rect.left + points[index].x, rect.top + points[index].y};
        hitTests = hitTests && SendMessageW(app.hwnd, WM_NCHITTEST, 0, MAKELPARAM(point.x, point.y)) == expected[index];
    }
    MINMAXINFO limits{};
    SendMessageW(app.hwnd, WM_GETMINMAXINFO, 0, reinterpret_cast<LPARAM>(&limits));
    const bool minimumSize = limits.ptMinTrackSize.x == app.Scale(MinWidth) && limits.ptMinTrackSize.y == app.Scale(app.MinimumHeight());
    const int originalOpacity = app.opacity;
    const auto originalControl = app.appliedControl;
    const ULONGLONG visualSequence = _wcstoui64(originalControl.c_str(),nullptr,10)+2;
    SendMessageW(app.hwnd,VisualControlMessage,41 | (app.excludeFromCapture ? 0x100 : 0),static_cast<LPARAM>(visualSequence));
    const bool immediateVisual = app.opacity==41;
    SendMessageW(app.hwnd,VisualControlMessage,88 | (app.excludeFromCapture ? 0x100 : 0),static_cast<LPARAM>(visualSequence-1));
    const bool orderedVisual = app.opacity==41;
    ok = ok && immediateVisual && orderedVisual;
    app.SetOpacityValue(originalOpacity);app.appliedControl=originalControl;app.visualSavePending=false;
    app.optionsOpen = true;
    const auto slider = app.SliderRect(width);
    const int sliderY = static_cast<int>(slider.Y + slider.Height / 2);
    SendMessageW(app.hwnd, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(static_cast<int>(slider.X + 1), sliderY));
    SendMessageW(app.hwnd, WM_MOUSEMOVE, MK_LBUTTON, MAKELPARAM(static_cast<int>(slider.X + slider.Width - 1), sliderY));
    SendMessageW(app.hwnd, WM_TIMER, StateTimer, 0);
    ok=ok && ReadNumber(app.layoutPath,L"opacity",-1)==app.opacity;
    SendMessageW(app.hwnd, WM_LBUTTONUP, 0, MAKELPARAM(static_cast<int>(slider.X + slider.Width - 1), sliderY));
    const bool sliderWorks = app.opacity >= 93 && ReadNumber(app.layoutPath, L"opacity", -1) == app.opacity;
    app.optionsOpen = true;
    const RECT captureButton = app.ButtonRect(4);
    const LPARAM capturePoint = MAKELPARAM(captureButton.left + app.Scale(10), captureButton.top + app.Scale(12));
    const bool originalExclude = app.excludeFromCapture;
    SendMessageW(app.hwnd, WM_LBUTTONDOWN, MK_LBUTTON, capturePoint);
    SendMessageW(app.hwnd, WM_LBUTTONUP, 0, capturePoint);
    DWORD affinity = 0;
    const bool captureToggle = app.excludeFromCapture != originalExclude &&
        GetWindowDisplayAffinity(app.hwnd, &affinity) && affinity == static_cast<DWORD>(app.excludeFromCapture ? 0x11 : 0) &&
        ReadNumber(app.layoutPath, L"exclude_capture", -1) == (app.excludeFromCapture ? 1 : 0);
    app.excludeFromCapture = originalExclude;
    app.ApplyCaptureSetting();
    const bool captureRestored = !app.captureSettingFailed;
    app.opacity = originalOpacity;
    app.optionsOpen = false;
    app.Render();
    const BYTE* pixels = static_cast<BYTE*>(app.surface.pixels);
    const BYTE alpha = pixels[((height - app.Scale(45)) * width + width - app.Scale(14)) * 4 + 3];
    bool opaque = false;
    for (int index = 0; index < width * height; ++index) opaque = opaque || pixels[index * 4 + 3] == 255;
    ok = ok && alpha > 0 && alpha < 255 && opaque;
    app.Lock(true, false);
    const LONG_PTR lockedStyle = GetWindowLongPtrW(app.hwnd, GWL_EXSTYLE);
    const bool lockStyles = (lockedStyle & WS_EX_TRANSPARENT) && (lockedStyle & WS_EX_NOACTIVATE);
    app.Lock(false, false);
    ok = ok && !(GetWindowLongPtrW(app.hwnd, GWL_EXSTYLE) & WS_EX_TRANSPARENT) && !app.renderFailed;
    const int savedWidth = app.Scale(520);
    const int savedHeight = app.Scale(340);
    SetWindowPos(app.hwnd, nullptr, rect.left, rect.top, savedWidth, savedHeight, SWP_NOZORDER | SWP_NOACTIVATE);
    ok = ok && app.SavePlacement();
    const RECT saved = app.ReadPlacement();
    ok = ok && saved.right - saved.left == savedWidth && saved.bottom - saved.top == savedHeight;
    const fs::path validPath = app.layoutPath;
    app.layoutPath = folder / L"不存在的子目录" / L"窗口布局.ini";
    const bool saveErrorHandled = !app.SavePlacement() && app.saveFailed;
    app.layoutPath = validPath;
    app.SavePlacement();
    const UINT originalModifiers = app.shortcutModifiers;
    const UINT originalKey = app.shortcutKey;
    const bool originalAvailable = app.hotkeyAvailable;
    const bool shortcutSaved = app.SetShortcut(MOD_CONTROL | MOD_SHIFT, VK_F23) && app.SavePlacement() &&
        ReadNumber(app.layoutPath, L"shortcut_modifiers", -1) == (MOD_CONTROL | MOD_SHIFT) &&
        ReadNumber(app.layoutPath, L"shortcut_key", -1) == VK_F23 && app.ShortcutText() == L"Ctrl+Shift+F23";
    if (originalAvailable) app.SetShortcut(originalModifiers, originalKey);
    else {
        if (app.hotkeyAvailable) UnregisterHotKey(app.hwnd, app.shortcutId);
        app.hotkeyAvailable = false; app.shortcutModifiers = originalModifiers; app.shortcutKey = originalKey;
    }
    app.SavePlacement();
    const RECT recovered = VisiblePlacement({-90000, -90000, -89600, -89700});
    const bool availableBeforeLockTest=app.hotkeyAvailable;
    app.hotkeyAvailable=false;
    app.Lock(false,false);
    const RECT lockButton=app.ButtonRect(1);
    const LPARAM lockPoint=MAKELPARAM((lockButton.left+lockButton.right)/2,(lockButton.top+lockButton.bottom)/2);
    SendMessageW(app.hwnd,WM_LBUTTONDOWN,MK_LBUTTON,lockPoint);
    SendMessageW(app.hwnd,WM_LBUTTONUP,0,lockPoint);
    const bool lockWithoutShortcut=app.locked;
    app.Lock(false,false);
    app.hotkeyAvailable=availableBeforeLockTest;
    if (!lockWithoutShortcut) return 34;
    MONITORINFO monitor{sizeof(MONITORINFO)};
    GetMonitorInfoW(MonitorFromRect(&recovered, MONITOR_DEFAULTTONEAREST), &monitor);
    const bool recoveredVisible = recovered.left >= monitor.rcWork.left && recovered.top >= monitor.rcWork.top;
    const HWND foregroundBefore = GetForegroundWindow();
    const bool wasVisible = IsWindowVisible(app.hwnd) != FALSE;
    HWND competing = CreateWindowExW(WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        L"STATIC", L"Own Z-order test", WS_POPUP, 0, 0, 200, 100, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    bool layerRecovery = false;
    if (competing) {
        ShowWindow(app.hwnd, SW_SHOWNOACTIVATE);
        SetWindowPos(competing, HWND_TOPMOST, 0, 0, 200, 100, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        const bool restored = app.EnsureAbove(competing);
        const bool stable = !app.EnsureAbove(competing);
        // The same window changes size and returns to the top, reproducing
        // mode-switch ordering without a foreground-handle transition.
        SetWindowPos(competing, HWND_TOPMOST, 0, 0, 800, 600, SWP_NOACTIVATE);
        layerRecovery = restored && stable && app.EnsureAbove(competing) &&
            !app.EnsureAbove(competing) && GetForegroundWindow() == foregroundBefore;
        DestroyWindow(competing);
        if (!wasVisible) ShowWindow(app.hwnd, SW_HIDE);
    }
    const bool shortcutFormat = FormatShortcut(L"ctrl+ALT+s") == L"Ctrl+Alt+S" &&
        FormatShortcut(L"shift+f23") == L"Shift+F23";
    app.Lock(false,false);app.ApplyTaskLock(true);
    SendMessageW(app.hwnd,WM_HOTKEY,app.shortcutId,0);
    const bool temporaryLocked = app.locked;
    app.ApplyTaskLock(false);
    const bool restoredUnlocked = !app.locked;
    app.Lock(true,false);app.ApplyTaskLock(true);
    SendMessageW(app.hwnd,WM_HOTKEY,app.shortcutId,0);
    const bool runningStaysLocked = app.locked;
    app.ApplyTaskLock(false);
    const bool retainedLocked = app.locked;
    SendMessageW(app.hwnd,WM_HOTKEY,app.shortcutId,0);
    const bool taskLock = temporaryLocked && restoredUnlocked && runningStaysLocked && retainedLocked && !app.locked && GetForegroundWindow()==foregroundBefore;
    ok = ok && recoveredVisible && lockStyles && hitTests && minimumSize && previewSaved && saveErrorHandled && sliderWorks && captureToggle && captureRestored && shortcutSaved && layerRecovery && shortcutFormat && taskLock;
    std::ofstream report(folder / L"selftest.json");
    report << "{\"ok\":" << (ok ? "true" : "false") << ",\"resize_hit_tests\":8,\"all_hit_tests_passed\":" << (hitTests ? "true" : "false") << ',' <<
        "\"minimum_size_passed\":" << (minimumSize ? "true" : "false") << ',' <<
        "\"background_alpha\":" << static_cast<int>(alpha) << ",\"opaque_text\":" << (opaque ? "true" : "false") << ","
        "\"click_through_styles\":" << (lockStyles ? "true" : "false") << ",\"saved_size\":[" << savedWidth << ',' << savedHeight << "],"
        "\"offscreen_recovery\":" << (recoveredVisible ? "true" : "false") << ",\"preview_saved\":" << (previewSaved ? "true" : "false") <<
        ",\"save_error_handled\":" << (saveErrorHandled ? "true" : "false") <<
        ",\"hotkey_available\":" << (app.hotkeyAvailable ? "true" : "false") <<
        ",\"opacity\":" << app.opacity << ",\"state_fields\":" << app.state.size() <<
        ",\"slider_and_save\":" << (sliderWorks ? "true" : "false") <<
        ",\"capture_toggle_and_save\":" << (captureToggle ? "true" : "false") <<
        ",\"capture_restored\":" << (captureRestored ? "true" : "false") <<
        ",\"shortcut_custom_saved\":" << (shortcutSaved ? "true" : "false") <<
        ",\"same_window_layer_recovery\":" << (layerRecovery ? "true" : "false") <<
        ",\"shortcut_format\":" << (shortcutFormat ? "true" : "false") <<
        ",\"task_lock_restore_no_activation\":" << (taskLock ? "true" : "false") <<
        ",\"capture_error\":" << app.captureError << ",\"capture_actual\":" << app.captureActual <<
        ",\"loading_empty\":" << (app.Value(L"loading").empty() ? "true" : "false") <<
        ",\"task_ended\":" << (app.Value(L"ended") == L"1" ? "true" : "false") << ",\"game_input\":false}";
    return ok ? 0 : 1;
}

LRESULT CALLBACK TestBackdrop(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    if (message == WM_PAINT) {
        PAINTSTRUCT paint{};
        HDC dc = BeginPaint(window, &paint);
        RECT rect{}; GetClientRect(window, &rect);
        HBRUSH brush = CreateSolidBrush(RGB(200, 100, 50));
        FillRect(dc, &rect, brush); DeleteObject(brush);
        EndPaint(window, &paint);
        return 0;
    }
    return DefWindowProcW(window, message, wParam, lParam);
}

int VisualTest(Overlay& app, const fs::path& folder) {
    WNDCLASSW backdropClass{};
    backdropClass.hInstance = GetModuleHandleW(nullptr);
    backdropClass.lpfnWndProc = TestBackdrop;
    backdropClass.lpszClassName = L"OverlayOwnedBackdrop";
    RegisterClassW(&backdropClass);
    RECT rect{}; GetWindowRect(app.hwnd, &rect);
    HWND backdrop = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        backdropClass.lpszClassName, L"Own overlay composition test", WS_POPUP,
        rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
        nullptr, nullptr, backdropClass.hInstance, nullptr);
    if (!backdrop) return 2;
    ShowWindow(backdrop, SW_SHOWNOACTIVATE); UpdateWindow(backdrop); DwmFlush();
    Surface sample; sample.Resize(1, 1);
    const int x = rect.right - app.Scale(18), y = rect.bottom - app.Scale(47);
    auto pixel = [&](DWORD operation) {
        HDC screen = GetDC(nullptr);
        BitBlt(sample.dc, 0, 0, 1, 1, screen, x, y, operation);
        ReleaseDC(nullptr, screen);
        return GetPixel(sample.dc, 0, 0);
    };
    const COLORREF background = pixel(SRCCOPY | CAPTUREBLT);
    app.excludeFromCapture = false; app.ApplyCaptureSetting();
    app.opacity = 50; app.Render();
    ShowWindow(app.hwnd, SW_SHOWNOACTIVATE);
    SetWindowPos(app.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
    UpdateWindow(app.hwnd); DwmFlush(); Sleep(100);
    const COLORREF visible = pixel(SRCCOPY | CAPTUREBLT);
    const COLORREF visiblePlain = pixel(SRCCOPY);
    app.excludeFromCapture = true; app.ApplyCaptureSetting(); DwmFlush(); Sleep(100);
    const COLORREF excluded = pixel(SRCCOPY | CAPTUREBLT);
    const COLORREF excludedPlain = pixel(SRCCOPY);
    const bool backdropVisible = background == RGB(200, 100, 50);
    const bool blended = abs(static_cast<int>(GetRValue(visible)) - 109) <= 8 &&
        abs(static_cast<int>(GetGValue(visible)) - 62) <= 8 && abs(static_cast<int>(GetBValue(visible)) - 42) <= 8;
    const bool exclusion = !app.captureSettingFailed && excluded == background && excludedPlain == background;
    ShowWindow(app.hwnd, SW_HIDE); DestroyWindow(backdrop);
    std::ofstream report(folder / L"visual.json");
    report << "{\"backdrop_visible\":" << (backdropVisible ? "true" : "false")
        << ",\"blended\":" << (blended ? "true" : "false") << ",\"excluded\":" << (exclusion ? "true" : "false")
        << ",\"background\":" << background << ",\"visible\":" << visible << ",\"excluded_pixel\":" << excluded
        << ",\"srccopy_visible\":" << visiblePlain << ",\"srccopy_excluded\":" << excludedPlain << "}";
    return backdropVisible && blended && exclusion ? 0 : 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    GdiplusStartupInput input;
    ULONG_PTR token = 0;
    if (GdiplusStartup(&token, &input, nullptr) != Ok) return 2;
    int count = 0;
    LPWSTR* args = CommandLineToArgvW(GetCommandLineW(), &count);
    wchar_t module[MAX_PATH]{};
    GetModuleFileNameW(nullptr, module, MAX_PATH);
    Overlay app;
    app.dpi = GetDpiForSystem();
    app.layoutPath = fs::path(module).parent_path() / L"窗口布局.ini";
    const bool visualTest = count == 3 && std::wstring(args[1]) == L"--visual-test";
    const bool selfTest = count >= 3 && (std::wstring(args[1]) == L"--self-test" || visualTest);
    fs::path testFolder;
    if (selfTest) {
        testFolder = args[2];
        fs::create_directories(testFolder);
        app.layoutPath = testFolder / L"窗口布局.ini";
        if (count >= 5 && std::wstring(args[3]) == L"--state") app.statePath = args[4];
        if (count >= 7 && std::wstring(args[5]) == L"--options") app.optionsOpen = std::wstring(args[6]) == L"1";
    } else {
        for (int index = 1; index + 1 < count; index += 2) {
            if (std::wstring(args[index]) == L"--layout") app.layoutPath = args[index + 1];
            else if (std::wstring(args[index]) == L"--state") app.statePath = args[index + 1];
            else if (std::wstring(args[index]) == L"--hidden") app.hiddenTest = std::wstring(args[index + 1]) == L"1";
            else if (std::wstring(args[index]) == L"--owner") {
                const auto pid = wcstoul(args[index + 1], nullptr, 10);
                app.owner = OpenProcess(SYNCHRONIZE, FALSE, pid);
                if (!app.owner) { LocalFree(args); GdiplusShutdown(token); return 5; }
            }
        }
    }
    app.opacity = std::clamp(ReadNumber(app.layoutPath, L"opacity", 72), 20, 95);
    app.excludeFromCapture = ReadNumber(app.layoutPath, L"exclude_capture", 1) != 0;
    app.shortcutModifiers = static_cast<UINT>(ReadNumber(app.layoutPath, L"shortcut_modifiers", MOD_CONTROL | MOD_ALT)) & 15;
    app.shortcutKey = static_cast<UINT>(std::clamp(ReadNumber(app.layoutPath, L"shortcut_key", 'O'), 1, 254));
    app.lastHeartbeat = GetTickCount64();
    LocalFree(args);
    WNDCLASSW windowClass{};
    windowClass.hInstance = instance;
    windowClass.lpfnWndProc = Overlay::Procedure;
    windowClass.lpszClassName = WindowClass;
    windowClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    windowClass.hIcon = LoadIconW(instance,MAKEINTRESOURCEW(101));
    RegisterClassW(&windowClass);
    const RECT rect = app.ReadPlacement();
    const DWORD extended = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOREDIRECTIONBITMAP;
    HWND window = CreateWindowExW(extended, WindowClass, L"原神副本扫描器 · 浮窗", WS_POPUP | WS_THICKFRAME | WS_SYSMENU,
        rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, nullptr, nullptr, instance, &app);
    // BGI's MaskWindow sets WS_CHILD after creating its independent window.
    // Keep the desktop parent and combine it with non-activating topmost
    // restoration when the game returns to the foreground. No game HWND is
    // reparented and no capture/input controller is involved in this display.
    if (window) SetWindowLongPtrW(window, GWL_STYLE, GetWindowLongPtrW(window, GWL_STYLE) | WS_CHILD);
    int result = 0;
    if (!window) result = 3;
    else if (selfTest) {
        app.PollState();
        result = visualTest ? VisualTest(app, testFolder) : SelfTest(app, testFolder);
        DestroyWindow(window);
    } else {
        // Windows 10 2004+ supports excluding our display from screen capture.
        app.ApplyCaptureSetting();
        app.returnFocus = GetForegroundWindow();
        if (!app.Render()) {
            MessageBoxW(nullptr, L"半透明窗口绘制失败。请保留实验程序，以便检查当前桌面环境。", L"悬浮窗实验", MB_OK | MB_ICONERROR);
            DestroyWindow(window);
            result = 4;
        } else {
            if (!app.hiddenTest) ShowWindow(window, SW_SHOWNOACTIVATE);
            MSG message{};
            while (GetMessageW(&message, nullptr, 0, 0) > 0) {
                TranslateMessage(&message);
                DispatchMessageW(&message);
            }
        }
    }
    GdiplusShutdown(token);
    return result;
}
