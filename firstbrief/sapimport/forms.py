from typing import Any, cast

from django import forms


class ImportUploadForm(forms.Form):
    file = forms.FileField(
        help_text="UTF-8 CSV, maximum 2 MB, using the documented version 1 schema."
    )


class ImportSelectionForm(forms.Form):
    selected = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(
        self,
        data: Any = None,
        *,
        choices: list[tuple[str, str]],
        initial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(data=data, initial=initial)
        cast(forms.MultipleChoiceField, self.fields["selected"]).choices = choices
