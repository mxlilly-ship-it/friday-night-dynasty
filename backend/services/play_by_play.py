import random


RUN_GAIN_OPENERS = [
    "{rb} takes the handoff",
    "{rb} gets the carry",
    "{rb} takes it up the middle",
    "{rb} finds the ball in his belly",
    "{rb} gets the call",
    "{rb} pounds it inside",
    "{rb} heads off right guard",
    "{rb} follows the blockers",
]

RUN_GAIN_MIDDLES = [
    "breaks through the first wave",
    "slips a tackle at the line",
    "finds a crease in the front",
    "cuts back into daylight",
    "keeps his legs driving",
    "leans through contact",
    "bounces off a defender",
    "plants and accelerates",
]

RUN_GAIN_ENDINGS = [
    "tackled for a {yards}-yard gain by {tackler}.",
    "dragged down by {tackler} after {yards} yards.",
    "finally brought down by {tackler} for {yards} yards.",
    "stopped by {tackler} after picking up {yards}.",
    "wrapped up by {tackler} at {yards} yards.",
    "hauled down by {tackler} with {yards} gained.",
]

RUN_LOSS_TEMPLATES = [
    "{rb} is met in the backfield by {tackler} for a loss of {ay}.",
    "{tackler} knifes in and drops {rb} for a {ay}-yard loss.",
    "{rb} tries to bounce outside, but {tackler} tracks him down for minus {ay}.",
    "{rb} is swallowed up by {tackler} and loses {ay} yards.",
    "{tackler} shoots the gap and buries {rb} for a loss of {ay}.",
]

RUN_NOGAIN_TEMPLATES = [
    "{rb} gets the handoff and {tackler} stonewalls him for no gain.",
    "{rb} is stacked up immediately by {tackler}. No gain.",
    "{tackler} fills the hole and {rb} is stopped at the line.",
    "{rb} lowers his shoulder, but {tackler} holds the point. No gain.",
]

PASS_COMPLETE_OPENERS = [
    "{qb} drops back and fires to {wr}",
    "{qb} looks over the middle for {wr}",
    "{qb} zips one to {wr}",
    "{qb} hits {wr} in stride",
    "{qb} finds {wr} on the route",
    "{qb} steps up and throws to {wr}",
    "{qb} delivers to {wr}",
]

PASS_COMPLETE_ENDINGS = [
    "for {yards} yards before {tackler} makes the stop.",
    "and {tackler} brings him down after {yards}.",
    "for a {yards}-yard pickup before {tackler} closes.",
    "for {yards}, then {tackler} finishes the tackle.",
    "for {yards} as {tackler} finally gets him to the turf.",
]

PASS_INCOMPLETE_TEMPLATES = [
    "{qb} throws to {wr}, incomplete.",
    "{qb} targets {wr} but it's off the mark.",
    "{qb} and {wr} can't connect. Incomplete pass.",
    "{qb} lets it go for {wr}, and it falls harmlessly incomplete.",
    "{wr} can't come down with it on {qb}'s throw.",
]

PASS_INT_TEMPLATES = [
    "{qb} throws toward {wr}; intercepted by {db} of {defense_team}.",
    "{qb} tries to force it to {wr}, and {db} picks it off for {defense_team}.",
    "{qb} fires to {wr}, but {db} jumps the route and intercepts it.",
    "{qb} is intercepted by {db} while targeting {wr}.",
    "{db} undercuts {wr}'s route and picks off {qb}.",
]

SACK_TEMPLATES = [
    "{rusher} sacks {qb} for a loss of {ay}.",
    "{qb} goes down! {rusher} gets home for minus {ay}.",
    "{rusher} beats the block and drops {qb} for a {ay}-yard loss.",
    "{qb} is wrapped up by {rusher} for a sack of {ay}.",
]

STRIP_SACK_TEMPLATES = [
    "{rusher} strip-sacks {qb}! {defense_team} recovers.",
    "{qb} is hit from behind by {rusher} and coughs it up. Turnover!",
    "{rusher} gets the sack and jars it loose from {qb} — takeaway for {defense_team}.",
]

SCRAMBLE_TEMPLATES = [
    "{qb} tucks it and runs for {yards} yards before {tackler} gets him.",
    "{qb} escapes pressure, scrambles for {yards}, and is pushed out by {tackler}.",
    "{qb} takes off and picks up {yards} before {tackler} makes contact.",
    "{qb} breaks the pocket and races for {yards} yards.",
]

RUN_FUMBLE_TEMPLATES = [
    "{rb} fumbles after contact from {tackler}! {defense_team} takes over.",
    "{tackler} punches it out from {rb} — turnover for {defense_team}.",
    "{rb} loses the football and {defense_team} recovers.",
]

TURNOVER_ON_DOWNS_TEMPLATES = [
    "{offense_team} comes up short on fourth down. Turnover on downs.",
    "No conversion on fourth down — {defense_team} takes over.",
    "Stuffed short of the line to gain. Turnover on downs for {offense_team}.",
]

RUN_TD_TEMPLATES = [
    "{rb} bursts into the end zone! Touchdown on a {ay}-yard run.",
    "{rb} finds daylight and scores from {ay} yards out.",
    "{rb} punches it in for six on a {ay}-yard touchdown run.",
]

PASS_TD_TEMPLATES = [
    "{qb} connects with {wr} for a {ay}-yard touchdown!",
    "Touchdown! {qb} finds {wr} from {ay} yards out.",
    "{wr} hauls in {qb}'s pass for a {ay}-yard score.",
]

SCRAMBLE_TD_TEMPLATES = [
    "{qb} keeps it and scrambles in for the touchdown!",
    "{qb} sees an opening and runs it in for six.",
    "{qb} breaks contain and scores on the scramble.",
]

PUNT_TEMPLATES = [
    "{offense_team} punts it away.",
    "Punt by {offense_team}; {defense_team} will take over.",
    "Special teams unit on: {offense_team} sends it deep.",
]

FG_GOOD_TEMPLATES = [
    "Field goal is good for {offense_team}.",
    "{offense_team} knocks through the field goal.",
    "Three points: {offense_team} is good from the kick team.",
]

FG_MISS_TEMPLATES = [
    "{offense_team} misses the field goal attempt.",
    "Field goal no good for {offense_team}.",
    "The kick is off target — no points for {offense_team}.",
]

KICKOFF_TOUCHBACK_TEMPLATES = [
    "Kickoff sails into the end zone — touchback; {offense_team} starts at their own 25.",
    "Touchback on the kickoff; {offense_team} will begin at the 25.",
]

KICKOFF_RETURN_TEMPLATES = [
    "Kickoff: {returner} brings it back {ret_yards} yards for {offense_team}.",
    "{offense_team} fields the kick and returns it {ret_yards} yards.",
]

KICKOFF_TD_TEMPLATES = [
    "Kickoff taken to the house! Touchdown {offense_team}!",
    "{returner} goes the distance on the kickoff return — touchdown {offense_team}!",
]


def _pick(templates, **ctx):
    return random.choice(templates).format(**ctx)


def _style_bucket(offensive_style: str, offensive_formation: str) -> str:
    text = f"{offensive_style} {offensive_formation}".lower()
    if any(k in text for k in ["air", "spread", "pass", "west coast"]):
        return "pass"
    if any(k in text for k in ["option", "power", "veer", "run", "wing", "wishbone"]):
        return "run"
    return "balanced"


def _situation_prefix(ctx):
    down = int(ctx.get("down", 1) or 1)
    ytg = int(ctx.get("yards_to_go", 10) or 10)
    ball = int(ctx.get("ball_position", 25) or 25)
    qtr = int(ctx.get("quarter", 1) or 1)
    sec = int(ctx.get("time_remaining", 12 * 60) or 0)
    offense_team = ctx.get("offense_team", "Offense")
    defense_team = ctx.get("defense_team", "Defense")
    score_margin = int(ctx.get("score_margin", 0) or 0)  # offense score - defense score

    red_zone = ball >= 80
    two_minute = qtr == 4 and sec <= 120

    lines = []
    if down == 4:
        lines.append("Fourth down pressure.")
    elif down == 3 and ytg >= 7:
        lines.append("Big third down.")
    elif down == 3:
        lines.append("Key third down.")

    if red_zone:
        lines.append(f"{offense_team} is in the red zone.")

    if two_minute:
        if score_margin < 0:
            lines.append(f"Two-minute drill for {offense_team}.")
        elif score_margin > 0:
            lines.append(f"{offense_team} looks to bleed the clock.")
        else:
            lines.append("Crunch time in a tight game.")

    if not lines:
        return ""
    return " ".join(lines) + " "


def _excitement_prefix(result, yards: int) -> str:
    ay = abs(yards)
    if result.get("touchdown"):
        return random.choice(["Touchdown! ", "What a strike! ", "Huge score! "])
    if result.get("interception"):
        return random.choice(["Turnover! ", "Picked off! ", "Disaster for the offense! "])
    if result.get("sack") and result.get("fumble"):
        return random.choice(["Game-changing play! ", "Chaos in the pocket! ", "Ball's out! "])
    if ay >= 35:
        return random.choice(["Explosive play! ", "Big-time chunk gain! ", "Home-run play! "])
    if ay >= 20:
        return random.choice(["Big gain! ", "They found space! ", "That's a shot play! "])
    return ""


def _style_prefix(style_bucket: str, is_run: bool, result) -> str:
    if result.get("punt") or result.get("field_goal") or result.get("kickoff"):
        return ""
    if style_bucket == "run" and is_run:
        return random.choice(["Power look. ", "Ground game call. ", "Smash-mouth football. "])
    if style_bucket == "pass" and not is_run:
        return random.choice(["Spread look. ", "Passing concept dialed up. ", "They go to the air. "])
    if style_bucket == "balanced":
        return random.choice(["Balanced call. ", "Standard look. ", "Base offense. "])
    return ""


def build_dynamic_play_by_play(
    result,
    is_run,
    offense_team,
    defense_team,
    qb,
    rb,
    wr,
    rusher,
    db,
    tackler,
    offensive_style="",
    offensive_formation="",
    context=None,
):
    yards = int(result.get("yards") or 0)
    ay = abs(yards)
    context = context or {}
    ctx = {
        "qb": qb,
        "rb": rb,
        "wr": wr,
        "rusher": rusher,
        "db": db,
        "tackler": tackler,
        "yards": yards,
        "ay": ay,
        "offense_team": offense_team,
        "defense_team": defense_team,
        "down": int(context.get("down", 1) or 1),
        "yards_to_go": int(context.get("yards_to_go", 10) or 10),
        "ball_position": int(context.get("ball_position", 25) or 25),
        "quarter": int(context.get("quarter", 1) or 1),
        "time_remaining": int(context.get("time_remaining", 12 * 60) or 0),
        "score_margin": int(context.get("score_margin", 0) or 0),
    }
    style = _style_bucket(str(offensive_style or ""), str(offensive_formation or ""))
    pre = _situation_prefix(ctx) + _style_prefix(style, is_run=is_run, result=result) + _excitement_prefix(result, yards)

    if result.get("punt"):
        return pre + _pick(PUNT_TEMPLATES, **ctx)
    if result.get("field_goal"):
        return pre + _pick(FG_GOOD_TEMPLATES if result.get("field_goal_good") else FG_MISS_TEMPLATES, **ctx)
    if result.get("kickoff"):
        ret_yards = int(result.get("return_yards") or 0)
        ctx2 = dict(ctx)
        ctx2["ret_yards"] = ret_yards
        ctx2["returner"] = rb
        if result.get("kickoff_td"):
            return pre + _pick(KICKOFF_TD_TEMPLATES, **ctx2)
        if result.get("touchback"):
            return pre + _pick(KICKOFF_TOUCHBACK_TEMPLATES, **ctx2)
        return pre + _pick(KICKOFF_RETURN_TEMPLATES, **ctx2)

    if result.get("touchdown"):
        if is_run:
            return pre + _pick(RUN_TD_TEMPLATES, **ctx)
        if result.get("scramble"):
            return pre + _pick(SCRAMBLE_TD_TEMPLATES, **ctx)
        return pre + _pick(PASS_TD_TEMPLATES, **ctx)

    if result.get("sack"):
        if result.get("fumble"):
            return pre + _pick(STRIP_SACK_TEMPLATES, **ctx)
        return pre + _pick(SACK_TEMPLATES, **ctx)

    if result.get("interception"):
        return pre + _pick(PASS_INT_TEMPLATES, **ctx)

    if result.get("scramble") and not result.get("touchdown"):
        return pre + _pick(SCRAMBLE_TEMPLATES, **ctx)

    if is_run:
        if result.get("turnover"):
            if result.get("fumble"):
                return pre + _pick(RUN_FUMBLE_TEMPLATES, **ctx)
            return pre + _pick(TURNOVER_ON_DOWNS_TEMPLATES, **ctx)
        if yards < 0:
            return pre + _pick(RUN_LOSS_TEMPLATES, **ctx)
        if yards == 0:
            return pre + _pick(RUN_NOGAIN_TEMPLATES, **ctx)
        return pre + f"{_pick(RUN_GAIN_OPENERS, **ctx)}, {_pick(RUN_GAIN_MIDDLES, **ctx)}, {_pick(RUN_GAIN_ENDINGS, **ctx)}"

    if result.get("incomplete_pass"):
        return pre + _pick(PASS_INCOMPLETE_TEMPLATES, **ctx)

    if result.get("turnover"):
        return pre + _pick(TURNOVER_ON_DOWNS_TEMPLATES, **ctx)

    return pre + f"{_pick(PASS_COMPLETE_OPENERS, **ctx)} {_pick(PASS_COMPLETE_ENDINGS, **ctx)}"


def estimated_variant_count() -> int:
    """Conservative lower bound of distinct line variants available."""
    run_gain = len(RUN_GAIN_OPENERS) * len(RUN_GAIN_MIDDLES) * len(RUN_GAIN_ENDINGS)
    other = (
        len(RUN_LOSS_TEMPLATES)
        + len(RUN_NOGAIN_TEMPLATES)
        + len(PASS_COMPLETE_OPENERS) * len(PASS_COMPLETE_ENDINGS)
        + len(PASS_INCOMPLETE_TEMPLATES)
        + len(PASS_INT_TEMPLATES)
        + len(SACK_TEMPLATES)
        + len(STRIP_SACK_TEMPLATES)
        + len(SCRAMBLE_TEMPLATES)
        + len(RUN_FUMBLE_TEMPLATES)
        + len(TURNOVER_ON_DOWNS_TEMPLATES)
        + len(RUN_TD_TEMPLATES)
        + len(PASS_TD_TEMPLATES)
        + len(SCRAMBLE_TD_TEMPLATES)
        + len(PUNT_TEMPLATES)
        + len(FG_GOOD_TEMPLATES)
        + len(FG_MISS_TEMPLATES)
    )
    return run_gain + other
