from .models import *
from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML, Button
from .constants import *
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count


class LanguageChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s (%s)" % (obj.name, obj.id)


class LexemeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s (%s)" % (obj.lexeme, obj.pos)


class LexemeForm(forms.ModelForm):
    lexeme = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Lexeme")}))
    specification = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Specification")}),
    )
    pos = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("POS")}))
    homoId = forms.IntegerField(required=True, label=_("Homonym ID"), initial=0)
    contlex = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Continuation Lexicon")}),
    )
    type = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Type")})
    )
    lemmaId = forms.CharField(required=False, label=_("Lemma ID"))
    inflexId = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Inflex ID")})
    )
    inflexType = forms.ChoiceField(
        choices=(("", ""),) + INFLEX_TYPE_OPTIONS,
        required=False,
        label=_("Inflex Type"),
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )
    checked = forms.BooleanField(required=False, label=_("Processed"))

    class Meta:
        model = Lexeme
        fields = [
            "lexeme",
            "pos",
            "homoId",
            "contlex",
            "type",
            "lemmaId",
            "inflexType",
            "notes",
            "checked",
            "specification",
        ]

    def __init__(self, *args, **kwargs):
        super(LexemeForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML("<h3>%s: %s</h3>" % (_("Lexeme"), "{{ form.instance.lexeme }}")),
                css_class="",
            ),
            Row(
                Column("lexeme", css_class="col-md-6 mb-3"),
                Column("pos", css_class="col-md-3 mb-3"),
                Column("homoId", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            Row(
                Column("contlex", css_class="col-md-6 mb-3"),
                Column("type", css_class="col-md-3 mb-3"),
                Column("inflexId", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            Row(
                Column("specification", css_class="col-md-5 mb-3"),
                Column("inflexType", css_class="col-md-3 mb-3"),
                Column("lemmaId", css_class="col-md-4 mb-3"),
                css_class="row",
            ),
            "notes",
            "checked",
            Submit("submit", _("Save")),
        )

    def clean(self):
        self.cleaned_data = super(LexemeForm, self).clean()
        if self.cleaned_data["inflexType"] == "":
            self.cleaned_data["inflexType"] = None
        return self.cleaned_data


class LexemeCreateForm(LexemeForm):
    language = LanguageChoiceField(
        queryset=Language.objects.all(), required=True, label=_("Languages")
    )

    class Meta:
        model = Lexeme
        fields = [
            "lexeme",
            "language",
            "pos",
            "homoId",
            "contlex",
            "type",
            "lemmaId",
            "inflexType",
            "notes",
            "checked",
            "specification",
        ]

    def __init__(self, *args, **kwargs):
        super(LexemeForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("lexeme", css_class="col-md-3 mb-3"),
                Column("language", css_class="col-md-3 mb-3"),
                Column("pos", css_class="col-md-3 mb-3"),
                Column("homoId", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            Row(
                Column("contlex", css_class="col-md-6 mb-3"),
                Column("type", css_class="col-md-3 mb-3"),
                Column("inflexId", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            Row(
                Column("specification", css_class="col-md-5 mb-3"),
                Column("inflexType", css_class="col-md-3 mb-3"),
                Column("lemmaId", css_class="col-md-4 mb-3"),
                css_class="row",
            ),
            "notes",
            "checked",
            Submit("submit", _("Save")),
        )


class RelationForm(forms.ModelForm):
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )
    checked = forms.BooleanField(required=False, label=_("Processed"))

    class Meta:
        model = Relation
        fields = ["type", "notes", "checked"]

    def __init__(self, *args, **kwargs):
        super(RelationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "type", "notes", "checked", Submit("submit", _("Save"))
        )


class RelationCreateForm(forms.ModelForm):
    lexeme_to = forms.CharField(
        required=False,
        label=_("To"),
        widget=forms.Select(
            attrs={
                "class": "lexeme-autocomplete",
            }
        ),
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = Relation
        fields = [
            "type",
            "notes",
            "checked",
        ]

    def __init__(self, *args, **kwargs):
        type = forms.ChoiceField(
            required=True, choices=RELATION_TYPE_OPTIONS, label=_("Type")
        )

        super(RelationCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(HTML("<h4>%s: %s</h4>" % (_("From"), "{{ lexeme }}")), css_class=""),
            "lexeme_to",
            "type",
            "notes",
            Submit("submit", _("Save")),
        )


class SourceForm(forms.ModelForm):
    type = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Type")}))
    name = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Name")}))
    page = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Page")})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = Source
        fields = ["type", "name", "page", "notes"]

    def __init__(self, *args, **kwargs):
        super(SourceForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML("<h3>%s: %s</h3>" % (_("Source"), "{{ form.instance.name }}")),
                css_class="",
            ),
            Row(
                Column("name", css_class="col-md-6 mb-3"),
                Column("type", css_class="col-md-3 mb-3"),
                Column("page", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            "notes",
            Submit("submit", _("Save")),
        )


class SourceCreateForm(forms.ModelForm):
    type = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Type")}))
    name = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Name")}))
    page = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Page")})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = Source
        fields = ["type", "name", "page", "notes"]

    def __init__(self, *args, **kwargs):
        super(SourceCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-md-6 mb-3"),
                Column("type", css_class="col-md-3 mb-3"),
                Column("page", css_class="col-md-3 mb-3"),
                css_class="row",
            ),
            "notes",
            Submit("submit", _("Save")),
        )


class AffiliationCreateForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Title")}))
    link = forms.URLField(widget=forms.URLInput(attrs={"placeholder": _("URL")}))
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )
    checked = forms.BooleanField(required=False, label=_("Approved"))

    class Meta:
        model = Affiliation
        fields = ["title", "link", "type", "checked", "notes"]

    def __init__(self, *args, **kwargs):
        self.type = forms.ChoiceField(
            choices=AFFILIATION_TYPES, required=True, label=_("Type")
        )

        super(AffiliationCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "title", "link", "type", "checked", "notes", Submit("submit", _("Save"))
        )


class AffiliationEditForm(forms.ModelForm):
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )
    checked = forms.BooleanField(required=False, label=_("Approved"))

    class Meta:
        model = Affiliation
        fields = ["checked", "notes"]

    def __init__(self, *args, **kwargs):
        super(AffiliationEditForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    '<h3>%s: <a href="%s">%s</a></h3>'
                    % (
                        dict(AFFILIATION_TYPES)[self.instance.type],
                        self.instance.link,
                        self.instance.title,
                    )
                ),
                css_class="",
            ),
            "title",
            "link",
            "type",
            "checked",
            "notes",
            Submit("submit", _("Save")),
        )


class MiniParadigmForm(forms.ModelForm):
    wordform = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": _("Word form")})
    )
    msd = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": _("Morphosyntactic description")})
    )

    class Meta:
        model = MiniParadigm
        fields = ["wordform", "msd"]

    def __init__(self, *args, **kwargs):
        super(MiniParadigmForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    "<h2>%s: (%s)</h2>"
                    % (_("Edit Mini Paradigm"), "{{ form.instance }}")
                ),
                css_class="",
            ),
            Row(
                Column("msd", css_class="col-md-5 mb-3"),
                Column("wordform", css_class="col-md-7 mb-3"),
                css_class="row",
            ),
            Submit("submit", _("Save")),
        )


class MiniParadigmCreateForm(forms.ModelForm):
    wordform = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": _("Word form")})
    )
    msd = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": _("Morphosyntactic description")})
    )

    class Meta:
        model = MiniParadigm
        fields = ["wordform", "msd"]

    def __init__(self, *args, **kwargs):
        super(MiniParadigmCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("msd", css_class="col-md-5 mb-3"),
                Column("wordform", css_class="col-md-7 mb-3"),
                css_class="row",
            ),
            Submit("submit", _("Save")),
        )


class CustomBtn(Submit):
    def __init__(self, *args, **kwargs):
        _type = kwargs.pop("type")
        self.field_classes = "btn btn-%s" % _type
        super(Submit, self).__init__(*args, **kwargs)


class DeleteFormBase(forms.Form):
    def __init__(self, *args, **kwargs):
        super(DeleteFormBase, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(CustomBtn("submit", _("Delete"), type="danger"))


class ExampleForm(forms.ModelForm):
    text = forms.CharField(
        label="", widget=forms.TextInput(attrs={"placeholder": _("Example")})
    )
    source = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Source")})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = Example
        fields = ["text", "source", "notes"]

    def __init__(self, *args, **kwargs):
        super(ExampleForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("text", css_class="col-md-12 mb-3"),
                css_class="row",
            ),
            Submit("submit", _("Save")),
        )


class RelationExampleForm(forms.ModelForm):
    text = forms.CharField(
        label="", widget=forms.TextInput(attrs={"placeholder": _("Example")})
    )
    source = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": _("Source")})
    )
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = RelationExample
        fields = ["text", "language", "source", "notes"]

    def __init__(self, *args, **kwargs):
        relation = kwargs.pop("relation")
        super(RelationExampleForm, self).__init__(*args, **kwargs)
        self.fields["language"] = LanguageChoiceField(
            queryset=Language.objects.filter(
                id__in=[relation.lexeme_to.language, relation.lexeme_from.language]
            ),
            label="",
        )

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("language", css_class="col-md-2"),
                Column("text", css_class="col-md-10"),
                css_class="row",
            ),
            "source",
            "notes",
            Submit("submit", _("Save")),
        )


class RelationMetadataForm(forms.ModelForm):
    text = forms.CharField(
        label="", widget=forms.TextInput(attrs={"placeholder": _("Text")})
    )

    class Meta:
        model = RelationMetadata
        fields = ["type", "text", "language"]

    def __init__(self, *args, **kwargs):
        relation = kwargs.pop("relation")
        super(RelationMetadataForm, self).__init__(*args, **kwargs)
        self.fields["language"] = LanguageChoiceField(
            queryset=Language.objects.filter(
                id__in=[relation.lexeme_to.language, relation.lexeme_from.language]
            ),
            label="",
        )
        self.fields["type"] = forms.ChoiceField(
            choices=RELATION_METADATA_TYPES, required=True, label=""
        )

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("language", css_class="col-md-2"),
                Column("type", css_class="col-md-2"),
                Column("text", css_class="col-md-8"),
                css_class="row",
            ),
            Submit("submit", _("Save")),
        )


class HistoryForm(forms.Form):
    start_date = forms.DateField(
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={
                "class": "form-control datepicker",
                "data-date-format": "dd/mm/yyyy",
                "value": (timezone.now().date() - timedelta(days=7)).strftime(
                    "%d/%m/%Y"
                ),
            }
        ),
    )
    end_date = forms.DateField(
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={
                "class": "form-control datepicker",
                "data-date-format": "dd/mm/yyyy",
                "value": timezone.now().date().strftime("%d/%m/%Y"),
            }
        ),
    )
    model_class = forms.ChoiceField(
        choices=(
            ("lexeme", _("Lexeme")),
            ("relation", _("Relation")),
            ("miniparadigm", _("Mini Paradigm")),
        ),
        required=True,
        label=_("Model"),
    )

    def __init__(self, *args, **kwargs):
        super(HistoryForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("start_date", css_class="col-md-6 mb-3"),
                Column("end_date", css_class="col-md-6 mb-3"),
                css_class="row",
            ),
            Submit("submit", _("Search")),
        )


class ApprovalMultipleChoiceForm(forms.Form):
    choices = forms.ModelMultipleChoiceField(
        queryset=None,
        label="",
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={}),
    )

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop("queryset")
        super().__init__(*args, **kwargs)
        self.fields["choices"].queryset = queryset
        self.initial["choices"] = [_i for _i in queryset if _i.checked]


class FlipRelationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        relation = kwargs.pop("relation")

        super(FlipRelationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = "switch-relation-form"
        self.helper.form_method = "post"
        self.helper.form_action = reverse("relation-switch", kwargs={"pk": relation.id})

        self.helper.layout = Layout(
            CustomBtn("submit", _("Switch Direction"), type="secondary")
        )


class ReverseRelationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        relation = kwargs.pop("relation")

        super(ReverseRelationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = "reverse-relation-form"
        self.helper.form_method = "post"
        self.helper.form_action = reverse(
            "relation-reverse", kwargs={"pk": relation.id}
        )

        self.helper.layout = Layout(
            CustomBtn("submit", _("Add Reverse"), type="secondary")
        )


class StemForm(forms.ModelForm):
    text = forms.CharField(
        label=_("Stem"),
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Stem")}),
    )
    contlex = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Continuation Lexicon")}),
    )
    order = forms.IntegerField(required=True, label=_("Order"), initial=0)
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )
    checked = forms.BooleanField(required=False, label=_("Processed"))

    class Meta:
        model = Stem
        fields = [
            "text",
            "contlex",
            "order",
            "notes",
            "checked",
        ]

    def __init__(self, *args, **kwargs):
        super(StemForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("text", css_class="col-md-4 mb-3"),
                Column("contlex", css_class="col-md-4 mb-3"),
                Column("order", css_class="col-md-4 mb-3"),
                css_class="row",
            ),
            "notes",
            "checked",
            Submit("submit", _("Save")),
        )


class SymbolForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Symbol"),
        required=True,
        widget=forms.TextInput(attrs={"placeholder": _("Symbol")}),
    )
    comment = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Comment")})
    )

    class Meta:
        model = Stem
        fields = [
            "name",
            "comment",
        ]

    def __init__(self, *args, **kwargs):
        super(SymbolForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout("name", "comment", Submit("submit", _("Save")))


class RelationExampleLinkForm(forms.ModelForm):
    example_to = forms.ModelChoiceField(queryset=None, required=True, label=_("To"))
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = RelationExampleRelation
        fields = ["example_to", "notes"]

    def __init__(self, *args, **kwargs):
        example_from = kwargs.pop("example_from")
        super(RelationExampleLinkForm, self).__init__(*args, **kwargs)

        filter_ids = list(
            example_from.example_from_relationexample_set.values_list(
                "example_to", flat=True
            ).all()
        )
        filter_ids.append(example_from.id)

        self.fields["example_to"].queryset = (
            example_from.relation.relationexample_set.filter(~Q(id__in=filter_ids))
        )

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML("<h4>%s: %s</h4>" % (_("From"), "{{ example_from }}")),
                css_class="",
            ),
            "example_to",
            "notes",
            Submit("submit", _("Save")),
        )


class RelationExampleLinkEditForm(forms.ModelForm):
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"placeholder": _("Notes")})
    )

    class Meta:
        model = RelationExampleRelation
        fields = ["notes"]

    def __init__(self, *args, **kwargs):
        super(RelationExampleLinkEditForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                HTML(
                    "<h4>%s - %s</h4>"
                    % ("{{ object.example_from }}", "{{ object.example_to}}")
                ),
                css_class="",
            ),
            "notes",
            Submit("submit", _("Save")),
        )


class LexemeMetadataForm(forms.ModelForm):
    text = forms.CharField(widget=forms.TextInput(attrs={"placeholder": _("Text")}))

    class Meta:
        model = LexemeMetadata
        fields = ["text", "type"]

    def __init__(self, *args, **kwargs):
        self.type = forms.ChoiceField(
            choices=LEXEME_METADATA_TYPES, required=True, label=_("Type")
        )

        super(LexemeMetadataForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout("text", "type", Submit("submit", _("Save")))


class FileRequestForm(forms.ModelForm):

    class Meta:
        model = FileRequest
        fields = ["lang_source", "lang_target", "type"]

    type = forms.ChoiceField(
        choices=DOWNLOAD_TYPES[1:], label=_("Download Type")
    )  # remove lexc file
    lang_source = LanguageChoiceField(
        queryset=Language.objects.annotate(lexeme_count=Count("lexemes")).filter(
            lexeme_count__gt=0
        ),
        required=True,
        label=_("Source Language"),
    )
    lang_target = LanguageChoiceField(
        queryset=Language.objects.annotate(lexeme_count=Count("lexemes")).filter(
            lexeme_count__gt=0
        ),
        required=True,
        label=_("Target Language"),
    )
    use_accepted = forms.BooleanField(required=False, label=_("Accepted only"))

    def __init__(self, *args, **kwargs):
        super(FileRequestForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("type", css_class="col-md-6 mb-3"),
                css_class="row",
            ),
            Row(
                Column("lang_source", css_class="col-md-6 mb-3"),
                Column(
                    "lang_target",
                    css_id="lang_target_form",
                    css_class="col-md-6 mb-3",
                ),
                css_class="row",
            ),
            Row(
                Column("use_accepted", css_class="col-md-6 mb-3"),
                css_class="row",
            ),
            Submit("submit", _("Request"), css_class="btn btn-primary"),
        )

    def clean(self):
        cleaned_data = super(FileRequestForm, self).clean()

        cleaned_data["type"] = int(cleaned_data.get("type"))

        return cleaned_data


class LanguageParadigmForm(forms.ModelForm):
    class Meta:
        model = LanguageParadigm
        fields = ["language", "pos", "form", "mini"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("language", css_class="col-md-6"),
                Column("pos", css_class="col-md-6"),
            ),
            "form",
            "mini",
            Submit("submit", "Save", css_class="btn btn-primary"),
        )
