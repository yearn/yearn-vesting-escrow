import ape
from ape.utils import ZERO_ADDRESS


def test_disown(vesting, owner):
    receipt = vesting.disown(sender=owner)
    disowned = vesting.Disowned.from_receipt(receipt)[0]

    assert disowned == vesting.Disowned(owner)
    assert vesting.owner() == ZERO_ADDRESS


def test_disown_not_owner(vesting, recipient):
    with ape.reverts(dev_message="dev: not owner"):
        vesting.disown(sender=recipient)


def test_set_open_claim(vesting, recipient):
    receipt = vesting.set_open_claim(False, sender=recipient)
    open_claim = vesting.SetOpenClaim.from_receipt(receipt)[0]
    assert not vesting.open_claim()
    assert vesting.SetOpenClaim() == open_claim

    # test state doesn't change after similar change
    receipt = vesting.set_open_claim(False, sender=recipient)
    open_claim = vesting.SetOpenClaim.from_receipt(receipt)[0]
    assert not vesting.open_claim()
    assert vesting.SetOpenClaim() == open_claim


def test_set_open_claim_not_recipient(vesting, owner):
    with ape.reverts(dev_message="dev: not recipient"):
        vesting.set_open_claim(False, sender=owner)
