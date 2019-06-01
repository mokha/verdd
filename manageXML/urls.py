from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.ElementView.as_view(), name='index'),
    re_path(r'^(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.ElementDetailView.as_view(), name='element-detail'),
    re_path(r'^(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.ElementEditView.as_view(), name='element-edit'),
]
