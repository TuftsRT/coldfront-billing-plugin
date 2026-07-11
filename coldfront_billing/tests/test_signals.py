"""Unit tests for coldfront_billing signals."""

from unittest.mock import patch

import pytest
from decimal import Decimal
from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttribute,
    AllocationAttributeChangeRequest,
    AllocationAttributeType,
    AllocationChangeRequest,
    AllocationChangeStatusChoice,
    AllocationStatusChoice,
)
from coldfront.core.allocation.models import AttributeType as AllocationAttributeTypeBase
from coldfront.core.allocation.signals import allocation_change_approved
from coldfront.core.resource.models import Resource, ResourceAttribute
from django.contrib.auth.models import Group

from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME, QUOTA_ATTR_NAME
from coldfront_billing.enums import ProjectStatus
from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment, NoCostQuotaGroup
from coldfront_billing.notifications import send_allocation_notification
from coldfront_billing.tests.conftest import (
    add_no_cost_quota_storage_allocation,
    add_storage_allocation_to_project,
    create_project_with_role_user,
)


@pytest.fixture
def no_cost_quota_group(db):
    """Create a NoCostQuotaGroup for signal tests."""
    group = Group.objects.create(name='tier_1_group')
    return NoCostQuotaGroup.objects.create(
        group=group,
        quota_type='tier_1',
        description='Tier 1 storage',
        amount=15.0,
        amount_tb=Decimal('15.0'),
        units='TB',
        minimum_increment=1.0,
        increment_gb=1000,
    )


@pytest.fixture
def no_cost_quota_group_tier2(db):
    """Create a second NoCostQuotaGroup for signal tests."""
    group = Group.objects.create(name='tier_2_group')

    return NoCostQuotaGroup.objects.create(
        group=group,
        quota_type='tier_2',
        description='Tier 2 storage',
        amount=50.0,
        amount_tb=Decimal('50.0'),
        units='TB',
        minimum_increment=0.5,
        increment_gb=500,
    )


@pytest.mark.django_db
class TestUserGroupsChangedSignal:
    """Test suite for user_groups_changed signal (m2m_changed on User.groups)."""

    def test_adding_user_to_matching_group_creates_no_cost_quota(
        self,
        user,
        no_cost_quota_group,
    ):
        """When user is added to the group linked to NoCostQuotaGrup, NoCostQuota is created."""
        user.groups.add(no_cost_quota_group.group)

        quota = NoCostQuota.objects.get(user=user, quota_type=no_cost_quota_group.quota_type)
        assert quota.amount_tb == no_cost_quota_group.amount_tb
        assert quota.units == no_cost_quota_group.units
        assert quota.increment_gb == no_cost_quota_group.increment_gb
        assert quota.description == no_cost_quota_group.description

    def test_adding_user_to_non_matching_group_does_not_create_quota(
        self,
        user,
        no_cost_quota_group,
    ):
        """When user is added to a group that does not match any NoCostQuotaGroup, no quota is created."""
        group = Group.objects.create(name='other_group')

        user.groups.add(group)

        assert not NoCostQuota.objects.filter(user=user).exists()

    def test_only_matching_group_creates_quota_when_multiple_groups_exist(
        self,
        user,
        no_cost_quota_group,
        no_cost_quota_group_tier2,
    ):
        """When user is added to one matching group, only that group's quota is created."""
        user.groups.add(no_cost_quota_group.group)

        assert NoCostQuota.objects.filter(user=user, quota_type='tier_1').exists()
        assert not NoCostQuota.objects.filter(user=user, quota_type='tier_2').exists()

    def test_adding_user_to_multiple_groups_creates_quotas_for_each_matching_group(
        self,
        user,
        no_cost_quota_group,
        no_cost_quota_group_tier2,
    ):
        """When user is added to multiple matching groups, a quota is created for each matching group."""
        user.groups.add(no_cost_quota_group.group, no_cost_quota_group_tier2.group)

        assert NoCostQuota.objects.filter(user=user, quota_type='tier_1').exists()
        assert NoCostQuota.objects.filter(user=user, quota_type='tier_2').exists()
        assert NoCostQuota.objects.filter(user=user).count() == 2

    def test_get_or_create_prevents_duplicate_when_user_already_in_group(
        self,
        user,
        no_cost_quota_group,
    ):
        """Adding user to same group twice does not create duplicate NoCostQuota."""
        user.groups.add(no_cost_quota_group.group)
        user.groups.add(no_cost_quota_group.group)  # Add again

        assert NoCostQuota.objects.filter(user=user, quota_type='tier_1').count() == 1

    def test_removing_user_from_group_does_not_create_quota(
        self,
        user,
        no_cost_quota_group,
    ):
        """post_remove action does not trigger NoCostQuota creation."""
        user.groups.add(no_cost_quota_group.group)

        NoCostQuota.objects.filter(user=user).delete()  # Clear any created quota

        user.groups.remove(no_cost_quota_group.group)

        assert not NoCostQuota.objects.filter(user=user).exists()

    def test_empty_no_cost_quota_group_does_not_cause_error(
        self,
        user,
    ):
        """When no NoCostQuotaGroup exists, adding user to any group does not error."""
        group = Group.objects.create(name='some_group')

        user.groups.add(group)  # Should not raise

        assert not NoCostQuota.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestProjectArchivedSignal:
    """Tests for project_archived (pre_save on Project): drop no-cost allotments when project is archived."""

    def _make_allotment(
        self,
        project,
        no_cost_quota,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        *,
        resource_name: str = 'No-Cost Storage',
    ):
        allocation, _ = add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
            resource_name=resource_name,
        )
        return NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount=5.0,
        )

    def test_transition_active_to_archived_deletes_allotments_for_project(
        self,
        project_with_billing_user,
        no_cost_quota,
        project_status_archived,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        allotment = self._make_allotment(
            project_with_billing_user,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
        )
        project_with_billing_user.status = project_status_archived
        project_with_billing_user.save()

        assert not NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()

    def test_saving_active_project_does_not_delete_allotments(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        allotment = self._make_allotment(
            project_with_billing_user,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
        )
        project_with_billing_user.title = 'Updated title'
        project_with_billing_user.save()

        assert NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()

    def test_second_save_while_archived_does_not_error(
        self,
        project_with_billing_user,
        no_cost_quota,
        project_status_archived,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        self._make_allotment(
            project_with_billing_user,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
        )
        project_with_billing_user.status = project_status_archived
        project_with_billing_user.save()

        project_with_billing_user.title = 'Still archived'
        project_with_billing_user.save()

        assert project_with_billing_user.status.name == ProjectStatus.ARCHIVED

    def test_archiving_one_project_does_not_remove_allotments_on_other_projects(
        self,
        user,
        pi_user,
        billing_role,
        project_user_status_active,
        project_status_active,
        project_status_archived,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        allotment_a = self._make_allotment(
            project_with_billing_user,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            resource_name='No-Cost Storage A',
        )
        project_b = create_project_with_role_user(
            user=user,
            pi_user=pi_user,
            project_status=project_status_active,
            role=billing_role,
            project_user_status=project_user_status_active,
            title='Other project',
        )
        allotment_b = self._make_allotment(
            project_b,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            resource_name='No-Cost Storage B',
        )

        project_with_billing_user.status = project_status_archived
        project_with_billing_user.save()

        assert not NoCostQuotaAllotment.objects.filter(pk=allotment_a.pk).exists()
        assert NoCostQuotaAllotment.objects.filter(pk=allotment_b.pk).exists()

    def test_transition_new_to_archived_deletes_allotments(
        self,
        project_with_billing_user,
        no_cost_quota,
        project_status_new,
        project_status_archived,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Any non-archived prior status to Archived triggers cleanup (not only Active)."""
        project_with_billing_user.status = project_status_new
        project_with_billing_user.save(update_fields=['status'])

        allotment = self._make_allotment(
            project_with_billing_user,
            no_cost_quota,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
        )

        project_with_billing_user.status = project_status_archived
        project_with_billing_user.save()

        assert not NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()


@pytest.fixture
def allocation_status_new(db) -> AllocationStatusChoice:
    """Non-active allocation status for testing transitions to Active."""
    return AllocationStatusChoice.objects.get_or_create(name='New')[0]


@pytest.fixture
def allocation_quota_apply_attribute_type(db) -> AllocationAttributeType:
    """Allocation attribute type for apply no-cost quota preference (allocation_no_cost_quota)."""
    text_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name='Text')
    return AllocationAttributeType.objects.get_or_create(
        name=ALLOCATION_QUOTA_ATTRIBUTE_NAME,
        defaults={'attribute_type': text_attr_type},
    )[0]


@pytest.mark.django_db
class TestAllocationBecameActiveSignal:
    """Tests for allocation_became_active (pre_save on Allocation): auto no-cost allotment when status -> Active."""

    def _pending_no_cost_allocation(
        self,
        project,
        storage_resource_type,
        allocation_status_new,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
        no_cost_quota,
        *,
        quota_value: str = '10',
        apply_pref_value: str | None = None,
        resource_name: str = 'No-Cost Storage Pending',
    ) -> Allocation:
        storage_resource = Resource.objects.create(
            name=resource_name,
            resource_type=storage_resource_type,
            requires_payment=True,
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value='100',
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=no_cost_quota_type_attribute_type,
            value=no_cost_quota.quota_type,
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_new,
            quantity=1,
            justification='pending activation',
        )
        allocation.resources.add(storage_resource)
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value=quota_value,
        )
        if apply_pref_value is not None:
            AllocationAttribute.objects.create(
                allocation=allocation,
                allocation_attribute_type=allocation_quota_apply_attribute_type,
                value=apply_pref_value,
            )
        return allocation

    def test_transition_to_active_creates_allotment_using_min_of_allocation_and_remaining(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            quota_value='10',
            apply_pref_value=str(no_cost_quota.pk),
        )

        allocation.status = allocation_status_active
        allocation.save()

        allotment = NoCostQuotaAllotment.objects.get(allocation=allocation, no_cost_quota=no_cost_quota)
        assert allotment.amount_tb == Decimal('10.0')

    def test_allocation_change_approved_creates_allotment_when_allocation_already_active(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        """``allocation_became_active`` does not run on create; approval signal applies allotments."""
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            quota_value='10',
            apply_pref_value=str(no_cost_quota.pk),
        )

        allocation_change_approved.send(sender=object, allocation_pk=allocation.pk, allocation_change_pk=1)

        allotment = NoCostQuotaAllotment.objects.get(allocation=allocation, no_cost_quota=no_cost_quota)
        assert allotment.amount == 10.0
        assert not AllocationAttribute.objects.filter(
            allocation=allocation,
            allocation_attribute_type__name=ALLOCATION_QUOTA_ATTRIBUTE_NAME,
        ).exists()

    def test_allotment_amount_capped_by_remaining_pool(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        consumer, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
            resource_name='No-Cost Consumer',
            quota_value='5',
        )
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota,
            allocation=consumer,
            amount=70.0,
        )

        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            quota_value='50',
            apply_pref_value=str(no_cost_quota.pk),
            resource_name='No-Cost Storage Pending B',
        )

        allocation.status = allocation_status_active
        allocation.save()

        allotment = NoCostQuotaAllotment.objects.get(allocation=allocation, no_cost_quota=no_cost_quota)
        assert allotment.amount == 30.0

    def test_no_apply_pref_attribute_skips_allotment(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            apply_pref_value=None,
        )

        allocation.status = allocation_status_active
        allocation.save()

        assert not NoCostQuotaAllotment.objects.filter(allocation=allocation).exists()

    def test_invalid_apply_pref_pk_skips_allotment(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            apply_pref_value='not-an-int',
        )

        allocation.status = allocation_status_active
        allocation.save()

        assert not NoCostQuotaAllotment.objects.filter(allocation=allocation).exists()

    def test_missing_quota_attribute_skips_allotment(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            apply_pref_value=str(no_cost_quota.pk),
        )
        AllocationAttribute.objects.filter(
            allocation=allocation, allocation_attribute_type=quota_attribute_type
        ).delete()

        allocation.status = allocation_status_active
        allocation.save()

        assert not NoCostQuotaAllotment.objects.filter(allocation=allocation).exists()

    def test_saving_already_active_allocation_does_not_run_transition_logic(
        self,
        project_with_billing_user,
        no_cost_quota,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
        allocation_quota_apply_attribute_type,
    ):
        allocation = self._pending_no_cost_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            allocation_quota_apply_attribute_type,
            no_cost_quota,
            quota_value='10',
            apply_pref_value=str(no_cost_quota.pk),
        )
        allocation.status = allocation_status_active
        allocation.save()

        allotment = NoCostQuotaAllotment.objects.get(allocation=allocation, no_cost_quota=no_cost_quota)
        first_amount = allotment.amount

        allocation.justification = 'still active'
        allocation.save()

        allotment.refresh_from_db()
        assert allotment.amount == first_amount


@pytest.fixture
def allocation_change_status_approved(db) -> AllocationChangeStatusChoice:
    return AllocationChangeStatusChoice.objects.get_or_create(name='Approved')[0]


@pytest.fixture
def allocation_change_status_pending(db) -> AllocationChangeStatusChoice:
    return AllocationChangeStatusChoice.objects.get_or_create(name='Pending')[0]


@pytest.mark.django_db
class TestAllocationQuotaApprovedNotification:
    """Tests for quota approval emails to project owner and requester."""

    @patch('coldfront_billing.notifications.EmailMessage')
    def test_activation_sends_email_to_project_owner(
        self,
        mock_email_message,
        project,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='12',
            resource_name='Quota Email Activation Storage',
        )

        allocation.status = allocation_status_active
        allocation.save()

        mock_email_message.return_value.send.assert_called_once()
        _, kwargs = mock_email_message.call_args
        assert project.pi.email in kwargs['to']
        assert '12' in kwargs['body']
        assert project.title in kwargs['body']
        assert '1200.00' in kwargs['body']

    @patch('coldfront_billing.notifications.EmailMessage')
    @patch('coldfront_billing.notifications.create_recipient_list')
    def test_activation_sends_email_to_requester_when_different_from_owner(
        self,
        mock_recipient_list,
        mock_email_message,
        project,
        user,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        mock_recipient_list.return_value = [project.pi.email, user.email]
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            resource_name='Quota Email Requester Storage',
        )

        allocation.status = allocation_status_active
        allocation.save()

        _, kwargs = mock_email_message.call_args
        assert set(kwargs['to']) == {project.pi.email, user.email}

    @patch('coldfront_billing.notifications.EmailMessage')
    def test_activation_skips_non_paid_storage(
        self,
        mock_email_message,
        project,
        storage_resource_type,
        allocation_status_new,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, storage_resource = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_new,
            cost_attribute_type,
            quota_attribute_type,
            resource_name='Quota Email Free Storage',
        )
        storage_resource.requires_payment = False
        storage_resource.save(update_fields=['requires_payment'])

        allocation.status = allocation_status_active
        allocation.save()

        mock_email_message.return_value.send.assert_not_called()

    @patch('coldfront_billing.notifications.EmailMessage')
    def test_change_approved_sends_when_quota_changed(
        self,
        mock_email_message,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        allocation_change_status_pending,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='5',
            resource_name='Quota Email Change Storage',
        )
        quota_attr = allocation.allocationattribute_set.get(
            allocation_attribute_type__name=QUOTA_ATTR_NAME,
        )
        change_request = AllocationChangeRequest.objects.create(
            allocation=allocation,
            status=allocation_change_status_pending,
            end_date_extension=0,
            justification='Increase quota',
        )
        AllocationAttributeChangeRequest.objects.create(
            allocation_change_request=change_request,
            allocation_attribute=quota_attr,
            new_value='20',
        )
        quota_attr.value = '20'
        quota_attr.save()

        allocation_change_approved.send(
            sender=object,
            allocation_pk=allocation.pk,
            allocation_change_pk=change_request.pk,
        )

        mock_email_message.return_value.send.assert_called_once()
        _, kwargs = mock_email_message.call_args
        assert '20' in kwargs['body']
        assert '2000.00' in kwargs['body']

    @patch('coldfront_billing.notifications.EmailMessage')
    def test_change_approved_skips_when_quota_not_in_request(
        self,
        mock_email_message,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        allocation_change_status_pending,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            resource_name='Quota Email Extend Storage',
        )
        change_request = AllocationChangeRequest.objects.create(
            allocation=allocation,
            status=allocation_change_status_pending,
            end_date_extension=30,
            justification='Extend only',
        )

        allocation_change_approved.send(
            sender=object,
            allocation_pk=allocation.pk,
            allocation_change_pk=change_request.pk,
        )

        mock_email_message.return_value.send.assert_not_called()

    @patch('coldfront_billing.notifications.EmailMessage')
    def test_skips_when_billable_cost_zero(
        self,
        mock_email_message,
        project,
        no_cost_quota,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='10',
            resource_name='Quota Email Zero Cost Storage',
        )
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount=10.0,
        )

        send_allocation_notification(allocation)

        mock_email_message.return_value.send.assert_not_called()

    @patch(
        'coldfront_billing.notifications.BILLING_ALLOCATION_EMAIL_BODY',
        'Project {project_name} quota is now {quota_amount} (cost: {cost}).',
    )
    @patch(
        'coldfront_billing.notifications.BILLING_ALLOCATION_EMAIL_SUBJECT',
        'Quota update: {project_name}',
    )
    @patch('coldfront_billing.notifications.EmailMessage')
    def test_uses_settings_templates(
        self,
        mock_email_message,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='7',
            resource_name='Quota Email Template Storage',
        )

        send_allocation_notification(allocation)

        _, kwargs = mock_email_message.call_args
        assert kwargs['subject'] == f'Quota update: {project.title}'
        assert kwargs['body'] == f'Project {project.title} quota is now 7 (cost: 700.00).'
