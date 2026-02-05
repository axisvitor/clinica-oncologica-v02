"""
Automated Deprecation Notifications

Celery task that sends weekly email notifications to clients
still using deprecated API endpoints.

Author: Backend API Developer
Created: 2025-01-16
"""

from typing import List
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session

from app.database import get_db, get_scoped_session
from app.task_queue import task_queue as celery_app
from app.monitoring.deprecation_tracking import get_deprecation_tracker

logger = logging.getLogger(__name__)


# ============================================================================
# Database Models (Stub - implement based on your schema)
# ============================================================================


class APIClient:
    """
    Model representing an API client.

    This should match your actual database schema.
    """

    id: str
    name: str
    email: str
    client_id: str  # API key or client identifier
    created_at: datetime


# ============================================================================
# Email Templates
# ============================================================================

DEPRECATION_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .header {{ background-color: #ff6b6b; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
        .action {{ background-color: #28a745; color: white; padding: 15px; text-align: center; margin: 20px 0; }}
        .footer {{ background-color: #f8f9fa; padding: 15px; font-size: 12px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚠️ Important: API Usage Notice</h1>
    </div>

    <div class="content">
        <p>Dear {client_name},</p>

        <div class="warning">
            <strong>Your application is using API v2 endpoints.</strong>
            <br>
            API v2 is the current stable version. No action required at this time.
        </div>

        <h2>Deprecated Endpoints You're Using</h2>

        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Calls (Last 7 Days)</th>
                    <th>Replacement</th>
                </tr>
            </thead>
            <tbody>
                {endpoint_rows}
            </tbody>
        </table>

        <h2>API v2 Status</h2>

        <p>API v2 is the current stable version. You're using the correct endpoints.</p>
        <p>We'll notify you well in advance if any changes are planned.</p>

        <div class="action">
            <h3>Need Help?</h3>
            <p>Join our migration office hours: <strong>Tuesdays 10am-12pm BRT</strong></p>
            <p>Or email us at: <a href="mailto:api-support@clinica.com">api-support@clinica.com</a></p>
        </div>

        <h2>Migration Dashboard</h2>

        <p>Track your migration progress:</p>
        <ul>
            <li>Dashboard: <a href="{dashboard_url}">Your Migration Status</a></li>
            <li>API Docs: <a href="{docs_url}">API v2 Documentation</a></li>
            <li>Status Page: <a href="{status_url}">API Status</a></li>
        </ul>

        <p>Continue using API v2 as normal. No changes are required.</p>

        <p>Best regards,<br>
        Clínica Oncológica API Team</p>
    </div>

    <div class="footer">
        <p>You're receiving this email because your API client (ID: {client_id}) is using deprecated endpoints.</p>
        <p>To unsubscribe from these notifications, contact api-support@clinica.com</p>
    </div>
</body>
</html>
"""

URGENT_DEPRECATION_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .header {{ background-color: #dc3545; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .critical {{ background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 URGENT: API v2 Sunset in {days_remaining} Days</h1>
    </div>

    <div class="content">
        <p>Dear {client_name},</p>

        <div class="critical">
            <h2>Critical Action Required</h2>
            <p>API v2 will be shut down in <strong>{days_remaining} days</strong> on {sunset_date}.</p>
            <p>Your application is still using v2 and <strong>will break</strong> after this date.</p>
        </div>

        <p><strong>You are still making {call_count} requests/day to deprecated endpoints.</strong></p>

        <h2>Immediate Action Required</h2>

        <ol>
            <li>Email api-support@clinica.com IMMEDIATELY if you need an extension</li>
            <li>Review API documentation: {migration_guide_url}</li>
            <li>Join emergency office hours: Daily 2pm-4pm BRT this week</li>
        </ol>

        <p><strong>After {sunset_date}, your application will receive 410 Gone responses and stop working.</strong></p>

        <p>Contact us immediately:<br>
        Email: api-support@clinica.com<br>
        Subject: [URGENT] API v2 Migration - {client_id}</p>
    </div>
</body>
</html>
"""


# ============================================================================
# Email Sending (Stub - integrate with your email service)
# ============================================================================


async def send_email(to: str, subject: str, html_content: str) -> bool:
    """
    Send email via email service.

    This is a stub - integrate with your actual email service:
    - SendGrid
    - AWS SES
    - Mailgun
    - etc.

    Args:
        to: Recipient email
        subject: Email subject
        html_content: HTML email body

    Returns:
        True if sent successfully
    """
    logger.info(f"Sending email to {to}: {subject}")

    # TODO: Integrate with actual email service
    # Example with SendGrid:
    # from sendgrid import SendGridAPIClient
    # from sendgrid.helpers.mail import Mail
    #
    # message = Mail(
    #     from_email='api-team@clinica.com',
    #     to_emails=to,
    #     subject=subject,
    #     html_content=html_content
    # )
    #
    # try:
    #     sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
    #     response = sg.send(message)
    #     return response.status_code == 202
    # except Exception as e:
    #     logger.error(f"Failed to send email: {e}")
    #     return False

    # For now, just log
    logger.info(f"Email content:\n{html_content}")
    return True


# ============================================================================
# Client Lookup
# ============================================================================


def get_api_clients(db: Session) -> List[APIClient]:
    """
    Get all registered API clients.

    Args:
        db: Database session

    Returns:
        List of API clients
    """
    # TODO: Implement based on your database schema
    # Example:
    # return db.query(APIClient).all()

    # Stub for now
    return []


def get_client_by_id(db: Session, client_id: str) -> APIClient:
    """
    Get API client by ID.

    Args:
        db: Database session
        client_id: Client identifier

    Returns:
        API client or None
    """
    # TODO: Implement based on your database schema
    # Example:
    # return db.query(APIClient).filter(APIClient.client_id == client_id).first()

    return None


# ============================================================================
# Celery Tasks
# ============================================================================


@celery_app.task(name="send_deprecation_notifications")
def send_deprecation_notifications():
    """
    Weekly task to email clients still using deprecated APIs.

    Schedule this to run weekly:
    - Via Celery Beat
    - Or via cron

    Example Celery Beat config:
    ```python
    CELERYBEAT_SCHEDULE = {
        'send-deprecation-notifications': {
            'task': 'send_deprecation_notifications',
            'schedule': crontab(day_of_week=1, hour=10, minute=0),  # Mondays 10am
        },
    }
    ```
    """
    logger.info("Starting deprecation notification task")

    tracker = get_deprecation_tracker()
    report = tracker.get_deprecation_report()

    with get_scoped_session() as db:
        try:
            emails_sent = 0
            emails_failed = 0

            # Get all clients at risk
            clients_at_risk = report["clients_at_risk"]

            logger.info(f"Found {len(clients_at_risk)} clients using deprecated APIs")

            for client_info in clients_at_risk:
                client_id = client_info["client_id"]

                # Get client details from database
                client = get_client_by_id(db, client_id)

                if not client or not client.email:
                    logger.warning(f"No email found for client {client_id}")
                    continue

                # Prepare endpoint rows for email
                endpoint_rows = ""
                total_calls = 0

                for endpoint in client_info["endpoints"]:
                    endpoint_rows += f"""
                    <tr>
                        <td>{endpoint["version"]}{endpoint["endpoint"]}</td>
                        <td>{endpoint["call_count"]}</td>
                        <td>Current (v2)</td>
                    </tr>
                    """
                    total_calls += endpoint["call_count"]

                # Calculate days remaining
                # Assuming sunset date is 2025-07-01
                sunset_date = datetime(2025, 7, 1, tzinfo=timezone.utc)
                days_remaining = max(0, (sunset_date - datetime.now(timezone.utc)).days)

                # Choose template based on urgency
                if days_remaining < 30:
                    # Urgent email (less than 30 days)
                    subject = f"🚨 URGENT: API v2 Sunset in {days_remaining} Days"
                    html_content = URGENT_DEPRECATION_EMAIL_TEMPLATE.format(
                        client_name=client.name,
                        days_remaining=days_remaining,
                        sunset_date=sunset_date.strftime("%Y-%m-%d"),
                        call_count=total_calls,
                        client_id=client_id,
                        migration_guide_url="https://api.clinica.com/docs/v2",
                    )
                else:
                    # Regular deprecation notice
                    subject = f"Action Required: API v2 Deprecation ({days_remaining} days remaining)"
                    html_content = DEPRECATION_EMAIL_TEMPLATE.format(
                        client_name=client.name,
                        days_remaining=days_remaining,
                        sunset_date=sunset_date.strftime("%Y-%m-%d"),
                        endpoint_rows=endpoint_rows,
                        client_id=client_id,
                        migration_guide_url="https://api.clinica.com/docs/v2",
                        dashboard_url=f"https://grafana.clinica.com/d/api-versioning?var-client_id={client_id}",
                        docs_url="https://api.clinica.com/docs/v2",
                        status_url="https://status.clinica.com",
                    )

                # Send email
                success = send_email(
                    to=client.email, subject=subject, html_content=html_content
                )

                if success:
                    emails_sent += 1
                    logger.info(f"Sent deprecation email to {client.email}")
                else:
                    emails_failed += 1
                    logger.error(f"Failed to send email to {client.email}")

            logger.info(
                f"Deprecation notification task completed: "
                f"{emails_sent} sent, {emails_failed} failed"
            )

            return {
                "success": True,
                "emails_sent": emails_sent,
                "emails_failed": emails_failed,
                "clients_at_risk": len(clients_at_risk),
            }

        except Exception as e:
            logger.error(f"Error in deprecation notification task: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


@celery_app.task(name="update_sunset_metrics")
def update_sunset_metrics():
    """
    Daily task to update Prometheus metrics for sunset countdown.

    Schedule this to run daily:
    ```python
    CELERYBEAT_SCHEDULE = {
        'update-sunset-metrics': {
            'task': 'update_sunset_metrics',
            'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        },
    }
    ```
    """
    logger.info("Updating sunset metrics")

    tracker = get_deprecation_tracker()

    # Update v2 sunset countdown
    sunset_date_v2 = datetime(2025, 7, 1, tzinfo=timezone.utc)
    tracker.update_sunset_countdown("v2", sunset_date_v2)

    logger.info("Sunset metrics updated")

    return {"success": True}
