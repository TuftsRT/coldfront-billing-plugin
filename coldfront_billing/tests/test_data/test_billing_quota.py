from decimal import Decimal

from coldfront_billing.data import BillingQuota
from coldfront_billing.enums import StorageUnit


class TestBillingQuota:
    """Test suite for BillingQuota class."""

    def test_normalized_amount_tb(self):
        """Test normalized_amount for TB unit (1:1 conversion)."""
        ncq = BillingQuota(amount=Decimal('5.0'), unit=StorageUnit.TB)
        assert ncq.normalized_amount == Decimal('5.0')

    def test_normalized_amount_gb(self):
        """Test normalized_amount for GB unit (converts to TB)."""
        ncq = BillingQuota(amount=Decimal('1000.0'), unit=StorageUnit.GB)
        assert ncq.normalized_amount == Decimal('1.0')

    def test_normalized_amount_gb_fractional(self):
        """Test normalized_amount for fractional GB."""
        ncq = BillingQuota(amount=Decimal('500.0'), unit=StorageUnit.GB)
        assert ncq.normalized_amount == Decimal('0.5')
