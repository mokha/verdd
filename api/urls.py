from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("lexemes", views.LexemeViewSet, basename="api-lexeme")
router.register("relations", views.RelationViewSet, basename="api-relation")
router.register(
    "relation-examples", views.RelationExampleViewSet, basename="api-relation-example"
)
router.register("examples", views.ExampleViewSet, basename="api-example")
router.register(
    "relation-example-links",
    views.RelationExampleLinkViewSet,
    basename="api-relation-example-link",
)
router.register("languages", views.LanguageViewSet, basename="api-language")

urlpatterns = [
    path("me/", views.MeView.as_view(), name="api-me"),
    path("pairs/", views.PairView.as_view(), name="api-pair"),
    path("pairs/bulk/", views.PairBulkView.as_view(), name="api-pair-bulk"),
] + router.urls
