---
name: meal-fit
description: Plan a meal from a menu's nutrition table under today's calorie budget and caps on sodium, fat, protein or calcium. Use when the user asks what to order or eat that fits their calorie goal, or a low-sodium / high-protein combo from a menu.
---

# meal-fit

Two steps in one command, all numbers computed by code (never estimate them yourself):
1. **Day budget**: daily goal minus what the user already ate, split across the meals still open
   (breakfast 30%, lunch 40%, dinner 30%). A meal whose time has passed with nothing logged gets no budget
   (breakfast ends 10:30, lunch 14:30).
2. **Combos**: every 2-3 item combo from the menu (at most 2 per category) that fits the budget and the caps,
   ranked sodium first, then calories, with protein as a bonus and a penalty under 200 kcal.

## Run
```bash
python meal_fit.py --goal 1800 --ate breakfast:420:18 --ate lunch:880:31 --now 18:40 --min-protein 20
python meal_fit.py --meal lunch --max-kcal 600 --max-sodium 800 --only burger,side,drink
python meal_fit.py --menu my-menu.json --json ...      # machine-readable
```
`--ate MEAL:KCAL[:PROTEIN_G]` is repeatable (breakfast, lunch, dinner, snack). `--max-kcal` overrides the day budget.

## Menu file
`{"items": [{"name", "category", "kcal", "protein_g", "fat_g", "carb_g", "sodium_mg", "calcium_mg"}]}`.
Categories used: burger, side, drink, dessert, other. `examples/menu.json` is sample data, not a real chain's numbers:
build the user's file from the restaurant's published nutrition table.

## Rules
- Ask what the user already ate today before planning; pass it with `--ate`.
- If nothing fits, say which limit to relax; do not invent items or numbers.
- This is not medical advice. Users with a medical diet should follow their clinician.
