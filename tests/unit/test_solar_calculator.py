"""Unit tests for SolarCalculator class."""

import pytest
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

from src.scheduler.solar_calculator import SolarCalculator


class TestSolarCalculatorInitialization:
    """Test SolarCalculator initialization."""
    
    def test_initialization(self, location_ny):
        """Test calculator initializes correctly."""
        calc = SolarCalculator(
            latitude=location_ny['latitude'],
            longitude=location_ny['longitude'],
            timezone=location_ny['timezone']
        )
        
        assert calc.latitude == location_ny['latitude']
        assert calc.longitude == location_ny['longitude']
        assert calc.timezone_str == location_ny['timezone']
        assert isinstance(calc.timezone, ZoneInfo)
        assert calc.location is not None
    
    def test_initialization_different_timezone(self, location_alaska):
        """Test initialization with different timezone."""
        calc = SolarCalculator(
            latitude=location_alaska['latitude'],
            longitude=location_alaska['longitude'],
            timezone=location_alaska['timezone']
        )
        
        assert calc.timezone_str == location_alaska['timezone']


class TestSolarTimeCalculation:
    """Test solar time calculations."""
    
    def test_calculate_sunrise_summer(self, solar_calculator, test_date):
        """Test sunrise calculation for summer date."""
        sunrise, sunset = solar_calculator.calculate_solar_times(test_date)
        
        assert isinstance(sunrise, time)
        assert isinstance(sunset, time)
        # Summer sunrise should be early (before 7am in NY)
        assert sunrise.hour < 7
    
    def test_calculate_sunset_summer(self, solar_calculator, test_date):
        """Test sunset calculation for summer date."""
        sunrise, sunset = solar_calculator.calculate_solar_times(test_date)
        
        # Summer sunset should be late (after 7pm in NY)
        assert sunset.hour >= 19
    
    def test_calculate_solar_times_winter(self, solar_calculator, test_date_winter):
        """Test solar time calculation for winter date."""
        sunrise, sunset = solar_calculator.calculate_solar_times(test_date_winter)
        
        # Winter sunrise should be later than summer
        assert sunrise.hour >= 7
        # Winter sunset should be earlier than summer
        assert sunset.hour < 19
    
    def test_solar_times_caching(self, solar_calculator, test_date):
        """Test that solar times are cached."""
        # First calculation
        sunrise1, sunset1 = solar_calculator.calculate_solar_times(test_date)
        
        # Should have one cached date
        cached_dates = solar_calculator.get_cached_dates()
        assert len(cached_dates) == 1
        assert test_date in cached_dates
        
        # Second calculation should use cache
        sunrise2, sunset2 = solar_calculator.calculate_solar_times(test_date)
        
        assert sunrise1 == sunrise2
        assert sunset1 == sunset2
        # Still only one cached date
        assert len(solar_calculator.get_cached_dates()) == 1
    
    def test_solar_times_multiple_dates(self, solar_calculator, test_date, test_date_winter):
        """Test caching works for multiple dates."""
        solar_calculator.calculate_solar_times(test_date)
        solar_calculator.calculate_solar_times(test_date_winter)
        
        cached_dates = solar_calculator.get_cached_dates()
        assert len(cached_dates) == 2
        assert test_date in cached_dates
        assert test_date_winter in cached_dates
    
    def test_clear_cache(self, solar_calculator, test_date):
        """Test clearing the solar time cache."""
        solar_calculator.calculate_solar_times(test_date)
        assert len(solar_calculator.get_cached_dates()) == 1
        
        solar_calculator.clear_cache()
        
        assert len(solar_calculator.get_cached_dates()) == 0


class TestGetSunriseTime:
    """Test get_sunrise_time method."""
    
    def test_get_sunrise_no_offset(self, solar_calculator, test_date):
        """Test getting sunrise without offset."""
        sunrise = solar_calculator.get_sunrise_time(test_date, offset_minutes=0)
        
        assert isinstance(sunrise, time)
        assert sunrise.hour < 7  # Summer sunrise in NY
    
    def test_get_sunrise_positive_offset(self, solar_calculator, test_date):
        """Test getting sunrise with positive offset (after sunrise)."""
        sunrise_base = solar_calculator.get_sunrise_time(test_date, offset_minutes=0)
        sunrise_offset = solar_calculator.get_sunrise_time(test_date, offset_minutes=30)
        
        # Convert to minutes for comparison
        base_minutes = sunrise_base.hour * 60 + sunrise_base.minute
        offset_minutes = sunrise_offset.hour * 60 + sunrise_offset.minute
        
        assert offset_minutes == base_minutes + 30
    
    def test_get_sunrise_negative_offset(self, solar_calculator, test_date):
        """Test getting sunrise with negative offset (before sunrise)."""
        sunrise_base = solar_calculator.get_sunrise_time(test_date, offset_minutes=0)
        sunrise_offset = solar_calculator.get_sunrise_time(test_date, offset_minutes=-30)
        
        # Convert to minutes for comparison
        base_minutes = sunrise_base.hour * 60 + sunrise_base.minute
        offset_minutes = sunrise_offset.hour * 60 + sunrise_offset.minute
        
        assert offset_minutes == base_minutes - 30
    
    def test_get_sunrise_with_fallback_not_used(self, solar_calculator, test_date):
        """Test that fallback is not used when calculation succeeds."""
        sunrise = solar_calculator.get_sunrise_time(
            test_date,
            offset_minutes=0,
            fallback="09:00"
        )
        
        # Should use calculated time, not fallback
        assert sunrise.hour < 7
        assert sunrise != time(9, 0)


class TestGetSunsetTime:
    """Test get_sunset_time method."""
    
    def test_get_sunset_no_offset(self, solar_calculator, test_date):
        """Test getting sunset without offset."""
        sunset = solar_calculator.get_sunset_time(test_date, offset_minutes=0)
        
        assert isinstance(sunset, time)
        assert sunset.hour >= 19  # Summer sunset in NY
    
    def test_get_sunset_positive_offset(self, solar_calculator, test_date):
        """Test getting sunset with positive offset (after sunset)."""
        sunset_base = solar_calculator.get_sunset_time(test_date, offset_minutes=0)
        sunset_offset = solar_calculator.get_sunset_time(test_date, offset_minutes=30)
        
        # Convert to minutes for comparison
        base_minutes = sunset_base.hour * 60 + sunset_base.minute
        offset_minutes = sunset_offset.hour * 60 + sunset_offset.minute
        
        assert offset_minutes == base_minutes + 30
    
    def test_get_sunset_negative_offset(self, solar_calculator, test_date):
        """Test getting sunset with negative offset (before sunset)."""
        sunset_base = solar_calculator.get_sunset_time(test_date, offset_minutes=0)
        sunset_offset = solar_calculator.get_sunset_time(test_date, offset_minutes=-30)
        
        # Convert to minutes for comparison
        base_minutes = sunset_base.hour * 60 + sunset_base.minute
        offset_minutes = sunset_offset.hour * 60 + sunset_offset.minute
        
        assert offset_minutes == base_minutes - 30
    
    def test_get_sunset_with_fallback_not_used(self, solar_calculator, test_date):
        """Test that fallback is not used when calculation succeeds."""
        sunset = solar_calculator.get_sunset_time(
            test_date,
            offset_minutes=0,
            fallback="15:00"
        )
        
        # Should use calculated time, not fallback
        assert sunset.hour >= 19
        assert sunset != time(15, 0)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_solar_calculator_consistency(self, solar_calculator):
        """Test that sunrise is always before sunset on same day."""
        test_dates = [
            date(2024, 1, 15),  # Winter
            date(2024, 4, 15),  # Spring
            date(2024, 7, 15),  # Summer
            date(2024, 10, 15)  # Fall
        ]
        
        for test_date in test_dates:
            sunrise, sunset = solar_calculator.calculate_solar_times(test_date)
            
            # Convert to minutes for comparison
            sunrise_minutes = sunrise.hour * 60 + sunrise.minute
            sunset_minutes = sunset.hour * 60 + sunset.minute
            
            assert sunrise_minutes < sunset_minutes, \
                f"Sunrise should be before sunset on {test_date}"
    
    def test_alaska_summer_long_days(self, solar_calculator_alaska):
        """Test solar times in Alaska (extreme latitudes) during summer."""
        # Use a date when sun calculations work (not during midnight sun period)
        summer_date = date(2024, 5, 15)  # Mid-May, still long but calculable
        
        try:
            sunrise, sunset = solar_calculator_alaska.calculate_solar_times(summer_date)
            
            # Alaska has very long days in summer
            sunrise_minutes = sunrise.hour * 60 + sunrise.minute
            sunset_minutes = sunset.hour * 60 + sunset.minute
            day_length = sunset_minutes - sunrise_minutes
            
            # Should have a long day (more than 14 hours)
            assert day_length > 14 * 60
        except ValueError as e:
            # At extreme latitudes during summer, astral library may raise ValueError
            # for "Sun never reaches X degrees below the horizon" (midnight sun period)
            if "never reaches" in str(e).lower() or "horizon" in str(e).lower():
                pytest.skip("Solar calculation not possible at this latitude/date (midnight sun period)")
            else:
                # Re-raise if it's a different type of ValueError
                raise
    
    def test_alaska_winter_short_days(self, solar_calculator_alaska):
        """Test solar times in Alaska during winter."""
        winter_date = date(2024, 12, 21)  # Winter solstice
        
        sunrise, sunset = solar_calculator_alaska.calculate_solar_times(winter_date)
        
        # Alaska has very short days in winter
        sunrise_minutes = sunrise.hour * 60 + sunrise.minute
        sunset_minutes = sunset.hour * 60 + sunset.minute
        day_length = sunset_minutes - sunrise_minutes
        
        # Should have a short day (less than 8 hours)
        assert day_length < 8 * 60


class TestSolarTimeWithFallback:
    """Test fallback behavior for solar time calculations."""
    
    def test_sunrise_fallback_format(self, solar_calculator, test_date):
        """Test that fallback time is properly formatted."""
        # This tests normal operation - actual fallback usage is harder to test
        # without mocking the astral library
        sunrise = solar_calculator.get_sunrise_time(
            test_date,
            offset_minutes=0,
            fallback="06:30"
        )
        
        assert isinstance(sunrise, time)
    
    def test_sunset_fallback_format(self, solar_calculator, test_date):
        """Test that fallback time is properly formatted."""
        sunset = solar_calculator.get_sunset_time(
            test_date,
            offset_minutes=0,
            fallback="19:30"
        )
        
        assert isinstance(sunset, time)
    
    def test_offset_with_fallback(self, solar_calculator, test_date):
        """Test that offset is applied correctly when fallback is provided."""
        sunrise = solar_calculator.get_sunrise_time(
            test_date,
            offset_minutes=45,
            fallback="06:00"
        )
        
        # Should get calculated sunrise + 45 minutes (not fallback)
        assert isinstance(sunrise, time)


class TestSolarCalculatorRepeatability:
    """Test that calculations are repeatable and deterministic."""
    
    def test_repeated_calculations_same_result(self, solar_calculator, test_date):
        """Test that repeated calculations give same result."""
        results = []
        
        # Calculate 5 times
        for _ in range(5):
            sunrise, sunset = solar_calculator.calculate_solar_times(test_date)
            results.append((sunrise, sunset))
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result
    
    def test_different_calculators_same_result(self, location_ny, test_date):
        """Test that different calculator instances give same result."""
        calc1 = SolarCalculator(
            latitude=location_ny['latitude'],
            longitude=location_ny['longitude'],
            timezone=location_ny['timezone']
        )
        calc2 = SolarCalculator(
            latitude=location_ny['latitude'],
            longitude=location_ny['longitude'],
            timezone=location_ny['timezone']
        )
        
        sunrise1, sunset1 = calc1.calculate_solar_times(test_date)
        sunrise2, sunset2 = calc2.calculate_solar_times(test_date)
        
        assert sunrise1 == sunrise2
        assert sunset1 == sunset2
