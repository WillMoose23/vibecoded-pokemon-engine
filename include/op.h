#ifndef OP_H
#define OP_H

#include "script_engine.h"

/// FEATURE-MAP-048: map script opcode dispatch (`src/op.cpp`). Opcode string literals used by
/// `tools/extract_map_script_ops.py` must appear here as `if (op == "...")` comparisons.
ScriptStepResult mapScriptDispatchOpcode(ScriptRuntime& rt, const std::string& op, const nlohmann::json& args);

#endif
