"""
Formation play definitions: which plays belong to each offensive formation.
Used to build playbooks (e.g. add all "Dual" plays to a team's playbook).
"""

from typing import Dict, List

from models.play import Play, OffensivePlayCategory


def _dual_plays() -> List[Play]:
    """Plays for the Dual offensive formation."""
    formation = "Dual"
    return [
        # Inside Run
        Play(
            id="dual_inside_zone",
            name="Inside Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="dual_read_option",
            name="Read Option",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB or RB"},
        ),
        Play(
            id="dual_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB", "note": "Quick Trap"},
        ),
        # Outside Run
        Play(
            id="dual_oz",
            name="OZ",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="dual_speed_option",
            name="Speed Option",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB or TB"},
        ),
        Play(
            id="dual_q_sweep",
            name="Q Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="dual_slants",
            name="Slants",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="dual_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="dual_bubbles",
            name="Bubbles",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="dual_smash",
            name="Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="dual_levels",
            name="Levels",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="dual_shallow",
            name="Shallow",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep (Long Pass)
        Play(
            id="dual_verts",
            name="Verts",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="dual_scissors",
            name="Scissors",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="dual_missile",
            name="Missile",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="dual_verticals_juke",
            name="Verticals-Juke",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        # Play Action
        Play(
            id="dual_boot",
            name="Boot",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _trio_plays() -> List[Play]:
    """Plays for the Trio formation (1 QB, 1 RB, 0 TE, 4 WR)."""
    formation = "Trio"
    return [
        # Inside Run
        Play(
            id="trio_inside_zone",
            name="Inside Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="trio_read_option",
            name="Read Option",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB/QB"},
        ),
        Play(
            id="trio_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="trio_oz",
            name="OZ",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="trio_speed_option",
            name="Speed Option",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB/QB"},
        ),
        Play(
            id="trio_q_sweep",
            name="Q Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="trio_slants",
            name="Slants",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="trio_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="trio_bubbles",
            name="Bubbles",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="trio_smash",
            name="Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="trio_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep (Long Pass)
        Play(
            id="trio_verts",
            name="Verts",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="trio_post_wheel",
            name="Post Wheel",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="trio_verticals_juke",
            name="Verticals-Juke",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        # Play Action
        Play(
            id="trio_boot",
            name="Boot",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _empty_plays() -> List[Play]:
    """Plays for the Empty formation (1 QB, 0 RB, 5 WR)."""
    formation = "Empty"
    return [
        # Inside Run
        Play(
            id="empty_qb_draw",
            name="QB Draw",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB"},
        ),
        Play(
            id="empty_qb_trap",
            name="QB Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB"},
        ),
        # Outside Run
        Play(
            id="empty_jet",
            name="Jet",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "WR"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="empty_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="empty_slants",
            name="Slants",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="empty_stick",
            name="Stick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="empty_smash",
            name="Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="empty_shallow",
            name="Shallow",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep (Long Pass)
        Play(
            id="empty_smash_pipe",
            name="Smash Pipe",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="empty_verticals_juke",
            name="Verticals-Juke",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        # Play Action
        Play(
            id="empty_boot",
            name="Boot",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _pro_plays() -> List[Play]:
    """Plays for the Pro formation. These plays exist only in Pro and do not appear in other formations."""
    formation = "Pro"
    return [
        # Inside Run
        Play(
            id="pro_fb_trap",
            name="FB Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "FB"},
        ),
        Play(
            id="pro_iso",
            name="Iso",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="pro_dive",
            name="Dive",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="pro_power_g",
            name="Power G",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="pro_toss_sweep",
            name="Toss Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="pro_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="pro_slants",
            name="Slants",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="pro_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="pro_hank",
            name="Hank",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="pro_te_post",
            name="TE Post",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="pro_levels",
            name="Levels",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="pro_curl_flat",
            name="Curl Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep (Long Pass)
        Play(
            id="pro_deep_post",
            name="Deep Post",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="pro_verticals",
            name="Verticals",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="pro_post_corner",
            name="Post Corner",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        # Play Action
        Play(
            id="pro_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="pro_boot",
            name="Boot",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _twins_plays() -> List[Play]:
    """Plays for the Twins formation. These plays exist only in Twins and do not appear in other formations."""
    formation = "Twins"
    return [
        # Inside Run
        Play(
            id="twins_iso",
            name="Iso",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="twins_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="twins_dive",
            name="Dive",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="twins_toss_st",
            name="Toss ST",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="twins_toss_wk",
            name="Toss WK",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="twins_power_g",
            name="Power G",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="twins_dbl_slants",
            name="DBL Slants",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="twins_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="twins_slant_flat",
            name="Slant/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="twins_sprint_smash",
            name="Sprint Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="twins_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="twins_dagger",
            name="Dagger",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep (Long Pass)
        Play(
            id="twins_post_wheel",
            name="Post Wheel",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="twins_post_dig",
            name="Post Dig",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="twins_verticals",
            name="Verticals",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        # Play Action
        Play(
            id="twins_boot",
            name="Boot",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="twins_flood_pa",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _trey_wing_plays() -> List[Play]:
    """Trey Wing (1 RB, 2 TE, 2 WR). Not assigned to Spread/Pro playbooks until wired in playbook_system."""
    formation = "Trey Wing"
    return [
        # Inside Run
        Play(
            id="trey_wing_inside_zone",
            name="Inside Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="trey_wing_power",
            name="Power",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="trey_wing_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="trey_wing_stretch",
            name="Stretch",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="trey_wing_speed_option",
            name="Speed Option",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB or RB"},
        ),
        Play(
            id="trey_wing_counter_sweep",
            name="Counter Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="trey_wing_stick",
            name="Stick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="trey_wing_slant_flat",
            name="Slant/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="trey_wing_hitches",
            name="Hitches",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="trey_wing_mesh",
            name="Mesh",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="trey_wing_drive",
            name="Drive",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="trey_wing_y_cross",
            name="Y-Cross",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="trey_wing_play_action_post",
            name="Play Action Post",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="trey_wing_double_move_sluggo",
            name="Double Move (Sluggo)",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="trey_wing_4_verts",
            name="4 Verts",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


def _wing_plays() -> List[Play]:
    """Wing (1 RB, 2 TE, 2 WR). Not assigned to Spread/Pro playbooks until wired in playbook_system."""
    formation = "Wing"
    return [
        # Inside Run
        Play(
            id="wing_belly",
            name="Belly",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="wing_buck_sweep",
            name="Buck Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_jet_sweep",
            name="Jet Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "WR"},
        ),
        Play(
            id="wing_reverse",
            name="Reverse",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "WR"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="wing_stick",
            name="Stick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="wing_slant_flat",
            name="Slant/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="wing_quick_out",
            name="Quick Out",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="wing_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="wing_smash",
            name="Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="wing_boot_cross",
            name="Boot Cross",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="wing_post_wheel",
            name="Post Wheel",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="wing_wheel_route",
            name="Wheel Route",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="wing_flood_shot",
            name="Flood Shot",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


def _flexbone_plays() -> List[Play]:
    """Flexbone (3 RB, 0 TE, 2 WR). Included in the Flexbone offensive playbook."""
    formation = "Flexbone"
    return [
        # Inside Run
        Play(
            id="flexbone_fullback_dive",
            name="Fullback Dive",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="flexbone_midline",
            name="Midline",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB or RB"},
        ),
        Play(
            id="flexbone_triple_option_dive",
            name="Triple Option (Dive phase)",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="flexbone_rocket_toss",
            name="Rocket Toss",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="flexbone_speed_option",
            name="Speed Option",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "QB or RB"},
        ),
        Play(
            id="flexbone_triple_option_pitch",
            name="Triple Option (Pitch phase)",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="flexbone_quick_hitch",
            name="Quick Hitch",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="flexbone_play_action_hitch",
            name="Play Action Hitch",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="flexbone_rocket_screen",
            name="Rocket Screen",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="flexbone_play_action_post",
            name="Play Action Post",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="flexbone_seam_read",
            name="Seam Read",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="flexbone_switch_verticals_medium",
            name="Switch Verticals",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="flexbone_play_action_go",
            name="Play Action Go",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="flexbone_switch_verticals_deep",
            name="Switch Verticals",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="flexbone_rocket_play_action",
            name="Rocket Play Action",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
    ]


def _double_wing_plays() -> List[Play]:
    """Double Wing (3 RB, 2 TE, 0 WR). Included in the Double Wing offensive playbook."""
    formation = "Double Wing"
    return [
        # Inside Run
        Play(
            id="double_wing_wedge",
            name="Wedge",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="double_wing_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="double_wing_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="double_wing_sweep",
            name="Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="double_wing_toss_crack",
            name="Toss Crack",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="double_wing_counter_sweep",
            name="Counter Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="double_wing_quick_slant",
            name="Quick Slant",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="double_wing_boot_flat",
            name="Boot Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="double_wing_te_pop_pass",
            name="TE Pop Pass",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="double_wing_boot_flood",
            name="Boot Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="double_wing_te_corner",
            name="TE Corner",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="double_wing_post_wheel",
            name="Post Wheel",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="double_wing_te_seam",
            name="TE Seam",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="double_wing_post_corner",
            name="Post Corner",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="double_wing_te_pop_go",
            name="TE Pop + Go",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


def _power_i_plays() -> List[Play]:
    """Power I (3 RB, 1 TE, 1 WR). Included in the Flexbone offensive playbook."""
    formation = "Power I"
    return [
        # Inside Run
        Play(
            id="power_i_iso",
            name="Iso",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="power_i_power",
            name="Power",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="power_i_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="power_i_toss_sweep",
            name="Toss Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="power_i_stretch",
            name="Stretch",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="power_i_counter_toss",
            name="Counter Toss",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="power_i_stick",
            name="Stick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="power_i_slant_flat",
            name="Slant/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="power_i_quick_out",
            name="Quick Out",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="power_i_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="power_i_curl_flat",
            name="Curl/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="power_i_dig",
            name="Dig",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="power_i_play_action_post",
            name="Play Action Post",
            side="offense",
            offensive_category=OffensivePlayCategory.PLAY_ACTION,
            formation=formation,
        ),
        Play(
            id="power_i_go_route",
            name="Go Route",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="power_i_deep_cross",
            name="Deep Cross",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


def _wing_t_plays() -> List[Play]:
    """Wing T (3 RB, 1 TE, 1 WR). Included in the Wing T offensive playbook."""
    formation = "Wing T"
    return [
        # Inside Run
        Play(
            id="wing_t_belly",
            name="Belly",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_t_trap",
            name="Trap",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_t_counter",
            name="Counter",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="wing_t_buck_sweep",
            name="Buck Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_t_jet_sweep",
            name="Jet Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="wing_t_waggle_run",
            name="Waggle Run",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="wing_t_waggle_quick",
            name="Waggle Quick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="wing_t_boot_pass",
            name="Boot Pass",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="wing_t_quick_screen",
            name="Quick Screen",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="wing_t_waggle",
            name="Waggle",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="wing_t_flood",
            name="Flood",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="wing_t_boot_drag",
            name="Boot Drag",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="wing_t_waggle_post",
            name="Waggle Post",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="wing_t_post_wheel",
            name="Post Wheel",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="wing_t_half_roll_shot",
            name="Half Roll Shot",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


def _doubles_plays() -> List[Play]:
    """Doubles (1 RB, 1 TE, 3 WR). Not assigned to Spread/Pro playbooks until wired in playbook_system."""
    formation = "Doubles"
    return [
        # Inside Run
        Play(
            id="doubles_inside_zone",
            name="Inside Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="doubles_duo",
            name="Duo",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="doubles_split_zone",
            name="Split Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.INSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        # Outside Run
        Play(
            id="doubles_outside_zone",
            name="Outside Zone",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB"},
        ),
        Play(
            id="doubles_jet_sweep",
            name="Jet Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "WR"},
        ),
        Play(
            id="doubles_orbit_motion_sweep",
            name="Orbit Motion Sweep",
            side="offense",
            offensive_category=OffensivePlayCategory.OUTSIDE_RUN,
            formation=formation,
            metadata={"ball_carrier": "RB or WR"},
        ),
        # Quick Game (Short Pass)
        Play(
            id="doubles_stick",
            name="Stick",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="doubles_slant_flat",
            name="Slant/Flat",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        Play(
            id="doubles_bubble_screen",
            name="Bubble Screen",
            side="offense",
            offensive_category=OffensivePlayCategory.SHORT_PASS,
            formation=formation,
            metadata={"concept": "Quick Game"},
        ),
        # Medium
        Play(
            id="doubles_mesh",
            name="Mesh",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="doubles_smash",
            name="Smash",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        Play(
            id="doubles_y_cross",
            name="Y-Cross",
            side="offense",
            offensive_category=OffensivePlayCategory.MEDIUM_PASS,
            formation=formation,
        ),
        # Deep
        Play(
            id="doubles_4_verticals",
            name="4 Verticals",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="doubles_post_dig_shot",
            name="Post/Dig Shot",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
        Play(
            id="doubles_fade_go",
            name="Fade/Go",
            side="offense",
            offensive_category=OffensivePlayCategory.LONG_PASS,
            formation=formation,
        ),
    ]


# Registry: formation name -> list of Play
_OFFENSIVE_FORMATIONS: Dict[str, List[Play]] = {
    "Dual": _dual_plays(),
    "Trio": _trio_plays(),
    "Empty": _empty_plays(),
    "Pro": _pro_plays(),
    "Twins": _twins_plays(),
    "Trey Wing": _trey_wing_plays(),
    "Wing": _wing_plays(),
    "Flexbone": _flexbone_plays(),
    "Double Wing": _double_wing_plays(),
    "Power I": _power_i_plays(),
    "Wing T": _wing_t_plays(),
    "Doubles": _doubles_plays(),
}


def get_formation_plays(formation_name: str) -> List[Play]:
    """Return all plays for an offensive formation. Raises KeyError if unknown."""
    key = formation_name.strip()
    if key not in _OFFENSIVE_FORMATIONS:
        raise KeyError(f"Unknown formation: {formation_name!r}. Known: {list(_OFFENSIVE_FORMATIONS)}")
    return list(_OFFENSIVE_FORMATIONS[key])


def list_formations() -> List[str]:
    """Return names of all defined offensive formations."""
    return list(_OFFENSIVE_FORMATIONS.keys())
