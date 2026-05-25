"""Analyze Ohio (or any) save: pod sizes vs regular-season game counts."""
import json
import sys
from collections import Counter, defaultdict

def main(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    teams = state.get("teams", [])
    meta = {}
    for t in teams:
        name = t.get("name")
        if not name:
            continue
        meta[name] = (str(t.get("classification") or "UNK"), str(t.get("region") or "State"))

    pods = defaultdict(list)
    for name, key in meta.items():
        pods[key].append(name)

    print("Total teams:", len(meta))
    print("Pods:", len(pods))
    sizes = Counter(len(v) for v in pods.values())
    print("Pod size distribution:", dict(sorted(sizes.items())))

    by_class = defaultdict(dict)
    for (c, r), names in pods.items():
        by_class[c][r] = len(names)

    uneven = []
    for c, regs in sorted(by_class.items()):
        counts = list(regs.values())
        total = sum(counts)
        ok = (
            (len(regs) == 2 and total == 20 and all(x == 10 for x in counts))
            or (len(regs) == 4 and total == 32 and all(x == 8 for x in counts))
            or (len(regs) == 4 and total == 40 and all(x == 10 for x in counts))
            or (len(regs) == 4 and total == 28 and all(x == 7 for x in counts))
        )
        if not ok:
            uneven.append((c, regs, total))

    print("Classes NOT using 2x10, 4x8, 4x10, or 4x7 cross-region templates:", len(uneven))
    for c, regs, total in uneven[:12]:
        print(f"  class {c}: {total} teams, regions={regs}")

    weeks = state.get("weeks") or []
    print("Week count in save:", len(weeks))

    game_count = Counter()
    for week in weeks:
        if not isinstance(week, list):
            continue
        for g in week:
            if not isinstance(g, dict):
                continue
            h, a = g.get("home"), g.get("away")
            if h:
                game_count[h] += 1
            if a:
                game_count[a] += 1

    gc = Counter(game_count.values())
    print("Games played distribution:", dict(sorted(gc.items())))

    for target in (7, 8, 9, 10):
        names = [n for n, c in game_count.items() if c == target]
        print(f"Teams with {target} games: {len(names)}")

    pod_size_for = {n: len(pods[k]) for k, names in pods.items() for n in names}
    nine = [n for n, c in game_count.items() if c == 9]
    nine_by_pod = Counter(pod_size_for[n] for n in nine)
    print("Pod sizes for 9-game teams:", dict(sorted(nine_by_pod.items())))

    print("\nSample 9-game teams:")
    for n in nine[:10]:
        c, r = meta[n]
        print(f"  {n}: class {c} region {r} pod={pod_size_for[n]}")

    # Expected games from schedule_system formula
    def expected_games(pod_n: int) -> int:
        n = pod_n + (1 if pod_n % 2 else 0)
        return min(10, n - 1)

    print("\nExpected in-region games by pod size (no cross-region):")
    for sz in sorted(set(pod_size_for.values())):
        print(f"  pod {sz} -> {expected_games(sz)} games")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"saves/1bf5b26f-1c18-4fec-8e67-f497822d49b7/My Dynastyohio1/league_save.json")
