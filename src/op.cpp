#include "op.h"

#include <algorithm>
#include <iostream>
#include <map>
#include <optional>
#include <string>

using json = nlohmann::json;

namespace
{

/// FEATURE-MAP-077: compare two scratch-variable values with op in {==, !=, <, >}.
/// Numbers compare numerically; strings compare lexicographically; booleans compare as bools.
/// Mismatched/unsupported types yield false (except != which is true) so authoring mistakes are
/// visible but never crash.
bool compareVar(const json& a, const std::string& cmp, const json& b)
{
    if (cmp == "==")
    {
        return a == b;
    }
    if (cmp == "!=")
    {
        return a != b;
    }
    const bool less = [&]() -> bool {
        if (a.is_number() && b.is_number())
        {
            return a.get<double>() < b.get<double>();
        }
        if (a.is_string() && b.is_string())
        {
            return a.get<std::string>() < b.get<std::string>();
        }
        if (a.is_boolean() && b.is_boolean())
        {
            return a.get<bool>() < b.get<bool>();
        }
        return false;
    }();
    if (cmp == "<")
    {
        return less;
    }
    if (cmp == ">")
    {
        return !less && (a != b);
    }
    return false;
}

void stubOp(ScriptRuntime& rt, const std::string& op)
{
    if (rt.onDebugStub)
    {
        rt.onDebugStub(op);
    }
    else
    {
        std::cerr << "script stub: " << op << '\n';
    }
}

std::optional<ScriptStepResult> tryDispatchMapViewerOpcodes(ScriptRuntime& rt, const std::string& op, const json& args);

} // namespace

ScriptStepResult mapScriptDispatchOpcode(ScriptRuntime& rt, const std::string& op, const json& args)
{
    if (op == "end_script")
    {
        rt.finished = true;
        if (rt.playerLocked && rt.onLockPlayer)
        {
            rt.onLockPlayer(false);
        }
        rt.playerLocked = false;
        return ScriptStepResult::Finished;
    }
    if (op == "lock_player")
    {
        rt.playerLocked = true;
        if (rt.onLockPlayer)
        {
            rt.onLockPlayer(true);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "unlock_player")
    {
        rt.playerLocked = false;
        if (rt.onLockPlayer)
        {
            rt.onLockPlayer(false);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "wait_frames")
    {
        rt.waitFrames = std::max(0, args.value("n", 0));
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "show_message")
    {
        rt.messageText = args.value("text", std::string());
        rt.messageBlocking = true;
        if (rt.onShowMessage)
        {
            rt.onShowMessage(rt.messageText);
        }
        ++rt.pc;
        return ScriptStepResult::Yield;
    }
    if (op == "close_message")
    {
        rt.messageBlocking = false;
        rt.messageText.clear();
        if (rt.onCloseMessage)
        {
            rt.onCloseMessage();
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "set_flag")
    {
        // FEATURE-MAP-072: persistent flag via GameState callback (or local map in tests).
        const std::string name = args.value("name", std::string());
        rt.writeFlag(name, true);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "clear_flag")
    {
        const std::string name = args.value("name", std::string());
        rt.writeFlag(name, false);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "unless_flag")
    {
        const std::string name = args.value("name", std::string());
        const int skip = std::max(0, args.value("skip", 0));
        ++rt.pc;
        if (!rt.readFlag(name))
        {
            rt.pc += static_cast<std::size_t>(skip);
        }
        return ScriptStepResult::Continue;
    }
    if (op == "if_flag")
    {
        // FEATURE-MAP-068: run the block (up to matching end_if) only when the flag is set.
        // `skip` (body action count) is stamped by ScriptRuntime::resolveControlFlow on load.
        const std::string name = args.value("name", std::string());
        const int skip = std::max(0, args.value("skip", 0));
        ++rt.pc;
        if (!rt.readFlag(name))
        {
            rt.pc += static_cast<std::size_t>(skip);
        }
        return ScriptStepResult::Continue;
    }
    if (op == "set_var")
    {
        // FEATURE-MAP-077: assign a scratch variable in the current frame scope.
        const std::string name = args.value("name", std::string());
        if (!name.empty() && args.contains("value"))
        {
            rt.vars[name] = args["value"];
        }
        else if (!name.empty())
        {
            rt.vars[name] = json(0);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "if_var")
    {
        // FEATURE-MAP-077: run the block only when the comparison holds. `skip` is stamped on load.
        const std::string name = args.value("name", std::string());
        const std::string cmp = args.value("op", std::string("=="));
        const int skip = std::max(0, args.value("skip", 0));
        const json lhs = rt.vars.count(name) ? rt.vars.at(name) : json(nullptr);
        const json rhs = args.contains("value") ? args["value"] : json(nullptr);
        ++rt.pc;
        if (!compareVar(lhs, cmp, rhs))
        {
            rt.pc += static_cast<std::size_t>(skip);
        }
        return ScriptStepResult::Continue;
    }
    if (op == "end_if_var")
    {
        // FEATURE-MAP-077: block terminator marker; no effect beyond advancing.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "call_subflow")
    {
        // FEATURE-MAP-074: run a named subflow like a method, seeding its locals from `vars`.
        const std::string name = args.value("name", std::string());
        const json seed = args.contains("vars") && args["vars"].is_object() ? args["vars"] : json::object();
        ++rt.pc; // return address: resume after the call when the subflow finishes.
        if (!rt.callSubflow(name, seed))
        {
            stubOp(rt, std::string("call_subflow:") + name);
        }
        return ScriptStepResult::Continue;
    }
    if (op == "stop_script")
    {
        // FEATURE-MAP-075: end the entire script immediately, even inside a subflow.
        rt.stopScript();
        return ScriptStepResult::Finished;
    }
    if (op == "goto")
    {
        // FEATURE-MAP-075: jump to a label within the current flow, continuing below it.
        const std::string label = args.value("label", std::string());
        const auto it = rt.labels.find(label);
        if (it != rt.labels.end())
        {
            rt.pc = it->second;
        }
        else
        {
            stubOp(rt, std::string("goto:") + label);
            ++rt.pc;
        }
        return ScriptStepResult::Continue;
    }
    if (op == "label")
    {
        // FEATURE-MAP-075: named jump target; no runtime effect beyond advancing.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "comment")
    {
        // FEATURE-MAP-076: organization-only note; no runtime effect beyond advancing.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "region")
    {
        // FEATURE-MAP-076: organization-only collapsible marker; skipped by the engine.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "end_region")
    {
        // FEATURE-MAP-076: end of a region marker; skipped by the engine.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "end_if")
    {
        // FEATURE-MAP-068: block terminator marker; no effect beyond advancing.
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "repeat")
    {
        // FEATURE-MAP-068: loop the block (up to matching end_repeat) n times.
        const int n = std::max(0, args.value("n", 0));
        const int skip = std::max(0, args.value("skip", 0));
        ++rt.pc;
        if (n <= 0)
        {
            rt.pc += static_cast<std::size_t>(skip);
            return ScriptStepResult::Continue;
        }
        rt.loopStack.push_back(ScriptLoopFrame{rt.pc, n});
        return ScriptStepResult::Continue;
    }
    if (op == "end_repeat")
    {
        // FEATURE-MAP-068: decrement the active loop; jump back to the body start until it drains.
        if (!rt.loopStack.empty())
        {
            ScriptLoopFrame& top = rt.loopStack.back();
            if (--top.remaining > 0)
            {
                rt.pc = top.bodyStartPc;
                return ScriptStepResult::Continue;
            }
            rt.loopStack.pop_back();
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "warp_player")
    {
        const std::string mid = args.value("mapId", std::string());
        const int tx = args.value("x", 0);
        const int ty = args.value("y", 0);
        if (rt.onWarp && !mid.empty())
        {
            rt.onWarp(mid, tx, ty);
        }
        rt.finished = true;
        if (rt.playerLocked && rt.onLockPlayer)
        {
            rt.onLockPlayer(false);
        }
        rt.playerLocked = false;
        return ScriptStepResult::Finished;
    }
    if (op == "set_player_facing")
    {
        const std::string d = args.value("dir", std::string());
        if (rt.onFacingHint)
        {
            rt.onFacingHint(d);
        }
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "set_route_music")
    {
        if (const std::optional<ScriptStepResult> mv = tryDispatchMapViewerOpcodes(rt, op, args))
        {
            return *mv;
        }
    }
    if (op == "play_music_once")
    {
        if (const std::optional<ScriptStepResult> mv = tryDispatchMapViewerOpcodes(rt, op, args))
        {
            return *mv;
        }
    }
    if (op == "start_trainer_battle")
    {
        if (const std::optional<ScriptStepResult> mv = tryDispatchMapViewerOpcodes(rt, op, args))
        {
            return *mv;
        }
    }

    if (const std::optional<ScriptStepResult> mv = tryDispatchMapViewerOpcodes(rt, op, args))
    {
        return *mv;
    }

    stubOp(rt, op);
    ++rt.pc;
    return ScriptStepResult::Continue;
}

namespace
{

std::optional<ScriptStepResult> tryDispatchMapViewerOpcodes(ScriptRuntime& rt, const std::string& op, const json& args)
{
    if (op == "walk_to_coords")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "run_to_coords")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_north")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_south")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_east")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "face_west")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "move_camera")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "camera_zoom_in")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "camera_zoom_out")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "camera_follow_player")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    if (op == "set_route_music" || op == "play_music_once" || op == "start_trainer_battle")
    {
        if (rt.tryMapViewerScriptStep)
        {
            if (const auto r = rt.tryMapViewerScriptStep(rt, op, args))
            {
                return *r;
            }
        }
        stubOp(rt, op);
        ++rt.pc;
        return ScriptStepResult::Continue;
    }
    return std::nullopt;
}

} // namespace
