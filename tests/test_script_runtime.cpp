// FEATURE-MAP-074..077: standalone unit test for the script runtime control-flow additions.
//
// Build (from repo root):
//   g++ -std=c++17 -Iinclude src/script_engine.cpp src/op.cpp tests/test_script_runtime.cpp \
//       -o build/test_script_runtime && ./build/test_script_runtime
//
// Exits non-zero on the first failed assertion.
#include "script_engine.h"

#include <cstdio>
#include <string>

namespace
{
int g_failures = 0;

void check(bool cond, const char* what)
{
    if (!cond)
    {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}

void runToEnd(ScriptRuntime& rt)
{
    int guard = 10000;
    while (guard-- > 0 && !rt.finished)
    {
        const ScriptStepResult r = rt.stepFrame();
        if (r == ScriptStepResult::Error)
        {
            break;
        }
        if (rt.messageBlocking)
        {
            rt.tryAdvanceMessage();
        }
    }
}

nlohmann::json step(const std::string& op, nlohmann::json args)
{
    return nlohmann::json{{op, std::move(args)}};
}
} // namespace

int main()
{
    using json = nlohmann::json;

    // 1) goto/label + set_var: the set_var x=99 between goto and label is skipped.
    {
        json doc;
        doc["script_1"] = json::array({
            step("set_var", {{"name", "x"}, {"value", 0}}),
            step("goto", {{"label", "skip"}}),
            step("set_var", {{"name", "x"}, {"value", 99}}),
            step("label", {{"name", "skip"}}),
            step("call_subflow", {{"name", "greet"}, {"vars", {{"msg", "hi"}}}}),
            step("set_flag", {{"name", "done"}}),
        });
        doc["subflows"]["greet"] = json::array({
            step("if_var", {{"name", "msg"}, {"op", "=="}, {"value", "hi"}}),
            step("set_flag", {{"name", "greeted"}}),
            step("end_if_var", json::object()),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.finished, "scenario1 finished");
        check(rt.vars.count("x") && rt.vars["x"].get<int>() == 0, "goto skipped set_var x=99");
        check(rt.flags["done"], "main continued after subflow return");
        check(rt.flags["greeted"], "subflow named-arg seeded if_var matched");
    }

    // 2) stop_script ends everything; the following step never runs.
    {
        json doc;
        doc["script_1"] = json::array({
            step("stop_script", json::object()),
            step("set_flag", {{"name", "never"}}),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.finished, "stop_script finished");
        check(rt.flags.find("never") == rt.flags.end(), "stop_script halted before set_flag");
    }

    // 3) if_var false skips its block; region/comment are no-ops.
    {
        json doc;
        doc["script_1"] = json::array({
            step("set_var", {{"name", "n"}, {"value", 1}}),
            step("region", {{"name", "R"}}),
            step("if_var", {{"name", "n"}, {"op", "=="}, {"value", 2}}),
            step("set_flag", {{"name", "inside"}}),
            step("end_if_var", json::object()),
            step("comment", {{"text", "note"}}),
            step("end_region", json::object()),
            step("set_flag", {{"name", "after"}}),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.flags.find("inside") == rt.flags.end(), "if_var false skipped block");
        check(rt.flags["after"], "region/comment skipped, after set");
    }

    // 4) flag callbacks override the local map.
    {
        std::map<std::string, bool> external;
        ScriptRuntime rt;
        rt.onReadFlag = [&](const std::string& n) { auto it = external.find(n); return it != external.end() && it->second; };
        rt.onWriteFlag = [&](const std::string& n, bool v) { external[n] = v; };
        json doc;
        doc["script_1"] = json::array({step("set_flag", {{"name", "ext"}})});
        rt.loadDocument(doc);
        runToEnd(rt);
        check(external["ext"], "set_flag wrote through onWriteFlag");
        check(rt.flags.find("ext") == rt.flags.end(), "callback path bypassed local flags map");
    }

    // 5) nested if_flag: outer false skips inner block entirely.
    {
        json doc;
        doc["script_1"] = json::array({
            step("if_flag", {{"name", "outer"}}),
            step("set_flag", {{"name", "inner_never"}}),
            step("if_flag", {{"name", "inner"}}),
            step("set_flag", {{"name", "deep_never"}}),
            step("end_if", json::object()),
            step("end_if", json::object()),
            step("set_flag", {{"name", "after"}}),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.flags.find("inner_never") == rt.flags.end(), "outer false skipped inner set_flag");
        check(rt.flags.find("deep_never") == rt.flags.end(), "outer false skipped nested if_flag body");
        check(rt.flags["after"], "continued after nested if_flag block");
    }

    // 6) nested repeat: outer 2 × inner 2 sets counter flag four times.
    {
        json doc;
        doc["script_1"] = json::array({
            step("set_var", {{"name", "n"}, {"value", 0}}),
            step("repeat", {{"n", 2}}),
            step("repeat", {{"n", 2}}),
            step("set_var", {{"name", "n"}, {"value", 1}}),
            step("end_repeat", json::object()),
            step("end_repeat", json::object()),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.vars["n"].get<int>() == 1, "nested repeat ran inner body four times");
    }

    // 7) in-file call_subflow returns to caller and restores caller vars.
    {
        json doc;
        doc["script_1"] = json::array({
            step("set_var", {{"name", "caller"}, {"value", "keep"}}),
            step("call_subflow", {{"name", "callee"}, {"vars", {{"local", 7}}}}),
            step("set_flag", {{"name", "resumed"}}),
        });
        doc["subflows"]["callee"] = json::array({
            step("if_var", {{"name", "local"}, {"op", "=="}, {"value", 7}}),
            step("set_flag", {{"name", "callee_ok"}}),
            step("end_if_var", json::object()),
        });
        ScriptRuntime rt;
        rt.loadDocument(doc);
        runToEnd(rt);
        check(rt.flags["callee_ok"], "subflow ran with seeded var");
        check(rt.flags["resumed"], "caller resumed after subflow");
        check(rt.vars["caller"].get<std::string>() == "keep", "caller var restored after return");
        check(rt.vars.find("local") == rt.vars.end(), "callee local not leaked to caller");
    }

    // 8) if_flag true runs body; end_if advances without re-entering.
    {
        std::map<std::string, bool> external{{"gate", true}};
        ScriptRuntime rt;
        rt.onReadFlag = [&](const std::string& n) { auto it = external.find(n); return it != external.end() && it->second; };
        rt.onWriteFlag = [&](const std::string& n, bool v) { external[n] = v; };
        json doc;
        doc["script_1"] = json::array({
            step("if_flag", {{"name", "gate"}}),
            step("set_flag", {{"name", "inside"}}),
            step("end_if", json::object()),
            step("set_flag", {{"name", "outside"}}),
        });
        rt.loadDocument(doc);
        runToEnd(rt);
        check(external["inside"], "if_flag true ran body");
        check(external["outside"], "continued after end_if");
    }

    if (g_failures == 0)
    {
        std::printf("test_script_runtime: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_script_runtime: %d failure(s)\n", g_failures);
    return 1;
}
