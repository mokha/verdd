import logging

from django.db import DatabaseError

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from manageXML.models import (
    Example,
    Language,
    Lexeme,
    Relation,
    RelationExample,
    RelationExampleRelation,
)

from .filters import LexemeFilter, RelationFilter
from .permissions import IsStaffOrSuperuser
from .merge import (
    MergeError,
    lexeme_summary,
    merge_candidates_queryset,
    merge_lexemes,
    siblings_of,
)
from .split import SplitError, split_lexeme
from .serializers import (
    ExampleSerializer,
    LanguageSerializer,
    LexemeSerializer,
    MergeRequestSerializer,
    PairSerializer,
    RelationExampleLinkSerializer,
    RelationExampleSerializer,
    RelationSerializer,
    SplitRequestSerializer,
)
from .services import AmbiguousLexeme, upsert_pair

logger = logging.getLogger("verdd.manageXML")

MAX_BULK_PAIRS = 100


class ApiPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 500


class ApiAccessMixin:
    # Set per view so the project-wide REST_FRAMEWORK defaults, which the session-based
    # lexeme autocomplete relies on, stay untouched.
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsStaffOrSuperuser]


class AuditedDestroyMixin:
    def perform_destroy(self, instance):
        # simple-history attributes deletions to _history_user, i.e. changed_by.
        instance.changed_by = self.request.user
        logger.info(
            "API delete %s %s by %s",
            instance.__class__.__name__,
            instance.pk,
            self.request.user,
        )
        instance.delete()


class ApiModelViewSet(ApiAccessMixin, AuditedDestroyMixin, viewsets.ModelViewSet):
    pagination_class = ApiPagination
    filter_backends = [DjangoFilterBackend]


class LexemeViewSet(ApiModelViewSet):
    """Deleting a lexeme cascades through relations and examples, so it stays web-only."""

    serializer_class = LexemeSerializer
    queryset = Lexeme.objects.order_by("id")
    filterset_class = LexemeFilter
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    @action(detail=False, methods=["get"], url_path="merge-candidates")
    def merge_candidates(self, request):
        """Undetermined-POS lexemes that share their string and language with a lexeme
        that has a real POS, each with those lexemes and what is attached to them."""
        queryset = merge_candidates_queryset(request.query_params.get("language"))
        page = self.paginate_queryset(queryset)
        groups = [
            {
                "undetermined": lexeme_summary(lexeme),
                "candidates": [lexeme_summary(s) for s in siblings_of(lexeme)],
            }
            for lexeme in page
        ]
        return self.get_paginated_response(groups)

    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request, pk=None):
        """Absorb this lexeme into `into`; send dry_run=true to preview. Headwords that
        differ need allow_different_headword=true."""
        absorbed = self.get_object()
        serializer = MergeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        keeper = serializer.validated_data["into"]
        dry_run = serializer.validated_data["dry_run"]
        try:
            report = merge_lexemes(
                absorbed,
                keeper,
                request.user,
                dry_run=dry_run,
                allow_different_headword=serializer.validated_data["allow_different_headword"],
            )
        except MergeError as exc:
            raise ValidationError({"into": [str(exc)]})
        if not dry_run:
            logger.info("API merge lexeme %s into %s by %s", pk, keeper.pk, request.user)
        return Response(report)

    @action(detail=True, methods=["post"], url_path="split")
    def split(self, request, pk=None):
        """Create a new lexeme (same language) and move the chosen relations and examples of
        this one onto it; send dry_run=true to preview."""
        source = self.get_object()
        serializer = SplitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            report = split_lexeme(
                source,
                request.user,
                new={key: data[key] for key in ("lexeme", "pos", "homoId") if key in data},
                relations=data["relations"],
                examples=data["examples"],
                dry_run=data["dry_run"],
            )
        except SplitError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        if not data["dry_run"]:
            logger.info(
                "API split lexeme %s into new lexeme %s by %s",
                pk,
                report["new"]["id"],
                request.user,
            )
        return Response(report, status=200 if data["dry_run"] else status.HTTP_201_CREATED)


class RelationViewSet(ApiModelViewSet):
    serializer_class = RelationSerializer
    queryset = Relation.objects.select_related(
        "lexeme_from", "lexeme_to"
    ).prefetch_related(
        "relationexample_set__example_from_relationexample_set",
        "relationexample_set__example_to_relationexample_set",
    ).order_by("id")
    filterset_class = RelationFilter


class RelationExampleViewSet(ApiModelViewSet):
    serializer_class = RelationExampleSerializer
    queryset = (
        RelationExample.objects.select_related(
            "relation__lexeme_from", "relation__lexeme_to"
        )
        .prefetch_related(
            "example_from_relationexample_set", "example_to_relationexample_set"
        )
        .order_by("id")
    )
    filterset_fields = ["relation", "language"]


class ExampleViewSet(ApiModelViewSet):
    serializer_class = ExampleSerializer
    queryset = Example.objects.order_by("id")
    filterset_fields = ["lexeme"]


class RelationExampleLinkViewSet(
    ApiAccessMixin,
    AuditedDestroyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RelationExampleLinkSerializer
    queryset = RelationExampleRelation.objects.order_by("id")
    pagination_class = ApiPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["example_from", "example_to"]


class LanguageViewSet(ApiAccessMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = LanguageSerializer
    queryset = Language.objects.order_by("id")
    pagination_class = None


class PosView(ApiAccessMixin, APIView):
    """The POS values currently in use, so clients offer Verdd's own vocabulary."""

    def get(self, request):
        used = Lexeme.objects.order_by("pos").values_list("pos", flat=True).distinct()
        return Response([pos for pos in used if pos])


class MeView(ApiAccessMixin, APIView):
    def get(self, request):
        user = request.user
        return Response(
            {
                "username": user.get_username(),
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )


def _store_pair(request, data):
    serializer = PairSerializer(data=data, context={"request": request})
    if not serializer.is_valid():
        return None, serializer.errors
    try:
        return upsert_pair(request.user, serializer.validated_data), None
    except AmbiguousLexeme as exc:
        return None, {exc.role: [str(exc)]}
    except DatabaseError:
        # upsert_pair is atomic, so nothing of this pair was stored; report it per item
        # instead of failing a bulk request whose earlier pairs are already committed.
        logger.exception("API pair could not be stored")
        return None, {"non_field_errors": ["The pair could not be stored; please retry."]}


class PairView(ApiAccessMixin, APIView):
    """POST one translation pair (plus usage-example pairs); safe to repeat."""

    def post(self, request):
        result, errors = _store_pair(request, request.data)
        if errors:
            raise ValidationError(errors)
        return Response(
            result, status=status.HTTP_201_CREATED if result["created"] else 200
        )


class PairBulkView(ApiAccessMixin, APIView):
    """POST {"pairs": [...]}; every pair is stored independently and reported per item."""

    def post(self, request):
        pairs = request.data.get("pairs") if hasattr(request.data, "get") else None
        if not isinstance(pairs, list):
            raise ValidationError({"pairs": ["Expected a list of pairs."]})
        if len(pairs) > MAX_BULK_PAIRS:
            raise ValidationError(
                {"pairs": ["At most %d pairs per request." % MAX_BULK_PAIRS]}
            )

        results = []
        for item in pairs:
            result, errors = _store_pair(request, item)
            if errors:
                results.append({"ok": False, "errors": errors})
            else:
                results.append({"ok": True, **result})
        return Response({"results": results})
