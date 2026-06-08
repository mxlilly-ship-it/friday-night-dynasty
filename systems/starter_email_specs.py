"""
Generic one-time coach inbox starter emails.

Placeholders filled at dynasty start from save / league JSON:
  [school name], [coach name], [State]
"""

from __future__ import annotations

from typing import Any, Dict, List

GENERIC_STARTER_SPECS: List[Dict[str, Any]] = [
    {
        "sender_type": "Football Program",
        "sender_name": "Program office",
        "subject": "Friday nights in [State]",
        "body": (
            "[coach name] — welcome back. Around [State] the bleachers still fill when the band hits the tunnel "
            "and the lights come on. [school name] has a real shot to be the program people talk about on the "
            "drive home. Let's build week-to-week and keep the standard high."
        ),
        "category": "performance",
        "tone": "positive",
    },
    {
        "sender_type": "Fans / Alumni",
        "sender_name": "Alumni thread",
        "subject": "Expectations this fall",
        "body": (
            "[coach name] — no disrespect, but in [State] folks remember who won the hard games and who didn't. "
            "[school name] has talent; the question is whether we finish when it gets loud on a Friday. "
            "Prove it early or the local radio lines get hot."
        ),
        "category": "performance",
        "tone": "negative",
    },
    {
        "sender_type": "Team Captain",
        "sender_name": "Captains",
        "subject": "Locker room is locked in",
        "body": (
            "[coach name] — we want you to know the room is together. Upperclassmen are picking freshmen up for "
            "study hall and nobody's ducking accountability. [school name] feels like one team, not cliques."
        ),
        "category": "player_issue",
        "tone": "positive",
    },
    {
        "sender_type": "Parents",
        "sender_name": "Parent committee",
        "subject": "Playing time questions",
        "body": (
            "[coach name], a few families are asking fair questions about rotations and special teams snaps. "
            "Nothing formal — yet — but in [State] small-school football, hurt feelings turn into parking-lot "
            "politics fast. A short, consistent message goes a long way."
        ),
        "category": "player_issue",
        "tone": "negative",
    },
    {
        "sender_type": "Disgruntled Player",
        "sender_name": "Anonymous player channel",
        "subject": "Depth chart message",
        "body": (
            "Coach — some guys feel like practice doesn't match what gets posted. If [school name] is supposed "
            "to be family, it can't feel like favorites. We just want straight answers."
        ),
        "category": "player_issue",
        "tone": "negative",
    },
    {
        "sender_type": "Principal",
        "sender_name": "Principal's office",
        "subject": "Program footprint",
        "body": (
            "[coach name], I walked the hall between bells and saw your players tutoring after school. "
            "In a lot of [State] communities, the football program is the heartbeat — [school name] is "
            "representing us well."
        ),
        "category": "admin",
        "tone": "positive",
    },
    {
        "sender_type": "Athletic Director",
        "sender_name": "Athletic director",
        "subject": "Safety and compliance",
        "body": (
            "[coach name] — thanks for running protocol the way the association wants it. "
            "If trainers need anything on Friday nights, we're one text away. Keep [school name] sharp and legal."
        ),
        "category": "admin",
        "tone": "positive",
    },
    {
        "sender_type": "Assistant Principal",
        "sender_name": "Discipline office",
        "subject": "Social media smoke",
        "body": (
            "[coach name] — there's chatter online about a weekend gathering involving a few players. "
            "Nothing verified, but in [State] towns news moves faster than facts. "
            "Please get ahead of it with your leaders before I have to."
        ),
        "category": "admin",
        "tone": "negative",
    },
    {
        "sender_type": "Booster Club",
        "sender_name": "Boosters",
        "subject": "Concession volunteers",
        "body": (
            "[coach name] — we filled every slot for the first home game. Local businesses stepped up for "
            "the chain crew. [school name] boosters are all-in this fall."
        ),
        "category": "boosters",
        "tone": "positive",
    },
    {
        "sender_type": "Booster Club President",
        "sender_name": "Booster president",
        "subject": "Donor temperature",
        "body": (
            "[coach name], a couple longtime donors asked why last season didn't match expectations. "
            "Nobody's pulling money — yet — but [school name] needs a clean narrative before banquet season."
        ),
        "category": "boosters",
        "tone": "negative",
    },
    {
        "sender_type": "Fundraising Coordinator",
        "sender_name": "Athletics finance",
        "subject": "Equipment timing",
        "body": (
            "Coach — we're waiting on a helmet refurb line item until receipts clear. "
            "If boosters hear 'no new gear' while rivals post haul photos, it gets tense in [State] in a hurry."
        ),
        "category": "boosters",
        "tone": "negative",
    },
    {
        "sender_type": "College Recruiters",
        "sender_name": "Regional scouting",
        "subject": "Underclassmen watch list",
        "body": (
            "[coach name] — we're updating profiles on a few [school name] underclassmen who popped on camp film. "
            "Kids from [State] still get overlooked by out-of-state evaluators; send verified measurables when you can."
        ),
        "category": "recruiting",
        "tone": "positive",
    },
    {
        "sender_type": "Youth Coaches",
        "sender_name": "Youth league",
        "subject": "Rankings chatter",
        "body": (
            "Coach — parents repeat whatever the statewide site posts. A preseason drop for [school name] "
            "has kids acting like scouts. Can we get a grounded message from the staff?"
        ),
        "category": "recruiting",
        "tone": "negative",
    },
    {
        "sender_type": "Newspaper Reporter",
        "sender_name": "Prep desk",
        "subject": "Season preview quote",
        "body": (
            "[coach name] — we're running a [State] roundup and want [school name] in the mix. "
            "Send a sentence on your opener and a player to watch."
        ),
        "category": "media",
        "tone": "positive",
    },
    {
        "sender_type": "Newspaper Reporter",
        "sender_name": "Talk radio",
        "subject": "Pressure index (heads up)",
        "body": (
            "[coach name] — a host wants a segment on [school name] based on close losses last year. "
            "You don't have to call in, but silence becomes a sound bite. Your choice."
        ),
        "category": "media",
        "tone": "negative",
    },
    {
        "sender_type": "Guidance Counselor",
        "sender_name": "Guidance office",
        "subject": "Leadership shout-out",
        "body": (
            "Hi [coach name] — teachers mentioned your players helping with freshman orientation. "
            "That matters at a [State] school where everybody knows the jersey numbers."
        ),
        "category": "community",
        "tone": "positive",
    },
    {
        "sender_type": "Community Leaders",
        "sender_name": "Chamber",
        "subject": "Friday night and Main Street",
        "body": (
            "[coach name] — merchants told us home games are their best nights. "
            "If [school name] runs a clean crowd, we'll keep pushing the county to support the field."
        ),
        "category": "community",
        "tone": "positive",
    },
    {
        "sender_type": "Community / Parents",
        "sender_name": "Neighbors group",
        "subject": "Traffic after practice",
        "body": (
            "[coach name] — a few folks behind the school are frustrated with pickup after scrimmages. "
            "When horns start blowing, it lands on [school name] and the whole [State] Friday-night reputation."
        ),
        "category": "community",
        "tone": "negative",
    },
    {
        "sender_type": "Teachers",
        "sender_name": "Faculty liaison",
        "subject": "Band vs. kickoff",
        "body": (
            "[coach name] — we have a school concert the same night as a late finish. Families are split. "
            "Can we coordinate so kids aren't forced to pick between the band room and the locker room?"
        ),
        "category": "community",
        "tone": "negative",
    },
]
