import ape


def test_approve_fail(vesting_factory, ychad, receiver, token, amount, duration):
    with ape.reverts("ERC20: transfer amount exceeds allowance"):
        vesting_factory.deploy_vesting_contract(
            token, receiver, amount, duration, ychad, sender=ychad
        )


def test_target_is_set(vesting_factory, vesting_target):
    assert vesting_factory.TARGET() == vesting_target


def test_deploy(
    vesting_factory,
    ychad,
    receiver,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token, receiver, amount, duration, start_time, cliff_duration, sender=ychad
    )

    vesting_escrow_address = receipt.return_value
    vesting_escrows = vesting_factory.VestingEscrowCreated.from_receipt(receipt)

    assert len(vesting_escrows) == 1
    assert vesting_escrows[0] == vesting_factory.VestingEscrowCreated(
        ychad,
        token,
        receiver,
        vesting_escrow_address,
        amount,
        start_time,
        duration,
        cliff_duration,
    )


def test_init_variables(
    project,
    vesting_factory,
    ychad,
    receiver,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token, receiver, amount, duration, start_time, cliff_duration, sender=ychad
    )

    vesting_escrow = project.VestingEscrowSimple.at(receipt.return_value)

    assert vesting_escrow.token() == token
    assert vesting_escrow.admin() == ychad
    assert vesting_escrow.recipient() == receiver
    assert vesting_escrow.start_time() == start_time
    assert vesting_escrow.end_time() == start_time + duration
    assert vesting_escrow.total_locked() == amount


def test_token_events(
    vesting_factory,
    ychad,
    receiver,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token, receiver, amount, duration, start_time, cliff_duration, sender=ychad
    )

    vesting_escrow = receipt.return_value
    transfers = token.Transfer.from_receipt(receipt)
    approval = token.Approval.from_receipt(receipt)

    assert len(transfers) == 2
    assert transfers[0] == token.Transfer(ychad, vesting_factory, amount)
    assert transfers[1] == token.Transfer(vesting_factory, vesting_escrow, amount)

    assert len(approval) == 3
    assert approval[0] == token.Approval(ychad, vesting_factory, 0)
    assert approval[1] == token.Approval(vesting_factory, vesting_escrow, amount)
    assert approval[2] == token.Approval(vesting_factory, vesting_escrow, 0)
