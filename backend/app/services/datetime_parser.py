from datetime import datetime, timedelta
import re
from dateutil import parser
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)

def parse_natural_language_datetime(text):
    """
    Parse natural language datetime expressions.
    Returns a dictionary with the parsing results including success status,
    extracted date/time, and whether it's an all-day event.
    """
    text = text.lower().strip()
    now = datetime.now()
    is_all_day = False
    
    # Check for "all day" markers
    if re.search(r'\b(all[- ]?day|full[- ]?day)\b', text):
        is_all_day = True
    
    # Day/date detection - enhanced with more patterns
    if 'tomorrow' in text:
        base_date = now + timedelta(days=1)
    elif 'today' in text:
        base_date = now
    elif 'day after tomorrow' in text:
        base_date = now + timedelta(days=2)
    elif re.search(r'next\s+monday', text, re.IGNORECASE):
        days_ahead = (7 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # If today is Monday, go to next Monday
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+tuesday', text, re.IGNORECASE):
        days_ahead = (8 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+wednesday', text, re.IGNORECASE):
        days_ahead = (9 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+thursday', text, re.IGNORECASE):
        days_ahead = (10 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+friday', text, re.IGNORECASE):
        days_ahead = (11 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+saturday', text, re.IGNORECASE):
        days_ahead = (12 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'next\s+sunday', text, re.IGNORECASE):
        days_ahead = (13 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = now + timedelta(days=days_ahead)
    elif re.search(r'this\s+weekend', text, re.IGNORECASE):
        # Assume this weekend means the upcoming Saturday
        days_ahead = (5 - now.weekday()) % 7
        base_date = now + timedelta(days=days_ahead)
    elif 'next week' in text:
        base_date = now + timedelta(weeks=1)
    elif 'next month' in text:
        base_date = now + relativedelta(months=1)
    else:
        try:
            base_date = parser.parse(text, fuzzy=True)
        except Exception as e:
            logger.warning(f"Failed to parse date with dateutil: {e}")
            base_date = now
    
    # Time detection with enhanced patterns
    time_found = False
    
    # Look for time ranges (start and end time)
    time_range_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)?\s*(?:to|until|till|-)\s*(\d{1,2}):(\d{2})\s*(am|pm)?',
        r'(\d{1,2})\s*(am|pm)\s*(?:to|until|till|-)\s*(\d{1,2})\s*(am|pm)',
        r'from\s*(\d{1,2}):(\d{2})\s*(am|pm)?\s*(?:to|until|till|-)\s*(\d{1,2}):(\d{2})\s*(am|pm)?',
        r'from\s*(\d{1,2})\s*(am|pm)\s*(?:to|until|till|-)\s*(\d{1,2})\s*(am|pm)'
    ]
    
    end_datetime = None
    
    for pattern in time_range_patterns:
        match = re.search(pattern, text)
        if match:
            time_found = True
            groups = match.groups()
            
            # Process start time
            if len(groups) == 6:  # Full pattern with hours:minutes for both start and end
                start_hour = int(groups[0])
                start_minute = int(groups[1])
                start_ampm = groups[2]
                
                end_hour = int(groups[3])
                end_minute = int(groups[4])
                end_ampm = groups[5]
                
                # Handle AM/PM for start time
                if start_ampm and start_ampm.lower() == 'pm' and start_hour != 12:
                    start_hour += 12
                elif start_ampm and start_ampm.lower() == 'am' and start_hour == 12:
                    start_hour = 0
                
                # Handle AM/PM for end time
                if end_ampm and end_ampm.lower() == 'pm' and end_hour != 12:
                    end_hour += 12
                elif end_ampm and end_ampm.lower() == 'am' and end_hour == 12:
                    end_hour = 0
                    
            elif len(groups) == 4:  # Hours only pattern
                start_hour = int(groups[0])
                start_minute = 0
                start_ampm = groups[1]
                
                end_hour = int(groups[2])
                end_minute = 0
                end_ampm = groups[3]
                
                # Handle AM/PM for start time
                if start_ampm and start_ampm.lower() == 'pm' and start_hour != 12:
                    start_hour += 12
                elif start_ampm and start_ampm.lower() == 'am' and start_hour == 12:
                    start_hour = 0
                
                # Handle AM/PM for end time
                if end_ampm and end_ampm.lower() == 'pm' and end_hour != 12:
                    end_hour += 12
                elif end_ampm and end_ampm.lower() == 'am' and end_hour == 12:
                    end_hour = 0
            
            # Set the start date/time
            base_date = base_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            
            # Set the end date/time
            end_datetime = base_date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            
            # If end time is earlier than start time, assume it's on the next day
            if end_datetime < base_date:
                end_datetime += timedelta(days=1)
                
            break
    
    # If no time range found, look for single time
    if not time_found:
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',
            r'(\d{1,2})\s*(am|pm)',
            r'at\s*(\d{1,2}):(\d{2})',
            r'at\s*(\d{1,2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                time_found = True
                groups = match.groups()
                
                if len(groups) == 3:  # HH:MM AM/PM
                    hour = int(groups[0])
                    minute = int(groups[1])
                    ampm = groups[2]
                    
                    if ampm and ampm.lower() == 'pm' and hour != 12:
                        hour += 12
                    elif ampm and ampm.lower() == 'am' and hour == 12:
                        hour = 0
                        
                elif len(groups) == 2:
                    if groups[1] in ['am', 'pm']:  # HH AM/PM
                        hour = int(groups[0])
                        minute = 0
                        ampm = groups[1]
                        
                        if ampm.lower() == 'pm' and hour != 12:
                            hour += 12
                        elif ampm.lower() == 'am' and hour == 12:
                            hour = 0
                    else:  # HH:MM (no AM/PM)
                        hour = int(groups[0])
                        minute = int(groups[1])
                
                base_date = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Default end time is 1 hour later
                end_datetime = base_date + timedelta(hours=1)
                break
    
    # If no time specification found and it's not explicitly an all-day event
    if not time_found and not is_all_day:
        # If there are day-related keywords but no time, make it an all-day event
        day_keywords = ['tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 
                      'thursday', 'friday', 'saturday', 'sunday', 'next week', 'weekend']
        
        if any(keyword in text.lower() for keyword in day_keywords):
            is_all_day = True
            # Set time to beginning of day
            base_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
            # No end time for all-day events
            end_datetime = None
    
    # Build and return the result structure
    result = {
        'success': True,
        'is_all_day': is_all_day
    }
    
    if is_all_day:
        result['start_date'] = base_date.date()
    else:
        result['start_datetime'] = base_date
        if end_datetime:
            result['end_datetime'] = end_datetime
            
    return result

# Test function
if __name__ == "__main__":
    test_cases = [
        "Schedule a meeting tomorrow at 3pm",
        "Create a doctor's appointment on Friday at 10am",
        "Add a team lunch next Tuesday from 12pm to 1:30pm",
        "Schedule an all-day conference on August 15",
        "Meeting with John at 2:30pm today"
    ]
    
    for case in test_cases:
        result = parse_natural_language_datetime(case)
        print(f"Input: {case}")
        print(f"Result: {result}")
        print()
