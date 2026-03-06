from typing import Optional


def build_form(
    title: str,
    fields: list[dict[str, str]],
    button_text: str,
    subtitle: Optional[str] = None,
    action: Optional[str] = None,
    enctype: str = 'application/x-www-form-urlencoded'
):
    """
    Build a form with the given title, subtitle, and fields.
    
    Args:
        title (str): The title of the form.
        fields (list[dict[str, str]]): A list of field dictionaries, where each dictionary contains 'type' and 'label' keys.
        button_text (str): The text for the submit button.
        subtitle (Optional[str]): The subtitle of the form. Defaults to None.
    
    Returns:
        dict: The form dictionary.
    """

    form = {
        'title': title,
        'subtitle': subtitle,
        'fields': fields,
        'button_text': button_text,
        'action': action,
        'enctype': enctype,
    }
    
    return form
