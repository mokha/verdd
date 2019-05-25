from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime
import django_filters
from django.views.generic.list import ListView
from manageXML.models import *


class FilteredListView(ListView):
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
    class Meta:
        model = Element
        fields = ['lexeme', 'pos']

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault('order', '+lexeme')
        super().__init__(data, *args, **kwargs)


class ElementView(FilteredListView):
    filterset_class = ElementFilter
    model = Element
    template_name = 'index.html'
    paginate_by = 50
    ordering = ['-id']
