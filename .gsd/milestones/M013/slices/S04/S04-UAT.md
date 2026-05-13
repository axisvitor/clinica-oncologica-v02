# S04: Private Upload/Report Serving — UAT

**Milestone:** M013
**Written:** 2026-05-13T01:10:50.297Z

## Automated UAT

- Default/private upload responses do not expose unauthenticated /uploads URLs and advertise the authenticated download route instead.
- /uploads serves only intentionally public assets; private upload bytes and derivatives are denied through the static mount.
- /api/v2/upload/{upload_id}/download requires session authentication and returns bytes for the owner or admin while returning generic errors for anonymous, foreign-user, deleted, missing, and unsafe-path records.
- Taskiq generate_patient_report writes PDFs under the private report artifact root, outside the mounted public upload root.
- Generated report artifact filenames include the generated report_id and sanitized report type, not patient UUIDs or raw patient identifiers.
- Focused pytest suites for private upload serving, Taskiq report tasks, enhanced report APIs, and report-service Taskiq compatibility all pass.
