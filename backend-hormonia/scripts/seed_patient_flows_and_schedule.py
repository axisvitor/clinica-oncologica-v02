#!/usr/bin/env python3
"""
Seed patient flow states for active patients and schedule initial messages + quiz link.
Idempotent by design.
"""
import os
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import json
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
	print("❌ DATABASE_URL not set")
	exit(1)
if DATABASE_URL.startswith("postgresql+psycopg://"):
	DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

INITIAL_FLOW_KIND = "initial_15_days"
INITIAL_VERSION_NUMBER = 1
WHATSAPP_INSTANCE = "default"

flow_version_id = None
patients = []

with psycopg.connect(DATABASE_URL) as conn:
	conn.execute("BEGIN")
	with conn.cursor() as cur:
		# Resolve initial flow template_version
		cur.execute(
			"""
			SELECT ftv.id
			FROM flow_template_versions ftv
			JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
			WHERE fk.kind_key = %s AND ftv.version_number = %s AND ftv.is_active = true
			LIMIT 1
			""",
			(INITIAL_FLOW_KIND, INITIAL_VERSION_NUMBER),
		)
		row = cur.fetchone()
		if not row:
			print("❌ No active flow_template_version found for", INITIAL_FLOW_KIND, INITIAL_VERSION_NUMBER)
			conn.rollback()
			exit(1)
		flow_version_id = row[0]

		# Active patients
		cur.execute(
			"""
			SELECT id, name, phone
			FROM patients
			WHERE flow_state = 'active'
			"""
		)
		patients = cur.fetchall()

		# Ensure whatsapp instance exists
		cur.execute(
			"""
			INSERT INTO whatsapp_instances (id, name, status, is_connected, created_at, updated_at)
			VALUES (%s, %s, %s, %s, NOW(), NOW())
			ON CONFLICT (name) DO NOTHING
			""",
			(str(uuid4()), WHATSAPP_INSTANCE, "connected", True),
		)

		seeded_states = 0
		scheduled_msgs = 0
		created_quiz = 0

		for pid, pname, phone in patients:
			# Seed patient_flow_states if absent
			cur.execute(
				"""
				SELECT 1 FROM patient_flow_states WHERE patient_id = %s LIMIT 1
				""",
				(pid,),
			)
			if cur.fetchone() is None:
				cur.execute(
					"""
					INSERT INTO patient_flow_states (id, patient_id, flow_template_version_id, current_step, started_at, step_data)
					VALUES (%s, %s, %s, %s, NOW(), %s::jsonb)
					""",
					(str(uuid4()), pid, flow_version_id, 0, json.dumps({})),
				)
				seeded_states += 1

			# Schedule first onboarding message in messages
			if phone:
				metadata = {"channel": "whatsapp", "instance": WHATSAPP_INSTANCE, "template": "onboarding_day_1"}
				scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=5)
				cur.execute(
					"""
					INSERT INTO messages (
						id, patient_id, direction, type, content, message_metadata,
						status, scheduled_for, created_at
					) VALUES (%s, %s, 'outbound', 'text', %s, %s::jsonb, 'pending', %s, NOW())
					ON CONFLICT DO NOTHING
					""",
					(
						str(uuid4()),
						pid,
						f"Olá {pname.split(' ')[0]}, vamos começar seu acompanhamento inicial.",
						json.dumps(metadata),
						scheduled_for,
					),
				)
				scheduled_msgs += 1

			# Create monthly quiz session (if none exists yet)
			cur.execute(
				"""
				SELECT 1 FROM quiz_sessions WHERE patient_id = %s LIMIT 1
				""",
				(pid,),
			)
			if cur.fetchone() is None:
				cur.execute(
					"""
					INSERT INTO quiz_sessions (
						id, patient_id, quiz_template_id, status, current_question, started_at, session_metadata
					) SELECT %s, %s, qt.id, 'started', 0, NOW(), %s::jsonb
					FROM quiz_templates qt
					WHERE qt.is_active = true
					LIMIT 1
					""",
					(str(uuid4()), pid, json.dumps({})),
				)
				created_quiz += 1

	conn.commit()

print(f"✅ Seed completed | states={seeded_states} scheduled_msgs={scheduled_msgs} quiz_sessions_created={created_quiz}")
