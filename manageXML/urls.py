from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.LexemeView.as_view(), name='index'),
    re_path(r'^lexeme/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.LexemeDetailView.as_view(),
            name='lexeme-detail'),
    path('download', views.LexemeExportView.as_view(), name='download-csv'),
    re_path(r'^lexeme/edit/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.LexemeEditView.as_view(),
            name='lexeme-edit'),
    re_path(r'^relation/(?P<pk>\d+)/$', views.RelationDetailView.as_view(),
            name='relation-detail'),
    re_path(r'^relation/edit/(?P<pk>\d+)/$', views.RelationEditView.as_view(),
            name='relation-edit'),
    re_path(r'^source/(?P<pk>\d+)/$', views.SourceDetailView.as_view(),
            name='source-detail'),
    re_path(r'^source/edit/(?P<pk>\d+)/$', views.SourceEditView.as_view(),
            name='source-edit'),
    re_path(r'^lexeme/(?P<lexeme_id>\d+)/add-mini-paradigm/$', views.MiniParadigmCreateView.as_view(),
            name='mini-paradigm-add'),
    re_path(r'^mini-paradigm/edit/(?P<pk>\d+)/$', views.MiniParadigmEditView.as_view(),
            name='mini-paradigm-edit'),

    # adding stuff
    re_path(r'^lexeme/add$', views.LexemeCreateView.as_view(),
            name='lexeme-add'),
    re_path(r'^affiliation/(?P<lexeme_id>\d+)/add$', views.AffiliationCreateView.as_view(),
            name='affiliation-add'),
    re_path(r'^source/(?P<lexeme_id>\d+)/(?P<relation_id>\d+)/add$', views.SourceCreateView.as_view(),
            name='source-add'),
    re_path(r'^relation/(?P<lexeme_id>\d+)/add$', views.RelationCreateView.as_view(),
            name='relation-add'),

    # editing
    re_path(r'^affiliation/edit/(?P<pk>\d+)/$', views.AffiliationEditView.as_view(),
            name='affiliation-edit'),
    #
    # deleting stuff
    re_path(r'^lexeme/delete/(?P<pk>\d+)/', views.LexemeDeleteView.as_view(),
            name='lexeme-delete'),
    re_path(r'^relation/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.RelationDeleteView.as_view(),
            name='relation-delete'),
    re_path(r'^affiliation/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.AffiliationDeleteView.as_view(),
            name='affiliation-delete'),
    re_path(r'^source/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.SourceDeleteView.as_view(),
            name='source-delete'),
]
