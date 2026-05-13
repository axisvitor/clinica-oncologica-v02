---
estimated_steps: 39
estimated_files: 5
skills_used: []
---

# T03: Remove quiz answer and PHI localStorage persistence

---
estimated_steps: 8
estimated_files: 5
skills_used:
  - react-best-practices
  - tdd
  - verify-before-complete
---

Why: The public quiz app currently saves `answers`, `otherTexts`, session IDs, patient names, template names, and question progress under `quiz-progress-v1-*` for seven days. Existing tests only check exact sensitive key names before answers are saved, so they do not prove PHI/answer non-persistence.

Files: `quiz-mensal-interface/lib/quiz-progress-storage.ts`, `quiz-mensal-interface/hooks/quiz/useQuizState.ts`, `quiz-mensal-interface/app/page.tsx`, `quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx`, `quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx`.

Do:
1. Replace persistent quiz progress storage with a safe no-PHI contract: `saveQuizProgress` must not write answers/free text/session/patient/template data, `loadQuizProgress` returns `null`, and cleanup removes all legacy `quiz-progress-*` keys.
2. Keep public quiz resume semantics backed by the backend `session.current_question_index` and HttpOnly `quiz_session_state` cookie only; do not copy cookie/session identifiers into web storage.
3. Remove or bypass `ResumeQuizDialog`/`resumeFromSaved` page flow so the quiz page no longer asks to restore local answers. It is acceptable to leave the component file unused if deleting it would create extra churn.
4. Update `useQuizState` so it initializes from backend session state, never restores answers/free text from localStorage, and never schedules autosave of answer maps; completion/error cleanup should still clear legacy keys generically.
5. Ensure localStorage/sessionStorage failures (private mode) are swallowed without logging PHI and without blocking quiz rendering/submission.
6. Add storage utility tests that seed legacy records containing answers, free text, patient/template labels, session IDs, token-like fields, and invalid JSON, then assert cleanup/load removes them and no save path persists them.
7. Add a component/security test that interacts with a quiz answer/free-text flow and then asserts all web-storage keys and values do not contain the fixture session ID, patient name, template name, question text, answer text, other text, token, cookie state, or PHI-like payload.

Failure Modes (Q5): localStorage unavailable/throws, malformed legacy JSON, large legacy records, missing backend `current_question_index`, and submit failures must not produce PHI persistence or block the existing controlled quiz flow.

Load Profile (Q6): Removing answer autosave eliminates per-answer web-storage writes. Legacy cleanup is O(localStorage key count) at mount/session boundary; at 10x quiz volume, browser storage size should decrease rather than grow.

Negative Tests (Q7): Legacy valid progress with PHI, invalid JSON, unrelated localStorage keys that must be preserved, private-mode throwing storage, answer text/free-text interaction, and completion cleanup.

Done when: focused Jest tests prove the public quiz frontend uses backend/cookie session recovery only and does not persist answer or PHI payloads in browser storage.

## Inputs

- `quiz-mensal-interface/lib/quiz-progress-storage.ts` — existing localStorage persistence utility.
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts` — current answer state and autosave behavior.
- `quiz-mensal-interface/app/page.tsx` — page-level resume dialog/localStorage loading.
- `quiz-mensal-interface/components/quiz-interface.tsx` — answer interaction path for storage proof.
- `quiz-mensal-interface/components/quiz/ResumeQuizDialog.tsx` — current local resume UI to remove/bypass.
- `quiz-mensal-interface/tests/security/session-security.test.tsx` — existing storage/security test baseline.
- `quiz-mensal-interface/package.json` — Jest script/dependency context.
- `quiz-mensal-interface/tests/setup.ts` — quiz app test setup.

## Expected Output

- `quiz-mensal-interface/lib/quiz-progress-storage.ts` — safe no-PHI storage/legacy-cleanup contract.
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts` — no answer/free-text localStorage restore or autosave.
- `quiz-mensal-interface/app/page.tsx` — no local resume dialog flow for answer persistence.
- `quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx` — deterministic legacy cleanup/no-save proof.
- `quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx` — deterministic quiz interaction storage proof.

## Verification

- `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx`

## Inputs

- `quiz-mensal-interface/lib/quiz-progress-storage.ts`
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts`
- `quiz-mensal-interface/app/page.tsx`
- `quiz-mensal-interface/components/quiz-interface.tsx`
- `quiz-mensal-interface/components/quiz/ResumeQuizDialog.tsx`
- `quiz-mensal-interface/tests/security/session-security.test.tsx`
- `quiz-mensal-interface/package.json`
- `quiz-mensal-interface/tests/setup.ts`

## Expected Output

- `quiz-mensal-interface/lib/quiz-progress-storage.ts`
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts`
- `quiz-mensal-interface/app/page.tsx`
- `quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx`
- `quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx`

## Verification

npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx

## Observability Impact

Quiz storage diagnostics should be limited to generic legacy-cleanup/no-persistence events and must not include session IDs, patient/template labels, answers, free text, tokens, cookies, or signed state.
