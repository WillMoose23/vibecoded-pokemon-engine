#ifndef PERF_STATS_H
#define PERF_STATS_H

#include <cstdint>

/// FEATURE-GAME-001: process RSS + CPU% sampling for debug HUD.
class PerfSampler
{
public:
    /// Call once per frame; updates wall/cpu deltas and EMA.
    void update();

    [[nodiscard]] bool rssKnown() const { return rssValid_; }
    [[nodiscard]] std::uint64_t rssBytes() const { return rssBytes_; }

    /// Smoothed CPU as % of one logical core (may exceed 100% if multi-threaded).
    [[nodiscard]] bool cpuPercentReady() const { return cpuPercentReady_; }
    [[nodiscard]] double cpuPercentSmoothed() const { return cpuPercentSmoothed_; }

private:
    double lastCpuSec_ = 0.0;
    std::int64_t lastWallNs_ = 0;
    std::int64_t lastSampleNs_ = 0;
    bool haveLastSample_ = false;
    bool rssValid_ = false;
    std::uint64_t rssBytes_ = 0;
    bool cpuPercentReady_ = false;
    double cpuPercentSmoothed_ = 0.0;
};

#endif
