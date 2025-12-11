import logging
import os
import requests
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import current_app, Flask
import uuid

from ..extensions import db
from ..models import User

# Optional models not present in this codebase
Log = None  # type: ignore
Note = None  # type: ignore

logger = logging.getLogger(__name__)

# Global reference to the Flask app instance, to be set by app.py
_flask_app_instance_cp = None

def set_flask_app_for_command_processor(app_instance: Flask):
    """Sets the Flask app instance for use in command processor background tasks."""
    global _flask_app_instance_cp
    _flask_app_instance_cp = app_instance

class VoiceCommandProcessor:
    """
    Enhanced voice command processor with real API integrations.
    Supports weather, news, reminders, timers, notes, and more.
    """
    def __init__(self, user_id: Optional[uuid.UUID] = None): # user_id is now a UUID object
        self.user_id = user_id
        self.commands = {
            'weather': self.get_weather,
            'news': self.get_news,
            'reminder': self.set_reminder,
            'timer': self.set_timer,
            'note': self.take_note,
            'search': self.web_search,
            'translate': self.translate_text,
            'calculate': self.calculate,
            'fact': self.get_random_fact,
            'joke': self.get_joke,
            # Calendar commands
            'calendar_next': self.get_next_meeting,
            'calendar_today': self.get_today_events,
            'calendar_upcoming': self.get_upcoming_events,
            'calendar_create': self.create_calendar_event,
            'calendar_free_time': self.find_free_time,
            'calendar_status': self.get_calendar_status,
        }
        
        # API Keys from environment
        self.weather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.news_api_key = os.getenv('NEWS_API_KEY')
        
        # Active timers storage
        self.active_timers = {}

    def process_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """
        Process a given command with enhanced error handling and logging.

        Args:
            command (str): The command to process (e.g., 'weather').
            **kwargs: Additional arguments for the command.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the command.
        """
        # Handle special case for 'unknown' command type from voice processing
        if command == 'unknown' and 'raw_command' in kwargs:
            raw_command = kwargs.get('raw_command', '')
            # Check for weather patterns in the raw command
            if 'weather' in raw_command.lower():
                logger.info(f"Detected weather intent in '{raw_command}', redirecting to weather command")
                
                # Try to extract location from the raw command
                import re
                location_match = re.search(r"weather(?:\s+(?:in|at|for))?\s+([a-zA-Z0-9 ,.-]+)", raw_command.lower())
                location = "current location"
                
                if location_match and location_match.group(1).strip():
                    location = location_match.group(1).strip()
                    
                logger.info(f"Extracted location: {location}")
                return self.get_weather(location=location)
                
        action = self.commands.get(command)
        if action:
            logger.info(f"Processing command '{command}' for user {self.user_id}")
            
            # Log to database, passing extra_data instead of metadata
            self._log_command_to_database('INFO', f"Processing voice command: {command}", kwargs)
            
            try:
                result = action(**kwargs)
                self._log_command_to_database('INFO', f"Command '{command}' completed successfully", result)
                return result
            except Exception as e:
                error_msg = f"Error processing command '{command}': {str(e)}"
                logger.error(error_msg)
                self._log_command_to_database('ERROR', error_msg, {'error': str(e)})
                return {'success': False, 'error': error_msg, 'user_message': 'Sorry, I encountered an error processing that command.'}
        else:
            error_msg = f"Unknown command: {command}"
            logger.warning(error_msg)
            self._log_command_to_database('WARNING', error_msg, {'command': command})
            return {'success': False, 'error': error_msg, 'user_message': f"I don't recognize the command '{command}'. Try asking for weather, news, or setting a reminder."}

    def _log_command_to_database(self, level: str, message: str, extra_data: Dict = None):
        """Log command events to database, ensuring application context."""
        if not _flask_app_instance_cp:
            logger.error("Flask app instance not set for command processor logging. Cannot log to DB.")
            return
            
        if not db or not Log:
            logger.warning("Database models not available - logging to console instead")
            logger.info(f"[{level}] {message}")
            return
            
        with _flask_app_instance_cp.app_context():
            try:
                new_log = Log(
                    user_id=str(self.user_id) if self.user_id else None,
                    level=level,
                    message=message,
                    source='voice_command_processor',
                    extra_data=extra_data or {}
                )
                db.session.add(new_log)
                db.session.commit()
            except Exception as e:
                _flask_app_instance_cp.logger.error(f"Failed to log to database from command processor: {e}")
                try:
                    if db and db.session and db.session.is_active:
                        db.session.rollback()
                except Exception as rollback_e:
                    _flask_app_instance_cp.logger.error(f"Error during rollback for command processor logging: {rollback_e}")
            finally:
                # Ensure session is cleaned up after each DB operation
                try:
                    if db and db.session:
                        db.session.remove()
                except Exception as cleanup_e:
                    _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in command processor log: {cleanup_e}")


    def get_weather(self, location: str = "New York") -> Dict[str, Any]:
        """
        Get the current weather for a location using OpenWeatherMap API.
        """
        logger.info(f"Fetching weather for {location}...")
        
        # If location is "current location", default to New York
        if location.lower() == "current location":
            location = "New York"
        
        # Get API key from environment or instance
        api_key = self.weather_api_key or os.getenv('OPENWEATHER_API_KEY')
        
        if not api_key:
            return {
                'success': True,  # Set to true so UI doesn't show error
                'data': {
                    'location': f"{location}",
                    'temperature': "72°F",
                    'condition': "Sunny",
                    'humidity': "50%",
                    'wind_speed': "5 mph"
                },
                'user_message': f"The weather in {location} is currently sunny and 72°F. (Demo mode - configure OPENWEATHER_API_KEY for real data)"
            }
        
        try:
            # OpenWeatherMap Current Weather API
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': location,
                'appid': api_key,
                'units': 'imperial'  # For Fahrenheit
            }
            
            logger.info(f"Making API request to {url} with location: {location}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            weather_info = {
                'location': f"{data['name']}, {data['sys']['country']}",
                'temperature': f"{round(data['main']['temp'])}°F",
                'feels_like': f"{round(data['main']['feels_like'])}°F",
                'condition': data['weather'][0]['description'].title(),
                'humidity': f"{data['main']['humidity']}%",
                'wind_speed': f"{data['wind']['speed']} mph"
            }
            
            user_message = f"The weather in {weather_info['location']} is {weather_info['condition']} with a temperature of {weather_info['temperature']} (feels like {weather_info['feels_like']}). Humidity is {weather_info['humidity']} and wind speed is {weather_info['wind_speed']}."
            
            return {
                'success': True,
                'data': weather_info,
                'user_message': user_message
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch weather data: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'user_message': f"Sorry, I couldn't get the weather for {location}. Please try again or try another location."
            }

    def get_news(self) -> Dict[str, Any]:
        """
        Get top headlines (placeholder for real news API integration).
        """
        logger.info("Fetching news headlines...")
        
        # This would typically use NewsAPI.org or similar
        headlines = [
            "Scientists Make Breakthrough in Quantum Computing",
            "New Climate Agreement Signed by 150 Nations",
            "Tech Company Launches Revolutionary AI Assistant",
            "Global Economy Shows Signs of Recovery",
            "Space Mission Successfully Lands on Mars"
        ]
        
        return {
            'success': True,
            'data': {
                'headlines': headlines
            },
            'user_message': "Here are today's top headlines: \n- " + "\n- ".join(headlines)
        }

    def set_reminder(self, text: str, when: str) -> Dict[str, Any]:
        """
        Set a reminder for a future time.
        """
        logger.info(f"Setting reminder: {text} for time: {when}")
        
        # This is a placeholder for actual reminder setting
        # In a real implementation, we would use a persistent storage
        # and a background scheduler
        
        # For demo purposes, let's just confirm the reminder
        reminder_id = str(uuid.uuid4())[:8]
        
        return {
            'success': True,
            'data': {
                'reminder_id': reminder_id,
                'text': text,
                'when': when,
                'status': 'scheduled'
            },
            'user_message': f"I've set a reminder for '{text}' at {when}."
        }

    def set_timer(self, duration_minutes: int, label: str = None) -> Dict[str, Any]:
        """
        Set a timer for a specified duration.
        """
        try:
            # Parse int if needed
            if isinstance(duration_minutes, str):
                duration_minutes = int(duration_minutes)
            
            if duration_minutes <= 0:
                return {
                    'success': False,
                    'error': 'Invalid duration',
                    'user_message': 'Please specify a positive duration in minutes.'
                }
                
            timer_id = str(uuid.uuid4())
            timer_label = label or f"Timer {timer_id[:6]}"
            
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Store timer info
            self.active_timers[timer_id] = {
                'id': timer_id,
                'user_id': self.user_id,
                'label': timer_label,
                'duration': duration_minutes,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'status': 'running'
            }
            
            # Start a background thread to manage the timer
            timer_thread = threading.Thread(
                target=self._run_timer,
                args=(timer_id, duration_minutes, timer_label),
                daemon=True
            )
            timer_thread.start()
            
            # Return immediate confirmation
            return {
                'success': True,
                'data': {
                    'timer_id': timer_id,
                    'label': timer_label,
                    'duration': duration_minutes,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'status': 'running'
                },
                'user_message': f"Timer '{timer_label}' set for {duration_minutes} minute{'s' if duration_minutes != 1 else ''}."
            }
            
        except ValueError as e:
            return {
                'success': False,
                'error': str(e),
                'user_message': 'Please specify a valid duration in minutes.'
            }
            
        except Exception as e:
            logger.error(f"Error setting timer: {str(e)}")
            return {
                'success': False, 
                'error': str(e),
                'user_message': 'Sorry, there was an error setting the timer.'
            }
    
    def _run_timer(self, timer_id: str, duration_minutes: int, label: str):
        """Background task to track a timer and mark it complete when done."""
        try:
            # Sleep for the timer duration
            time.sleep(duration_minutes * 60)
            
            # Update timer status
            if timer_id in self.active_timers:
                self.active_timers[timer_id]['status'] = 'completed'
                
                # Log completion to database
                self._log_command_to_database(
                    'INFO', 
                    f"Timer {label} completed after {duration_minutes} minutes",
                    {'timer_id': timer_id, 'duration': duration_minutes, 'label': label}
                )
                
                # Here we would trigger a notification system
                logger.info(f"Timer {label} completed after {duration_minutes} minutes")
                
        except Exception as e:
            logger.error(f"Error in timer background task: {str(e)}")
            if timer_id in self.active_timers:
                self.active_timers[timer_id]['status'] = 'error'
                self.active_timers[timer_id]['error'] = str(e)

    def take_note(self, note_text: str) -> Dict[str, Any]:
        """
        Take a note and save it with enhanced metadata.
        """
        logger.info(f"Taking note for user {self.user_id}: '{note_text}'")
        
        if not self.user_id:
            return {
                'success': False,
                'error': 'User not identified.',
                'user_message': 'I need to know who you are to save a note.'
            }
            
        if _flask_app_instance_cp and Note:
            with _flask_app_instance_cp.app_context():
                try:
                    new_note = Note(
                        user_id=self.user_id,
                        content=note_text
                    )
                    db.session.add(new_note)
                    db.session.commit()
                    
                    logger.info(f"Note saved successfully with ID {new_note.id}")
                    user_message = f"Note saved: {note_text[:50]}{'...' if len(note_text) > 50 else ''}"
                    
                    return {
                        'success': True,
                        'data': {
                            'note_id': new_note.id,
                            'content': new_note.content,
                            'created_at': new_note.created_at.isoformat(),
                            'message': 'Note saved successfully.'
                        },
                        'user_message': user_message
                    }
                except Exception as e:
                    _flask_app_instance_cp.logger.error(f"Failed to save note to database from command processor: {e}")
                    try:
                        if db.session.is_active:
                            db.session.rollback()
                    except Exception as rollback_e:
                        _flask_app_instance_cp.logger.error(f"Error during rollback for note: {rollback_e}")
                    return {
                        'success': False,
                        'error': str(e),
                        'user_message': 'Sorry, I couldn\'t save that note. Please try again.'
                    }
                finally:
                    try:
                        db.session.remove()
                    except Exception as cleanup_e:
                        _flask_app_instance_cp.logger.error(f"Error cleaning up DB session in note: {cleanup_e}")
        else:
            logger.error("Note model or app context not available. Cannot save note to DB.")
            return {
                'success': False,
                'error': 'Note storage not configured.',
                'user_message': 'Note taking is not configured yet.'
            }


    def web_search(self, query: str) -> Dict[str, Any]:
        """
        Perform a web search (placeholder for search API integration).
        """
        logger.info(f"Performing web search for: {query}")
        
        # Demo response (integrate with real search API like Google Custom Search or Bing)
        return {
            'success': True,
            'data': {
                'query': query,
                'results': [
                    f"Search result 1 for '{query}'",
                    f"Search result 2 for '{query}'",
                    f"Search result 3 for '{query}'"
                ]
            },
            'user_message': f"Here are search results for '{query}': (Demo mode - integrate with search API for real results)"
        }

    def translate_text(self, text: str, target_language: str = "Spanish") -> Dict[str, Any]:
        """
        Translate text to another language (placeholder for translation API).
        """
        logger.info(f"Translating '{text}' to {target_language}")
        
        # Demo response (integrate with Google Translate or similar)
        translations = {
            'hello': {'Spanish': 'Hola', 'French': 'Bonjour', 'German': 'Hallo'},
            'goodbye': {'Spanish': 'Adiós', 'French': 'Au revoir', 'German': 'Auf Wiedersehen'},
            'thank you': {'Spanish': 'Gracias', 'French': 'Merci', 'German': 'Danke'}
        }
        
        translated = translations.get(text.lower(), {}).get(target_language, f"[{text} in {target_language}]")
        
        return {
            'success': True,
            'data': {
                'original_text': text,
                'translated_text': translated,
                'target_language': target_language
            },
            'user_message': f"'{text}' in {target_language} is: {translated}"
        }

    def calculate(self, expression: str) -> Dict[str, Any]:
        """
        Calculate the result of a simple arithmetic expression.
        """
        logger.info(f"Calculating: {expression}")
        
        try:
            # A safer eval implementation for simple arithmetic
            # In production, you would want a proper expression parser
            import re
            if not re.match(r'^[\d\s\+\-\*\/\(\)\.\,]+$', expression):
                raise ValueError("Invalid characters in expression")
                
            result = eval(expression)
            
            return {
                'success': True,
                'data': {
                    'expression': expression,
                    'result': result
                },
                'user_message': f"The result of {expression} is {result}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'user_message': f"Sorry, I couldn't calculate '{expression}'. Please check the syntax and try again."
            }
    
    def get_random_fact(self) -> Dict[str, Any]:
        """
        Get a random interesting fact.
        """
        facts = [
            "The Great Wall of China is not visible from space with the naked eye, contrary to popular belief.",
            "Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly good to eat.",
            "A day on Venus is longer than a year on Venus. It takes 243 Earth days to rotate once on its axis, but only 225 Earth days to go around the Sun.",
            "The fingerprints of koalas are so similar to humans that they have on occasion been confused at crime scenes.",
            "The Hawaiian alphabet has only 13 letters.",
            "Octopuses have three hearts, nine brains, and blue blood."
        ]
        
        import random
        fact = random.choice(facts)
        
        return {
            'success': True,
            'data': {'fact': fact},
            'user_message': fact
        }
    
    def get_joke(self) -> Dict[str, Any]:
        """
        Get a joke.
        """
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a fake noodle? An impasta!",
            "Why did the math book look so sad? Because it had too many problems!",
            "What do you call a bear with no teeth? A gummy bear!"
        ]
        
        import random
        joke = random.choice(jokes)
        
        return {
            'success': True,
            'data': {'joke': joke},
            'user_message': joke
        }

    def get_active_timers(self) -> Dict[str, Any]:
        """
        Get list of active timers for the current user.
        """
        user_timers = {tid: timer for tid, timer in self.active_timers.items() 
                      if timer.get('user_id') == self.user_id and timer.get('status') == 'running'}
        
        return {
            'success': True,
            'data': {'timers': user_timers},
            'user_message': f"You have {len(user_timers)} active timer(s)."
        }
            
    # Calendar-related functions
    def get_next_meeting(self) -> Dict[str, Any]:
        """Get the next meeting from the calendar."""
        logger.info("Fetching next meeting from calendar")
        
        try:
            from .google_calendar_integration import get_next_meeting
                
            meeting = get_next_meeting()
            logger.info(f"Retrieved meeting data: {meeting}")
            
            if meeting and 'event' in meeting and meeting['event']:
                event = meeting.get('event', {})
                start_time = event.get('start_time', 'Unknown time')
                end_time = event.get('end_time', 'Unknown time')
                summary = event.get('summary', 'Untitled meeting')
                location = event.get('location', 'No location specified')
                
                formatted_time = meeting.get('formatted_time', start_time)
                
                user_message = f"Your next meeting is '{summary}' at {formatted_time}"
                if location and location != 'No location specified':
                    user_message += f", located at {location}"
                
                return {
                    'success': True,
                    'data': event,
                    'user_message': user_message
                }
            else:
                return {
                    'success': True,
                    'data': {},
                    'user_message': "You don't have any upcoming meetings on your calendar."
                }
                
        except Exception as e:
            logger.error(f"Error getting next meeting: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't access your calendar information at the moment."
            }
    
    def get_today_events(self) -> Dict[str, Any]:
        """Get today's calendar events."""
        logger.info("Fetching today's calendar events")
        
        try:
            from .google_calendar_integration import get_today_schedule
                
            result = get_today_schedule()
            
            if result and 'events' in result and result['events']:
                events = result['events']
                
                if len(events) == 1:
                    user_message = f"You have 1 event today: {events[0]['summary']} at {events[0]['start_time']}"
                else:
                    user_message = f"You have {len(events)} events today. Here are your events:"
                    for i, event in enumerate(events[:5], 1):  # Limit to first 5 events
                        user_message += f"\n{i}. {event['summary']} at {event['start_time']}"
                    
                    if len(events) > 5:
                        user_message += f"\n...and {len(events) - 5} more event(s)."
                
                return {
                    'success': True,
                    'data': {'events': events},
                    'user_message': user_message
                }
            else:
                return {
                    'success': True,
                    'data': {'events': []},
                    'user_message': "You don't have any events scheduled for today."
                }
                
        except Exception as e:
            logger.error(f"Error getting today's events: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't access your calendar information at the moment."
            }
    
    def get_upcoming_events(self, days=7) -> Dict[str, Any]:
        """Get upcoming calendar events for the next X days."""
        logger.info(f"Fetching upcoming calendar events for the next {days} days")
        
        try:
            # Convert days parameter to int if it's a string
            if isinstance(days, str):
                days = int(days)
                
            from .google_calendar_integration import get_upcoming_events
                
            result = get_upcoming_events(days_ahead=days)
            
            if result and 'events' in result and result['events']:
                events = result['events']
                
                if len(events) == 1:
                    user_message = f"You have 1 upcoming event in the next {days} days: {events[0]['summary']} on {events[0]['date']} at {events[0]['start_time']}"
                else:
                    user_message = f"You have {len(events)} events in the next {days} days. Here are your upcoming events:"
                    for i, event in enumerate(events[:5], 1):  # Limit to first 5 events
                        user_message += f"\n{i}. {event['summary']} on {event['date']} at {event['start_time']}"
                    
                    if len(events) > 5:
                        user_message += f"\n...and {len(events) - 5} more event(s)."
                
                return {
                    'success': True,
                    'data': {'events': events},
                    'user_message': user_message
                }
            else:
                return {
                    'success': True,
                    'data': {'events': []},
                    'user_message': f"You don't have any events scheduled for the next {days} days."
                }
                
        except Exception as e:
            logger.error(f"Error getting upcoming events: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't access your calendar information at the moment."
            }
    
    def create_calendar_event(self, event_text: str) -> Dict[str, Any]:
        """Create a calendar event from natural language text."""
        logger.info(f"Creating calendar event from: {event_text}")
        
        try:
            from .google_calendar_integration import create_event_from_conversation
                
            result = create_event_from_conversation(event_text)
            
            if result and result.get('success'):
                event = result.get('event', {})
                
                # Build the base message
                if 'message' in result:
                    base_message = result.get('message')
                else:
                    # Otherwise, construct the message based on event details
                    if event.get('is_all_day', False):
                        base_message = f"I've scheduled an all-day event '{event.get('summary')}' on {event.get('date', 'the requested date')}."
                    else:
                        base_message = f"I've scheduled '{event.get('summary')}' on {event.get('date', 'the requested date')} at {event.get('start_time', 'specified time')}."
                
                # APPEND THE FOLLOW-UP QUESTION
                user_message = f"{base_message} Is there anything else I can help you with?"
                
                return {
                    'success': True,
                    'data': event,
                    'user_message': user_message,
                    'htmlLink': event.get('htmlLink', '')
                }
            else:
                error_msg = result.get('error', 'Could not parse event details from your request.')
                # Use the message provided by the calendar service if available
                user_message = result.get('message', f"I couldn't create that calendar event. Please provide more details like date, time, and title.")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'user_message': user_message
                }
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't create the calendar event at the moment. Please make sure to include a title, date and time."
            }
    
    def find_free_time(self, date: str = None) -> Dict[str, Any]:
        """Find free time slots in the calendar."""
        logger.info(f"Finding free time slots in calendar for date: {date or 'today'}")
        
        try:
            from .google_calendar_integration import get_free_time_today
                
            result = get_free_time_today()  # TODO: Enhance to support specific dates
            
            if result and 'free_slots' in result and result['free_slots']:
                free_slots = result['free_slots']
                
                if len(free_slots) == 1:
                    slot = free_slots[0]
                    user_message = f"You have 1 free time slot today: {slot['start']} to {slot['end']} ({slot['duration']} minutes)"
                else:
                    user_message = f"You have {len(free_slots)} free time slots today. Here they are:"
                    for i, slot in enumerate(free_slots[:5], 1):  # Limit to first 5 slots
                        user_message += f"\n{i}. {slot['start']} to {slot['end']} ({slot['duration']} minutes)"
                    
                    if len(free_slots) > 5:
                        user_message += f"\n...and {len(free_slots) - 5} more time slot(s)."
                
                return {
                    'success': True,
                    'data': {'free_slots': free_slots},
                    'user_message': user_message
                }
            else:
                return {
                    'success': True,
                    'data': {'free_slots': []},
                    'user_message': "I couldn't find any significant free time slots in your calendar today."
                }
                
        except Exception as e:
            logger.error(f"Error finding free time: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't access your calendar information to find free time."
            }
    
    def get_calendar_status(self) -> Dict[str, Any]:
        """Check if the calendar service is connected and working."""
        logger.info("Checking calendar connection status")
        
        try:
            from .google_calendar_integration import test_calendar_connection
                
            result = test_calendar_connection()
            
            if result and result.get('connected'):
                user_message = f"Your Google Calendar is connected. Associated with: {result.get('email', 'Unknown email')}"
                
                return {
                    'success': True,
                    'data': result,
                    'user_message': user_message
                }
            else:
                error_msg = result.get('error', 'Unknown error')
                return {
                    'success': False,
                    'error': error_msg,
                    'user_message': f"Your Google Calendar is not connected: {error_msg}"
                }
                
        except Exception as e:
            logger.error(f"Error checking calendar status: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'user_message': "I couldn't verify your calendar connection status."
            }
