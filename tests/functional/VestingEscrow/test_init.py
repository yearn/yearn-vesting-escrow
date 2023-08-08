import ape


def test_vesting_reinit(
    vesting,
    ychad,
    receiver,
    token,
    amount,
    start_time,
    end_time,
    cliff_duration,
):
    # same salt reverts
    with ape.reverts(): # dev_message="dev: can only initialize once"):
        vesting.initialize(
            ychad,
            token,
            receiver,
            amount,
            start_time,
            end_time,
            cliff_duration,
            True,
            sender=ychad,
        )
