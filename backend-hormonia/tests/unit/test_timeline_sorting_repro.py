import pytest
from datetime import datetime, timezone
from app.api.v2.routers.patients.flow import _normalize_datetime

def test_timeline_sorting_mixed_types_success():
    """
    Verification test for fix of TypeError in get_patient_timeline sorting.
    """
    # Create a list of events with mixed date types (datetime and str)
    events = [
        {"date": datetime(2023, 1, 1, tzinfo=timezone.utc), "event": "event1"},
        {"date": "2023-01-02T10:00:00+00:00", "event": "event2"},
        {"date": None, "event": "event3"},
    ]
    
    # Sort using the new helper
    events.sort(key=lambda x: _normalize_datetime(x.get("date")), reverse=True)
    
    # Check order (most recent first)
    assert events[0]["event"] == "event2"  # 2023-01-02
    assert events[1]["event"] == "event1"  # 2023-01-01
    assert events[2]["event"] == "event3"  # None (datetime.min)

def test_normalize_datetime_helper():
    """Test the _normalize_datetime helper individually."""
    # Test datetime
    dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    assert _normalize_datetime(dt) == dt
    
    # Test naive datetime (should become aware)
    dt_naive = datetime(2023, 1, 1)
    assert _normalize_datetime(dt_naive).tzinfo is not None
    
    # Test ISO string
    s = "2023-01-01T10:00:00+00:00"
    assert isinstance(_normalize_datetime(s), datetime)
    assert _normalize_datetime(s).year == 2023
    
    # Test Z string
    s_z = "2023-01-01T10:00:00Z"
    assert _normalize_datetime(s_z).tzinfo is not None
    
    # Test None
    assert _normalize_datetime(None) == datetime.min.replace(tzinfo=timezone.utc)
    
    # Test invalid string
    assert _normalize_datetime("invalid") == datetime.min.replace(tzinfo=timezone.utc)