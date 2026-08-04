#include "game.h"

#include <random>

int random(int min, int max)
{
    static std::random_device rd;
    static std::mt19937 gen(rd());
    std::uniform_int_distribution<> dist(min, max);
    return dist(gen);
}

namespace
{

const char* typeLabel(Type t)
{
    switch (t)
    {
    case Type::Normal:
        return "Normal";
    case Type::Fire:
        return "Fire";
    case Type::Water:
        return "Water";
    case Type::Electric:
        return "Electric";
    case Type::Grass:
        return "Grass";
    case Type::Ice:
        return "Ice";
    case Type::Fighting:
        return "Fighting";
    case Type::Poison:
        return "Poison";
    case Type::Ground:
        return "Ground";
    case Type::Flying:
        return "Flying";
    case Type::Psychic:
        return "Psychic";
    case Type::Bug:
        return "Bug";
    case Type::Rock:
        return "Rock";
    case Type::Ghost:
        return "Ghost";
    case Type::Dragon:
        return "Dragon";
    case Type::Dark:
        return "Dark";
    case Type::Steel:
        return "Steel";
    case Type::Fairy:
        return "Fairy";
    default:
        return "?";
    }
}

const char* moveCategoryLabel(MoveCategory c)
{
    switch (c)
    {
    case MoveCategory::Physical:
        return "Physical";
    case MoveCategory::Special:
        return "Special";
    case MoveCategory::Status:
        return "Status";
    default:
        return "?";
    }
}

} // namespace

std::ostream& operator<<(std::ostream& os, const Pokemon& p)
{
    os << "===== Pokemon Stats =====\n";

    os << "\n--- IVs ---\n";
    os << "HP: " << p.ivs().hp << "\n";
    os << "ATK: " << p.ivs().atk << "\n";
    os << "DEF: " << p.ivs().def << "\n";
    os << "SP ATK: " << p.ivs().spAtk << "\n";
    os << "SP DEF: " << p.ivs().spDef << "\n";
    os << "SPD: " << p.ivs().spd << "\n";

    os << "\n--- Base Stats ---\n";
    os << "HP: " << p.bases().hp << "\n";
    os << "ATK: " << p.bases().atk << "\n";
    os << "DEF: " << p.bases().def << "\n";
    os << "SP ATK: " << p.bases().spAtk << "\n";
    os << "SP DEF: " << p.bases().spDef << "\n";
    os << "SPD: " << p.bases().spd << "\n";

    os << "\n--- Types ---\n";
    const auto& ts = p.getTypes();
    if (ts.empty())
    {
        os << "(none)\n";
    }
    else
    {
        for (std::size_t i = 0; i < ts.size(); ++i)
        {
            if (i > 0)
            {
                os << " / ";
            }
            os << typeLabel(ts[i]);
        }
        os << '\n';
    }

    os << "\n--- Moves ---\n";
    const auto& mv = p.moves();
    if (mv.empty())
    {
        os << "(none)\n";
    }
    else
    {
        for (const MoveTemplate& m : mv)
        {
            os << m.name << " [" << typeLabel(m.moveType) << ", " << moveCategoryLabel(m.category) << "] ";
            os << "Pow " << m.power << " / ";
            if (m.accuracy < 0)
            {
                os << "Acc —";
            }
            else
            {
                os << "Acc " << m.accuracy;
            }
            os << " / PP " << m.pp << "\n";
        }
    }

    os << "==========================";

    return os;
}
