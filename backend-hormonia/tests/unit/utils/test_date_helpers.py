"""
Comprehensive unit tests for app.utils.date_helpers module.
Tests date calculations, treatment day calculations, and business date utilities.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.utils.date_helpers import (
    _calculate_treatment_day, _parse_date, _get_today_in_timezone,
    calculate_flow_type_from_day, get_treatment_phase_info,
    is_business_day, get_next_business_day, calculate_days_until_next_phase,
    format_treatment_day_info, is_within_business_hours, get_next_scheduled_time,
    _get_next_daily_time, _get_next_interval_time, _get_next_monthly_time,
    _get_default_next_time
)


class TestParseDate:
    """Test date parsing functionality."""

    def test_parse_date_date_object(self):
        """Test parsing date object."""
        test_date = date(2024, 1, 15)
        result = _parse_date(test_date)
        assert result == test_date

    def test_parse_date_datetime_object(self):
        """Test parsing datetime object."""
        test_datetime = datetime(2024, 1, 15, 14, 30, 0)
        result = _parse_date(test_datetime)
        assert result == date(2024, 1, 15)

    def test_parse_date_iso_string_with_time(self):
        """Test parsing ISO string with time."""
        iso_string = "2024-01-15T14:30:00"
        result = _parse_date(iso_string)
        assert result == date(2024, 1, 15)

    def test_parse_date_iso_string_with_timezone(self):
        """Test parsing ISO string with timezone."""
        iso_string = "2024-01-15T14:30:00Z"
        result = _parse_date(iso_string)
        assert result == date(2024, 1, 15)

    def test_parse_date_date_only_string(self):
        """Test parsing date-only string."""
        date_string = "2024-01-15"
        result = _parse_date(date_string)
        assert result == date(2024, 1, 15)

    def test_parse_date_alternative_formats(self):
        """Test parsing alternative date formats."""
        test_cases = [
            ("15/01/2024", date(2024, 1, 15)),
            ("15-01-2024", date(2024, 1, 15)),
            ("2024/01/15", date(2024, 1, 15))
        ]

        for date_str, expected in test_cases:
            result = _parse_date(date_str)
            assert result == expected

    def test_parse_date_invalid_string(self):
        """Test parsing invalid date string."""
        invalid_dates = [
            "not-a-date",
            "2024-13-40",  # Invalid month/day
            "invalid format",
            ""
        ]

        for invalid_date in invalid_dates:
            result = _parse_date(invalid_date)
            assert result is None

    def test_parse_date_none_input(self):
        """Test parsing None input."""
        result = _parse_date(None)
        assert result is None


class TestGetTodayInTimezone:
    """Test timezone-aware date retrieval."""

    def test_get_today_in_timezone_default(self):
        """Test getting today's date in default timezone."""
        with patch('app.utils.date_helpers.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.date.return_value = date(2024, 1, 15)
            mock_datetime.now.return_value = mock_now

            result = _get_today_in_timezone()

            assert result == date(2024, 1, 15)
            mock_datetime.now.assert_called_once()

    def test_get_today_in_timezone_custom(self):
        """Test getting today's date in custom timezone."""
        with patch('app.utils.date_helpers.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.date.return_value = date(2024, 1, 15)
            mock_datetime.now.return_value = mock_now

            result = _get_today_in_timezone("America/New_York")

            assert result == date(2024, 1, 15)

    def test_get_today_in_timezone_invalid_timezone(self):
        """Test getting today's date with invalid timezone falls back to UTC."""
        with patch('app.utils.date_helpers.datetime') as mock_datetime, \
             patch('app.utils.date_helpers.ZoneInfo') as mock_zone_info, \
             patch('app.utils.date_helpers.logger') as mock_logger:

            mock_zone_info.side_effect = Exception("Invalid timezone")
            mock_datetime.utcnow.return_value.date.return_value = date(2024, 1, 15)

            result = _get_today_in_timezone("Invalid/Timezone")

            assert result == date(2024, 1, 15)
            mock_logger.warning.assert_called_once()
            mock_datetime.utcnow.assert_called_once()


class TestCalculateTreatmentDay:
    """Test treatment day calculation."""

    def test_calculate_treatment_day_same_date(self):
        """Test treatment day calculation for same date."""
        start_date = date(2024, 1, 1)
        reference_date = date(2024, 1, 1)

        result = _calculate_treatment_day(start_date, reference_date)
        assert result == 1

    def test_calculate_treatment_day_future_dates(self):
        """Test treatment day calculation for future dates."""
        start_date = date(2024, 1, 1)
        test_cases = [
            (date(2024, 1, 2), 2),   # Day 2
            (date(2024, 1, 10), 10), # Day 10
            (date(2024, 1, 31), 31), # Day 31
            (date(2024, 2, 1), 32),  # Day 32 (next month)
        ]

        for reference_date, expected_day in test_cases:
            result = _calculate_treatment_day(start_date, reference_date)
            assert result == expected_day

    def test_calculate_treatment_day_past_start_date(self):
        """Test treatment day calculation when reference is before start date."""
        start_date = date(2024, 1, 10)
        reference_date = date(2024, 1, 5)  # Before start date

        result = _calculate_treatment_day(start_date, reference_date)
        assert result == 0

    def test_calculate_treatment_day_none_start_date(self):
        """Test treatment day calculation with None start date."""
        result = _calculate_treatment_day(None, date(2024, 1, 1))
        assert result == 0

    def test_calculate_treatment_day_empty_start_date(self):
        """Test treatment day calculation with empty start date."""
        result = _calculate_treatment_day("", date(2024, 1, 1))
        assert result == 0

    def test_calculate_treatment_day_invalid_start_date(self):
        """Test treatment day calculation with invalid start date."""
        with patch('app.utils.date_helpers.logger') as mock_logger:
            result = _calculate_treatment_day("invalid-date", date(2024, 1, 1))

            assert result == 0
            mock_logger.warning.assert_called()

    def test_calculate_treatment_day_no_reference_date(self):
        """Test treatment day calculation without reference date uses today."""
        start_date = date(2024, 1, 1)

        with patch('app.utils.date_helpers._get_today_in_timezone') as mock_today:
            mock_today.return_value = date(2024, 1, 5)

            result = _calculate_treatment_day(start_date)

            assert result == 5
            mock_today.assert_called_once()

    def test_calculate_treatment_day_string_dates(self):
        """Test treatment day calculation with string dates."""
        result = _calculate_treatment_day("2024-01-01", "2024-01-10")
        assert result == 10

    def test_calculate_treatment_day_datetime_objects(self):
        """Test treatment day calculation with datetime objects."""
        start_datetime = datetime(2024, 1, 1, 10, 0, 0)
        reference_datetime = datetime(2024, 1, 5, 15, 30, 0)

        result = _calculate_treatment_day(start_datetime, reference_datetime)
        assert result == 5

    def test_calculate_treatment_day_custom_timezone(self):
        """Test treatment day calculation with custom timezone."""
        start_date = date(2024, 1, 1)

        with patch('app.utils.date_helpers._get_today_in_timezone') as mock_today:
            mock_today.return_value = date(2024, 1, 8)

            result = _calculate_treatment_day(start_date, timezone="America/New_York")

            assert result == 8
            mock_today.assert_called_with("America/New_York")

    def test_calculate_treatment_day_exception_handling(self):
        """Test treatment day calculation handles exceptions."""
        with patch('app.utils.date_helpers._parse_date') as mock_parse, \
             patch('app.utils.date_helpers.logger') as mock_logger:

            mock_parse.side_effect = Exception("Parse error")

            result = _calculate_treatment_day("2024-01-01", "2024-01-05")

            assert result == 0
            mock_logger.error.assert_called()


class TestCalculateFlowTypeFromDay:
    """Test flow type calculation based on treatment day."""

    def test_calculate_flow_type_day_1_15(self):
        """Test flow type for days 1-15."""
        test_cases = [0, 1, 5, 10, 15]

        for day in test_cases:
            result = calculate_flow_type_from_day(day)
            assert result == "day_1_15"

    def test_calculate_flow_type_day_16_45(self):
        """Test flow type for days 16-45."""
        test_cases = [16, 20, 30, 40, 45]

        for day in test_cases:
            result = calculate_flow_type_from_day(day)
            assert result == "day_16_45"

    def test_calculate_flow_type_monthly(self):
        """Test flow type for days 46+."""
        test_cases = [46, 50, 100, 365]

        for day in test_cases:
            result = calculate_flow_type_from_day(day)
            assert result == "monthly"

    def test_calculate_flow_type_negative_day(self):
        """Test flow type for negative days defaults to initial flow."""
        result = calculate_flow_type_from_day(-5)
        assert result == "day_1_15"


class TestGetTreatmentPhaseInfo:
    """Test comprehensive treatment phase information."""

    def test_get_treatment_phase_info(self):
        """Test getting treatment phase info."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc_day:
            mock_calc_day.return_value = 25

            day, flow_type = get_treatment_phase_info("2024-01-01", "2024-01-25")

            assert day == 25
            assert flow_type == "day_16_45"
            mock_calc_day.assert_called_once_with("2024-01-01", "2024-01-25")

    def test_get_treatment_phase_info_no_reference(self):
        """Test getting treatment phase info without reference date."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc_day:
            mock_calc_day.return_value = 50

            day, flow_type = get_treatment_phase_info("2024-01-01")

            assert day == 50
            assert flow_type == "monthly"


class TestBusinessDayUtils:
    """Test business day utility functions."""

    def test_is_business_day_weekdays(self):
        """Test is_business_day for weekdays."""
        # Monday = 0, Tuesday = 1, ..., Friday = 4
        weekdays = [
            date(2024, 1, 1),  # Monday
            date(2024, 1, 2),  # Tuesday
            date(2024, 1, 3),  # Wednesday
            date(2024, 1, 4),  # Thursday
            date(2024, 1, 5),  # Friday
        ]

        for day in weekdays:
            assert is_business_day(day) is True

    def test_is_business_day_weekends(self):
        """Test is_business_day for weekends."""
        weekends = [
            date(2024, 1, 6),  # Saturday
            date(2024, 1, 7),  # Sunday
        ]

        for day in weekends:
            assert is_business_day(day) is False

    def test_is_business_day_none_uses_today(self):
        """Test is_business_day with None uses today."""
        with patch('app.utils.date_helpers._get_today_in_timezone') as mock_today:
            mock_today.return_value = date(2024, 1, 3)  # Wednesday

            result = is_business_day(None)

            assert result is True
            mock_today.assert_called_once()

    def test_is_business_day_string_date(self):
        """Test is_business_day with string date."""
        result = is_business_day("2024-01-03")  # Wednesday
        assert result is True

        result = is_business_day("2024-01-06")  # Saturday
        assert result is False

    def test_is_business_day_invalid_date(self):
        """Test is_business_day with invalid date."""
        result = is_business_day("invalid-date")
        assert result is False

    def test_get_next_business_day_from_friday(self):
        """Test get_next_business_day from Friday returns Monday."""
        friday = date(2024, 1, 5)
        result = get_next_business_day(friday)
        assert result == date(2024, 1, 8)  # Monday

    def test_get_next_business_day_from_saturday(self):
        """Test get_next_business_day from Saturday returns Monday."""
        saturday = date(2024, 1, 6)
        result = get_next_business_day(saturday)
        assert result == date(2024, 1, 8)  # Monday

    def test_get_next_business_day_from_sunday(self):
        """Test get_next_business_day from Sunday returns Monday."""
        sunday = date(2024, 1, 7)
        result = get_next_business_day(sunday)
        assert result == date(2024, 1, 8)  # Monday

    def test_get_next_business_day_from_wednesday(self):
        """Test get_next_business_day from Wednesday returns Thursday."""
        wednesday = date(2024, 1, 3)
        result = get_next_business_day(wednesday)
        assert result == date(2024, 1, 4)  # Thursday

    def test_get_next_business_day_none_uses_today(self):
        """Test get_next_business_day with None uses today."""
        with patch('app.utils.date_helpers._get_today_in_timezone') as mock_today:
            mock_today.return_value = date(2024, 1, 3)  # Wednesday

            result = get_next_business_day(None)

            assert result == date(2024, 1, 4)  # Thursday


class TestCalculateDaysUntilNextPhase:
    """Test days until next treatment phase calculation."""

    def test_calculate_days_until_next_phase_day_1_15(self):
        """Test days until next phase from day_1_15 phase."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc:
            mock_calc.return_value = 10

            result = calculate_days_until_next_phase("2024-01-01", "2024-01-10")

            assert result == 6  # 16 - 10

    def test_calculate_days_until_next_phase_day_16_45(self):
        """Test days until next phase from day_16_45 phase."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc:
            mock_calc.return_value = 30

            result = calculate_days_until_next_phase("2024-01-01", "2024-01-30")

            assert result == 16  # 46 - 30

    def test_calculate_days_until_next_phase_monthly(self):
        """Test days until next phase from monthly phase (final phase)."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc:
            mock_calc.return_value = 50

            result = calculate_days_until_next_phase("2024-01-01", "2024-02-19")

            assert result is None  # Already in final phase

    def test_calculate_days_until_next_phase_edge_cases(self):
        """Test days until next phase for edge cases."""
        with patch('app.utils.date_helpers._calculate_treatment_day') as mock_calc:
            # Exactly at phase boundary
            mock_calc.return_value = 15
            result = calculate_days_until_next_phase("2024-01-01", "2024-01-15")
            assert result == 1  # 16 - 15

            # Exactly at next phase boundary
            mock_calc.return_value = 45
            result = calculate_days_until_next_phase("2024-01-01", "2024-02-14")
            assert result == 1  # 46 - 45


class TestFormatTreatmentDayInfo:
    """Test treatment day information formatting."""

    def test_format_treatment_day_info_basic(self):
        """Test basic treatment day info formatting."""
        with patch('app.utils.date_helpers.get_treatment_phase_info') as mock_phase:
            mock_phase.return_value = (25, "day_16_45")

            result = format_treatment_day_info("2024-01-01", "2024-01-25")

            assert "Dia 25 do tratamento" in result
            assert "Fase de Manutenção" in result

    def test_format_treatment_day_info_without_phase(self):
        """Test treatment day info formatting without phase."""
        with patch('app.utils.date_helpers.get_treatment_phase_info') as mock_phase:
            mock_phase.return_value = (10, "day_1_15")

            result = format_treatment_day_info("2024-01-01", "2024-01-10", include_phase=False)

            assert result == "Dia 10 do tratamento"
            assert "Fase" not in result

    def test_format_treatment_day_info_not_started(self):
        """Test treatment day info formatting when not started."""
        with patch('app.utils.date_helpers.get_treatment_phase_info') as mock_phase:
            mock_phase.return_value = (0, "day_1_15")

            result = format_treatment_day_info("2024-01-01", "2023-12-31")

            assert result == "Tratamento não iniciado"

    def test_format_treatment_day_info_all_phases(self):
        """Test treatment day info formatting for all phases."""
        phase_test_cases = [
            (5, "day_1_15", "Fase Inicial"),
            (25, "day_16_45", "Fase de Manutenção"),
            (60, "monthly", "Acompanhamento Mensal"),
            (10, "unknown_phase", "Fase Desconhecida")
        ]

        for day, phase, expected_phase_name in phase_test_cases:
            with patch('app.utils.date_helpers.get_treatment_phase_info') as mock_phase:
                mock_phase.return_value = (day, phase)

                result = format_treatment_day_info("2024-01-01", "2024-01-10")

                assert f"Dia {day} do tratamento" in result
                assert expected_phase_name in result


class TestBusinessHoursUtils:
    """Test business hours utility functions."""

    def test_is_within_business_hours_default(self):
        """Test is_within_business_hours with default hours."""
        # Mock business day and time within hours (10 AM)
        test_time = datetime(2024, 1, 3, 10, 0, 0)  # Wednesday 10:00 AM

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = is_within_business_hours(test_time)
            assert result is True

    def test_is_within_business_hours_outside_hours(self):
        """Test is_within_business_hours outside business hours."""
        # Mock business day but time outside hours (8 PM)
        test_time = datetime(2024, 1, 3, 20, 0, 0)  # Wednesday 8:00 PM

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = is_within_business_hours(test_time)
            assert result is False

    def test_is_within_business_hours_weekend(self):
        """Test is_within_business_hours on weekend."""
        test_time = datetime(2024, 1, 6, 10, 0, 0)  # Saturday 10:00 AM

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = False

            result = is_within_business_hours(test_time)
            assert result is False

    def test_is_within_business_hours_custom_hours(self):
        """Test is_within_business_hours with custom hours."""
        test_time = datetime(2024, 1, 3, 8, 0, 0)  # Wednesday 8:00 AM

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            # Custom hours: 8 AM - 6 PM
            result = is_within_business_hours(test_time, start_hour=8, end_hour=18)
            assert result is True

    def test_is_within_business_hours_none_time(self):
        """Test is_within_business_hours with None time uses now."""
        with patch('app.utils.date_helpers.datetime') as mock_datetime, \
             patch('app.utils.date_helpers.is_business_day') as mock_is_business:

            mock_now = Mock()
            mock_now.hour = 10
            mock_now.date.return_value = date(2024, 1, 3)
            mock_datetime.now.return_value = mock_now

            mock_is_business.return_value = True

            result = is_within_business_hours(None)
            assert result is True


class TestSchedulingHelpers:
    """Test scheduling helper functions."""

    def test_get_next_scheduled_time_with_template_loader(self):
        """Test get_next_scheduled_time with template loader."""
        with patch('app.utils.date_helpers.get_template_loader') as mock_loader:
            mock_config = Mock()
            mock_config.timing = {"start_hour": 9, "end_hour": 17}
            mock_config.frequency = "daily"
            mock_loader.return_value.get_flow_type_config.return_value = mock_config

            from_time = datetime(2024, 1, 3, 8, 0, 0)  # Wednesday 8:00 AM

            with patch('app.utils.date_helpers._get_next_daily_time') as mock_daily:
                mock_daily.return_value = datetime(2024, 1, 3, 9, 0, 0)

                result = get_next_scheduled_time("daily_flow", from_time)

                mock_daily.assert_called_once()
                assert result == datetime(2024, 1, 3, 9, 0, 0)

    def test_get_next_scheduled_time_no_config(self):
        """Test get_next_scheduled_time without config falls back to default."""
        with patch('app.utils.date_helpers.get_template_loader') as mock_loader, \
             patch('app.utils.date_helpers._get_default_next_time') as mock_default:

            mock_loader.return_value.get_flow_type_config.return_value = None
            mock_default.return_value = datetime(2024, 1, 4, 9, 0, 0)

            from_time = datetime(2024, 1, 3, 8, 0, 0)

            result = get_next_scheduled_time("unknown_flow", from_time)

            mock_default.assert_called_once_with(from_time, "America/Sao_Paulo")
            assert result == datetime(2024, 1, 4, 9, 0, 0)

    def test_get_next_scheduled_time_exception_handling(self):
        """Test get_next_scheduled_time handles exceptions."""
        with patch('app.utils.date_helpers.get_template_loader') as mock_loader, \
             patch('app.utils.date_helpers._get_default_next_time') as mock_default, \
             patch('app.utils.date_helpers.logger') as mock_logger:

            mock_loader.side_effect = Exception("Template loader error")
            mock_default.return_value = datetime(2024, 1, 4, 9, 0, 0)

            result = get_next_scheduled_time("error_flow")

            mock_logger.error.assert_called()
            mock_default.assert_called_once()

    def test_get_next_daily_time_before_business_hours(self):
        """Test _get_next_daily_time when current time is before business hours."""
        from_time = datetime(2024, 1, 3, 7, 0, 0)  # Wednesday 7:00 AM

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = _get_next_daily_time(from_time, 9, 17, "America/Sao_Paulo")

            expected = from_time.replace(hour=9, minute=0, second=0, microsecond=0)
            assert result == expected

    def test_get_next_daily_time_after_business_hours(self):
        """Test _get_next_daily_time when current time is after business hours."""
        from_time = datetime(2024, 1, 3, 19, 0, 0)  # Wednesday 7:00 PM

        with patch('app.utils.date_helpers.get_next_business_day') as mock_next_business:
            mock_next_business.return_value = date(2024, 1, 4)

            result = _get_next_daily_time(from_time, 9, 17, "America/Sao_Paulo")

            assert result.date() == date(2024, 1, 4)
            assert result.hour == 9

    def test_get_next_interval_time(self):
        """Test _get_next_interval_time calculation."""
        from_time = datetime(2024, 1, 3, 10, 0, 0)  # Wednesday

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = _get_next_interval_time(from_time, 2, 9, 17, "America/Sao_Paulo")

            expected_date = date(2024, 1, 5)  # Friday (2 days later)
            assert result.date() == expected_date
            assert result.hour == 9

    def test_get_next_interval_time_skip_weekends(self):
        """Test _get_next_interval_time skips weekends."""
        from_time = datetime(2024, 1, 5, 10, 0, 0)  # Friday

        def mock_is_business(check_date, timezone=None):
            # Saturday and Sunday are not business days
            return check_date.weekday() < 5

        with patch('app.utils.date_helpers.is_business_day', side_effect=mock_is_business):
            result = _get_next_interval_time(from_time, 2, 9, 17, "America/Sao_Paulo")

            # Should skip weekend and land on Monday
            assert result.date() == date(2024, 1, 8)  # Monday

    def test_get_next_monthly_time_same_month(self):
        """Test _get_next_monthly_time for next month."""
        from_time = datetime(2024, 1, 15, 10, 0, 0)

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = _get_next_monthly_time(from_time, 9, "America/Sao_Paulo")

            assert result.month == 2  # February
            assert result.day == 15
            assert result.hour == 9

    def test_get_next_monthly_time_december_rollover(self):
        """Test _get_next_monthly_time rollover from December."""
        from_time = datetime(2024, 12, 15, 10, 0, 0)

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = _get_next_monthly_time(from_time, 9, "America/Sao_Paulo")

            assert result.year == 2025  # Next year
            assert result.month == 1   # January
            assert result.day == 15

    def test_get_next_monthly_time_invalid_date_fallback(self):
        """Test _get_next_monthly_time with invalid date fallback."""
        from_time = datetime(2024, 1, 31, 10, 0, 0)  # January 31

        with patch('app.utils.date_helpers.is_business_day') as mock_is_business:
            mock_is_business.return_value = True

            result = _get_next_monthly_time(from_time, 9, "America/Sao_Paulo")

            # Should fall back to February 28 (no Feb 31)
            assert result.month == 2
            assert result.day == 28

    def test_get_default_next_time(self):
        """Test _get_default_next_time function."""
        from_time = datetime(2024, 1, 3, 15, 0, 0)  # Wednesday 3:00 PM

        with patch('app.utils.date_helpers.get_next_business_day') as mock_next_business:
            mock_next_business.return_value = date(2024, 1, 4)

            result = _get_default_next_time(from_time, "America/Sao_Paulo")

            assert result.date() == date(2024, 1, 4)
            assert result.hour == 9  # Default start hour

    def test_get_default_next_time_none_input(self):
        """Test _get_default_next_time with None input."""
        with patch('app.utils.date_helpers.datetime') as mock_datetime, \
             patch('app.utils.date_helpers.get_next_business_day') as mock_next_business:

            mock_datetime.now.return_value = datetime(2024, 1, 3, 15, 0, 0)
            mock_next_business.return_value = date(2024, 1, 4)

            result = _get_default_next_time(None, "America/Sao_Paulo")

            assert result.date() == date(2024, 1, 4)
            assert result.hour == 9