#ifndef BATTLE_H
#define BATTLE_H

#include "game.h"

#include <string>
#include <vector>

enum class BattleOutcome
{
    Ongoing,
    PlayerWon,
    FoeWon
};

struct BattleDamageResult
{
    int damage = 0;
    bool critical = false;
};

class Battle
{
public:
    Battle(
        json& pokedb,
        const std::string& playerKey,
        const std::string& foeKey,
        const std::string& playerForm = "",
        const std::string& foeForm = "",
        int playerLevel = 50,
        int foeLevel = 50);

    const Pokemon& player() const { return player_; }
    const Pokemon& foe() const { return foe_; }

    int playerCurrentHp() const { return playerHp_; }
    int foeCurrentHp() const { return foeHp_; }
    int playerMaxHp() const { return playerMaxHp_; }
    int foeMaxHp() const { return foeMaxHp_; }

    bool battleEnded() const { return outcome_ != BattleOutcome::Ongoing; }
    bool playerWon() const { return outcome_ == BattleOutcome::PlayerWon; }

    /// Lines describing what happened last turn (moves used, damage, crits), newest-relevant order.
    const std::vector<std::string>& lastTurnMessages() const { return lastTurnMessages_; }

    const std::string& playerSpeciesKey() const { return playerKey_; }
    const std::string& foeSpeciesKey() const { return foeKey_; }
    const std::string& playerFormKey() const { return playerForm_; }
    const std::string& foeFormKey() const { return foeForm_; }

    /// FEATURE-MAP-088: when true, foe attacks deal enough damage to KO the active player Pokémon.
    void setFoeOhko(bool on) { foeOhkoMode_ = on; }
    bool foeOhko() const { return foeOhkoMode_; }

    /// Hook for future rules; called at the start of each player turn resolution.
    void onPlayerMoveChosen(int slot);

    /// Runs one turn: foe picks a random move, speed decides order, damage applied. Returns false if
    /// the slot is invalid, the battle is already over, or the chosen slot has no move.
    bool executeTurn(int playerMoveSlot);

private:
    Pokemon player_;
    Pokemon foe_;
    std::string playerKey_;
    std::string foeKey_;
    std::string playerForm_;
    std::string foeForm_;
    std::vector<std::string> lastTurnMessages_;
    int playerMaxHp_ = 1;
    int foeMaxHp_ = 1;
    int playerHp_ = 1;
    int foeHp_ = 1;
    int playerLevel_ = 50;
    int foeLevel_ = 50;
    bool foeOhkoMode_ = false;
    BattleOutcome outcome_ = BattleOutcome::Ongoing;

    static int combinedSpeed(const Pokemon& p);
    static BattleDamageResult calculateDamage(
        const Pokemon& attacker,
        const Pokemon& defender,
        const MoveTemplate& move,
        int attackerLevel);
    static bool hasStab(const Pokemon& attacker, Type moveType);

    void attackWith(
        Pokemon& attacker,
        Pokemon& defender,
        int& defenderHp,
        const MoveTemplate& move,
        const std::string& attackerName,
        int attackerLevel);
};

#endif // BATTLE_H
