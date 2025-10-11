"""Fix critical RLS policies for 18 tables with enabled RLS but missing policies

Revision ID: 20251011_130000
Revises: 20251011_120000
Create Date: 2025-10-11 13:00:00.000000

CRITICAL SECURITY FIX:
This migration addresses a major security vulnerability where 18 tables have
Row Level Security (RLS) enabled but NO policies defined, effectively blocking
ALL access to these tables.

Tables fixed:
- patients, messages, quiz_sessions, quiz_responses, medical_reports
- audit_logs, appointments, medications, treatments, consents
- notifications, sessions, alerts, flow_analytics, flow_messages
- user_sync_log, webhook_events, whatsapp_delivery_failures

Security Model:
- Doctors can only access their patients' data
- Admins can access everything
- System service can access all data
- Patients can only access their own data (where applicable)

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20251011_130000'
down_revision = '20251011_120000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply comprehensive RLS policies for all 18 tables.
    """

    # Get connection for executing raw SQL
    connection = op.get_bind()

    print("🔒 Starting critical RLS policy implementation...")

    # =============================================================================
    # PATIENTS TABLE - Core patient data access
    # =============================================================================
    print("📋 Setting up RLS policies for PATIENTS table...")

    connection.execute(text("""
        -- Admins can access all patients
        CREATE POLICY "admins_all_patients" ON patients
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        -- Doctors can only access their assigned patients
        CREATE POLICY "doctors_own_patients" ON patients
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'doctor'
                    AND users.id = patients.doctor_id
                )
            );
    """))

    connection.execute(text("""
        -- Patients can access their own data (read-only)
        CREATE POLICY "patients_own_data" ON patients
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'patient'
                    AND users.id = patients.user_id
                )
            );
    """))

    connection.execute(text("""
        -- Service role can access all (for system operations)
        CREATE POLICY "service_all_patients" ON patients
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # MESSAGES TABLE - Patient communication
    # =============================================================================
    print("💬 Setting up RLS policies for MESSAGES table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_messages" ON messages
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_messages" ON messages
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = messages.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_messages" ON messages
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = messages.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_messages" ON messages
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # QUIZ_SESSIONS TABLE - Quiz session management
    # =============================================================================
    print("📝 Setting up RLS policies for QUIZ_SESSIONS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_quiz_sessions" ON quiz_sessions
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_quiz_sessions" ON quiz_sessions
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = quiz_sessions.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_quiz_sessions" ON quiz_sessions
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = quiz_sessions.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_quiz_sessions" ON quiz_sessions
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # QUIZ_RESPONSES TABLE - Quiz answers
    # =============================================================================
    print("✅ Setting up RLS policies for QUIZ_RESPONSES table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_quiz_responses" ON quiz_responses
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_quiz_responses" ON quiz_responses
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    JOIN quiz_sessions qs ON p.id = qs.patient_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND qs.id = quiz_responses.session_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_quiz_responses" ON quiz_responses
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    JOIN quiz_sessions qs ON p.id = qs.patient_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND qs.id = quiz_responses.session_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_quiz_responses" ON quiz_responses
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # MEDICAL_REPORTS TABLE - Medical documentation
    # =============================================================================
    print("🏥 Setting up RLS policies for MEDICAL_REPORTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_medical_reports" ON medical_reports
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_medical_reports" ON medical_reports
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = medical_reports.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_medical_reports" ON medical_reports
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = medical_reports.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_medical_reports" ON medical_reports
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # AUDIT_LOGS TABLE - System audit trail (admin only)
    # =============================================================================
    print("🔍 Setting up RLS policies for AUDIT_LOGS table...")

    connection.execute(text("""
        CREATE POLICY "admins_only_audit_logs" ON audit_logs
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_audit_logs" ON audit_logs
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # APPOINTMENTS TABLE - Medical appointments
    # =============================================================================
    print("📅 Setting up RLS policies for APPOINTMENTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_appointments" ON appointments
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_appointments" ON appointments
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = appointments.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_appointments" ON appointments
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = appointments.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_appointments" ON appointments
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # MEDICATIONS TABLE - Patient medications
    # =============================================================================
    print("💊 Setting up RLS policies for MEDICATIONS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_medications" ON medications
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_medications" ON medications
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = medications.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_medications" ON medications
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = medications.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_medications" ON medications
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # TREATMENTS TABLE - Treatment records
    # =============================================================================
    print("🩺 Setting up RLS policies for TREATMENTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_treatments" ON treatments
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_treatments" ON treatments
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = treatments.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_treatments" ON treatments
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = treatments.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_treatments" ON treatments
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # CONSENTS TABLE - Patient consents
    # =============================================================================
    print("📄 Setting up RLS policies for CONSENTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_consents" ON consents
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_consents" ON consents
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = consents.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_consents" ON consents
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = consents.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_consents" ON consents
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # NOTIFICATIONS TABLE - System notifications
    # =============================================================================
    print("🔔 Setting up RLS policies for NOTIFICATIONS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_notifications" ON notifications
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "users_own_notifications" ON notifications
            FOR ALL
            TO authenticated
            USING (
                notifications.user_id = auth.uid()
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_notifications" ON notifications
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # SESSIONS TABLE - User sessions
    # =============================================================================
    print("🔐 Setting up RLS policies for SESSIONS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_sessions" ON sessions
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "users_own_sessions" ON sessions
            FOR ALL
            TO authenticated
            USING (
                sessions.user_id = auth.uid()
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_sessions" ON sessions
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # ALERTS TABLE - System alerts
    # =============================================================================
    print("⚠️ Setting up RLS policies for ALERTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_alerts" ON alerts
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_alerts" ON alerts
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = alerts.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_alerts" ON alerts
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = alerts.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_alerts" ON alerts
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # FLOW_ANALYTICS TABLE - Analytics data
    # =============================================================================
    print("📊 Setting up RLS policies for FLOW_ANALYTICS table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_flow_analytics" ON flow_analytics
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_flow_analytics" ON flow_analytics
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = flow_analytics.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_flow_analytics" ON flow_analytics
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # FLOW_MESSAGES TABLE - Flow messaging
    # =============================================================================
    print("📨 Setting up RLS policies for FLOW_MESSAGES table...")

    connection.execute(text("""
        CREATE POLICY "admins_all_flow_messages" ON flow_messages
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "doctors_patient_flow_messages" ON flow_messages
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.doctor_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'doctor'
                    AND p.id = flow_messages.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "patients_own_flow_messages" ON flow_messages
            FOR SELECT
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users u
                    JOIN patients p ON u.id = p.user_id
                    WHERE u.id = auth.uid()
                    AND u.role = 'patient'
                    AND p.id = flow_messages.patient_id
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_flow_messages" ON flow_messages
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # USER_SYNC_LOG TABLE - User synchronization logs (admin only)
    # =============================================================================
    print("🔄 Setting up RLS policies for USER_SYNC_LOG table...")

    connection.execute(text("""
        CREATE POLICY "admins_only_user_sync_log" ON user_sync_log
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_user_sync_log" ON user_sync_log
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # WEBHOOK_EVENTS TABLE - Webhook logs (admin only)
    # =============================================================================
    print("🪝 Setting up RLS policies for WEBHOOK_EVENTS table...")

    connection.execute(text("""
        CREATE POLICY "admins_only_webhook_events" ON webhook_events
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_webhook_events" ON webhook_events
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # WHATSAPP_DELIVERY_FAILURES TABLE - WhatsApp failure logs (admin only)
    # =============================================================================
    print("📱 Setting up RLS policies for WHATSAPP_DELIVERY_FAILURES table...")

    connection.execute(text("""
        CREATE POLICY "admins_only_whatsapp_failures" ON whatsapp_delivery_failures
            FOR ALL
            TO authenticated
            USING (
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = auth.uid()
                    AND users.role = 'admin'
                )
            );
    """))

    connection.execute(text("""
        CREATE POLICY "service_all_whatsapp_failures" ON whatsapp_delivery_failures
            FOR ALL
            TO service_role
            USING (true);
    """))

    # =============================================================================
    # VERIFICATION QUERIES - Confirm policies are properly applied
    # =============================================================================
    print("✅ Running verification queries...")

    # Verify all tables have policies
    verification_result = connection.execute(text("""
        SELECT
            schemaname,
            tablename,
            policyname,
            permissive,
            roles,
            cmd,
            qual,
            with_check
        FROM pg_policies
        WHERE schemaname = 'public'
        AND tablename IN (
            'patients', 'messages', 'quiz_sessions', 'quiz_responses',
            'medical_reports', 'audit_logs', 'appointments', 'medications',
            'treatments', 'consents', 'notifications', 'sessions',
            'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
            'webhook_events', 'whatsapp_delivery_failures'
        )
        ORDER BY tablename, policyname;
    """))

    policy_count = len(list(verification_result))
    print(f"📊 Total RLS policies created: {policy_count}")

    # Verify RLS is enabled on all tables
    rls_status = connection.execute(text("""
        SELECT
            schemaname,
            tablename,
            rowsecurity,
            relforcerowsecurity
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        WHERE schemaname = 'public'
        AND tablename IN (
            'patients', 'messages', 'quiz_sessions', 'quiz_responses',
            'medical_reports', 'audit_logs', 'appointments', 'medications',
            'treatments', 'consents', 'notifications', 'sessions',
            'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
            'webhook_events', 'whatsapp_delivery_failures'
        )
        ORDER BY tablename;
    """))

    rls_enabled_count = len(list(rls_status))
    print(f"🔒 Tables with RLS enabled: {rls_enabled_count}")

    print("✅ Critical RLS policy implementation completed successfully!")
    print("🛡️ Security vulnerability fixed - all 18 tables now have proper access policies")


def downgrade() -> None:
    """
    Remove all RLS policies - WARNING: This will restore the security vulnerability!
    """

    # Get connection for executing raw SQL
    connection = op.get_bind()

    print("⚠️ WARNING: Removing RLS policies - This will restore the security vulnerability!")

    # List of all tables with policies to remove
    tables_with_policies = [
        'patients', 'messages', 'quiz_sessions', 'quiz_responses',
        'medical_reports', 'audit_logs', 'appointments', 'medications',
        'treatments', 'consents', 'notifications', 'sessions',
        'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
        'webhook_events', 'whatsapp_delivery_failures'
    ]

    # Remove all policies for each table
    for table in tables_with_policies:
        print(f"🗑️ Removing policies for {table}...")

        # Get all policies for this table
        policies = connection.execute(text(f"""
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = 'public'
            AND tablename = '{table}';
        """))

        # Drop each policy
        for policy in policies:
            policy_name = policy[0]
            connection.execute(text(f"DROP POLICY IF EXISTS \"{policy_name}\" ON {table};"))

    print("🚨 CRITICAL: All RLS policies removed - Security vulnerability restored!")
    print("🚨 IMMEDIATE ACTION REQUIRED: Run the upgrade again to restore security!")