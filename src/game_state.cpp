#include "game_state.h"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <unistd.h>

using json = nlohmann::json;

namespace
{
namespace fs = std::filesystem;

/// FEATURE-MAP-072: the active GameState for crash-safety handlers. Only the snapshot string and
/// save path are read from signal context (both are touched with async-signal-safe operations).
GameState* g_crashState = nullptr;
std::atomic<bool> g_inCrashHandler{false};

const char* g_crashSavePath = nullptr;
const std::string* g_crashSnapshot = nullptr;

/// Async-signal-safe-ish flush: open + write + close with raw syscalls, no allocation.
void signalSafeFlush()
{
    if (g_crashSavePath == nullptr || g_crashSnapshot == nullptr)
    {
        return;
    }
    const int fd = ::open(g_crashSavePath, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd < 0)
    {
        return;
    }
    const char* data = g_crashSnapshot->c_str();
    std::size_t remaining = g_crashSnapshot->size();
    while (remaining > 0)
    {
        const ssize_t n = ::write(fd, data, remaining);
        if (n <= 0)
        {
            break;
        }
        data += n;
        remaining -= static_cast<std::size_t>(n);
    }
    ::close(fd);
}

void crashSignalHandler(int sig)
{
    if (!g_inCrashHandler.exchange(true))
    {
        signalSafeFlush();
    }
    // Restore default handler and re-raise so the process still terminates as expected.
    std::signal(sig, SIG_DFL);
    std::raise(sig);
}

void atexitFlush()
{
    if (g_crashState != nullptr)
    {
        g_crashState->flush(false);
    }
}

} // namespace

void GameState::load(const std::string& registryPath, const std::string& savePath)
{
    savePath_ = savePath;
    flags_.clear();

    json reg;
    {
        std::ifstream f(registryPath);
        if (f)
        {
            try
            {
                f >> reg;
                applyRegistryDefaults_(reg);
            }
            catch (const std::exception& e)
            {
                std::fprintf(stderr, "GameState: bad registry %s: %s\n", registryPath.c_str(), e.what());
            }
        }
    }

    json save;
    {
        std::ifstream f(savePath_);
        if (f)
        {
            try
            {
                f >> save;
                overlaySave_(save);
            }
            catch (const std::exception& e)
            {
                std::fprintf(stderr, "GameState: bad save %s: %s\n", savePath_.c_str(), e.what());
            }
        }
    }

    rebuildSnapshot_();
    dirty_ = false;
}

void GameState::applyRegistryDefaults_(const json& reg)
{
    if (!reg.is_object() || !reg.contains("flags") || !reg["flags"].is_array())
    {
        return;
    }
    for (const auto& entry : reg["flags"])
    {
        if (!entry.is_object())
        {
            continue;
        }
        const std::string name = entry.value("name", std::string());
        if (name.empty())
        {
            continue;
        }
        flags_[name] = entry.value("initial", false);
    }
}

void GameState::overlaySave_(const json& save)
{
    if (!save.is_object() || !save.contains("flags") || !save["flags"].is_object())
    {
        return;
    }
    for (auto it = save["flags"].begin(); it != save["flags"].end(); ++it)
    {
        if (it.value().is_boolean())
        {
            flags_[it.key()] = it.value().get<bool>();
        }
    }
}

bool GameState::getFlag(const std::string& name) const
{
    const auto it = flags_.find(name);
    return it != flags_.end() && it->second;
}

void GameState::setFlag(const std::string& name, bool value)
{
    if (name.empty())
    {
        return;
    }
    const auto it = flags_.find(name);
    if (it != flags_.end() && it->second == value)
    {
        return;
    }
    flags_[name] = value;
    dirty_ = true;
    rebuildSnapshot_();
}

void GameState::clearFlag(const std::string& name)
{
    setFlag(name, false);
}

void GameState::rebuildSnapshot_()
{
    // Keep keys sorted (std::map already is) so the file is clear, concise, and stable.
    json out;
    out["version"] = 1;
    json flagsObj = json::object();
    for (const auto& [name, value] : flags_)
    {
        flagsObj[name] = value;
    }
    out["flags"] = std::move(flagsObj);
    snapshot_ = out.dump(2);
    // Keep crash-handler pointers valid even if the std::string buffer was reallocated.
    g_crashSnapshot = &snapshot_;
}

bool GameState::writeAtomic_(const std::string& path, const std::string& contents) const
{
    if (path.empty())
    {
        return false;
    }
    std::error_code ec;
    const fs::path target(path);
    if (target.has_parent_path())
    {
        fs::create_directories(target.parent_path(), ec);
    }
    const fs::path tmp = fs::path(path + ".tmp");
    {
        std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
        if (!f)
        {
            return false;
        }
        f << contents;
        f.flush();
        if (!f)
        {
            return false;
        }
    }
    fs::rename(tmp, target, ec);
    if (ec)
    {
        // Fall back to a direct write if rename failed (e.g. cross-device).
        std::ofstream f(target, std::ios::binary | std::ios::trunc);
        if (!f)
        {
            return false;
        }
        f << contents;
        return static_cast<bool>(f);
    }
    return true;
}

void GameState::flushIfDirty()
{
    if (dirty_)
    {
        flush(false);
    }
}

void GameState::flush(bool force)
{
    if (!force && !dirty_)
    {
        return;
    }
    if (writeAtomic_(savePath_, snapshot_))
    {
        dirty_ = false;
    }
    if (debugDumps_)
    {
        debugDump("flush");
    }
}

void GameState::enableCrashSafety()
{
    if (crashInstalled_)
    {
        return;
    }
    crashInstalled_ = true;
    g_crashState = this;
    g_crashSavePath = savePath_.c_str();
    g_crashSnapshot = &snapshot_;

    std::atexit(atexitFlush);
    for (int sig : {SIGSEGV, SIGABRT, SIGINT, SIGTERM, SIGBUS})
    {
        std::signal(sig, crashSignalHandler);
    }
}

void GameState::debugDump(const std::string& tag) const
{
    std::error_code ec;
    const fs::path dir("debug/state_dumps");
    fs::create_directories(dir, ec);
    if (ec)
    {
        return;
    }
    using clock = std::chrono::system_clock;
    const std::time_t now = clock::to_time_t(clock::now());
    std::tm tmv{};
#if defined(_WIN32)
    localtime_s(&tmv, &now);
#else
    localtime_r(&now, &tmv);
#endif
    std::ostringstream name;
    name << "state_" << std::put_time(&tmv, "%Y%m%d_%H%M%S") << "_" << tag << ".json";
    const fs::path file = dir / name.str();
    std::ofstream f(file, std::ios::binary | std::ios::trunc);
    if (f)
    {
        f << snapshot_;
    }
}
