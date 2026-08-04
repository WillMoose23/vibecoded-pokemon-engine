// FEATURE-MAP-072: standalone unit test for GameState load/save round-trip.
//
// Build (from repo root):
//   make test-game-state && ./build/test_game_state
#include "game_state.h"

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

namespace fs = std::filesystem;

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
} // namespace

int main()
{
    const fs::path tmp = fs::temp_directory_path() / "phase4_game_state_test";
    fs::create_directories(tmp);
    const std::string regPath = (tmp / "registry.json").string();
    const std::string savePath = (tmp / "save.json").string();

    {
        std::ofstream f(regPath);
        f << R"({"version":1,"flags":[{"name":"quest_started","initial":false},{"name":"got_item","initial":true}]})";
    }

    GameState gs;
    gs.load(regPath, savePath);
    check(!gs.getFlag("quest_started"), "registry default quest_started false");
    check(gs.getFlag("got_item"), "registry default got_item true");

    gs.setFlag("quest_started", true);
    gs.flushIfDirty();

    GameState gs2;
    gs2.load(regPath, savePath);
    check(gs2.getFlag("quest_started"), "persisted quest_started survives reload");
    check(gs2.getFlag("got_item"), "registry default still applied for unset keys");

    gs2.clearFlag("got_item");
    gs2.flush(true);

    GameState gs3;
    gs3.load(regPath, savePath);
    check(!gs3.getFlag("got_item"), "cleared flag persisted");

    fs::remove_all(tmp);

    if (g_failures == 0)
    {
        std::printf("test_game_state: all checks passed\n");
        return 0;
    }
    std::fprintf(stderr, "test_game_state: %d failure(s)\n", g_failures);
    return 1;
}
