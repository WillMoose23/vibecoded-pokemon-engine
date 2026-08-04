#ifndef SCRIPT_ENGINE_H
#define SCRIPT_ENGINE_H

#include <cstddef>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include <json.hpp>

enum class ScriptStepResult
{
    Continue,
    Yield,
    Finished,
    Error
};

/// FEATURE-MAP-068: one active `repeat`/`end_repeat` iteration frame on the loop stack.
struct ScriptLoopFrame
{
    std::size_t bodyStartPc = 0; ///< pc of the first body action (the action after `repeat`).
    int remaining = 0;           ///< iterations left, including the one currently running.
};

/// FEATURE-MAP-074: one saved caller frame for `call_subflow` (method-like call/return).
/// Captures everything that is local to a flow so the callee runs in isolation and the caller
/// resumes exactly where it left off when the subflow returns.
struct ScriptCallFrame
{
    nlohmann::json actions = nlohmann::json::array();
    std::size_t pc = 0;
    std::map<std::string, nlohmann::json> vars;          ///< caller's local scratch variables.
    std::vector<ScriptLoopFrame> loopStack;
    std::map<std::string, std::size_t> labels;           ///< caller flow label -> pc index.
    std::string flowName;
};

/// FEATURE-MAP-030 / FEATURE-MAP-043: map script runner; `loadDocument` accepts legacy `actions` or `script_1` (array of one-key objects or insertion-ordered object).
struct ScriptRuntime
{
    /// FEATURE-MAP-074: maximum nested `call_subflow` depth (recursion guard).
    static constexpr int kMaxCallDepth = 32;

    nlohmann::json actions = nlohmann::json::array();
    std::size_t pc = 0;
    int waitFrames = 0;
    bool finished = false;
    bool hadError = false;
    std::string lastError;
    bool messageBlocking = false;
    std::string messageText;
    bool playerLocked = false;
    std::map<std::string, bool> flags; ///< local fallback when no GameState callbacks are wired (tests).
    /// FEATURE-MAP-068: active `repeat` loop frames (supports nesting). Cleared in `reset()`.
    std::vector<ScriptLoopFrame> loopStack;

    /// FEATURE-MAP-074: named flows (main + in-file subflows), each a resolved actions array.
    std::map<std::string, nlohmann::json> flows;
    std::string activeFlow = "main";
    /// FEATURE-MAP-075: label name -> action index for the active flow (O(1) goto).
    std::map<std::string, std::size_t> labels;
    /// FEATURE-MAP-077: per-frame scratch variables (int/string/bool), not persisted.
    std::map<std::string, nlohmann::json> vars;
    /// FEATURE-MAP-074: saved caller frames for nested subflow calls.
    std::vector<ScriptCallFrame> callStack;

    std::function<void(const std::string&)> onShowMessage;
    std::function<void()> onCloseMessage;
    std::function<void(bool)> onLockPlayer;
    std::function<void(const std::string&, int, int)> onWarp;
    std::function<void(const std::string&)> onDebugStub;
    std::function<void(const std::string&)> onFacingHint;
    /// FEATURE-MAP-072: persistent flag access (wired to GameState). When unset, `flags` is used.
    std::function<bool(const std::string&)> onReadFlag;
    std::function<void(const std::string&, bool)> onWriteFlag;
    /// FEATURE-MAP-074: load a reusable library connector by name (returns a script document).
    std::function<nlohmann::json(const std::string&)> onLoadLibrarySubflow;
    /// FEATURE-MAP-048: map viewer hook for movement / camera opcodes. Return a value to handle the
    /// opcode (including advancing `pc` when appropriate); return `std::nullopt` if not handled.
    std::function<std::optional<ScriptStepResult>(
        ScriptRuntime&, const std::string&, const nlohmann::json&)>
        tryMapViewerScriptStep;

    void reset();
    bool loadDocument(const nlohmann::json& doc);
    ScriptStepResult stepFrame();
    /// Advance past show_message (Q / Space).
    bool tryAdvanceMessage();

    /// FEATURE-MAP-072: read/write a flag through GameState callbacks when wired, else local map.
    bool readFlag(const std::string& name) const;
    void writeFlag(const std::string& name, bool value);

    /// FEATURE-MAP-074: enter a subflow (in-file flow or library connector) as a call.
    /// Pushes the current frame and switches to the callee with seeded local variables.
    /// Returns false when the target cannot be resolved or the call depth limit is reached.
    bool callSubflow(const std::string& name, const nlohmann::json& seedVars);
    /// Pop the most recent call frame and resume the caller. Returns false at the bottom frame.
    bool returnFromCall();
    /// FEATURE-MAP-074/075: stop everything (clear the call stack and finish the script).
    void stopScript();

private:
    /// FEATURE-MAP-075: rebuild `labels` from the current `actions` (scans `label` opcodes).
    void rebuildLabels_();
};

#endif
