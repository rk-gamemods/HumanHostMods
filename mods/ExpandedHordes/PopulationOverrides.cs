using HarmonyLib;

namespace ExpandedHordes
{
    // Restore only values still owned by us; do not undo a later write by another mod.
    internal static class PopulationOverrides
    {
        private static AI_Agen_Mgr ai;
        private static int originalAi, writtenAi;
        private static NPC_Horde_Mgr horde;
        private static int originalTotal, originalPioneers, originalGrowth, originalLimit;
        private static int writtenTotal, writtenPioneers, writtenGrowth, writtenLimit;
        private static readonly AccessTools.FieldRef<NPC_Horde_Mgr, int> Total = AccessTools.FieldRefAccess<NPC_Horde_Mgr, int>("_HordeZombieAll");
        private static readonly AccessTools.FieldRef<NPC_Horde_Mgr, int> Pioneers = AccessTools.FieldRefAccess<NPC_Horde_Mgr, int>("_ZombiesPioneerCount");
        private static readonly AccessTools.FieldRef<NPC_Horde_Mgr, int> Growth = AccessTools.FieldRefAccess<NPC_Horde_Mgr, int>("_ZombiesPerWaveAdd");

        internal static void SetAi(AI_Agen_Mgr owner, int value)
        {
            if (ai != owner) { ai = owner; originalAi = owner._MaxAllowActiveZombies; }
            owner._MaxAllowActiveZombies = writtenAi = value;
        }
        internal static void Capture(NPC_Horde_Mgr owner)
        {
            if (horde == owner) return;
            horde = owner;
            originalTotal = writtenTotal = Total(owner);
            originalPioneers = writtenPioneers = Pioneers(owner);
            originalGrowth = writtenGrowth = Growth(owner);
            originalLimit = writtenLimit = owner._MaxAllowActiveZombies;
        }
        internal static void SetLimit(NPC_Horde_Mgr owner, int value)
        {
            if (!owner) return;
            Capture(owner);
            owner._MaxAllowActiveZombies = writtenLimit = value;
        }
        internal static void Record(NPC_Horde_Mgr owner)
        {
            writtenTotal = Total(owner); writtenPioneers = Pioneers(owner);
            writtenGrowth = Growth(owner); writtenLimit = owner._MaxAllowActiveZombies;
        }
        internal static void Restore()
        {
            if (ai && ai._MaxAllowActiveZombies == writtenAi) ai._MaxAllowActiveZombies = originalAi;
            if (horde)
            {
                if (Total(horde) == writtenTotal) Total(horde) = originalTotal;
                if (Pioneers(horde) == writtenPioneers) Pioneers(horde) = originalPioneers;
                if (Growth(horde) == writtenGrowth) Growth(horde) = originalGrowth;
                if (horde._MaxAllowActiveZombies == writtenLimit) horde._MaxAllowActiveZombies = originalLimit;
            }
            ai = null; horde = null;
        }
    }
}
