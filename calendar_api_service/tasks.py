# tasks.py
import requests, json, io, re
from datetime import datetime, timedelta
from celery import shared_task
from googleapiclient.discovery import build
import google.oauth2.credentials

from django.conf import settings
from django.utils import timezone
from dateutil.parser import isoparse
from pydub import AudioSegment
from pydub.utils import which
from io import BytesIO
from openai import OpenAI

from .models import GoogleCredentials, CalendarEvent

AudioSegment.converter = which("ffmpeg")
AudioSegment.ffprobe = which("ffprobe")

last_order_id = 1727253113783446562
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def add_meeting_bot(meeting_url):
    """
    Function to add the meeting bot to a specified meeting URL.
    """
    parameters = {
        "meetingUrl": meeting_url,
        "language": "en-US",
        "apiKey": settings.TRANSKRIPTOR_API_KEY
    }

    response = requests.get(settings.TRANSKRIPTOR_JOIN_MEETING_URL, params=parameters)
    if response.status_code == 200:
        print(f"Meeting Bot Added Successfully to {meeting_url}")
        return True
    else:
        print(f"Failed to add Meeting Bot to {meeting_url}: {response.status_code}")
        return False

def get_event_transcription(orderId):
    """
    Functino to fetch the event transcription by orderId
    """
    parameters = {
        "orderid": orderId
    }

    try:
        response = requests.get(settings.TRANSKRIPTOR_GET_CONTENT_URL, params=parameters)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
    except KeyError as e:
        print(f"Missing expected key in parsed data: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def get_audio_duration(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        audio = AudioSegment.from_file(BytesIO(response.content))
        duration_in_seconds = int(len(audio) / 1000.0)
        return duration_in_seconds
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def save_meeting_content_to_vector_store(name, content):
    vector_store = client.beta.vector_stores.create(name=name)
    
    filtered_content = [
        f"{chat['Speaker']} : {chat['text']}"
        for chat in content
    ]

    file_stream = io.BytesIO(json.dumps(filtered_content).encode())
    file_stream.name = "meeting_content.txt"

    client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id,
        files=[file_stream]
    )

    return vector_store.id

def handle_finished_events_history():
    """
    Function to retrieve the events history and update the 'orderId' of active events
    based on the retrieved data.
    """

    global previous_ordered_events_length

    parameters = {
        "apiKey": settings.TRANSKRIPTOR_API_KEY
    }

    try:
        response = requests.get(settings.TRANSKRIPTOR_GET_HISTORY_URL, params=parameters)
        response.raise_for_status()
        
        parsed_data = json.loads(json.loads((response.text)))

        filtered_data = [event for event in parsed_data if int(event["OrderID"]["S"]) > last_order_id]
        length = len(filtered_data)

        if len(filtered_data) > 0:
            active_events = CalendarEvent.objects.filter(status='active').order_by('start_time')
            for i in range(length):
                if i < len(active_events):
                    orderId = filtered_data[i]["OrderID"]["S"]
                    parsed_event_transcription = json.loads(get_event_transcription(orderId))
                    sound_url = parsed_event_transcription['sound']
                    duration_in_second = get_audio_duration(sound_url)
                    vector_store_id = save_meeting_content_to_vector_store(active_events[i].summary, parsed_event_transcription['content'])

                    active_events[i].orderId = orderId
                    active_events[i].status = 'finished'
                    active_events[i].duration = duration_in_second
                    active_events[i].vectorStoreId = vector_store_id

                    active_events[i].save()

    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
    except KeyError as e:
        print(f"Missing expected key in parsed data: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

@shared_task
def update_all_google_calendar_events():
    # Fetch all GoogleCredentials from the database
    credentials_list = GoogleCredentials.objects.all()
    for google_credentials in credentials_list:
        try:
            credentials = google.oauth2.credentials.Credentials(
                token=google_credentials.token,
                refresh_token=google_credentials.refresh_token,
                token_uri=google_credentials.token_uri,
                client_id=google_credentials.client_id,
                client_secret=google_credentials.client_secret,
                scopes=google_credentials.scopes.split(',')
            )

            service = build('calendar', 'v3', credentials=credentials)
            now = datetime.utcnow().isoformat() + 'Z' 
            events_result = service.events().list(
                calendarId='primary', timeMin=now
            ).execute()
            events = events_result.get('items', [])
            print(f"Event numbers {len(events)}")
            for event in events:
                start_time = event['start'].get('dateTime')
                event_start_time = isoparse(start_time)
                # event_start_time = datetime.fromisoformat(start_time[:-1])
                CalendarEvent.objects.update_or_create(
                    google_credentials=google_credentials,
                    event_id=event['id'],
                    defaults={
                        'summary': event.get('summary', ''),
                        'description': event.get('description', ''),
                        'location': event.get('location', ''),
                        'start_time': event['start'].get('dateTime'),
                        'end_time': event['end'].get('dateTime'),
                        'organizer_email': event['organizer'].get('email'),
                        'creator_email': event['creator'].get('email'),
                        'hangout_link': event.get('hangoutLink'),
                        'conference_id': event.get('conferenceData', {}).get('conferenceId'),
                        'conference_solution_name': event.get('conferenceData', {}).get('conferenceSolution', {}).get('name')
                    }
                )
                # Check if the event is starting within the next few minutes
                current_time = timezone.now()  # Get the current time
                time_difference = event_start_time - current_time

                if timedelta(minutes=-5) <= time_difference <= timedelta(minutes=5):  # Check if the event is about to start
                    # Automatically add the meeting bot
                    meeting_url = event.get('hangoutLink')
                    if meeting_url:
                        is_added = add_meeting_bot(meeting_url)
                        if is_added == True:
                            pass
                        else:
                            pass

        except Exception as e:
            print(f"Error updating events for {google_credentials.email}: {e}")

    handle_finished_events_history()