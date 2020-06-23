from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView
from django.views.generic.base import RedirectView

from django_filters.views import FilterView
from timeline_logger.models import TimelineLog

from rma.accounts.mixins import RoleRequiredMixin

from .filters import ReviewerListFilter
from .forms import DestructionListForm, get_reviewer_choices, get_zaaktype_choices
from .models import DestructionList, DestructionListReview


class EnterView(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        role = self.request.user.role
        if role and role.can_start_destruction:
            return reverse("destruction:record-manager-list")

        if self.request.user.is_superuser:
            return reverse("audit:audit-trail")

        raise PermissionDenied(self.get_permission_denied_message())


class RecordManagerDestructionListView(RoleRequiredMixin, ListView):
    """ data for user who can start destruction lists"""

    role_permission = "can_start_destruction"
    template_name = "destruction/recordmanager_list.html"

    def get_queryset(self):
        return DestructionList.objects.filter(author=self.request.user).order_by("-id")


class DestructionListCreateView(RoleRequiredMixin, CreateView):
    model = DestructionList
    form_class = DestructionListForm
    template_name = "destruction/destructionlist_create.html"
    success_url = reverse_lazy("destruction:record-manager-list")
    role_permission = "can_start_destruction"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)

        # add zaaktypen
        context.update(
            {
                "zaaktypen": get_zaaktype_choices(),
                "reviewers": get_reviewer_choices(self.request.user),
            }
        )

        return context

    @transaction.atomic
    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)

        destruction_list = form.instance

        TimelineLog.log_from_request(
            self.request,
            destruction_list,
            template="destruction/logs/created.txt",
            n_items=destruction_list.items.count(),
            reviewers=list(
                destruction_list.assignees.values("assignee__id", "assignee__username")
            ),
        )

        return response


class ReviewerDestructionListView(RoleRequiredMixin, FilterView):
    """ data for user who can reviewer destruction lists"""

    role_permission = "can_review_destruction"
    template_name = "destruction/reviewer_list.html"
    filterset_class = ReviewerListFilter

    def get_queryset(self):
        review_status = DestructionListReview.objects.filter(
            author=self.request.user, destruction_list=models.OuterRef("id")
        ).values("status")
        prefiltered_qs = DestructionList.objects.filter(
            assignee=self.request.user
        ) | DestructionList.objects.reviewed_by(self.request.user)
        return prefiltered_qs.annotate(
            review_status=models.Subquery(review_status[:1])
        ).order_by("-id")

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)

        context["notifications"] = (
            Notification.objects.filter(user=self.request.user).order_by("-id").all()
        )

        return context
