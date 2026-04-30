"""
Defensive formation play definitions: which plays belong to each defensive front/scheme.
Used to build playbooks (e.g. add all "4-3" plays to a team's playbook).
"""

from typing import Dict, List

from models.play import Play, DefensivePlayCategory


def _formation_43_plays() -> List[Play]:
    """Plays for the 4-3 defensive formation."""
    formation = "4-3"
    return [
        # Zones
        Play(
            id="43_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Base Cover 3"},
        ),
        Play(
            id="43_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Solid against passing teams, can be lighter against run",
            },
        ),
        Play(
            id="43_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "3rd down coverage or passing teams, struggles against run",
            },
        ),
        # Man
        Play(
            id="43_1_strong",
            name="1 Strong",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Man coverage"},
        ),
        Play(
            id="43_1_weak",
            name="1 Weak",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={
                "note": "Man coverage with the Sam linebacker in man, can get exploited in pass",
            },
        ),
        # Zone Pressure
        Play(
            id="43_saw_cover_3",
            name="Saw Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "Strong pressure, good against run, struggle against pass unless bad OL",
            },
        ),
        # Man Pressure
        Play(
            id="43_mag_cover_1",
            name="Mag Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Better against pass, not great for speed option",
            },
        ),
        Play(
            id="43_spark_cover_0",
            name="Spark Cover 0",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Hurts really bad offensive lines against run or pass, can create TFLs or sacks, but will give up a big play if blocked well",
            },
        ),
    ]


def _formation_34_plays() -> List[Play]:
    """Plays for the 3-4 defensive formation (3 DL, 4 LB, 4 DB)."""
    formation = "3-4"
    return [
        # Zones
        Play(
            id="34_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Rushing 4. Weak against flood and verticals, solid against the run",
            },
        ),
        Play(
            id="34_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Rushing 4. Weak against quick game and screens, solid vs medium and deep passing",
            },
        ),
        Play(
            id="34_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Rushing 2. Good against pass game but weak against the run",
            },
        ),
        # Man
        Play(
            id="34_1_strong",
            name="1 Strong",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={
                "note": "Rushing 4. Weak against matchups in man coverage",
            },
        ),
        # Zone Pressures
        Play(
            id="34_weak_war_trey",
            name="Weak War Trey",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "2 LBs blitzing with the DL. Can be weak against pass if rush is bad",
            },
        ),
        Play(
            id="34_favre_3",
            name="Favre 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "Creeper pressure with ONE LB rushing, 4 in coverage. Similar to Cover 3",
            },
        ),
        Play(
            id="34_orton_4",
            name="Orton 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "Creeper pressure with one LB rushing. Similar to Cover 4",
            },
        ),
        # Man Pressures
        Play(
            id="34_saw_0",
            name="Saw 0",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Double Edged Cover 0. Weak against pass if they don't get home. Sack or TFL if they do",
            },
        ),
        Play(
            id="34_wag_1",
            name="Wag 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Similar to Man. Weak against matchups",
            },
        ),
        Play(
            id="34_dbl_war_0",
            name="DBL War 0",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "All out pressure. Good in red zone. TFL/sack if advantage, big play if not",
            },
        ),
    ]


def _formation_nickel_plays() -> List[Play]:
    """Plays for the Nickel defensive formation (5 DBs)."""
    formation = "Nickel"
    return [
        # Zones
        Play(
            id="nickel_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Good against the pass, ok against the run, quick game will be ok",
            },
        ),
        Play(
            id="nickel_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Better against the run, solid vs pass, struggles against verticals",
            },
        ),
        Play(
            id="nickel_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={
                "note": "Good against the pass, not great against the run",
            },
        ),
        # Man
        Play(
            id="nickel_1_rat",
            name="1 Rat",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={
                "note": "Good if you have good matchups",
            },
        ),
        Play(
            id="nickel_2_man",
            name="2 Man",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={
                "note": "Bad against the run, good against pass and 3rd downs",
            },
        ),
        # Zone Pressures
        Play(
            id="nickel_favre",
            name="Favre",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "Cover 3 ideas",
            },
        ),
        Play(
            id="nickel_war_trey",
            name="War Trey",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={
                "note": "Bad against quick game",
            },
        ),
        # Man Pressures
        Play(
            id="nickel_war_blue",
            name="War Blue",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Based on matchups",
            },
        ),
        Play(
            id="nickel_saw_blue",
            name="Saw Blue",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={
                "note": "Based on matchups",
            },
        ),
    ]


def _formation_dime_plays() -> List[Play]:
    """Plays for the Dime defensive formation (4 DL, 1 LB, 2 S, 4 CB)."""
    formation = "Dime"
    return [
        # Zones
        Play(
            id="dime_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "DIME (4 DL, 1 LB, 2 S, 4 CB) — split safety zone shell."},
        ),
        Play(
            id="dime_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "3-deep zone from DIME spacing."},
        ),
        Play(
            id="dime_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Quarters shell for vertical stress."},
        ),
        Play(
            id="dime_cover_6",
            name="Cover 6 (Quarter-Quarter-Half)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Quarter-quarter-half split coverage."},
        ),
        Play(
            id="dime_tampa_2",
            name="Tampa 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Middle-runner variation of Cover 2."},
        ),
        # Man
        Play(
            id="dime_2_man",
            name="2 Man",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Two-high man-under call."},
        ),
        Play(
            id="dime_cover_1_robber",
            name="Cover 1 Robber",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Single-high with robber support."},
        ),
        Play(
            id="dime_cover_0_blitz",
            name="Cover 0 Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "All-man pressure with no deep help."},
        ),
        # Zone Pressures
        Play(
            id="dime_nickel_fire_zone",
            name="Nickel Fire Zone (5-man)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "5-man fire zone pressure."},
        ),
        Play(
            id="dime_db_blitz",
            name="DB Blitz (slot/corner)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Slot/corner pressure from DIME."},
        ),
        Play(
            id="dime_fire_zone_3u3d",
            name="3-under 3-deep fire zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Classic 3-under, 3-deep fire zone."},
        ),
        # Man Pressures
        Play(
            id="dime_double_edge_0",
            name="Double Edge 0",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Edge pressure in Cover 0 structure."},
        ),
        Play(
            id="dime_slot_blitz_1",
            name="Slot Blitz 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Slot pressure paired with Cover 1."},
        ),
        Play(
            id="dime_mike_cover_1",
            name="Mike Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Mike pressure from single-high man."},
        ),
    ]


def _formation_52_plays() -> List[Play]:
    """Plays for the 5-2 defensive formation (5 DL, 2 LB, 2 S, 2 CB)."""
    formation = "5-2"
    return [
        # Zones
        Play(
            id="52_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "5-2 shell with 3-deep zone."},
        ),
        Play(
            id="52_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Two-high zone look from heavy front."},
        ),
        Play(
            id="52_cover_1_zone_match",
            name="Cover 1 (zone-match)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Zone-match principles in single-high shell."},
        ),
        # Man
        Play(
            id="52_cover_1",
            name="Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Single-high man coverage."},
        ),
        # Zone Pressures
        Play(
            id="52_olb_fire_zone",
            name="OLB Fire Zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Edge fire zone from OLB pressure."},
        ),
        Play(
            id="52_strong_side_trap_zone",
            name="5-man strong-side pressure Trap Zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Strong-side five-man zone pressure."},
        ),
        # Man Pressures
        Play(
            id="52_double_edge_blitz",
            name="Double Edge Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Both edges pressure in man structure."},
        ),
        Play(
            id="52_mlb_a_gap_blitz",
            name="MLB A-gap blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Mike attacks interior A-gap."},
        ),
    ]


def _formation_33_stack_plays() -> List[Play]:
    """Plays for the 3-3 Stack defensive formation (3 DL, 3 LB, 3 S, 2 CB)."""
    formation = "3-3 Stack"
    return [
        # Zones
        Play(
            id="33stk_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "3-deep zone from stack front."},
        ),
        Play(
            id="33stk_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Quarters spacing with stack structure."},
        ),
        Play(
            id="33stk_cover_2",
            name="Cover 2",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Split-safety zone option."},
        ),
        Play(
            id="33stk_drop_8",
            name="Drop 8 (3 rush)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Three-man rush with eight in coverage."},
        ),
        # Man
        Play(
            id="33stk_cover_1",
            name="Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Single-high man coverage."},
        ),
        Play(
            id="33stk_2_man",
            name="2 Man",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Two-high man-under call."},
        ),
        # Zone Pressures
        Play(
            id="33stk_fire_zone",
            name="Stack Fire Zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Fire zone pressure from stack alignment."},
        ),
        Play(
            id="33stk_cross_dog_zone",
            name="Cross Dog Zone Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Cross-dog pressure with zone shell behind it."},
        ),
        # Man Pressures
        Play(
            id="33stk_double_a_gap",
            name="Double A-gap",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Interior double A-gap pressure."},
        ),
        Play(
            id="33stk_mike_will_blitz",
            name="Mike + Will Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Mike and Will pressure package."},
        ),
    ]


def _formation_33_stack_3_high_plays() -> List[Play]:
    """Plays for 3-3 Stack 3-High (3 DL, 3 LB, 3 S, 2 CB)."""
    formation = "3-3 Stack 3-High"
    return [
        # Zones
        Play(
            id="33stk3h_cover_3_rot",
            name="Cover 3 (rotated)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Rotated 3-high shell into Cover 3."},
        ),
        Play(
            id="33stk3h_cover_4",
            name="Cover 4",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Quarters from three-high shell."},
        ),
        Play(
            id="33stk3h_cover_6",
            name="Cover 6",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Quarter-quarter-half variation."},
        ),
        Play(
            id="33stk3h_drop_8",
            name="Drop 8",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Three-man rush, eight in coverage."},
        ),
        # Man
        Play(
            id="33stk3h_cover_1",
            name="Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Single-high man option from disguise shell."},
        ),
        Play(
            id="33stk3h_2_man_split",
            name="2 Man (from split safeties)",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Two-man from split safety presentation."},
        ),
        # Zone Pressures
        Play(
            id="33stk3h_simulated",
            name="Stack Fire Zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Fire zone pressure from stack alignment."},
        ),
        Play(
            id="33stk3h_creeper",
            name="Cross Dog Zone Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Cross-dog pressure with zone shell behind it."},
        ),
        # Man Pressures
        Play(
            id="33stk3h_safety_insert",
            name="Mike + Will Blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Mike and Will pressure package."},
        ),
        Play(
            id="33stk3h_double_a_gap",
            name="Double A-gap",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Interior double A-gap pressure look."},
        ),
    ]


def _formation_62_plays() -> List[Play]:
    """Plays for the 6-2 defensive formation (6 DL, 4 LB, 2 DB)."""
    formation = "6-2"
    return [
        # Zones
        Play(
            id="62_cover_3",
            name="Cover 3",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Heavy-front Cover 3 shell."},
        ),
        Play(
            id="62_cover_1_zone",
            name="Cover 1 zone",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONES,
            formation=formation,
            metadata={"note": "Zone-match style Cover 1 from heavy front."},
        ),
        # Man
        Play(
            id="62_cover_0",
            name="Cover 0",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "All-man with no deep help."},
        ),
        Play(
            id="62_cover_1",
            name="Cover 1",
            side="defense",
            defensive_category=DefensivePlayCategory.MANS,
            formation=formation,
            metadata={"note": "Single-high man coverage."},
        ),
        # Zone Pressures
        Play(
            id="62_heavy_run_blitz",
            name="Heavy run blitz (6+ rushers)",
            side="defense",
            defensive_category=DefensivePlayCategory.ZONE_PRESSURE,
            formation=formation,
            metadata={"note": "Heavy run pressure with six-plus rushers."},
        ),
        # Man Pressures
        Play(
            id="62_all_out_blitz",
            name="All-out blitz",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "All-out man pressure package."},
        ),
        Play(
            id="62_edge_overload",
            name="Edge overload",
            side="defense",
            defensive_category=DefensivePlayCategory.MAN_PRESSURE,
            formation=formation,
            metadata={"note": "Overload pressure to one edge."},
        ),
    ]


def _extended_defensive_registry() -> Dict[str, List[Play]]:
    """Base fronts plus sub-packages (Dime, 5-2, stack, 6-2) built from proven templates."""
    f43 = _formation_43_plays()
    f34 = _formation_34_plays()
    nickel = _formation_nickel_plays()
    dime = _formation_dime_plays()
    f52 = _formation_52_plays()
    stack = _formation_33_stack_plays()
    stack3h = _formation_33_stack_3_high_plays()
    f62 = _formation_62_plays()
    return {
        "4-3": f43,
        "3-4": f34,
        "Nickel": nickel,
        "Dime": dime,
        "5-2": f52,
        "3-3 Stack": stack,
        "3-3 Stack 3-High": stack3h,
        "6-2": f62,
    }


# Registry: formation name -> list of Play
_DEFENSIVE_FORMATIONS: Dict[str, List[Play]] = _extended_defensive_registry()


def get_defensive_formation_plays(formation_name: str) -> List[Play]:
    """Return all plays for a defensive formation. Raises KeyError if unknown."""
    key = formation_name.strip()
    if key not in _DEFENSIVE_FORMATIONS:
        raise KeyError(
            f"Unknown defensive formation: {formation_name!r}. "
            f"Known: {list(_DEFENSIVE_FORMATIONS)}"
        )
    return list(_DEFENSIVE_FORMATIONS[key])


def list_defensive_formations() -> List[str]:
    """Return names of all defined defensive formations."""
    return list(_DEFENSIVE_FORMATIONS.keys())
