import ape


def test_vesting_reinit(
    vesting,
    owner,
    recipient,
    token,
    amount,
    start_time,
    end_time,
    cliff_duration,
    open_claim,
):
    with ape.reverts(dev_message="dev: can only initialize once"):
        vesting.initialize(
            owner,
            token,
            recipient,
            amount,
            start_time,
            end_time,
            cliff_duration,
            open_claim,
            sender=owner,
        )
