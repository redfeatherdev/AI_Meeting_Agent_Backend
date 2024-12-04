import uuid
import urllib.parse

from django.contrib.auth import authenticate
from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.utils.decorators import method_decorator
from django.db import models

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from .models import CustomUser
from .utils import token_required

class Auth(APIView):
  @method_decorator(token_required)
  def get(self, request):
     user = request.user
     user_data = {
        'email': user.email,
        'username': user.username,
        'is_active': user.is_active,
        'is_admin': user.is_admin
     }
     return Response({'message': 'Success', 'user': user_data}, status=status.HTTP_200_OK)

class SignUp(APIView):
  def post(self, request):
    username = request.data.get('name')
    email = request.data.get('email')
    password = request.data.get('password')

    if CustomUser.objects.filter(username=username).exists():
      return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

    if CustomUser.objects.filter(email=email).exists():
      return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    max_team = CustomUser.objects.aggregate(max_team=models.Max('team'))['max_team']

    if max_team is None:
       team = 1
    else:
       team = max_team + 1
    
    user = CustomUser.objects.create(
      username=username,
      email=email,
      team = team
    )
    user.set_password(password)
    user.save()

    return Response({'message': 'User created successfully'}, status=status.HTTP_200_OK)
    
class SignIn(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active:
              refresh = RefreshToken.for_user(user)
              update_last_login(None, user)
              return Response({
                'message': 'User signed in successfully',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
              },
              status=status.HTTP_200_OK)
            else:
               return Response({'error': 'This account is inactive'}, status=status.HTTP_400_BAD_REQUEST)
               
        return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        
class GoogleLogin(APIView):
  def get(self, request, *args, **kwargs):
    flow = Flow.from_client_config(
      client_config=settings.CLIENT_CONFIG,
      scopes=["https://www.googleapis.com/auth/userinfo.email"],
      redirect_uri=settings.GOOGLE_REDIRECT_URL_FOR_AUTH
    )

    state = uuid.uuid4().hex

    authorization_url, state = flow.authorization_url(
      access_type='offline',
      include_granted_scopes='true',
      prompt='consent',
      state=state
    )

    return Response(authorization_url, status=status.HTTP_200_OK)
   
class GoogleCallbackView(APIView):
  def get(self, request, *args, **kwargs):
    flow = Flow.from_client_config(
      client_config=settings.CLIENT_CONFIG,
      scopes=["https://www.googleapis.com/auth/userinfo.email"],
      redirect_uri=settings.GOOGLE_REDIRECT_URL_FOR_AUTH
    )

    flow.fetch_token(authorization_response=request.build_absolute_uri())

    credentials = flow.credentials
    token = credentials.id_token

    try:
      id_info = id_token.verify_oauth2_token(token, Request(), settings.CLIENT_CONFIG['web']['client_id'])
      email = id_info.get('email')
      username = id_info.get('name')

      if not username:
        username = email.split('@')[0]

      user, created = CustomUser.objects.get_or_create(email=email, defaults={'username': username})

      if created:
        user.set_unusable_password()
        user.save()

      refresh = RefreshToken.for_user(user)
      params = {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
      }
      redirect_url = settings.REACT_APP_FRONTEND_URL
      query_string = urllib.parse.urlencode(params)
      full_url = f"{redirect_url}?{query_string}"

      return HttpResponseRedirect(full_url)
    
    except ValueError as e:
      return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)