# Initial Concept
Integrated oncology clinic management system featuring a clinical dashboard for staff and a dedicated patient interface for periodic health monitoring.

# Product Definition

## Vision
To provide a robust, secure, and efficient platform for oncology clinics to manage clinical workflows, monitor patient health through periodic assessments, and ensure high-quality care through automated follow-ups and data-driven insights.

## Core Purpose
The system bridges the gap between clinic visits by providing patients with a simple interface for health reporting (Quizzes) and giving clinical staff a centralized dashboard to monitor those responses, manage patient records, and handle administrative tasks.

## Target Users
- **Clinic Administrators:** Responsible for system configuration, user provisioning (physicians/staff), and monitoring system health.
- **Physicians & Clinical Staff:** Use the dashboard to manage patient lists, review health assessments, and respond to clinical alerts.
- **Patients:** Interact with the Next.js quiz interface to provide periodic updates on their health status and symptoms.

## Key Features
- **Patient Monitoring:** Monthly automated health quizzes via WhatsApp integration.
- **Clinical Dashboard:** Real-time monitoring of patient responses and clinical alerts.
- **User Management:** Secure authentication and role-based access control (RBAC).
- **Communication:** Integration with Evolution API for WhatsApp messaging.
- **Resilience:** Built-in circuit breakers, retries, and compensation flows for background tasks.
- **Audit & Compliance:** Detailed audit logging and LGPD-compliant data handling.

## Success Metrics
- High patient engagement with monthly health assessments.
- Reduced time-to-response for critical health alerts.
- System stability with 99.9% uptime for core API services.
