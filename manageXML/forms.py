from .models import *
from django import forms
from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML
from .constants import *


class LexmeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s (%s)" % (obj.lexeme, obj.pos)


class LexemeForm(forms.ModelForm):
    lexeme = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Lexeme')}))
    pos = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('POS')}))
    contlex = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': _('Continuation Lexicon')}))
    type = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': _('Type')}))
    lemmaId = forms.CharField(required=False, label=_('Lemma ID'))
    inflexId = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': _('Inflex ID')}))
    inflexType = forms.ChoiceField(choices=(('', ''),) + INFLEX_TYPE_OPTIONS, required=False,
                                   label=_('Inflex Type'))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': _('Notes')}))
    checked = forms.BooleanField(required=False, label=_('Processed'))

    class Meta:
        model = Lexeme
        fields = ['lexeme', 'pos', 'contlex', 'type', 'lemmaId', 'inflexType', 'notes', 'checked']

    def __init__(self, *args, **kwargs):
        super(LexemeForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    "<h3>%s: %s</h3>" % (_("Lexeme"), "{{ form.instance.lexeme }}")),
                css_class=''
            ),
            Row(
                Column('lexeme', css_class='form-group col-md-6 mb-0'),
                Column('pos', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('contlex', css_class='form-group col-md-6 mb-0'),
                Column('type', css_class='form-group col-md-3 mb-0'),
                Column('inflexId', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('inflexType', css_class='form-group col-md-6 mb-0'),
                Column('lemmaId', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'notes',
            'checked',
            Submit('submit', 'Save')
        )

    def clean(self):
        self.cleaned_data = super(LexemeForm, self).clean()
        if self.cleaned_data['inflexType'] == '': self.cleaned_data['inflexType'] = None
        return self.cleaned_data


class RelationForm(forms.ModelForm):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': _('Notes')}))
    checked = forms.BooleanField(required=False, label=_('Processed'))

    class Meta:
        model = Relation
        fields = ['notes', 'checked']

    def __init__(self, *args, **kwargs):
        super(RelationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'notes',
            'checked',
            Submit('submit', 'Save')
        )


class SourceForm(forms.ModelForm):
    type = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Type')}))
    name = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Name')}))
    page = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': _('Page')}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': _('Notes')}))

    class Meta:
        model = Source
        fields = ['type', 'name', 'page', 'notes']

    def __init__(self, *args, **kwargs):
        super(SourceForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    "<h3>%s: %s</h3>" % (_("Source"), "{{ form.instance.name }}")),
                css_class=''
            ),
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('type', css_class='form-group col-md-3 mb-0'),
                Column('page', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            'notes',
            Submit('submit', 'Save')
        )


class MiniParadigmForm(forms.ModelForm):
    wordform = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Word form')}))
    msd = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Morphosyntactic description')}))

    class Meta:
        model = MiniParadigm
        fields = ['wordform', 'msd']

    def __init__(self, *args, **kwargs):
        super(MiniParadigmForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    "<h2>%s: (%s)</h2>" % (_("Edit Mini Paradigm"), "{{ form.instance }}")),
                css_class=''
            ),
            Row(
                Column('msd', css_class='form-group col-md-5 mb-0'),
                Column('wordform', css_class='form-group col-md-7 mb-0'),
                css_class='form-row'
            ),
            Submit('submit', 'Save')
        )


class MiniParadigmCreateForm(forms.ModelForm):
    wordform = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Word form')}))
    msd = forms.CharField(widget=forms.TextInput(attrs={'placeholder': _('Morphosyntactic description')}))

    class Meta:
        model = MiniParadigm
        fields = ['wordform', 'msd']

    def __init__(self, *args, **kwargs):
        super(MiniParadigmCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(

            Row(
                Column('msd', css_class='form-group col-md-5 mb-0'),
                Column('wordform', css_class='form-group col-md-7 mb-0'),
                css_class='form-row'
            ),
            Submit('submit', 'Save')
        )
