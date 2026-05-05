import builtins
import random


def _safe_engine_print(*args, **kwargs) -> None:
    """Never let console I/O crash sims (Windows errno 22 / broken pipe on stdout under uvicorn)."""
    try:
        builtins.print(*args, **kwargs)
    except Exception:
        # Also catches BrokenPipeError, BufferError, and odd Windows EINVAL from TextIOWrapper.flush.
        return


def _tri_int(lo: int, hi: int, mode: int) -> int:
    """Triangular sample: most mass near ``mode`` (HS play-count tuning)."""
    lo, hi = int(lo), int(hi)
    if hi <= lo:
        return lo
    mode = max(lo, min(hi, int(mode)))
    return int(round(random.triangular(lo, hi, mode)))


def regulation_dead_ball_clock_seconds() -> int:
    """Clock runoff for punt, FG, change of possession, TD celebration, legacy auto-4th."""
    return _tri_int(14, 30, 22)


def regulation_kneel_clock_seconds() -> int:
    """Clock burned on a victory formation kneel."""
    return _tri_int(26, 40, 33)


def regulation_scrimmage_clock_seconds(
    offense_choice: str,
    *,
    incomplete_pass: bool,
    sack: bool = False,
    scramble: bool = False,
) -> int:
    """
    Seconds burned on one regulation scrimmage snap.
    Pass completions (and sacks) tick faster than runs; incompletes do not run the main clock
    (extra snaps → higher play volume for pass-heavy games).
    """
    if incomplete_pass:
        return 0
    if sack:
        return _tri_int(16, 34, 24)
    if scramble:
        return _tri_int(15, 32, 23)
    if offense_choice == "1":
        return _tri_int(22, 40, 31)
    return _tri_int(14, 32, 23)


def _normalize_offense_choice(choice):
    """Convert Play object to legacy '1' (run) or '2' (pass). Pass-through for str."""
    if choice is None:
        return None
    if hasattr(choice, "offensive_category") and choice.offensive_category is not None:
        cat = choice.offensive_category
        if getattr(cat, "name", None) in ("INSIDE_RUN", "OUTSIDE_RUN"):
            return "1"
        return "2"
    return choice


def _normalize_defense_choice(choice):
    """Convert Play object to legacy '1' (run D), '2' (pass rush), '3' (balanced). Pass-through for str."""
    if choice is None:
        return None
    if hasattr(choice, "defensive_category") and choice.defensive_category is not None:
        cat = choice.defensive_category
        name = getattr(cat, "name", None)
        if name == "ZONES":
            return "3"
        if name == "MANS":
            return "1"
        return "2"  # ZONE_PRESSURE, MAN_PRESSURE
    return choice


def _offense_play_label(choice):
    """Display label for offense call: play name (formation) or RUN/PASS."""
    if choice is None:
        return "?"
    if hasattr(choice, "name"):
        form = getattr(choice, "formation", None) or ""
        return f"{choice.name}" + (f" ({form})" if form else "")
    return "RUN" if choice == "1" else "PASS"


def _defense_play_label(choice):
    """Display label for defense call: play name (formation) or generic."""
    if choice is None:
        return "?"
    if hasattr(choice, "name"):
        form = getattr(choice, "formation", None) or ""
        return f"{choice.name}" + (f" ({form})" if form else "")
    if choice == "1":
        return "RUN DEFENSE"
    if choice == "2":
        return "PASS RUSH"
    return "BALANCED DEFENSE"


# Kickoff is taken from the kicking team's own 40 (HS-style); ball_position is always
# yards from the current offense's own goal toward the opponent's goal line.
KICKOFF_TEE_YARDS = 40


class Game:
    def __init__(self, offense_rating=60, defense_rating=60, run_rating=60, pass_rating=60):
        self.quarter = 1
        self.time_remaining = 12 * 60
        self.ball_position = 25
        self.down = 1
        self.yards_to_go = 10
        self.score_home = 0
        self.score_away = 0
        self.possession = "home"

        self.offense_rating = offense_rating
        self.defense_rating = defense_rating
        self.run_rating = run_rating
        self.pass_rating = pass_rating

        # Turnover tuning ratings (set each possession by caller; defaults are neutral)
        self.qb_decision_rating = 50
        self.qb_arm_strength = 50
        self.qb_scramble_base = 0.04  # Base scramble chance (Pocket ~2%, Average ~4-5%, Dual-Threat ~6-8%, Elite ~9-12%)
        self.ball_security_rating = 50
        self.off_discipline_rating = 50
        self.def_coverage_rating = 50
        self.def_tackling_rating = 50
        self.def_pass_rush_rating = 50

        # ✅ TEAM TURNOVER STATS
        self.interceptions_home = 0
        self.interceptions_away = 0
        self.fumbles_home = 0
        self.fumbles_away = 0

        # ✅ NCAA OVERTIME
        self.is_overtime = False
        self.ot_period = 0
        self.ot_possession_count = 0  # 0 or 1 = which possession this period
        self.ot_2pt_mode = False      # True in OT3+ = 2-point shootout only
        self.ot_2pt_round = {"home": None, "away": None}  # Current round results in 2pt shootout
        self.ot_winner = None         # "home", "away", or None

        # Regulation: after TD, offense chooses XP or 2PT before kickoff
        self.pending_pat = False
        # Who received the opening kickoff ("home" or "away") — other team receives 2nd-half kickoff
        self.opening_kickoff_receiver = "home"

    def switch_possession(self):
        self.possession = "away" if self.possession == "home" else "home"
        self.ball_position = 100 - self.ball_position
        self.down = 1
        self.yards_to_go = 10

    # ------------------ PUNT ------------------
    def punt_ball(self, defense_mode: str = "return"):
        """
        defense_mode: 'return' (default), 'block' (sell out for block — shorter / riskier punt)
        """
        _safe_engine_print("PUNT!")
        blocked = False
        punt_distance = random.randint(35, 50)
        if defense_mode == "block":
            if random.random() < 0.09:
                _safe_engine_print("PUNT BLOCKED!")
                blocked = True
                punt_distance = random.randint(8, 18)
            else:
                punt_distance -= random.randint(6, 14)
                punt_distance = max(18, punt_distance)

        self.ball_position += punt_distance

        if self.ball_position >= 100:
            _safe_engine_print("Touchback!")
            self.ball_position = 80

        if not blocked:
            _safe_engine_print(f"Punt travels {punt_distance} yards.")
        self.switch_possession()
        self.display_status()
        return {"blocked": blocked, "distance": punt_distance}

    def apply_kickoff_return_spot(self) -> dict:
        """
        Receiving team is already in self.possession. Sets ball_position (and rarely PAT after KR TD).
        Returns metadata for play-by-play: kickoff, touchback, return_yards, kickoff_td.
        """
        meta: dict = {"kickoff": True, "touchback": False, "return_yards": 0, "kickoff_td": False}
        kick_travel = random.randint(55, 70)
        # Tee at own 40; travel toward opponent. Receiver's field yard = 100 - 40 - travel.
        catch_yard = 100 - KICKOFF_TEE_YARDS - kick_travel
        if catch_yard < 1 or random.random() < 0.28:
            meta["touchback"] = True
            self.ball_position = 25
            _safe_engine_print("Kickoff — touchback.")
            return meta

        ret = random.randint(8, 40)
        meta["return_yards"] = ret
        catch_yard = max(1, min(99, catch_yard))
        new_pos = catch_yard + ret
        if new_pos >= 100:
            _safe_engine_print("KICKOFF RETURN TOUCHDOWN!")
            meta["kickoff_td"] = True
            meta["touchdown"] = True
            if self.possession == "home":
                self.score_home += 6
            else:
                self.score_away += 6
            self.pending_pat = True
            self.ball_position = 97
            return meta
        self.ball_position = min(new_pos, 99)
        _safe_engine_print(f"Kickoff return: {ret} yards — ball at {self.ball_position}.")
        return meta

    def apply_opening_kickoff(self) -> None:
        """Coin flip for receiver; place ball after opening kickoff return. Sets opening_kickoff_receiver."""
        self.opening_kickoff_receiver = random.choice(["home", "away"])
        self.possession = self.opening_kickoff_receiver
        ko = self.apply_kickoff_return_spot()
        if not ko.get("kickoff_td"):
            self.down = 1
            self.yards_to_go = 10

    def finish_pat_and_kickoff(self) -> dict:
        """After XP / 2PT: kickoff and return (regulation). OT keeps opponent's-25 spot."""
        self.pending_pat = False
        self.switch_possession()
        if self.is_overtime:
            self.ball_position = 75
            self.down = 1
            self.yards_to_go = 10
            return {}
        meta = self.apply_kickoff_return_spot()
        if not meta.get("kickoff_td"):
            self.down = 1
            self.yards_to_go = 10
        self.time_remaining = max(0, self.time_remaining - random.randint(5, 14))
        return meta

    def attempt_extra_point_kick(self, defense_pat_choice: str = "return"):
        """
        defense_pat_choice: 'block' (rush to block) or 'return' (safe / hold lanes).
        Returns dict with pat_kick, pat_success, blocked, missed.
        """
        blocked = False
        if defense_pat_choice == "block":
            if random.random() < 0.11:
                _safe_engine_print("EXTRA POINT BLOCKED!")
                blocked = True
                return {"pat_kick": True, "pat_success": False, "blocked": True, "missed": False}
            make_chance = 0.88
        else:
            make_chance = 0.945

        if random.random() < make_chance:
            _safe_engine_print("EXTRA POINT IS GOOD!")
            if self.possession == "home":
                self.score_home += 1
            else:
                self.score_away += 1
            return {"pat_kick": True, "pat_success": True, "blocked": False, "missed": False}
        _safe_engine_print("EXTRA POINT NO GOOD!")
        return {"pat_kick": True, "pat_success": False, "blocked": False, "missed": True}

    def _second_half_receiver(self) -> str:
        return "away" if self.opening_kickoff_receiver == "home" else "home"

    def apply_halftime_kickoff(self):
        """Start 3rd quarter: team that did not receive opening kickoff gets 2nd-half kickoff return."""
        recv = self._second_half_receiver()
        self.possession = recv
        ko = self.apply_kickoff_return_spot()
        if not ko.get("kickoff_td"):
            self.down = 1
            self.yards_to_go = 10

    # ------------------ NCAA OVERTIME ------------------
    def start_overtime(self):
        """Start OT per NCAA rules. Coin toss: random who gets ball first."""
        self.is_overtime = True
        self.ot_period = 1
        self.ot_possession_count = 0
        self.ot_2pt_mode = False
        # Coin toss: random who goes first
        self.possession = random.choice(["home", "away"])
        self.ball_position = 75   # Opponent's 25 = 75 yards from own goal
        self.down = 1
        self.yards_to_go = 10
        self.time_remaining = 0   # No clock in OT
        _safe_engine_print(f"\n*** OVERTIME {self.ot_period} ***")
        _safe_engine_print(f"Coin toss: {self.possession.upper()} chooses to go first. Ball at opponent's 25.")
        self.display_status()

    def setup_ot_possession(self):
        """Give ball to other team at opponent's 25."""
        self.switch_possession()
        self.ball_position = 75   # Opponent's 25
        self.down = 1
        self.yards_to_go = 10

    def attempt_two_point(self, offense_choice=None, defense_choice=None):
        """2-point conversion from the 3-yard line. Returns {"success": bool}."""
        offense_choice = offense_choice or self.get_ai_play_call()
        defense_choice = defense_choice or self.get_ai_defense_call()
        if hasattr(offense_choice, "name"):
            _safe_engine_print(f"  2PT Offense: {_offense_play_label(offense_choice)}")
            _safe_engine_print(f"  2PT Defense: {_defense_play_label(defense_choice)}")
        offense_choice = _normalize_offense_choice(offense_choice)
        defense_choice = _normalize_defense_choice(defense_choice)

        yards = 0
        if offense_choice == "1":  # Run
            base_yards = random.randint(-1, 6)
            rating_bonus = (self.run_rating - self.defense_rating) // 8
            yards = base_yards + rating_bonus
            if defense_choice == "3":
                yards -= max(1, (100 - self.defense_rating) // 18)
        else:  # Pass
            base_yards = random.randint(-4, 10)
            rating_bonus = (self.pass_rating - self.defense_rating) // 8
            yards = base_yards + rating_bonus
            sack_chance = max(0.07, 0.18 - (self.pass_rating - self.defense_rating) / 250)
            if defense_choice == "2" and random.random() < sack_chance:
                yards = -7
            int_chance = max(0.01, 0.05 - (self.pass_rating - self.defense_rating) / 200)
            if random.random() < int_chance:
                yards = 0  # INT = failed 2pt
                if self.possession == "home":
                    self.interceptions_home += 1
                else:
                    self.interceptions_away += 1

        self.ball_position = 97 + yards
        self.ball_position = max(0, min(self.ball_position, 100))
        success = self.ball_position >= 100

        if success:
            _safe_engine_print("2-POINT CONVERSION GOOD!")
            if self.possession == "home":
                self.score_home += 2
            else:
                self.score_away += 2
        else:
            _safe_engine_print("2-POINT CONVERSION FAILED.")

        return {"success": success, "touchdown": success, "yards": yards}

    def run_play_2pt_shootout(self, offense_choice=None, defense_choice=None):
        """OT3+: Single 2-point attempt. Teams alternate. Returns {"success": bool, "game_over": bool}."""
        result = self.attempt_two_point(offense_choice, defense_choice)
        success = result["success"]
        team = "home" if self.possession == "home" else "away"
        self.ot_2pt_round[team] = success

        # Check if both have attempted this round
        if self.ot_2pt_round["home"] is not None and self.ot_2pt_round["away"] is not None:
            h, a = self.ot_2pt_round["home"], self.ot_2pt_round["away"]
            if h and not a:
                self.ot_winner = "home"
                _safe_engine_print("\n*** 2-POINT SHOOTOUT: HOME WINS! ***")
            elif a and not h:
                self.ot_winner = "away"
                _safe_engine_print("\n*** 2-POINT SHOOTOUT: AWAY WINS! ***")
            else:
                # Both made or both missed - next round
                self.ot_2pt_round = {"home": None, "away": None}
                # Alternate who goes first: team that went second goes first
                self.possession = "away" if self.possession == "home" else "home"
            return {"success": success, "game_over": self.ot_winner is not None}

        # Switch to other team for their attempt
        self.possession = "away" if self.possession == "home" else "home"
        return {"success": success, "game_over": False}

    # ------------------ FIELD GOAL ------------------
    def attempt_field_goal(self, defense_fg_block: bool = False):
        kick_distance = (100 - self.ball_position) + 17
        _safe_engine_print(f"Field Goal Attempt from {kick_distance} yards!")

        if kick_distance <= 35:
            success_chance = 0.95
        elif kick_distance <= 45:
            success_chance = 0.85
        elif kick_distance <= 55:
            success_chance = 0.65
        else:
            success_chance = 0.40

        if defense_fg_block:
            if random.random() < 0.09:
                _safe_engine_print("FIELD GOAL BLOCKED!")
                self.switch_possession()
                self.ball_position = 25
                self.down = 1
                self.yards_to_go = 10
                self.display_status()
                return False
            success_chance *= 0.88

        good = random.random() < success_chance
        if good:
            _safe_engine_print("FIELD GOAL IS GOOD!")
            if self.possession == "home":
                self.score_home += 3
            else:
                self.score_away += 3
            self.switch_possession()
            if not self.is_overtime:
                self.apply_kickoff_return_spot()
                if not getattr(self, "pending_pat", False):
                    self.down = 1
                    self.yards_to_go = 10
            else:
                self.ball_position = 75
                self.down = 1
                self.yards_to_go = 10
        else:
            _safe_engine_print("Field Goal Missed!")
            self.switch_possession()
            self.ball_position = 25
            self.down = 1
            self.yards_to_go = 10

        self.display_status()
        return good

    # ------------------ 4TH DOWN DECISION ------------------
    def _fourth_down_decision(self):
        """
        Decide whether to go for it, punt, or attempt a field goal on 4th down.
        Returns "go", "punt", or "fg".
        - FG range: ball at opponent's 35 or closer (ball_position >= 65).
        - Own territory deep: almost always punt when not in FG range (4th and 7+ from own 0-40).
        - Go for it in opponent's territory when not in FG range and 4th and 6 or less.
        - When trailing in second half, go for it more (4th and 5 or less from anywhere, 4th and 6 in opp territory).
        - 4th and 2 or less: go for it anywhere (unless FG range already returned "fg").
        """
        if self.is_overtime:
            return "go"  # NCAA OT: no punt, always go (or FG in range)

        if self.possession == "home":
            off_score, def_score = self.score_home, self.score_away
        else:
            off_score, def_score = self.score_away, self.score_home
        margin = off_score - def_score
        trailing = margin < 0
        second_half = self.quarter >= 3
        in_opponent_territory = self.ball_position >= 50
        # HS realism: routine FG decisions should usually stay inside ~50 yards.
        # ball_position 67 => ~50-yard attempt ((100-67)+17).
        in_fg_range = self.ball_position >= 67
        own_territory_deep = self.ball_position < 40

        # Field goal when in realistic range
        if in_fg_range:
            return "fg"

        # Coach override: if provided, use a simple yards-to-go threshold.
        try:
            go_max = getattr(self, "fourth_down_go_for_it_max_ytg", None)
            if go_max is not None:
                go_max_i = max(0, min(10, int(go_max)))
                return "go" if self.yards_to_go <= go_max_i else "punt"
        except Exception:
            pass

        # Deep own territory, long to go: punt (field position game)
        if own_territory_deep and self.yards_to_go >= 7:
            return "punt"

        # 4th and 2 or less: go for it anywhere
        if self.yards_to_go <= 2:
            return "go"

        # Opponent's territory, not in FG range, 4th and 6 or less: go for it
        if in_opponent_territory and self.yards_to_go <= 6:
            return "go"

        # Trailing in second half: more aggressive – go for it on 4th and 5 or less from anywhere, 4th and 6 in opp territory
        if trailing and second_half:
            if self.yards_to_go <= 5:
                return "go"
            if in_opponent_territory and self.yards_to_go <= 6:
                return "go"

        # Default: punt
        return "punt"

    def fourth_down_decision(self) -> str:
        """Public alias for AI / sim (punt, fg, or go)."""
        return self._fourth_down_decision()

    # ------------------ AI PLAY CALL ------------------
    def get_ai_play_call(self):
        # Determine which team has the ball
        if self.possession == "home":
            my_score = self.score_home
            opp_score = self.score_away
        else:
            my_score = self.score_away
            opp_score = self.score_home

        score_margin = my_score - opp_score
        my_turnovers = (
            (self.interceptions_home + self.fumbles_home)
            if self.possession == "home"
            else (self.interceptions_away + self.fumbles_away)
        )

        # If offense is already turning it over repeatedly, call safer.
        if my_turnovers >= 3:
            return random.choices(["1", "2"], weights=[72, 28])[0]
        if my_turnovers >= 2:
            return random.choices(["1", "2"], weights=[62, 38])[0]

        # -------- 2-MINUTE DRILL LOGIC --------
        if self.quarter == 4 and self.time_remaining <= 2*60 and score_margin < 0:
            # Trailing with 2 minutes left → very aggressive passing
            _safe_engine_print("2-MINUTE DRILL: PASSING!")
            return "2"

        # Losing in 4th quarter → heavy pass
        elif self.quarter >= 4 and score_margin < 0:
            return "2"  # pass

        # Winning big → more runs
        elif score_margin > 10:
            return random.choices(["1", "2"], weights=[70, 30])[0]

        # Otherwise balanced
        else:
            return random.choices(["1", "2"], weights=[50, 50])[0]

    # ------------------ AI DEFENSE CALL ------------------
    def get_ai_defense_call(self):
        """Defense predicts offense based on down & distance, score, and time."""
        # 1 = Run Defense, 2 = Pass Rush, 3 = Balanced
        if self.possession == "home":
            my_score = self.score_home
            opp_score = self.score_away
        else:
            my_score = self.score_away
            opp_score = self.score_home

        score_margin = my_score - opp_score  # Defense's perspective (we are defending)

        # -------- 2-MINUTE DRILL: Expect pass --------
        if self.quarter == 4 and self.time_remaining <= 2 * 60:
            if score_margin >= 0:  # Tied or winning → offense will pass to catch up
                return random.choices(["2", "3"], weights=[75, 25])[0]  # Heavy pass rush
            else:  # Losing → offense may run clock, mixed call
                return random.choices(["1", "2", "3"], weights=[35, 45, 20])[0]

        # -------- Down & Distance --------
        if self.yards_to_go >= 5 and self.down >= 3:  # 3rd/4th and long
            return random.choices(["2", "3"], weights=[70, 30])[0]  # Expect pass

        if self.yards_to_go <= 2:  # Short yardage
            return random.choices(["1", "3"], weights=[70, 30])[0]  # Expect run

        if self.down == 1 or (self.down == 2 and self.yards_to_go <= 4):
            return random.choices(["1", "3"], weights=[60, 40])[0]  # Slight run lean

        # -------- Score-based --------
        if score_margin > 10:  # Winning big → offense will pass to catch up
            return random.choices(["2", "3"], weights=[60, 40])[0]

        if score_margin < -7:  # Losing → offense may run to kill clock
            return random.choices(["1", "3"], weights=[55, 45])[0]

        # Default: balanced
        return random.choices(["1", "2", "3"], weights=[35, 35, 30])[0]

    # ------------------ MAIN PLAY ENGINE ------------------
    def run_play(self, offense_choice=None, defense_choice=None, offense_team=None, defense_team=None):
        yards = 0
        sack = False
        scramble = False
        interception = False
        fumble = False
        incomplete_pass = False

        # -------- 4TH DOWN: AI auto punt/FG only when no explicit coach play (legacy / silent sim) --------
        if self.down == 4 and offense_team is None:
            decision = self._fourth_down_decision()
            if decision == "punt":
                _safe_engine_print("4th down: PUNT")
                self.punt_ball()
                clock_elapsed = regulation_dead_ball_clock_seconds()
                self.time_remaining -= clock_elapsed
                if self.time_remaining < 0:
                    self.time_remaining = 0
                return {"yards": 0, "touchdown": False, "turnover": False, "sack": False, "interception": False, "incomplete_pass": False, "clock_elapsed": clock_elapsed, "first_down": False, "fumble": False}
            if decision == "fg":
                _safe_engine_print("4th down: Field Goal Attempt")
                self.attempt_field_goal()
                clock_elapsed = regulation_dead_ball_clock_seconds() if not self.is_overtime else 0
                self.time_remaining -= clock_elapsed
                if self.time_remaining < 0:
                    self.time_remaining = 0
                return {"yards": 0, "touchdown": False, "turnover": False, "sack": False, "interception": False, "incomplete_pass": False, "clock_elapsed": clock_elapsed, "first_down": False, "fumble": False}

        # -------- AI / RANDOM PLAY SELECTION --------
        if offense_choice is None:
            offense_choice = self.get_ai_play_call()

        if defense_choice is None:
            defense_choice = self.get_ai_defense_call()

        # -------- DISPLAY CALLED PLAYS --------
        off_label = _offense_play_label(offense_choice)
        def_label = _defense_play_label(defense_choice)
        _safe_engine_print(f"Offense Call: {off_label}")
        _safe_engine_print(f"Defense Call: {def_label}")

        # Keep play objects around for turnover tuning by concept/coverage call
        offense_play_obj = offense_choice if hasattr(offense_choice, "offensive_category") else None
        defense_play_obj = defense_choice if hasattr(defense_choice, "defensive_category") else None
        pass_concept = (
            getattr(getattr(offense_play_obj, "offensive_category", None), "name", "")
            if offense_play_obj is not None
            else ""
        )
        coverage_call = (
            getattr(getattr(defense_play_obj, "defensive_category", None), "name", "")
            if defense_play_obj is not None
            else ""
        )
        def_formation = getattr(defense_play_obj, "formation", None) if defense_play_obj else None
        off_formation = getattr(offense_play_obj, "formation", None) if offense_play_obj else None

        # -------- NORMALIZE TO LEGACY (run_play uses "1"/"2" and "1"/"2"/"3") --------
        offense_choice = _normalize_offense_choice(offense_choice)
        defense_choice = _normalize_defense_choice(defense_choice)

        # Formation-aware defensive ratings (DL/LB/DB counts on this snap vs team baseline)
        def_eff_defense = self.defense_rating
        def_eff_coverage = self.def_coverage_rating
        def_eff_pass_rush = self.def_pass_rush_rating
        def_eff_tackling = self.def_tackling_rating
        if defense_team is not None and def_formation:
            try:
                from systems.defensive_personnel import snap_defensive_ratings

                _adj = snap_defensive_ratings(
                    defense_team,
                    str(def_formation),
                    {
                        "defense": self.defense_rating,
                        "def_coverage": self.def_coverage_rating,
                        "def_pass_rush": self.def_pass_rush_rating,
                        "def_tackling": self.def_tackling_rating,
                    },
                )
                def_eff_defense = _adj["defense"]
                def_eff_coverage = _adj["def_coverage"]
                def_eff_pass_rush = _adj["def_pass_rush"]
                def_eff_tackling = _adj["def_tackling"]
            except Exception:
                pass

        off_eff_run = self.run_rating
        off_eff_pass = self.pass_rating
        if offense_team is not None and off_formation:
            try:
                from systems.offensive_personnel import snap_offensive_ratings

                _oadj = snap_offensive_ratings(
                    offense_team,
                    str(off_formation),
                    {"run": self.run_rating, "pass": self.pass_rating},
                )
                off_eff_run = _oadj["run"]
                off_eff_pass = _oadj["pass"]
            except Exception:
                pass

        # -------- RUN --------
        if offense_choice == "1":
            # Base 4-7 YPC (slight uptick); better run O gets more, strong run D/poor OL stuffs
            base_yards = random.randint(4, 7)
            rating_bonus = (off_eff_run - def_eff_defense) // 7
            yards = base_yards + rating_bonus

            # Run defense: called run D or strong run D can stuff
            if defense_choice == "1":
                yards -= max(0, (def_eff_defense - off_eff_run) // 20)
            elif defense_choice == "3":
                yards -= max(0, (100 - def_eff_defense) // 40)

            # Explosive runs: chunk (10-18) and breakaway (18-45). Scale with matchup.
            # Slightly elevated vs prior (~+15–18% relative chance) for a few more chunk/breakaway runs per game.
            adv = off_eff_run - def_eff_defense
            roll = random.random()
            # Chunk run 10-18 yd
            chunk_chance = 0.165 + max(0, adv) / 330
            if roll < chunk_chance:
                yards = random.randint(10, 18)
            # Breakaway 18-45 yd
            elif roll < chunk_chance + (0.093 + max(0, adv) / 138):
                max_break = min(45, 99 - self.ball_position)
                if max_break >= 18:
                    yards = random.randint(18, max_break)

            yards = max(-3, min(99, yards))

            # Fumble chance on run: low ball security + low discipline increase risk.
            # Better defensive tackling/pass rush can increase forced fumbles.
            off_carry_security = (
                (self.ball_security_rating * 0.55)
                + (self.off_discipline_rating * 0.25)
                + (off_eff_run * 0.20)
            )
            def_strip_force = (
                (def_eff_tackling * 0.65)
                + (def_eff_defense * 0.20)
                + (def_eff_pass_rush * 0.15)
            )
            fumble_chance = 0.0165 + ((def_strip_force - off_carry_security) / 1000.0)
            fumble_chance = max(0.0035, min(0.048, fumble_chance))
            # Season target: good teams 8-14 TO, bad teams 20-35. Scale by offense ball security.
            off_to_quality = (self.qb_decision_rating + self.ball_security_rating + self.off_discipline_rating) / 3.0
            to_scale = 1.5 - off_to_quality / 72.0
            to_scale = max(0.48, min(1.12, to_scale))
            fumble_chance *= to_scale * 1.08
            if random.random() < fumble_chance:
                _safe_engine_print("FUMBLE!")
                fumble = True
                if self.possession == "home":
                    self.fumbles_home += 1
                else:
                    self.fumbles_away += 1

        # -------- PASS --------
        elif offense_choice == "2":
            sack = False
            scramble = False
            explosive_chance = 0.0  # set in pass-resolution block; 0 when sack/scramble
            # Sack: strong pass rush vs weak pass protection / bad QB = disaster
            pressure_boost = (def_eff_pass_rush - off_eff_pass) / 350.0
            sack_chance = max(0.06, 0.20 - ((off_eff_pass - def_eff_defense) / 220))
            sack_chance = max(0.05, min(0.32, sack_chance + pressure_boost))
            if defense_choice == "2" and random.random() < sack_chance:
                _safe_engine_print("SACK! Loss of 7 yards")
                yards = -7
                sack = True

            # QB scramble: pressure + coverage increase chance; good DL can negate (reduce yards)
            if not sack:
                scramble_base = getattr(self, "qb_scramble_base", 0.04)
                pressure = def_eff_pass_rush / 100.0
                coverage = def_eff_coverage / 100.0
                scramble_chance = scramble_base + (pressure * 0.04) + (coverage * 0.02)
                scramble_chance = max(0.02, min(0.25, scramble_chance))
                if random.random() < scramble_chance:
                    # QB run; good DL contains (reduces yards)
                    base_yards = random.randint(2, 9)
                    rating_bonus = (off_eff_run - def_eff_defense) // 8
                    yards = base_yards + rating_bonus
                    yards = max(0, min(25, yards))  # cap scramble gains; good D can stuff
                    yards = max(-2, min(99, yards))
                    scramble = True
                    _safe_engine_print("QB SCRAMBLE! " + str(yards) + " yards")

            if not sack and not scramble:
                # Yardage by concept. Avg 120-150/game; variance 75 (bad) to 300+ (great matchup)
                adv = off_eff_pass - def_eff_coverage
                if pass_concept == "SHORT_PASS":
                    base_yards = random.randint(2, 10)
                    explosive_chance = 0.078 + max(0, adv) / 380  # YAC explosion
                elif pass_concept == "MEDIUM_PASS":
                    base_yards = random.randint(4, 14)
                    explosive_chance = 0.162 + max(0, adv) / 265
                elif pass_concept == "LONG_PASS":
                    base_yards = random.randint(6, 24)
                    explosive_chance = 0.268 + max(0, adv) / 142
                    if adv >= 12 and random.random() < 0.12:
                        base_yards += random.randint(10, 28)
                elif pass_concept == "PLAY_ACTION":
                    base_yards = random.randint(3, 14)
                    explosive_chance = 0.152 + max(0, adv) / 305
                else:
                    base_yards = random.randint(2, 10)
                    explosive_chance = 0.185 + max(0, adv) / 265  # Legacy/default

                rating_bonus = (off_eff_pass - def_eff_defense) // 7
                coverage_penalty = max(0, (def_eff_coverage - off_eff_pass) // 12)
                yards = base_yards + rating_bonus - coverage_penalty
                yards = max(-4, min(99, yards))

            # Interception chance (pass only; no INT on sack or scramble): QB decisions/arm + discipline vs coverage/takeaway ability + coverage call
            if pass_concept == "SHORT_PASS":
                base_int = 0.0155
            elif pass_concept == "MEDIUM_PASS":
                base_int = 0.022
            elif pass_concept == "LONG_PASS":
                base_int = 0.0355
            elif pass_concept == "PLAY_ACTION":
                base_int = 0.021
            else:
                base_int = 0.022

            if coverage_call == "ZONES":
                coverage_mult = 1.12
            elif coverage_call == "MANS":
                coverage_mult = 1.03
            elif coverage_call == "ZONE_PRESSURE":
                coverage_mult = 1.06
            elif coverage_call == "MAN_PRESSURE":
                coverage_mult = 1.00
            else:
                # Legacy mapping from defense choice
                coverage_mult = 1.05 if defense_choice == "3" else (1.0 if defense_choice == "2" else 0.92)

            off_pass_security = (
                (self.qb_decision_rating * 0.45)
                + (self.qb_arm_strength * 0.20)
                + (self.off_discipline_rating * 0.20)
                + (off_eff_pass * 0.15)
            )
            def_takeaway = (
                (def_eff_coverage * 0.55)
                + (def_eff_defense * 0.20)
                + (def_eff_pass_rush * 0.15)
                + (def_eff_tackling * 0.10)
            )
            int_chance = (base_int + ((def_takeaway - off_pass_security) / 1000.0)) * coverage_mult
            int_chance = max(0.0035, min(0.090, int_chance))
            # Season target: good teams 8-14 TO, bad teams 20-35. Scale by offense ball security.
            _off_to = (self.qb_decision_rating + self.ball_security_rating + self.off_discipline_rating) / 3.0
            _to_scale = max(0.48, min(1.12, 1.5 - _off_to / 72.0))
            int_chance *= _to_scale * 1.08
            if not sack and not scramble and random.random() < int_chance:
                _safe_engine_print("INTERCEPTION!")
                interception = True
                if self.possession == "home":
                    self.interceptions_home += 1
                else:
                    self.interceptions_away += 1

            # Strip sack fumble
            off_sack_security = (
                (self.ball_security_rating * 0.45)
                + (self.off_discipline_rating * 0.30)
                + (self.qb_decision_rating * 0.25)
            )
            def_strip = (def_eff_pass_rush * 0.65) + (def_eff_tackling * 0.35)
            strip_fumble_chance = 0.0046 + ((def_strip - off_sack_security) / 1500.0)
            strip_fumble_chance = max(0.0012, min(0.022, strip_fumble_chance))
            strip_fumble_chance *= _to_scale * 1.08
            if sack and not interception and random.random() < strip_fumble_chance:
                _safe_engine_print("STRIP SACK FUMBLE!")
                fumble = True
                if self.possession == "home":
                    self.fumbles_home += 1
                else:
                    self.fumbles_away += 1

            # Incomplete: QB/accuracy vs coverage. Bad QB vs good DBs = more misses
            base_incomplete = 0.28
            inc_adj = (def_eff_coverage - 50) / 450.0 - (self.qb_decision_rating - 50) / 550.0
            incomplete_chance = max(0.18, min(0.48, base_incomplete + inc_adj))
            if not sack and not scramble and not interception and random.random() < incomplete_chance:
                yards = 0
                incomplete_pass = True
                _safe_engine_print("Incomplete pass.")
            # Explosive pass (20+): on completions only. Good O vs weak coverage = more.
            elif not sack and not scramble and not interception and random.random() < explosive_chance:
                max_yards = min(55, 99 - self.ball_position)
                if max_yards >= 22:
                    yards = random.randint(22, max_yards)

        # -------- PLAY UNDERSTANDING MODIFIER (scheme teach + player iq/coachability) --------
        try:
            from systems.play_selection import get_understanding_modifier
            off_grade = getattr(offense_team, "season_play_understanding_grade", None) if offense_team else None
            def_grade = getattr(defense_team, "season_play_understanding_grade", None) if defense_team else None
            off_mod = get_understanding_modifier(off_grade)
            def_mod = get_understanding_modifier(def_grade)
            yards = int(round(yards * off_mod / def_mod))
            yards = max(-4, min(99, yards))
        except Exception:
            pass

        # -------- APPLY YARDS --------
        self.ball_position += yards
        self.yards_to_go -= yards
        self.ball_position = max(0, min(self.ball_position, 100))

        # -------- TOUCHDOWN --------
        if self.ball_position >= 100:
            _safe_engine_print("TOUCHDOWN!")
            needs_2pt = False
            needs_pat = False
            if self.is_overtime and self.ot_period >= 2:
                # OT2+: Must attempt 2-point (add 6 for TD, 2pt attempt handled separately)
                pts = 6
                needs_2pt = True
            elif self.is_overtime:
                # OT period 1: keep automatic 7 (TD + XP rolled in) for now
                pts = 7
            else:
                # Regulation: 6 points, then PAT / 2PT choice
                pts = 6
                needs_pat = True

            if self.possession == "home":
                self.score_home += pts
            else:
                self.score_away += pts

            clock_elapsed = regulation_dead_ball_clock_seconds() if not self.is_overtime else 0
            self.time_remaining -= clock_elapsed
            if self.time_remaining < 0:
                self.time_remaining = 0

            if self.is_overtime:
                if needs_2pt:
                    self.display_status(yards)
                    return {"yards": yards, "touchdown": True, "turnover": False, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": True, "needs_2pt": True, "ot_possession_ended": False, "fumble": False}
                else:
                    self.setup_ot_possession()
                    self.display_status(yards)
                    return {"yards": yards, "touchdown": True, "turnover": False, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": True, "needs_2pt": False, "ot_possession_ended": True, "fumble": False}
            else:
                self.ball_position = 97
                self.pending_pat = True
                self.display_status(yards)
                return {
                    "yards": yards,
                    "touchdown": True,
                    "turnover": False,
                    "sack": sack,
                    "scramble": scramble,
                    "interception": interception,
                    "incomplete_pass": incomplete_pass,
                    "clock_elapsed": clock_elapsed,
                    "first_down": True,
                    "needs_pat": True,
                    "fumble": False,
                }

        # -------- TURNOVERS --------
        if interception or fumble:
            _safe_engine_print("Possession switches due to TURNOVER!")
            clock_elapsed = regulation_dead_ball_clock_seconds() if not self.is_overtime else 0
            self.time_remaining -= clock_elapsed
            if self.time_remaining < 0:
                self.time_remaining = 0

            if self.is_overtime:
                self.setup_ot_possession()
                self.display_status(yards)
                return {"yards": yards, "touchdown": False, "turnover": True, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": False, "ot_possession_ended": True, "fumble": fumble}
            else:
                self.switch_possession()
                self.display_status(yards)
                return {"yards": yards, "touchdown": False, "turnover": True, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": False, "fumble": fumble}

        # -------- FIRST DOWN --------
        first_down = self.yards_to_go <= 0
        if first_down:
            _safe_engine_print(f"{yards} yards – First Down!")
            self.down = 1
            self.yards_to_go = 10
        else:
            _safe_engine_print(f"{yards} yards")
            self.down += 1

        # -------- 4TH DOWN FAILED (we went for it and didn't convert) --------
        if self.down > 4:
            _safe_engine_print("Failed 4th Down Conversion!")
            clock_elapsed = regulation_dead_ball_clock_seconds() if not self.is_overtime else 0
            self.time_remaining -= clock_elapsed
            if self.time_remaining < 0:
                self.time_remaining = 0
            if self.is_overtime:
                self.setup_ot_possession()
                self.display_status(yards)
                return {"yards": yards, "touchdown": False, "turnover": True, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": False, "ot_possession_ended": True, "fumble": False}
            self.switch_possession()
            self.display_status(yards)
            return {"yards": yards, "touchdown": False, "turnover": True, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": False, "fumble": False}

        # -------- CLOCK --------
        # Tuned for ~120-130 regulation snaps total: shorter per snap than old 32-52s; passes tick faster than runs.
        run_clock = offense_choice == "1" or not incomplete_pass
        clock_elapsed = (
            regulation_scrimmage_clock_seconds(
                offense_choice,
                incomplete_pass=incomplete_pass,
                sack=sack,
                scramble=scramble,
            )
            if run_clock
            else 0
        )
        if run_clock:
            self.time_remaining -= clock_elapsed
            if self.time_remaining < 0:
                self.time_remaining = 0

        self.display_status(yards)
        return {"yards": yards, "touchdown": False, "turnover": False, "sack": sack, "scramble": scramble, "interception": interception, "incomplete_pass": incomplete_pass, "clock_elapsed": clock_elapsed, "first_down": first_down, "fumble": False}

    # ------------------ DISPLAY ------------------
    def display_status(self, last_play_yards=None):
        if self.ball_position < 50:
            yard_marker = f"Own {self.ball_position}"
        else:
            yard_marker = f"Opp {100 - self.ball_position}"

        if last_play_yards is not None:
            _safe_engine_print(f"Play Result: {last_play_yards} yards")

        _safe_engine_print(f"Possession: {self.possession.upper()}")
        _safe_engine_print(f"Down: {self.down} & {self.yards_to_go}")
        _safe_engine_print(f"Ball: {yard_marker} yard line")
        _safe_engine_print(f"Score: Home {self.score_home} - Away {self.score_away}")
        _safe_engine_print(f"Time: {self.time_remaining // 60}:{self.time_remaining % 60:02}")
        _safe_engine_print(f"INT - Home: {self.interceptions_home} | Away: {self.interceptions_away}")
        _safe_engine_print(f"FUM - Home: {self.fumbles_home} | Away: {self.fumbles_away}")
        _safe_engine_print("----------------------------")

    # ------------------ END GAME SUMMARY ------------------
    def end_game_summary(self):
        _safe_engine_print("\n===== FINAL GAME STATS =====")
        _safe_engine_print(f"Final Score: Home {self.score_home} - Away {self.score_away}")
        _safe_engine_print(f"Interceptions - Home: {self.interceptions_home} | Away: {self.interceptions_away}")
        _safe_engine_print(f"Fumbles - Home: {self.fumbles_home} | Away: {self.fumbles_away}")
        _safe_engine_print("============================")

    def advance_quarter(self):
        if getattr(self, "pending_pat", False):
            return
        if self.time_remaining <= 0 and not self.is_overtime:
            _safe_engine_print(f"End of Quarter {self.quarter}")
            if self.quarter == 4 and self.score_home == self.score_away:
                # NCAA OT: Regulation ended tied
                self.start_overtime()
            else:
                ended_quarter = self.quarter
                self.quarter += 1
                if self.quarter <= 4:
                    self.time_remaining = 12 * 60
                    if ended_quarter == 2:
                        # Halftime only: new kickoff (not after Q1 or Q3).
                        # Interactive coach games use pending_kickoff flow from game_service.
                        if hasattr(self, "pending_kickoff"):
                            self.pending_kickoff = True
                            # Team that received opening kickoff now kicks to start 2nd half.
                            self.kickoff_kicking_team = self.opening_kickoff_receiver
                            self.possession = self.kickoff_kicking_team
                            self.down = 1
                            self.yards_to_go = 10
                            # Kickoff spot at kicking team's own 40 until kickoff play resolves.
                            self.ball_position = KICKOFF_TEE_YARDS
                        else:
                            self.apply_halftime_kickoff()
                    # Q1→Q2 and Q3→Q4: keep ball, down, and distance

    def is_game_over(self):
        if self.ot_winner is not None:
            return True
        if self.is_overtime:
            return False
        return self.quarter > 4

    def check_ot_period_end(self):
        """After both teams have had possession in OT1/OT2, compare scores and set ot_winner or advance to next OT."""
        if not self.is_overtime or self.ot_2pt_mode:
            return
        self.ot_possession_count += 1
        if self.ot_possession_count >= 2:
            # Both teams had possession - compare scores
            if self.score_home > self.score_away:
                self.ot_winner = "home"
                _safe_engine_print(f"\n*** OVERTIME {self.ot_period} COMPLETE *** HOME WINS!")
            elif self.score_away > self.score_home:
                self.ot_winner = "away"
                _safe_engine_print(f"\n*** OVERTIME {self.ot_period} COMPLETE *** AWAY WINS!")
            else:
                # Tied - next OT period
                self.ot_period += 1
                self.ot_possession_count = 0
                if self.ot_period >= 3:
                    # OT3+: 2-point shootout
                    self.ot_2pt_mode = True
                    self.ot_2pt_round = {"home": None, "away": None}
                    _safe_engine_print(f"\n*** OVERTIME {self.ot_period} *** 2-POINT CONVERSION SHOOTOUT")
                else:
                    # OT2: Alternate who goes first (team that went second in previous OT goes first)
                    self.possession = "away" if self.possession == "home" else "home"
                    self.ball_position = 75
                    self.down = 1
                    self.yards_to_go = 10
                    _safe_engine_print(f"\n*** OVERTIME {self.ot_period} ***")
                self.display_status()
