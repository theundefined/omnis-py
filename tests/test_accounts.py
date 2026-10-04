import pytest

from omnis.cli import (
    DEMO_PASSWORD,
    DEMO_USERNAME,
    _apply_demo_mode,
    _enabled_accounts,
    _exit_demo_mode,
    _select_account,
    _set_account_enabled,
    _set_account_timeout,
)
from omnis.tenants import MOCK_TENANT


def _account(**overrides):
    account = {
        "username": "user",
        "password": "pw",
        "base_url": "https://example.com",
        "institution": "INST",
        "view": "INST:VIEW",
        "tenant_name": "Example Library",
    }
    account.update(overrides)
    return account


def test_enabled_accounts_filters_disabled():
    accounts = [_account(username="a", enabled=True), _account(username="b", enabled=False), _account(username="c")]
    result = _enabled_accounts(accounts)
    assert [a["username"] for a in result] == ["a", "c"]


def test_apply_demo_mode_from_empty_config():
    result = _apply_demo_mode([])
    assert len(result) == 1
    demo = result[0]
    assert demo["is_demo"] is True
    assert demo["enabled"] is True
    assert demo["base_url"] == MOCK_TENANT["base_url"]
    assert demo["timeout"] == MOCK_TENANT["default_timeout"]
    assert demo["username"] == DEMO_USERNAME
    assert demo["password"] == DEMO_PASSWORD


def test_apply_demo_mode_disables_existing_enabled_accounts():
    accounts = [_account(enabled=True)]
    result = _apply_demo_mode(accounts)
    real_account = next(a for a in result if not a.get("is_demo"))
    assert real_account["enabled"] is False
    assert real_account["disabled_by_demo"] is True


def test_apply_demo_mode_is_idempotent():
    accounts = _apply_demo_mode([_account(enabled=True)])
    accounts = _apply_demo_mode(accounts)
    demo_accounts = [a for a in accounts if a.get("is_demo")]
    assert len(demo_accounts) == 1


def test_apply_demo_mode_reuses_existing_disabled_demo_account():
    accounts = [_account(username=DEMO_USERNAME, is_demo=True, enabled=False)]
    result = _apply_demo_mode(accounts)
    assert len(result) == 1
    assert result[0]["enabled"] is True


def test_exit_demo_mode_restores_only_demo_disabled_accounts():
    manually_disabled = _account(username="manual", enabled=False)
    demo_disabled = _account(username="was-active", enabled=False, disabled_by_demo=True)
    demo_account = _account(username=DEMO_USERNAME, is_demo=True, enabled=True)
    accounts = [manually_disabled, demo_disabled, demo_account]

    result = _exit_demo_mode(accounts)

    assert result[0]["enabled"] is False
    assert result[1]["enabled"] is True
    assert "disabled_by_demo" not in result[1]
    assert result[2]["enabled"] is False


def test_set_account_enabled_by_index():
    accounts = [_account(username="a"), _account(username="b")]
    _set_account_enabled(accounts, 2, False)
    assert accounts[0].get("enabled", True) is True
    assert accounts[1]["enabled"] is False


def test_set_account_enabled_out_of_range_raises_index_error():
    accounts = [_account()]
    with pytest.raises(IndexError):
        _set_account_enabled(accounts, 5, True)


def test_set_account_enabled_true_clears_disabled_by_demo_marker():
    accounts = [_account(enabled=False, disabled_by_demo=True)]
    _set_account_enabled(accounts, 1, True)
    assert accounts[0]["enabled"] is True
    assert "disabled_by_demo" not in accounts[0]


def test_set_account_timeout_by_index():
    accounts = [_account(), _account()]
    _set_account_timeout(accounts, 2, 45.0)
    assert "timeout" not in accounts[0]
    assert accounts[1]["timeout"] == 45.0


def test_old_config_without_new_keys_treated_as_enabled_default_timeout():
    account = _account()
    assert account.get("enabled", True) is True
    assert account.get("timeout", 30.0) == 30.0


def test_select_account_refuses_to_guess_between_several_enabled():
    accounts = [{"username": "a"}, {"username": "b"}]
    account, error = _select_account(accounts, None)
    assert account is None
    assert "--account" in error


def test_select_account_uses_the_only_enabled_one():
    accounts = [{"username": "a", "enabled": False}, {"username": "b"}]
    assert _select_account(accounts, None) == ({"username": "b"}, None)


def test_select_account_by_one_based_index():
    accounts = [{"username": "a"}, {"username": "b"}]
    assert _select_account(accounts, 2) == ({"username": "b"}, None)


@pytest.mark.parametrize("index", [0, 3, -1])
def test_select_account_rejects_out_of_range_index(index):
    account, error = _select_account([{"username": "a"}, {"username": "b"}], index)
    assert account is None
    assert "No account at index" in error


def test_select_account_rejects_disabled_index():
    account, error = _select_account([{"username": "a", "enabled": False}], 1)
    assert account is None
    assert "disabled" in error


def test_select_account_no_enabled_accounts():
    account, error = _select_account([{"username": "a", "enabled": False}], None)
    assert account is None
    assert "No enabled accounts" in error
