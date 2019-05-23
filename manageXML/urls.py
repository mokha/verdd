from django.urls import path
from . import views

urlpatterns = [
    path(r'', views.ElementView.as_view(), name='index')
]
