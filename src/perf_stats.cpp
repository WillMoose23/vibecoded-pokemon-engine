// FEATURE-GAME-001: process memory + CPU sampling (see docs/tracker.md).

#include "perf_stats.h"

#include <chrono>
#include <fstream>
#include <sstream>
#include <string>
#include <algorithm>

#if defined(__APPLE__)
#include <mach/mach_init.h>
#include <mach/task.h>
#include <mach/task_info.h>
#endif

#include <sys/resource.h>

namespace
{

constexpr double kCpuEmaAlpha = 0.15;
constexpr std::int64_t kSampleIntervalNs = 250000000;

double monotonicCpuSeconds()
{
    struct rusage ru {};
    if (getrusage(RUSAGE_SELF, &ru) != 0)
    {
        return 0.0;
    }
    return static_cast<double>(ru.ru_utime.tv_sec) + static_cast<double>(ru.ru_utime.tv_usec) * 1.0e-6 +
           static_cast<double>(ru.ru_stime.tv_sec) + static_cast<double>(ru.ru_stime.tv_usec) * 1.0e-6;
}

bool sampleRss(std::uint64_t& outBytes)
{
    outBytes = 0;

#if defined(__APPLE__)
    mach_task_basic_info_data_t info{};
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    const kern_return_t kr = task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count);
    if (kr == KERN_SUCCESS)
    {
        outBytes = static_cast<std::uint64_t>(info.resident_size);
        return true;
    }
    return false;
#elif defined(__linux__)
    std::ifstream f("/proc/self/status");
    std::string line;
    while (std::getline(f, line))
    {
        if (line.compare(0, 6, "VmRSS:") == 0)
        {
            std::istringstream iss(line.substr(6));
            long kb = 0;
            std::string unit;
            iss >> kb >> unit;
            outBytes = static_cast<std::uint64_t>(std::max(0L, kb)) * 1024ULL;
            return true;
        }
    }
    return false;
#else
    struct rusage ru {};
    if (getrusage(RUSAGE_SELF, &ru) == 0)
    {
        // ru_maxrss in KB on many Unix systems (approximate resident peak).
        outBytes = static_cast<std::uint64_t>(ru.ru_maxrss) * 1024ULL;
        return true;
    }
    return false;
#endif
}

} // namespace

void PerfSampler::update()
{
    const auto now = std::chrono::steady_clock::now();
    const auto wallNs = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
    if (lastSampleNs_ != 0 && (wallNs - lastSampleNs_) < kSampleIntervalNs)
    {
        return;
    }
    lastSampleNs_ = wallNs;

    rssValid_ = sampleRss(rssBytes_);
    const double cpuSec = monotonicCpuSeconds();

    if (!haveLastSample_)
    {
        lastCpuSec_ = cpuSec;
        lastWallNs_ = wallNs;
        haveLastSample_ = true;
        return;
    }

    const double dCpu = cpuSec - lastCpuSec_;
    const double dWallSec = static_cast<double>(wallNs - lastWallNs_) * 1.0e-9;
    lastCpuSec_ = cpuSec;
    lastWallNs_ = wallNs;

    if (dWallSec > 1.0e-6 && dCpu >= 0.0)
    {
        const double rawPct = (dCpu / dWallSec) * 100.0;
        if (!cpuPercentReady_)
        {
            cpuPercentSmoothed_ = rawPct;
            cpuPercentReady_ = true;
        }
        else
        {
            cpuPercentSmoothed_ = kCpuEmaAlpha * rawPct + (1.0 - kCpuEmaAlpha) * cpuPercentSmoothed_;
        }
    }
}
