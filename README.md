<div align="center">

# meal-fit

**See how many calories your next meal has left today, then get the menu combos that fit it.**

Two of the McDonald's MCP contest skills each did half of this: [mcd-calorie-butler](https://github.com/WilderNoTrack/mcd-calorie-butler) works out the calorie budget, [mcd-budget-planner](https://github.com/AAA-EE/mcd-budget-planner) finds combos under nutrient caps. This puts both in one file that works with any menu's nutrition table.

Works with **Claude Code** and **Codex**.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Status: prototype](https://img.shields.io/badge/status-prototype-orange.svg)

</div>

## Quick start
```bash
git clone https://github.com/Dodai0419/meal-fit && cd meal-fit
python meal_fit.py --goal 1800 --ate breakfast:420:18 --ate lunch:880:31 --now 18:40 --min-protein 20
```
```
Today: goal 1800 kcal, eaten 1300, left 500. Protein still to go: 41 g.
Dinner budget: 500 kcal
#1  Fish Fillet + Corn Cup + Side Salad
    500 kcal, protein 20 g, fat 20 g, sodium 575 mg, calcium 165 mg  (score 19.25)
#2  Classic Burger + Milk
    350 kcal, protein 20 g, fat 12 g, sodium 635 mg, calcium 390 mg  (score 19.55)
```
Python 3.8+, standard library only. `examples/menu.json` is sample data; point `--menu` at your own table.

## The problem
- Calorie apps tell you what is left for the day, not which menu items fit it.
- "Lowest sodium" lists return a cola and a coffee, not a meal.
- The two tools that solve each half are tied to one chain's MCP server and Chinese menu names, and live in separate repos.

## The solution
| Idea | Fixes |
|------|-------|
| **Day budget first** | Goal minus what you ate, split over the meals still open (30/40/30); a meal whose time passed unlogged gets nothing |
| **Constraint search** | Every 2-3 item combo (at most 2 per category) under kcal / sodium / fat caps and protein / calcium floors |
| **Meal-shaped scoring** | Sodium first, then calories, protein as a bonus, a penalty under 200 kcal so drinks alone don't win |
| **Any menu** | A plain JSON nutrition table instead of one chain's live API |

```bash
python meal_fit.py --meal lunch --max-kcal 600 --max-sodium 800 --only burger,side,drink
python meal_fit.py --menu my-menu.json --exclude "Large Fries" --size 2 --top 3 --json
```

## Use with Claude Code
```bash
/plugin marketplace add Dodai0419/meal-fit
/plugin install meal-fit@meal-fit
```
Then: "I had 420 kcal for breakfast and 880 for lunch, goal 1800. What can I get for dinner with 20 g protein?"

## Use with Codex (ChatGPT)
```bash
git clone https://github.com/Dodai0419/meal-fit && cp -r meal-fit/skills/* ~/.codex/skills/
```
Or copy `AGENTS.md` into your project root.

## Benchmarks
`find_meals` vs upstream `recommend()` from mcd-budget-planner, in-process on upstream's own 158-item nutrition table (`data/nutrition_mcd.json`, upstream categories), best of 5 runs x 3 calls, `limit=5`. Windows 11, Python 3.11.1.

| | upstream | meal-fit |
|-|-|-|
| sodium <= 600, kcal <= 500, up to 3 items | 34.83 ms | 15.20 ms |
| no caps, up to 3 items | 68.08 ms | 32.71 ms |
| no caps, up to 4 items | 553.98 ms | 240.55 ms |
| same combos, same order, same score | reference | 800 / 800 random cases (both menus) |
| day budget same as calorie-butler `day_summary` | reference | 1000 / 1000 random diaries |
| code | 293 lines (`solver.py`) + 822 lines (`butler.py`, budget logic about 40 of them) | 161 lines |
| dependencies | 0 | 0 |

The speedup comes from carrying running totals down the search instead of re-adding every chosen item at each step. The same float operations happen in the same order, so scores match bit for bit. tests/upstream_expected.json holds 219 combos and 60 day budgets recorded from both upstream functions on `examples/menu.json`.

## Inspired by
- [AAA-EE/mcd-budget-planner](https://github.com/AAA-EE/mcd-budget-planner) — nutrient constraints, per-category pre-filter, sodium-first scoring with the satiety penalty
- [WilderNoTrack/mcd-calorie-butler](https://github.com/WilderNoTrack/mcd-calorie-butler) — day budget: meal split, meal end times, remaining calories and protein gap

## Roadmap
- [ ] Prices: a `--max-price` cap when the menu file has prices
- [ ] Per-item "how much I like it" weights, as calorie-butler does
- [ ] Converters for common published nutrition tables (CSV)

## License
MIT
