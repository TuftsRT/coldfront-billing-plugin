from unittest.mock import Mock

from coldfront_billing.constants import (
    COST_ATTRIBUTE_NAME,
    NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data import (
    BillingAllocation,
    BillingQuota,
    NoCostQuotaAllocation,
    StorageUnit,
)

DEFAULT_QUOTA = 0
DEFAULT_COST = 10


class TestBillingAllocation:
    """Test suite for BillingAllocation class."""

    @staticmethod
    def _create_mock_allotment(amount, units='TB'):
        """Helper to create a mock no-cost quota allotment object."""
        allotment = Mock()
        allotment.amount = amount
        allotment.no_cost_quota = Mock()
        allotment.no_cost_quota.units = units
        return allotment

    @staticmethod
    def _create_mock_allocation(
        allocation_id=1,
        project_id=1,
        quota_attrs=None,
        storage_resources=None,
        project=None,
        status=None,
        end_date=None,
        no_cost_quota_data=None,
    ):
        """Helper to create a mock allocation object.

        Attributes are only set when provided (truthy), so missing attributes
        trigger getattr defaults - matching real allocations without prefetched data.
        """
        spec = [
            'id',
            'project_id',
            'end_date',
            'status',
            'project',
            QUOTA_ATTRIBUTE_NAME,
            STORAGE_RESOURCE_ATTRIBUTE_NAME,
        ]
        if no_cost_quota_data:
            spec = spec + [NO_COST_QUOTA_DATA_ATTRIBUTE_NAME]
        allocation = Mock(spec=spec)
        allocation.id = allocation_id
        allocation.project_id = project_id
        allocation.end_date = end_date

        status_mock = Mock()
        status_mock.name = status or 'Active'
        allocation.status = status_mock

        allocation.project = project
        # Always set quota_attrs and storage_resources so getattr returns real values
        # (not Mock) when tests use empty list or None for "missing" attributes
        setattr(allocation, QUOTA_ATTRIBUTE_NAME, quota_attrs)
        setattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, storage_resources)
        if no_cost_quota_data:
            setattr(allocation, NO_COST_QUOTA_DATA_ATTRIBUTE_NAME, no_cost_quota_data)
        return allocation

    @staticmethod
    def _create_mock_storage_resource(cost_attrs=None, name='Test Storage'):
        """Helper to create a mock storage resource object."""
        resource = Mock()
        resource.name = name
        setattr(resource, COST_ATTRIBUTE_NAME, cost_attrs)
        return resource

    @staticmethod
    def _create_mock_project(title='Test Project', pi=None):
        """Helper to create a mock project object."""
        project = Mock()
        project.title = title
        project.pi = pi
        return project

    @staticmethod
    def _create_mock_pi(username='pi_user'):
        """Helper to create a mock PI user object."""
        pi = Mock()
        pi.username = username
        return pi

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

        billing = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)
        # ceil(7.3) = 8, int(150.5) = 150, so 8 * 150 = 1200
        assert billing.total_cost == 1200

    def test_parse_includes_extra_project_title_and_pi_name(self):
        """Test parse populates extra.project_title and extra.pi_name from project."""
        pi = self._create_mock_pi(username='test_pi')
        project = self._create_mock_project(title='My Project', pi=pi)
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
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
        storage_resource = self._create_mock_storage_resource(
            cost_attrs=[Mock(value='100')],
            name='My Storage Resource',
        )
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['resource_name'] == 'My Storage Resource'

    def test_parse_includes_extra_status(self):
        """Test parse populates extra.status from allocation status."""
        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
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

        storage_resource = self._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = self._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
            end_date=date(2025, 12, 31),
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.extra is not None
        assert result.extra['end_date'] == date(2025, 12, 31)

    def test_parse_uses_dash_for_missing_extra_fields(self):
        """Test parse uses '-' for missing project_title, pi_name, resource_name, end_date."""
        allocation = self._create_mock_allocation(
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


class TestBillingQuota:
    """Test suite for BillingQuota class."""

    def test_normalized_amount_tb(self):
        """Test normalized_amount for TB unit (1:1 conversion)."""
        ncq = BillingQuota(amount=5.0, unit=StorageUnit.TB)
        assert ncq.normalized_amount == 5.0

    def test_normalized_amount_gb(self):
        """Test normalized_amount for GB unit (converts to TB)."""
        ncq = BillingQuota(amount=1000.0, unit=StorageUnit.GB)
        assert ncq.normalized_amount == 1.0

    def test_normalized_amount_gb_fractional(self):
        """Test normalized_amount for fractional GB."""
        ncq = BillingQuota(amount=500.0, unit=StorageUnit.GB)
        assert ncq.normalized_amount == 0.5


class TestBillingAllocationNoCostQuotas:
    """Test suite for BillingAllocation no_cost_quotas functionality."""

    def test_total_cost_reduced_by_no_cost_quota_tb(self):
        """Test total_cost is reduced when no_cost_quotas (TB) are present."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=10,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=3.0, unit=StorageUnit.TB)],
        )
        # 10 - 3 = 7 TB billable, ceil(7) * 100 = 700
        assert billing.total_cost == 700

    def test_total_cost_reduced_by_no_cost_quota_gb(self):
        """Test total_cost is reduced when no_cost_quotas (GB) are present."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=1000.0, unit=StorageUnit.GB)],
        )
        # 5 - 1 = 4 TB billable, 4 * 100 = 400
        assert billing.total_cost == 400

    def test_total_cost_with_multiple_no_cost_quotas(self):
        """Test total_cost with multiple no_cost_quotas summed."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=10,
            cost_per_tb=100,
            no_cost_quotas=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=500.0, unit=StorageUnit.GB),  # 0.5 TB
            ],
        )
        # 10 - 2.5 = 7.5 TB billable, ceil(7.5) * 100 = 800
        assert billing.total_cost == 800

    def test_total_cost_no_cost_quota_exceeds_quota_returns_zero(self):
        """Test total_cost is zero when no_cost_quotas exceed quota."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=10.0, unit=StorageUnit.TB)],
        )
        # max(5 - 10, 0) = 0, 0 * 100 = 0
        assert billing.total_cost == 0

    def test_total_cost_empty_no_cost_quotas_unchanged(self):
        """Test total_cost with empty no_cost_quotas behaves like before."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[],
        )
        assert billing.total_cost == 500

    def test_parse_with_no_cost_quota_data(self):
        """Test parse populates no_cost_quotas from allocation allotments."""
        allotment1 = TestBillingAllocation._create_mock_allotment(amount=2.0, units='TB')
        allotment2 = TestBillingAllocation._create_mock_allotment(amount=500.0, units='GB')
        storage_resource = TestBillingAllocation._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = TestBillingAllocation._create_mock_allocation(
            quota_attrs=[Mock(value='10')],
            storage_resources=[storage_resource],
            no_cost_quota_data=[allotment1, allotment2],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert len(result.no_cost_quotas) == 2
        assert result.no_cost_quotas[0].amount == 2.0
        assert result.no_cost_quotas[0].unit == StorageUnit.TB
        assert result.no_cost_quotas[1].amount == 500.0
        assert result.no_cost_quotas[1].unit == StorageUnit.GB
        assert result.total_cost == 800  # 10 - 2.5 = 7.5 TB, ceil(7.5) * 100 = 800

    def test_parse_without_no_cost_quota_data_yields_empty(self):
        """Test parse when allocation has no allotments (attribute not set, real-life scenario)."""
        storage_resource = TestBillingAllocation._create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = TestBillingAllocation._create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.no_cost_quotas == []
        assert result.total_cost == 500


class TestNoCostQuotaAllocation:
    """Test suite for NoCostQuotaAllocation class."""

    @staticmethod
    def _create_mock_allotment(amount, units='TB', user_id=1):
        """Helper to create a mock allotment for NoCostQuotaAllocation.create()."""
        allotment = Mock()
        allotment.amount = amount
        allotment.no_cost_quota = Mock()
        allotment.no_cost_quota.units = units
        allotment.no_cost_quota.user_id = user_id
        return allotment

    def test_user_ammount_with_users_allotment(self):
        """Test user_ammount returns the amount when users_allotment is set."""
        users_allotment = BillingQuota(amount=5.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_amount == 5.0

    def test_user_ammount_without_users_allotment(self):
        """Test user_ammount returns None when users_allotment is None."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[],
        )
        assert allocation.user_amount == 0

    def test_user_allotment_amount_with_users_allotment_tb(self):
        """Test user_allotment_amount returns normalized TB amount."""
        users_allotment = BillingQuota(amount=3.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 3.0

    def test_user_allotment_amount_with_users_allotment_gb(self):
        """Test user_allotment_amount returns normalized amount for GB (converts to TB)."""
        users_allotment = BillingQuota(amount=1000.0, unit=StorageUnit.GB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 1.0

    def test_user_allotment_amount_without_users_allotment(self):
        """Test user_allotment_amount returns 0 when users_allotment is None."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 0

    def test_other_allotments_amount_empty(self):
        """Test other_allotments_amount returns 0 when no other allotments."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=BillingQuota(amount=2.0, unit=StorageUnit.TB),
            other_allotments=[],
        )
        assert allocation.other_allotments_amount == 0

    def test_other_allotments_amount_single(self):
        """Test other_allotments_amount sums single allotment."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=3.0, unit=StorageUnit.TB)],
        )
        assert allocation.other_allotments_amount == 3.0

    def test_other_allotments_amount_multiple_mixed_units(self):
        """Test other_allotments_amount sums multiple allotments with mixed units."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=1000.0, unit=StorageUnit.GB),  # 1 TB
            ],
        )
        assert allocation.other_allotments_amount == 3.0

    def test_max_possible_allocation_allocation_amount_none(self):
        """Test max_possible_allocation when allocation_amount is None returns remaining + user allotment."""
        users_allotment = BillingQuota(amount=2.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=None,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 7.0  # 5 + 2

    def test_max_possible_allocation_limit_from_quota(self):
        """Test max_possible_allocation when allocation_amount is set and limits result."""
        users_allotment = BillingQuota(amount=1.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=1000.0, unit=StorageUnit.GB),  # 1 TB
            ],
        )
        # remaining_quota=5 + 1 (existing user_allotment) = 6 TB possible from quota
        # allocation_available = 10 - 3 (from other users) = 7 TB
        # min(6, 7) = 6, floor(6/1)*1 = 6
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 6.0

    def test_max_possible_allocation_limit_from_allocation(self):
        """Test max_possible_allocation when allocation limit is lower than quota."""
        users_allotment = BillingQuota(amount=5.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=8.0,
            users_allotment=users_allotment,
            other_allotments=[BillingQuota(amount=6.0, unit=StorageUnit.TB)],
        )
        # remaining_quota=10 + 5 (existing user_allotment) = 15 TB
        # allocation_available = 8 - 6 = 2 TB
        # min(15, 2) = 2, floor(2/1)*1 = 2
        result = allocation.max_possible_allocation(remaining_quota=10.0, quota_unit='TB', min_increment=1.0)
        assert result == 2.0

    def test_max_possible_allocation_allocation_amount_none_rounds_to_two_decimals(self):
        """Test max_possible_allocation when allocation_amount is None rounds to 2 decimal places."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=None,
            users_allotment=BillingQuota(amount=1.333, unit=StorageUnit.TB),
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=2.666, quota_unit='TB', min_increment=0.1)
        assert result == 4.0  # 2.666 + 1.333 = 3.999 -> round(4.0, 2) = 4.0

    def test_max_possible_allocation_floors_to_min_increment(self):
        """Test max_possible_allocation floors result to nearest min_increment when allocation_amount is set."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=5.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=2.0, unit=StorageUnit.TB)],
        )
        # allocation_available = 5 - 2 = 3 TB, remaining_quota=2.95 -> max_possible = min(2.95, 3) = 2.95
        # floor(2.95 / 0.1) * 0.1 = 2.9
        result = allocation.max_possible_allocation(remaining_quota=2.95, quota_unit='TB', min_increment=0.1)
        assert result == 2.9

    def test_max_possible_allocation_other_allotments_exceed_allocation(self):
        """Test max_possible_allocation when other allotments exceed allocation_amount."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=5.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=10.0, unit=StorageUnit.TB)],
        )
        # allocation_available_tb = max(0, 5 - 10) = 0
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 0.0

    def test_max_possible_allocation_quota_unit_gb_no_allotments(self):
        """Test max_possible_allocation with GB quota unit without existing allotment."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=1.0,  # 1 TB
            users_allotment=None,
            other_allotments=[],
        )
        # allocation_available = 1 TB = 1000 GB, min(500, 1000) = 500
        result = allocation.max_possible_allocation(remaining_quota=500.0, quota_unit='GB', min_increment=1.0)
        assert result == 500.0

    def test_max_possible_allocation_quota_unit_gb_with_allotments(self):
        """Test max_possible_allocation with GB quota unit with existing allotment."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=2.0,  # 1 TB
            users_allotment=BillingQuota(amount=500, unit=StorageUnit.GB),
            other_allotments=[],
        )
        # allocation_available = 2 TB = 2000 GB, min(500 + 500, 2000) = 1000
        result = allocation.max_possible_allocation(remaining_quota=500.0, quota_unit='GB', min_increment=1.0)
        assert result == 1000.0

    def test_create_with_user_in_allotments(self):
        """Test create extracts user allotment for matching user_id."""
        allotments = [
            self._create_mock_allotment(amount=2.0, units='TB', user_id=1),
            self._create_mock_allotment(amount=3.0, units='TB', user_id=2),
        ]
        result = NoCostQuotaAllocation.create(user_id=1, allocation_amount=10.0, allotments=allotments)

        assert result.user_id == 1
        assert result.allocation_amount == 10.0
        assert result.users_allotment is not None
        assert result.users_allotment.amount == 2.0
        assert result.users_allotment.unit == StorageUnit.TB
        assert len(result.other_allotments) == 1
        assert result.other_allotments[0].amount == 3.0

    def test_create_without_user_in_allotments(self):
        """Test create sets users_allotment to None when user not in allotments."""
        allotments = [
            self._create_mock_allotment(amount=2.0, units='TB', user_id=2),
            self._create_mock_allotment(amount=3.0, units='TB', user_id=3),
        ]
        result = NoCostQuotaAllocation.create(user_id=1, allocation_amount=10.0, allotments=allotments)

        assert result.users_allotment is None
        assert len(result.other_allotments) == 2

    def test_create_with_empty_allotments(self):
        """Test create with empty allotments."""
        result = NoCostQuotaAllocation.create(user_id=1, allocation_amount=10.0, allotments=[])

        assert result.users_allotment is None
        assert result.other_allotments == []

    def test_create_with_gb_units(self):
        """Test create correctly parses GB units."""
        allotments = [
            self._create_mock_allotment(amount=1000.0, units='GB', user_id=1),
        ]
        result = NoCostQuotaAllocation.create(user_id=1, allocation_amount=5.0, allotments=allotments)

        assert result.users_allotment.amount == 1000.0
        assert result.users_allotment.unit == StorageUnit.GB
        assert result.users_allotment.normalized_amount == 1.0
