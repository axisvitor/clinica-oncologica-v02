"""
Example data for API documentation and testing.
"""
from datetime import datetime, date
from uuid import UUID

# Example UUIDs for consistent documentation
EXAMPLE_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
EXAMPLE_PATIENT_ID = "550e8400-e29b-41d4-a716-446655440001"
EXAMPLE_MESSAGE_ID = "550e8400-e29b-41d4-a716-446655440002"
EXAMPLE_QUIZ_ID = "550e8400-e29b-41d4-a716-446655440003"
EXAMPLE_REPORT_ID = "550e8400-e29b-41d4-a716-446655440004"
EXAMPLE_ALERT_ID = "550e8400-e29b-41d4-a716-446655440005"
EXAMPLE_FLOW_ID = "550e8400-e29b-41d4-a716-446655440006"

# Authentication Examples
AUTH_EXAMPLES = {
    "login_request": {
        "email": "doctor@hormonia.com",
        "password": "securepassword123"
    },
    "login_response": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "user": {
            "id": EXAMPLE_USER_ID,
            "email": "doctor@hormonia.com",
            "full_name": "Dr. Sarah Johnson",
            "role": "doctor",
            "is_active": True
        }
    },
    "refresh_request": {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
}

# Patient Examples
PATIENT_EXAMPLES = {
    "patient_create": {
        "phone": "+1234567890",
        "name": "Maria Rodriguez",
        "email": "maria.rodriguez@email.com",
        "birth_date": "1985-03-15",
        "treatment_type": "hormone_replacement_therapy",
        "treatment_start_date": "2024-01-15"
    },
    "patient_response": {
        "id": EXAMPLE_PATIENT_ID,
        "doctor_id": EXAMPLE_USER_ID,
        "phone": "+1234567890",
        "name": "Maria Rodriguez",
        "email": "maria.rodriguez@email.com",
        "birth_date": "1985-03-15",
        "treatment_type": "hormone_replacement_therapy",
        "treatment_start_date": "2024-01-15",
        "flow_state": "active",
        "current_day": 45,
        "created_at": "2024-01-15",
        "updated_at": "2024-02-28"
    },
    "patient_update": {
        "email": "maria.new@email.com",
        "treatment_type": "bioidentical_hormones",
        "current_day": 50
    }
}

# Message Examples
MESSAGE_EXAMPLES = {
    "message_create": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "direction": "outbound",
        "type": "text",
        "content": "Good morning! How are you feeling today? Please rate your energy level from 1-10.",
        "scheduled_for": "2024-03-01T09:00:00Z"
    },
    "message_response": {
        "id": EXAMPLE_MESSAGE_ID,
        "patient_id": EXAMPLE_PATIENT_ID,
        "direction": "outbound",
        "type": "text",
        "content": "Good morning! How are you feeling today? Please rate your energy level from 1-10.",
        "message_metadata": {
            "flow_step": 5,
            "template_id": "daily_check_in"
        },
        "whatsapp_id": "wamid.HBgNMTIzNDU2Nzg5MBUCABIYFjNBMzM1RjA4RkY1NzQ5NzBBNzY4",
        "status": "delivered",
        "scheduled_for": "2024-03-01T09:00:00Z",
        "sent_at": "2024-03-01T09:00:05Z",
        "delivered_at": "2024-03-01T09:00:10Z",
        "created_at": "2024-03-01T08:55:00Z",
        "updated_at": "2024-03-01T09:00:10Z"
    },
    "inbound_message": {
        "patient_phone": "+1234567890",
        "content": "I'm feeling much better today! Energy level is about 8/10.",
        "whatsapp_id": "wamid.HBgNMTIzNDU2Nzg5MBUCABIYFjNBMzM1RjA4RkY1NzQ5NzBBNzY4",
        "type": "text",
        "message_metadata": {
            "timestamp": "2024-03-01T09:15:00Z"
        }
    }
}

# Flow Examples
FLOW_EXAMPLES = {
    "flow_template_create": {
        "name": "Daily Check-in Flow",
        "flow_type": "daily_checkin",
        "version": "1.0.0",
        "description": "Daily patient check-in and symptom tracking",
        "duration_days": 90,
        "is_active": True,
        "template_data": {
            "steps": [
                {
                    "step_id": 1,
                    "name": "Morning Greeting",
                    "triggers": ["time:09:00"],
                    "actions": [
                        {
                            "type": "send_message",
                            "content": "Good morning! How are you feeling today?"
                        }
                    ]
                },
                {
                    "step_id": 2,
                    "name": "Energy Assessment",
                    "triggers": ["response_received"],
                    "actions": [
                        {
                            "type": "send_quiz",
                            "quiz_id": "energy_assessment"
                        }
                    ]
                }
            ],
            "triggers": ["patient_active"]
        }
    },
    "flow_state_response": {
        "id": EXAMPLE_FLOW_ID,
        "patient_id": EXAMPLE_PATIENT_ID,
        "flow_type": "daily_checkin",
        "template_version": "1.0.0",
        "current_step": 2,
        "started_at": "2024-01-15T00:00:00Z",
        "state_data": {
            "last_response": "2024-03-01T09:15:00Z",
            "completion_rate": 0.85,
            "missed_days": 3
        },
        "created_at": "2024-01-15T00:00:00Z",
        "updated_at": "2024-03-01T09:15:00Z"
    },
    "flow_progression_request": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "target_step": 3,
        "force_advance": False,
        "metadata": {
            "reason": "manual_progression",
            "triggered_by": EXAMPLE_USER_ID
        }
    }
}

# Quiz Examples
QUIZ_EXAMPLES = {
    "quiz_template_create": {
        "name": "Daily Symptom Assessment",
        "version": "1.0.0",
        "questions": [
            {
                "id": "energy_level",
                "type": "scale",
                "text": "How would you rate your energy level today?",
                "description": "Scale from 1 (very low) to 10 (very high)",
                "required": True,
                "validation_rules": [
                    {
                        "type": "range",
                        "value": [1, 10],
                        "message": "Please select a value between 1 and 10"
                    }
                ]
            },
            {
                "id": "mood_rating",
                "type": "multiple_choice",
                "text": "How would you describe your mood today?",
                "required": True,
                "options": [
                    {"id": "excellent", "text": "Excellent", "value": "excellent"},
                    {"id": "good", "text": "Good", "value": "good"},
                    {"id": "fair", "text": "Fair", "value": "fair"},
                    {"id": "poor", "text": "Poor", "value": "poor"}
                ]
            }
        ],
        "is_active": True
    },
    "quiz_response_create": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "quiz_template_id": EXAMPLE_QUIZ_ID,
        "question_id": "energy_level",
        "question_text": "How would you rate your energy level today?",
        "response_type": "scale",
        "response_value": "8",
        "response_metadata": {
            "scale_min": 1,
            "scale_max": 10
        },
        "responded_at": "2024-03-01T09:15:00Z"
    },
    "quiz_session_create": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "quiz_template_id": EXAMPLE_QUIZ_ID
    }
}

# Report Examples
REPORT_EXAMPLES = {
    "report_generation_request": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "period_start": "2024-02-01",
        "period_end": "2024-02-29",
        "include_sections": ["summary", "treatment", "symptoms", "adherence", "recommendations"],
        "format": "pdf"
    },
    "report_preview": {
        "patient_name": "Maria Rodriguez",
        "patient_id": EXAMPLE_PATIENT_ID,
        "doctor_name": "Dr. Sarah Johnson",
        "report_period": "February 1-29, 2024",
        "generated_date": "2024-03-01T10:00:00Z",
        "executive_summary": "Patient shows excellent progress with 95% medication adherence and significant improvement in energy levels.",
        "treatment_progress": {
            "title": "Treatment Progress",
            "content": "Patient has completed 45 days of hormone replacement therapy with consistent improvement in symptoms.",
            "subsections": []
        },
        "symptoms_analysis": {
            "title": "Symptom Analysis",
            "content": "Energy levels have improved from average 4/10 to 8/10. Mood stability has increased significantly.",
            "subsections": []
        },
        "medication_adherence": {
            "title": "Medication Adherence",
            "content": "95% adherence rate with only 2 missed doses in the reporting period.",
            "subsections": []
        },
        "recommendations": {
            "title": "Recommendations",
            "content": "Continue current treatment plan. Consider increasing exercise recommendations.",
            "subsections": []
        },
        "quiz_responses_count": 28,
        "message_statistics": {
            "sent": 45,
            "received": 32,
            "response_rate": 0.71
        },
        "alert_count": 1
    },
    "analytics_request": {
        "patient_ids": [EXAMPLE_PATIENT_ID],
        "start_date": "2024-02-01",
        "end_date": "2024-02-29",
        "metrics": ["engagement", "adherence", "symptoms", "alerts"]
    }
}

# Alert Examples
ALERT_EXAMPLES = {
    "alert_create": {
        "patient_id": EXAMPLE_PATIENT_ID,
        "alert_type": "symptom_concern",
        "severity": "medium",
        "description": "Patient reported persistent fatigue for 3 consecutive days",
        "data": {
            "symptom": "fatigue",
            "duration_days": 3,
            "severity_trend": "increasing"
        }
    },
    "alert_response": {
        "id": EXAMPLE_ALERT_ID,
        "patient_id": EXAMPLE_PATIENT_ID,
        "alert_type": "symptom_concern",
        "severity": "medium",
        "description": "Patient reported persistent fatigue for 3 consecutive days",
        "data": {
            "symptom": "fatigue",
            "duration_days": 3,
            "severity_trend": "increasing"
        },
        "status": "pending",
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_at": None,
        "created_at": "2024-03-01T10:30:00Z",
        "updated_at": "2024-03-01T10:30:00Z"
    },
    "alert_acknowledge": {
        "user_id": EXAMPLE_USER_ID
    }
}

# WebSocket Examples
WEBSOCKET_EXAMPLES = {
    "authentication_request": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "join_room_request": {
        "patient_id": EXAMPLE_PATIENT_ID
    },
    "websocket_message": {
        "type": "new_message",
        "timestamp": "2024-03-01T09:15:00Z",
        "data": {
            "message_id": EXAMPLE_MESSAGE_ID,
            "patient_id": EXAMPLE_PATIENT_ID,
            "direction": "inbound",
            "type": "text",
            "content": "I'm feeling much better today!",
            "status": "received"
        }
    }
}

# Error Examples
ERROR_EXAMPLES = {
    "validation_error": {
        "error": "validation_error",
        "message": "Request validation failed",
        "field_errors": {
            "email": ["Invalid email format"],
            "phone": ["Phone number must start with country code (+)"]
        },
        "timestamp": "2024-03-01T10:00:00Z"
    },
    "not_found": {
        "error": "not_found",
        "message": "Patient not found",
        "resource_type": "patient",
        "resource_id": EXAMPLE_PATIENT_ID,
        "timestamp": "2024-03-01T10:00:00Z"
    },
    "unauthorized": {
        "error": "unauthorized",
        "message": "Authentication required",
        "timestamp": "2024-03-01T10:00:00Z"
    },
    "forbidden": {
        "error": "forbidden",
        "message": "Insufficient permissions",
        "required_permissions": ["patient:read"],
        "timestamp": "2024-03-01T10:00:00Z"
    },
    "rate_limit": {
        "error": "rate_limit_exceeded",
        "message": "Rate limit exceeded",
        "retry_after": 60,
        "limit": 100,
        "timestamp": "2024-03-01T10:00:00Z"
    }
}

# Common Examples
COMMON_EXAMPLES = {
    "pagination_params": {
        "skip": 0,
        "limit": 20
    },
    "paginated_response": {
        "total": 150,
        "skip": 0,
        "limit": 20,
        "has_next": True,
        "has_previous": False
    },
    "success_response": {
        "status": "success",
        "message": "Operation completed successfully",
        "data": {
            "id": EXAMPLE_PATIENT_ID,
            "status": "updated"
        },
        "timestamp": "2024-03-01T10:00:00Z"
    },
    "health_check": {
        "status": "healthy",
        "timestamp": "2024-03-01T10:00:00Z",
        "version": "1.0.0",
        "dependencies": {
            "database": "healthy",
            "redis": "healthy",
            "evolution_api": "healthy"
        }
    }
}

# Combine all examples
ALL_EXAMPLES = {
    "auth": AUTH_EXAMPLES,
    "patient": PATIENT_EXAMPLES,
    "message": MESSAGE_EXAMPLES,
    "flow": FLOW_EXAMPLES,
    "quiz": QUIZ_EXAMPLES,
    "report": REPORT_EXAMPLES,
    "alert": ALERT_EXAMPLES,
    "websocket": WEBSOCKET_EXAMPLES,
    "error": ERROR_EXAMPLES,
    "common": COMMON_EXAMPLES,
}