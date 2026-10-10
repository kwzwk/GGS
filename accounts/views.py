from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, RegistrationForm
from .models import Profile


def register(request):
    if request.user.is_authenticated:
        return redirect("children:list")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "accounts/register_done.html")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class LoginView(auth_views.LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("password_change_done")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["forced"] = Profile.objects.filter(
            user=self.request.user, must_change_password=True
        ).exists()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        Profile.objects.filter(user=self.request.user).update(must_change_password=False)
        return response


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"
