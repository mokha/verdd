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
from django.shortcuts import get_object_or_404
from uralicNLP import uralicApi
from collections import defaultdict


class TitleMixin:
    title = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.get_title()
        return context

    def get_title(self):
        return self.title


class FilteredListView(TitleMixin, ListView):
    filterset_class = None

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
        return context


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
        range_from = self.data['range_from'] if 'range_from' in self.data else None  # get key
        range_to = self.data['range_to'] if 'range_to' in self.data else None  # get key

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


class ElementDetailView(TitleMixin, DetailView):
    model = Element
    template_name = 'element_detail.html'

    def get_title(self):
        return self.object


class MiniParadigmMixin:
    language = 'sms'

    MP_forms = {
        'N': ['+N+Pl+Nom',
              '+N+Sg+Ill',
              '+N+Sg+Loc',
              '+N+Pl+Gen'],
        'Adj': ['+A+Attr',
                '+A+Pl+Nom',
                '+A+Sg+Ill',
                '+A+Sg+Loc',
                '+A+Pl+Gen'],
        'V': ['+V+Ind+Prs+Sg3',
              '+V+Ind+Prs+ConNeg',
              '+V+Ind+Prs+Pl3',
              '+V+Ind+Prt+Pl3']
    }  # mini paradigms

    lemma = None

    def get_miniparadigm_forms(self):
        return self.MP_forms

    def get_language(self):
        return self.language

    def generate_forms(self, translation):
        generated_forms = defaultdict(list)

        MP_forms = self.get_miniparadigm_forms()
        if translation.pos in MP_forms:
            for f in MP_forms[translation.pos]:
                results = uralicApi.generate(translation.text + f, self.get_language())
                for r in results:
                    generated_forms[f].append(r[0].split('@')[0])
        generated_forms.default_factory = None

        return generated_forms


class TranslationDetailView(TitleMixin, MiniParadigmMixin, DetailView):
    model = Translation
    template_name = 'translation_detail.html'

    def get_context_data(self, **kwargs):
        context = super(TranslationDetailView, self).get_context_data(**kwargs)
        translation = self.object
        context['generated_miniparadigms'] = self.generate_forms(translation)
        return context

    def get_title(self):
        return "%s (%s)" % (self.object.text, self.object.element.lexeme)


#
# class SourceDetailView(DetailView):
#     model = Source
#     template_name = 'source_detail.html'
#
#
# class MiniParadigmDetailView(DetailView):
#     model = MiniParadigm
#     template_name = 'mini_paradigm_detail.html'


class ElementEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'element_edit.html'
    model = Element
    form_class = ElementForm

    def get_title(self):
        return "%s: %s" % (_("Edit"), self.object.lexeme)


class TranslationEditView(LoginRequiredMixin, MiniParadigmMixin, TitleMixin, UpdateView):
    template_name = 'translation_edit.html'
    model = Translation
    form_class = TranslationForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit translation"), self.object.text, self.object.element.lexeme)


class SourceEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'source_edit.html'
    model = Source
    form_class = SourceForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit source"), self.object.translation.text, self.object.translation.element.lexeme)


class MiniParadigmEditView(LoginRequiredMixin, MiniParadigmMixin, TitleMixin, UpdateView):
    template_name = 'mini_paradigm_edit.html'
    model = MiniParadigm
    form_class = MiniParadigmForm

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmEditView, self).get_context_data(**kwargs)
        translation = self.object.translation
        context['generated_miniparadigms'] = self.generate_forms(translation)
        return context

    def get_title(self):
        return "%s: %s (%s)" % (
            _("Edit mini paradigm"), self.object.translation.text, self.object.translation.element.lexeme)


class MiniParadigmCreateView(LoginRequiredMixin, MiniParadigmMixin, TitleMixin, CreateView):
    template_name = 'mini_paradigm_add.html'
    model = MiniParadigm
    form_class = MiniParadigmCreateForm

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmCreateView, self).get_context_data(**kwargs)
        # Pass the filterset to the template - it provides the form.
        translation = get_object_or_404(Translation,
                                        pk=self.kwargs['translation_id'])
        context['translation'] = translation
        context['generated_miniparadigms'] = self.generate_forms(translation)
        return context

    def get_title(self):
        translation = Translation.objects.get(pk=self.kwargs['translation_id'])
        return "%s: %s (%s)" % (
            _("Add mini paradigm"), translation.text, translation.element.lexeme)

    def form_valid(self, form):
        form.instance.translation = get_object_or_404(Translation,
                                                      pk=self.kwargs['translation_id'])
        return super().form_valid(form)
