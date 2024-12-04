from django.urls import path
from .views import FetchGoogleCalendarEvents, AddCalendarEvent, DeleteCalendarEvent, JoinMeetingEvents, GoogleLogin, GoogleCallback, ConnectedEmails, DeleteEmails, FetchUpcomingEvents, FetchFinishedEvents, FetchTranscription, RunChatBot

urlpatterns = [
    path('auth/', GoogleLogin.as_view(), name='google-auth'),
    path('auth/callback', GoogleCallback.as_view(), name='google-auth-callback'),
    path('connected-emails/', ConnectedEmails.as_view(), name='connected-emails'),
    path('delete-email/<str:email>/', DeleteEmails.as_view(), name='delete-email'), 
    path('fetch-meeting-invites/', FetchGoogleCalendarEvents.as_view(), name='list-connected-emails'),
    path('fetch-active-events/', FetchUpcomingEvents.as_view(), name='upcoming-events'),
    path('fetch-finished-events/', FetchFinishedEvents.as_view(), name='finished-events'),
    path('add-event/', AddCalendarEvent.as_view(), name='add-event'),
    path('delete-event/<str:id>/', DeleteCalendarEvent.as_view(), name='delete-event'),
    path('join-meeting/', JoinMeetingEvents.as_view(), name='join-meeting'), 
    path('fetch-transcription/', FetchTranscription.as_view(),  name='fetch-transcription'),
    path('chatbot/', RunChatBot.as_view(),  name='chat-with-openai'),
]
