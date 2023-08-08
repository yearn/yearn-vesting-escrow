import pytest
import ape
from ape.utils import ZERO_ADDRESS


def set_free():
    pass


def set_open_claim():
    pass


@pytest.mark.skip("refactor")
def test_commit_admin_only(vesting, ytrades):
    with ape.reverts(dev_message="dev: admin only"):
        vesting.commit_transfer_ownership(ytrades, sender=ytrades)

@pytest.mark.skip("refactor")
def test_apply_admin_only(vesting, ytrades):
    with ape.reverts(dev_message="dev: future admin only"):
        vesting.apply_transfer_ownership(sender=ytrades)

@pytest.mark.skip("refactor")
def test_commit_transfer_ownership(vesting, ychad, ytrades):
    vesting.commit_transfer_ownership(ytrades, sender=ychad)

    assert vesting.admin() == ychad
    assert vesting.future_admin() == ytrades

@pytest.mark.skip("refactor")
def test_apply_transfer_ownership(vesting, ychad, ytrades):
    vesting.commit_transfer_ownership(ytrades, sender=ychad)
    vesting.apply_transfer_ownership(sender=ytrades)

    assert vesting.admin() == ytrades

@pytest.mark.skip("refactor")
def test_apply_without_commit(vesting, ychad):
    with ape.reverts(dev_message="dev: future admin only"):
        vesting.apply_transfer_ownership(sender=ychad)

@pytest.mark.skip("refactor")
def test_renounce_ownership(vesting, ychad):
    vesting.renounce_ownership(sender=ychad)

    assert vesting.admin() == ZERO_ADDRESS
    assert vesting.future_admin() == ZERO_ADDRESS
