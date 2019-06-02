from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime
from django_filters import DateFromToRangeFilter, DateFilter, CharFilter, NumberFilter, ModelChoiceFilter, ChoiceFilter
from django_filters.widgets import RangeWidget
import django_filters
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext as _
import string
from .models import *
from .forms import *


class FilteredListView(ListView):
    filterset_class = None
    title = None

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
        context['filterset'] = self.filterset
        context['title'] = self.get_title()
        return context

    def get_title(self):
        return self.title


class ElementFilter(django_filters.FilterSet):
    STATUS_CHOICES = (
        (True, _('Yes')),
        (False, _('No')),
    )

    ALPHABETS_CHOICES = list(enumerate(string.ascii_uppercase + 'ÄÅÖ'))

    checked = ChoiceFilter(choices=STATUS_CHOICES, label=_('Processed'))
    range_from = ChoiceFilter(choices=ALPHABETS_CHOICES, label=_('Range from'), method='filter_range')
    range_to = ChoiceFilter(choices=ALPHABETS_CHOICES, label=_('Range to'), method='filter_range')

    class Meta:
        model = Element
        fields = ['lexeme', 'pos', 'checked', 'range_from', 'range_to']

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault('order', '+lexeme')
        super().__init__(data, *args, **kwargs)

    def filter_range(self, queryset, name, value):
        # transform datetime into timestamp
        range_from = self.data['range_from']  # get key
        range_to = self.data['range_to']  # get key

        range_from = int(range_from) if range_from else 0
        range_to = int(range_to) if range_to else len(ElementFilter.ALPHABETS_CHOICES) - 1

        if range_from > range_to:
            return queryset.none()

        filters = models.Q()
        for i in range(range_from, range_to + 1):
            filters |= models.Q(
                lexeme__istartswith=ElementFilter.ALPHABETS_CHOICES[i][1],
            )

        return queryset.filter(filters)


class ElementView(FilteredListView):
    filterset_class = ElementFilter
    model = Element
    template_name = 'element_list.html'
    paginate_by = 50
    ordering = ['lexeme']  # -id
    title = _("Homepage")


class ElementDetailView(DetailView):
    model = Element
    template_name = 'element_detail.html'


class TranslationDetailView(DetailView):
    model = Translation
    template_name = 'translation_detail.html'


class SourceDetailView(DetailView):
    model = Source
    template_name = 'source_detail.html'


class MiniParadigmDetailView(DetailView):
    model = MiniParadigm
    template_name = 'mini_paradigm_detail.html'


class ElementEditView(LoginRequiredMixin, UpdateView):
    template_name = 'element_edit.html'
    model = Element
    form_class = ElementForm


class TranslationEditView(LoginRequiredMixin, UpdateView):
    template_name = 'translation_edit.html'
    model = Translation
    form_class = TranslationForm


class SourceEditView(LoginRequiredMixin, UpdateView):
    template_name = 'source_edit.html'
    model = Source
    form_class = SourceForm


class MiniParadigmEditView(LoginRequiredMixin, UpdateView):
    template_name = 'mini_paradigm_edit.html'
    model = MiniParadigm
    form_class = MiniParadigmForm


class MiniParadigmCreateView(LoginRequiredMixin, CreateView):
    template_name = 'mini_paradigm_add.html'
    model = MiniParadigm
    form_class = MiniParadigmCreateForm
