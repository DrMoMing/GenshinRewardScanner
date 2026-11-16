// Bounded native observer bridge. Never captures images or sends input.
// No Python calls, allocations, file IO, GPU work or frame-permission decisions
// occur on Maa's capture/FrameArrived threads.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <atomic>
#include <cstdint>

namespace {
struct Entry { std::int64_t sequence,stage,tick,frame_time,thread; };
SRWLOCK lock=SRWLOCK_INIT;
Entry ring[128]{};
std::int64_t sequence=0;
std::atomic<std::int64_t> signals{0},last_signal{0};
}

extern "C" __declspec(dllexport) void __cdecl DomainScannerCaptureTraceCallback(
    int stage,std::int64_t frame_time) noexcept
{
    LARGE_INTEGER now;QueryPerformanceCounter(&now);
    if(stage==10){last_signal.store(now.QuadPart);signals.fetch_add(1);return;}
    AcquireSRWLockExclusive(&lock);
    const auto next=++sequence;
    ring[(next-1)%128]={next,stage,now.QuadPart,frame_time,GetCurrentThreadId()};
    ReleaseSRWLockExclusive(&lock);
}

// ABI version 1: five int64 values per event, five metadata values. The reader
// is called outside capture work and copies at most 128 entries under the lock.
extern "C" __declspec(dllexport) int __cdecl DomainScannerReadCaptureTrace(
    std::int64_t after,std::int64_t* values,int capacity,std::int64_t* metadata) noexcept
{
    if(!values||!metadata||capacity<1)return -1;
    LARGE_INTEGER frequency;QueryPerformanceFrequency(&frequency);
    AcquireSRWLockShared(&lock);
    metadata[0]=1;metadata[1]=frequency.QuadPart;metadata[2]=sequence;
    metadata[3]=signals.load();metadata[4]=last_signal.load();
    const auto first=(sequence>128?sequence-128:0)+1;
    auto begin=after+1;if(begin<first)begin=first;
    int count=0;
    for(auto index=begin;index<=sequence&&count<capacity;++index){
        const auto& entry=ring[(index-1)%128];
        values[count*5]=entry.sequence;values[count*5+1]=entry.stage;
        values[count*5+2]=entry.tick;values[count*5+3]=entry.frame_time;
        values[count*5+4]=entry.thread;++count;
    }
    ReleaseSRWLockShared(&lock);
    return count;
}
