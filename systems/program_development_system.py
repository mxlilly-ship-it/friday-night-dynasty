"""
Program Development System — annual funding, equipment catalog, inventory, purchases.

Funding is awarded at season review. Users (and CPU teams) spend balance on
equipment during the offseason Program Development stage.
"""

from __future__ import annotations

import json
import os
import random
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

FUNDING_BASE = 8_750
FUNDING_MULTIPLIER = 16_658
FUNDING_EXPONENT = 1.3
FUNDING_INCOME_MIN = 20_000
FUNDING_INCOME_MAX = 100_000
FUNDING_BALANCE_CAP = 250_000
RENEWAL_COST_MULTIPLIER = 0.6
MAX_WINS_FOR_FORMULA = 10

_PP_POINTS_RE = re.compile(r"(\d+)\s*PP\s*Points?", re.IGNORECASE)

_CATALOG_CACHE: Optional[Dict[str, Any]] = None


def _default_catalog_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "program_equipment_catalog.json")


def load_equipment_catalog(path: Optional[str] = None) -> Dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None and path is None:
        return _CATALOG_CACHE
    p = path or _default_catalog_path()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Invalid equipment catalog")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Equipment catalog missing items")
    by_id = {str(it.get("id")): it for it in items if isinstance(it, dict) and it.get("id")}
    data["_by_id"] = by_id
    if path is None:
        _CATALOG_CACHE = data
    return data


def catalog_item(item_id: str, catalog: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    cat = catalog or load_equipment_catalog()
    return (cat.get("_by_id") or {}).get(str(item_id))


def compute_annual_funding(
    *,
    booster_rating: int,
    wins: int,
    community_outreach: int,
) -> int:
    """
    Funding = 8750 + (((Booster/10 * 0.5) + (Wins * 0.3) + (Outreach/10 * 0.2)) ^ 1.3 * 16658)

    Tuned so ~10/10/10 ≈ $100k, ~5/5/5 ≈ $45–50k, ~2/2/2 ≈ $20k.
    Wins are clamped to 0–10 (regular season length). Income is clamped to $20k–$100k.
    """
    b = max(1, min(10, int(booster_rating or 5)))
    o = max(1, min(10, int(community_outreach or 5)))
    w = max(0, min(MAX_WINS_FOR_FORMULA, int(wins or 0)))
    score = (b / 10.0 * 0.5) + (w * 0.3) + (o / 10.0 * 0.2)
    score = max(0.0, score)
    raw = FUNDING_BASE + (score ** FUNDING_EXPONENT) * FUNDING_MULTIPLIER
    return max(FUNDING_INCOME_MIN, min(FUNDING_INCOME_MAX, int(round(raw))))


def funding_breakdown(
    *,
    booster_rating: int,
    wins: int,
    community_outreach: int,
) -> Dict[str, Any]:
    b = max(1, min(10, int(booster_rating or 5)))
    o = max(1, min(10, int(community_outreach or 5)))
    w = max(0, min(MAX_WINS_FOR_FORMULA, int(wins or 0)))
    booster_part = b / 10.0 * 0.5
    wins_part = w * 0.3
    outreach_part = o / 10.0 * 0.2
    score = booster_part + wins_part + outreach_part
    total = compute_annual_funding(booster_rating=b, wins=w, community_outreach=o)
    return {
        "booster_rating": b,
        "wins": w,
        "community_outreach": o,
        "score": round(score, 3),
        "total": total,
        "booster_component": round(booster_part, 3),
        "wins_component": round(wins_part, 3),
        "outreach_component": round(outreach_part, 3),
    }


def get_team_program_state(team: Any) -> Dict[str, Any]:
    bal = int(getattr(team, "program_funding_balance", 0) or 0)
    last = int(getattr(team, "program_last_funding_income", 0) or 0)
    inv = getattr(team, "program_equipment", None)
    if not isinstance(inv, list):
        inv = []
    return {
        "balance": max(0, min(FUNDING_BALANCE_CAP, bal)),
        "last_income": max(0, last),
        "inventory": deepcopy(inv),
    }


def set_team_program_state(team: Any, *, balance: int, last_income: int, inventory: List[Dict[str, Any]]) -> None:
    team.program_funding_balance = max(0, min(FUNDING_BALANCE_CAP, int(balance)))
    team.program_last_funding_income = max(0, int(last_income))
    team.program_equipment = list(inventory or [])
    if hasattr(team, "_clamp_values"):
        team._clamp_values()


def ensure_team_program_fields(team: Any) -> None:
    if getattr(team, "program_funding_balance", None) is None:
        team.program_funding_balance = 0
    if getattr(team, "program_last_funding_income", None) is None:
        team.program_last_funding_income = 0
    if not isinstance(getattr(team, "program_equipment", None), list):
        team.program_equipment = []


def migrate_team_dict_program_fields(t: Dict[str, Any]) -> bool:
    if not isinstance(t, dict):
        return False
    changed = False
    if t.get("program_funding_balance") is None:
        t["program_funding_balance"] = 0
        changed = True
    if t.get("program_last_funding_income") is None:
        t["program_last_funding_income"] = 0
        changed = True
    if not isinstance(t.get("program_equipment"), list):
        t["program_equipment"] = []
        changed = True
    bal = max(0, min(FUNDING_BALANCE_CAP, int(t.get("program_funding_balance") or 0)))
    if int(t.get("program_funding_balance") or 0) != bal:
        t["program_funding_balance"] = bal
        changed = True
    return changed


def _inventory_index(inventory: List[Dict[str, Any]], item_id: str) -> int:
    for i, row in enumerate(inventory):
        if isinstance(row, dict) and str(row.get("item_id") or row.get("id")) == str(item_id):
            return i
    return -1


def age_program_equipment_one_season(inventory: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Decrement seasons remaining; return (kept, expired)."""
    kept: List[Dict[str, Any]] = []
    expired: List[Dict[str, Any]] = []
    for row in inventory:
        if not isinstance(row, dict):
            continue
        rem = float(row.get("seasons_remaining", 0) or 0)
        rem -= 1.0
        if rem <= 0:
            expired.append(dict(row))
        else:
            nr = dict(row)
            nr["seasons_remaining"] = round(rem, 2)
            kept.append(nr)
    return kept, expired


def parse_pp_points_from_attribute_lines(lines: Optional[List[Any]]) -> int:
    """Extract PP grant total from catalog ``attributes_affected`` strings."""
    total = 0
    for line in lines or []:
        for match in _PP_POINTS_RE.finditer(str(line or "")):
            total += int(match.group(1))
    return max(0, total)


def compute_equipment_pp_bonus(
    team: Any,
    catalog: Optional[Dict[str, Any]] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Annual PP from active (non-expired) owned program equipment.
    Returns (total_pp, [{item_id, name, pp}, ...]).
    """
    ensure_team_program_fields(team)
    cat = catalog or load_equipment_catalog()
    total = 0
    items_out: List[Dict[str, Any]] = []
    for row in getattr(team, "program_equipment", []) or []:
        if not isinstance(row, dict):
            continue
        if float(row.get("seasons_remaining", 0) or 0) <= 0:
            continue
        iid = str(row.get("item_id") or row.get("id") or "").strip()
        if not iid:
            continue
        spec = catalog_item(iid, cat)
        if not spec:
            continue
        pp = parse_pp_points_from_attribute_lines(spec.get("attributes_affected"))
        if pp <= 0:
            continue
        total += pp
        items_out.append({"item_id": iid, "name": str(spec.get("name") or iid), "pp": pp})
    return total, items_out


def credit_equipment_pp_to_improvements_bank(
    bank: Dict[str, Any],
    team: Any,
    *,
    current_year: int,
    catalog: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Add equipment PP into the offseason Improvements flex bank once per calendar year.
    Mutates ``bank`` in place. Returns PP added this call (0 if already credited).
    """
    if not isinstance(bank, dict) or team is None:
        return 0
    cy = int(current_year or 0)
    eq_meta = bank.get("equipment_pp")
    if isinstance(eq_meta, dict) and int(eq_meta.get("credited_year") or 0) == cy:
        return 0

    amount, items = compute_equipment_pp_bonus(team, catalog=catalog)
    bank["equipment_pp"] = {
        "credited_year": cy,
        "amount": int(amount),
        "items": items,
    }

    if amount <= 0:
        return 0

    prev_total = int(bank.get("pp_total") or 0)
    prev_remaining = int(bank.get("pp_remaining") if bank.get("pp_remaining") is not None else prev_total)
    bank["pp_total"] = prev_total + int(amount)
    bank["pp_remaining"] = prev_remaining + int(amount)

    breakdown = bank.get("breakdown")
    if not isinstance(breakdown, dict):
        breakdown = {}
        bank["breakdown"] = breakdown
    breakdown["equipment_pp_total"] = int(amount)
    breakdown["equipment_pp_items"] = list(items)
    breakdown["pp_total"] = int(breakdown.get("pp_total") or 0) + int(amount)
    return int(amount)


def renewal_cost(item: Dict[str, Any], catalog: Optional[Dict[str, Any]] = None) -> int:
    cat = catalog or load_equipment_catalog()
    mult = float(cat.get("renewal_cost_multiplier") or RENEWAL_COST_MULTIPLIER)
    return max(1, int(round(int(item.get("cost") or 0) * mult)))


def purchase_item(
    team: Any,
    item_id: str,
    *,
    current_year: int,
    catalog: Optional[Dict[str, Any]] = None,
    renew: bool = False,
) -> Dict[str, Any]:
    """Purchase or renew one catalog item. Returns result dict; raises ValueError on failure."""
    ensure_team_program_fields(team)
    cat = catalog or load_equipment_catalog()
    spec = catalog_item(item_id, cat)
    if not spec:
        raise ValueError(f"Unknown equipment item: {item_id}")
    inventory = list(getattr(team, "program_equipment", []) or [])
    idx = _inventory_index(inventory, item_id)
    cost = renewal_cost(spec, cat) if renew else int(spec.get("cost") or 0)
    balance = int(getattr(team, "program_funding_balance", 0) or 0)
    if balance < cost:
        raise ValueError("Insufficient program funding balance.")
    exp_years = int(spec.get("expiration_years") or 3)
    if renew:
        if idx < 0:
            raise ValueError("Cannot renew — item not owned.")
        row = dict(inventory[idx])
        row["seasons_remaining"] = float(exp_years)
        row["purchased_year"] = int(current_year)
        row["renewals"] = int(row.get("renewals") or 0) + 1
        inventory[idx] = row
    else:
        if idx >= 0:
            raise ValueError("Item already owned — renew instead.")
        inventory.append(
            {
                "item_id": str(item_id),
                "seasons_remaining": float(exp_years),
                "purchased_year": int(current_year),
                "renewals": 0,
            }
        )
    set_team_program_state(
        team,
        balance=balance - cost,
        last_income=int(getattr(team, "program_last_funding_income", 0) or 0),
        inventory=inventory,
    )
    return {"item_id": item_id, "cost": cost, "renew": renew, "balance_after": int(team.program_funding_balance)}


def apply_program_funding_for_season(
    team: Any,
    *,
    wins: int,
    losses: int,
    current_year: int,
) -> Dict[str, Any]:
    """Award annual funding after season; does not age equipment (age at Program Development stage)."""
    ensure_team_program_fields(team)
    booster = int(getattr(team, "booster_support", 5) or 5)
    outreach = 5
    coach = getattr(team, "coach", None)
    if coach is not None:
        outreach = int(getattr(coach, "community_outreach", 5) or 5)
    income = compute_annual_funding(booster_rating=booster, wins=wins, community_outreach=outreach)
    balance = int(getattr(team, "program_funding_balance", 0) or 0)
    new_balance = min(FUNDING_BALANCE_CAP, balance + income)
    set_team_program_state(
        team,
        balance=new_balance,
        last_income=income,
        inventory=list(getattr(team, "program_equipment", []) or []),
    )
    return funding_breakdown(booster_rating=booster, wins=wins, community_outreach=outreach) | {
        "income": income,
        "balance_after": new_balance,
        "year": int(current_year),
    }


def prepare_program_development_stage(team: Any) -> Dict[str, Any]:
    """Age inventory one season; return expiring/expired summary."""
    ensure_team_program_fields(team)
    inventory = list(getattr(team, "program_equipment", []) or [])
    kept, expired = age_program_equipment_one_season(inventory)
    set_team_program_state(
        team,
        balance=int(getattr(team, "program_funding_balance", 0) or 0),
        last_income=int(getattr(team, "program_last_funding_income", 0) or 0),
        inventory=kept,
    )
    expiring: List[Dict[str, Any]] = []
    cat = load_equipment_catalog()
    for row in kept:
        iid = str(row.get("item_id") or "")
        spec = catalog_item(iid, cat) or {}
        rem = float(row.get("seasons_remaining") or 0)
        if rem <= 1.0:
            expiring.append(
                {
                    "item_id": iid,
                    "name": spec.get("name") or iid,
                    "seasons_remaining": rem,
                    "renewal_cost": renewal_cost(spec, cat) if spec else 0,
                    "urgency": "urgent" if rem <= 0.5 else "soon",
                }
            )
    return {"expired": expired, "expiring": expiring}


def build_inventory_view(team: Any, catalog: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cat = catalog or load_equipment_catalog()
    out: List[Dict[str, Any]] = []
    for row in list(getattr(team, "program_equipment", []) or []):
        if not isinstance(row, dict):
            continue
        iid = str(row.get("item_id") or "")
        spec = catalog_item(iid, cat) or {}
        exp_years = max(1, int(spec.get("expiration_years") or 1))
        rem = float(row.get("seasons_remaining") or 0)
        pct = max(0, min(100, int(round((rem / exp_years) * 100))))
        out.append(
            {
                **spec,
                "item_id": iid,
                "seasons_remaining": rem,
                "durability_pct": pct,
                "purchased_year": row.get("purchased_year"),
                "renewals": int(row.get("renewals") or 0),
                "renewal_cost": renewal_cost(spec, cat) if spec else 0,
            }
        )
    return out


def run_ai_program_purchases(
    team: Any,
    *,
    current_year: int,
    catalog: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> List[Dict[str, Any]]:
    """CPU teams renew expiring gear and buy affordable upgrades (inventory must already be aged)."""
    ensure_team_program_fields(team)
    cat = catalog or load_equipment_catalog()
    r = rng or random.Random()
    actions: List[Dict[str, Any]] = []
    expiring = []
    for row in list(getattr(team, "program_equipment", []) or []):
        if not isinstance(row, dict):
            continue
        rem = float(row.get("seasons_remaining") or 0)
        if rem <= 1.0:
            iid = str(row.get("item_id") or "")
            spec = catalog_item(iid, cat) or {}
            expiring.append({"item_id": iid, "renewal_cost": renewal_cost(spec, cat) if spec else 0})
    for ex in expiring:
        iid = str(ex.get("item_id") or "")
        if not iid:
            continue
        try:
            actions.append(purchase_item(team, iid, current_year=current_year, catalog=cat, renew=True))
        except ValueError:
            pass
    owned = {str(x.get("item_id")) for x in (getattr(team, "program_equipment", []) or []) if isinstance(x, dict)}
    balance = int(getattr(team, "program_funding_balance", 0) or 0)
    candidates = [it for it in (cat.get("items") or []) if isinstance(it, dict) and str(it.get("id")) not in owned]
    prestige = int(getattr(team, "prestige", 5) or 5)
    candidates.sort(key=lambda it: (-int(it.get("cost") or 0), str(it.get("name") or "")))
    tries = 0
    while balance > 5000 and tries < 6 and candidates:
        tries += 1
        affordable = [c for c in candidates if int(c.get("cost") or 0) <= balance]
        if not affordable:
            break
        if prestige >= 10:
            pick = affordable[0]
        elif prestige >= 6:
            pick = r.choice(affordable[: max(1, min(8, len(affordable)))])
        else:
            pick = r.choice(affordable[-max(1, min(5, len(affordable))):])
        iid = str(pick.get("id") or "")
        try:
            res = purchase_item(team, iid, current_year=current_year, catalog=cat, renew=False)
            actions.append(res)
            owned.add(iid)
            candidates = [c for c in candidates if str(c.get("id")) not in owned]
            balance = int(getattr(team, "program_funding_balance", 0) or 0)
        except ValueError:
            break
    return actions


def apply_user_program_actions(
    team: Any,
    actions: List[Dict[str, Any]],
    *,
    current_year: int,
    catalog: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for raw in actions or []:
        if not isinstance(raw, dict):
            continue
        iid = str(raw.get("item_id") or raw.get("id") or "").strip()
        if not iid:
            continue
        renew = str(raw.get("action") or raw.get("type") or "purchase").lower() in ("renew", "renewal")
        try:
            results.append(purchase_item(team, iid, current_year=current_year, catalog=catalog, renew=renew))
        except ValueError as e:
            results.append({"item_id": iid, "error": str(e)})
    return results


def program_development_summary_for_team(team: Any, *, wins: int, losses: int) -> Dict[str, Any]:
    ensure_team_program_fields(team)
    coach = getattr(team, "coach", None)
    outreach = int(getattr(coach, "community_outreach", 5) or 5) if coach else 5
    return {
        "balance": int(getattr(team, "program_funding_balance", 0) or 0),
        "last_income": int(getattr(team, "program_last_funding_income", 0) or 0),
        "funding_breakdown": funding_breakdown(
            booster_rating=int(getattr(team, "booster_support", 5) or 5),
            wins=wins,
            community_outreach=outreach,
        ),
        "inventory": build_inventory_view(team),
    }
