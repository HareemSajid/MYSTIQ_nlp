from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to Baker Street, Detective.")
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    from game.services import player_summary
    if request.method == "POST":
        name = request.POST.get("display_name", "").strip()[:60]
        if name:
            request.user.profile.display_name = name
            request.user.profile.save()
            messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"summary": player_summary(request.user)})
