#ifndef MUSIC_MANAGER_H
#define MUSIC_MANAGER_H

#include <string>

/// FEATURE-MAP-087: SDL2_mixer route BGM and one-shot music playback.
class MusicManager
{
public:
    bool init();
    void shutdown();

    bool isReady() const { return ready_; }

    void playRouteMusic(const std::string& trackStem, int fadeMs = 0);
    void playBattleMusic(const std::string& trackStem, int fadeMs = 0);
    void playOnce(const std::string& trackStem);
    void stop(int fadeMs = 0);

    const std::string& currentRouteTrack() const { return currentRouteTrack_; }

private:
    bool ready_ = false;
    std::string currentRouteTrack_;
    std::string resolvePath(const std::string& trackStem) const;
};

#endif // MUSIC_MANAGER_H
