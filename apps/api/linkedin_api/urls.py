from django.urls import path

from login_api.api import api


urlpatterns = [path("api/", api.urls)]
