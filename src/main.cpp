#include "game.h"

// SDL window and renderer are owned by Game (see game.cpp). Phase 2 adds TTF text rendering.

int main()
{
    Game game;
    game.run();
    return 0;
}
