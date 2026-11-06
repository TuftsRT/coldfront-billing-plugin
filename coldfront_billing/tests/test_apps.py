import importlib

import pytest
from django.conf import settings
from django.test import override_settings

from coldfront_billing.apps import ColdfrontBillingConfig


@pytest.mark.django_db
class TestColdfrontBillingConfig:
    """Test suite for ColdfrontBillingConfig."""

    def _get_app_config(self):
        """Helper to create AppConfig instance with proper module."""
        # Import the actual module to provide to AppConfig
        app_module = importlib.import_module("coldfront_billing")
        return ColdfrontBillingConfig("coldfront_billing", app_module)

    def test_ready_registers_context_processor(self):
        """Test that ready() method registers the context processor."""
        app_config = self._get_app_config()
        context_processor = "coldfront_billing.context_processor.billing_role"

        app_config.ready()

        # Verify it's in the list
        final_processors = settings.TEMPLATES[0].get("OPTIONS", {}).get("context_processors", [])
        assert context_processor in final_processors

    def test_ready_is_idempotent(self):
        """Test that calling ready() multiple times doesn't duplicate processors."""
        app_config = self._get_app_config()
        context_processor = "coldfront_billing.context_processor.billing_role"

        # Call ready() first time
        app_config.ready()
        first_count = len(settings.TEMPLATES[0].get("OPTIONS", {}).get("context_processors", []))

        # Call ready() second time
        app_config.ready()
        second_count = len(settings.TEMPLATES[0].get("OPTIONS", {}).get("context_processors", []))

        # Count should be the same (idempotent)
        assert first_count == second_count
        assert settings.TEMPLATES[0].get("OPTIONS", {}).get("context_processors", []).count(context_processor) == 1

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            },
        ]
    )
    def test_ready_creates_missing_settings(self):
        """Test that ready() creates OPTIONS and context_processors if missing."""
        app_config = self._get_app_config()
        context_processor = "coldfront_billing.context_processor.billing_role"

        app_config.ready()

        # Verify context processor was added
        processors = settings.TEMPLATES[0].get("OPTIONS", {}).get("context_processors", [])
        assert context_processor in processors
