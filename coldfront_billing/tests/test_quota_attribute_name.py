"""Which allocation attribute billing reads the quota from, when no setting names it."""

import pytest

from coldfront_billing.constants import default_quota_attribute_name


@pytest.fixture(autouse=True)
def no_quota_settings(monkeypatch):
    monkeypatch.delenv("COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME", raising=False)
    monkeypatch.delenv("QUOTA_ATTRIBUTE_NAME", raising=False)


WITHOUT_STORAGE = ["coldfront.core.allocation", "coldfront_billing"]
WITH_STORAGE = ["coldfront.core.allocation", "storage", "coldfront_billing"]


def test_without_the_storage_plugin_it_is_quota_in_terabyte():
    assert default_quota_attribute_name(WITHOUT_STORAGE) == "quota_in_terabyte"


@pytest.mark.parametrize("entry", ["storage", "storage.apps.StorageConfig"])
def test_with_the_storage_plugin_it_is_storages_default(entry):
    assert default_quota_attribute_name(["coldfront.core.allocation", entry]) == "Storage Quota (TB)"


def test_an_app_that_only_starts_with_storage_isnt_it():
    assert default_quota_attribute_name(["coldfront.core.allocation", "storage_reports"]) == "quota_in_terabyte"


def test_with_the_storage_plugin_it_follows_storages_setting(monkeypatch):
    monkeypatch.setenv("QUOTA_ATTRIBUTE_NAME", "Quota (TiB)")

    assert default_quota_attribute_name(WITH_STORAGE) == "Quota (TiB)"


def test_billings_own_setting_wins(monkeypatch):
    monkeypatch.setenv("QUOTA_ATTRIBUTE_NAME", "Quota (TiB)")
    monkeypatch.setenv("COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME", "Billed Quota")

    assert default_quota_attribute_name(WITH_STORAGE) == "Billed Quota"


def test_without_a_list_it_reads_the_settings():
    # billing's own tests don't install the storage plugin
    assert default_quota_attribute_name() == default_quota_attribute_name(WITHOUT_STORAGE)
