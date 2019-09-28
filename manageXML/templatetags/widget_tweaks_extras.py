from django import template
import re
from widget_tweaks.templatetags.widget_tweaks import append_attr, set_attr

register = template.Library()


@register.tag
def render_lookup_choice_field(parser, token):
    """
    Takes form field as first argument, field number as second argument, and
    list of attribute-value pairs for all other arguments.

    Attribute-value pairs should be in the form of attribute=value OR
    attribute="a value"
    """
    error_msg = ('%r tag requires a form field and index followed by a list '
                 'of attributes and values in the form attr="value"'
                 % token.split_contents()[0])
    try:
        bits = token.split_contents()
        form_field = bits[1]
        field_index = int(bits[2])
        attr_list = bits[3:]
    except ValueError:
        raise template.TemplateSyntaxError(error_msg)

    attr_assign_dict = {}
    attr_concat_dict = {}
    for pair in attr_list:
        match = re.match(r'([\w_-]+)(\+?=)"?([^"]*)"?', pair)
        if not match:
            raise template.TemplateSyntaxError(error_msg + ": %s" % pair)
        attr, sign, value = match.groups()
        if sign == "=":
            attr_assign_dict[attr] = value
        else:
            attr_concat_dict[attr] = value

    return MultiFieldAttributeNode(form_field, attr_assign_dict,
                                   attr_concat_dict, index=field_index)


class MultiFieldAttributeNode(template.Node):
    def __init__(self, field, set_attrs, append_attrs, index):
        self.field = field
        self.set_attrs = set_attrs
        self.append_attrs = append_attrs
        self.index = index

    def render(self, context):
        bounded_field = template.Variable(self.field).resolve(context)
        field = bounded_field.field.fields[self.index]
        widget = bounded_field.field.widget.widgets[self.index]
        widget_data = bounded_field.subwidgets[0].data['subwidgets'][self.index]

        attrs = widget_data['attrs'].copy()

        for k, v in self.set_attrs.items():
            attrs[k] = v

        for k, v in self.append_attrs.items():
            attrs[k] = widget.attrs.get(k, '') + ' ' + v

        if bounded_field.errors:
            attrs['class'] = attrs.get('class', '') + ' error'

        if not bounded_field.form.is_bound:
            data = bounded_field.form.initial.get(bounded_field.name,
                                                  field.initial)
            if callable(data):
                data = data()
            data = bounded_field.field.widget.decompress(data)[self.index]
        else:
            data = bounded_field.data[self.index]

        return widget.render(widget_data['name'], data, attrs)
