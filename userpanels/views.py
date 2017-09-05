# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.forms import ModelForm

from userpanels.models import *

@permission_required('userpanels.add_panel')
def list_panels(request):
    if request.method == "GET":
        return render(request,
            "userpanels/list_panels.html", {
            "panels": Panel.objects.filter(admins=request.user).order_by('-created')
        })
    else:
        # POST is always to create a new panel.
        panel = Panel.objects.create(
            title="New Panel",
            welcome_message="Please join my panel.",
            contact_info="If you have any questions about this panel, please contact [Your Contact Info Here].",
            consent_text="Your email address will be shared with the panel owner.")
        panel.admins.add(request.user)
        return HttpResponseRedirect(panel.get_absolute_url())

@permission_required('userpanels.add_panel')
def show_panel(request, panel_id):
    
    panel = get_object_or_404(Panel, id=panel_id, admins=request.user)
    inv, _ = PanelInvitation.objects.get_or_create(panel=panel)

    if request.method == "GET":
        return render(request,
            "userpanels/show_panel.html", {
            "panel": panel,
            "invitation": inv,
            "memberships": PanelMembership.objects.filter(panel=panel).order_by('created'),
        })
    
    elif request.method == "POST":
        if request.POST.get("action") == "reset-link":
            inv.delete() # will be re-created on next load
        if request.POST.get("action") == "remove-user":
            PanelMembership.objects.filter(panel=panel, user__id=request.POST.get("user")).delete()
        if request.POST.get("action") == "set-user-notes":
            pm = PanelMembership.objects.filter(panel=panel, user__id=request.POST.get("user")).first()
            if pm:
                pm.extra["notes"] = request.POST.get("value")
                pm.save()

        return HttpResponseRedirect(panel.get_absolute_url())

@permission_required('userpanels.add_panel')
def change_panel(request, panel_id):
    panel = get_object_or_404(Panel, id=panel_id, admins=request.user)

    class PanelInfoForm(ModelForm):
        class Meta:
            model = Panel
            fields = ("title", "private_notes", "welcome_message", "consent_text", "contact_info")

    if request.method == "GET":
        return render(request,
            "userpanels/change_panel.html", {
            "panel": panel,
            "form": PanelInfoForm(instance=panel),
        })
    else:
        form = PanelInfoForm(request.POST, instance=panel)
        try:
            form.save()
        except ValueError:
            return render(request,
                "userpanels/change_panel.html", {
                "panel": panel,
                "form": form,
            })
        else:
            return HttpResponseRedirect("/panels/" + panel_id)

@permission_required('userpanels.add_panel')
def export_panel_users(requet, panel_id):
    pass

@login_required
def accept_invitation(request, invitation_id):
    inv = get_object_or_404(PanelInvitation, code=invitation_id)

    if PanelMembership.objects.filter(panel=inv.panel, user=request.user).exists():
        # already joined
        return render(request,
            "userpanels/invitation_accepted.html", {
            "panel": inv.panel
        })
    elif request.method == "GET":
        # show join form
        return render(request,
            "userpanels/invitation.html", {
            "panel": inv.panel
        })
    else:
        # POST is their acceptance.
        PanelMembership.objects.create(
            panel=inv.panel,
            user=request.user,
            invitation_code=inv.code,
        )
        return render(request,
            "userpanels/invitation_accepted.html", {
            "panel": inv.panel
        })
