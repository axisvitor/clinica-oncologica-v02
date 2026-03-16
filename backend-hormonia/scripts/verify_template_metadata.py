#!/usr/bin/env python3
"""Verify send_mode and expects_response for seeded templates."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        # Check step-level send_mode and expects_response from raw JSONB
        from sqlalchemy import text

        rows = db.execute(text("""
            SELECT ftv.template_name, fk.kind_key, ftv.steps
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
            WHERE ftv.is_active = true
            ORDER BY fk.kind_key
        """)).fetchall()

        all_ok = True
        for row in rows:
            template_name = row[0]
            kind_key = row[1]
            steps = row[2]

            print(f"\n=== {template_name} ({kind_key}) ===")
            for step in steps:
                day = step.get("day")
                send_mode = step.get("send_mode", "MISSING")
                messages = step.get("messages", [])
                
                expects_list = []
                for msg in messages:
                    expects_list.append(msg.get("expects_response"))

                print(f"  Day {day:2d}: send_mode={send_mode:20s} expects_response={expects_list}")
                
                if send_mode == "MISSING":
                    print(f"    ⚠️ send_mode missing!")
                    all_ok = False
                if not messages:
                    print(f"    ⚠️ no messages!")
                    all_ok = False
                for msg in messages:
                    if "expects_response" not in msg:
                        print(f"    ⚠️ expects_response missing from message!")
                        all_ok = False

        # Verify specific known values from snapshots
        print("\n=== Spot Checks ===")
        # Onboarding day 1: sequential_auto, all False
        # Onboarding day 3: wait_response, first msg expects_response
        # Daily day 18: single, True
        # Daily day 16: single, False
        
        onb_steps = None
        daily_steps = None
        for row in rows:
            if row[1] == "onboarding":
                onb_steps = {s["day"]: s for s in row[2]}
            elif row[1] == "daily_follow_up":
                daily_steps = {s["day"]: s for s in row[2]}

        checks = [
            ("onboarding", 1, "sequential_auto", onb_steps),
            ("onboarding", 3, "wait_response", onb_steps),
            ("daily_follow_up", 16, "single", daily_steps),
            ("daily_follow_up", 18, "single", daily_steps),
        ]

        for kind, day, expected_mode, steps_map in checks:
            step = steps_map.get(day)
            if not step:
                print(f"  {kind} day {day}: MISSING ❌")
                all_ok = False
                continue
            actual_mode = step.get("send_mode")
            if actual_mode == expected_mode:
                print(f"  {kind} day {day}: send_mode={actual_mode} ✅")
            else:
                print(f"  {kind} day {day}: send_mode={actual_mode} expected={expected_mode} ❌")
                all_ok = False

        # Check expects_response specifically
        # Day 18 daily_follow_up should have expects_response=True
        d18 = daily_steps.get(18) if daily_steps else None
        if d18 and d18["messages"][0].get("expects_response") == True:
            print(f"  daily_follow_up day 18: expects_response=True ✅")
        else:
            print(f"  daily_follow_up day 18: expects_response WRONG ❌")
            all_ok = False

        # Day 16 daily_follow_up should have expects_response=False
        d16 = daily_steps.get(16) if daily_steps else None
        if d16 and d16["messages"][0].get("expects_response") == False:
            print(f"  daily_follow_up day 16: expects_response=False ✅")
        else:
            print(f"  daily_follow_up day 16: expects_response WRONG ❌")
            all_ok = False

        print(f"\n{'ALL CHECKS PASSED ✅' if all_ok else 'SOME CHECKS FAILED ❌'}")
        return 0 if all_ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
