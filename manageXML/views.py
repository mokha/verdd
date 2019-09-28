from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime
from django_filters import DateFromToRangeFilter, DateFilter, CharFilter, NumberFilter, ModelChoiceFilter, ChoiceFilter, \
    OrderingFilter, LookupChoiceFilter
from django_filters.widgets import RangeWidget
import django_filters
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext as _
import string
from .forms import *
from django.shortcuts import get_object_or_404
from uralicNLP import uralicApi
from collections import defaultdict
import csv
from .constants import INFLEX_TYPE_OPTIONS
from wiki.semantic_api import SemanticAPI


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


class LexemeFilter(django_filters.FilterSet):
    STATUS_CHOICES = (
        (True, _('Yes')),
        (False, _('No')),
    )

    ALPHABETS_CHOICES = list(enumerate(string.ascii_uppercase + 'ÄÅÖ'))
    ORDER_BY_FIELDS = {
        'pos': 'pos',
        'lexeme': 'lexeme',
        'consonance': 'consonance',
        'consonance_rev': 'revConsonance',
        'assonance': 'assonance',
        'assonance_rev': 'revAssonance',
    }

    lookup_choices = [
        ('exact', _('Exact')),
        ('iexact', _('iExact')),
        ('contains', _('Contains')),
        ('icontains', _('iContains')),
        ('startswith', _('Starts with')),
        ('istartswith', _('iStarts with')),
        ('endswith', _('Ends with')),
        ('iendswith', _('iEnds with')),
        ('regex', _('Regex')),
        ('iregex', _('iRegex')),
    ]

    lexeme = LookupChoiceFilter(field_class=forms.CharField, label=_('Lexeme'), empty_label=None,
                                lookup_choices=lookup_choices)
    language = ChoiceFilter(label=_('Language'))
    pos = ChoiceFilter(label=_('POS'))
    inflexType = ChoiceFilter(choices=INFLEX_TYPE_OPTIONS, label=_('Inflex Type'))
    contlex = CharFilter(label=_('Contlex'), lookup_expr='icontains')
    range_from = ChoiceFilter(choices=ALPHABETS_CHOICES, label=_('Range from'), method='filter_range')
    range_to = ChoiceFilter(choices=ALPHABETS_CHOICES, label=_('Range to'), method='filter_range')
    checked = ChoiceFilter(choices=STATUS_CHOICES, label=_('Processed'))
    source = CharFilter(label=_('Source'), method='source_filter')

    order_by = OrderingFilter(
        choices=(
            ('lexeme', _('Lexeme')),
            ('-lexeme', '%s (%s)' % (_('Lexeme'), _('descending'))),
            ('pos', _('POS')),
            ('-pos', '%s (%s)' % (_('POS'), _('descending'))),
            ('contlex', _('ContLex')),
            ('-contlex', '%s (%s)' % (_('ContLex'), _('descending'))),
            ('inflexType', _('inflexType')),
            ('-inflexType', '%s (%s)' % (_('inflexType'), _('descending'))),
            ('consonance', _('Consonance')),
            ('-consonance', '%s (%s)' % (_('Consonance'), _('descending'))),
            ('revConsonance', _('revConsonance')),
            ('-revConsonance', '%s (%s)' % (_('revConsonance'), _('descending'))),
            ('assonance', _('Assonance')),
            ('-assonance', '%s (%s)' % (_('Assonance'), _('descending'))),
            ('revAssonance', _('RevAssonance')),
            ('-revAssonance', '%s (%s)' % (_('RevAssonance'), _('descending'))),
        ),
        fields=ORDER_BY_FIELDS,
        label=_("Order by")
    )

    class Meta:
        model = Lexeme
        fields = ['lexeme', 'language', 'pos', 'contlex', 'inflexType', 'range_from', 'range_to', 'source']

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault('order', '+lexeme')
        super().__init__(data, *args, **kwargs)

        self.form.fields['language'].choices = set(
            [(p['language'], p['language']) for p in Lexeme.objects.all().values('language')])
        self.form.fields['pos'].choices = set([(p['pos'], p['pos']) for p in Lexeme.objects.all().values('pos')])

    def filter_range(self, queryset, name, value):
        # transform datetime into timestamp
        range_from = self.data['range_from'] if 'range_from' in self.data else None  # get key
        range_to = self.data['range_to'] if 'range_to' in self.data else None  # get key

        range_from = int(range_from) if range_from else 0
        range_to = int(range_to) if range_to else len(LexemeFilter.ALPHABETS_CHOICES) - 1

        if range_from > range_to:
            return queryset.none()

        filters = models.Q()
        for i in range(range_from, range_to + 1):
            filters |= models.Q(
                lexeme__istartswith=LexemeFilter.ALPHABETS_CHOICES[i][1],
            )

        return queryset.filter(filters)

    def source_filter(self, queryset, name, value):
        source = self.data['source'] if 'source' in self.data else None  # get key

        filters = models.Q()
        if source:
            relations_with_source = Relation.objects.filter(source__name__icontains=source)
            filters = Q(lexeme_from_lexeme_set__in=relations_with_source) | Q(
                lexeme_to_lexeme_set__in=relations_with_source)
        return queryset.filter(filters)


class LexemeView(FilteredListView):
    filterset_class = LexemeFilter
    model = Lexeme
    template_name = 'lexeme_list.html'
    paginate_by = 50
    title = _("Homepage")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_by = self.request.GET.get('order_by', None)
        order_by = order_by[1:] if order_by and order_by.startswith('-') else order_by
        order_by_options = dict([[v, k] for k, v in self.filterset_class.ORDER_BY_FIELDS.items()])
        if order_by and order_by not in ['pos', 'lexeme'] and order_by in order_by_options:
            context['order_by'] = order_by_options[order_by]
        return context


class LexemeExportView(LexemeView):
    def render_to_response(self, context, **response_kwargs):
        filename = "{}-export.csv".format(datetime.datetime.now().replace(microsecond=0).isoformat())

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

        writer = csv.writer(response)
        header = [_('ID'), _('Language'), _('Lexeme'), _('POS'), _('Contlex'), _('Inflex Type'), ]
        if 'order_by' in context:
            header += [_('Ordered By')]
        writer.writerow(header)

        for obj in self.object_list:
            row = [
                obj.id,
                obj.language,
                obj.lexeme,
                obj.pos,
                obj.contlex,
                obj.inflexType_str()
            ]
            if 'order_by' in context:
                row += [getattr(obj, context['order_by'])]
            writer.writerow(row)

        return response


class HistoryExportView:
    def nothing(self):
        Lexeme.history.all()


class MiniParadigmMixin:
    MP_forms = {
        'N': ['N+Pl+Nom',
              'N+Sg+Ill',
              'N+Sg+Loc',
              'N+Pl+Gen'],
        'Adj': ['A+Attr',
                'A+Pl+Nom',
                'A+Sg+Ill',
                'A+Sg+Loc',
                'A+Pl+Gen'],
        'V': ['V+Ind+Prs+Sg3',
              'V+Ind+Prs+ConNeg',
              'V+Ind+Prs+Pl3',
              'V+Ind+Prt+Pl3']
    }  # mini paradigms

    lemma = None

    def get_miniparadigm_forms(self):
        return self.MP_forms

    @staticmethod
    def existing_forms(lexeme):
        MP_forms = lexeme.miniparadigm_set.all()
        return {form.msd: form.wordform for form in MP_forms}

    def generate_forms(self, lexeme):
        generated_forms = defaultdict(list)
        MP_forms = self.get_miniparadigm_forms()
        existing_MP_forms = MiniParadigmMixin.existing_forms(lexeme)
        if lexeme.pos in MP_forms:
            for f in MP_forms[lexeme.pos]:
                if f in existing_MP_forms:  # if overridden by the user
                    continue  # ignore it

                results = uralicApi.generate(lexeme.lexeme + '+' + f, lexeme.language)
                for r in results:
                    generated_forms[f].append(r[0].split('@')[0])
        generated_forms.default_factory = None
        return generated_forms


class LexemeDetailView(TitleMixin, MiniParadigmMixin, DetailView):
    model = Lexeme
    template_name = 'lexeme_detail.html'

    def get_around_objects(self, request, object, n=5):
        filter = LexemeFilter(request.GET, queryset=Lexeme.objects.all())
        qs_list = list(filter.qs)

        lexeme_position = qs_list.index(object)
        next_objects = qs_list[lexeme_position + 1:lexeme_position + 1 + n]

        prev_objects_len = max(0, lexeme_position - n)
        prev_objects = qs_list[prev_objects_len:lexeme_position]

        return prev_objects, next_objects

    def get_context_data(self, **kwargs):
        context = super(LexemeDetailView, self).get_context_data(**kwargs)
        context['generated_miniparadigms'] = self.generate_forms(self.object)

        context['prev_objects'], context['next_objects'] = self.get_around_objects(request=self.request,
                                                                                   object=self.object,
                                                                                   n=25)
        return context

    def get_title(self):
        return self.object


class LexemeEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'lexeme_edit.html'
    model = Lexeme
    form_class = LexemeForm

    def get_title(self):
        return "%s: %s" % (_("Edit"), self.object.lexeme)

    def form_valid(self, form):
        initial = form.initial
        clean = form.cleaned_data

        old_lexeme = initial.get('lexeme').strip()
        new_lexeme = clean.get('lexeme').strip()

        if new_lexeme != old_lexeme:  # they are different lexemes
            # delete existing affiliations
            form.instance.affiliation_set.all().delete()

            # check if new affiliation exists
            semAPI = SemanticAPI()
            r1 = semAPI.ask(query=(
                '[[%s:%s]]' % (form.instance.language.capitalize(), new_lexeme), '?Category', '?POS', '?Lang',
                '?Contlex')
            )

            if 'query' in r1 and 'results' in r1['query'] and r1['query']['results']:
                title, info = r1['query']['results'].popitem()

                # link it
                if title:
                    a, created = Affiliation.objects.get_or_create(lexeme=form.instance, title=title)

        return super(LexemeEditView, self).form_valid(form)


class RelationDetailView(TitleMixin, DetailView):
    model = Relation
    template_name = 'relation_detail.html'

    def get_context_data(self, **kwargs):
        context = super(RelationDetailView, self).get_context_data(**kwargs)
        return context

    def get_title(self):
        return "%s (%s)" % (self.object.lexeme_from.lexeme, self.object.lexeme_to.lexeme)


class RelationEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'relation_edit.html'
    model = Relation
    form_class = RelationForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Relation"), self.object.lexeme_from.lexeme, self.object.lexeme_to.lexeme)

    def form_valid(self, form):
        return super(RelationEditView, self).form_valid(form)


class SourceDetailView(DetailView):
    model = Source
    template_name = 'source_detail.html'


class SourceEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'source_edit.html'
    model = Source
    form_class = SourceForm

    def get_title(self):
        return "%s: %s" % (_("Edit source"), self.object.relation,)


class MiniParadigmEditView(LoginRequiredMixin, MiniParadigmMixin, TitleMixin, UpdateView):
    template_name = 'mini_paradigm_edit.html'
    model = MiniParadigm
    form_class = MiniParadigmForm

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmEditView, self).get_context_data(**kwargs)
        # Pass the filterset to the template - it provides the form.
        lexeme = get_object_or_404(Lexeme,
                                   pk=self.object.lexeme.id)
        context['lexeme'] = lexeme
        context['generated_miniparadigms'] = self.generate_forms(lexeme)
        return context

    def get_title(self):
        return "%s: %s" % (
            _("Edit mini paradigm"), self.object.lexeme.lexeme)


class MiniParadigmCreateView(LoginRequiredMixin, MiniParadigmMixin, TitleMixin, CreateView):
    template_name = 'mini_paradigm_add.html'
    model = MiniParadigm
    form_class = MiniParadigmCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MiniParadigmCreateView, self).get_context_data(**kwargs)
        context['lexeme'] = self.lexeme
        context['generated_miniparadigms'] = self.generate_forms(self.lexeme)
        return context

    def get_title(self):
        lexeme = Lexeme.objects.get(pk=self.kwargs['lexeme_id'])
        return "%s: %s" % (
            _("Add mini paradigm"), lexeme.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        return super().form_valid(form)
