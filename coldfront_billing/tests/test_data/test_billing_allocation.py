from unittest.mock import Mock

from coldfront_billing.data import BillingAllocation

from .allocation_mocks import (
    create_mock_allocation,
    create_mock_pi,
    create_mock_project,
    create_mock_storage_resource,
)
from .defaults import DEFAULT_COST, DEFAULT_QUOTA


class TestBillingAllocation:
    """Test suite for BillingAllocation class."""

    def test_total_cost_basic_calculation(self):
        """Test basic total cost calculation."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
        )
        assert billing.total_cost == 500

    def test_total_cost_with_float_quota_rounds_up(self):
        """Test that float quota values are rounded up using ceil."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5.03,
            cost_per_tb=100,
        )
        assert billing.total_cost == 510

    def test_total_cost_with_float_quota_exact(self):
        """Test that exact float quota values work correctly."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5.0,
            cost_per_tb=100,
        )
        assert billing.total_cost == 500

    def test_total_cost_with_float_cost(self):
        """Test total cost with float cost per TB."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=99.51,
        )
        assert billing.total_cost == 500

    def test_calculate_cost_integer_quota(self):
        """ceil is applied in tenths; whole TB matches simple product."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
        )
        assert billing.calculate_cost(5) == 500.0

    def test_calculate_cost_ceils_quota_to_next_tenth(self):
        """Quota below next tenth is ceiled (e.g. 5.01 TB -> 5.1 TB billable)."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=0,
            cost_per_tb=100,
        )
        assert billing.calculate_cost(5.01) == 510.0
        assert billing.calculate_cost(5.03) == 510.0

    def test_calculate_cost_exact_tenth_unchanged(self):
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=0,
            cost_per_tb=100,
        )
        assert billing.calculate_cost(5.0) == 500.0
        assert billing.calculate_cost(5.1) == 510.0

    def test_calculate_cost_zero_quota(self):
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=0,
            cost_per_tb=100,
        )
        assert billing.calculate_cost(0) == 0.0

    def test_calculate_cost_uses_rounded_cost_per_tb(self):
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=0,
            cost_per_tb=99.51,
        )
        assert billing.calculate_cost(5) == 500.0

    def test_calculate_cost_fractional_quota_with_cost(self):
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=0,
            cost_per_tb=50,
        )
        assert billing.calculate_cost(1.11) == 60.0

    def test_parse_with_valid_quota_and_cost_attributes(self):
        """Test parse with valid quota and cost attributes."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            allocation_id=1,
            project_id=1,
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.allocation_id == 1
        assert result.project_id == 1
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == 100.0

    def test_parse_with_new_quota_adds_to_quota_tb(self):
        """When new_quota is provided, it is added to the resolved quota_tb."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(
            allocation,
            default_quota=DEFAULT_QUOTA,
            default_cost=DEFAULT_COST,
            new_quota=2.5,
        )
        assert result.quota_tb == 7.5

    def test_parse_with_negative_new_quota_subtracts_from_quota_tb(self):
        """Negative new_quota is applied additively (reduces resolved quota_tb)."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(
            allocation,
            default_quota=DEFAULT_QUOTA,
            default_cost=DEFAULT_COST,
            new_quota=-2.0,
        )
        assert result.quota_tb == 3.0

    def test_parse_without_new_quota_unchanged(self):
        """When new_quota is omitted or None, quota_tb matches baseline parse."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        baseline = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        with_extra = BillingAllocation.parse(
            allocation,
            default_quota=DEFAULT_QUOTA,
            default_cost=DEFAULT_COST,
            new_quota=None,
        )
        assert with_extra.quota_tb == baseline.quota_tb == 5.0

    def test_parse_with_new_quota_adds_to_default_quota(self):
        """new_quota is added when quota_tb is the default (no quota attribute on allocation)."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(
            allocation,
            default_quota=DEFAULT_QUOTA,
            default_cost=DEFAULT_COST,
            new_quota=3.0,
        )
        assert result.quota_tb == DEFAULT_QUOTA + 3.0

    def test_parse_without_quota_attribute_uses_default(self):
        """Test parse when quota attribute is missing, uses default."""

        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_without_cost_attribute_uses_default(self):
        """Test parse when cost attribute is missing, uses default."""
        storage_resource = create_mock_storage_resource()  # No cost attrs
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_without_storage_resource_uses_defaults(self):
        """Test parse when storage resource is missing, uses default cost."""
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[],  # Empty list
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_invalid_quota_value_uses_default(self):
        """Test parse when quota value is invalid, uses default."""

        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='invalid_number')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_invalid_cost_value_uses_default(self):
        """Test parse when cost value is invalid, uses default."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='not_a_number')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_quota_string_uses_default(self):
        """Test parse when quota value is empty string, uses default."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_empty_cost_string_uses_default(self):
        """Test parse when cost value is empty string, uses default."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_none_quota_value_uses_default(self):
        """Test parse when quota value is None, uses default."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value=None)],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_none_cost_value_uses_default(self):
        """Test parse when cost value is None, uses default."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value=None)])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_float_string_values(self):
        """Test parse with float values as strings."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='99.99')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='7.5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 7.5
        assert result.cost_per_tb == 99.99

    def test_parse_with_negative_values_uses_defaults(self):
        """Test parse with negative values (should use default)."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='-100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='-5')],
            storage_resources=[storage_resource],
        )

        # Negative values should be handled as defaults
        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA
        assert result.cost_per_tb == DEFAULT_COST

    def test_parse_with_scientific_notation(self):
        """Test parse with scientific notation values."""
        cost_attr = Mock(value='1e2')  # 100
        storage_resource = create_mock_storage_resource(cost_attrs=[cost_attr])
        quota_attr = Mock(value='5e0')  # 5
        allocation = create_mock_allocation(
            quota_attrs=[quota_attr],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == 100.0

    def test_parse_with_multiple_storage_resources_uses_first(self):
        """Test parse when multiple storage resources exist, uses first one."""
        storage_resource1 = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        storage_resource2 = create_mock_storage_resource(cost_attrs=[Mock(value='200')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource1, storage_resource2],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.cost_per_tb == 100.0  # Uses first resource's cost

    def test_parse_with_storage_resource_no_cost_attributes_uses_default(self):
        """Test parse when storage resource exists but has no cost attributes."""
        storage_resource = create_mock_storage_resource()  # Explicitly None
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_cost_attributes_list_uses_default(self):
        """Test parse when cost attributes list is empty."""
        storage_resource = create_mock_storage_resource(cost_attrs=[])  # Empty list
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_quota_attributes_list_uses_default(self):
        """Test parse when quota attributes list is empty."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[],  # Empty list
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_quota_attributes_missing_uses_default(self):
        """Test parse when quota attribute is missing entirely."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            storage_resources=[storage_resource],
            # Don't set quota_attrs at all
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_storage_resource_missing_uses_default_cost(self):
        """Test parse when storage resource attribute is missing entirely."""
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            # Don't set storage_resources at all
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_total_cost_with_parsed_float_values_1(self):
        """Test total_cost calculation with float values from parse."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='150.5')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='7.3')],
            storage_resources=[storage_resource],
        )

        billing = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)
        # round up with 1 digit (7.3) = 7.3, int(150.5) = 150, so 7.3 * 150 = 1200
        assert billing.total_cost == 1095

    def test_total_cost_with_parsed_float_values_2(self):
        """Test total_cost calculation with float values from parse."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='150.5')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='7.32')],
            storage_resources=[storage_resource],
        )

        billing = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)
        # round up with 1 digit (7.32) = 7.4, int(150.5) = 150, so 7.4 * 150 = 1200
        assert billing.total_cost == 1110

    def test_parse_includes_extra_project_title_and_pi_name(self):
        """Test parse populates extra.project_title and extra.pi_name from project."""
        pi = create_mock_pi(username='test_pi')
        project = create_mock_project(title='My Project', pi=pi)
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
            project=project,
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['project_title'] == 'My Project'
        assert result.extra['pi_name'] == 'test_pi'

    def test_parse_includes_extra_resource_name(self):
        """Test parse populates extra.resource_name from first storage resource."""
        storage_resource = create_mock_storage_resource(
            cost_attrs=[Mock(value='100')],
            name='My Storage Resource',
        )
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['resource_name'] == 'My Storage Resource'

    def test_parse_includes_extra_status(self):
        """Test parse populates extra.status from allocation status."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
            status='Active',
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['status'] == 'Active'

    def test_parse_includes_extra_end_date_when_present(self):
        """Test parse populates extra.end_date when allocation has end_date."""
        from datetime import date

        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
            end_date=date(2025, 12, 31),
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['end_date'] == date(2025, 12, 31)

    def test_parse_uses_dash_for_missing_extra_fields(self):
        """Test parse uses '-' for missing project_title, pi_name, resource_name, end_date."""
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[],
            project=None,
            end_date=None,
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['project_title'] == '-'
        assert result.extra['pi_name'] == '-'
        assert result.extra['resource_name'] == '-'
        assert result.extra['end_date'] == '-'
