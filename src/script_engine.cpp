#include "script_engine.h"

#include "op.h"

namespace
{

using json = nlohmann::json;

/// FEATURE-MAP-043: coerce script value to args object for `script_1` one-key entries.
json argsFromScript1Value(const json& v)
{
    if (v.is_object())
    {
        return v;
    }
    return json::object();
}

/// Append steps from `script_1` array (each element: single-key object → op/args).
void appendScript1Array(nlohmann::json& outActions, const nlohmann::json& arr)
{
    if (!arr.is_array())
    {
        return;
    }
    for (const auto& el : arr)
    {
        if (!el.is_object() || el.empty())
        {
            continue;
        }
        if (el.size() != 1)
        {
            continue;
        }
        auto it = el.begin();
        json step;
        step["op"] = it.key();
        step["args"] = argsFromScript1Value(it.value());
        outActions.push_back(std::move(step));
    }
}

/// Append steps from `script_1` object (insertion order → op/args).
void appendScript1Object(nlohmann::json& outActions, const nlohmann::json& obj)
{
    if (!obj.is_object())
    {
        return;
    }
    for (auto it = obj.begin(); it != obj.end(); ++it)
    {
        json step;
        step["op"] = it.key();
        step["args"] = argsFromScript1Value(it.value());
        outActions.push_back(std::move(step));
    }
}

/// FEATURE-MAP-068 / FEATURE-MAP-077: stamp `args.skip` on each block opener so the flat runtime
/// can jump over the matching block without authors precomputing counts. `skip` = number of body
/// actions between the opener and its matching closer (exclusive of both). Stack-based, so nested
/// blocks resolve correctly. Unbalanced markers are left without a skip (treated as 0).
/// region/end_region and label are organization-only and intentionally excluded from pairing.
void resolveControlFlow(nlohmann::json& actions)
{
    if (!actions.is_array())
    {
        return;
    }
    std::vector<std::pair<std::size_t, std::string>> stack;
    for (std::size_t i = 0; i < actions.size(); ++i)
    {
        json& step = actions.at(i);
        if (!step.is_object() || !step.contains("op") || !step["op"].is_string())
        {
            continue;
        }
        const std::string op = step["op"].get<std::string>();
        if (op == "if_flag" || op == "repeat" || op == "if_var")
        {
            stack.emplace_back(i, op);
        }
        else if (op == "end_if" || op == "end_repeat" || op == "end_if_var")
        {
            std::string opener;
            if (op == "end_if")
            {
                opener = "if_flag";
            }
            else if (op == "end_repeat")
            {
                opener = "repeat";
            }
            else
            {
                opener = "if_var";
            }
            if (!stack.empty() && stack.back().second == opener)
            {
                const std::size_t start = stack.back().first;
                stack.pop_back();
                const std::size_t skip = i - start - 1;
                json& opStep = actions.at(start);
                if (!opStep.contains("args") || !opStep["args"].is_object())
                {
                    opStep["args"] = json::object();
                }
                opStep["args"]["skip"] = static_cast<int>(skip);
            }
        }
    }
}

/// FEATURE-MAP-074: normalize a flow value (script_1-style array or insertion-ordered object) into
/// a resolved actions array (control flow stamped). Shared by main, in-file subflows, and library.
json normalizeFlowActions(const json& flowVal)
{
    json out = json::array();
    if (flowVal.is_array())
    {
        appendScript1Array(out, flowVal);
    }
    else if (flowVal.is_object())
    {
        appendScript1Object(out, flowVal);
    }
    resolveControlFlow(out);
    return out;
}

} // namespace

void ScriptRuntime::reset()
{
    actions = nlohmann::json::array();
    pc = 0;
    waitFrames = 0;
    finished = false;
    hadError = false;
    lastError.clear();
    messageBlocking = false;
    messageText.clear();
    playerLocked = false;
    flags.clear();
    loopStack.clear();
    flows.clear();
    activeFlow = "main";
    labels.clear();
    vars.clear();
    callStack.clear();
}

void ScriptRuntime::rebuildLabels_()
{
    labels.clear();
    if (!actions.is_array())
    {
        return;
    }
    for (std::size_t i = 0; i < actions.size(); ++i)
    {
        const json& step = actions.at(i);
        if (!step.is_object() || !step.contains("op") || !step["op"].is_string())
        {
            continue;
        }
        if (step["op"].get<std::string>() != "label")
        {
            continue;
        }
        const json& a = step.contains("args") && step["args"].is_object() ? step["args"] : json::object();
        const std::string name = a.value("name", std::string());
        if (!name.empty() && labels.find(name) == labels.end())
        {
            labels[name] = i;
        }
    }
}

bool ScriptRuntime::loadDocument(const nlohmann::json& doc)
{
    reset();
    if (!doc.is_object())
    {
        lastError = "script root not object";
        hadError = true;
        finished = true;
        return false;
    }
    // FEATURE-MAP-043: prefer normalized `script_1` when it yields at least one step;
    // otherwise use legacy `actions` array (same precedence as tools/event_script_schema.py).
    nlohmann::json fromScript1 = nlohmann::json::array();
    if (doc.contains("script_1"))
    {
        const nlohmann::json& s1 = doc["script_1"];
        if (s1.is_array())
        {
            appendScript1Array(fromScript1, s1);
        }
        else if (s1.is_object())
        {
            appendScript1Object(fromScript1, s1);
        }
    }
    if (!fromScript1.empty())
    {
        actions = std::move(fromScript1);
        resolveControlFlow(actions);
    }
    else if (doc.contains("actions") && doc["actions"].is_array())
    {
        actions = doc["actions"];
        resolveControlFlow(actions);
    }
    else
    {
        actions = nlohmann::json::array();
    }

    // FEATURE-MAP-074: parse named in-file subflows so call_subflow can resolve them locally.
    flows.clear();
    flows["main"] = actions;
    if (doc.contains("subflows") && doc["subflows"].is_object())
    {
        for (auto it = doc["subflows"].begin(); it != doc["subflows"].end(); ++it)
        {
            if (it.key().empty() || it.key() == "main")
            {
                continue;
            }
            flows[it.key()] = normalizeFlowActions(it.value());
        }
    }

    activeFlow = "main";
    rebuildLabels_();
    return true;
}

bool ScriptRuntime::readFlag(const std::string& name) const
{
    if (onReadFlag)
    {
        return onReadFlag(name);
    }
    const auto it = flags.find(name);
    return it != flags.end() && it->second;
}

void ScriptRuntime::writeFlag(const std::string& name, bool value)
{
    if (name.empty())
    {
        return;
    }
    if (onWriteFlag)
    {
        onWriteFlag(name, value);
        return;
    }
    if (value)
    {
        flags[name] = true;
    }
    else
    {
        flags.erase(name);
    }
}

bool ScriptRuntime::callSubflow(const std::string& name, const nlohmann::json& seedVars)
{
    if (name.empty() || static_cast<int>(callStack.size()) >= kMaxCallDepth)
    {
        return false;
    }

    nlohmann::json target;
    auto it = flows.find(name);
    if (it != flows.end())
    {
        target = it->second;
    }
    else if (onLoadLibrarySubflow)
    {
        const nlohmann::json doc = onLoadLibrarySubflow(name);
        if (doc.is_object())
        {
            if (doc.contains("script_1"))
            {
                target = normalizeFlowActions(doc["script_1"]);
            }
            else if (doc.contains("actions"))
            {
                target = normalizeFlowActions(doc["actions"]);
            }
        }
    }
    if (!target.is_array())
    {
        return false;
    }

    ScriptCallFrame frame;
    frame.actions = std::move(actions);
    frame.pc = pc;
    frame.vars = std::move(vars);
    frame.loopStack = std::move(loopStack);
    frame.labels = std::move(labels);
    frame.flowName = activeFlow;
    callStack.push_back(std::move(frame));

    actions = std::move(target);
    pc = 0;
    loopStack.clear();
    vars.clear();
    if (seedVars.is_object())
    {
        for (auto v = seedVars.begin(); v != seedVars.end(); ++v)
        {
            vars[v.key()] = v.value();
        }
    }
    activeFlow = name;
    rebuildLabels_();
    return true;
}

bool ScriptRuntime::returnFromCall()
{
    if (callStack.empty())
    {
        return false;
    }
    ScriptCallFrame frame = std::move(callStack.back());
    callStack.pop_back();
    actions = std::move(frame.actions);
    pc = frame.pc;
    vars = std::move(frame.vars);
    loopStack = std::move(frame.loopStack);
    labels = std::move(frame.labels);
    activeFlow = std::move(frame.flowName);
    return true;
}

void ScriptRuntime::stopScript()
{
    callStack.clear();
    loopStack.clear();
    finished = true;
    if (playerLocked && onLockPlayer)
    {
        onLockPlayer(false);
    }
    playerLocked = false;
}

bool ScriptRuntime::tryAdvanceMessage()
{
    if (!messageBlocking)
    {
        return false;
    }
    messageBlocking = false;
    messageText.clear();
    if (onCloseMessage)
    {
        onCloseMessage();
    }
    return true;
}

ScriptStepResult ScriptRuntime::stepFrame()
{
    if (finished)
    {
        return ScriptStepResult::Finished;
    }
    if (waitFrames > 0)
    {
        --waitFrames;
        return ScriptStepResult::Yield;
    }
    if (messageBlocking)
    {
        return ScriptStepResult::Yield;
    }

    if (!actions.is_array() || pc >= actions.size())
    {
        // FEATURE-MAP-074: end of a subflow returns to its caller; end of main finishes the script.
        if (returnFromCall())
        {
            return ScriptStepResult::Continue;
        }
        finished = true;
        if (playerLocked && onLockPlayer)
        {
            onLockPlayer(false);
        }
        playerLocked = false;
        return ScriptStepResult::Finished;
    }

    const nlohmann::json& step = actions.at(pc);
    if (!step.is_object() || !step.contains("op"))
    {
        lastError = "bad action at pc " + std::to_string(pc);
        hadError = true;
        finished = true;
        return ScriptStepResult::Error;
    }

    const std::string op = step["op"].get<std::string>();
    const nlohmann::json& args = step.contains("args") && step["args"].is_object() ? step["args"] : nlohmann::json::object();

    return mapScriptDispatchOpcode(*this, op, args);
}
