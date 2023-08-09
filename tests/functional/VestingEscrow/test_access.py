import ape
from ape.utils import ZERO_ADDRESS


def test_disown(vesting, ychad):
    receipt = vesting.disown(sender=ychad)
    disowned = vesting.Disowned.from_receipt(receipt)[0]

    assert disowned == vesting.Disowned(ychad)
    assert vesting.owner() == ZERO_ADDRESS


def test_disown_not_owner(vesting, recipient):
    with ape.reverts():  # dev_message="dev: not owner")
        vesting.disown(sender=recipient)


def test_set_open_claim(vesting, recipient):
    receipt = vesting.set_open_claim(False, sender=recipient)
    open_claim = vesting.SetOpenClaim.from_receipt(receipt)[0]
    assert not vesting.open_claim()
    assert vesting.SetOpenClaim() == open_claim

    # test state doens't change after similar change
    receipt = vesting.set_open_claim(False, sender=recipient)
    open_claim = vesting.SetOpenClaim.from_receipt(receipt)[0]
    assert not vesting.open_claim()
    assert vesting.SetOpenClaim() == open_claim


def test_set_open_claim_not_recipient(vesting, ychad):
    with ape.reverts():  # dev_message="dev: not recipient")
        vesting.set_open_claim(False, sender=ychad)
