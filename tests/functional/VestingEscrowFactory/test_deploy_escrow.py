import pytest
import ape
from ape.utils import ZERO_ADDRESS

@pytest.mark.skip("awaiting ape bug fix")
def test_approve_fail(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    with ape.reverts():  # no error message, depends on token
        vesting_factory.deploy_vesting_contract(
            token,
            recipient,
            amount,
            duration,
            start_time,
            cliff_duration,
            open_claim,
            support_vyper,
            owner,
            sender=owner,
        )


def test_target_is_set(vesting_factory, vesting_target):
    assert vesting_factory.TARGET() == vesting_target


def test_vyper_is_set(vesting_factory, vyper_donation):
    assert vesting_factory.VYPER() == vyper_donation


def test_deploy(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        support_vyper,
        owner,
        sender=owner,
    )

    vesting_escrow_address = receipt.return_value
    vesting_escrows = vesting_factory.VestingEscrowCreated.from_receipt(receipt)

    assert len(vesting_escrows) == 1
    assert vesting_escrows[0] == vesting_factory.VestingEscrowCreated(
        owner,
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
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        support_vyper,
        sender=owner,
    )

    vesting_escrow = project.VestingEscrowSimple.at(receipt.return_value)

    assert vesting_escrow.token() == token
    assert vesting_escrow.owner() == owner
    assert vesting_escrow.recipient() == recipient
    assert vesting_escrow.start_time() == start_time
    assert vesting_escrow.end_time() == start_time + duration
    assert vesting_escrow.total_locked() == amount
    assert vesting_escrow.open_claim()


def test_transfer_events(
    vesting_factory,
    vyper_donation,
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        support_vyper,
        sender=owner,
    )
    vesting_escrow = receipt.return_value
    transfers = token.Transfer.from_receipt(receipt)

    assert len(transfers) == 2
    assert transfers[0] == token.Transfer(owner, vesting_escrow, amount)
    assert transfers[1] == token.Transfer(owner, vyper_donation, support_amount)


def test_vesting_duration(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    with ape.reverts(dev_message="dev: incorrect vesting cliff"):
        vesting_factory.deploy_vesting_contract(
            token,
            recipient,
            amount,
            0,
            start_time,
            cliff_duration,
            open_claim,
            support_vyper,
            sender=owner,
        )


def test_wrong_recipient(
    vesting_factory,
    owner,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)

    for wrong_recipient in [vesting_factory, ZERO_ADDRESS, token, owner]:
        with ape.reverts(dev_message="dev: wrong recipient"):
            vesting_factory.deploy_vesting_contract(
                token,
                wrong_recipient,
                amount,
                duration,
                start_time,
                cliff_duration,
                open_claim,
                support_vyper,
                sender=owner,
            )


def test_use_transfer(
    chain,
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    chain.pending_timestamp += start_time + duration

    with ape.reverts(dev_message="dev: just use a transfer, dummy"):
        vesting_factory.deploy_vesting_contract(
            token,
            recipient,
            amount,
            duration,
            start_time,
            cliff_duration,
            open_claim,
            support_vyper,
            sender=owner,
        )


@pytest.mark.skip("awaiting ape bug fix")
def test_vyper_donation(
    project,
    vesting_target,
    owner,
    recipient,
    token,
    amount,
    support_amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
    support_vyper,
):
    vyper_donation = ZERO_ADDRESS
    vesting_factory = owner.deploy(project.VestingEscrowFactory, vesting_target, vyper_donation)

    token.mint(owner, amount + support_amount, sender=owner)
    token.approve(vesting_factory, amount + support_amount, sender=owner)
    with ape.reverts(dev_message="dev: lost donation"):
        vesting_factory.deploy_vesting_contract(
            token,
            recipient,
            amount,
            duration,
            start_time,
            cliff_duration,
            open_claim,
            support_vyper,
            sender=owner,
        )


def test_vyper_donation_empty(
    project,
    vesting_target,
    owner,
    recipient,
    token,
    amount,
    start_time,
    duration,
    cliff_duration,
    open_claim,
):
    vyper_donation = ZERO_ADDRESS
    support_vyper = 0

    vesting_factory = owner.deploy(project.VestingEscrowFactory, vesting_target, vyper_donation)

    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        support_vyper,
        sender=owner,
    )
