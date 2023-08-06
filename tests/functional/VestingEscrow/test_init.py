import ape


def test_vesting_reinit(
    vesting,
    ychad,
    receiver,
    vesting_factory,
    token,
    amount,
    start_time,
    cliff_duration,
    duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    # same salt reverts
    with ape.reverts(dev_message="dev: CHECK_NONZERO"):
        vesting_factory.deploy_vesting_contract(
            token,
            receiver,
            amount,
            duration,
            start_time,
            cliff_duration,
            sender=ychad,
        )
