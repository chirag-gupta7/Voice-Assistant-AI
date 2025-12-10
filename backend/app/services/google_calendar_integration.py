import os
import pickle
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from dateutil import parser
from dateutil.relativedelta import relativedelta
import logging

# Import our improved datetime parser and event creator
# Comment these imports for now as we'll update the functions directly
# from .datetime_parser import parse_natural_language_datetime
# from .calendar_event_parser import create_event_manual_parse

logger = logging.getLogger(__name__)

# Define the scope for read-only access to calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- Corrected Code: Build absolute paths to the backend directory ---
# services -> app -> backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
# ---

# Global variable to hold the authenticated service object
# This will be managed by the Flask app context for efficiency
_cached_calendar_service = None

def authenticate_google_calendar():
    """
    Authenticate and return Google Calendar service object.
    This handles the OAuth flow and token management.
    This function should ideally be called once and its result cached.
    """
    creds = None
    
    # Check if we have stored credentials using the absolute path
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            logger.error(f"Error loading token.pickle: {e}")
            creds = None # Force re-authentication

    # If there are no valid credentials available, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Google Calendar credentials refreshed.")
            except Exception as e:
                logger.error(f"Error refreshing Google Calendar credentials: {e}")
                # Delete the token file and re-authenticate
                if os.path.exists(TOKEN_PATH):
                    os.remove(TOKEN_PATH)
                    logger.warning("Deleted expired/invalid token.pickle to force re-authentication.")
                creds = None
        
        if not creds:
            # Check for credentials.json using the absolute path
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "credentials.json not found. Please place it in the 'backend' directory."
                )
            
            logger.info("Initiating full Google Calendar OAuth flow...")
            # Load credentials from the absolute path
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Google Calendar OAuth flow completed successfully.")
        
        # Save credentials for future use using the absolute path
        try:
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)
            logger.info("Google Calendar token saved to token.pickle.")
        except Exception as e:
            logger.error(f"Error saving token.pickle: {e}")

    return build('calendar', 'v3', credentials=creds)

def get_calendar_service():
    """
    Provides the authenticated Google Calendar service object.
    Caches the service object for efficiency.
    """
    global _cached_calendar_service
    if _cached_calendar_service is None:
        logger.info("Google Calendar service not cached, authenticating now...")
        _cached_calendar_service = authenticate_google_calendar()
        logger.info("Google Calendar service cached.")
    return _cached_calendar_service

def get_today_schedule():
    """
    Get today's schedule from Google Calendar.
    Returns a formatted string with today's events.
    """
    try:
        # Use the cached service
        service = get_calendar_service()
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat() + 'Z',
            timeMax=today_end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "No events scheduled for today"
        
        schedule_items = []
        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = start_time.strftime('%H:%M')
            else:
                time_str = 'All day'
            
            location = event.get('location', '')
            location_str = f" at {location}" if location else ""
            
            schedule_items.append(f"{summary} at {time_str}{location_str}")
        
        return "; ".join(schedule_items)
    
    except HttpError as error:
        logger.error(f"An HTTP error occurred with Google Calendar API: {error}")
        return "Unable to fetch calendar events"
    except Exception as error:
        logger.error(f"An unexpected error occurred while fetching calendar events: {error}")
        return "Unable to fetch calendar events"

def get_upcoming_events(days_ahead=7):
    """
    Get upcoming events for the next specified number of days.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        end_time = now + timedelta(days=days_ahead)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_time.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"No events scheduled for the next {days_ahead} days"
        
        schedule_items = []
        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime', event['start'].get('date'))
            
            if 'T' in start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                date_str = start_time.strftime('%Y-%m-%d')
                time_str = start_time.strftime('%H:%M')
                schedule_items.append(f"{summary} on {date_str} at {time_str}")
            else:
                schedule_items.append(f"{summary} on {start} (All day)")
        
        return "; ".join(schedule_items)
    
    except Exception as error:
        logger.error(f"An error occurred while fetching upcoming events: {error}")
        return "Unable to fetch upcoming events"

def get_next_meeting():
    """Get the next upcoming meeting."""
    try:
        service = get_calendar_service() # Use the cached service
        now = datetime.utcnow()
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            maxResults=1,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return {
                'event': {},
                'formatted_time': '',
                'message': "No upcoming meetings"
            }
        
        event = events[0]
        summary = event.get('summary', 'Untitled Event')
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        if 'T' in start:
            start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
            time_str = start_time.strftime('%H:%M on %B %d')
        else:
            time_str = f"All day on {start}"
        
        # Return a structured object instead of a string
        location = event.get('location', '')
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        if 'T' in end:
            end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
        else:
            end_time = None
            
        result = {
            'event': {
                'summary': summary,
                'start_time': start,
                'end_time': end,
                'location': location,
                'id': event.get('id', ''),
                'html_link': event.get('htmlLink', '')
            },
            'formatted_time': time_str,
            'message': f"Next meeting: {summary} at {time_str}"
        }
        
        return result
    
    except Exception as error:
        logger.error(f"An error occurred while fetching next meeting: {error}")
        return {
            'event': {},
            'formatted_time': '',
            'message': "Unable to fetch next meeting due to an error"
        }

def get_free_time_today():
    """Find free time slots in today's schedule."""
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start.isoformat() + 'Z',
            timeMax=today_end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return "You have the whole day free!"
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')
            
            if start and end:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
                busy_times.append((start_time, end_time))
        
        if not busy_times:
            return "No timed events today, mostly free!"
        
        busy_times.sort(key=lambda x: x[0])
        
        free_slots = []
        current_time = now
        
        for start, end in busy_times:
            if current_time < start:
                duration = start - current_time
                if duration.total_seconds() > 3600: # Only consider slots longer than 1 hour
                    free_slots.append(f"{current_time.strftime('%H:%M')} - {start.strftime('%H:%M')}")
            current_time = max(current_time, end)
        
        # Check for free time after the last event until end of day (e.g., 5 PM work day end)
        end_of_work_day = today_start.replace(hour=17, minute=0, second=0, microsecond=0)
        if current_time < end_of_work_day:
            duration = end_of_work_day - current_time
            if duration.total_seconds() > 3600:
                free_slots.append(f"{current_time.strftime('%H:%M')} - {end_of_work_day.strftime('%H:%M')}")


        if free_slots:
            return f"Free time slots: {'; '.join(free_slots)}"
        else:
            return "No significant free time slots found today"
    
    except Exception as error:
        logger.error(f"An error occurred while getting free time: {error}")
        return "Unable to calculate free time"

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

# --- NEW FUNCTION: create_event_manual_parse ---
def create_event_manual_parse(conversation_text):
    """
    Manually parses conversation text to create a calendar event.
    This is a fallback if quickAdd fails.
    Returns a structured dictionary with success status and event details.
    """
    logger.info(f"Attempting manual parse for event: {conversation_text}")
    summary = "Untitled Event"
    
    # Simple regex to find common patterns for event summary
    # This regex is improved to be more robust
    summary_match = re.search(r'(?:schedule|create|add)\s+(?:a\s+)?(.+?)(?:\s+(?:on|at|for|from)\s+.*|$)', conversation_text, re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip()
        # Clean up summary if it contains time/date phrases that were part of the summary extraction
        # This is a heuristic and might need further refinement based on user input patterns
        summary = re.sub(r'(?:tomorrow|today|next week|next month|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|on \w+ \d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?::\d{2})?\s*(?:am|pm)?).*', '', summary, flags=re.IGNORECASE).strip()
        if not summary: # Fallback if regex removed everything
            summary = "New Event"
    else:
        # If no clear summary found, use the whole text or a default
        summary = conversation_text.split(' for ')[0].strip() if ' for ' in conversation_text else "New Event"
        if len(summary) > 100: # Prevent very long summaries
            summary = summary[:100] + "..."

    # Try to parse date/time from the text using the enhanced function
    datetime_result = parse_natural_language_datetime(conversation_text)
    
    if not datetime_result.get('success', True):  # Default to True if 'success' key isn't present
        logger.warning(f"Failed to parse date/time information: {datetime_result.get('error', 'Unknown error')}")
        return {
            'success': False, 
            'error': 'Could not understand the date and time for this event',
            'message': f"❌ Could not understand when this event should be scheduled. Please try again with a clearer date and time."
        }
    
    # Format the event based on the extracted information
    try:
        service = get_calendar_service()
        
        if datetime_result.get('is_all_day', False):
            # Create all-day event
            start_date = datetime_result.get('start_date')
            event = {
                'summary': summary,
                'start': {
                    'date': start_date.strftime('%Y-%m-%d'),
                },
                'end': {
                    'date': (start_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                },
                'description': conversation_text
            }
            
            created_event = service.events().insert(calendarId='primary', body=event).execute()
            
            date_str = start_date.strftime('%B %d, %Y')
            
            result = {
                'success': True,
                'event': {
                    'id': created_event.get('id'),
                    'summary': summary,
                    'htmlLink': created_event.get('htmlLink', ''),
                    'date': date_str,
                    'is_all_day': True
                },
                'message': f"✅ All-day event created: '{summary}' on {date_str}"
            }
            
            return result
        else:
            # Create timed event
            start_time = datetime_result.get('start_datetime')
            
            # If end time is specified in the datetime_result, use it
            # Otherwise default to 1 hour after start time
            if 'end_datetime' in datetime_result:
                end_time = datetime_result.get('end_datetime')
            else:
                end_time = start_time + timedelta(hours=1)
            
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'description': conversation_text
            }
            
            created_event = service.events().insert(calendarId='primary', body=event).execute()
            
            # Create response dictionary
            date_str = start_time.strftime('%B %d, %Y')
            start_str = start_time.strftime('%I:%M %p')
            end_str = end_time.strftime('%I:%M %p')
            
            result = {
                'success': True,
                'event': {
                    'id': created_event.get('id'),
                    'summary': summary,
                    'htmlLink': created_event.get('htmlLink', ''),
                    'date': date_str,
                    'start_time': start_str,
                    'end_time': end_str,
                    'is_all_day': False
                },
                'message': f"✅ Event created: '{summary}' on {date_str} from {start_str} to {end_str}"
            }
            
            return result
        
    except Exception as e:
        logger.error(f"Error in manual event parsing: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': f"❌ Failed to create event: {str(e)}"
        }

# --- END NEW FUNCTION ---

# --- Moved create_event_from_conversation here (before __main__ block) ---
def create_event_from_conversation(conversation_text):
    """
    Create a calendar event from natural language conversation text.
    Returns a structured dictionary with success status and event details.
    """
    try:
        service = get_calendar_service() # Use the cached service
        text = conversation_text.strip()
        
        try:
            event = service.events().quickAdd(
                calendarId='primary',
                text=text
            ).execute()
            
            summary = event.get('summary', 'Event')
            start_info = event.get('start', {})
            end_info = event.get('end', {})
            
            result = {
                'success': True,
                'event': {
                    'id': event.get('id'),
                    'summary': summary,
                    'htmlLink': event.get('htmlLink', '')
                }
            }
            
            if start_info.get('dateTime'):
                start_time = datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00'))
                date_str = start_time.strftime('%B %d, %Y')
                start_time_str = start_time.strftime('%I:%M %p')
                
                # Format end time if available
                end_time_str = None
                if end_info.get('dateTime'):
                    end_time = datetime.fromisoformat(end_info['dateTime'].replace('Z', '+00:00'))
                    end_time_str = end_time.strftime('%I:%M %p')
                
                result['event'].update({
                    'date': date_str,
                    'start_time': start_time_str,
                    'end_time': end_time_str or (start_time + timedelta(hours=1)).strftime('%I:%M %p'),
                    'is_all_day': False
                })
                
                result['message'] = f"✅ Event created: '{summary}' on {date_str} from {start_time_str}"
                
            elif start_info.get('date'):
                date_str = start_info['date']
                result['event'].update({
                    'date': date_str,
                    'is_all_day': True
                })
                result['message'] = f"✅ All-day event created: '{summary}' on {date_str}"
            else:
                result['message'] = f"✅ Event created: '{summary}'"
                
            return result
                
        except HttpError as error:
            if error.resp.status == 400:
                logger.warning(f"Google QuickAdd failed, attempting manual parse: {error}")
                return create_event_manual_parse(text)
            else:
                raise error
                
    except Exception as error:
        logger.error(f"Error creating event from conversation: {error}")
        return {
            'success': False,
            'error': str(error),
            'message': f"❌ Error creating event: {error}"
        }
# --- End of moved create_event_from_conversation ---

# Use our new function for manual parsing
def create_event_manual_parse(conversation_text):
    """
    Manually parses conversation text to create a calendar event.
    This is a fallback if quickAdd fails.
    Returns a structured dictionary with success status and event details.
    """
    # Call our standalone implementation that uses the improved datetime parser
    from .calendar_event_parser import create_event_manual_parse as improved_parser
    return improved_parser(conversation_text, get_calendar_service)

def create_event(summary, start_time, end_time, description=None, location=None):
    """
    Create a new calendar event.
    Returns a structured dictionary with success status and event details.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        event = {
            'summary': summary,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }
        
        if description:
            event['description'] = description
        if location:
            event['location'] = location
        
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        
        date_str = start_time.strftime('%B %d, %Y')
        start_str = start_time.strftime('%I:%M %p')
        end_str = end_time.strftime('%I:%M %p')
        
        result = {
            'success': True,
            'event': {
                'id': event_result.get('id'),
                'summary': summary,
                'htmlLink': event_result.get('htmlLink', ''),
                'date': date_str,
                'start_time': start_str,
                'end_time': end_str,
                'is_all_day': False
            },
            'message': f"✅ Event created: '{summary}' on {date_str} from {start_str} to {end_str}"
        }
        
        return result
    
    except Exception as error:
        logger.error(f"Error creating event: {error}")
        return {
            'success': False,
            'error': str(error),
            'message': f"❌ Error creating event: {error}"
        }

def reschedule_event(event_id, new_start_time_iso):
    """
    Reschedule an existing event to a new time.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        new_start_time = parser.isoparse(new_start_time_iso)
        
        original_start = parser.isoparse(event['start']['dateTime'])
        original_end = parser.isoparse(event['end']['dateTime'])
        duration = original_end - original_start
        new_end_time = new_start_time + duration
        
        event['start']['dateTime'] = new_start_time.isoformat()
        event['end']['dateTime'] = new_end_time.isoformat()

        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        
        time_str = new_start_time.strftime('%B %d, %Y at %I:%M %p')
        return f"✅ Event '{updated_event['summary']}' rescheduled to {time_str}."
    except Exception as error:
        logger.error(f"Error rescheduling event: {error}")
        return f"❌ Error rescheduling event: {error}"

def cancel_event(event_id):
    """
    Cancel a calendar event.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        summary = event.get('summary', 'Unknown Event')

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        return f"✅ Event '{summary}' has been canceled."
    except HttpError as error:
        if error.resp.status == 410:
            return "✅ Event has already been canceled."
        logger.error(f"HTTP error canceling event: {error}")
        return f"❌ Error canceling event: {error}"
    except Exception as error:
        logger.error(f"An unexpected error occurred canceling event: {error}")
        return f"❌ Error canceling event: {error}"

def find_meeting_slots(duration_minutes, participants_str, days_ahead=7):
    """
    Find available meeting slots considering all participants' calendars.
    """
    try:
        service = get_calendar_service() # Use the cached service
        
        now = datetime.utcnow()
        time_min_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        time_max_dt = now + timedelta(days=days_ahead)
        
        participants = [p.strip() for p in participants_str.split(',') if p.strip()]
        if 'primary' not in participants:
            participants.append('primary')

        freebusy_query = {
            "timeMin": time_min_dt.isoformat() + 'Z',
            "timeMax": time_max_dt.isoformat() + 'Z',
            "items": [{"id": p} for p in participants],
        }
        
        freebusy_result = service.freebusy().query(body=freebusy_query).execute()
        
        busy_slots = []
        for cal_id, data in freebusy_result['calendars'].items():
            busy_slots.extend(data['busy'])
            
        if not busy_slots:
            return ["Everyone is free for the next 7 days during work hours."]

        busy_times = sorted([(parser.isoparse(slot['start']), parser.isoparse(slot['end'])) for slot in busy_slots])
        
        merged_busy = []
        if busy_times:
            current_start, current_end = busy_times[0]
            for next_start, next_end in busy_times[1:]:
                if next_start < current_end:
                    current_end = max(current_end, next_end)
                else:
                    merged_busy.append((current_start, current_end))
                    current_start, current_end = next_start, next_end
            merged_busy.append((current_start, current_end))

        free_slots = []
        search_time = time_min_dt
        duration = timedelta(minutes=duration_minutes)

        while search_time < time_max_dt and len(free_slots) < 5:
            if search_time.hour >= 17: # End searching at 5 PM
                search_time = (search_time + timedelta(days=1)).replace(hour=9, minute=0) # Start next day at 9 AM
                continue
            if search_time.hour < 9: # Start searching from 9 AM
                search_time = search_time.replace(hour=9, minute=0)
                continue

            potential_end_time = search_time + duration
            is_free = True
            for busy_start, busy_end in merged_busy:
                # Check for overlap
                if max(search_time, busy_start) < min(potential_end_time, busy_end):
                    is_free = False
                    search_time = busy_end # Move search time past the busy slot
                    break
            
            if is_free:
                free_slots.append(search_time.strftime('%A, %b %d at %I:%M %p'))
                search_time += timedelta(minutes=30) # Move to next potential slot
            
        return free_slots if free_slots else ["No common slots found."]

    except Exception as error:
        logger.error(f"Error finding meeting slots: {error}")
        return [f"❌ Error finding slots: {error}"]

def set_event_reminder(event_id, minutes_before):
    """
    Set a custom reminder for an event.
    """
    try:
        service = get_calendar_service() # Use the cached service
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        event['reminders'] = {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': minutes_before},
                {'method': 'email', 'minutes': minutes_before},
            ],
        }

        updated_event = service.events().update(
            calendarId='primary', eventId=event_id, body=event
        ).execute()

        return f"✅ Reminder set for '{updated_event['summary']}' ({minutes_before} minutes before)."
    except Exception as error:
        logger.error(f"Error setting reminder: {error}")
        return f"❌ Error setting reminder: {error}"

def test_calendar_connection():
    """
    Test the calendar connection and print some basic info.
    """
    try:
        service = get_calendar_service()
        
        calendar = service.calendars().get(calendarId='primary').execute()
        print(f"Successfully connected to calendar: {calendar['summary']}")
        
        return service
    except Exception as error:
        logger.error(f"Failed to connect to calendar: {error}")
        return None


class GoogleCalendarService:
    """
    A service class that wraps Google Calendar API functions.
    """
    
    def __init__(self):
        """Initialize the Google Calendar service."""
        self.service = None
        try:
            self.service = get_calendar_service()
            logger.info("GoogleCalendarService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GoogleCalendarService: {e}")
    
    def is_available(self):
        """Check if the calendar service is available."""
        return self.service is not None
    
    def get_next_meeting(self, user_id=None):
        """Get the next upcoming meeting."""
        try:
            if not self.service:
                return "Calendar service not available"
            return get_next_meeting()
        except Exception as e:
            logger.error(f"Error getting next meeting: {e}")
            return "Unable to get next meeting"
    
    def get_today_events(self, user_id=None):
        """Get today's events."""
        try:
            if not self.service:
                return "Calendar service not available"
            return get_today_schedule()
        except Exception as e:
            logger.error(f"Error getting today's events: {e}")
            return "Unable to get today's events"
    
    def get_upcoming_events(self, user_id=None, days=7):
        """Get upcoming events."""
        try:
            if not self.service:
                return "Calendar service not available"
            return get_upcoming_events(days)
        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            return "Unable to get upcoming events"
    
    def create_event_from_text(self, text, user_id=None):
        """Create an event from natural language text."""
        try:
            if not self.service:
                return "Calendar service not available"
            return create_event_from_conversation(text)
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return "Unable to create event"
    
    def find_free_slots(self, duration_minutes, participants="", days_ahead=7):
        """Find available meeting slots."""
        try:
            if not self.service:
                return ["Calendar service not available"]
            return find_meeting_slots(duration_minutes, participants, days_ahead)
        except Exception as e:
            logger.error(f"Error finding free slots: {e}")
            return ["Unable to find free slots"]


# Create a global instance
calendar_service = GoogleCalendarService()

if __name__ == "__main__":
    print("Testing calendar integration...")
    test_calendar_connection()
    
    print("\nTesting event creation...")
    test_events = [
        "Meeting with John tomorrow at 2pm",
        "Gym session Friday 6pm",
        "Dentist appointment next Monday at 10am"
    ]
    
    for event_text in test_events:
        result = create_event_from_conversation(event_text)
        print(f"'{event_text}' -> {result}")

