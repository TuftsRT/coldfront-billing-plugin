import pytest

from coldfront_billing.tests.conftest import (
    create_pi_user,
    create_project_with_role_user,
)
from coldfront_billing.tests.test_views.common import get_billing_response


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingViewSearchFilters:
    """Test suite for BillingView search and filter functionality."""

    def test_search_by_pi_user_success(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        pi_user1 = create_pi_user('_searchable')
        pi_user2 = create_pi_user('_other')
        user = create_pi_user('_billing')
        create_project_with_role_user(
            user,
            pi_user1,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project 1',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        create_project_with_role_user(
            user,
            pi_user2,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project 2',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?username=searchable')

        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project 1' in project_titles
        assert 'Project 2' not in project_titles

    def test_search_by_project_user_success(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        from django.contrib.auth.models import User

        pi_user = create_pi_user('_pi')
        billing_user1 = User.objects.create_user(
            username='searchable_billing', email='billing1@example.com', password='pass'
        )
        billing_user2 = User.objects.create_user(
            username='other_billing', email='billing2@example.com', password='pass'
        )
        create_project_with_role_user(
            billing_user1,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project with searchable user',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        create_project_with_role_user(
            billing_user2,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project with other user',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?username=searchable')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project with searchable user' in project_titles
        assert 'Project with other user' not in project_titles

    def test_search_case_insensitive(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        pi_user = create_pi_user('_CamelCase')
        user = create_pi_user('_billing')
        create_project_with_role_user(
            user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'CamelCase Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?username=camelcase')
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0].title == 'CamelCase Project'

    def test_search_with_empty_username_returns_all_projects(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser, '?username=')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 5

    def test_search_by_user_name_no_matches(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser, '?username=nonexistent')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_search_form_included_in_context(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser, '?username=test')

        assert response.status_code == 200
        assert 'search_form' in response.context
        form = response.context['search_form']
        assert form.initial.get('username') == 'test' or form.data.get('username') == 'test'

    def test_search_filters_only_active_project_users(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        project_user_status_inactive,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        from django.contrib.auth.models import User

        pi_user = create_pi_user('_pi')
        billing_user = User.objects.create_user(
            username='searchable_user', email='billing@example.com', password='pass'
        )
        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Active User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_inactive,
            'Inactive User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?username=searchable')

        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Active User Project' in project_titles
        assert 'Inactive User Project' not in project_titles

    def test_search_multiple_fields_combined(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        """Test search using both username and last_name filters."""
        from django.contrib.auth.models import User

        pi_user = User.objects.create_user(
            username='specific_username',
            email='pi@example.com',
            password='pass',
            first_name='John',
            last_name='Specific',
        )
        billing_user = create_pi_user('_billing')
        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Specific Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?username=specific&last_name=Specific')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0].title == 'Specific Project'

    def test_search_by_project_title_partial_match(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        pi_user = create_pi_user('_pi')
        billing_user = create_pi_user('_billing')
        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Alpha Genomics Core',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Beta unrelated work',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?project_title=genomics')
        assert response.status_code == 200
        titles = [p.title for p in response.context['project_list']]
        assert 'Alpha Genomics Core' in titles
        assert 'Beta unrelated work' not in titles

        response = get_billing_response(client, superuser, '?project_title=GENOMICS')
        assert response.status_code == 200
        titles = [p.title for p in response.context['project_list']]
        assert titles == ['Alpha Genomics Core']

    def test_no_cost_center_filter_includes_only_projects_without_assignment(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        """Test that no_cost_center filter returns only projects without cost center assignments."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        pi_user = create_pi_user('_pi')
        billing_user = create_pi_user('_billing')

        project_with_assignment = create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project With Cost Center',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        CostCenter.objects.create(name='DEPT001', cost_center_type='department')
        CostCenterAssignment.objects.create(
            project=project_with_assignment,
            assignments=[{'department': 'DEPT001', 'percentage': 100}],
        )

        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project Without Cost Center',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser)
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project With Cost Center' in project_titles
        assert 'Project Without Cost Center' in project_titles

        response = get_billing_response(client, superuser, '?no_cost_center=on')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project With Cost Center' not in project_titles
        assert 'Project Without Cost Center' in project_titles

    def test_search_by_cost_center_contains_partial_department(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        pi_user = create_pi_user('_pi')
        billing_user = create_pi_user('_billing')
        CostCenter.objects.create(name='ENG_BIOLOGY_01', cost_center_type='department')

        with_cc = create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project Alpha CC',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        CostCenterAssignment.objects.create(
            project=with_cc,
            assignments=[{'department': 'ENG_BIOLOGY_01', 'percentage': 100}],
        )

        create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project Beta No Match',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = get_billing_response(client, superuser, '?cost_center=bio')
        assert response.status_code == 200
        titles = [p.title for p in response.context['project_list']]
        assert 'Project Alpha CC' in titles
        assert 'Project Beta No Match' not in titles

    def test_search_by_cost_center_contains_grant_name(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        pi_user = create_pi_user('_pi')
        billing_user = create_pi_user('_billing')
        CostCenter.objects.create(name='DEPT_GRANT', cost_center_type='department')
        CostCenter.objects.create(name='NIH_R01_ABC', cost_center_type='grant')

        proj = create_project_with_role_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project With Grant',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        CostCenterAssignment.objects.create(
            project=proj,
            assignments=[{'department': 'DEPT_GRANT', 'grant': 'NIH_R01_ABC', 'percentage': 100}],
        )

        response = get_billing_response(client, superuser, '?cost_center_contains=r01')
        assert response.status_code == 200
        assert [p.title for p in response.context['project_list']] == ['Project With Grant']
