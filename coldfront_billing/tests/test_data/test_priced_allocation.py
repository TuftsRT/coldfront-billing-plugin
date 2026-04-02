from unittest.mock import Mock

from coldfront_billing.constants import COST_ATTRIBUTE_NAME
from coldfront_billing.data.quota import PricedAllocation

from .allocation_mocks import (
    create_ncq_allotment,
    mock_allocation_for_priced,
    storage_resource_with_cost,
)


class TestPricedAllocation:
    """Tests for PricedAllocation.create and cost_per_tb (via get_cost_per_tb)."""

    def test_create_sets_cost_per_tb_from_storage_resource(self):
        """cost_per_tb comes from the first prefetched storage resource cost attribute."""
        allocation = mock_allocation_for_priced(
            storage_resources=[storage_resource_with_cost('127.5')],
        )
        priced = PricedAllocation.create(1, allocation)
        assert priced.cost_per_tb == 127.5
        assert priced.allocation_amount == 10.0
        assert priced.allocation_id == 1

    def test_create_cost_per_tb_zero_without_storage_resources(self):
        """No storage resources yields default cost 0."""
        allocation = mock_allocation_for_priced(storage_resources=[])
        assert PricedAllocation.create(1, allocation).cost_per_tb == 0.0

    def test_create_cost_per_tb_zero_when_resource_has_no_cost_attrs(self):
        """Storage resource without cost prefetch yields default cost 0."""
        resource = Mock()
        setattr(resource, COST_ATTRIBUTE_NAME, None)
        allocation = mock_allocation_for_priced(storage_resources=[resource])
        assert PricedAllocation.create(1, allocation).cost_per_tb == 0.0

    def test_create_cost_per_tb_zero_when_cost_list_empty(self):
        """Empty cost attribute list yields default cost 0."""
        resource = Mock()
        setattr(resource, COST_ATTRIBUTE_NAME, [])
        allocation = mock_allocation_for_priced(storage_resources=[resource])
        assert PricedAllocation.create(1, allocation).cost_per_tb == 0.0

    def test_create_cost_per_tb_defaults_on_invalid_cost_value(self):
        """Non-numeric cost value falls back to default 0."""
        allocation = mock_allocation_for_priced(
            storage_resources=[storage_resource_with_cost('not-a-number')],
        )
        assert PricedAllocation.create(1, allocation).cost_per_tb == 0.0

    def test_create_cost_per_tb_defaults_when_negative(self):
        """Negative parsed cost falls back to default 0."""
        allocation = mock_allocation_for_priced(
            storage_resources=[storage_resource_with_cost('-50')],
        )
        assert PricedAllocation.create(1, allocation).cost_per_tb == 0.0

    def test_create_preserves_no_cost_quota_base_fields(self):
        """PricedAllocation still builds user allotment and other_allotments like the base class."""
        allotments = [
            create_ncq_allotment(2.0, 'TB', user_id=1),
            create_ncq_allotment(1.0, 'TB', user_id=2),
        ]
        allocation = mock_allocation_for_priced(
            all_allotments=allotments,
            quota_attrs=[Mock(value='8')],
            storage_resources=[storage_resource_with_cost('100')],
        )
        priced = PricedAllocation.create(1, allocation)
        assert priced.cost_per_tb == 100.0
        assert priced.allocation_amount == 8.0
        assert priced.users_allotment is not None and priced.users_allotment.amount == 2.0
        assert len(priced.other_allotments) == 1 and priced.other_allotments[0].amount == 1.0
