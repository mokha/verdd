from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.ElementView.as_view(), name='index'),
    re_path(r'^lexeme/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.ElementDetailView.as_view(),
            name='element-detail'),
    re_path(r'^lexeme/edit/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.ElementEditView.as_view(),
            name='element-edit'),
    re_path(r'^translation/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.TranslationDetailView.as_view(),
            name='translation-detail'),
    re_path(r'^translation/edit/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.TranslationEditView.as_view(),
            name='translation-edit'),
    # re_path(r'^source/(?P<pk>\d+)/$', views.SourceDetailView.as_view(),
    #         name='source-detail'),
    re_path(r'^source/edit/(?P<pk>\d+)/$', views.SourceEditView.as_view(),
            name='source-edit'),
    # re_path(r'^mini-paradigm/(?P<pk>\d+)/$', views.MiniParadigmDetailView.as_view(),
    #         name='mini-paradigm-detail'),
    re_path(r'^lexeme/(?P<translation_id>\d+)/add-mini-paradigm/$', views.MiniParadigmCreateView.as_view(),
            name='mini-paradigm-add'),
    re_path(r'^mini-paradigm/edit/(?P<pk>\d+)/$', views.MiniParadigmEditView.as_view(),
            name='mini-paradigm-edit')
]
