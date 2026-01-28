import pytest
from django.conf import settings
from django.test import override_settings

from coldfront_billing.apps import ColdfrontBillingConfig


@pytest.mark.django_db
class TestColdfrontBillingConfig:
    """Test suite for ColdfrontBillingConfig."""

    def test_ready_registers_context_processor(self):
        """Test that ready() method registers the context processor."""
        config = ColdfrontBillingConfig('coldfront_billing', None)
        context_processor = 'coldfront_billing.context_processor.billing_role'

        config.ready()

        # Verify it's in the list
        final_processors = settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', [])
        assert context_processor in final_processors

    def test_ready_is_idempotent(self):
        """Test that calling ready() multiple times doesn't duplicate processors."""
        config = ColdfrontBillingConfig('coldfront_billing', None)
        context_processor = 'coldfront_billing.context_processor.billing_role'

        # Call ready() first time
        config.ready()
        first_count = len(settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', []))

        # Call ready() second time
        config.ready()
        second_count = len(settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', []))

        # Count should be the same (idempotent)
        assert first_count == second_count
        assert settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', []).count(context_processor) == 1

    @override_settings(
        TEMPLATES=[
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
            },
        ]
    )
    def test_ready_creates_missing_settings(self):
        """Test that ready() creates OPTIONS and context_processors if missing."""
        config = ColdfrontBillingConfig('coldfront_billing', None)
        context_processor = 'coldfront_billing.context_processor.billing_role'

        config.ready()

        # Verify context processor was added
        processors = settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', [])
        assert context_processor in processors
