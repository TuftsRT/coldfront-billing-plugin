"""Unit tests for coldfront_billing signals."""

import pytest
from django.contrib.auth.models import Group

from coldfront_billing.models import NoCostQuota, NoCostQuotaGroup


@pytest.fixture
def no_cost_quota_group(db):
    """Create a NoCostQuotaGroup for signal tests."""
    group = Group.objects.create(name='tier_1_group')
    return NoCostQuotaGroup.objects.create(
        group=group,
        quota_type='tier_1',
        description='Tier 1 storage',
        amount=15.0,
        units='TB',
        minimum_increment=1.0,
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
        units='TB',
        minimum_increment=0.5,
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
        assert quota.amount == no_cost_quota_group.amount
        assert quota.units == no_cost_quota_group.units
        assert quota.minimum_increment == no_cost_quota_group.minimum_increment
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
