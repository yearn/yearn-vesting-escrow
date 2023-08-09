import ape
from ape.utils import ZERO_ADDRESS


def test_approve_fail(vesting_factory, ychad, recipient, token, amount, duration):
    with ape.reverts():  # no error message, depends on token
        vesting_factory.deploy_vesting_contract(
            token, recipient, amount, duration, ychad, sender=ychad
        )


def test_target_is_set(vesting_factory, vesting_target):
    assert vesting_factory.TARGET() == vesting_target


def test_deploy(
    vesting_factory,
    ychad,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token, recipient, amount, duration, start_time, cliff_duration, sender=ychad
    )

    vesting_escrow_address = receipt.return_value
    vesting_escrows = vesting_factory.VestingEscrowCreated.from_receipt(receipt)

    assert len(vesting_escrows) == 1
    assert vesting_escrows[0] == vesting_factory.VestingEscrowCreated(
        ychad,
        token,
        recipient,
        vesting_escrow_address,
        amount,
        start_time,
        duration,
        cliff_duration,
        open_claim,
    )


def test_init_variables(
    project,
    vesting_factory,
    ychad,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        sender=ychad,
    )

    vesting_escrow = project.VestingEscrowSimple.at(receipt.return_value)

    assert vesting_escrow.token() == token
    assert vesting_escrow.owner() == ychad
    assert vesting_escrow.recipient() == recipient
    assert vesting_escrow.start_time() == start_time
    assert vesting_escrow.end_time() == start_time + duration
    assert vesting_escrow.total_locked() == amount
    assert vesting_escrow.open_claim()


def test_token_events(
    vesting_factory,
    ychad,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token, recipient, amount, duration, start_time, cliff_duration, sender=ychad
    )

    vesting_escrow = receipt.return_value
    transfers = token.Transfer.from_receipt(receipt)
    approval = token.Approval.from_receipt(receipt)

    assert len(transfers) == 1
    assert transfers[0] == token.Transfer(ychad, vesting_escrow, amount)

    assert len(approval) == 1
    assert approval[0] == token.Approval(ychad, vesting_factory, 0)


def test_vesting_duration(
    vesting_factory,
    ychad,
    recipient,
    token,
    amount,
    start_time,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    with ape.reverts():  # dev_message="dev: duration must be > 0")
        vesting_factory.deploy_vesting_contract(
            token, recipient, amount, 0, start_time, cliff_duration, sender=ychad
        )


def test_wrong_recipient(
    vesting_factory,
    ychad,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
):
    token.approve(vesting_factory, amount, sender=ychad)

    for wrong_recipient in [vesting_factory, ZERO_ADDRESS, token, ychad]:
        with ape.reverts():  # dev_message="dev: wrong recipient"):
            vesting_factory.deploy_vesting_contract(
                token,
                wrong_recipient,
                amount,
                duration,
                start_time,
                cliff_duration,
                open_claim,
                sender=ychad,
            )


def test_use_transfer(
    chain,
    vesting_factory,
    ychad,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    chain.pending_timestamp += start_time + duration

    with ape.reverts():  # dev_message="dev: just use a transfer, dummy")
        vesting_factory.deploy_vesting_contract(
            token, recipient, amount, duration, start_time, cliff_duration, sender=ychad
        )
