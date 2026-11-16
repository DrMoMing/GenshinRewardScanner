#include <windows.h>
#include <evntrace.h>
#include <evntcons.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {
constexpr GUID threads = {0x3d6fa8d1,0xfe05,0x11d0,{0x9d,0xda,0x00,0xc0,0x4f,0xd7,0xba,0x7c}};
constexpr GUID stacks = {0xdef2fe46,0x7bd6,0x4b80,{0xbd,0x94,0xf5,0x7f,0xe2,0x0d,0x0c,0xe3}};
constexpr GUID markers = {0xbec8a40d,0x9c3b,0x41bb,{0x96,0x2b,0x54,0x4c,0x6c,0x39,0xda,0x91}};
constexpr GUID processes = {0x3d6fa8d0,0xfe05,0x11d0,{0x9d,0xda,0x00,0xc0,0x4f,0xd7,0xba,0x7c}};
constexpr GUID images = {0x2cb15d1d,0x5fc1,0x11d2,{0xab,0xe1,0x00,0xa0,0xc9,0x11,0xf5,0x18}};
constexpr GUID graphics = {0x802ec45a,0x1e99,0x4b83,{0x99,0x20,0x87,0xc9,0x82,0x77,0xba,0x9d}};
struct Mark {std::string kind, task; LONGLONG qpc;};
std::vector<Mark> marks;
ULONGLONG count=0, switches=0, stack_count=0;
ULONGLONG process_count=0, image_count=0, graphics_count=0;
LONGLONG first=0, last=0;
void WINAPI event(PEVENT_RECORD record) {
    ++count;
    auto tick=record->EventHeader.TimeStamp.QuadPart;
    if (IsEqualGUID(record->EventHeader.ProviderId,threads) && record->EventHeader.EventDescriptor.Opcode==36) {
        ++switches;
        if (!first || tick<first) first=tick;
        if (tick>last) last=tick;
    }
    if (IsEqualGUID(record->EventHeader.ProviderId,stacks)) ++stack_count;
    if (IsEqualGUID(record->EventHeader.ProviderId,processes)) ++process_count;
    if (IsEqualGUID(record->EventHeader.ProviderId,images)) ++image_count;
    if (IsEqualGUID(record->EventHeader.ProviderId,graphics)) ++graphics_count;
    if (!IsEqualGUID(record->EventHeader.ProviderId,markers) || !(record->EventHeader.Flags&EVENT_HEADER_FLAG_STRING_ONLY)) return;
    const auto text=static_cast<const wchar_t*>(record->UserData);
    std::wstring value(text,record->UserDataLength/sizeof(wchar_t));
    if (value.rfind(L"DS73|",0)!=0) return;
    auto split=value.find(L'|',5);
    if (split==std::wstring::npos) return;
    auto kind=value.substr(5,split-5), task=value.substr(split+1,32);
    if ((kind!=L"begin" && kind!=L"end") || task.size()!=32 || task.find_first_not_of(L"0123456789abcdef")!=std::wstring::npos) return;
    marks.push_back({std::string(kind.begin(),kind.end()),std::string(task.begin(),task.end()),tick});
}
}

int wmain(int argc,wchar_t** argv) {
    if (argc!=3) return 2;
    EVENT_TRACE_LOGFILEW log{};
    log.LogFileName=argv[1];
    log.ProcessTraceMode=PROCESS_TRACE_MODE_EVENT_RECORD|PROCESS_TRACE_MODE_RAW_TIMESTAMP;
    log.EventRecordCallback=event;
    auto handle=OpenTraceW(&log);
    if (handle==INVALID_PROCESSTRACE_HANDLE) return 3;
    auto status=ProcessTrace(&handle,1,nullptr,nullptr);
    CloseTrace(handle);
    std::ofstream out(std::filesystem::path(argv[2]),std::ios::binary);
    if (!out) return 4;
    out<<"{\"status\":"<<status<<",\"events\":"<<count<<",\"context_switches\":"<<switches
       <<",\"stacks\":"<<stack_count<<",\"first_switch_qpc\":"<<first<<",\"last_switch_qpc\":"<<last
       <<",\"frequency\":"<<log.LogfileHeader.PerfFreq.QuadPart<<",\"events_lost\":"<<log.LogfileHeader.EventsLost<<",\"markers\":[";
    bool comma=false;
    for (const auto& mark:marks) {
        if (comma) out<<',';
        comma=true;
        out<<"{\"kind\":\""<<mark.kind<<"\",\"task\":\""<<mark.task<<"\",\"qpc\":"<<mark.qpc<<'}';
    }
    out<<"],\"process_events\":"<<process_count<<",\"image_events\":"<<image_count<<",\"graphics_events\":"<<graphics_count<<"}";
    return status ? 5 : 0;
}
