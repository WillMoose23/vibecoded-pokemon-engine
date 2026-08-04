#include "game.h"

#include "battle.h"

#include <SDL_image.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace
{

// All drawing uses this logical resolution; SDL scales to the actual window (any size / DPI).
constexpr int kLogicalWidth = 1280;
constexpr int kLogicalHeight = 720;
constexpr int kTextMargin = 16;
constexpr int kFontSize = 18;

constexpr int kBattlePromptBoxW = 640;
/// Fallback height if font is unavailable (matches ~4 move rows + padding).
constexpr int kBattlePromptBoxH = 150;
constexpr int kBattlePromptPadding = 10;
constexpr int kBattleMoveRows = 4;

inline int battleMovePanelHeight(TTF_Font* font)
{
    if (font == nullptr)
    {
        return kBattlePromptBoxH;
    }
    return kBattleMoveRows * TTF_FontLineSkip(font) + 2 * kBattlePromptPadding;
}
constexpr int kHealthBarW = 140;
constexpr int kHealthBarH = 12;
constexpr std::int64_t kFpsSampleWindowNs = 250000000;

constexpr int kDebugDexModalW = 440;
constexpr int kDebugDexModalH = 152;

constexpr int kSpriteTopMargin = 24;
constexpr int kSpriteScale = 4;
/// Battle corner sprites: render 30% smaller than title sprite scale (4 × 0.7 = 2.8).
constexpr int kBattleCornerScaleNumer = 7;
constexpr int kBattleCornerScaleDenom = 10;
constexpr int kGapSpriteToText = 24;

inline int battleCornerDstDim(int srcPixels)
{
    return (srcPixels * kSpriteScale * kBattleCornerScaleNumer) / kBattleCornerScaleDenom;
}

/// Foe front sprite: additional scale-down vs player battle corners (85% of player battle size).
inline int battleFoeCornerDstDim(int srcPixels)
{
    return (battleCornerDstDim(srcPixels) * 17) / 20;
}

/// Shift battle corner sprites horizontally toward screen center (10% of logical width).
constexpr int kBattleSpriteInwardShift = (kLogicalWidth * 10) / 100;
/// Move player back sprite up from the bottom edge (pixels).
constexpr int kPlayerBattleSpriteRaise = 48;
/// Gap between HP bar block and adjacent sprite edge.
constexpr int kBattleHpGap = 10;

/// FEATURE-GAME-001: title + returnToTitle() welcome text (keep in sync).
const char* const kTitleScreenHelpText =
    "Pokemon demo\n\n"
    "Press 1 — debug: choose Pokédex # (player), random foe\n"
    "Press 2 — quick battle: Squirtle vs Charmander\n"
    "Press 3 — map viewer: Overworld (world_layout.json) or any map; viewport in src/overworld_view.json; WASD\n"
    "F3 — RAM/CPU (any screen)   F4 — key list (replaces F3 when on)\n"
    "In battle: [ and ] — cycle battle background (debug)\n";

const char* const kKeybindHudLines[] = {
    "Keys — title: 1 dex  2 battle  3 map  F3 RAM/CPU  F4 this panel",
    "Pokédex modal: Enter  Backspace  0-9  Esc",
    "Battle: Esc title  [ ] bg  Q W E R moves",
    "Map list: Up Down Enter  Esc exit (Overworld = composite world_layout.json)",
    "Map view: W A S D move  Q talk  L tile grid  Esc list",
    "Overworld: W A S D  Q talk  L tile grid  Esc list",
};

// Try project font first; add fonts/default.ttf for portable builds. macOS fallbacks if missing.
const char* const kFontSearchPaths[] = {
    "fonts/default.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
};

} // namespace

bool Game::initFont()
{
    if (TTF_Init() == -1)
    {
        std::cerr << "TTF_Init Error: " << TTF_GetError() << '\n';
        return false;
    }
    ttfInitialized_ = true;

    for (const char* path : kFontSearchPaths)
    {
        font_ = TTF_OpenFont(path, kFontSize);
        if (font_ != nullptr)
        {
            break;
        }
    }

    if (font_ == nullptr)
    {
        std::cerr << "TTF_OpenFont: no font loaded. Add a .ttf at fonts/default.ttf (see kFontSearchPaths in game.cpp).\n";
    }

    return true;
}

bool Game::initImage()
{
    const int flags = IMG_INIT_PNG;
    if ((IMG_Init(flags) & flags) != flags)
    {
        std::cerr << "IMG_Init Error: " << IMG_GetError() << '\n';
        return false;
    }
    imageInitialized_ = true;
    return true;
}

bool Game::initVideo()
{
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) != 0)
    {
        std::cerr << "SDL_Init Error: " << SDL_GetError() << '\n';
        return false;
    }
    musicManager_.init();

    window = SDL_CreateWindow(
        "Pokemon RPG (C++ alpha 0.1)",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        kLogicalWidth,
        kLogicalHeight,
        SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE);

    if (!window)
    {
        std::cerr << "SDL_CreateWindow Error: " << SDL_GetError() << '\n';
        SDL_Quit();
        return false;
    }

    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer)
    {
        std::cerr << "SDL_CreateRenderer Error: " << SDL_GetError() << '\n';
        SDL_DestroyWindow(window);
        window = nullptr;
        SDL_Quit();
        return false;
    }

    // Map logical (1280x720) coords to the drawable area; scales when the window is resized.
    SDL_RenderSetLogicalSize(renderer, kLogicalWidth, kLogicalHeight);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);

    sdlInitialized = true;

    if (!initFont())
    {
        std::cerr << "Font subsystem failed to initialize.\n";
    }

    if (!initImage())
    {
        std::cerr << "SDL2_image failed to initialize; PNG sprites will be unavailable.\n";
    }

    return true;
}

void Game::destroyPokemonSprite()
{
    if (pokemonSprite_ != nullptr)
    {
        SDL_DestroyTexture(pokemonSprite_);
        pokemonSprite_ = nullptr;
    }
}

void Game::destroyCornerSprites()
{
    if (cornerBL_ != nullptr)
    {
        SDL_DestroyTexture(cornerBL_);
        cornerBL_ = nullptr;
    }
    if (cornerTR_ != nullptr)
    {
        SDL_DestroyTexture(cornerTR_);
        cornerTR_ = nullptr;
    }
}

void Game::destroyBattleBackgroundTextures()
{
    for (BattleBackgroundEntry& e : battleBackgrounds_)
    {
        if (e.texture != nullptr)
        {
            SDL_DestroyTexture(e.texture);
            e.texture = nullptr;
        }
    }
    battleBackgrounds_.clear();
}

void Game::loadBattleBackgroundTextures()
{
    destroyBattleBackgroundTextures();
    if (renderer == nullptr || !imageInitialized_)
    {
        return;
    }

    if (!battleCfg_.contains("backgrounds") || !battleCfg_["backgrounds"].is_array())
    {
        battleBackgrounds_.push_back(BattleBackgroundEntry{"black", nullptr});
        debugBattleBgIndex_ = 0;
        return;
    }

    std::string defaultId = "black";
    if (battleCfg_.contains("defaultBackgroundId") && battleCfg_["defaultBackgroundId"].is_string())
    {
        defaultId = battleCfg_["defaultBackgroundId"].get<std::string>();
    }

    debugBattleBgIndex_ = 0;
    bool matchedDefault = false;

    for (const auto& el : battleCfg_["backgrounds"])
    {
        if (!el.is_object())
        {
            continue;
        }
        std::string id = el.contains("id") ? el["id"].get<std::string>() : std::string("bg_") + std::to_string(battleBackgrounds_.size());
        std::string file = el.contains("file") ? el["file"].get<std::string>() : std::string{};
        SDL_Texture* tex = nullptr;
        if (!file.empty())
        {
            loadIntoTexture(tex, file);
        }
        battleBackgrounds_.push_back(BattleBackgroundEntry{std::move(id), tex});
        if (!matchedDefault && battleBackgrounds_.back().id == defaultId)
        {
            debugBattleBgIndex_ = battleBackgrounds_.size() - 1;
            matchedDefault = true;
        }
    }

    if (battleBackgrounds_.empty())
    {
        battleBackgrounds_.push_back(BattleBackgroundEntry{"black", nullptr});
        debugBattleBgIndex_ = 0;
    }
    else if (!matchedDefault || debugBattleBgIndex_ >= battleBackgrounds_.size())
    {
        debugBattleBgIndex_ = 0;
    }
}

void Game::drawBattleBackgroundIfActive()
{
    if (renderer == nullptr || !activeBattle_ || activeBattle_->battleEnded())
    {
        return;
    }
    if (debugBattleBgIndex_ >= battleBackgrounds_.size())
    {
        return;
    }
    SDL_Texture* tex = battleBackgrounds_[debugBattleBgIndex_].texture;
    if (tex == nullptr)
    {
        return;
    }
    SDL_Rect dst{0, 0, kLogicalWidth, kLogicalHeight};
    SDL_RenderCopy(renderer, tex, nullptr, &dst);
}

void Game::drawBattleBackgroundDebugLabel()
{
    if (renderer == nullptr || font_ == nullptr || !activeBattle_ || activeBattle_->battleEnded())
    {
        return;
    }
    if (debugBattleBgIndex_ >= battleBackgrounds_.size())
    {
        return;
    }
    const std::string& bid = battleBackgrounds_[debugBattleBgIndex_].id;
    const SDL_Color c{200, 200, 200, 255};
    const int lineSkip = TTF_FontLineSkip(font_);
    const std::string line = std::string("BG: ") + bid;
    renderText(line, kTextMargin, kLogicalHeight - lineSkip - kTextMargin, c);
}

bool Game::loadIntoTexture(SDL_Texture*& target, const std::string& path)
{
    if (target != nullptr)
    {
        SDL_DestroyTexture(target);
        target = nullptr;
    }
    if (path.empty())
    {
        return false;
    }
    if (!imageInitialized_ || renderer == nullptr)
    {
        std::cerr << "loadIntoTexture: image subsystem or renderer not ready.\n";
        return false;
    }
    target = IMG_LoadTexture(renderer, path.c_str());
    if (target == nullptr)
    {
        std::cerr << "IMG_LoadTexture(\"" << path << "\"): " << IMG_GetError() << '\n';
        return false;
    }
    return true;
}

bool Game::loadPokemonSprite(const char* relativePath)
{
    destroyPokemonSprite();
    displayTextTopY_ = kTextMargin;
    displayTextLeftX_ = kTextMargin;

    if (relativePath == nullptr || relativePath[0] == '\0')
    {
        return false;
    }

    if (!imageInitialized_ || renderer == nullptr)
    {
        std::cerr << "loadPokemonSprite: image subsystem or renderer not ready.\n";
        return false;
    }

    pokemonSprite_ = IMG_LoadTexture(renderer, relativePath);
    if (pokemonSprite_ == nullptr)
    {
        std::cerr << "IMG_LoadTexture(\"" << relativePath << "\"): " << IMG_GetError() << '\n';
        return false;
    }

    int w = 0;
    int h = 0;
    SDL_QueryTexture(pokemonSprite_, nullptr, nullptr, &w, &h);
    const int scaledW = w * kSpriteScale;
    // Stats column starts to the right of the scaled sprite (same vertical band as sprite).
    displayTextLeftX_ = kTextMargin + scaledW + kGapSpriteToText;
    displayTextTopY_ = kSpriteTopMargin;
    return true;
}

void Game::drawPokemonSprite()
{
    if (pokemonSprite_ == nullptr || renderer == nullptr)
    {
        return;
    }

    int w = 0;
    int h = 0;
    SDL_QueryTexture(pokemonSprite_, nullptr, nullptr, &w, &h);

    SDL_Rect dst{};
    dst.w = w * kSpriteScale;
    dst.h = h * kSpriteScale;
    dst.x = kTextMargin;
    dst.y = kSpriteTopMargin;

    SDL_RenderCopy(renderer, pokemonSprite_, nullptr, &dst);
}

void Game::drawCornerSprites()
{
    if (renderer == nullptr)
    {
        return;
    }

    auto drawScaled = [this](SDL_Texture* tex, int x, int y) {
        if (tex == nullptr)
        {
            return;
        }
        int w = 0;
        int h = 0;
        SDL_QueryTexture(tex, nullptr, nullptr, &w, &h);
        SDL_Rect dst{};
        dst.w = battleCornerDstDim(w);
        dst.h = battleCornerDstDim(h);
        dst.x = x;
        dst.y = y;
        SDL_RenderCopy(renderer, tex, nullptr, &dst);
    };

    if (cornerBL_ != nullptr)
    {
        int w = 0;
        int h = 0;
        SDL_QueryTexture(cornerBL_, nullptr, nullptr, &w, &h);
        const int dstH = battleCornerDstDim(h);
        const int blX = kTextMargin + kBattleSpriteInwardShift;
        const int blY = kLogicalHeight - kTextMargin - dstH - kPlayerBattleSpriteRaise;
        drawScaled(cornerBL_, blX, blY);
    }
    if (cornerTR_ != nullptr)
    {
        int w = 0;
        int h = 0;
        SDL_QueryTexture(cornerTR_, nullptr, nullptr, &w, &h);
        const int dstW = battleFoeCornerDstDim(w);
        const int dstH = battleFoeCornerDstDim(h);
        const int trX = kLogicalWidth - kTextMargin - dstW - kBattleSpriteInwardShift;
        SDL_Rect dst{};
        dst.w = dstW;
        dst.h = dstH;
        dst.x = trX;
        dst.y = kTextMargin;
        SDL_RenderCopy(renderer, cornerTR_, nullptr, &dst);
    }
}

void Game::renderText(const std::string& text, int x, int y, SDL_Color color)
{
    if (font_ == nullptr || renderer == nullptr || text.empty())
    {
        return;
    }

    const TextCacheKey key{text, color.r, color.g, color.b, color.a};
    auto it = textCache_.find(key);
    if (it == textCache_.end())
    {
        SDL_Surface* surface = TTF_RenderUTF8_Blended(font_, text.c_str(), color);
        if (surface == nullptr)
        {
            return;
        }
        SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
        if (texture == nullptr)
        {
            SDL_FreeSurface(surface);
            return;
        }
        TextCacheEntry entry{};
        entry.texture = texture;
        entry.width = surface->w;
        entry.height = surface->h;
        SDL_FreeSurface(surface);
        it = textCache_.emplace(key, entry).first;
    }
    SDL_Rect dst{static_cast<int>(x), static_cast<int>(y), it->second.width, it->second.height};
    SDL_RenderCopy(renderer, it->second.texture, nullptr, &dst);
}

void Game::clearTextCache_()
{
    for (auto& [_, entry] : textCache_)
    {
        if (entry.texture != nullptr)
        {
            SDL_DestroyTexture(entry.texture);
            entry.texture = nullptr;
        }
    }
    textCache_.clear();
}

void Game::warmStaticTextCache_()
{
    if (font_ == nullptr || renderer == nullptr)
    {
        return;
    }
    const SDL_Color title{220, 225, 240, 255};
    const SDL_Color dim{160, 165, 180, 255};
    const SDL_Color fg{170, 210, 175, 255};
    renderText("Map viewer — Up/Down  Enter  Esc back", 0, 0, title);
    renderText("No maps found under src/maps (run validate_maps or the map editor).", 0, 0, dim);
    renderText("RAM: —", 0, 0, fg);
    renderText("CPU: —", 0, 0, fg);
    renderText("FPS: —", 0, 0, fg);
    for (const char* line : kKeybindHudLines)
    {
        renderText(line, 0, 0, fg);
    }
}

void Game::setDisplayText_(std::string text)
{
    displayText_ = std::move(text);
    rebuildDisplayTextLines_();
}

void Game::rebuildDisplayTextLines_()
{
    displayTextLines_.clear();
    std::string current;
    current.reserve(displayText_.size());
    for (char ch : displayText_)
    {
        if (ch == '\n')
        {
            displayTextLines_.push_back(current);
            current.clear();
            continue;
        }
        current.push_back(ch);
    }
    displayTextLines_.push_back(current);
}

void Game::drawPerfHud_()
{
    if (!showPerfHud_ || showKeybindHud_ || renderer == nullptr || font_ == nullptr)
    {
        return;
    }

    const int lineSkip = TTF_FontLineSkip(font_);
    const SDL_Color fg{170, 210, 175, 255};
    const int pad = 8;
    const int x0 = kTextMargin;
    const int yStart = kTextMargin;

    char ramLine[96];
    char cpuLine[96];
    char fpsLine[96];
    if (perfSampler_.rssKnown())
    {
        const double mb = static_cast<double>(perfSampler_.rssBytes()) / (1024.0 * 1024.0);
        std::snprintf(ramLine, sizeof(ramLine), "RAM: %.1f MB", mb);
    }
    else
    {
        std::snprintf(ramLine, sizeof(ramLine), "RAM: —");
    }
    if (perfSampler_.cpuPercentReady())
    {
        std::snprintf(
            cpuLine, sizeof(cpuLine), "CPU: %.1f%% (of 1 core)", perfSampler_.cpuPercentSmoothed());
    }
    else
    {
        std::snprintf(cpuLine, sizeof(cpuLine), "CPU: —");
    }
    if (fpsDisplay_ > 0)
    {
        std::snprintf(fpsLine, sizeof(fpsLine), "FPS: %d", fpsDisplay_);
    }
    else
    {
        std::snprintf(fpsLine, sizeof(fpsLine), "FPS: —");
    }

    auto lineWidth = [&](const char* s) {
        int lw = 0;
        int lh = 0;
        if (s != nullptr && s[0] != '\0' && TTF_SizeUTF8(font_, s, &lw, &lh) == 0)
        {
            return lw;
        }
        return 0;
    };

    const int maxW = std::max(std::max(lineWidth(ramLine), lineWidth(cpuLine)), lineWidth(fpsLine));
    const int totalLines = 3;
    const int boxW = maxW + 2 * pad;
    const int boxH = totalLines * lineSkip + 2 * pad;

    SDL_BlendMode prevBlend = SDL_BLENDMODE_NONE;
    SDL_GetRenderDrawBlendMode(renderer, &prevBlend);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 8, 12, 10, 200);
    SDL_Rect bg{x0 - pad, yStart - pad, boxW, boxH};
    SDL_RenderFillRect(renderer, &bg);
    SDL_SetRenderDrawBlendMode(renderer, prevBlend);

    renderText(ramLine, x0, yStart, fg);
    renderText(cpuLine, x0, yStart + lineSkip, fg);
    renderText(fpsLine, x0, yStart + 2 * lineSkip, fg);
}

void Game::drawKeybindHud_()
{
    if (!showKeybindHud_ || renderer == nullptr || font_ == nullptr)
    {
        return;
    }

    const int lineSkip = TTF_FontLineSkip(font_);
    const SDL_Color fg{170, 210, 175, 255};
    const int pad = 8;
    const int x0 = kTextMargin;
    const int yStart = kTextMargin;

    auto lineWidth = [&](const char* s) {
        int lw = 0;
        int lh = 0;
        if (s != nullptr && s[0] != '\0' && TTF_SizeUTF8(font_, s, &lw, &lh) == 0)
        {
            return lw;
        }
        return 0;
    };

    int maxW = 0;
    for (const char* s : kKeybindHudLines)
    {
        maxW = std::max(maxW, lineWidth(s));
    }
    const int totalLines = static_cast<int>(sizeof(kKeybindHudLines) / sizeof(kKeybindHudLines[0]));
    const int boxW = maxW + 2 * pad;
    const int boxH = totalLines * lineSkip + 2 * pad;

    SDL_BlendMode prevBlend = SDL_BLENDMODE_NONE;
    SDL_GetRenderDrawBlendMode(renderer, &prevBlend);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 8, 12, 10, 200);
    SDL_Rect bg{x0 - pad, yStart - pad, boxW, boxH};
    SDL_RenderFillRect(renderer, &bg);
    SDL_SetRenderDrawBlendMode(renderer, prevBlend);

    int y = yStart;
    for (const char* s : kKeybindHudLines)
    {
        renderText(s, x0, y, fg);
        y += lineSkip;
    }
}

void Game::drawDisplayText()
{
    if (font_ == nullptr)
    {
        return;
    }

    const SDL_Color white{255, 255, 255, 255};
    const int lineSkip = TTF_FontLineSkip(font_);
    const int x = displayTextLeftX_;
    int y = displayTextTopY_;

    for (const std::string& line : displayTextLines_)
    {
        if (!line.empty())
        {
            renderText(line, x, y, white);
        }
        y += lineSkip;
    }
}

Game::Game()
{
    try
    {
        std::ifstream file("src/monster.json");
        if (!file)
        {
            std::cerr << "Failed to open src/monster.json\n";
            return;
        }
        file >> pokedb;
    }
    catch (const std::exception& e)
    {
        std::cerr << "Failed to read or parse monster.json: " << e.what() << '\n';
        return;
    }

    try
    {
        std::ifstream bf("src/battle.json");
        if (bf)
        {
            bf >> battleCfg_;
        }
    }
    catch (const std::exception& e)
    {
        std::cerr << "Failed to read battle.json: " << e.what() << '\n';
        battleCfg_ = json::object();
    }
    if (!battleCfg_.contains("backgrounds") || !battleCfg_["backgrounds"].is_array())
    {
        battleCfg_["defaultBackgroundId"] = "black";
        battleCfg_["backgrounds"] = json::array({json::object({{"id", "black"}, {"file", ""}})});
    }

    rebuildPokedexIndex_();

    // FEATURE-MAP-072/073: load persistent flags (registry defaults overlaid by the save file),
    // enable crash-safety flushing, and optionally enable debug dumps.
    gameState_.load("src/maps/scripts/flag_registry.json", "save/game_state.json");
    if (const char* dbg = std::getenv("EVENT_DEBUG_STATE"); dbg != nullptr && dbg[0] != '\0' && dbg[0] != '0')
    {
        gameState_.setDebugDumps(true);
        gameState_.debugDump("startup");
    }
    gameState_.enableCrashSafety();

    if (!initVideo())
    {
        std::cerr << "Video initialization failed; run() will exit early.\n";
    }
    else if (renderer != nullptr)
    {
        loadBattleBackgroundTextures();
        warmStaticTextCache_();
    }
}

Game::~Game()
{
    // FEATURE-MAP-072: persist any pending flag changes on clean shutdown.
    gameState_.flush(true);
    destroyMapViewTextures_();
    activeBattle_.reset();
    destroyCornerSprites();
    destroyPokemonSprite();
    destroyBattleBackgroundTextures();
    clearTextCache_();

    if (font_ != nullptr)
    {
        TTF_CloseFont(font_);
        font_ = nullptr;
    }
    if (ttfInitialized_)
    {
        TTF_Quit();
        ttfInitialized_ = false;
    }

    if (imageInitialized_)
    {
        IMG_Quit();
        imageInitialized_ = false;
    }

    if (renderer != nullptr)
    {
        SDL_DestroyRenderer(renderer);
        renderer = nullptr;
    }
    if (window != nullptr)
    {
        SDL_DestroyWindow(window);
        window = nullptr;
    }
    if (sdlInitialized)
    {
        SDL_Quit();
        sdlInitialized = false;
    }
}

void Game::run()
{
    if (renderer == nullptr)
    {
        std::cerr << "Renderer not available; skipping main loop.\n";
        return;
    }

    setDisplayText_(kTitleScreenHelpText);
    displayTextTopY_ = kTextMargin;
    displayTextLeftX_ = kTextMargin;
    showMainSpriteAndStats_ = true;

    bool running = true;
    SDL_Event event;

    while (running)
    {
        while (SDL_PollEvent(&event))
        {
            if (event.type == SDL_QUIT)
            {
                running = false;
            }
            else if (event.type == SDL_KEYDOWN)
            {
                const SDL_Keycode key = event.key.keysym.sym;
                if (key == SDLK_F3 && event.key.repeat == 0)
                {
                    showKeybindHud_ = false;
                    showPerfHud_ = !showPerfHud_;
                    continue;
                }
                if (key == SDLK_F4 && event.key.repeat == 0)
                {
                    showPerfHud_ = false;
                    showKeybindHud_ = !showKeybindHud_;
                    continue;
                }
                if (mapUiMode_ != MapUiMode::None)
                {
                    if (overworldBattleActive_)
                    {
                        if (event.key.repeat == 0)
                        {
                            handleOverworldBattleKey_(key);
                        }
                    }
                    else
                    {
                        handleMapUiKey_(key, event.key.repeat);
                    }
                    continue;
                }
                if (key == SDLK_ESCAPE && activeBattle_)
                {
                    returnToTitle();
                }
                else if (key == SDLK_ESCAPE && debugDexEntryActive_)
                {
                    debugDexEntryActive_ = false;
                    debugDexInput_.clear();
                    debugDexError_.clear();
                }
                else if (debugDexEntryActive_ && event.key.repeat == 0)
                {
                    if (key == SDLK_RETURN || key == SDLK_KP_ENTER)
                    {
                        tryConfirmDebugDexEntry();
                    }
                    else if (key == SDLK_BACKSPACE)
                    {
                        if (!debugDexInput_.empty())
                        {
                            debugDexInput_.pop_back();
                        }
                        debugDexError_.clear();
                    }
                    else if (debugDexInput_.size() < 4)
                    {
                        int digit = -1;
                        if (key >= SDLK_0 && key <= SDLK_9)
                        {
                            digit = key - SDLK_0;
                        }
                        else
                        {
                            switch (key)
                            {
                            case SDLK_KP_0:
                                digit = 0;
                                break;
                            case SDLK_KP_1:
                                digit = 1;
                                break;
                            case SDLK_KP_2:
                                digit = 2;
                                break;
                            case SDLK_KP_3:
                                digit = 3;
                                break;
                            case SDLK_KP_4:
                                digit = 4;
                                break;
                            case SDLK_KP_5:
                                digit = 5;
                                break;
                            case SDLK_KP_6:
                                digit = 6;
                                break;
                            case SDLK_KP_7:
                                digit = 7;
                                break;
                            case SDLK_KP_8:
                                digit = 8;
                                break;
                            case SDLK_KP_9:
                                digit = 9;
                                break;
                            default:
                                break;
                            }
                        }
                        if (digit >= 0)
                        {
                            debugDexInput_.push_back(static_cast<char>('0' + digit));
                            debugDexError_.clear();
                        }
                    }
                }
                else if (event.key.repeat == 0)
                {
                    if (key == SDLK_1 || key == SDLK_KP_1)
                    {
                        if (!activeBattle_ && !debugDexEntryActive_)
                        {
                            debugDexEntryActive_ = true;
                            debugDexInput_.clear();
                            debugDexError_.clear();
                        }
                    }
                    else if (key == SDLK_2 || key == SDLK_KP_2)
                    {
                        if (!activeBattle_ && !debugDexEntryActive_)
                        {
                            activeBattle_ = std::make_unique<Battle>(pokedb, "Squirtle", "Charmander");
                            applyBattleView(*activeBattle_);
                        }
                    }
                    else if (key == SDLK_3 || key == SDLK_KP_3)
                    {
                        if (!activeBattle_ && !debugDexEntryActive_)
                        {
                            openMapPicker_();
                        }
                    }
                    else if (activeBattle_ && !activeBattle_->battleEnded())
                    {
                        if (key == SDLK_LEFTBRACKET || key == SDLK_RIGHTBRACKET)
                        {
                            if (!battleBackgrounds_.empty())
                            {
                                if (key == SDLK_LEFTBRACKET)
                                {
                                    debugBattleBgIndex_ =
                                        (debugBattleBgIndex_ + battleBackgrounds_.size() - 1) % battleBackgrounds_.size();
                                }
                                else
                                {
                                    debugBattleBgIndex_ = (debugBattleBgIndex_ + 1) % battleBackgrounds_.size();
                                }
                            }
                        }
                        else
                        {
                            int slot = -1;
                            if (key == SDLK_q)
                            {
                                slot = 0;
                            }
                            else if (key == SDLK_w)
                            {
                                slot = 1;
                            }
                            else if (key == SDLK_e)
                            {
                                slot = 2;
                            }
                            else if (key == SDLK_r)
                            {
                                slot = 3;
                            }
                            if (slot >= 0)
                            {
                                activeBattle_->executeTurn(slot);
                                if (activeBattle_->battleEnded())
                                {
                                    returnToTitle();
                                }
                            }
                        }
                    }
                }
            }
        }

        if (!overworldBattleActive_)
        {
            tickMapScript_();
            tickMapPlayerWalk_();
        }

        perfSampler_.update();
        {
            const auto now = std::chrono::steady_clock::now();
            const std::int64_t nowNs =
                std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
            if (fpsWindowStartNs_ == 0)
            {
                fpsWindowStartNs_ = nowNs;
                fpsWindowFrames_ = 0;
            }
            ++fpsWindowFrames_;
            const std::int64_t elapsedNs = nowNs - fpsWindowStartNs_;
            if (elapsedNs >= kFpsSampleWindowNs)
            {
                const double elapsedSec = static_cast<double>(elapsedNs) * 1.0e-9;
                fpsDisplay_ = elapsedSec > 0.0 ? static_cast<int>(fpsWindowFrames_ / elapsedSec + 0.5) : 0;
                fpsWindowStartNs_ = nowNs;
                fpsWindowFrames_ = 0;
            }
        }

        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
        SDL_RenderClear(renderer);
        if (mapUiMode_ == MapUiMode::PickMap)
        {
            drawMapPicker_();
        }
        else if (mapUiMode_ == MapUiMode::ViewMap)
        {
            drawMapView_();
            if (overworldBattleActive_ && activeBattle_)
            {
                drawBattleBackgroundIfActive();
                drawCornerSprites();
                drawBattleHealthBars(*activeBattle_);
                drawBattleMovePrompt(*activeBattle_);
            }
        }
        else if (mapUiMode_ == MapUiMode::ViewWorld)
        {
            drawWorldLayoutView_();
            if (overworldBattleActive_ && activeBattle_)
            {
                drawBattleBackgroundIfActive();
                drawCornerSprites();
                drawBattleHealthBars(*activeBattle_);
                drawBattleMovePrompt(*activeBattle_);
            }
        }
        else
        {
            drawBattleBackgroundIfActive();
            drawCornerSprites();
            if (activeBattle_)
            {
                drawBattleHealthBars(*activeBattle_);
                drawBattleMovePrompt(*activeBattle_);
                drawBattleBackgroundDebugLabel();
            }
            else if (showMainSpriteAndStats_)
            {
                drawPokemonSprite();
                drawDisplayText();
            }
        }
        if (debugDexEntryActive_)
        {
            drawDebugDexModal();
        }
        if (showKeybindHud_)
        {
            drawKeybindHud_();
        }
        else if (showPerfHud_)
        {
            drawPerfHud_();
        }
        SDL_RenderPresent(renderer);

        SDL_Delay(1);
    }
}

void Game::createPokemon(json& data, const std::string& key)
{
    try
    {
        Pokemon temp(data, key);
        std::ostringstream oss;
        oss << temp;
        setDisplayText_(oss.str());
        std::cout << displayText_ << std::endl;
    }
    catch (const std::exception& e)
    {
        const std::string msg = std::string("createPokemon: ") + e.what();
        std::cerr << msg << '\n';
        setDisplayText_(msg);
    }
}

void Game::applyBattleView(const Battle& battle)
{
    try
    {
        std::ostringstream oss;
        oss << battle.player();
        std::cout << oss.str() << std::endl;

        showMainSpriteAndStats_ = false;
        setDisplayText_("");
        destroyPokemonSprite();

        destroyCornerSprites();
        loadIntoTexture(cornerBL_, battle.player().backSpritePath());
        loadIntoTexture(cornerTR_, battle.foe().frontSpritePath());
    }
    catch (const std::exception& e)
    {
        const std::string msg = std::string("applyBattleView: ") + e.what();
        std::cerr << msg << '\n';
        showMainSpriteAndStats_ = true;
        setDisplayText_(msg);
        activeBattle_.reset();
    }
}

void Game::drawHealthBar(int x, int y, int w, int h, int current, int max, const std::string& label)
{
    if (renderer == nullptr || font_ == nullptr)
    {
        return;
    }
    const SDL_Color white{255, 255, 255, 255};
    const int lineSkip = TTF_FontLineSkip(font_);
    std::ostringstream caption;
    caption << label << "  " << current << "/" << max;
    renderText(caption.str(), x, y - lineSkip - 2, white);

    SDL_Rect bg{x, y, w, h};
    SDL_SetRenderDrawColor(renderer, 40, 40, 40, 255);
    SDL_RenderFillRect(renderer, &bg);

    int fillW = 0;
    if (max > 0)
    {
        fillW = static_cast<int>(static_cast<long long>(w) * current / max);
    }
    if (fillW > w)
    {
        fillW = w;
    }
    if (fillW < 0)
    {
        fillW = 0;
    }
    SDL_Rect fill{x, y, fillW, h};
    const double ratio = max > 0 ? static_cast<double>(current) / static_cast<double>(max) : 0.0;
    if (ratio >= 0.5)
    {
        SDL_SetRenderDrawColor(renderer, 40, 180, 60, 255);
    }
    else if (ratio >= 0.25)
    {
        SDL_SetRenderDrawColor(renderer, 220, 200, 40, 255);
    }
    else
    {
        SDL_SetRenderDrawColor(renderer, 200, 50, 50, 255);
    }
    SDL_RenderFillRect(renderer, &fill);
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    SDL_RenderDrawRect(renderer, &bg);
}

void Game::drawBattleHealthBars(const Battle& battle)
{
    // Each Pokémon's HP bar sits on the opponent's side of the field (near the other sprite).
    const int lineSkip = (font_ != nullptr) ? TTF_FontLineSkip(font_) : 20;

    int swBl = 0;
    int shBl = 0;
    int swTr = 0;
    if (cornerBL_ != nullptr)
    {
        SDL_QueryTexture(cornerBL_, nullptr, nullptr, &swBl, &shBl);
    }
    if (cornerTR_ != nullptr)
    {
        SDL_QueryTexture(cornerTR_, nullptr, nullptr, &swTr, nullptr);
    }

    const int blDstH = (cornerBL_ != nullptr) ? battleCornerDstDim(shBl) : 0;
    const int trDstW = (cornerTR_ != nullptr) ? battleFoeCornerDstDim(swTr) : 0;

    const int blX = kTextMargin + kBattleSpriteInwardShift;
    const int blY =
        (cornerBL_ != nullptr && blDstH > 0)
            ? (kLogicalHeight - kTextMargin - blDstH - kPlayerBattleSpriteRaise)
            : (kLogicalHeight - battleMovePanelHeight(font_) - kTextMargin - 100);
    const int trX =
        (cornerTR_ != nullptr && trDstW > 0)
            ? (kLogicalWidth - kTextMargin - trDstW - kBattleSpriteInwardShift)
            : (kLogicalWidth / 2);
    constexpr int trY = kTextMargin;

    // Player status: upper area near foe (to the left of the foe sprite, "middle-right").
    int playerBarX = kLogicalWidth - kTextMargin - kHealthBarW;
    int playerHpBarY = 36;
    if (cornerTR_ != nullptr && trDstW > 0)
    {
        playerBarX = std::max(kTextMargin, trX - kBattleHpGap - kHealthBarW);
        playerHpBarY = trY + 16;
    }

    // Foe status: above player sprite on the left ("middle-left").
    int foeBarX = kTextMargin;
    int foeHpBarY = kLogicalHeight - battleMovePanelHeight(font_) - kTextMargin - 28;
    if (cornerBL_ != nullptr && blDstH > 0)
    {
        foeBarX = blX;
        const int desiredBarTop = blY - kBattleHpGap - kHealthBarH - lineSkip - 8;
        foeHpBarY = std::max(kTextMargin + lineSkip * 2, desiredBarTop);
    }

    drawHealthBar(
        playerBarX + 200,
        playerHpBarY + 370,
        kHealthBarW,
        kHealthBarH,
        battle.playerCurrentHp(),
        battle.playerMaxHp(),
        battle.playerSpeciesKey());

    drawHealthBar(
        foeBarX + 175,
        foeHpBarY - 40,
        kHealthBarW,
        kHealthBarH,
        battle.foeCurrentHp(),
        battle.foeMaxHp(),
        battle.foeSpeciesKey());
}

void Game::returnToTitle()
{
    overworldBattleActive_ = false;
    activeBattle_.reset();
    destroyCornerSprites();
    showMainSpriteAndStats_ = true;
    setDisplayText_(kTitleScreenHelpText);
    displayTextTopY_ = kTextMargin;
    displayTextLeftX_ = kTextMargin;
}

void Game::startOverworldWildBattle_(const std::string& foeSpeciesKey)
{
    if (pokedb.is_null() || foeSpeciesKey.empty())
    {
        return;
    }
    if (!pokedb.contains(kPokemonDbKey) || !pokedb[kPokemonDbKey].is_object())
    {
        return;
    }
    const json& pokemon = pokedb[kPokemonDbKey];
    std::string playerKey = playerSpeciesKey_;
    if (!pokemon.contains(playerKey))
    {
        if (!speciesKeys_.empty())
        {
            playerKey = speciesKeys_.front();
        }
        else
        {
            return;
        }
    }
    if (!pokemon.contains(foeSpeciesKey))
    {
        return;
    }
    activeBattle_ = std::make_unique<Battle>(pokedb, playerKey, foeSpeciesKey);
    applyBattleView(*activeBattle_);
    overworldBattleActive_ = true;
    showMainSpriteAndStats_ = false;
}

void Game::endOverworldBattle_(bool playerWon)
{
    const bool scripted = scriptedTrainerBattleActive_;
    overworldBattleActive_ = false;
    scriptedTrainerBattleActive_ = false;
    clearScriptedBattleState_();
    activeBattle_.reset();
    destroyCornerSprites();
    reloadMapPlayerSpriteTexture_();
    if (scripted)
    {
        resolveScriptedTrainerBattleEnd_(playerWon);
        return;
    }
    if (!playerWon)
    {
        setDisplayText_("You were defeated...");
    }
    else
    {
        setDisplayText_("");
    }
}

void Game::clearScriptedBattleState_()
{
    scriptedBattleTrainers_.clear();
    scriptedBattleTrainerIdx_ = 0;
    scriptedBattleFoeMonIdx_ = 0;
    scriptedBattlePlayerParty_.clear();
    scriptedBattlePlayerMonIdx_ = 0;
    scriptedBattlePlayerTurnCount_ = 0;
    scriptedBattleScriptedLossTurns_ = 0;
}

void Game::setBattleBackgroundById_(const std::string& bgId)
{
    if (bgId.empty() || battleBackgrounds_.empty())
    {
        return;
    }
    for (std::size_t i = 0; i < battleBackgrounds_.size(); ++i)
    {
        if (battleBackgrounds_[i].id == bgId)
        {
            debugBattleBgIndex_ = i;
            return;
        }
    }
}

void Game::parseScriptedBattleParties_(const nlohmann::json& effective)
{
    scriptedBattleTrainers_.clear();
    scriptedBattleTrainerIdx_ = 0;
    scriptedBattleFoeMonIdx_ = 0;
    scriptedBattlePlayerMonIdx_ = 0;
    scriptedBattlePlayerTurnCount_ = 0;

    if (effective.contains("trainers") && effective["trainers"].is_array())
    {
        for (const auto& tr : effective["trainers"])
        {
            if (!tr.is_object())
            {
                continue;
            }
            std::vector<ScriptedBattleMon> party;
            if (tr.contains("party") && tr["party"].is_array())
            {
                for (const auto& mon : tr["party"])
                {
                    if (!mon.is_object())
                    {
                        continue;
                    }
                    ScriptedBattleMon entry;
                    entry.species = mon.value("species", std::string("Pidgey"));
                    entry.level = std::max(1, mon.value("level", 5));
                    party.push_back(std::move(entry));
                }
            }
            if (!party.empty())
            {
                scriptedBattleTrainers_.push_back(std::move(party));
            }
            if (scriptedBattleTrainers_.size() >= 2)
            {
                break;
            }
        }
    }
    if (scriptedBattleTrainers_.empty())
    {
        scriptedBattleTrainers_.push_back({ScriptedBattleMon{"Pidgey", 5}});
    }

    scriptedBattlePlayerParty_.clear();
    std::string playerKey = playerSpeciesKey_;
    if (!pokedb.contains(kPokemonDbKey) || !pokedb[kPokemonDbKey].is_object())
    {
        playerKey = speciesKeys_.empty() ? std::string("Squirtle") : speciesKeys_.front();
    }
    else
    {
        const json& pokemon = pokedb[kPokemonDbKey];
        if (playerKey.empty() || !pokemon.contains(playerKey))
        {
            playerKey = speciesKeys_.empty() ? std::string("Squirtle") : speciesKeys_.front();
        }
    }
    scriptedBattlePlayerParty_.push_back(ScriptedBattleMon{playerKey, 50});
}

bool Game::startScriptedBattleEncounter_()
{
    if (scriptedBattleTrainerIdx_ >= scriptedBattleTrainers_.size())
    {
        return false;
    }
    const auto& party = scriptedBattleTrainers_[scriptedBattleTrainerIdx_];
    if (scriptedBattleFoeMonIdx_ >= party.size())
    {
        return false;
    }
    if (scriptedBattlePlayerMonIdx_ >= scriptedBattlePlayerParty_.size())
    {
        return false;
    }
    const ScriptedBattleMon& foe = party[scriptedBattleFoeMonIdx_];
    const ScriptedBattleMon& player = scriptedBattlePlayerParty_[scriptedBattlePlayerMonIdx_];
    if (!pokedb.contains(kPokemonDbKey) || !pokedb[kPokemonDbKey].is_object())
    {
        return false;
    }
    const json& pokemon = pokedb[kPokemonDbKey];
    if (!pokemon.contains(foe.species) || !pokemon.contains(player.species))
    {
        return false;
    }
    activeBattle_ = std::make_unique<Battle>(
        pokedb, player.species, foe.species, "", "", player.level, foe.level);
    applyBattleView(*activeBattle_);
    updateScriptedBattleOhko_();
    return true;
}

void Game::updateScriptedBattleOhko_()
{
    if (!activeBattle_ || !scriptedTrainerBattleActive_)
    {
        return;
    }
    const bool ohko = scriptedBattleOutcomeMode_ == "scripted_loss" && scriptedBattleScriptedLossTurns_ > 0
        && scriptedBattlePlayerTurnCount_ >= scriptedBattleScriptedLossTurns_;
    activeBattle_->setFoeOhko(ohko);
}

bool Game::tryRotateScriptedBattle_(bool playerWon)
{
    if (!scriptedTrainerBattleActive_)
    {
        return false;
    }
    if (playerWon)
    {
        ++scriptedBattleFoeMonIdx_;
        if (scriptedBattleFoeMonIdx_ < scriptedBattleTrainers_[scriptedBattleTrainerIdx_].size())
        {
            return startScriptedBattleEncounter_();
        }
        ++scriptedBattleTrainerIdx_;
        scriptedBattleFoeMonIdx_ = 0;
        if (scriptedBattleTrainerIdx_ < scriptedBattleTrainers_.size())
        {
            return startScriptedBattleEncounter_();
        }
        return false;
    }
    ++scriptedBattlePlayerMonIdx_;
    if (scriptedBattlePlayerMonIdx_ < scriptedBattlePlayerParty_.size())
    {
        return startScriptedBattleEncounter_();
    }
    return false;
}

void Game::startScriptedTrainerBattleFromOpcode_(const json& args)
{
    // FEATURE-MAP-088: merge library battle config with inline opcode args.
    // Priority: inline args > library battleId > defaults.
    json effective = json::object();
    const std::string battleId = args.value("battleId", std::string());
    if (!battleId.empty())
    {
        // Load library battle JSON: src/maps/scripts/_library/battles/<id>.json
        const std::string libPath =
            std::string("src/maps/scripts/_library/battles/") + battleId + ".json";
        std::ifstream libFile(libPath);
        if (libFile.is_open())
        {
            try
            {
                json libDef = json::parse(libFile);
                if (libDef.is_object())
                {
                    effective = libDef;
                }
            }
            catch (...)
            {
            }
        }
    }
    // Overlay inline args onto the library base (non-empty / non-zero values win).
    for (const auto& [k, v] : args.items())
    {
        if (k == "battleId")
        {
            continue;
        }
        const bool overrideVal =
            (v.is_string() && !v.get<std::string>().empty()) ||
            (v.is_number() && v.get<double>() != 0.0) ||
            (v.is_array() && !v.empty()) ||
            (v.is_boolean());
        if (overrideVal || !effective.contains(k))
        {
            effective[k] = v;
        }
    }

    const std::string music = effective.value("music", std::string());
    if (!music.empty())
    {
        musicManager_.playBattleMusic(music, 0);
    }
    scriptedBattleOutcomeMode_ = effective.value("outcomeMode", std::string("normal"));
    scriptedBattleScriptedLossTurns_ = std::max(0, effective.value("scriptedLossTurns", 0));

    // Store opcode-level lossWarp for priority chain in executeBattleLossWarp_.
    pendingLossWarpMapId_.clear();
    pendingLossWarpX_ = 0;
    pendingLossWarpY_ = 0;
    if (effective.contains("lossWarp") && effective["lossWarp"].is_object())
    {
        const auto& lw = effective["lossWarp"];
        const std::string lwMap = lw.value("mapId", std::string());
        if (!lwMap.empty())
        {
            pendingLossWarpMapId_ = lwMap;
            pendingLossWarpX_ = lw.value("x", 0);
            pendingLossWarpY_ = lw.value("y", 0);
        }
    }

    const std::string bgId = effective.value("background", std::string());
    if (!bgId.empty())
    {
        setBattleBackgroundById_(bgId);
    }

    parseScriptedBattleParties_(effective);
    overworldBattleActive_ = true;
    scriptedTrainerBattleActive_ = true;
    showMainSpriteAndStats_ = false;
    if (!startScriptedBattleEncounter_())
    {
        overworldBattleActive_ = false;
        scriptedTrainerBattleActive_ = false;
        clearScriptedBattleState_();
    }
}

void Game::resolveScriptedTrainerBattleEnd_(bool playerWon)
{
    if (!mapScript_)
    {
        setDisplayText_(playerWon ? "" : "You were defeated...");
        return;
    }
    const std::string mode = scriptedBattleOutcomeMode_;
    bool lossWarp = false;
    if (mode == "scripted_loss")
    {
        lossWarp = true;
    }
    else if (mode == "normal" && !playerWon)
    {
        lossWarp = true;
    }
    if (lossWarp)
    {
        mapScriptWasBattleLoss_ = true;
        executeBattleLossWarp_();
        mapScript_->stopScript();
        mapScriptBattleYielding_ = false;
        setDisplayText_("You were defeated...");
        return;
    }
    if (mapScriptBattleYielding_ && mapScript_)
    {
        ++mapScript_->pc;
        mapScriptBattleYielding_ = false;
    }
    setDisplayText_(playerWon ? "" : "You blacked out... (scripted win continues)");
}

void Game::executeBattleLossWarp_()
{
    // Priority: opcode lossWarp > map healPoint > global default (overworld_view.json).
    std::string mapId;
    int tx = 0;
    int ty = 0;
    if (!pendingLossWarpMapId_.empty())
    {
        mapId = pendingLossWarpMapId_;
        tx = pendingLossWarpX_;
        ty = pendingLossWarpY_;
    }
    else if (viewMapData_.healPoint.mapId.size() > 0)
    {
        mapId = viewMapData_.healPoint.mapId;
        tx = viewMapData_.healPoint.x;
        ty = viewMapData_.healPoint.y;
    }
    else if (!defaultHealMapId_.empty())
    {
        mapId = defaultHealMapId_;
        tx = defaultHealX_;
        ty = defaultHealY_;
    }
    pendingLossWarpMapId_.clear();
    pendingLossWarpX_ = 0;
    pendingLossWarpY_ = 0;
    if (!mapId.empty() && mapScript_ && mapScript_->onWarp)
    {
        mapScript_->onWarp(mapId, tx, ty);
    }
}

bool Game::handleOverworldBattleKey_(SDL_Keycode key)
{
    if (!overworldBattleActive_ || !activeBattle_ || activeBattle_->battleEnded())
    {
        return false;
    }
    int slot = -1;
    if (key == SDLK_q)
    {
        slot = 0;
    }
    else if (key == SDLK_w)
    {
        slot = 1;
    }
    else if (key == SDLK_e)
    {
        slot = 2;
    }
    else if (key == SDLK_r)
    {
        slot = 3;
    }
    if (slot < 0)
    {
        return false;
    }
    activeBattle_->executeTurn(slot);
    if (scriptedTrainerBattleActive_)
    {
        ++scriptedBattlePlayerTurnCount_;
        updateScriptedBattleOhko_();
    }
    if (activeBattle_->battleEnded())
    {
        const bool won = activeBattle_->playerWon();
        if (tryRotateScriptedBattle_(won))
        {
            return true;
        }
        endOverworldBattle_(won);
    }
    return true;
}

int Game::maxPokedexNum() const
{
    if (pokedexNumToSpecies_.empty())
    {
        return 1;
    }
    int m = 1;
    for (const auto& [dex, _] : pokedexNumToSpecies_)
    {
        m = std::max(m, dex);
    }
    return m;
}

std::optional<std::string> Game::speciesKeyForPokedexNum(int n) const
{
    const auto it = pokedexNumToSpecies_.find(n);
    return it == pokedexNumToSpecies_.end() ? std::nullopt : std::optional<std::string>(it->second);
}

std::optional<std::string> Game::pickRandomFoeKey(const std::string& playerKey) const
{
    std::vector<std::string> candidates;
    candidates.reserve(speciesKeys_.size());
    for (const std::string& key : speciesKeys_)
    {
        if (key != playerKey)
        {
            candidates.push_back(key);
        }
    }
    if (candidates.empty())
    {
        return std::nullopt;
    }
    return candidates[static_cast<size_t>(random(0, static_cast<int>(candidates.size()) - 1))];
}

void Game::rebuildPokedexIndex_()
{
    pokedexNumToSpecies_.clear();
    speciesKeys_.clear();
    if (!pokedb.contains(kPokemonDbKey) || !pokedb[kPokemonDbKey].is_object())
    {
        return;
    }
    for (const auto& el : pokedb[kPokemonDbKey].items())
    {
        speciesKeys_.push_back(el.key());
        const auto& v = el.value();
        if (!v.contains("pokedexNum") || !v["pokedexNum"].is_number_integer())
        {
            continue;
        }
        const int n = v["pokedexNum"].get<int>();
        if (n >= 1 && pokedexNumToSpecies_.find(n) == pokedexNumToSpecies_.end())
        {
            pokedexNumToSpecies_[n] = el.key();
        }
    }
}

void Game::tryConfirmDebugDexEntry()
{
    debugDexError_.clear();
    if (debugDexInput_.empty())
    {
        debugDexError_ = "Enter a number (1–max).";
        return;
    }
    int n = 0;
    try
    {
        n = std::stoi(debugDexInput_);
    }
    catch (const std::exception&)
    {
        debugDexError_ = "Invalid number.";
        return;
    }
    const int mx = maxPokedexNum();
    if (n < 1 || n > mx)
    {
        debugDexError_ = "Out of range (1–" + std::to_string(mx) + ").";
        return;
    }
    const auto pk = speciesKeyForPokedexNum(n);
    if (!pk.has_value())
    {
        debugDexError_ = "No species for that #.";
        return;
    }
    const auto foe = pickRandomFoeKey(*pk);
    if (!foe.has_value())
    {
        debugDexError_ = "Could not pick foe.";
        return;
    }
    const std::string playerKey = *pk;
    const std::string foeKey = *foe;
    debugDexEntryActive_ = false;
    debugDexInput_.clear();
    debugDexError_.clear();
    activeBattle_ = std::make_unique<Battle>(pokedb, playerKey, foeKey);
    applyBattleView(*activeBattle_);
}

void Game::drawDebugDexModal()
{
    if (renderer == nullptr || font_ == nullptr)
    {
        return;
    }
    const int mx = maxPokedexNum();
    const int boxX = (kLogicalWidth - kDebugDexModalW) / 2;
    const int boxY = (kLogicalHeight - kDebugDexModalH) / 2;

    SDL_Rect bg{0, 0, kLogicalWidth, kLogicalHeight};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 160);
    SDL_RenderFillRect(renderer, &bg);

    SDL_Rect panel{boxX, boxY, kDebugDexModalW, kDebugDexModalH};
    SDL_SetRenderDrawColor(renderer, 24, 24, 28, 255);
    SDL_RenderFillRect(renderer, &panel);
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    SDL_RenderDrawRect(renderer, &panel);

    const SDL_Color white{255, 255, 255, 255};
    const int lineSkip = TTF_FontLineSkip(font_);
    int x = boxX + kBattlePromptPadding;
    int y = boxY + kBattlePromptPadding;

    {
        std::ostringstream title;
        title << "Debug: Pokédex # (1–" << mx << ")";
        renderText(title.str(), x, y, white);
        y += lineSkip;
    }
    renderText("Player species = this #; foe = random # in same range.", x, y, white);
    y += lineSkip;

    const std::string inputLine = std::string("Input: ") + debugDexInput_;
    renderText(inputLine, x, y, white);
    y += lineSkip;

    if (!debugDexError_.empty())
    {
        const SDL_Color err{255, 120, 120, 255};
        renderText(debugDexError_, x, y, err);
        y += lineSkip;
    }

    renderText("Enter confirm · Esc cancel · 0–9 Backspace", x, y, white);
}

void Game::drawBattleMovePrompt(const Battle& battle)
{
    if (renderer == nullptr || font_ == nullptr)
    {
        return;
    }

    const int lineSkip = TTF_FontLineSkip(font_);
    const int boxH = battleMovePanelHeight(font_);
    const int boxX = (kLogicalWidth - kBattlePromptBoxW) / 2;
    const int boxY = kLogicalHeight - boxH - kTextMargin;

    SDL_Rect panel{boxX, boxY, kBattlePromptBoxW, boxH};
    SDL_SetRenderDrawColor(renderer, 248, 248, 248, 255);
    SDL_RenderFillRect(renderer, &panel);
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderDrawRect(renderer, &panel);

    const SDL_Color textColor{24, 24, 24, 255};
    const int x = boxX + kBattlePromptPadding;
    // Anchor moves to bottom of panel so they are never clipped when the panel height changes.
    const int yFirst =
        boxY + boxH - kBattlePromptPadding - kBattleMoveRows * lineSkip;

    const auto& moves = battle.player().moves();
    const char* keys[] = {"Q", "W", "E", "R"};
    for (int i = 0; i < kBattleMoveRows; ++i)
    {
        const int y = yFirst + i * lineSkip;
        std::string line = "[";
        line += keys[i];
        line += "] ";
        if (i < static_cast<int>(moves.size()))
        {
            line += moves[static_cast<size_t>(i)].name;
        }
        else
        {
            line += "--";
        }
        renderText(line, x, y, textColor);
    }
}
