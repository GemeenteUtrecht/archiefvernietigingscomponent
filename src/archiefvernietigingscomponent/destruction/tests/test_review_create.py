from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils.translation import gettext as _

from django_capture_on_commit_callbacks import capture_on_commit_callbacks

from archiefvernietigingscomponent.accounts.tests.factories import UserFactory
from archiefvernietigingscomponent.notifications.models import Notification

from ...constants import RoleTypeChoices
from ..constants import ReviewStatus, Suggestion
from ..models import DestructionListReview
from .factories import (
    DestructionListAssigneeFactory,
    DestructionListFactory,
    DestructionListItemFactory,
    DestructionListReviewCommentFactory,
    DestructionListReviewFactory,
)

MANAGEMENT_FORM_DATA = {
    "item_reviews-TOTAL_FORMS": 3,
    "item_reviews-INITIAL_FORMS": 0,
    "item_reviews-MIN_NUM_FORMS": 0,
    "item_reviews-MAX_NUM_FORMS": 1000,
}


class DLMixin:
    def _create_destruction_list(self, contains_sensitive_info=False):
        destruction_list = DestructionListFactory.create(
            contains_sensitive_info=contains_sensitive_info
        )

        DestructionListItemFactory.create_batch(3, destruction_list=destruction_list)
        assignee = DestructionListAssigneeFactory.create(
            assignee=self.user, destruction_list=destruction_list
        )
        destruction_list.assignee = assignee.assignee
        destruction_list.save()

        return destruction_list


class ReviewCreateTests(DLMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = UserFactory(role__can_review_destruction=True)

    def setUp(self) -> None:
        super().setUp()

        self.client.force_login(self.user)

    def test_create_review_approve(self):
        destruction_list = self._create_destruction_list()
        next_assignee = DestructionListAssigneeFactory.create(
            destruction_list=destruction_list
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        data = {
            "author": self.user.id,
            "destruction_list": destruction_list.id,
            "status": ReviewStatus.approved,
            "text": "some comment",
        }
        data.update(MANAGEMENT_FORM_DATA)
        for i, item in enumerate(destruction_list.items.all()):
            data.update(
                {
                    f"item_reviews-{i}-destruction_list_item": item.id,
                    f"item_reviews-{i}-suggestion": "",
                    f"item_reviews-{i}-text": "",
                }
            )

        response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("destruction:reviewer-list"))

        review = DestructionListReview.objects.get()

        self.assertEqual(review.author, self.user)
        self.assertEqual(review.destruction_list, destruction_list)
        self.assertEqual(review.status, ReviewStatus.approved)
        self.assertEqual(review.text, "some comment")

        items_reviews = review.item_reviews.all()
        self.assertEqual(items_reviews.count(), 0)  # save only changed items

        self.assertEqual(review.destruction_list.assignee, next_assignee.assignee)

        #  check logs
        timeline_log = review.logs.get()
        self.assertEqual(timeline_log.user, self.user)
        self.assertEqual(timeline_log.template, "destruction/logs/review_created.txt")

        #  check notifications
        notifications = Notification.objects.all()
        self.assertEqual(notifications.count(), 2)
        notif_review = notifications.get(user=destruction_list.author)
        self.assertEqual(
            notif_review.message,
            _("{author} has reviewed the destruction list.").format(author=self.user),
        )
        notif_assign = notifications.get(user=next_assignee.assignee)
        self.assertEqual(notif_assign.message, _("You are assigned for review."))

    def test_create_review_change(self):
        destruction_list = self._create_destruction_list()
        DestructionListAssigneeFactory.create(
            destruction_list=destruction_list, assignee__role=self.user.role
        )
        items = destruction_list.items.order_by("id").all()

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        data = {
            "author": self.user.id,
            "destruction_list": destruction_list.id,
            "status": ReviewStatus.changes_requested,
            "item_reviews-0-destruction_list_item": items[0].id,
            "item_reviews-0-suggestion": Suggestion.change_and_remove,
            "item_reviews-0-text": "some comment",
            "item_reviews-1-destruction_list_item": items[1].id,
            "item_reviews-1-suggestion": Suggestion.remove,
            "item_reviews-1-text": "",
            "item_reviews-2-destruction_list_item": items[2].id,
            "item_reviews-2-suggestion": "",
            "item_reviews-2-text": "",
        }
        data.update(MANAGEMENT_FORM_DATA)

        response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("destruction:reviewer-list"))

        review = DestructionListReview.objects.get()

        self.assertEqual(review.author, self.user)
        self.assertEqual(review.destruction_list, destruction_list)
        self.assertEqual(review.status, ReviewStatus.changes_requested)

        item_reviews = review.item_reviews.order_by("destruction_list_item_id").all()
        self.assertEqual(item_reviews.count(), 2)  # save only changed items
        self.assertEqual(item_reviews[0].destruction_list_item, items[0])
        self.assertEqual(item_reviews[0].suggestion, Suggestion.change_and_remove)
        self.assertEqual(item_reviews[1].destruction_list_item, items[1])
        self.assertEqual(item_reviews[1].suggestion, Suggestion.remove)

        self.assertEqual(review.destruction_list.assignee, destruction_list.author)

        #  check logs
        timeline_log = review.logs.get()
        self.assertEqual(timeline_log.user, self.user)
        self.assertEqual(timeline_log.template, "destruction/logs/review_created.txt")

        #  check notifications
        notifications = Notification.objects.order_by("created").all()
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(notifications[0].user, destruction_list.author)
        self.assertEqual(
            notifications[0].message,
            _("{author} has reviewed the destruction list.").format(author=self.user),
        )
        self.assertEqual(notifications[1].user, destruction_list.author)
        self.assertEqual(notifications[1].message, _("There is a review to process."))

    def test_create_review_reject(self):
        destruction_list = self._create_destruction_list()
        DestructionListAssigneeFactory.create(
            destruction_list=destruction_list, assignee__role=self.user.role
        )
        items = destruction_list.items.order_by("id").all()

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        data = {
            "author": self.user.id,
            "destruction_list": destruction_list.id,
            "status": ReviewStatus.rejected,
            "item_reviews-0-destruction_list_item": items[0].id,
            "item_reviews-0-suggestion": "",
            "item_reviews-0-text": "",
            "item_reviews-1-destruction_list_item": items[1].id,
            "item_reviews-1-suggestion": "",
            "item_reviews-1-text": "",
            "item_reviews-2-destruction_list_item": items[2].id,
            "item_reviews-2-suggestion": "",
            "item_reviews-2-text": "",
        }
        data.update(MANAGEMENT_FORM_DATA)

        response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("destruction:reviewer-list"))

        review = DestructionListReview.objects.get()

        self.assertEqual(review.author, self.user)
        self.assertEqual(review.destruction_list, destruction_list)
        self.assertEqual(review.status, ReviewStatus.rejected)

        item_reviews = review.item_reviews.order_by("destruction_list_item_id").all()
        self.assertEqual(item_reviews.count(), 0)  # save only changed items
        self.assertEqual(review.destruction_list.assignee, destruction_list.author)

        #  check logs
        timeline_log = review.logs.get()
        self.assertEqual(timeline_log.user, self.user)
        self.assertEqual(timeline_log.template, "destruction/logs/review_created.txt")

        #  check notifications
        notifications = Notification.objects.order_by("created").all()
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(notifications[0].user, destruction_list.author)
        self.assertEqual(
            notifications[0].message,
            _("{author} has reviewed the destruction list.").format(author=self.user),
        )
        self.assertEqual(notifications[1].user, destruction_list.author)
        self.assertEqual(notifications[1].message, _("There is a review to process."))

    @patch(
        "archiefvernietigingscomponent.destruction.views.process_destruction_list.delay"
    )
    def test_create_review_approve_last(self, m):
        destruction_list = self._create_destruction_list()

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        data = {
            "author": self.user.id,
            "destruction_list": destruction_list.id,
            "status": ReviewStatus.approved,
            "text": "some comment",
        }
        data.update(MANAGEMENT_FORM_DATA)

        response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("destruction:reviewer-list"))

        review = DestructionListReview.objects.get()

        self.assertEqual(review.author, self.user)
        self.assertEqual(review.destruction_list, destruction_list)
        self.assertEqual(review.status, ReviewStatus.approved)
        self.assertEqual(review.text, "some comment")

        #  check logs
        timeline_log = review.logs.get()
        self.assertEqual(timeline_log.user, self.user)
        self.assertEqual(timeline_log.template, "destruction/logs/review_created.txt")

        #  check notification
        notification = Notification.objects.get()
        self.assertEqual(notification.user, destruction_list.author)
        self.assertEqual(
            notification.message,
            _("{author} has reviewed the destruction list.").format(author=self.user),
        )

        # NOT called since the test transaction should not commit
        m.assert_not_called()

    def test_create_review_with_comment(self):
        """
        After a record manager has made changes to a list based on the comments of a reviewer, they may have added
        a comment to explain why they ignored some remarks. Here we test that the reviewer can see those remarks.
        """
        destruction_list = self._create_destruction_list()
        destruction_review = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=self.user
        )
        DestructionListReviewCommentFactory.create(
            review=destruction_review, text="Important comment text"
        )
        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        response = self.client.get(url)

        self.assertEqual(200, response.status_code)

        self.assertIn(b"Important comment text", response.content)

    def test_reviewer_only_sees_comments_to_their_review(self):
        """
        Since a list may have been reviewed multiple times, check that a reviewer only sees comments to their review.
        """
        archivist = UserFactory(
            role__can_review_destruction=True, role__type=RoleTypeChoices.archivist
        )
        destruction_list = self._create_destruction_list()
        destruction_review = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=archivist
        )
        DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=self.user
        )
        DestructionListReviewCommentFactory.create(
            review=destruction_review, text="Important comment text"
        )
        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        response = self.client.get(url)

        self.assertEqual(200, response.status_code)

        self.assertNotIn(b"Important comment text", response.content)

    def test_reviewer_only_sees_comments_to_their_last_review(self):
        """
        Since a list may have been reviewed multiple times, check that a reviewer only sees comments to their last
        review.
        """
        destruction_list = self._create_destruction_list()

        destruction_review_1 = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=self.user
        )
        DestructionListReviewCommentFactory.create(
            review=destruction_review_1, text="First important comment text"
        )

        destruction_review_2 = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=self.user
        )
        DestructionListReviewCommentFactory.create(
            review=destruction_review_2, text="Second important comment text"
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        response = self.client.get(url)

        self.assertEqual(200, response.status_code)

        self.assertIn(b"Second important comment text", response.content)
        self.assertNotIn(b"First important comment text", response.content)

    def test_each_reviewer_sees_the_right_comment(self):
        """
        Flow to test: there are multiple reviewers and the last one requests changes. The author of the list
        makes changes and adds a comment to the last review. The rewiew process restarts, but now the first reviewer
        asks for changes. The author adds a comment. Reviewer 1 and 2 need to see the comments that were addressed
        to their review.
        """
        process_owner = UserFactory(
            role__can_review_destruction=True, role__type=RoleTypeChoices.process_owner
        )
        destruction_list = self._create_destruction_list()
        destruction_review_1 = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=process_owner
        )
        destruction_review_2 = DestructionListReviewFactory.create(
            destruction_list=destruction_list, author=self.user
        )

        DestructionListReviewCommentFactory.create(
            review=destruction_review_1, text="Important comment for process owner"
        )
        DestructionListReviewCommentFactory.create(
            review=destruction_review_2, text="Important comment for user"
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        self.client.force_login(self.user)
        response = self.client.get(url)

        self.assertEqual(200, response.status_code)

        self.assertNotIn(b"Important comment for process owner", response.content)
        self.assertIn(b"Important comment for user", response.content)

        assignee = DestructionListAssigneeFactory.create(
            assignee=process_owner, destruction_list=destruction_list
        )
        destruction_list.assignee = assignee.assignee
        destruction_list.save()

        self.client.force_login(process_owner)
        response = self.client.get(url)

        self.assertEqual(200, response.status_code)

        self.assertIn(b"Important comment for process owner", response.content)
        self.assertNotIn(b"Important comment for user", response.content)


class SendTaskReviewCreateTests(DLMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory(role__can_review_destruction=True)
        self.client.force_login(self.user)

    @patch(
        "archiefvernietigingscomponent.destruction.views.process_destruction_list.delay"
    )
    def test_create_review_approve_last(self, m):
        destruction_list = self._create_destruction_list()

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        data = {
            **MANAGEMENT_FORM_DATA,
            "author": self.user.id,
            "destruction_list": destruction_list.id,
            "status": ReviewStatus.approved,
            "text": "some comment",
        }
        with capture_on_commit_callbacks(execute=True) as callbacks:
            response = self.client.post(url, data=data)

        self.assertRedirects(response, reverse("destruction:reviewer-list"))

        self.assertEqual(len(callbacks), 1)
        m.assert_called_once_with(destruction_list.id)


class CreateReviewViewContextTest(TestCase):
    def test_sensitive_info_process_owner(self):
        destruction_list = DestructionListFactory.create(contains_sensitive_info=True)
        process_owner = UserFactory.create(
            role__can_review_destruction=True, role__type=RoleTypeChoices.process_owner,
        )
        DestructionListAssigneeFactory.create(
            destruction_list=destruction_list, assignee=process_owner
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        self.client.force_login(process_owner)
        response = self.client.get(url)

        # Process owner can see sensitive info
        self.assertTrue(response.context["show_optional_columns"])

    def test_sensitive_info_archivist(self):
        destruction_list = DestructionListFactory.create(contains_sensitive_info=True)
        archivist = UserFactory.create(
            role__can_review_destruction=True, role__type=RoleTypeChoices.archivist,
        )
        DestructionListAssigneeFactory.create(
            destruction_list=destruction_list, assignee=archivist
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        self.client.force_login(archivist)
        response = self.client.get(url)

        # Archivist cannot see sensitive info
        self.assertFalse(response.context["show_optional_columns"])

    def test_no_sensitive_info_archivist(self):
        destruction_list = DestructionListFactory.create(contains_sensitive_info=False)
        archivist = UserFactory.create(
            role__can_review_destruction=True, role__type=RoleTypeChoices.archivist,
        )
        DestructionListAssigneeFactory.create(
            destruction_list=destruction_list, assignee=archivist
        )

        url = reverse("destruction:reviewer-create", args=[destruction_list.id])

        self.client.force_login(archivist)
        response = self.client.get(url)

        # Archivist can see everything since it's not sensitive
        self.assertTrue(response.context["show_optional_columns"])
