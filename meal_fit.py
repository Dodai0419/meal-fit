#!/usr/bin/env python3
"""meal-fit: see how many calories this meal has left today, then get the meal combos that fit it.

Fuses WilderNoTrack/mcd-calorie-butler (day budget: goal minus what you logged, split across the meals
still open, skipping meals whose time has passed) and AAA-EE/mcd-budget-planner (constraint search over a
nutrition table: calories, sodium, fat, protein, calcium; sodium-first scoring). Both MIT. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

NUTRIENTS = ("kcal", "protein_g", "fat_g", "carb_g", "sodium_mg", "calcium_mg")
MAIN_MEALS = ("breakfast", "lunch", "dinner")
DEFAULT_SPLIT = {"breakfast": 0.30, "lunch": 0.40, "dinner": 0.30}
MEAL_ENDS = {"breakfast": "10:30", "lunch": "14:30", "dinner": "23:59"}  # an unlogged meal past this time gets no budget
PER_CATEGORY = 6  # candidates kept per category before the combo search (keeps it fast)
HERE = os.path.dirname(os.path.abspath(__file__))


def load_menu(path):
    """Menu JSON: {"items": [{"name", "category", "kcal", "protein_g", "fat_g", "carb_g", "sodium_mg", "calcium_mg"}]}."""
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["items"]
    return [{"name": r["name"], "category": r.get("category", "other"), **{k: float(r.get(k, 0)) for k in NUTRIENTS}}
            for r in rows]


def day_budget(goal_kcal, protein_goal_g, eaten, now=None, split=None, past_day=False):
    """eaten: [{"meal": "lunch", "items": [{"kcal": 520, "protein": 25}]}]. Same rules as calorie-butler's day_summary."""
    slots = {m: [0, 0.0, 0] for m in (*MAIN_MEALS, "snack")}
    for e in eaten:
        s = slots.setdefault(e["meal"], [0, 0.0, 0])
        s[0] += sum(i["kcal"] for i in e["items"])
        s[1] += sum(i.get("protein", 0) for i in e["items"])
        s[2] += 1
    total = sum(s[0] for s in slots.values())
    remaining = goal_kcal - total
    unlogged = [m for m in MAIN_MEALS if slots[m][2] == 0]
    passed = [] if now is None else unlogged if past_day else [m for m in unlogged if now > MEAL_ENDS[m]]
    open_meals = [m for m in unlogged if m not in passed]
    shares = {m: (split or DEFAULT_SPLIT).get(m, 0.3) for m in open_meals}
    total_share = sum(shares.values())
    return {"goal_kcal": goal_kcal, "eaten_kcal": total, "remaining_kcal": remaining,
            "protein_gap_g": round(max(0, protein_goal_g - round(sum(s[1] for s in slots.values()), 1)), 1),
            "open_meals": open_meals, "passed_meals": passed,
            "meal_budgets": {m: max(0, round(remaining * shares[m] / total_share)) if total_share else 0 for m in open_meals}}


def score(t):
    """Lower is better: sodium weighs most, then calories, protein helps; under 200 kcal is not a meal."""
    satiety = (200 - t[0]) / 100.0 * 2.5 if t[0] < 200 else 0.0
    return t[4] / 100.0 * 3.0 + t[0] / 100.0 * 1.0 - t[1] * 0.15 + satiety


def find_meals(items, max_kcal=None, max_sodium_mg=None, max_fat_g=None, min_protein_g=None, min_calcium_mg=None,
               exclude=(), categories=None, max_size=3, limit=5):
    """Best combos of 2..max_size items (at most 2 per category) that meet every cap, best score first."""
    caps = ((0, max_kcal), (4, max_sodium_mg), (2, max_fat_g))
    groups = {}
    for it in items:
        if it["name"] in exclude or (categories and it["category"] not in categories):
            continue
        vec = tuple(it[k] for k in NUTRIENTS)
        if any(cap is not None and vec[i] > cap for i, cap in caps):
            continue
        groups.setdefault(it["category"], []).append((it, vec))
    pool = [x for g in groups.values() for x in sorted(g, key=lambda x: (x[1][4], x[1][0]))[:PER_CATEGORY]]
    found, seen, chosen, per_cat = [], set(), [], {}

    def ok(t):
        return not ((max_kcal is not None and t[0] > max_kcal) or (max_sodium_mg is not None and t[4] > max_sodium_mg)
                    or (max_fat_g is not None and t[2] > max_fat_g) or (min_protein_g is not None and t[1] < min_protein_g)
                    or (min_calcium_mg is not None and t[5] < min_calcium_mg))

    def walk(start, t):
        if len(chosen) >= 2 and ok(t):
            key = tuple(sorted(it["name"] for it in chosen))
            if key not in seen:
                seen.add(key)
                found.append((score(t), [it["name"] for it in chosen], t))
        if len(chosen) >= max_size:
            return
        for i in range(start, len(pool)):
            it, vec = pool[i]
            if per_cat.get(it["category"], 0) >= 2:
                continue
            nt = tuple(a + b for a, b in zip(t, vec))  # same float order as summing item by item
            if (max_sodium_mg is not None and nt[4] > max_sodium_mg) or (max_kcal is not None and nt[0] > max_kcal):
                continue
            chosen.append(it)
            per_cat[it["category"]] = per_cat.get(it["category"], 0) + 1
            walk(i + 1, nt)
            per_cat[it["category"]] -= 1
            chosen.pop()

    walk(0, (0.0,) * 6)
    found.sort(key=lambda f: f[0])
    return [{"items": names, "score": s, **dict(zip(NUTRIENTS, t))} for s, names, t in found[:limit]]


def parse_ate(value):
    m = re.fullmatch(r"(\w+):(\d+)(?::(\d+(?:\.\d+)?))?", value)
    if not m:
        raise argparse.ArgumentTypeError(f"expected MEAL:KCAL[:PROTEIN_G], e.g. lunch:650:30, got {value!r}")
    return {"meal": m.group(1).lower(), "items": [{"kcal": int(m.group(2)), "protein": float(m.group(3) or 0)}]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="meal-fit", description=__doc__.splitlines()[0])
    ap.add_argument("--menu", default=os.path.join(HERE, "examples", "menu.json"), help="nutrition table JSON")
    ap.add_argument("--goal", type=int, default=1800, help="daily calorie goal (default 1800)")
    ap.add_argument("--protein", type=float, default=90, help="daily protein goal in g (default 90)")
    ap.add_argument("--ate", type=parse_ate, action="append", default=[], metavar="MEAL:KCAL[:PROTEIN]",
                    help="something you already ate today, repeatable: breakfast, lunch, dinner or snack")
    ap.add_argument("--now", help="current time HH:MM (default: now)")
    ap.add_argument("--meal", help="meal to plan (default: the next open meal)")
    ap.add_argument("--max-kcal", type=float, help="override the calorie cap from the day budget")
    ap.add_argument("--max-sodium", type=float)
    ap.add_argument("--max-fat", type=float)
    ap.add_argument("--min-protein", type=float)
    ap.add_argument("--min-calcium", type=float)
    ap.add_argument("--only", help="comma-separated categories, e.g. burger,drink")
    ap.add_argument("--exclude", default="", help="comma-separated item names to leave out")
    ap.add_argument("--size", type=int, default=3, help="max items per meal (default 3)")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.now and not re.fullmatch(r"\d{1,2}:\d{2}", a.now):
        ap.error("--now must be HH:MM, e.g. 18:40")
    now = f"{int(a.now.split(':')[0]):02d}:{a.now.split(':')[1]}" if a.now else dt.datetime.now().strftime("%H:%M")
    day = day_budget(a.goal, a.protein, a.ate, now)
    meal = (a.meal or (day["open_meals"] or ["snack"])[0]).lower()
    budget = a.max_kcal if a.max_kcal is not None else day["meal_budgets"].get(meal, max(0, day["remaining_kcal"]))
    meals = find_meals(load_menu(a.menu), max_kcal=budget, max_sodium_mg=a.max_sodium, max_fat_g=a.max_fat,
                       min_protein_g=a.min_protein, min_calcium_mg=a.min_calcium,
                       exclude={x.strip() for x in a.exclude.split(",") if x.strip()},
                       categories={x.strip() for x in a.only.split(",")} if a.only else None, max_size=a.size, limit=a.top)
    if a.json:
        print(json.dumps({"day": day, "meal": meal, "budget_kcal": budget, "meals": meals}, indent=1))
        return 0
    print(f"Today: goal {day['goal_kcal']} kcal, eaten {day['eaten_kcal']}, left {day['remaining_kcal']}. "
          f"Protein still to go: {day['protein_gap_g']:g} g.")
    if day["passed_meals"]:
        print(f"No budget kept for {', '.join(day['passed_meals'])}: its time has passed and nothing was logged.")
    print(f"{meal.capitalize()} budget: {budget:g} kcal")
    if not meals:
        print("Nothing on the menu fits these limits. Loosen one (--max-sodium, --min-protein) or raise --max-kcal.")
        return 1
    for i, m in enumerate(meals, 1):
        print(f"#{i}  {' + '.join(m['items'])}\n    {m['kcal']:.0f} kcal, protein {m['protein_g']:.0f} g, "
              f"fat {m['fat_g']:.0f} g, sodium {m['sodium_mg']:.0f} mg, calcium {m['calcium_mg']:.0f} mg  (score {m['score']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
