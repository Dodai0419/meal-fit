import io, json, os, sys, unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import meal_fit as mf

MENU = mf.load_menu(os.path.join(ROOT, "examples", "menu.json"))
with open(os.path.join(HERE, "upstream_expected.json")) as f:
    EXPECTED = json.load(f)


class SameAsBudgetPlanner(unittest.TestCase):
    """Expected combos recorded by running AAA-EE/mcd-budget-planner recommend() on examples/menu.json."""

    def test_every_recorded_constraint_set(self):
        for case in EXPECTED["combos"]:
            with self.subTest(case["constraints"]):
                got = mf.find_meals(MENU, max_size=case["max_size"], limit=case["limit"], **case["constraints"])
                self.assertEqual([[m["items"], round(m["score"], 9)] for m in got], case["combos"])

    def test_constraints_hold(self):
        for m in mf.find_meals(MENU, max_kcal=600, max_sodium_mg=900, min_protein_g=25, limit=20):
            self.assertLessEqual(m["kcal"], 600)
            self.assertLessEqual(m["sodium_mg"], 900)
            self.assertGreaterEqual(m["protein_g"], 25)


class SameAsCalorieButler(unittest.TestCase):
    """Expected budgets recorded by running WilderNoTrack/mcd-calorie-butler day_summary() on generated diaries."""

    def test_every_recorded_day(self):
        for case in EXPECTED["budgets"]:
            with self.subTest(case["eaten"]):
                p = case["profile"]
                got = mf.day_budget(p["goal_kcal"], p["protein_g"], case["eaten"], case["now"], p["split"], case["past_day"])
                for key in ("remaining_kcal", "protein_gap_g", "open_meals", "meal_budgets"):
                    self.assertEqual(got[key], case[key], key)


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = mf.main(list(argv))
        return code, out.getvalue()

    def test_plan_uses_the_meal_budget_as_calorie_cap(self):
        code, out = self.run_cli("--menu", os.path.join(ROOT, "examples", "menu.json"), "--goal", "1800",
                                 "--ate", "breakfast:420:18", "--ate", "lunch:880:31", "--now", "18:40",
                                 "--meal", "dinner", "--min-protein", "20", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["budget_kcal"], 500)
        self.assertTrue(res["meals"])
        self.assertTrue(all(m["kcal"] <= 500 and m["protein_g"] >= 20 for m in res["meals"]))

    def test_bad_ate_value_is_rejected(self):
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()):
                mf.main(["--ate", "lunch-lots"])


import unittest.mock  # noqa: E402
