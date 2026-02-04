from unittest.mock import Mock

from coldfront_billing.constants import COST_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME
from coldfront_billing.data import BillingAllocation

DEFAULT_QUOTA = 0
DEFAULT_COST = 10


class TestBillingAllocation:
    """Test suite for BillingAllocation class."""

    @staticmethod
    def _create_mock_allocation(allocation_id=1, project_id=1, quota_attrs=None, storage_resources=None):
        """Helper to create a mock allocation object."""
        allocation = Mock()
        allocation.id = allocation_id
        allocation.project_id = project_id

        setattr(allocation, QUOTA_ATTRIBUTE_NAME, quota_attrs)
        setattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, storage_resources)

        return allocation

    @staticmethod
    def _create_mock_storage_resource(cost_attrs=None):
        """Helper to create a mock storage resource object."""
        resource = Mock()
        setattr(resource, COST_ATTRIBUTE_NAME, cost_attrs)
        return resource

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
            quota_tb=5.1,
            cost_per_tb=100,
        )
        assert billing.total_cost == 600

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

    def test_parse_with_valid_quota_and_cost_attributes(self):
        """Test parse with valid quota and cost attributes."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
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

    def test_parse_without_quota_attribute_uses_default(self):
        """Test parse when quota attribute is missing, uses default."""

        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_without_cost_attribute_uses_default(self):
        """Test parse when cost attribute is missing, uses default."""
        storage_resource = self._create_mock_storage_resource()  # No cost attrs
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_without_storage_resource_uses_defaults(self):
        """Test parse when storage resource is missing, uses default cost."""
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[],  # Empty list
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_invalid_quota_value_uses_default(self):
        """Test parse when quota value is invalid, uses default."""

        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='invalid_number')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_invalid_cost_value_uses_default(self):
        """Test parse when cost value is invalid, uses default."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='not_a_number')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_quota_string_uses_default(self):
        """Test parse when quota value is empty string, uses default."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_empty_cost_string_uses_default(self):
        """Test parse when cost value is empty string, uses default."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_none_quota_value_uses_default(self):
        """Test parse when quota value is None, uses default."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value=None)],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_with_none_cost_value_uses_default(self):
        """Test parse when cost value is None, uses default."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value=None)])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_float_string_values(self):
        """Test parse with float values as strings."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='99.99')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='7.5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 7.5
        assert result.cost_per_tb == 99.99

    def test_parse_with_negative_values_uses_defaults(self):
        """Test parse with negative values (should use default)."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='-100')])
        allocation = self._create_mock_allocation(
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
        storage_resource = self._create_mock_storage_resource(cost_attrs=[cost_attr])
        quota_attr = Mock(value='5e0')  # 5
        allocation = self._create_mock_allocation(
            quota_attrs=[quota_attr],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == 100.0

    def test_parse_with_multiple_storage_resources_uses_first(self):
        """Test parse when multiple storage resources exist, uses first one."""
        storage_resource1 = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        storage_resource2 = self._create_mock_storage_resource(cost_attrs=[Mock(value='200')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource1, storage_resource2],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.cost_per_tb == 100.0  # Uses first resource's cost

    def test_parse_with_storage_resource_no_cost_attributes_uses_default(self):
        """Test parse when storage resource exists but has no cost attributes."""
        storage_resource = self._create_mock_storage_resource()  # Explicitly None
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_cost_attributes_list_uses_default(self):
        """Test parse when cost attributes list is empty."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[])  # Empty list
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_parse_with_empty_quota_attributes_list_uses_default(self):
        """Test parse when quota attributes list is empty."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            quota_attrs=[],  # Empty list
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_quota_attributes_missing_uses_default(self):
        """Test parse when quota attribute is missing entirely."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            storage_resources=[storage_resource],
            # Don't set quota_attrs at all
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == DEFAULT_QUOTA  # Uses default
        assert result.cost_per_tb == 100.0

    def test_parse_storage_resource_missing_uses_default_cost(self):
        """Test parse when storage resource attribute is missing entirely."""
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            # Don't set storage_resources at all
        )

        result = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        assert result.quota_tb == 5.0
        assert result.cost_per_tb == DEFAULT_COST  # Uses default

    def test_total_cost_with_parsed_float_values(self):
        """Test total_cost calculation with float values from parse."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='150.5')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='7.3')],
            storage_resources=[storage_resource],
        )

        billing = BillingAllocation.parse(allocation, default_quota=DEFAULT_QUOTA, default_cost=DEFAULT_COST)
        # ceil(7.3) = 8, int(150.5) = 150, so 8 * 150 = 1200
        assert billing.total_cost == 1200
