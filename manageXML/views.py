from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime
from django_filters import DateFromToRangeFilter, DateFilter, CharFilter, NumberFilter, ModelChoiceFilter, ChoiceFilter, \
    OrderingFilter, LookupChoiceFilter, DateRangeFilter
from django_filters.widgets import RangeWidget
import django_filters
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView, ModelFormMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.translation import gettext as _
from django.db.models import Q
from rest_framework import generics, response
from .serializers import *
import string
from .forms import *
from django.shortcuts import get_object_or_404
from collections import defaultdict
import csv
from .constants import INFLEX_TYPE_OPTIONS
from manageXML.inflector import Inflector
import operator
import logging

logger = logging.getLogger('verdd.manageXML')  # Get an instance of a logger
_inflector = Inflector()


class AdminStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff


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


class LexemeOrderingFilter(OrderingFilter):
    def filter(self, qs, value):
        if value and any('consonance' in v.lower() or 'assonance' in v.lower() for v in value):
            return qs.order_by(value[0], 'lexeme_lang')
        return super(LexemeOrderingFilter, self).filter(qs, value)


class LexemeFilter(django_filters.FilterSet):
    STATUS_CHOICES = (
        (True, _('Yes')),
        (False, _('No')),
    )

    ALPHABETS_CHOICES = list(enumerate(string.ascii_uppercase + 'ÄÅÖ'))
    ORDER_BY_FIELDS = {
        'pos': 'pos',
        'lexeme_lang': 'lexeme_lang',
        'consonance': 'consonance',
        'consonance_rev': 'consonance_rev',
        'assonance': 'assonance',
        'assonance_rev': 'assonance_rev',
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

    order_by = LexemeOrderingFilter(
        choices=(
            ('lexeme_lang', _('Lexeme')),
            ('-lexeme_lang', '%s (%s)' % (_('Lexeme'), _('descending'))),
            ('pos', _('POS')),
            ('-pos', '%s (%s)' % (_('POS'), _('descending'))),
            ('contlex', _('ContLex')),
            ('-contlex', '%s (%s)' % (_('ContLex'), _('descending'))),
            ('inflexType', _('inflexType')),
            ('-inflexType', '%s (%s)' % (_('inflexType'), _('descending'))),
            ('consonance', _('Consonance')),
            ('-consonance', '%s (%s)' % (_('Consonance'), _('descending'))),
            ('consonance_rev', _('revConsonance')),
            ('-consonance_rev', '%s (%s)' % (_('revConsonance'), _('descending'))),
            ('assonance', _('Assonance')),
            ('-assonance', '%s (%s)' % (_('Assonance'), _('descending'))),
            ('assonance_rev', _('RevAssonance')),
            ('-assonance_rev', '%s (%s)' % (_('RevAssonance'), _('descending'))),
        ),
        fields=ORDER_BY_FIELDS,
        label=_("Order by")
    )

    class Meta:
        model = Lexeme
        fields = ['lexeme', 'language', 'pos', 'contlex', 'inflexType', 'range_from', 'range_to', 'source']

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault('order', '+lexeme_lang')
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
        if order_by and order_by not in ['pos', 'lexeme_lang'] and order_by in order_by_options:
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
    @staticmethod
    def existing_forms(lexeme):
        MP_forms = lexeme.miniparadigm_set.all()
        return {form.msd: form.wordform for form in MP_forms}

    def generate_forms(self, lexeme):
        existing_MP_forms = MiniParadigmMixin.existing_forms(lexeme)
        MP_forms = _inflector.generate(lexeme.language, lexeme.lexeme, lexeme.pos)

        generated_forms = defaultdict(list)
        for f, r in MP_forms.items():
            if f in existing_MP_forms:  # if overridden by the user
                continue  # ignore it

            for _r in r:
                generated_forms[f].append(_r[0])
        generated_forms.default_factory = None
        return generated_forms

    def short_generate_forms(self, lexeme):
        existing_MP_forms = MiniParadigmMixin.existing_forms(lexeme)
        MP_forms = _inflector.generate_uralicNLP(lexeme.language, lexeme.lexeme, lexeme.pos)

        generated_forms = defaultdict(list)
        for f, r in MP_forms.items():
            if f in existing_MP_forms:  # if overridden by the user
                continue  # ignore it

            for _r in r:
                generated_forms[f].append(_r[0])
        generated_forms.default_factory = None
        return generated_forms


class LexemeCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'lexeme_add.html'
    model = Lexeme
    form_class = LexemeCreateForm

    def get_title(self):
        return "%s" % _("Add Lexeme")

    def form_valid(self, form):
        clean = form.cleaned_data
        lexeme = clean.get('lexeme').strip()

        self.object = form.save(commit=False)
        self.object.save()

        # check if affiliation exists in akusanat
        title = self.object.find_akusanat_affiliation()
        # link it
        if title:
            a, created = Affiliation.objects.get_or_create(lexeme=self.object, title=title)
        form.instance.changed_by = self.request.user
        return HttpResponseRedirect(self.get_success_url())


class LexemeDetailView(TitleMixin, MiniParadigmMixin, DetailView):
    model = Lexeme
    template_name = 'lexeme_detail.html'

    def get_around_objects(self, request, object, n=5):
        filter = LexemeFilter(request.GET, queryset=Lexeme.objects.all())
        qs_list = list(filter.qs)

        next_objects, prev_objects = [], []

        try:
            lexeme_position = qs_list.index(object)
            next_objects = qs_list[lexeme_position + 1:lexeme_position + 1 + n]

            prev_objects_len = max(0, lexeme_position - n)
            prev_objects = qs_list[prev_objects_len:lexeme_position]
        except:
            pass

        return prev_objects, next_objects

    def get_context_data(self, **kwargs):
        context = super(LexemeDetailView, self).get_context_data(**kwargs)
        context['generated_miniparadigms'] = self.generate_forms(self.object)
        context['short_generated_miniparadigms'] = self.short_generate_forms(self.object)

        last_lexeme = self.request.GET.get('lastlexeme', None)  # is last lexeme passed?
        last_lexeme = Lexeme.objects.get(
            pk=last_lexeme) if last_lexeme else self.object  # if not, use the current object

        context['prev_objects'], context['next_objects'] = self.get_around_objects(request=self.request,
                                                                                   object=last_lexeme,
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
            title = self.object.find_akusanat_affiliation()
            # link it
            if title:
                a, created = Affiliation.objects.get_or_create(lexeme=form.instance, title=title)
        form.instance.changed_by = self.request.user
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
        form.instance.changed_by = self.request.user
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

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(SourceEditView, self).form_valid(form)


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

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(MiniParadigmEditView, self).form_valid(form)


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
        form.instance.changed_by = self.request.user
        return super(MiniParadigmCreateView).form_valid(form)


class RelationCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'relation_add.html'
    model = Relation
    form_class = RelationCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super(RelationCreateView, self).dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super(RelationCreateView, self).get_form(form_class)

        lexeme_from = get_object_or_404(Lexeme, pk=self.kwargs['lexeme_id'])
        form.instance.lexeme_from = lexeme_from

        if form.is_valid():
            data = form.cleaned_data
            form.instance.lexeme_to = Lexeme.objects.get(pk=data.get('lexeme_to'))
        return form

    def get_title(self):
        return "%s %s" % (_("Add Relation from"), self.lexeme)

    def get_context_data(self, **kwargs):
        context = super(RelationCreateView, self).get_context_data(**kwargs)
        context['lexeme'] = self.lexeme
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationCreateView, self).form_valid(form)


class AffiliationCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'affiliation_add.html'
    model = Affiliation
    form_class = AffiliationCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AffiliationCreateView, self).get_context_data(**kwargs)
        context['lexeme'] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Affiliation"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(AffiliationCreateView, self).form_valid(form)


class AffiliationEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'affiliation_edit.html'
    model = Affiliation
    form_class = AffiliationEditForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Affiliation"), self.object.title, self.object.lexeme)

    def get_context_data(self, **kwargs):
        context = super(AffiliationEditView, self).get_context_data(**kwargs)
        context['lexeme'] = self.object.lexeme
        return context

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(AffiliationEditView, self).form_valid(form)


class SourceCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'source_add.html'
    model = Source
    form_class = SourceCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs['relation_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SourceCreateView, self).get_context_data(**kwargs)
        context['relation'] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (_("Add source"), self.object,)

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(SourceCreateView, self).form_valid(form)


class DeleteFormMixin(LoginRequiredMixin, TitleMixin, DeleteView):
    def get_context_data(self, **kwargs):
        context = super(DeleteFormMixin, self).get_context_data(**kwargs)
        context.update({
            'form': DeleteFormBase(),
        })
        return context

    def delete(self, request, *args, **kwargs):
        object = self.get_object()
        logger.info("[DELETE] %s: %s (%d) by %s" % (object.__class__.__name__, object, object.id, self.request.user))
        return super(DeleteFormMixin, self).delete(request, *args, **kwargs)


class LexemeDeleteFormMixin(DeleteFormMixin):
    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(LexemeDeleteFormMixin, self).get_context_data(**kwargs)
        context['lexeme'] = self.lexeme
        return context

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class LexemeDeleteView(DeleteFormMixin):
    template_name = 'lexeme_confirm_delete.html'
    model = Lexeme

    def get_success_url(self):
        return reverse('index')

    def get_title(self):
        return "%s: %s" % (_("Delete lexeme"), self.object,)


class RelationDeleteView(LexemeDeleteFormMixin):
    template_name = 'relation_confirm_delete.html'
    model = Relation

    def get_title(self):
        return "%s: %s" % (_("Delete Relation"), self.object,)


class AffiliationDeleteView(LexemeDeleteFormMixin):
    template_name = 'affiliation_confirm_delete.html'
    model = Affiliation

    def get_title(self):
        return "%s: %s" % (_("Delete Affiliation"), self.object,)


class SourceDeleteView(LexemeDeleteFormMixin):
    template_name = 'source_confirm_delete.html'
    model = Source

    def get_title(self):
        return "%s: %s" % (_("Delete Source"), self.object,)


class ExampleCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'example_add.html'
    model = Example
    form_class = ExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ExampleCreateView, self).get_context_data(**kwargs)
        context['lexeme'] = self.lexeme
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Example"), self.lexeme)

    def form_valid(self, form):
        form.instance.lexeme = self.lexeme
        form.instance.changed_by = self.request.user
        return super(ExampleCreateView, self).form_valid(form)


class ExampleEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'example_edit.html'
    model = Example
    form_class = ExampleForm

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Example"), self.object.text, self.object.lexeme)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(ExampleEditView, self).form_valid(form)


class ExampleDeleteView(LexemeDeleteFormMixin):
    template_name = 'example_confirm_delete.html'
    model = Example

    def get_title(self):
        return "%s: %s" % (_("Delete Example"), self.object,)


class RelationExampleCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'relation_example_add.html'
    model = RelationExample
    form_class = RelationExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs['relation_id'])
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationExampleCreateView, self).get_form_kwargs()
        kwargs['relation'] = self.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationExampleCreateView, self).get_context_data(**kwargs)
        context['relation'] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Example"), self.relation)

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(RelationExampleCreateView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataCreateView(LoginRequiredMixin, TitleMixin, CreateView):
    template_name = 'relation_metadata_add.html'
    model = RelationMetadata
    form_class = RelationMetadataForm

    def dispatch(self, request, *args, **kwargs):
        self.relation = get_object_or_404(Relation, pk=kwargs['relation_id'])
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationMetadataCreateView, self).get_form_kwargs()
        kwargs['relation'] = self.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationMetadataCreateView, self).get_context_data(**kwargs)
        context['relation'] = self.relation
        return context

    def get_title(self):
        return "%s: %s" % (_("Add Data"), self.relation)

    def form_valid(self, form):
        form.instance.relation = self.relation
        form.instance.changed_by = self.request.user
        return super(RelationMetadataCreateView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationExampleEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'relation_example_edit.html'
    model = RelationExample
    form_class = RelationExampleForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationExampleEditView, self).get_form_kwargs()
        kwargs['relation'] = self.object.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationExampleEditView, self).get_context_data(**kwargs)
        context['relation'] = self.object.relation
        return context

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Example"), self.object.text, self.object.relation)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationExampleEditView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataEditView(LoginRequiredMixin, TitleMixin, UpdateView):
    template_name = 'relation_metadata_edit.html'
    model = RelationMetadata
    form_class = RelationMetadataForm

    def dispatch(self, request, *args, **kwargs):
        self.lexeme = get_object_or_404(Lexeme, pk=kwargs['lexeme_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs = super(RelationMetadataEditView, self).get_form_kwargs()
        kwargs['relation'] = self.object.relation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(RelationMetadataEditView, self).get_context_data(**kwargs)
        context['relation'] = self.object.relation
        return context

    def get_title(self):
        return "%s: %s (%s)" % (_("Edit Data"), self.object.text, self.object.relation)

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(RelationMetadataEditView, self).form_valid(form)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationExampleDeleteView(LexemeDeleteFormMixin):
    template_name = 'relation_example_confirm_delete.html'
    model = RelationExample

    def get_title(self):
        return "%s: %s" % (_("Delete Example"), self.object,)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class RelationMetadataDeleteView(LexemeDeleteFormMixin):
    template_name = 'relation_metadata_confirm_delete.html'
    model = RelationMetadata

    def get_title(self):
        return "%s: %s" % (_("Delete Data"), self.object,)

    def get_success_url(self):
        return self.lexeme.get_absolute_url()


class LexemeSearchView(generics.ListAPIView):
    serializer_class = LexemeSerializer

    def get_queryset(self):
        query = self.request.query_params.get('q', None)
        if query is not None and query:
            filter_Q = Q(lexeme__icontains=query)
            if query.isdigit() and int(query) > 0:
                filter_Q |= Q(id=query)
            return Lexeme.objects.filter(filter_Q)
        return Lexeme.objects.none()


class HistorySearchView(TitleMixin, ListView, AdminStaffRequiredMixin):
    template_name = 'history_list.html'
    form_class = HistoryForm
    title = _("Lexeme History Search")
    model = HistoricalRecords
    query_model = Lexeme
    paginate_by = 50

    query_model_options = {
        'lexeme': Lexeme,
        'relation': Relation,
    }

    def get_context_data(self, *args, **kwargs):
        # Just include the form
        context = super(HistorySearchView, self).get_context_data(*args, **kwargs)
        context['form'] = self.form_class(self.request.GET)
        return context

    def get_queryset(self):
        object_list = self.query_model.history.none()
        if self.request.GET:
            form = self.form_class(self.request.GET)
            if form.is_valid():
                self.query_model = self.query_model_options[form.cleaned_data['model_class']]

                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']

                object_list = self.query_model.history \
                    .filter(Q(history_date__gte=start_date) & Q(history_date__lte=end_date)) \
                    .order_by("-history_date")
        return object_list
