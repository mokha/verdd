import json
import os

from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime
from django_filters import (
    DateFromToRangeFilter,
    DateFilter,
    CharFilter,
    NumberFilter,
    ModelChoiceFilter,
    ChoiceFilter,
    OrderingFilter,
    LookupChoiceFilter,
    DateRangeFilter,
)
from django_filters.widgets import RangeWidget
import django_filters
from django.views.generic import TemplateView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import (
    CreateView,
    DeleteView,
    UpdateView,
    ModelFormMixin,
    FormView,
    FormMixin,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models.functions import Substr, Upper
from django.db.models import Prefetch
from django.core.paginator import Paginator
import hashlib
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.http import Http404
from django.db.models import Q
from rest_framework import generics, response
from .serializers import *
import string
from .forms import *
from django.shortcuts import get_object_or_404
from collections import defaultdict
import csv
import re
from .constants import INFLEX_TYPE_OPTIONS
from .inflector import generate_inflections
from .utils import get_all_used_languages, get_all_used_pos
import logging
from django.conf import settings
from .tasks import process_file_request

logger = logging.getLogger("verdd.manageXML")  # Get an instance of a logger


class AdminStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff


class TitleMixin:
    title = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.get_title()
        return context

    def get_title(self):
        return self.title


class CachedPaginator(Paginator):
    """
    A Paginator that caches the total count of objects to avoid expensive queries.
    Built on top of Django's Paginator.
    """

    def __init__(
        self,
        object_list,
        per_page,
        orphans=0,
        allow_empty_first_page=True,
        cache_timeout=3600,
        cache_key_prefix=None,
    ):
        """
        Initializes the CachedPaginator with additional parameters for caching.

        :param cache_timeout: Time in seconds for which the count will be cached.
        :param cache_key_prefix: Optional prefix for the cache key to avoid collisions.
        """
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.cache_timeout = cache_timeout
        self.cache_key_prefix = cache_key_prefix or "cached_paginator"

    def _generate_cache_key(self):
        """
        Generates a cache key based on the query and model, using a hash for uniqueness.
        """
        query_hash = hashlib.md5(
            str(self.object_list.query).encode("utf-8")
        ).hexdigest()
        return f"{self.cache_key_prefix}:{query_hash}"

    @cached_property
    def count(self):
        """
        Returns the total number of objects, caching the result to avoid redundant count queries.
        """
        cache_key = self._generate_cache_key()
        cached_count = cache.get(cache_key)

        if cached_count is not None:
            return cached_count

        # If count isn't cached, get the actual count and cache it
        total_count = super().count
        cache.set(cache_key, total_count, self.cache_timeout)

        return total_count


class FilteredListView(TitleMixin, ListView):
    filterset_class = None
    paginator_class = CachedPaginator

    def get_queryset(self):
        # Get the queryset however you usually would.  For example:
        queryset = super().get_queryset()
        # Then use the query parameters and the queryset to
        # instantiate a filterset and save it as an attribute
        # on the view instance for later.
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        # Return the filtered queryset
        return self.filterset.qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the filterset to the template - it provides the form.
        context["filterset"] = self.filterset
        return context


class LexemeOrderingFilter(OrderingFilter):
    def filter(self, qs, value):
        if value and any(
            "consonance" in v.lower() or "assonance" in v.lower() for v in value
        ):
            return qs.order_by(value[0], "lexeme_lang")
        return super(LexemeOrderingFilter, self).filter(qs, value)


class LexemeFilter(django_filters.FilterSet):
    STATUS_CHOICES = (
        (True, _("Yes")),
        (False, _("No")),
    )

    ALPHABETS_CHOICES = list(enumerate(string.ascii_uppercase + "ÄÅÖ"))
    ORDER_BY_FIELDS = {
        "pos": "pos",
        "lexeme_lang": "lexeme_lang",
        "consonance": "consonance",
        "consonance_rev": "consonance_rev",
        "assonance": "assonance",
        "assonance_rev": "assonance_rev",
    }

    lookup_choices = [
        ("exact", _("Exact")),
        ("iexact", _("iExact")),
        ("contains", _("Contains")),
        ("icontains", _("iContains")),
        ("startswith", _("Starts with")),
        ("istartswith", _("iStarts with")),
        ("endswith", _("Ends with")),
        ("iendswith", _("iEnds with")),
        ("regex", _("Regex")),
        ("iregex", _("iRegex")),
    ]

    lexeme = LookupChoiceFilter(
        field_class=forms.CharField,
        label=_("Lexeme"),
        empty_label=None,
        lookup_choices=lookup_choices,
    )
    language = ChoiceFilter(label=_("Language"))
    pos = ChoiceFilter(label=_("POS"))
    inflexType = ChoiceFilter(choices=INFLEX_TYPE_OPTIONS, label=_("Inflex Type"))
    contlex = CharFilter(label=_("Contlex"), lookup_expr="exact")
    range_from = ChoiceFilter(
        choices=ALPHABETS_CHOICES, label=_("Range from"), method="filter_range"
    )
    range_to = ChoiceFilter(
        choices=ALPHABETS_CHOICES, label=_("Range to"), method="filter_range"
    )
    checked = ChoiceFilter(choices=STATUS_CHOICES, label=_("Processed"))
    source = CharFilter(label=_("Source"), method="source_filter")

    order_by = LexemeOrderingFilter(fields=ORDER_BY_FIELDS, label=_("Order by"))

    class Meta:
        model = Lexeme
        fields = [
            "lexeme",
            "language",
            "pos",
            "contlex",
            "inflexType",
            "range_from",
            "range_to",
            "source",
        ]

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("order", "+lexeme_lang")
        super().__init__(data, *args, **kwargs)

        languages = get_all_used_languages()
        pos = get_all_used_pos()
        self.form.fields["language"].choices = zip(languages, languages)
        self.form.fields["pos"].choices = zip(pos, pos)
        self.form.fields["order_by"].choices = (
            ("lexeme_lang", _("Lexeme")),
            ("-lexeme_lang", "%s (%s)" % (_("Lexeme"), _("descending"))),
            ("pos", _("POS")),
            ("-pos", "%s (%s)" % (_("POS"), _("descending"))),
            ("contlex", _("ContLex")),
            ("-contlex", "%s (%s)" % (_("ContLex"), _("descending"))),
            ("inflexType", _("inflexType")),
            ("-inflexType", "%s (%s)" % (_("inflexType"), _("descending"))),
            ("consonance", _("Consonance")),
            ("-consonance", "%s (%s)" % (_("Consonance"), _("descending"))),
            ("consonance_rev", _("revConsonance")),
            ("-consonance_rev", "%s (%s)" % (_("revConsonance"), _("descending"))),
            ("assonance", _("Assonance")),
            ("-assonance", "%s (%s)" % (_("Assonance"), _("descending"))),
            ("assonance_rev", _("RevAssonance")),
            ("-assonance_rev", "%s (%s)" % (_("RevAssonance"), _("descending"))),
        )

    def filter_range(self, queryset, name, value):
        # transform datetime into timestamp
        range_from = (
            self.data["range_from"] if "range_from" in self.data else None
        )  # get key
        range_to = self.data["range_to"] if "range_to" in self.data else None  # get key

        range_from = int(range_from) if range_from else 0
        range_to = (
            int(range_to) if range_to else len(LexemeFilter.ALPHABETS_CHOICES) - 1
        )

        if range_from > range_to:
            return queryset.none()

        filters = models.Q()
        for i in range(range_from, range_to + 1):
            filters |= models.Q(
                lexeme__istartswith=LexemeFilter.ALPHABETS_CHOICES[i][1],
            )

        return queryset.filter(filters)

    def source_filter(self, queryset, name, value):
        source = self.data["source"] if "source" in self.data else None  # get key

        filters = models.Q()
        if source:
            relations_with_source = Relation.objects.filter(
                source__name__icontains=source
            )
            filters = Q(lexeme_from_lexeme_set__in=relations_with_source) | Q(
                lexeme_to_lexeme_set__in=relations_with_source
            )
        return queryset.filter(filters)


class LexemeView(FilteredListView):
    filterset_class = LexemeFilter
    model = Lexeme
    template_name = "lexeme_list.html"
    paginate_by = 50
    title = _("Homepage")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_by = self.request.GET.get("order_by", None)
        order_by = order_by[1:] if order_by and order_by.startswith("-") else order_by
        order_by_options = dict(
            [[v, k] for k, v in self.filterset_class.ORDER_BY_FIELDS.items()]
        )
        if (
            order_by
            and order_by not in ["pos", "lexeme_lang"]
            and order_by in order_by_options
        ):
            context["order_by"] = order_by_options[order_by]
        return context


class LexemeDictionaryFilter(django_filters.FilterSet):
    ORDER_BY_FIELDS = {
        "pos": "pos",
        "lexeme_lang": "lexeme_lang",
        "consonance": "consonance",
        "consonance_rev": "consonance_rev",
        "assonance": "assonance",
        "assonance_rev": "assonance_rev",
    }

    lookup_choices = [
        ("exact", _("Exact")),
        ("iexact", _("iExact")),
        ("contains", _("Contains")),
        ("icontains", _("iContains")),
        ("startswith", _("Starts with")),
        ("istartswith", _("iStarts with")),
        ("endswith", _("Ends with")),
        ("iendswith", _("iEnds with")),
        ("regex", _("Regex")),
        ("iregex", _("iRegex")),
    ]

    lexeme = LookupChoiceFilter(
        field_class=forms.CharField,
        label=_("Lexeme"),
        empty_label=None,
        lookup_choices=lookup_choices,
    )
    language = ChoiceFilter(
        label=_("Language"), choices=[(_v, _v) for _v in get_all_used_languages()]
    )
    pos = ChoiceFilter(label=_("POS"), choices=[(_v, _v) for _v in get_all_used_pos()])
    contlex = CharFilter(
        label=_("Contlex") + " (" + _("Regex") + ")", method="filter_contlex"
    )
    order_by = LexemeOrderingFilter(fields=ORDER_BY_FIELDS, label=_("Order by"))

    class Meta:
        model = Lexeme
        fields = ["lexeme", "language", "pos", "contlex"]

    def __init__(self, data, *args, **kwargs):
        data = data.copy() if data else {}
        data.setdefault("order", "+lexeme_lang")
        super().__init__(data, *args, **kwargs)

        self.form.fields["order_by"].choices = (
            ("lexeme_lang", _("Lexeme")),
            ("-lexeme_lang", "%s (%s)" % (_("Lexeme"), _("descending"))),
            ("consonance", _("Consonance")),
            ("-consonance", "%s (%s)" % (_("Consonance"), _("descending"))),
            ("consonance_rev", _("revConsonance")),
            ("-consonance_rev", "%s (%s)" % (_("revConsonance"), _("descending"))),
            ("assonance", _("Assonance")),
            ("-assonance", "%s (%s)" % (_("Assonance"), _("descending"))),
            ("assonance_rev", _("RevAssonance")),
            ("-assonance_rev", "%s (%s)" % (_("RevAssonance"), _("descending"))),
        )

    def filter_contlex(self, queryset, name, value):
        """
        Custom filter method to filter Lexemes based on contlex of the Lexeme or related Stem objects.
        """
        return queryset.filter(Q(stem__contlex__iregex=value))


class LexemeDictionaryView(FilteredListView):
    filterset_class = LexemeDictionaryFilter
    model = Lexeme
    template_name = "dictionary/dictionary.html"
    paginate_by = 50
    title = _("Dictionary")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_by = self.request.GET.get("order_by", None)
        if order_by:
            order_by_options = dict(
                [[v, k] for k, v in self.filterset_class.ORDER_BY_FIELDS.items()]
            )
            clean_order_by = order_by[1:] if order_by.startswith("-") else order_by
            if clean_order_by in order_by_options:
                context["order_by"] = order_by_options[clean_order_by]

        return context


class LexemeExportView(LexemeView):
    def render_to_response(self, context, **response_kwargs):
        filename = "{}-export.csv".format(
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        header = [
            _("ID"),
            _("Language"),
            _("Lexeme"),
            _("POS"),
            _("Contlex"),
            _("Inflex Type"),
        ]
        if "order_by" in context:
            header += [_("Ordered By")]
        writer.writerow(header)

        for obj in self.object_list:
            row = [
                obj.id,
                obj.language,
                obj.lexeme,
                obj.pos,
                obj.contlex,
                obj.inflexType_str(),
            ]
            if "order_by" in context:
                row += [getattr(obj, context["order_by"])]
            writer.writerow(row)

        return response


class HistoryExportView:
    def nothing(self):
        Lexeme.history.all()


class MiniParadigmMixin:
    @staticmethod
    def existing_forms(lexeme):
        MP_forms = lexeme.miniparadigm_set.all()
        existing_MP_forms = defaultdict(list)
        for form in MP_forms:
            existing_MP_forms[form.msd].append(form.wordform)
        return existing_MP_forms

    def short_generate_forms(self, lexeme):

        MP_forms = generate_inflections(lexeme)

        existing_MP_forms = MiniParadigmMixin.existing_forms(lexeme)

        generated_forms = defaultdict(list)
        for f, r in MP_forms.items():
            if f in existing_MP_forms:  # if overridden by the user
                continue  # ignore it

            for _r in r:
                generated_forms[f].append(_r)
        generated_forms.default_factory = None
        return generated_forms


class LexemeCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "lexeme_add.html"
    model = Lexeme
    form_class = LexemeCreateForm

    def get_title(self):
        return "%s" % _("Add Lexeme")

    def form_valid(self, form):
        clean = form.cleaned_data
        lexeme = clean.get("lexeme").strip()

        self.object = form.save(commit=False)
        self.object.save()

        # check if affiliation exists in akusanat
        title = self.object.find_akusanat_affiliation()
        # link it
        if title:
            a, created = Affiliation.objects.get_or_create(
                lexeme=self.object,
                title=title,
                type=AKUSANAT,
                link="{}{}".format(settings.WIKI_URL, title),
            )
        form.instance.changed_by = self.request.user
        return HttpResponseRedirect(self.get_success_url())


class LexemeDetailView(TitleMixin, MiniParadigmMixin, DetailView):
    model = Lexeme
    template_name = "lexeme_detail.html"

    def get_around_objects(self, request, object, n=5):
        _filter = LexemeFilter(request.GET)
        ordered = _filter.qs.ordered
        order_by = _filter.qs.query.order_by[0] if ordered else "id"
        desc = order_by.startswith("-")
        order_by = order_by[1:] if order_by[0] in ["-", "+"] else order_by
        value = getattr(object, order_by)

        next_objects, prev_objects = [], []

        try:
            prev_qs = _filter.qs.filter(**{order_by + "__lt": value}).order_by(
                "-" + order_by if not desc else order_by
            )
            next_qs = _filter.qs.filter(**{order_by + "__gt": value})
            prev_objects = prev_qs[:n][::-1]
            next_objects = next_qs[:n]
        except Exception as e:
            pass

        return (
            (
                prev_objects,
                next_objects,
            )
            if not desc
            else (
                next_objects,
                prev_objects,
            )
        )

    def get_context_data(self, **kwargs):
        context = super(LexemeDetailView, self).get_context_data(**kwargs)
        context["generated_miniparadigms"] = self.short_generate_forms(self.object)

        last_lexeme = self.request.GET.get("lastlexeme", None)  # is last lexeme passed?
        last_lexeme = (
            Lexeme.objects.get(pk=last_lexeme) if last_lexeme else self.object
        )  # if not, use the current object

        context["prev_objects"], context["next_objects"] = self.get_around_objects(
            request=self.request, object=last_lexeme, n=25
        )
        context["stems"] = self.object.stem_set.order_by("order").all()
        return context

    def get_title(self):
        return self.object


class LexemeEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "lexeme_edit.html"
    model = Lexeme
    form_class = LexemeForm

    def get_title(self):
        return "%s: %s" % (_("Edit"), self.object.lexeme)

    def form_valid(self, form):
        initial = form.initial
        clean = form.cleaned_data

        old_lexeme = initial.get("lexeme").strip()
        new_lexeme = clean.get("lexeme").strip()

        if new_lexeme != old_lexeme:  # they are different lexemes
            # delete existing affiliations
            form.instance.affiliation_set.all().delete()

            # check if new affiliation exists
            title = self.object.find_akusanat_affiliation()
            # link it
            if title:
                a, created = Affiliation.objects.get_or_create(
                    lexeme=self.object,
                    title=title,
                    type=AKUSANAT,
                    link="{}{}".format(settings.WIKI_URL, title),
                )
        form.instance.changed_by = self.request.user
        return super(LexemeEditView, self).form_valid(form)


class RelationDetailView(TitleMixin, DetailView):
    model = Relation
    template_name = "relation_detail.html"

    def get_context_data(self, **kwargs):
        context = super(RelationDetailView, self).get_context_data(**kwargs)
        return context

    def get_title(self):
        return "%s (%s)" % (
            self.object.lexeme_from.lexeme,
            self.object.lexeme_to.lexeme if self.object.lexeme_to else "",
        )


class RelationEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "relation_edit.html"
    model = Relation
    form_class = RelationForm

    def get_title(self):
        return "%s: %s (%s)" % (
            _("Edit Relation"),
            self.object.lexeme_from.lexeme,
            self.object.lexeme_to.lexeme if self.object.lexeme_to else "",
        )

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationEditView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(RelationEditView, self).get_context_data(**kwargs)
        try:
            _ = Relation.objects.get(
                lexeme_from=self.object.lexeme_to, lexeme_to=self.object.lexeme_from
            )
        except Relation.DoesNotExist:
            context["switch_form"] = FlipRelationForm(relation=self.object)
            context["reverse_form"] = ReverseRelationForm(relation=self.object)
        return context


class SourceDetailView(DetailView):
    model = Source
    template_name = "source_detail.html"


class SourceEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "source_edit.html"
    model = Source
    form_class = SourceForm

    def get_title(self):
        return "%s: %s" % (
            _("Edit source"),
            self.object.relation,
        )

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(SourceEditView, self).form_valid(form)


class MiniParadigmEditView(
    AdminStaffRequiredMixin, MiniParadigmMixin, TitleMixin, UpdateView
):
    template_name = "mini_paradigm_edit.html"
    model = MiniParadigm
    form_class = MiniParadigmForm

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmEditView, self).get_context_data(**kwargs)
        # Pass the filterset to the template - it provides the form.
        lexeme = get_object_or_404(Lexeme, pk=self.object.lexeme.id)
        context["lexeme"] = lexeme
        context["generated_miniparadigms"] = self.short_generate_forms(lexeme)
        return context

    def get_title(self):
        return "%s: %s" % (_("Edit mini paradigm"), self.object.lexeme.lexeme)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(MiniParadigmEditView, self).form_valid(form)


class MiniParadigmCreateView(
    LoginRequiredMixin, MiniParadigmMixin, TitleMixin, CreateView
):
    template_name = "mini_paradigm_add.html"
    model = MiniParadigm
    form_class = MiniParadigmCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        context["generated_miniparadigms"] = self.short_generate_forms(self.lexeme)
        return context

    def get_title(self):
        lexeme = Lexeme.objects.get(pk=self.kwargs["lexeme_id"])
        return "%s: %s" % (_("Add mini paradigm"), lexeme.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(MiniParadigmCreateView, self).form_valid(form)


class RelationCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "relation_add.html"
    model = Relation
    form_class = RelationCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super(RelationCreateView, self).dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super(RelationCreateView, self).get_form(form_class)

        lexeme_from = get_object_or_404(Lexeme, pk=self.kwargs["lexeme_id"])
        form.instance.lexeme_from = lexeme_from

        if form.is_valid():
            data = form.cleaned_data

            lexeme_to_id = data.get("lexeme_to", None)
            if lexeme_to_id:
                form.instance.lexeme_to = Lexeme.objects.get(pk=lexeme_to_id)
        return form

    def get_title(self):
        return "%s %s" % (_("Add Relation from"), self.lexeme)

    def get_context_data(self, **kwargs):
        context = super(RelationCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationCreateView, self).form_valid(form)


class AffiliationCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "affiliation_add.html"
    model = Affiliation
    form_class = AffiliationCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AffiliationCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Affiliation"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(AffiliationCreateView, self).form_valid(form)


class AffiliationEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "affiliation_edit.html"
    model = Affiliation
    form_class = AffiliationEditForm

    def get_title(self):
        return "%s: %s (%s)" % (
            _("Edit Affiliation"),
            self.object.title,
            self.object.lexeme,
        )

    def get_context_data(self, **kwargs):
        context = super(AffiliationEditView, self).get_context_data(**kwargs)
        context["lexeme"] = self.object.lexeme
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(AffiliationEditView, self).form_valid(form)


class SourceCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "source_add.html"
    model = Source
    form_class = SourceCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs["relation_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SourceCreateView, self).get_context_data(**kwargs)
        context["relation"] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (
            _("Add source"),
            self.object,
        )

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(SourceCreateView, self).form_valid(form)


class DeleteFormMixin(AdminStaffRequiredMixin, TitleMixin, DeleteView):
    def get_context_data(self, **kwargs):
        context = super(DeleteFormMixin, self).get_context_data(**kwargs)
        context.update(
            {
                "form": DeleteFormBase(),
            }
        )
        return context

    def delete(self, request, *args, **kwargs):
        object = self.get_object()
        logger.info(
            "[DELETE] %s: %s (%d) by %s"
            % (object.__class__.__name__, object, object.id, self.request.user)
        )
        return super(DeleteFormMixin, self).delete(request, *args, **kwargs)


class LexemeDeleteFormMixin(DeleteFormMixin):
    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(LexemeDeleteFormMixin, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class LexemeDeleteView(DeleteFormMixin):
    template_name = "lexeme_confirm_delete.html"
    model = Lexeme

    def get_success_url(self):
        return reverse("index")

    def get_title(self):
        return "%s: %s" % (
            _("Delete lexeme"),
            self.object,
        )


class RelationDeleteView(LexemeDeleteFormMixin):
    template_name = "relation_confirm_delete.html"
    model = Relation

    def get_title(self):
        return "%s: %s" % (
            _("Delete Relation"),
            self.object,
        )


class AffiliationDeleteView(LexemeDeleteFormMixin):
    template_name = "affiliation_confirm_delete.html"
    model = Affiliation

    def get_title(self):
        return "%s: %s" % (
            _("Delete Affiliation"),
            self.object,
        )


class SourceDeleteView(LexemeDeleteFormMixin):
    template_name = "source_confirm_delete.html"
    model = Source

    def get_title(self):
        return "%s: %s" % (
            _("Delete Source"),
            self.object,
        )


class ExampleCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "example_add.html"
    model = Example
    form_class = ExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ExampleCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Example"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(ExampleCreateView, self).form_valid(form)


class ExampleEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "example_edit.html"
    model = Example
    form_class = ExampleForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Example"), self.object.text, self.object.lexeme)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(ExampleEditView, self).form_valid(form)


class ExampleDeleteView(LexemeDeleteFormMixin):
    template_name = "example_confirm_delete.html"
    model = Example

    def get_title(self):
        return "%s: %s" % (
            _("Delete Example"),
            self.object,
        )


class RelationExampleCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "relation_example_add.html"
    model = RelationExample
    form_class = RelationExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs["relation_id"])
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationExampleCreateView, self).get_form_kwargs()
        kwargs["relation"] = self.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationExampleCreateView, self).get_context_data(**kwargs)
        context["relation"] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Example"), self.relation)

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(RelationExampleCreateView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "relation_metadata_add.html"
    model = RelationMetadata
    form_class = RelationMetadataForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs["relation_id"])
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationMetadataCreateView, self).get_form_kwargs()
        kwargs["relation"] = self.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationMetadataCreateView, self).get_context_data(**kwargs)
        context["relation"] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Data"), self.relation)

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(RelationMetadataCreateView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationExampleEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "relation_example_edit.html"
    model = RelationExample
    form_class = RelationExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationExampleEditView, self).get_form_kwargs()
        kwargs["relation"] = self.object.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationExampleEditView, self).get_context_data(**kwargs)
        context["relation"] = self.object.relation
        return context

    def get_title(self):
        return "%s: %s (%s)" % (
            _("Edit Example"),
            self.object.text,
            self.object.relation,
        )

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationExampleEditView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "relation_metadata_edit.html"
    model = RelationMetadata
    form_class = RelationMetadataForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationMetadataEditView, self).get_form_kwargs()
        kwargs["relation"] = self.object.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationMetadataEditView, self).get_context_data(**kwargs)
        context["relation"] = self.object.relation
        return context

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Data"), self.object.text, self.object.relation)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationMetadataEditView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationExampleRelationView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "relation_example_relation_add.html"
    model = RelationExampleRelation
    form_class = RelationExampleLinkForm

    def __init__(self, *args, **kwargs):
        super(RelationExampleRelationView, self).__init__(*args, **kwargs)
        self.example_from = None

    def dispatch(self, request, *args, **kwargs):
        self.example_from = get_object_or_404(RelationExample, pk=kwargs["pk"])
        return super(RelationExampleRelationView, self).dispatch(
            request, *args, **kwargs
        )

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationExampleRelationView, self).get_form_kwargs()
        kwargs["example_from"] = self.example_from
        return kwargs

    def get_form(self, form_class=None):
        form = super(RelationExampleRelationView, self).get_form(form_class)
        form.instance.example_from = self.example_from
        return form

    def get_title(self):
        return "%s %s" % (_("Add example from"), self.example_from)

    def get_context_data(self, **kwargs):
        context = super(RelationExampleRelationView, self).get_context_data(**kwargs)
        context["example_from"] = self.example_from
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationExampleRelationView, self).form_valid(form)


class RelationExampleRelationEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "relation_example_relation_edit.html"
    model = RelationExampleRelation
    form_class = RelationExampleLinkEditForm

    def dispatch(self, request, *args, **kwargs):
        self.example_from = get_object_or_404(RelationExample, pk=kwargs["pk"])
        return super(RelationExampleRelationEditView, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, **kwargs):
        context = super(RelationExampleRelationEditView, self).get_context_data(
            **kwargs
        )
        context["example_from"] = self.object.example_from
        return context

    def get_title(self):
        return "%s %s" % (_("Edit example link"), self.object.example_from)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationExampleRelationEditView, self).form_valid(form)

    def get_success_url(self):
        return self.object.example_from.get_absolute_url()


class RelationExampleRelationDeleteView(LexemeDeleteFormMixin):
    template_name = "example_relation_confirm_delete.html"
    model = RelationExampleRelation

    def get_title(self):
        return "%s: %s" % (
            _("Delete Example Relation"),
            self.object,
        )


class RelationExampleDeleteView(LexemeDeleteFormMixin):
    template_name = "relation_example_confirm_delete.html"
    model = RelationExample

    def get_title(self):
        return "%s: %s" % (
            _("Delete Example"),
            self.object,
        )

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataDeleteView(LexemeDeleteFormMixin):
    template_name = "relation_metadata_confirm_delete.html"
    model = RelationMetadata

    def get_title(self):
        return "%s: %s" % (
            _("Delete Data"),
            self.object,
        )

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class LexemeSearchView(generics.ListAPIView):
    serializer_class = LexemeSerializer

    def get_queryset(self):
        query = self.request.query_params.get("q", None)
        if query is not None and query:
            filter_Q = Q(lexeme__icontains=query)
            if query.isdigit() and int(query) > 0:
                filter_Q |= Q(id=query)
            return Lexeme.objects.filter(filter_Q).order_by("lexeme_lang")
        return Lexeme.objects.none()


class HistorySearchView(TitleMixin, ListView, AdminStaffRequiredMixin):
    template_name = "history_list.html"
    form_class = HistoryForm
    title = _("History Search")
    model = HistoricalRecords
    query_model = Lexeme
    paginate_by = 50

    query_model_options = {
        "lexeme": Lexeme,
        "relation": Relation,
        "miniparadigm": MiniParadigm,
    }

    def get_context_data(self, *args, **kwargs):
        # Just include the form
        context = super(HistorySearchView, self).get_context_data(*args, **kwargs)
        context["form"] = self.form_class(self.request.GET)
        return context

    def get_queryset(self):
        object_list = self.query_model.history.none()
        if self.request.GET:
            form = self.form_class(self.request.GET)
            if form.is_valid():
                self.query_model = self.query_model_options[
                    form.cleaned_data["model_class"]
                ]

                start_date = form.cleaned_data["start_date"]
                end_date = form.cleaned_data["end_date"]

                object_list = self.query_model.history.filter(
                    Q(history_date__gte=start_date) & Q(history_date__lte=end_date)
                ).order_by("-history_date")
        return object_list


class ApprovalViewMixin(AdminStaffRequiredMixin, FormMixin, FilteredListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            **{"form": None, **kwargs}
        )  # ignore the default form rendering
        context["form"] = self.form_class(
            **{"queryset": context["object_list"], **self.get_form_kwargs()}
        )
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()

        if not allow_empty:
            if self.get_paginate_by(self.object_list) is not None and hasattr(
                self.object_list, "exists"
            ):
                is_empty = not self.object_list.exists()
            else:
                is_empty = not self.object_list
            if is_empty:
                raise Http404(
                    _("Empty list and '%(class_name)s.allow_empty' is False.")
                    % {
                        "class_name": self.__class__.__name__,
                    }
                )
        context = self.get_context_data()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()

        if not allow_empty:
            if self.get_paginate_by(self.object_list) is not None and hasattr(
                self.object_list, "exists"
            ):
                is_empty = not self.object_list.exists()
            else:
                is_empty = not self.object_list
            if is_empty:
                raise Http404(
                    _("Empty list and '%(class_name)s.allow_empty' is False.")
                    % {
                        "class_name": self.__class__.__name__,
                    }
                )

        context = self.get_context_data()
        form = self.form_class(
            **{"queryset": self.object_list, **self.get_form_kwargs()}
        )
        if form.is_valid():
            approved_items = form.cleaned_data["choices"]
            for _i in context["object_list"]:
                if (not _i.checked and _i not in approved_items) or (
                    _i.checked and _i in approved_items
                ):  # nothing changed
                    continue

                _i.checked = not _i.checked
                _i.changed_by = self.request.user
                _i.save()

        return self.get(request, *args, **kwargs)


class LexemeApprovalView(ApprovalViewMixin):
    filterset_class = LexemeFilter
    model = Lexeme
    template_name = "lexeme_approval.html"
    paginate_by = 50
    title = _("Approving Lexemes")
    form_class = ApprovalMultipleChoiceForm


class RelationFilter(django_filters.FilterSet):
    class Meta:
        model = Lexeme
        fields = ["checked", "type"]

    STATUS_CHOICES = (
        (True, _("Yes")),
        (False, _("No")),
    )

    lookup_choices = [
        ("exact", _("Exact")),
        ("iexact", _("iExact")),
        ("contains", _("Contains")),
        ("icontains", _("iContains")),
        ("startswith", _("Starts with")),
        ("istartswith", _("iStarts with")),
        ("endswith", _("Ends with")),
        ("iendswith", _("iEnds with")),
        ("regex", _("Regex")),
        ("iregex", _("iRegex")),
    ]

    lexeme = LookupChoiceFilter(
        field_class=forms.CharField,
        label=_("Lexeme"),
        empty_label=None,
        lookup_choices=lookup_choices,
        method="filter_lexeme",
    )
    pos = ChoiceFilter(label=_("POS"), method="filter_pos")
    lexeme_side = ChoiceFilter(
        label="", method="filter_pos", choices=[("from", _("From")), ("to", _("To"))]
    )
    source = CharFilter(label=_("Source"), method="filter_source")
    checked = ChoiceFilter(choices=STATUS_CHOICES, label=_("Processed"))
    type = ChoiceFilter(choices=RELATION_TYPE_OPTIONS, label=_("Type"))

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        super().__init__(data, *args, **kwargs)

        pos = get_all_used_pos()
        self.form.fields["pos"].choices = zip(pos, pos)

    def filter_lexeme(self, queryset, name, value):
        lexeme_str, lookup_expr = (
            self.form.cleaned_data["lexeme"]
            if "lexeme" in self.form.cleaned_data
            else None
        )
        lexeme_side = self.data["lexeme_side"] if "lexeme_side" in self.data else None
        return self.filter_field(
            queryset, "lexeme", lexeme_str, lookup_expr, side=lexeme_side
        )

    def filter_pos(self, queryset, name, value):
        value = self.data["pos"] if "pos" in self.data else None
        return self.filter_field(queryset, "pos", value)

    def filter_field(self, queryset, name, value, lookup_expr="exact", side=None):
        filters = models.Q()
        if value:
            if not side or side == "from":
                filters |= models.Q(
                    **{"lexeme_from__{}__{}".format(name, lookup_expr): value}
                )
            if not side or side == "to":
                filters |= models.Q(
                    **{"lexeme_to__{}__{}".format(name, lookup_expr): value}
                )
        return queryset.filter(filters)

    def filter_source(self, queryset, name, value):
        source = self.data["source"] if "source" in self.data else None
        filters = models.Q()
        if source:
            filters |= models.Q(source__name__icontains=source)
        return queryset.filter(filters)


class RelationView(FilteredListView):
    filterset_class = RelationFilter
    model = Relation
    template_name = "relation_list.html"
    paginate_by = 50
    title = _("Relation Search")
    ordering = ["-lexeme_to"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class RelationExportView(RelationView):
    def render_to_response(self, context, **response_kwargs):
        filename = "{}-export.csv".format(
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)

        headers = [
            [
                "",
                _("From"),
                "",
                "",
                "",
                "",
                _("To"),
                "",
                "",
                "",
                "",
            ],
            [
                _("ID"),
                _("Lexeme ID"),
                _("Lexeme"),
                _("Language"),
                _("POS"),
                _("Contlex"),
                _("Lexeme ID"),
                _("Lexeme"),
                _("Language"),
                _("POS"),
                _("Contlex"),
            ],
        ]
        for header in headers:
            writer.writerow(header)

        for obj in (
            self.object_list.select_related("lexeme_from")
            .select_related("lexeme_to")
            .all()
        ):
            row = [
                obj.id,
                obj.lexeme_from.id,
                obj.lexeme_from.lexeme,
                obj.lexeme_from.language,
                obj.lexeme_from.pos,
                obj.lexeme_from.contlex,
                obj.lexeme_to.id,
                obj.lexeme_to.lexeme,
                obj.lexeme_to.language,
                obj.lexeme_to.pos,
                obj.lexeme_to.contlex,
            ]
            writer.writerow(row)

        return response


class RelationApprovalView(ApprovalViewMixin):
    filterset_class = RelationFilter
    model = Relation
    template_name = "relation_approval.html"
    paginate_by = 50
    title = _("Approving Relations")
    form_class = ApprovalMultipleChoiceForm

    def get_queryset(self):
        # prefetch to speed things up
        queryset = self.model.objects.prefetch_related("lexeme_from").prefetch_related(
            "lexeme_to"
        )
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs.distinct()


class StemDetailView(TitleMixin, DetailView):
    model = Stem
    template_name = "stem_detail.html"

    def get_title(self):
        return "%s (%s)" % (self.object.text, self.object.lexeme.lexeme)


class StemCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "stem_add.html"
    model = Stem
    form_class = StemForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(StemCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Stem"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(StemCreateView, self).form_valid(form)


class StemEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "stem_edit.html"
    model = Stem
    form_class = StemForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Stem"), self.object.text, self.object.lexeme)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(StemEditView, self).form_valid(form)


class StemDeleteView(LexemeDeleteFormMixin):
    template_name = "stem_confirm_delete.html"
    model = Stem

    def get_title(self):
        return "%s: %s" % (
            _("Delete Stem"),
            self.object,
        )


class SymbolListView(TitleMixin, ListView):
    model = Symbol
    template_name = "symbol_list.html"
    title = _("Symbol")


class LexemeMetadataCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "lexeme_metadata_add.html"
    model = LexemeMetadata
    form_class = LexemeMetadataForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs["lexeme_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(LexemeMetadataCreateView, self).get_context_data(**kwargs)
        context["lexeme"] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Metadata"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(LexemeMetadataCreateView, self).form_valid(form)


class LexemeMetadataEditView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    template_name = "lexeme_metadata_edit.html"
    model = LexemeMetadata
    form_class = LexemeMetadataForm

    def get_title(self):
        return "%s: %s (%s)" % (
            _("Edit Metadata"),
            self.object.text,
            self.object.lexeme,
        )

    def get_context_data(self, **kwargs):
        context = super(LexemeMetadataEditView, self).get_context_data(**kwargs)
        context["lexeme"] = self.object.lexeme
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(LexemeMetadataEditView, self).form_valid(form)


class LexemeMetadataDeleteView(LexemeDeleteFormMixin):
    template_name = "lexeme_metadata_confirm_delete.html"
    model = LexemeMetadata

    def get_title(self):
        return "%s: %s" % (
            _("Delete Metadata"),
            self.object,
        )


@login_required
def approve_lexeme(request, pk):
    lexeme = get_object_or_404(Lexeme, pk=pk)
    if request.method == "POST":
        lexeme.checked = True
        lexeme.changed_by = request.user
        lexeme.save()

    return HttpResponseRedirect(lexeme.get_absolute_url())


@login_required
def approve_relation(request, pk):
    relation = get_object_or_404(Relation, pk=pk)
    if request.method == "POST":
        relation.checked = True
        relation.changed_by = request.user
        relation.save()

    return HttpResponseRedirect(relation.get_absolute_url())


@login_required
def approve_stem(request, pk):
    stem = get_object_or_404(Stem, pk=pk)
    if request.method == "POST":
        stem.checked = True
        stem.changed_by = request.user
        stem.save()

    return HttpResponseRedirect(stem.get_absolute_url())


@login_required
def switch_relation(request, pk):
    relation = get_object_or_404(Relation, pk=pk)

    if request.method == "POST":
        form = FlipRelationForm(request.POST, relation=relation)
        if form.is_valid():
            relation.lexeme_from, relation.lexeme_to = (
                relation.lexeme_to,
                relation.lexeme_from,
            )
            relation.changed_by = request.user
            relation.save()

    return HttpResponseRedirect(relation.get_absolute_url())


@login_required
def reverse_relation(request, pk):
    relation = get_object_or_404(Relation, pk=pk)

    if request.method == "POST":
        form = ReverseRelationForm(request.POST, relation=relation)
        if form.is_valid():
            try:
                relation = Relation.objects.get(
                    lexeme_from=relation.lexeme_to, lexeme_to=relation.lexeme_from
                )
            except Relation.DoesNotExist:
                relation.pk = None
                relation.lexeme_from, relation.lexeme_to = (
                    relation.lexeme_to,
                    relation.lexeme_from,
                )
                relation.changed_by = request.user
                relation.save()

    return HttpResponseRedirect(relation.get_absolute_url())


class LexemeExportLexcView(LexemeView):
    def get_queryset(self):
        queryset = self.model.objects.prefetch_related("stem_set", "lexememetadata_set")
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs.distinct()

    def render_to_response(self, context, **response_kwargs):
        result = [
            (
                "".join(
                    (
                        obj.lexeme,
                        (
                            "+v{}".format(stem.order + 1)
                            if i > 0 or len(obj.stem_set.all()) > 1
                            else ""
                        ),
                        "+Hom{}".format(obj.homoId) if obj.homoId > 0 else "",
                        "+{}".format(
                            "N+{}".format(obj.pos) if obj.pos == "Prop" else obj.pos
                        ),
                        "".join(
                            [
                                (
                                    "+{}".format(md.text)
                                    if re.match(r"prop|np", md.text, re.I)
                                    else ""
                                )
                                for md in obj.lexememetadata_set.all()
                            ]
                        ),
                        ":{}".format(stem.text),
                    )
                ),
                "{}".format(stem.contlex),
                '"{}"'.format(stem.notes),
                ";",
            )
            for obj in self.object_list
            for i, stem in enumerate(obj.stem_set.order_by("order").all())
        ]

        result = [(re.sub(r"(\s|\.|\<|\>|\,)", r"%\1", _r) for _r in r) for r in result]
        result = [" ".join(r) for r in result]
        content = "\n".join(result)
        filename = "{}-export.lexc".format(
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )
        response = HttpResponse(content, content_type="text/plain")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)

        return response


class FileRequestView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    template_name = "file_request.html"
    model = FileRequest
    form_class = FileRequestForm

    def form_valid(self, form):
        form.instance.user = self.request.user

        clean = form.cleaned_data

        job_options = {"use_accepted": clean["use_accepted"]}

        file_request = FileRequest.objects.create(
            user=self.request.user,
            type=clean["type"],
            lang_source=clean["lang_source"],
            lang_target=clean["lang_target"],
            options=json.dumps(job_options),
        )

        lang_source = form.cleaned_data.get("lang_source")
        lang_target = form.cleaned_data.get("lang_target")

        process_file_request.delay(
            file_request_id=file_request.id,
            download_type=form.cleaned_data["type"],
            lang_source=lang_source.id,
            lang_target=lang_target.id if lang_target else None,
            options=job_options,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["files"] = FileRequest.objects.filter(
            user=self.request.user, deleted=False
        ).order_by("-created_at")
        return context

    def get_success_url(self):
        return reverse("file-request")

    def get_title(self):
        return _("Files")


@login_required
def download_file(request, pk):
    file_request = get_object_or_404(
        FileRequest,
        id=pk,
        user=request.user,
        status=DOWNLOAD_STATUS_COMPLETED,
    )

    tmp_storage = TemporaryFileStorage()

    file_path = tmp_storage.path(file_request.file.name)

    if not os.path.exists(file_path):
        raise Http404("File not found.")

    with open(file_path, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/zip")
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(file_path)}"'
        )
        return response


class LanguageParadigmListView(AdminStaffRequiredMixin, TitleMixin, ListView):
    model = LanguageParadigm
    template_name = "language_paradigm_list.html"
    context_object_name = "paradigms"

    def get_title(self):
        return _("Language Paradigms")


class LanguageParadigmCreateView(AdminStaffRequiredMixin, TitleMixin, CreateView):
    model = LanguageParadigm
    form_class = LanguageParadigmForm
    template_name = "language_paradigm_add.html"
    success_url = reverse_lazy("language-paradigm-list")

    def get_title(self):
        return _("Add Language Paradigm")


class LanguageParadigmUpdateView(AdminStaffRequiredMixin, TitleMixin, UpdateView):
    model = LanguageParadigm
    form_class = LanguageParadigmForm
    template_name = "language_paradigm_edit.html"
    success_url = reverse_lazy("language-paradigm-list")

    def get_title(self):
        return _("Edit Language Paradigm")


class LanguageParadigmDeleteView(AdminStaffRequiredMixin, TitleMixin, DeleteView):
    model = LanguageParadigm
    template_name = "language_paradigm_confirm_delete.html"
    success_url = reverse_lazy("language-paradigm-list")

    def get_title(self):
        return _("Delete Language Paradigm")
