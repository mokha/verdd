from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.LexemeView.as_view(), name='index'),
    re_path(r'^lexeme/(?P<pk>\d+)(?:-(?P<slug>[\w\d-]+))?/$', views.LexemeDetailView.as_view(),
            name='lexeme-detail'),
    path('download', views.LexemeExportView.as_view(), name='download-csv'),
    path('download-lexc', views.LexemeExportLexcView.as_view(), name='download-lexc'),
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
    re_path(r'^stem/(?P<pk>\d+)/$', views.StemDetailView.as_view(),
            name='stem-detail'),

    # adding stuff
    re_path(r'^lexeme/add$', views.LexemeCreateView.as_view(),
            name='lexeme-add'),
    re_path(r'^affiliation/(?P<lexeme_id>\d+)/add$', views.AffiliationCreateView.as_view(),
            name='affiliation-add'),
    re_path(r'^example/(?P<lexeme_id>\d+)/add$', views.ExampleCreateView.as_view(),
            name='example-add'),
    re_path(r'^relation-example/(?P<lexeme_id>\d+)/(?P<relation_id>\d+)/add$',
            views.RelationExampleCreateView.as_view(),
            name='relation-example-add'),
    re_path(r'^relation-metadata/(?P<lexeme_id>\d+)/(?P<relation_id>\d+)/add$',
            views.RelationMetadataCreateView.as_view(),
            name='relation-metadata-add'),
    re_path(r'^source/(?P<lexeme_id>\d+)/(?P<relation_id>\d+)/add$', views.SourceCreateView.as_view(),
            name='source-add'),
    re_path(r'^relation/(?P<lexeme_id>\d+)/add$', views.RelationCreateView.as_view(),
            name='relation-add'),
    re_path(r'^stem/(?P<lexeme_id>\d+)/add$', views.StemCreateView.as_view(),
            name='stem-add'),

    # editing
    re_path(r'^affiliation/edit/(?P<pk>\d+)/$', views.AffiliationEditView.as_view(),
            name='affiliation-edit'),
    re_path(r'^example/edit/(?P<pk>\d+)/$', views.ExampleEditView.as_view(),
            name='example-edit'),
    re_path(r'^relation-example/(?P<lexeme_id>\d+)/edit/(?P<pk>\d+)/$', views.RelationExampleEditView.as_view(),
            name='relation-example-edit'),
    re_path(r'^relation-metadata/(?P<lexeme_id>\d+)/edit/(?P<pk>\d+)/$', views.RelationMetadataEditView.as_view(),
            name='relation-metadata-edit'),
    re_path(r'^stem/edit/(?P<pk>\d+)/$', views.StemEditView.as_view(),
            name='stem-edit'),

    #
    # deleting stuff
    re_path(r'^lexeme/delete/(?P<pk>\d+)/', views.LexemeDeleteView.as_view(),
            name='lexeme-delete'),
    re_path(r'^relation/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.RelationDeleteView.as_view(),
            name='relation-delete'),
    re_path(r'^affiliation/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.AffiliationDeleteView.as_view(),
            name='affiliation-delete'),
    re_path(r'^example/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.ExampleDeleteView.as_view(),
            name='example-delete'),
    re_path(r'^relation-example/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.RelationExampleDeleteView.as_view(),
            name='relation-example-delete'),
    re_path(r'^relation-metadata/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.RelationMetadataDeleteView.as_view(),
            name='relation-metadata-delete'),
    re_path(r'^source/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.SourceDeleteView.as_view(),
            name='source-delete'),
    re_path(r'^stem/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.StemDeleteView.as_view(),
            name='stem-delete'),

    # searching
    re_path(r'^lexeme/search$', views.LexemeSearchView.as_view(),
            name='lexeme-search'),

    # history search
    re_path(r'^history/search$', views.HistorySearchView.as_view(), name='history-search'),

    # approving lexemes
    re_path(r'^lexeme/approval', views.LexemeApprovalView.as_view(), name='lexeme-approval'),

    path('relation/search', views.RelationView.as_view(), name='relation-search'),
    path('relation/download', views.RelationExportView.as_view(), name='relation-download-csv'),
    path('relation/approval', views.RelationApprovalView.as_view(), name='relation-approval'),

    # approving lexemes and relations from view page
    re_path(r'^lexeme/approve/(?P<pk>\d+)/', views.approve_lexeme,
            name='lexeme-approve'),
    re_path(r'^relation/approve/(?P<pk>\d+)/', views.approve_relation,
            name='relation-approve'),
    re_path(r'^stem/approve/(?P<pk>\d+)/', views.approve_stem,
            name='stem-approve'),

    # switching the directionality of a relation
    re_path(r'^relation/switch/(?P<pk>\d+)/', views.switch_relation,
            name='relation-switch'),
    re_path(r'^relation/reverse/(?P<pk>\d+)/', views.reverse_relation,
            name='relation-reverse'),

    # link two relations
    re_path(r'^relation/example/(?P<pk>\d+)/link$', views.RelationExampleRelationView.as_view(),
            name='relation-link'),
    re_path(r'^example/relation/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/',
            views.RelationExampleRelationDeleteView.as_view(),
            name='relation-link-delete'),
    re_path(r'^example/relation/(?P<lexeme_id>\d+)/edit/(?P<pk>\d+)/$', views.RelationExampleRelationEditView.as_view(),
            name='relation-link-edit'),

    # symbols
    re_path(r'^symbol/list', views.SymbolListView.as_view(), name='symbol-list'),

    # lexeme metadata
    re_path(r'^metadata/(?P<lexeme_id>\d+)/add$', views.LexemeMetadataCreateView.as_view(),
            name='lexeme-metadata-add'),
    re_path(r'^metadata/edit/(?P<pk>\d+)/$', views.LexemeMetadataEditView.as_view(),
            name='lexeme-metadata-edit'),
    re_path(r'^metadata/(?P<lexeme_id>\d+)/delete/(?P<pk>\d+)/', views.LexemeMetadataDeleteView.as_view(),
            name='lexeme-metadata-delete'),

]
