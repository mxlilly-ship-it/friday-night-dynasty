"""
Coach inbox: simulated email/messages for immersion (Team tab UI).

Generates structured emails scaled by program prestige, with weekly scheduling
(Mon–Sun labels), sentiment from results, and optional player choices that
nudge abstract meters (morale, admin trust, etc.).
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- Sender type tags (stable ids for filtering) ---
SENDER_FOOTBALL_PROGRAM = "Football Program"
SENDER_ASSISTANT_COACH = "Assistant Coaches"
SENDER_PLAYER = "Players"
SENDER_TEAM_CAPTAIN = "Team Captain"
SENDER_DISGRUNTLED_PLAYER = "Disgruntled Player"
SENDER_INJURED_PLAYER = "Injured Player"
SENDER_TRAINER = "Athletic Trainer"
SENDER_ADMIN = "School Administration"
SENDER_AD = "Athletic Director"
SENDER_ASST_PRINCIPAL = "Assistant Principal"
SENDER_PRINCIPAL = "Principal"
SENDER_GUIDANCE = "Guidance Counselor"
SENDER_TEACHER = "Teachers"
SENDER_PARENTS = "Parents"
SENDER_COMMUNITY = "Community / Parents"
SENDER_FANS_ALUMNI = "Fans / Alumni"
SENDER_YOUTH_COACH = "Youth Coaches"
SENDER_COMMUNITY_LEADER = "Community Leaders"
SENDER_BOOSTER_CLUB = "Booster Club"
SENDER_BOOSTER_PRESIDENT = "Booster Club President"
SENDER_SPONSOR = "Sponsors"
SENDER_FUNDRAISING = "Fundraising Coordinator"
SENDER_REPORTER = "Newspaper Reporter"
SENDER_RECRUITING_SERVICE = "Recruiting Services"
SENDER_COLLEGE_RECRUITER = "College Recruiters"
SENDER_7ON7 = "7-on-7 Coaches / Trainers"
SENDER_SCHOOL_BOARD = "School Board Member"
SENDER_STATE_ASSOC = "State Athletic Association"
SENDER_COMPLIANCE = "Compliance Officer"

MAX_STORED_EMAILS = 180
DAYS_ORDER = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def ensure_coach_inbox(state: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure ``state['coach_inbox']`` exists with defaults; returns the inbox dict."""
    inbox = state.setdefault("coach_inbox", {})
    if not isinstance(inbox, dict):
        inbox = {}
        state["coach_inbox"] = inbox
    inbox.setdefault("emails", [])
    if not isinstance(inbox["emails"], list):
        inbox["emails"] = []
    inbox.setdefault("program_morale", 58)
    inbox.setdefault("public_perception", 55)
    inbox.setdefault("admin_trust", 52)
    inbox.setdefault("job_security", 72)
    inbox.setdefault("last_week_sim_batch_key", None)
    inbox.setdefault("last_playoff_batch_key", None)
    seed_starter_coach_emails(state, inbox)
    return inbox


def seed_starter_coach_emails(state: Dict[str, Any], inbox: Dict[str, Any]) -> None:
    """One-time generic starter mail; ``[State]`` comes from league JSON / save ``state`` field."""
    seed_generic_starter_coach_emails(state, inbox)


def _clamp_meter(v: Any, lo: int = 0, hi: int = 100) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 50
    return max(lo, min(hi, n))


def _prestige_volume_range(prestige: int, rng: random.Random) -> Tuple[int, int]:
    """Return (lo, hi) inclusive email count for a full week sim batch."""
    p = max(1, min(15, int(prestige)))
    if p <= 5:
        return 2, rng.randint(4, 5)
    if p <= 10:
        return 5, rng.randint(8, 10)
    return 10, rng.randint(14, min(20, 10 + p))


def _pick_name(pool: List[str], rng: random.Random) -> str:
    return str(rng.choice(pool))


def _user_team_row(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ut = state.get("user_team")
    if not ut:
        return None
    for row in state.get("teams") or []:
        if isinstance(row, dict) and row.get("name") == ut:
            return row
    return None


def _streak_and_last_user_game(state: Dict[str, Any], user_team: str) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    """One reverse scan of ``week_results``: W/L streak (newest-first) and most recent game (same semantics as old pair of helpers)."""
    weeks = state.get("week_results") or []
    last_detail: Optional[Dict[str, Any]] = None
    streak_ch: Optional[str] = None
    streak_n = 0
    for wi in range(len(weeks) - 1, -1, -1):
        wk = weeks[wi] or []
        for gi in range(len(wk) - 1, -1, -1):
            g = wk[gi]
            if not isinstance(g, dict) or not g.get("played"):
                continue
            h, a = g.get("home"), g.get("away")
            if user_team not in (h, a):
                continue
            hs = int(g.get("home_score", 0) or 0)
            as_ = int(g.get("away_score", 0) or 0)
            if hs == as_:
                continue
            if user_team == h:
                outcome = "W" if hs > as_ else "L"
                user_score, opp_score = hs, as_
                opp = a
            else:
                outcome = "W" if as_ > hs else "L"
                user_score, opp_score = as_, hs
                opp = h
            if last_detail is None:
                margin = user_score - opp_score
                last_detail = {
                    "week_index": wi,
                    "home": h,
                    "away": a,
                    "user_score": user_score,
                    "opp_score": opp_score,
                    "opponent": opp,
                    "margin": margin,
                    "won": user_score > opp_score,
                }
            if streak_ch is None:
                streak_ch = outcome
                streak_n = 1
            elif outcome == streak_ch:
                streak_n += 1
            else:
                return streak_n, streak_ch, last_detail
    if streak_ch is None:
        return 0, "W", None
    return streak_n, streak_ch, last_detail


def _update_sentiment_from_game(inbox: Dict[str, Any], last: Dict[str, Any], prestige: int, rng: random.Random) -> None:
    won = bool(last.get("won"))
    margin = int(last.get("margin", 0))
    blow = abs(margin) >= 21
    pm = _clamp_meter(inbox.get("program_morale"))
    pp = _clamp_meter(inbox.get("public_perception"))
    pressure = 1.0 + max(0, prestige - 8) * 0.08
    if won:
        pm = min(100, pm + (5 if blow else 3))
        pp = min(100, pp + (4 if blow else 2))
    else:
        pm = max(0, pm - int(round((6 if blow else 4) * pressure)))
        pp = max(0, pp - int(round((5 if blow else 3) * pressure)))
    inbox["program_morale"] = pm
    inbox["public_perception"] = pp


def _make_email(
    *,
    sender_type: str,
    sender_name: str,
    subject: str,
    body: str,
    category: str,
    year: int,
    week: int,
    virtual_day: str,
    trigger_conditions: List[str],
    choices: Optional[List[Dict[str, Any]]] = None,
    effects_if_ignored: Optional[Dict[str, int]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    if rng is not None:
        eid = f"{rng.getrandbits(64):016x}{rng.getrandbits(32):08x}"
    else:
        eid = str(uuid.uuid4())
    return {
        "id": eid,
        "sender_type": sender_type,
        "sender_name": sender_name,
        "subject": subject,
        "body": body,
        "category": category,
        "year": int(year),
        "week": int(week),
        "virtual_day": virtual_day,
        "read": False,
        "resolved": False,
        "chosen_choice_id": None,
        "trigger_conditions": list(trigger_conditions),
        "effects_if_ignored": dict(effects_if_ignored or {}),
        "choices": choices,
    }


STARTER_PACK_VERSION = 1


def _starter_display_coach_name(state: Dict[str, Any]) -> str:
    row = _user_team_row(state)
    if not row:
        return "Coach"
    c = row.get("coach")
    if isinstance(c, dict):
        n = str(c.get("name") or "").strip()
        return n or "Coach"
    return "Coach"


def _starter_state_name(state: Dict[str, Any]) -> str:
    from systems.league_metadata import ensure_league_metadata_in_state

    meta = ensure_league_metadata_in_state(state)
    return str(meta.get("state") or "your state").strip() or "your state"


def _subst_starter_placeholders(text: str, school: str, coach: str, state_name: str) -> str:
    return (
        text.replace("[school name]", school)
        .replace("[coach name]", coach)
        .replace("[State]", state_name)
        .replace("[School name]", school)
        .replace("[Coach name]", coach)
    )


def _starter_pack_already_seeded(inbox: Dict[str, Any]) -> bool:
    return bool(
        inbox.get("starter_coach_emails_v1")
        or inbox.get("wv_starter_coach_emails_v1")
        or inbox.get("oh_starter_coach_emails_v1")
    )


def seed_generic_starter_coach_emails(state: Dict[str, Any], inbox: Dict[str, Any]) -> None:
    """Append generic starter mail once; [State] from save metadata (league JSON)."""
    if _starter_pack_already_seeded(inbox):
        return
    ut = str(state.get("user_team") or "").strip()
    if not ut:
        return
    emails = inbox.get("emails")
    if not isinstance(emails, list):
        return
    if len(emails) > 0:
        inbox["starter_coach_emails_v1"] = STARTER_PACK_VERSION
        return

    from systems.starter_email_specs import GENERIC_STARTER_SPECS

    school = ut
    coach = _starter_display_coach_name(state)
    state_name = _starter_state_name(state)
    year = int(state.get("current_year", 1) or 1)
    week = max(1, int(state.get("current_week", 1) or 1))
    rng = random.Random((hash(ut) ^ STARTER_PACK_VERSION) % (2**32))

    built: List[Dict[str, Any]] = []
    for i, spec in enumerate(GENERIC_STARTER_SPECS):
        tone = str(spec.get("tone") or "neutral")
        built.append(
            _make_email(
                sender_type=str(spec["sender_type"]),
                sender_name=str(spec["sender_name"]),
                subject=_subst_starter_placeholders(str(spec["subject"]), school, coach, state_name),
                body=_subst_starter_placeholders(str(spec["body"]), school, coach, state_name),
                category=str(spec["category"]),
                year=year,
                week=week,
                virtual_day=DAYS_ORDER[i % 7],
                trigger_conditions=["starter_pack", f"generic_{tone}"],
                rng=rng,
            )
        )
    _append_emails(inbox, built)
    inbox["starter_coach_emails_v1"] = STARTER_PACK_VERSION


def _append_emails(inbox: Dict[str, Any], new_rows: List[Dict[str, Any]]) -> None:
    emails: List[Dict[str, Any]] = inbox.setdefault("emails", [])
    for e in new_rows:
        emails.append(e)
    if len(emails) > MAX_STORED_EMAILS:
        emails[:] = emails[-MAX_STORED_EMAILS:]


def _spread_days(n: int, rng: random.Random) -> List[str]:
    if n <= 0:
        return []
    out: List[str] = []
    for i in range(n):
        out.append(DAYS_ORDER[i % 7])
    rng.shuffle(out)
    return out


def generate_week_sim_emails(
    state: Dict[str, Any],
    *,
    completed_week: int,
) -> None:
    """After a regular-season week is fully simulated, append a batch of emails."""
    inbox = ensure_coach_inbox(state)
    ut = str(state.get("user_team") or "")
    if not ut:
        return
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase not in ("regular", "playoffs"):
        return

    year = int(state.get("current_year", 1))
    batch_key = f"{year}|{phase}|{completed_week}|week_sim"
    if inbox.get("last_week_sim_batch_key") == batch_key:
        return

    row = _user_team_row(state)
    prestige = int(row.get("prestige", 5) or 5) if row else 5
    school = ut
    rng = random.Random((hash(batch_key) ^ hash(ut)) % (2**32))
    _mk_email = _make_email

    def em(**kwargs: Any) -> Dict[str, Any]:
        kwargs["rng"] = rng
        return _mk_email(**kwargs)

    standings = state.get("standings") or {}
    srow = standings.get(ut) or {}
    wins = int(srow.get("wins", 0) or 0)
    losses = int(srow.get("losses", 0) or 0)

    streak_n, streak_ch, last = _streak_and_last_user_game(state, ut)

    if last:
        _update_sentiment_from_game(inbox, last, prestige, rng)

    morale = _clamp_meter(inbox.get("program_morale"))
    sentiment_neg = morale < 45 or (last and not last["won"] and streak_ch == "L" and streak_n >= 2)

    lo, hi = _prestige_volume_range(prestige, rng)
    target = rng.randint(lo, hi)
    if phase == "playoffs":
        target = max(3, min(hi, target // 2 + 3))

    days = _spread_days(target, rng)
    emails: List[Dict[str, Any]] = []

    ad_names = ["Pat Morrison", "Jordan Reeves", "Alex Kim", "Sam Ortiz"]
    reporter_names = ["Chris Vale", "Morgan Ellis", "Riley Boone"]
    booster_names = ["Terry Whitfield", "Dana Cho", "Marcus Ingle"]
    principal_names = ["Dr. Helen Marsh", "Robert Pruitt"]
    trainer_names = ["Jamie Collins", "Casey Wu"]
    asst_names = ["Coach Vega", "Coach Hardy", "Coach Nguyen"]
    captain_names = ["Your team captains"]

    def take_day() -> str:
        if days:
            return days.pop(0)
        return rng.choice(DAYS_ORDER)

    # --- Monday: reactions ---
    if last and phase == "regular":
        opp = str(last.get("opponent") or "opponent")
        if last["won"]:
            if abs(last["margin"]) >= 21:
                emails.append(
                    em(
                        sender_type=SENDER_REPORTER,
                        sender_name=_pick_name(reporter_names, rng),
                        subject=f"Cover story: {school} dominates {opp}",
                        body=(
                            f"Coach — the local desk is running a short feature on Friday's win over {opp}. "
                            f"The community loves a statement win. Keep the players focused; noise gets louder when you're winning big."
                        ),
                        category="media",
                        year=year,
                        week=completed_week,
                        virtual_day="Monday",
                        trigger_conditions=["win", "blowout"],
                    )
                )
            else:
                emails.append(
                    em(
                        sender_type=SENDER_AD,
                        sender_name=_pick_name(ad_names, rng),
                        subject=f"Solid night vs {opp}",
                        body=(
                            f"Watched the film cut you sent over — good execution down the stretch against {opp}. "
                            f"Let's keep grades and attendance clean this week while confidence is up."
                        ),
                        category="admin",
                        year=year,
                        week=completed_week,
                        virtual_day="Monday",
                        trigger_conditions=["win"],
                        choices=[
                            {
                                "id": "thanks_staff",
                                "text": "Reply: Credit the staff and move on",
                                "effects": {"admin_trust": 1, "program_morale": 1},
                            },
                            {
                                "id": "promise_cleanup",
                                "text": "Promise extra focus on details in practice",
                                "effects": {"admin_trust": 2, "program_morale": 0},
                            },
                        ],
                    )
                )
        else:
            tone = "sharp" if prestige >= 11 else "measured"
            emails.append(
                em(
                    sender_type=SENDER_BOOSTER_PRESIDENT if prestige >= 10 else SENDER_BOOSTER_CLUB,
                    sender_name=_pick_name(booster_names, rng),
                    subject=f"After the {opp} game",
                    body=(
                        f"Coach, a few members reached out after the loss to {opp}. "
                        + (
                            "Expectations here are championship-level — we need a cleaner plan before district play."
                            if tone == "sharp"
                            else "We're behind you, but we'd like to see the program respond with discipline and effort this week."
                        ),
                    ),
                    category="boosters",
                    year=year,
                    week=completed_week,
                    virtual_day="Monday",
                    trigger_conditions=["loss"],
                    choices=[
                        {
                            "id": "ack_hear",
                            "text": "Acknowledge concerns; vow to correct fundamentals",
                            "effects": {"public_perception": 1, "program_morale": -1},
                        },
                        {
                            "id": "brief",
                            "text": "Keep response short and internal",
                            "effects": {"public_perception": -1, "job_security": -1},
                        },
                    ],
                )
            )
            if prestige >= 12:
                emails.append(
                    em(
                        sender_type=SENDER_REPORTER,
                        sender_name=_pick_name(reporter_names, rng),
                        subject="Notebook: what went wrong Friday?",
                        body=(
                            f"I'm filing a short piece on the loss to {opp}. "
                            f"Can you give one sentence on what you'll fix in practice? (Or I can run with 'no comment'.)"
                        ),
                        category="media",
                        year=year,
                        week=completed_week,
                        virtual_day="Monday",
                        trigger_conditions=["loss", "high_prestige"],
                        choices=[
                            {
                                "id": "quote_fix",
                                "text": "Offer a constructive quote",
                                "effects": {"public_perception": 2, "admin_trust": 0},
                            },
                            {
                                "id": "no_comment",
                                "text": "No comment",
                                "effects": {"public_perception": -2},
                            },
                        ],
                    )
                )

    # --- Tue–Wed: academics / training noise ---
    if target >= 4 and phase == "regular":
        emails.append(
            em(
                sender_type=SENDER_GUIDANCE,
                sender_name="Taylor Brooks",
                subject="Academic check-in",
                body=(
                    "A few players are trending close to eligibility thresholds. "
                    "Nothing alarming yet — please remind position groups that study hall blocks matter."
                ),
                category="admin",
                year=year,
                week=completed_week,
                virtual_day="Tuesday",
                trigger_conditions=["academic_routine"],
            )
        )
    if target >= 5:
        emails.append(
            em(
                sender_type=SENDER_TRAINER,
                sender_name=_pick_name(trainer_names, rng),
                subject="Injury / maintenance notes",
                body=(
                    "Trainers will run a lighter contact plan if we see heavy lower-leg complaints this week. "
                    "Shout if you want anyone held from team periods."
                ),
                category="player_issue",
                year=year,
                week=completed_week,
                virtual_day="Wednesday",
                trigger_conditions=["training"],
            )
        )

    # --- Player sentiment ---
    if sentiment_neg and last and not last["won"]:
        emails.append(
            em(
                sender_type=SENDER_DISGRUNTLED_PLAYER,
                sender_name="Anonymous player (via captain)",
                subject="Playing time / roles",
                body=(
                    "Some guys are frustrated with how reps shook out late in the game. "
                    "Not asking for a promise — just want clarity on what earns snaps."
                ),
                category="player_issue",
                year=year,
                week=completed_week,
                virtual_day="Tuesday",
                trigger_conditions=["morale_low"],
                choices=[
                    {
                        "id": "team_meeting",
                        "text": "Schedule a short leadership meeting",
                        "effects": {"program_morale": 3, "admin_trust": 0},
                    },
                    {
                        "id": "ignore_soft",
                        "text": "Defer until weekly unit meetings",
                        "effects": {"program_morale": -2},
                    },
                ],
            )
        )
    elif last and last["won"] and streak_n >= 3:
        emails.append(
            em(
                sender_type=SENDER_TEAM_CAPTAIN,
                sender_name=captain_names[0],
                subject="Locker room energy",
                body=(
                    f"We're rolling ({wins}-{losses}). Guys want to keep the standard high — "
                    f"any chance we get a little more red-zone work this week?"
                ),
                category="performance",
                year=year,
                week=completed_week,
                virtual_day="Wednesday",
                trigger_conditions=["win_streak"],
            )
        )

    # --- Thursday prep / staff ---
    if target >= 6:
        emails.append(
            em(
                sender_type=SENDER_ASSISTANT_COACH,
                sender_name=_pick_name(asst_names, rng),
                subject="Scout tendencies",
                body=(
                    "Put together a 1-pager on next opponent formation tendencies. "
                    "Tell me if you want it tighter for Friday installs."
                ),
                category="performance",
                year=year,
                week=completed_week,
                virtual_day="Thursday",
                trigger_conditions=["prep"],
            )
        )

    # --- Friday hype ---
    emails.append(
        em(
            sender_type=SENDER_FANS_ALUMNI,
            sender_name="Friday Night Lights Alumni Group",
            subject="Good luck tonight",
            body=(
                "We'll be in the stands. Feed the linemen, protect the ball, and represent the school well."
            ),
            category="community",
            year=year,
            week=completed_week,
            virtual_day="Friday",
            trigger_conditions=["community"],
        )
    )

    # --- Weekend recruiting / governance (prestige scaled) ---
    if prestige >= 7 and phase == "regular":
        emails.append(
            em(
                sender_type=SENDER_COLLEGE_RECRUITER,
                sender_name="Regional scouting staff",
                subject="Campus visit interest",
                body=(
                    f"We're tracking a few underclassmen at {school}. "
                    f"If you have academic/character notes, send them when you can."
                ),
                category="recruiting",
                year=year,
                week=completed_week,
                virtual_day="Saturday",
                trigger_conditions=["recruiting", "mid_prestige"],
            )
        )
    if prestige >= 12:
        emails.append(
            em(
                sender_type=SENDER_SCHOOL_BOARD,
                sender_name="Board office",
                subject="Program visibility",
                body=(
                    "The district office noted higher community engagement around football. "
                    "Please keep communications professional and timely when media reaches out."
                ),
                category="admin",
                year=year,
                week=completed_week,
                virtual_day="Sunday",
                trigger_conditions=["governance", "high_prestige"],
            )
        )

    # --- Facilities / program (culture grade proxy) ---
    culture = int(row.get("culture_grade", 5) or 5) if row else 5
    if culture <= 4 and rng.random() < 0.45:
        emails.append(
            em(
                sender_type=SENDER_PRINCIPAL,
                sender_name=_pick_name(principal_names, rng),
                subject="Culture and conduct",
                body=(
                    "I want football to set the tone in the hallways. "
                    "If you need support on discipline follow-ups, loop me in early."
                ),
                category="admin",
                year=year,
                week=completed_week,
                virtual_day=take_day(),
                trigger_conditions=["culture_low"],
            )
        )

    # --- Fill toward target with generic weighted pool ---
    filler_senders: List[Tuple[str, str, str, Callable[[], str]]] = [
        (SENDER_TEACHER, "Faculty liaison", "classroom", lambda: "Thanks for keeping athletes accountable in class this week."),
        (SENDER_PARENTS, "Parent committee", "community", lambda: "Carpool and concession volunteers still needed — appreciate anything you can signal-boost."),
        (SENDER_FUNDRAISING, "Athletics office", "boosters", lambda: "Reminder: sponsor packets are due soon; happy to help with talking points."),
        (SENDER_COMPLIANCE, "Athletics compliance", "admin", lambda: "Please confirm your travel roster matches the submitted eligibility list."),
        (SENDER_STATE_ASSOC, "WVSSAC office", "admin", lambda: "Routine postseason eligibility memo attached conceptually — no action unless you host a regional."),
        (SENDER_RECRUITING_SERVICE, "Regional rankings desk", "recruiting", lambda: f"We're updating {school}'s profile — send any corrected heights/weights."),
        (SENDER_7ON7, "Skills trainer network", "recruiting", lambda: "Open invite for QB/WR work Sunday evening if you want skill guys getting extra reps."),
        (SENDER_YOUTH_COACH, "Youth league president", "community", lambda: "Youth night ideas: simple handshake tunnel pregame works well with our kids."),
        (SENDER_COMMUNITY_LEADER, "Chamber of Commerce", "community", lambda: "Friday games drive traffic for local businesses — thanks for running a first-class operation."),
        (SENDER_SPONSOR, "Local business partner", "boosters", lambda: "Logo placement looked great last week. Appreciate the shout-out in the program if possible."),
    ]
    rng.shuffle(filler_senders)
    filler_work: List[Tuple[str, str, str, Callable[[], str]]] = []
    for tup in filler_senders:
        st, nm, cat, body_fn = tup
        if prestige <= 6 and cat in ("recruiting", "media") and rng.random() < 0.35:
            continue
        filler_work.append(tup)
    if not filler_work:
        filler_work = list(filler_senders)
    rng.shuffle(filler_work)
    idx = 0
    while len(emails) < target and filler_work:
        st, nm, cat, body_fn = filler_work[idx % len(filler_work)]
        idx += 1
        emails.append(
            em(
                sender_type=st,
                sender_name=nm,
                subject="Quick note",
                body=body_fn(),
                category=cat,
                year=year,
                week=completed_week,
                virtual_day=take_day(),
                trigger_conditions=["filler"],
            )
        )

    inbox["last_week_sim_batch_key"] = batch_key
    _append_emails(inbox, emails[:target])


def generate_playoff_round_emails(state: Dict[str, Any]) -> None:
    """Light batch after playoff simulation / round (user team)."""
    inbox = ensure_coach_inbox(state)
    ut = str(state.get("user_team") or "")
    if not ut:
        return
    year = int(state.get("current_year", 1))
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    flat: List[Dict[str, Any]] = []
    for sub in (playoffs.get("by_class") or {}).values():
        if isinstance(sub, dict):
            flat.extend(list(sub.get("bracket_results") or []))
    key = f"{year}|playoff|{len(flat)}"
    if inbox.get("last_playoff_batch_key") == key:
        return
    row = _user_team_row(state)
    prestige = int(row.get("prestige", 5) or 5) if row else 5

    last_g = None
    for g in reversed(flat):
        if not isinstance(g, dict):
            continue
        if ut not in (g.get("home"), g.get("away")):
            continue
        last_g = g
        break
    if not last_g:
        return

    rng = random.Random((hash(key) ^ hash(ut)) % (2**32))
    _mk_email = _make_email

    def em(**kwargs: Any) -> Dict[str, Any]:
        kwargs["rng"] = rng
        return _mk_email(**kwargs)

    hs = int(last_g.get("home_score", 0) or 0)
    as_ = int(last_g.get("away_score", 0) or 0)
    h, a = last_g.get("home"), last_g.get("away")
    user_is_home = ut == h
    us = hs if user_is_home else as_
    them = as_ if user_is_home else hs
    won = us > them
    rnd = str(last_g.get("round") or "Playoffs")

    emails: List[Dict[str, Any]] = []
    if won:
        emails.append(
            em(
                sender_type=SENDER_REPORTER,
                sender_name="Press box",
                subject=f"{rnd}: {ut} advances",
                body=(
                    f"Coach — congrats on moving on. I'll keep the story centered on the players unless you want a quote on scheme."
                ),
                category="media",
                year=year,
                week=int(state.get("current_week", 1) or 1),
                virtual_day="Saturday",
                trigger_conditions=["playoff_win"],
            )
        )
    else:
        emails.append(
            em(
                sender_type=SENDER_AD,
                sender_name="Athletic Director",
                subject="Postseason exit — debrief",
                body=(
                    f"Tough ending in {rnd}. When you're ready, let's do a short debrief on injuries, eligibility, and spring priorities."
                ),
                category="admin",
                year=year,
                week=int(state.get("current_week", 1) or 1),
                virtual_day="Sunday",
                trigger_conditions=["playoff_loss"],
            )
        )
    if prestige >= 10:
        emails.append(
            em(
                sender_type=SENDER_BOOSTER_PRESIDENT,
                sender_name="Boosters",
                subject="Playoff note",
                body=(
                    "Appreciate how hard the staff pushed this postseason. We'll discuss banquet timing separately."
                    if won
                    else "Disappointed, but we trust the process. Expect more noise if we underperform early next year."
                ),
                category="boosters",
                year=year,
                week=int(state.get("current_week", 1) or 1),
                virtual_day="Sunday",
                trigger_conditions=["playoff_booster"],
            )
        )

    inbox["last_playoff_batch_key"] = key
    _append_emails(inbox, emails)


def generate_coach_game_touch_emails(
    state: Dict[str, Any],
    *,
    home: str,
    away: str,
    hs: int,
    as_: int,
    rng: Optional[random.Random] = None,
) -> None:
    """A smaller pulse after a user-coached game (regular season)."""
    ut = str(state.get("user_team") or "")
    if ut not in (home, away):
        return
    if str(state.get("season_phase") or "").strip().lower() != "regular":
        return
    inbox = ensure_coach_inbox(state)
    year = int(state.get("current_year", 1))
    week = int(state.get("current_week", 1) or 1)
    rng = rng or random.Random()
    _mk_email = _make_email

    def em(**kwargs: Any) -> Dict[str, Any]:
        kwargs["rng"] = rng
        return _mk_email(**kwargs)

    us, them = (hs, as_) if ut == home else (as_, hs)
    won = us > them
    opp = away if ut == home else home
    margin = us - them
    last = {"won": won, "margin": margin, "opponent": opp}
    row = _user_team_row(state)
    prestige = int(row.get("prestige", 5) or 5) if row else 5
    _update_sentiment_from_game(inbox, last, prestige, rng)

    extras: List[Dict[str, Any]] = []
    if won:
        extras.append(
            em(
                sender_type=SENDER_FOOTBALL_PROGRAM,
                sender_name="Program office",
                subject="Game film uploaded",
                body=f"Your cut vs {opp} is tagged for staff review. Nice work getting the win on the field.",
                category="performance",
                year=year,
                week=week,
                virtual_day="Monday",
                trigger_conditions=["coach_played", "win"],
            )
        )
    else:
        extras.append(
            em(
                sender_type=SENDER_ASSISTANT_COACH,
                sender_name="Staff thread",
                subject=f"Quick thoughts — {opp}",
                body="We should tighten third-down communication. I can bring a cut-up Tuesday.",
                category="performance",
                year=year,
                week=week,
                virtual_day="Monday",
                trigger_conditions=["coach_played", "loss"],
            )
        )
    _append_emails(inbox, extras)


def apply_choice_effects(inbox: Dict[str, Any], effects: Dict[str, Any]) -> None:
    for k, dv in (effects or {}).items():
        if k not in ("program_morale", "public_perception", "admin_trust", "job_security"):
            continue
        try:
            delta = int(dv)
        except (TypeError, ValueError):
            continue
        cur = _clamp_meter(inbox.get(k))
        inbox[k] = _clamp_meter(cur + delta)


def mark_emails_read(inbox: Dict[str, Any], ids: List[str]) -> None:
    want = set(ids)
    for e in inbox.get("emails") or []:
        if isinstance(e, dict) and e.get("id") in want:
            e["read"] = True


def delete_emails(inbox: Dict[str, Any], ids: List[str]) -> int:
    """Remove messages by id. Returns number removed."""
    want = {str(x) for x in ids if x}
    if not want:
        return 0
    emails = inbox.get("emails")
    if not isinstance(emails, list):
        return 0
    kept = [e for e in emails if isinstance(e, dict) and str(e.get("id") or "") not in want]
    removed = len(emails) - len(kept)
    if removed:
        inbox["emails"] = kept
    return removed


def resolve_email_choice(inbox: Dict[str, Any], email_id: str, choice_id: str) -> bool:
    for e in inbox.get("emails") or []:
        if not isinstance(e, dict) or e.get("id") != email_id:
            continue
        if e.get("resolved"):
            return False
        choices = e.get("choices")
        if not isinstance(choices, list):
            return False
        picked = None
        for c in choices:
            if isinstance(c, dict) and str(c.get("id")) == str(choice_id):
                picked = c
                break
        if not picked:
            return False
        apply_choice_effects(inbox, picked.get("effects") or {})
        e["resolved"] = True
        e["chosen_choice_id"] = str(choice_id)
        e["read"] = True
        return True
    return False
