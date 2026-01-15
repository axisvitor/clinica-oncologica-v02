# Flow Kinds

This document describes the supported flow kinds and how they are used across the system.

## Canonical kinds

| kind_key | Purpose | Typical duration | Message frequency | Common use cases |
| --- | --- | --- | --- | --- |
| onboarding | Introduce the patient to the program and establish baseline context | 7-15 days | Daily | Welcome, first check-ins, education |
| daily_follow_up | Ongoing follow-up after onboarding | 30-45 days | Daily or every few days | Routine check-ins, adherence reminders |
| quiz_mensal | Monthly assessments and questionnaires | 30 days | Monthly | Monthly quiz, symptom surveys |
| custom | Ad-hoc or bespoke flows | Varies | Varies | Clinician-defined or experimental flows |

## Legacy aliases

Some environments still store legacy keys in `flow_kinds.kind_key`. These are treated as aliases for compatibility:

- onboarding: `initial_15_days`
- daily_follow_up: `daily_checkin`, `daily_engagement`, `days_16_45`
- quiz_mensal: `monthly_quiz`, `monthly_recurring`

When possible, prefer the canonical keys in new templates and client integrations.
