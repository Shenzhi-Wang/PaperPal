"""
Natural language time parsing module
Supports parsing various time range descriptions
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import dateparser
from dateutil.relativedelta import relativedelta

import config


class TimeParser:
    """Natural language time parser"""
    
    # Predefined time range patterns
    PREDEFINED_PATTERNS = {
        # Chinese patterns (longer patterns first!)
        r"最近一天|今天|当天": ("days", 1),
        r"最近两天|前两天": ("days", 2),
        r"最近三天|前三天|近三天": ("days", 3),
        r"最近一周|这周|本周|过去一周": ("weeks", 1),
        r"最近两周|前两周|过去两周": ("weeks", 2),
        r"最近一个月|这个月|本月|过去一个月": ("months", 1),
        r"最近两个月|前两个月": ("months", 2),
        r"最近三个月|这个季度": ("months", 3),
        r"最近半年|过去半年": ("months", 6),
        r"最近一年|今年|过去一年": ("years", 1),
        # Single time words (default to week for "最近"/"recent")
        r"^最近$|^过去$|^近期$": ("weeks", 1),
        
        # English patterns
        r"today|last day|past day": ("days", 1),
        r"last 2 days|past 2 days": ("days", 2),
        r"last 3 days|past 3 days": ("days", 3),
        r"this week|last week|past week": ("weeks", 1),
        r"last 2 weeks|past 2 weeks": ("weeks", 2),
        r"this month|last month|past month": ("months", 1),
        r"last 2 months|past 2 months": ("months", 2),
        r"last 3 months|past 3 months|this quarter": ("months", 3),
        r"last 6 months|past 6 months|half year": ("months", 6),
        r"this year|last year|past year": ("years", 1),
        # Single time words (default to week)
        r"^recent$|^recently$": ("weeks", 1),
    }
    
    # Number patterns - Chinese (Updated to support Chinese characters for numbers)
    CHINESE_NUMBER_PATTERNS = {
        r"最近([0-9一二三四五六七八九十]+)天|过去([0-9一二三四五六七八九十]+)天|前([0-9一二三四五六七八九十]+)天": "days",
        r"最近([0-9一二三四五六七八九十]+)周|过去([0-9一二三四五六七八九十]+)周|前([0-9一二三四五六七八九十]+)周": "weeks",
        r"最近([0-9一二三四五六七八九十]+)个?月|过去([0-9一二三四五六七八九十]+)个?月|前([0-9一二三四五六七八九十]+)个?月": "months",
        r"最近([0-9一二三四五六七八九十]+)年|过去([0-9一二三四五六七八九十]+)年": "years",
    }
    
    # Number patterns - English
    ENGLISH_NUMBER_PATTERNS = {
        r"last (\d+) days?|past (\d+) days?": "days",
        r"last (\d+) weeks?|past (\d+) weeks?": "weeks",
        r"last (\d+) months?|past (\d+) months?": "months",
        r"last (\d+) years?|past (\d+) years?": "years",
    }
    
    def __init__(self):
        self.now = datetime.now()
    
    def parse(self, time_str: str) -> Tuple[datetime, datetime]:
        """
        Parse time range string
        
        Args:
            time_str: Time range description, e.g., "last week", "from 2024-01-01 to 2024-01-31"
            
        Returns:
            (start_date, end_date) tuple
        """
        time_str = time_str.strip().lower()
        self.now = datetime.now()  # Update current time
        
        # First check if it's a predefined shortcut
        if time_str in config.DEFAULT_TIME_RANGES:
            return self._parse_shortcut(time_str)
        
        # Try parsing predefined patterns
        result = self._parse_predefined(time_str)
        if result:
            return result
        
        # Try parsing number patterns
        result = self._parse_number_pattern(time_str)
        if result:
            return result
        
        # Try parsing date range (from...to...)
        result = self._parse_date_range(time_str)
        if result:
            return result
        
        # Try parsing with dateparser
        result = self._parse_with_dateparser(time_str)
        if result:
            return result
        
        # Default to last day
        return self._get_relative_range("days", 1)

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a YYYY-MM-DD string into datetime"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return None
    
    def _chinese_to_int(self, char_str: str) -> int:
        """Convert basic Chinese number characters to integer"""
        if char_str.isdigit():
            return int(char_str)
        
        cn_num = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        return cn_num.get(char_str, 1)

    def _parse_shortcut(self, shortcut: str) -> Tuple[datetime, datetime]:
        """Parse predefined shortcuts"""
        mapping = {
            "today": ("days", 1),
            "3days": ("days", 3),
            "week": ("weeks", 1),
            "2weeks": ("weeks", 2),
            "month": ("months", 1),
        }
        unit, value = mapping.get(shortcut, ("days", 1))
        return self._get_relative_range(unit, value)
    
    def _parse_predefined(self, time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse predefined patterns"""
        for pattern, (unit, value) in self.PREDEFINED_PATTERNS.items():
            if re.search(pattern, time_str, re.IGNORECASE):
                return self._get_relative_range(unit, value)
        return None
    
    def _parse_number_pattern(self, time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse number patterns"""
        all_patterns = {**self.CHINESE_NUMBER_PATTERNS, **self.ENGLISH_NUMBER_PATTERNS}
        
        for pattern, unit in all_patterns.items():
            match = re.search(pattern, time_str, re.IGNORECASE)
            if match:
                # Get matched number from any group
                groups = match.groups()
                value_str = next((g for g in groups if g), None)
                if value_str:
                    value = self._chinese_to_int(value_str)
                    return self._get_relative_range(unit, value)
        return None
    
    def _parse_date_range(self, time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse date range, e.g., 'from 2024-01-01 to 2024-01-31'"""
        # Chinese patterns
        cn_pattern = r"从?\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)\s*[到至-]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)"
        # English patterns
        en_pattern = r"from\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+to\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
        # Simple date range
        simple_pattern = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*[-~到至]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
        
        for pattern in [cn_pattern, en_pattern, simple_pattern]:
            match = re.search(pattern, time_str, re.IGNORECASE)
            if match:
                start_str, end_str = match.groups()
                start_date = self._parse_single_date(start_str)
                end_date = self._parse_single_date(end_str)
                if start_date and end_date:
                    # Ensure end_date includes full day
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                    return start_date, end_date
        
        return None
    
    def _parse_single_date(self, date_str: str) -> Optional[datetime]:
        """Parse single date string"""
        # Standardize date string
        date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
        
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try using dateparser
        parsed = dateparser.parse(date_str)
        return parsed
    
    def _parse_with_dateparser(self, time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse using dateparser library"""
        # Try parsing as relative time
        parsed = dateparser.parse(
            time_str,
            settings={
                'PREFER_DATES_FROM': 'past',
                'RELATIVE_BASE': self.now,
            }
        )
        
        if parsed:
            # If successfully parsed, return range from parsed date to now
            return parsed, self.now
        
        return None
    
    def _get_relative_range(self, unit: str, value: int) -> Tuple[datetime, datetime]:
        """Get relative time range"""
        end_date = self.now
        
        if unit == "days":
            start_date = end_date - timedelta(days=value)
        elif unit == "weeks":
            start_date = end_date - timedelta(weeks=value)
        elif unit == "months":
            start_date = end_date - relativedelta(months=value)
        elif unit == "years":
            start_date = end_date - relativedelta(years=value)
        else:
            start_date = end_date - timedelta(days=1)
        
        return start_date, end_date
    
    def get_available_shortcuts(self) -> dict[str, str]:
        """Get available shortcuts"""
        return config.DEFAULT_TIME_RANGES.copy()


# Helper function
def parse_time_range(time_str: str) -> Tuple[datetime, datetime]:
    """Helper function to parse time range"""
    parser = TimeParser()
    return parser.parse(time_str)
