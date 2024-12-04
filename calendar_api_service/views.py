import uuid, json
import requests
import google.oauth2.credentials

from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from asgiref.sync import async_to_sync
from datetime import datetime

from .chat import *
from .models import GoogleCredentials, CalendarEvent
from authentication.models import CustomUser
from .serializers import JoinMeetingRequestSerializer, CalendarEventSerializer
from authentication.utils import token_required

# Create your views here.
class GoogleLogin(APIView):
    @method_decorator(token_required)
    def get(self, request, *args, **kwargs):
        flow = Flow.from_client_config(
            client_config=settings.CLIENT_CONFIG,
            scopes=["https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/userinfo.email"],
            redirect_uri=settings.GOOGLE_REDIRECT_URL_FOR_CALENDAR_API
        )

        state = f"{uuid.uuid4()}|{request.user.id}"

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )

        return Response(authorization_url, status=status.HTTP_200_OK)

class GoogleCallback(APIView):
    def get(self, request, *args, **kwargs):
        state = request.GET.get('state')
        flow = Flow.from_client_config(
            client_config=settings.CLIENT_CONFIG,
            scopes=["https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/userinfo.email"],
            state=state,
            redirect_uri=settings.GOOGLE_REDIRECT_URL_FOR_CALENDAR_API
        )
        try:
            _, user_id = state.split('|')
            user = CustomUser.objects.get(id=user_id)
            flow.fetch_token(authorization_response=request.build_absolute_uri())
            credentials = flow.credentials

            user_info_service = build('oauth2', 'v2', credentials=credentials)
            user_info = user_info_service.userinfo().get().execute()
            email = user_info['email']
            google_credentials, _ = GoogleCredentials.objects.get_or_create(email=email, user=user)
            google_credentials.email = email
            google_credentials.token = credentials.token
            google_credentials.refresh_token = credentials.refresh_token
            google_credentials.token_uri = credentials.token_uri
            google_credentials.client_id = credentials.client_id
            google_credentials.client_secret = credentials.client_secret
            google_credentials.scopes = ','.join(credentials.scopes)
            google_credentials.save()

            return redirect(settings.REACT_APP_FRONTEND_URL)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
class FetchGoogleCalendarEvents(APIView):
    @method_decorator(token_required)
    @swagger_auto_schema(
        operation_description="Fetches Google Calendar events for a given email.",
        manual_parameters=[
            openapi.Parameter('email', openapi.IN_QUERY, description="Email of the Google account to fetch events for", type=openapi.TYPE_STRING)
        ],
        responses={
            200: openapi.Response('List of calendar events'),
            400: openapi.Response('Error message'),
            404: openapi.Response('Credentials not found')
        }
    )
    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({'error': 'Email parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            google_credentials = GoogleCredentials.objects.get(email=email)
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

            return Response({
                'email': google_credentials.email,
                'events': events
            })
        
        except GoogleCredentials.DoesNotExist:
            return Response({'error': 'Google credentials not found for user.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FetchUpcomingEvents(APIView):
    """
    Fetches upcoming events from the database for all connected accounts.
    """
    @method_decorator(token_required)
    def get(self, request):
        try:
            # Fetch active events that are starting from now onwards
            events = CalendarEvent.objects.filter(status='active').order_by('start_time')
            serializer = CalendarEventSerializer(events, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class FetchFinishedEvents(APIView):
    """
    Fetches finished events from the database for all connected accounts.
    """
    @method_decorator(token_required)
    def get(self, request):
        try:
            # Fetch finished events that are starting from now onwards
            events = CalendarEvent.objects.filter(status='finished').order_by('start_time')
            serializer = CalendarEventSerializer(events, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
   
class JoinMeetingEvents(APIView):
    @swagger_auto_schema(
        request_body=JoinMeetingRequestSerializer,
        responses={
            200: openapi.Response('Meeting Bot Added Successfully', JoinMeetingRequestSerializer),
            400: 'Meeting URL is required',
            403: 'Meeting URL is not valid'
        }
    )
    @method_decorator(token_required)
    def post(self, request):
        serializer = JoinMeetingRequestSerializer(data=request.data)
        if serializer.is_valid():
            meeting_url = serializer.validated_data['meeting_url']

            print(meeting_url)
            
            if meeting_url:
                parameters = {
                    "meetingUrl": meeting_url,
                    "language": "en-US",
                    "apiKey": settings.TRANSKRIPTOR_API_KEY
                }

                response = requests.get(settings.TRANSKRIPTOR_JOIN_MEETING_URL, params = parameters)
                if response.status_code == 200:
                    return Response({"message": "Meeting Bot Added Successfully.", "meeting_url": meeting_url}, status=status.HTTP_200_OK)
                else:
                    return Response({"message": "Meeting URL is not valid"}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "Meeting URL is required."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddCalendarEvent(APIView):
    """
    API endpoint to add a new calendar event manually.
    """
    @method_decorator(token_required)
    def post(self, request):
        data = request.data.copy()  # Copy the request data to modify it safely
        
        if 'event_id' not in data or not data['event_id']:
            data['event_id'] = None
            
        if 'google_credentials' not in data or not data['google_credentials']:
            data['google_credentials'] = None

        serializer = CalendarEventSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DeleteCalendarEvent(APIView):
    """
    API endpoint to mark an event as deleted instead of removing it from the database.
    """
    @method_decorator(token_required)
    def delete(self, request, id):
        try:
            event = CalendarEvent.objects.get(id=id, status='active')
            event.status = 'deleted'
            event.save()
            return Response({'message': 'Event marked as deleted.'}, status=status.HTTP_200_OK)
        except CalendarEvent.DoesNotExist:
            return Response({'error': 'Event not found or already deleted.'}, status=status.HTTP_404_NOT_FOUND)

class ConnectedEmails(APIView):
    @method_decorator(token_required)
    def get(self, request):
        emails = GoogleCredentials.objects.filter(user_id=request.user.id).values_list('email', flat=True)
        return Response(emails, status=status.HTTP_200_OK)

class DeleteEmails(APIView):
    @method_decorator(token_required)
    def delete(self, request, email):
        try:
            GoogleCredentials.objects.filter(email=email).delete()
            return Response({'status': 'Successfully deleted the email'}, status=status.HTTP_200_OK)
        except GoogleCredentials.DoesNotExist:
            return Response({'error': 'Email not found'}, status=status.HTTP_404_NOT_FOUND)

class FetchTranscription(APIView):
    """
    Function to fetch the transcription from order id
    """
    @method_decorator(token_required)
    def post(self, request):
        parameters = {
            "orderid": request.data['orderId']
        }
        transcription_res = requests.get(settings.TRANSKRIPTOR_GET_CONTENT_URL, params=parameters)
        if transcription_res.status_code == 200:
            parsed_data = json.loads(transcription_res.content)
            return Response(parsed_data, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Transcription not found"}, status=status.HTTP_400_BAD_REQUEST)

class RunChatBot(APIView):
    """
    Function to get the openai's response based on vector store id
    """
    @method_decorator(token_required)
    def post(self, request):
        query = request.data.get('query')
        vector_store_id = request.data.get('vectorStoreId')

        if not query or not vector_store_id:
            return Response({"error": "Query and vectorStoreId are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = async_to_sync(get_openai_assistant_response)(query, vector_store_id)
            return Response({"response": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)