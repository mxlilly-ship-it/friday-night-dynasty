from .player_generator import (
    generate_player,
    generate_roster,
    generate_name,
    roll_height_weight_for_position,
    ARCHETYPES,
    POSITION_ARCHETYPES,
)
from .generate_team_roster import (
    generate_team_roster,
    calculate_roster_size,
)
from .team_ratings import (
    calculate_team_ratings,
    calculate_turnover_profile,
    calculate_player_overall,
    OVERALL_TIERS,
    get_overall_tier,
    get_overall_tier_range,
)
from .coach_generator import (
    generate_coach,
    generate_coach_for_team,
    assign_coaches_to_teams,
    get_program_attractiveness,
)
from .playoff_system import seed_teams, run_playoff_game, run_playoff
from .development_system import (
    develop_player,
    run_offseason_development,
    run_winter_phase_development,
    run_spring_ball_development,
    in_season_development,
    remove_graduated_players,
    advance_age_and_year,
    add_incoming_freshmen,
    run_full_offseason,
)
from .coach_development import (
    COACH_DEV_SKILLS,
    CP_PER_SKILL_LEVEL,
    apply_coach_development,
    compute_coach_development_bank,
)
from .offseason_manager import (
    run_offseason,
    run_offseason_all_teams,
    trim_roster,
    reset_team_season_stats,
    reset_standings,
    reset_season_stats,
    OFFSEASON_PHASES,
)
from .game_stats import (
    PlayerGameStats,
    PlayerSeasonStats,
    create_game_stats,
    record_play,
    format_game_box_score,
    merge_game_stats_into_season,
    format_season_player_stats,
    player_game_stats_map_to_json_list,
)
from .playbook_system import Playbook, build_playbook_for_team
from .play_caller import (
    GameSituation,
    build_situation_from_game,
    pick_offensive_play,
    pick_defensive_play,
    call_plays_for_situation,
)
from .formation_plays import get_formation_plays, list_formations
from .defensive_formations import (
    get_defensive_formation_plays,
    list_defensive_formations,
)
from .play_weighting import (
    get_offensive_play_score,
    get_defensive_play_score,
    get_position_rating,
)
from .recruiting_system import (
    compute_recruiting_score,
    compute_recruiting_context,
    generate_recruited_freshman,
    RecruitingContext,
)
from .prestige_system import update_prestige, compute_prestige_delta, get_coach_skill_sum
from .coach_career_system import run_coach_career_phase
from .teams_loader import load_teams_from_json, build_teams_from_json
from .awards_system import compute_awards, format_awards_text
from .records_system import load_records, save_records, update_records_from_season, update_records_from_game, format_records_text
from .game_fatigue import (
    GameStaminaTracker,
    PlayFatigueContext,
    build_current_lineup_from_depth_chart,
    process_after_play,
    effective_attribute,
)

__all__ = [
    "generate_player",
    "generate_roster",
    "generate_name",
    "roll_height_weight_for_position",
    "ARCHETYPES",
    "POSITION_ARCHETYPES",
    "generate_team_roster",
    "calculate_roster_size",
    "calculate_team_ratings",
    "calculate_turnover_profile",
    "calculate_player_overall",
    "OVERALL_TIERS",
    "get_overall_tier",
    "get_overall_tier_range",
    "generate_coach",
    "generate_coach_for_team",
    "assign_coaches_to_teams",
    "get_program_attractiveness",
    "seed_teams",
    "run_playoff_game",
    "run_playoff",
    "PlayerGameStats",
    "create_game_stats",
    "record_play",
    "format_game_box_score",
    "PlayerSeasonStats",
    "merge_game_stats_into_season",
    "format_season_player_stats",
    "player_game_stats_map_to_json_list",
    "develop_player",
    "run_offseason_development",
    "run_winter_phase_development",
    "run_spring_ball_development",
    "in_season_development",
    "remove_graduated_players",
    "advance_age_and_year",
    "add_incoming_freshmen",
    "run_full_offseason",
    "run_offseason",
    "run_offseason_all_teams",
    "trim_roster",
    "reset_team_season_stats",
    "reset_standings",
    "reset_season_stats",
    "OFFSEASON_PHASES",
    "COACH_DEV_SKILLS",
    "CP_PER_SKILL_LEVEL",
    "apply_coach_development",
    "compute_coach_development_bank",
    "Playbook",
    "build_playbook_for_team",
    "GameSituation",
    "build_situation_from_game",
    "pick_offensive_play",
    "pick_defensive_play",
    "call_plays_for_situation",
    "get_formation_plays",
    "list_formations",
    "get_defensive_formation_plays",
    "list_defensive_formations",
    "get_offensive_play_score",
    "get_defensive_play_score",
    "get_position_rating",
    "compute_recruiting_score",
    "compute_recruiting_context",
    "generate_recruited_freshman",
    "RecruitingContext",
    "update_prestige",
    "compute_prestige_delta",
    "get_coach_skill_sum",
    "run_coach_career_phase",
    "load_teams_from_json",
    "build_teams_from_json",
    "compute_awards",
    "format_awards_text",
    "load_records",
    "save_records",
    "update_records_from_season",
    "update_records_from_game",
    "format_records_text",
    "GameStaminaTracker",
    "PlayFatigueContext",
    "build_current_lineup_from_depth_chart",
    "process_after_play",
    "effective_attribute",
]
