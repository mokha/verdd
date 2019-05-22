from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.loader import get_template
import datetime


# Create your views here.

def index(request):
    now = datetime.datetime.now()
    return render(request, 'base.html', {'current_date': now})
