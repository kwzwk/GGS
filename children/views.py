from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import ChildForm
from .models import Child


def _own_child(request, pk):
    return get_object_or_404(Child, pk=pk, parent=request.user)


@login_required
def child_list(request):
    return render(request, "children/list.html", {"children": request.user.children.all()})


@login_required
def child_create(request):
    form = ChildForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        child = form.save(commit=False)
        child.parent = request.user
        child.save()
        messages.success(request, _("%(name)s was added.") % {"name": child.name})
        return redirect("children:list")
    return render(request, "children/form.html", {"form": form})


@login_required
def child_update(request, pk):
    child = _own_child(request, pk)
    form = ChildForm(request.POST or None, instance=child)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Changes saved."))
        return redirect("children:list")
    return render(request, "children/form.html", {"form": form, "child": child})


@login_required
def child_delete(request, pk):
    child = _own_child(request, pk)
    if request.method == "POST":
        child.delete()
        messages.success(request, _("%(name)s was removed.") % {"name": child.name})
        return redirect("children:list")
    return render(request, "children/delete.html", {"child": child})
