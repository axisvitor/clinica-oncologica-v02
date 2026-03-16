#!/usr/bin/env python3
"""Verify seeded templates are loadable via EnhancedTemplateLoader."""

import sys
import os

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.template_loader_pkg.loader import EnhancedTemplateLoader


def main():
    db = SessionLocal()
    try:
        loader = EnhancedTemplateLoader(db)

        # --- Onboarding: days 1,2,3,5,7,9,11,13,15 ---
        onboarding_days = [1, 2, 3, 5, 7, 9, 11, 13, 15]
        print("=== Onboarding Template ===")
        for day in onboarding_days:
            msg = loader.get_message_for_day("onboarding", day)
            if msg is None:
                print(f"  Day {day:2d}: MISSING ❌")
            else:
                snippet = msg.base_content[:80].replace("\n", " ")
                print(f"  Day {day:2d}: OK ✅ — {snippet}...")

        # Also test days that should NOT have messages (gaps)
        gap_days_onb = [4, 6, 8, 10, 12, 14]
        for day in gap_days_onb:
            msg = loader.get_message_for_day("onboarding", day)
            if msg is None:
                print(f"  Day {day:2d}: (no message, expected) ✅")
            else:
                print(f"  Day {day:2d}: UNEXPECTED MESSAGE ⚠️")

        # --- Daily Follow-Up: days 16,18,20,...,44,45 ---
        daily_days = [16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 45]
        print("\n=== Daily Follow-Up Template ===")
        for day in daily_days:
            msg = loader.get_message_for_day("daily_follow_up", day)
            if msg is None:
                print(f"  Day {day:2d}: MISSING ❌")
            else:
                snippet = msg.base_content[:80].replace("\n", " ")
                print(f"  Day {day:2d}: OK ✅ — {snippet}...")

        # --- Quiz Mensal ---
        print("\n=== Quiz Mensal Template ===")
        quiz_template = loader.load_flow_template("quiz_mensal")
        if quiz_template:
            print(f"  Loaded: {quiz_template.name} v{quiz_template.version}")
            print(f"  Days with messages: {sorted(quiz_template.messages.keys())}")
        else:
            print("  MISSING ❌")

        # --- Summary ---
        print("\n=== Summary ===")
        all_ok = True

        for day in onboarding_days:
            if loader.get_message_for_day("onboarding", day) is None:
                print(f"FAIL: onboarding day {day} missing")
                all_ok = False

        for day in daily_days:
            if loader.get_message_for_day("daily_follow_up", day) is None:
                print(f"FAIL: daily_follow_up day {day} missing")
                all_ok = False

        if all_ok:
            print("ALL CHECKS PASSED ✅")
            return 0
        else:
            print("SOME CHECKS FAILED ❌")
            return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
