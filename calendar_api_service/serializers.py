from rest_framework import serializers
from .models import CalendarEvent

class JoinMeetingRequestSerializer(serializers.Serializer):
    meeting_url = serializers.URLField(required=True, help_text="URL of the meeting to join")

class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = '__all__'
        extra_kwargs = {
            'event_id': {'required': False, 'allow_null': True, 'allow_blank': True},
            'google_credentials': {'required': False, 'allow_null': True},
            'organizer_email': {'required': False, 'allow_blank': True, 'allow_null': True},
            'creator_email': {'required': False, 'allow_blank': True, 'allow_null': True},
            'orderId': {'required': False, 'allow_blank': True, 'allow_null': True},
            'duration': {'required': False, 'allow_null': True},
            'vectorStoreId': {'required': False, 'allow_blank': True, 'allow_null': True},
        }
