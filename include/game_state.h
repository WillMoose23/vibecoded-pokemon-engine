#ifndef GAME_STATE_H
#define GAME_STATE_H

#include <map>
#include <string>

#include <json.hpp>

/// FEATURE-MAP-072 / FEATURE-MAP-073: persistent game-state flags.
///
/// Flags are the durable game progress (e.g. "talked to rival", "got starter"). They are seeded
/// from a registry of declared defaults, overlaid by an on-disk save file, and written back
/// atomically. A pre-serialized snapshot string is kept current on every mutation so the
/// crash-safety handler can flush with an async-signal-safe raw write. Scratch variables are NOT
/// persisted here (they live per script-run in ScriptRuntime).
class GameState
{
public:
    /// Load registry defaults then overlay the save file. Safe to call once at startup.
    void load(const std::string& registryPath, const std::string& savePath);

    bool getFlag(const std::string& name) const;
    /// Set or clear a flag; updates the in-memory snapshot and marks the state dirty.
    void setFlag(const std::string& name, bool value);
    void clearFlag(const std::string& name);

    /// Debounced flush: writes to disk only when dirty.
    void flushIfDirty();
    /// Write to disk when dirty, or unconditionally when force is true.
    void flush(bool force);

    /// Install signal + atexit handlers (idempotent). Best-effort crash persistence.
    void enableCrashSafety();

    void setDebugDumps(bool on) { debugDumps_ = on; }
    /// Write a timestamped dump into debug/state_dumps/ when debug dumps are enabled.
    void debugDump(const std::string& tag) const;

    const std::map<std::string, bool>& flags() const { return flags_; }

private:
    void applyRegistryDefaults_(const nlohmann::json& reg);
    void overlaySave_(const nlohmann::json& save);
    void rebuildSnapshot_();
    bool writeAtomic_(const std::string& path, const std::string& contents) const;

    std::map<std::string, bool> flags_;
    std::string savePath_;
    std::string snapshot_;  ///< current serialized JSON; kept up to date for signal-safe flush.
    bool dirty_ = false;
    bool debugDumps_ = false;
    bool crashInstalled_ = false;
};

#endif
