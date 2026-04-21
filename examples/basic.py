"""
Smoke-test example: Intercessors (bolt rifles) vs. 10 Guardsmen.
"""
from wh40k_sim import SimAttacker, SimDefender, SimWeapon, simulate


bolt_rifle = SimWeapon(
    name="Bolt Rifle",
    attacks="2",
    skill=3,
    strength=4,
    ap=-1,
    damage="1",
    count=5,                        # 5 intercessors firing
    keywords=[],
    weapon_type="ranged",
)

intercessors = SimAttacker(name="Intercessors", model_count=5, weapons=[bolt_rifle])

guardsmen = SimDefender(
    name="Guardsmen",
    toughness=3,
    save=5,
    wounds=1,
    unit_size=10,
    fnp=0,
    keywords=["Infantry"],
)

result = simulate(intercessors, guardsmen, n_iter=20000, seed=42)
print(f"avg_damage:           {result.avg_damage}")
print(f"avg_damage_uncapped:  {result.avg_damage_uncapped}")
print(f"avg_kills:            {result.avg_kills}")
print(f"avg_damage_per_model: {result.avg_damage_per_model}")
print(f"p_wipe:               {result.p_wipe}")
print(f"p_kills:              {result.p_kills}")
