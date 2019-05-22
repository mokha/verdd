from django.urls import reverse
from django.utils.translation import ugettext as _

from allauth.account.forms import LoginForm

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # Add magic stuff to redirect back.
        self.helper.layout.append(
            HTML(
                "{% if redirect_field_value %}"
                "<input type='hidden' name='{{ redirect_field_name }}'"
                " value='{{ redirect_field_value }}' />"
                "{% endif %}"
            )
        )
        # Add password reset link.
        self.helper.layout.append(
            HTML(
                "<p><a class='button secondaryAction' href={url}>{text}</a></p>".format(
                    url=reverse('account_reset_password'),
                    text=_('Forgot Password?')
                )
            )
        )
        # Add submit button like in original form.
        self.helper.layout.append(
            HTML(
                '<button class="btn btn-lg btn-primary btn-block" type="submit">'
                '%s</button>' % _('Sign In')
            )
        )

        self.helper.form_class = 'form-signin'
        self.helper.label_class = 'sr-only'
        self.helper.field_class = ''
