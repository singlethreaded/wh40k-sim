"""Smoke tests for the added keywords."""
from wh40k_sim import SimAttacker, SimDefender, SimWeapon, simulate


def run(label, attacker, defender):
    r = simulate(attacker, defender, n_iter=20000, seed=1)
    print(f"{label:35s}  dmg={r.avg_damage:6.2f}  kills={r.avg_kills:5.2f}  p_wipe={r.p_wipe:.3f}")


guard = SimDefender(name="Guardsmen", toughness=3, save=5, wounds=1, unit_size=10, keywords=["Infantry"])
rhino = SimDefender(name="Rhino",      toughness=9, save=3, wounds=10, unit_size=1, keywords=["Vehicle"])

# Baseline: 5 Intercessors, A2 BS3+ S4 AP-1 D1
baseline = SimWeapon(name="Bolt Rifle", attacks="2", skill=3, strength=4, ap=-1, damage="1", count=5)
run("Baseline Bolt Rifle vs Guard", SimAttacker("Intercessors", 5, [baseline]), guard)

# Rapid Fire 1 — expect +1 attack per model → ~50% more damage
rf = SimWeapon(name="Bolt Rifle (RF1)", attacks="2", skill=3, strength=4, ap=-1, damage="1", count=5,
               keywords=["Rapid Fire 1"])
run("Rapid Fire 1 vs Guard", SimAttacker("Intercessors", 5, [rf]), guard)

# Heavy — stationary +1 to hit
heavy = SimWeapon(name="Heavy Bolter", attacks="3", skill=4, strength=5, ap=-1, damage="2", count=1,
                  keywords=["Heavy"])
run("Heavy Bolter (Heavy) vs Guard", SimAttacker("Devastators", 1, [heavy]), guard)

# Blast — 10-model unit gives +2 attacks per weapon
blast = SimWeapon(name="Frag Missile", attacks="D6", skill=3, strength=4, ap=0, damage="1", count=2,
                  keywords=["Blast"])
run("Frag (Blast) vs 10 Guard", SimAttacker("Devastators", 2, [blast]), guard)

# Melta 2 vs Rhino — +2 damage per wound
melta = SimWeapon(name="Meltagun", attacks="1", skill=3, strength=9, ap=-4, damage="D6", count=2,
                  keywords=["Melta 2"])
run("Meltagun (Melta 2) vs Rhino", SimAttacker("Marines", 2, [melta]), rhino)

# Lance — melee, charging +1 to wound
lance = SimWeapon(name="Power Lance", attacks="3", skill=3, strength=5, ap=-2, damage="2", count=5,
                  keywords=["Lance"], weapon_type="melee")
run("Power Lance (Lance) vs Rhino", SimAttacker("Bikers", 5, [lance]), rhino)

# Torrent — autohits, 1/6 crits still feed Sustained
torrent = SimWeapon(name="Flamer", attacks="D6", skill=4, strength=5, ap=0, damage="1", count=2,
                    keywords=["Torrent", "Sustained Hits 1"])
run("Flamer (Torrent+Sus1) vs Guard", SimAttacker("Marines", 2, [torrent]), guard)

# Cover: +1 save vs ranged. Baseline bolt rifle into guard in cover → save goes 6+ → 5+.
guard_cover = SimDefender(name="Guardsmen (cover)", toughness=3, save=5, wounds=1,
                          unit_size=10, keywords=["Infantry"], save_bonus_ranged=1)
run("Bolt Rifle vs Guard in cover",    SimAttacker("Intercessors", 5, [baseline]), guard_cover)

# Ignores Cover bypasses the +1
ic = SimWeapon(name="Bolt Rifle (IC)", attacks="2", skill=3, strength=4, ap=-1, damage="1", count=5,
               keywords=["Ignores Cover"])
run("Bolt Rifle+IC vs Guard in cover", SimAttacker("Intercessors", 5, [ic]),      guard_cover)
