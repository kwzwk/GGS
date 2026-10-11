import datetime

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import monday_of

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_FILES = 20
ACCEPT = "image/*,.heic,.heif,application/pdf,.pdf"


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ACCEPT}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        if not files:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        return [super(MultipleFileField, self).clean(f, initial) for f in files]


class UploadForm(forms.Form):
    week = forms.DateField(
        label=_("Week"),
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text=_("Any day of the school week the work is for."),
    )
    files = MultipleFileField(
        label=_("Photos or PDFs of the worksheets"),
        help_text=_("You can pick several files at once. Photos straight from the phone are fine."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["week"].initial = monday_of(datetime.date.today())

    def clean_week(self):
        return monday_of(self.cleaned_data["week"])

    def clean_files(self):
        files = self.cleaned_data["files"]
        if len(files) > MAX_FILES:
            raise forms.ValidationError(
                _("Please upload at most %(count)d files at once.") % {"count": MAX_FILES}
            )
        for f in files:
            if f.size > MAX_FILE_SIZE:
                raise forms.ValidationError(
                    _("%(name)s is larger than %(size)d MB.")
                    % {"name": f.name, "size": MAX_FILE_SIZE // (1024 * 1024)}
                )
        return files
