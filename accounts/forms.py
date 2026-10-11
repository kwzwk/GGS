from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Email (optional)"),
        required=False,
        help_text=_("Only so the admin can reach you. We don't send emails."),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        # New parents wait for the admin to approve them.
        user.is_active = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "pending": _(
            "Your account is waiting for approval by the admin. "
            "Please try again later."
        ),
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            # The default backend rejects inactive users like a wrong password.
            # Tell a pending parent (with the right password) what's going on.
            user = User.objects.filter(username=username, is_active=False).first()
            if user and user.check_password(password):
                raise forms.ValidationError(self.error_messages["pending"], code="pending")
        return super().clean()
