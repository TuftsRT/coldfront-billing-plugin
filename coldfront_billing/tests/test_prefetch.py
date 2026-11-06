"""Tests for coldfront_billing.prefetch functions that had no direct coverage:
get_filtered_allocations_prefetch, get_billing_visible_projects_query,
is_paid_storage_allocation, has_billing_perm, has_billing_perm_for_project,
and the NoStorageException/filtering behavior of get_projects_prefetch.
"""

from decimal import Decimal

import pytest

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project, ProjectUser
from coldfront.core.resource.models import Resource, ResourceType

from coldfront_billing.enums import ProjectStatus
from coldfront_billing.models import NoCostQuota
from coldfront_billing.prefetch import (
    get_billing_visible_projects_query,
    get_filtered_allocations_prefetch,
    get_projects_prefetch,
    has_billing_perm,
    has_billing_perm_for_project,
    is_paid_storage_allocation,
)
from coldfront_billing.tests.conftest import (
    add_no_cost_quota_storage_allocation,
    add_storage_allocation_to_project,
    create_pi_user,
    get_or_create_project_role,
)
from coldfront_billing.utils import NoStorageException

pytestmark = pytest.mark.django_db


def _add_project_user(project, user, role, status):
    return ProjectUser.objects.create(project=project, user=user, role=role, status=status)


class TestGetProjectsPrefetch:
    def test_raises_no_storage_exception_when_no_storage_resource_type_exists(self):
        with pytest.raises(NoStorageException):
            get_projects_prefetch(Project.objects.all())

    def test_excludes_projects_without_a_paid_storage_allocation(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        # project has no allocation at all yet
        result = list(get_projects_prefetch(Project.objects.all()))
        assert project not in result

    def test_includes_project_with_a_paid_storage_allocation(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
        )
        result = list(get_projects_prefetch(Project.objects.all()))
        assert result == [project]

    def test_excludes_project_whose_only_storage_resource_does_not_require_payment(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        free_resource = Resource.objects.create(
            name="Free Storage",
            resource_type=storage_resource_type,
            requires_payment=False,
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification="j",
        )
        allocation.resources.add(free_resource)

        result = list(get_projects_prefetch(Project.objects.all()))
        assert project not in result


class TestGetBillingVisibleProjectsQuery:
    def test_matches_project_where_user_is_pi(self, project):
        result = list(Project.objects.filter(get_billing_visible_projects_query(project.pi.username)))
        assert result == [project]

    def test_matches_project_where_user_has_active_billing_role(
        self,
        project,
        user,
        billing_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, billing_role, project_user_status_active)

        result = list(Project.objects.filter(get_billing_visible_projects_query(user.username)))
        assert result == [project]

    def test_matches_project_where_user_has_active_manager_role(
        self,
        project,
        user,
        manager_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, manager_role, project_user_status_active)

        result = list(Project.objects.filter(get_billing_visible_projects_query(user.username)))
        assert result == [project]

    def test_excludes_project_when_role_membership_is_inactive(
        self,
        project,
        user,
        billing_role,
        project_user_status_inactive,
    ):
        _add_project_user(project, user, billing_role, project_user_status_inactive)

        result = list(Project.objects.filter(get_billing_visible_projects_query(user.username)))
        assert result == []

    def test_excludes_project_for_unrelated_user(self, project, user):
        result = list(Project.objects.filter(get_billing_visible_projects_query(user.username)))
        assert result == []


class TestIsPaidStorageAllocation:
    def test_true_for_paid_storage_resource(
        self,
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
        )
        assert is_paid_storage_allocation(allocation) is True

    def test_false_for_storage_resource_that_does_not_require_payment(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
    ):
        free_resource = Resource.objects.create(
            name="Free Storage",
            resource_type=storage_resource_type,
            requires_payment=False,
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification="j",
        )
        allocation.resources.add(free_resource)

        assert is_paid_storage_allocation(allocation) is False

    def test_false_for_non_storage_resource_type(self, project, allocation_status_active):
        other_type = ResourceType.objects.get_or_create(name="Compute")[0]
        compute_resource = Resource.objects.create(
            name="Compute Node",
            resource_type=other_type,
            requires_payment=True,
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification="j",
        )
        allocation.resources.add(compute_resource)

        assert is_paid_storage_allocation(allocation) is False

    def test_false_when_allocation_has_no_resources(self, project, allocation_status_active):
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification="j",
        )
        assert is_paid_storage_allocation(allocation) is False


class TestHasBillingPerm:
    def test_true_for_pi_of_active_project(self, project):
        assert has_billing_perm(project.pi) is True

    def test_true_for_pi_of_archived_project(self, project, project_status_archived):
        project.status = project_status_archived
        project.save()
        assert has_billing_perm(project.pi) is True

    def test_false_for_pi_of_new_status_project(self, project, project_status_new):
        project.status = project_status_new
        project.save()
        assert has_billing_perm(project.pi) is False

    def test_true_for_billing_role_member_with_active_status(
        self,
        project,
        user,
        billing_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, billing_role, project_user_status_active)
        assert has_billing_perm(user) is True

    def test_true_for_manager_role_member_with_active_status(
        self,
        project,
        user,
        manager_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, manager_role, project_user_status_active)
        assert has_billing_perm(user) is True

    def test_false_for_billing_role_member_with_inactive_status(
        self,
        project,
        user,
        billing_role,
        project_user_status_inactive,
    ):
        _add_project_user(project, user, billing_role, project_user_status_inactive)
        assert has_billing_perm(user) is False

    def test_false_for_non_billing_role_member(
        self,
        project,
        user,
        project_user_status_active,
    ):
        other_role = get_or_create_project_role("Member")
        _add_project_user(project, user, other_role, project_user_status_active)
        assert has_billing_perm(user) is False

    def test_false_for_user_with_no_project_relation(self, user):
        assert has_billing_perm(user) is False


class TestHasBillingPermForProject:
    def test_true_for_pi_of_the_project(self, project):
        assert has_billing_perm_for_project(project.pi, project) is True

    def test_true_for_billing_role_member_of_that_project(
        self,
        project,
        user,
        billing_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, billing_role, project_user_status_active)
        assert has_billing_perm_for_project(user, project) is True

    def test_true_for_manager_role_member_of_that_project(
        self,
        project,
        user,
        manager_role,
        project_user_status_active,
    ):
        _add_project_user(project, user, manager_role, project_user_status_active)
        assert has_billing_perm_for_project(user, project) is True

    def test_false_for_inactive_role_membership(
        self,
        project,
        user,
        billing_role,
        project_user_status_inactive,
    ):
        _add_project_user(project, user, billing_role, project_user_status_inactive)
        assert has_billing_perm_for_project(user, project) is False

    def test_false_for_unrelated_user(self, project, user):
        assert has_billing_perm_for_project(user, project) is False

    def test_false_for_billing_role_member_of_a_different_project(
        self,
        project,
        user,
        billing_role,
        project_user_status_active,
        project_status_active,
        field_of_science,
    ):
        """has_billing_perm_for_project is scoped to a single project: a Billing
        role on one project must not grant access to a different project."""
        other_pi = create_pi_user("_other_perm_project")
        other_project = Project.objects.create(
            title="Other Perm Project",
            pi=other_pi,
            status=project_status_active,
            field_of_science=field_of_science,
        )
        _add_project_user(other_project, user, billing_role, project_user_status_active)

        assert has_billing_perm_for_project(user, project) is False
        assert has_billing_perm_for_project(user, other_project) is True


class TestGetFilteredAllocationsPrefetch:
    def test_returns_empty_queryset_when_no_storage_resource_type_exists(self, user):
        quota = NoCostQuota.objects.create(
            user=user,
            quota_type="tier_1",
            description="d",
            amount_tb=Decimal("10"),
            units="TB",
            increment_gb=10,
        )
        assert list(get_filtered_allocations_prefetch(quota)) == []

    def test_includes_allocation_when_quota_owner_is_pi(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        quota = NoCostQuota.objects.create(
            user=project.pi,
            quota_type="tier_1",
            description="d",
            amount_tb=Decimal("10"),
            units="TB",
            increment_gb=10,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value="tier_1",
        )

        result = list(get_filtered_allocations_prefetch(quota))
        assert result == [allocation]

    def test_includes_allocation_when_quota_owner_has_billing_role_but_is_not_pi(
        self,
        project,
        user,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        _add_project_user(project, user, billing_role, project_user_status_active)
        quota = NoCostQuota.objects.create(
            user=user,
            quota_type="tier_1",
            description="d",
            amount_tb=Decimal("10"),
            units="TB",
            increment_gb=10,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value="tier_1",
        )

        result = list(get_filtered_allocations_prefetch(quota))
        assert result == [allocation]

    def test_excludes_allocation_for_unrelated_quota_owner(
        self,
        project,
        user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        quota = NoCostQuota.objects.create(
            user=user,
            quota_type="tier_1",
            description="d",
            amount_tb=Decimal("10"),
            units="TB",
            increment_gb=10,
        )
        add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value="tier_1",
        )

        result = list(get_filtered_allocations_prefetch(quota))
        assert result == []

    def test_excludes_allocation_with_a_different_quota_type(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        quota = NoCostQuota.objects.create(
            user=project.pi,
            quota_type="tier_1",
            description="d",
            amount_tb=Decimal("10"),
            units="TB",
            increment_gb=10,
        )
        add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value="tier_2",
        )

        result = list(get_filtered_allocations_prefetch(quota))
        assert result == []
