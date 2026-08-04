#include "battle.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <sstream>

Battle::Battle(
    json& pokedb,
    const std::string& playerKey,
    const std::string& foeKey,
    const std::string& playerForm,
    const std::string& foeForm,
    int playerLevel,
    int foeLevel)
    : player_(pokedb, playerKey, playerForm)
    , foe_(pokedb, foeKey, foeForm)
    , playerKey_(playerKey)
    , foeKey_(foeKey)
    , playerForm_(playerForm)
    , foeForm_(foeForm)
    , playerLevel_(std::max(1, playerLevel))
    , foeLevel_(std::max(1, foeLevel))
{
    playerMaxHp_ = std::max(1, player_.bases().hp);
    foeMaxHp_ = std::max(1, foe_.bases().hp);
    playerHp_ = playerMaxHp_;
    foeHp_ = foeMaxHp_;
}

void Battle::onPlayerMoveChosen(int slot)
{
    (void)slot;
}

int Battle::combinedSpeed(const Pokemon& p)
{
    return p.bases().spd + p.ivs().spd;
}

bool Battle::hasStab(const Pokemon& attacker, Type moveType)
{
    for (Type t : attacker.getTypes())
    {
        if (t == moveType)
        {
            return true;
        }
    }
    return false;
}

BattleDamageResult Battle::calculateDamage(
    const Pokemon& attacker,
    const Pokemon& defender,
    const MoveTemplate& move,
    int attackerLevel)
{
    BattleDamageResult out{};
    if (move.category == MoveCategory::Status || move.power <= 0)
    {
        return out;
    }
    const int level = std::max(1, attackerLevel);

    const auto& ab = attacker.bases();
    const auto& ai = attacker.ivs();
    const auto& db = defender.bases();
    const auto& di = defender.ivs();

    int attackStat = 0;
    int defenseStat = 1;
    if (move.category == MoveCategory::Physical)
    {
        attackStat = ab.atk + ai.atk;
        defenseStat = db.def + di.def;
    }
    else
    {
        attackStat = ab.spAtk + ai.spAtk;
        defenseStat = db.spDef + di.spDef;
    }
    if (defenseStat < 1)
    {
        defenseStat = 1;
    }

    double base =
        ((2.0 * level / 5.0 + 2.0) * move.power * (static_cast<double>(attackStat) / defenseStat)) / 50.0 + 2.0;

    const double stab = hasStab(attacker, move.moveType) ? 1.5 : 1.0;
    const double typeEffect = 1.0;

    const int rMin = 85;
    const int rMax = 100;
    const double randomFactor = static_cast<double>(random(rMin, rMax)) / 100.0;

    out.critical = (random(0, 15) == 0);
    const double critMultiplier = out.critical ? 1.5 : 1.0;

    if (out.critical)
    {
        std::cout << "Critical hit!\n";
    }

    const double dmg = base * stab * typeEffect * randomFactor * critMultiplier;
    out.damage = std::max(1, static_cast<int>(std::floor(dmg)));
    return out;
}

void Battle::attackWith(
    Pokemon& attacker,
    Pokemon& defender,
    int& defenderHp,
    const MoveTemplate& move,
    const std::string& attackerName,
    int attackerLevel)
{
    if (move.category == MoveCategory::Status || move.power <= 0)
    {
        std::cout << attackerName << " used " << move.name << " (no damage).\n";
        lastTurnMessages_.push_back(attackerName + " used " + move.name + " (no damage).");
        return;
    }

    BattleDamageResult dr = calculateDamage(attacker, defender, move, attackerLevel);
    if (foeOhkoMode_ && &attacker == &foe_)
    {
        dr.damage = std::max(1, defenderHp);
    }
    if (dr.critical)
    {
        lastTurnMessages_.push_back("Critical hit!");
    }
    std::cout << attackerName << " used " << move.name << " for " << dr.damage << " damage.\n";
    {
        std::ostringstream line;
        line << attackerName << " used " << move.name << " for " << dr.damage << " damage.";
        lastTurnMessages_.push_back(line.str());
    }
    defenderHp -= dr.damage;
    if (defenderHp < 0)
    {
        defenderHp = 0;
    }
}

bool Battle::executeTurn(int playerMoveSlot)
{
    if (battleEnded())
    {
        return false;
    }

    const auto& pMoves = player_.moves();
    if (playerMoveSlot < 0 || playerMoveSlot >= static_cast<int>(pMoves.size()))
    {
        std::cout << "Invalid move slot.\n";
        return false;
    }

    lastTurnMessages_.clear();

    onPlayerMoveChosen(playerMoveSlot);
    const MoveTemplate& playerMove = pMoves[static_cast<size_t>(playerMoveSlot)];
    std::cout << "Player chose " << playerMove.name << " (slot " << playerMoveSlot << ").\n";

    const auto& fMoves = foe_.moves();
    if (fMoves.empty())
    {
        std::cout << "Foe has no moves; skipping foe action.\n";
    }

    const MoveTemplate* foeMovePtr = nullptr;
    if (!fMoves.empty())
    {
        const int fi = random(0, static_cast<int>(fMoves.size()) - 1);
        foeMovePtr = &fMoves[static_cast<size_t>(fi)];
        std::cout << "Foe chose " << foeMovePtr->name << ".\n";
    }

    const int ps = combinedSpeed(player_);
    const int fs = combinedSpeed(foe_);
    const bool playerFirst = (ps >= fs);

    auto doPlayerAttack = [&]() {
        if (outcome_ != BattleOutcome::Ongoing)
        {
            return;
        }
        attackWith(player_, foe_, foeHp_, playerMove, playerKey_, playerLevel_);
        if (foeHp_ <= 0)
        {
            outcome_ = BattleOutcome::PlayerWon;
            std::cout << "Foe fainted. Player wins.\n";
            lastTurnMessages_.push_back(foeKey_ + " fainted. " + playerKey_ + " wins!");
        }
    };

    auto doFoeAttack = [&]() {
        if (outcome_ != BattleOutcome::Ongoing || foeMovePtr == nullptr)
        {
            return;
        }
        attackWith(foe_, player_, playerHp_, *foeMovePtr, foeKey_, foeLevel_);
        if (playerHp_ <= 0)
        {
            outcome_ = BattleOutcome::FoeWon;
            std::cout << "Player fainted. Foe wins.\n";
            lastTurnMessages_.push_back(playerKey_ + " fainted. " + foeKey_ + " wins!");
        }
    };

    if (playerFirst)
    {
        doPlayerAttack();
        doFoeAttack();
    }
    else
    {
        doFoeAttack();
        doPlayerAttack();
    }

    return true;
}
