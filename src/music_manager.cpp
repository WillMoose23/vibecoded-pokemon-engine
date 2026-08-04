#include "music_manager.h"

#include <iostream>

#if defined(USE_SDL2_MIXER) && USE_SDL2_MIXER
#  include <SDL_mixer.h>
#endif

namespace
{
constexpr int kDefaultFreq = 44100;
constexpr int kDefaultChannels = 2;
constexpr int kDefaultChunk = 2048;
}

bool MusicManager::init()
{
    if (ready_)
    {
        return true;
    }
#if USE_SDL2_MIXER
    if (Mix_OpenAudio(kDefaultFreq, MIX_DEFAULT_FORMAT, kDefaultChannels, kDefaultChunk) != 0)
    {
        std::cerr << "MusicManager: Mix_OpenAudio failed: " << Mix_GetError() << '\n';
        return false;
    }
    ready_ = true;
    return true;
#else
    std::cerr << "MusicManager: SDL2_mixer not available at build time (brew install sdl2_mixer)\n";
    return false;
#endif
}

void MusicManager::shutdown()
{
    if (!ready_)
    {
        return;
    }
#if USE_SDL2_MIXER
    Mix_HaltMusic();
    Mix_CloseAudio();
#endif
    ready_ = false;
    currentRouteTrack_.clear();
}

std::string MusicManager::resolvePath(const std::string& trackStem) const
{
    if (trackStem.empty())
    {
        return {};
    }
    return std::string("src/audio/") + trackStem + ".ogg";
}

void MusicManager::playRouteMusic(const std::string& trackStem, int fadeMs)
{
#if USE_SDL2_MIXER
    if (!ready_ || trackStem.empty())
    {
        return;
    }
    if (trackStem == currentRouteTrack_ && Mix_PlayingMusic())
    {
        return;
    }
    const std::string path = resolvePath(trackStem);
    Mix_Music* mus = Mix_LoadMUS(path.c_str());
    if (!mus)
    {
        std::cerr << "MusicManager: failed to load " << path << ": " << Mix_GetError() << '\n';
        return;
    }
    if (fadeMs > 0 && Mix_PlayingMusic())
    {
        Mix_FadeOutMusic(fadeMs);
    }
    const int loops = -1;
    if (fadeMs > 0)
    {
        Mix_FadeInMusic(mus, loops, fadeMs);
    }
    else
    {
        Mix_PlayMusic(mus, loops);
    }
    Mix_FreeMusic(mus);
    currentRouteTrack_ = trackStem;
#else
    (void)trackStem;
    (void)fadeMs;
#endif
}

void MusicManager::playBattleMusic(const std::string& trackStem, int fadeMs)
{
    playRouteMusic(trackStem, fadeMs);
}

void MusicManager::playOnce(const std::string& trackStem)
{
#if USE_SDL2_MIXER
    if (!ready_ || trackStem.empty())
    {
        return;
    }
    const std::string path = resolvePath(trackStem);
    Mix_Music* mus = Mix_LoadMUS(path.c_str());
    if (!mus)
    {
        std::cerr << "MusicManager: failed to load " << path << ": " << Mix_GetError() << '\n';
        return;
    }
    Mix_PlayMusic(mus, 1);
    Mix_FreeMusic(mus);
#else
    (void)trackStem;
#endif
}

void MusicManager::stop(int fadeMs)
{
#if USE_SDL2_MIXER
    if (!ready_)
    {
        return;
    }
    if (fadeMs > 0)
    {
        Mix_FadeOutMusic(fadeMs);
    }
    else
    {
        Mix_HaltMusic();
    }
#else
    (void)fadeMs;
#endif
    currentRouteTrack_.clear();
}
