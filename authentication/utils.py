from authentication.models import CustomUser

from django.contrib.auth.backends import ModelBackend

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.response import Response
from rest_framework import status

from functools import wraps

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(email=username)
        except CustomUser.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
        
def token_required(f):
    @wraps(f)
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        refresh_token = request.headers.get('Refresh')

        if auth_header is None:
            return Response({'error': 'Authorization header is expected'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            token = auth_header.split()[1]
            access_token = AccessToken(token)
            
            user_id = access_token['user_id']
            request.user = CustomUser.objects.get(id=user_id)
            return f(request, *args, **kwargs)
        
        except TokenError as e:
            if refresh_token is None:
                return Response({'error': 'Access token is expired and no refresh token provided'}, status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                refresh = RefreshToken(refresh_token)
                new_access_token = str(refresh.access_token)

                access_token = AccessToken(new_access_token)
                user_id = access_token['user_id']
                user = CustomUser.objects.get(id=user_id)

                request.user = user

                response = f(request, *args, **kwargs)
                response.data['access'] = new_access_token
                
                return response
            
            except TokenError as e:
                return Response({'error': f'Refresh token error: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)
            
        except Exception as e:
            print("General Exception:", str(e))
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    return wrapped_view