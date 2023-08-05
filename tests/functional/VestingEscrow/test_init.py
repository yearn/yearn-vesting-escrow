import ape


def test_reinit_impossible(vesting, ychad, token):
    vesting.renounce_ownership(sender=ychad)
    with ape.reverts(dev_message="dev: can only initialize once"):
        vesting.initialize(ychad, token, ychad, 0, 0, 0, 0, sender=ychad)
