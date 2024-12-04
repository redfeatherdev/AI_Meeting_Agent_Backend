from django.urls import path
from .views import Auth, SignUp, SignIn, GoogleLogin, GoogleCallbackView

urlpatterns = [
  path('', Auth.as_view(), name='auth'),
  path('signup/', SignUp.as_view(), name='sign-up'),
  path('signin/', SignIn.as_view(), name='sign-in'),
  path('google/', GoogleLogin.as_view(), name='google-login'),
  path('google/callback/', GoogleCallbackView.as_view(), name='google-callback'),
]