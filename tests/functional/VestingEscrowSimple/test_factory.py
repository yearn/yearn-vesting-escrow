import boa
import pytest

from tests.helpers import ZERO_ADDRESS, at, deploy, events


def deploy_escrow(
    factory,
    token,
    funder,
    recipient,
    owner,
    amount,
    duration,
    start,
    *,
    cliff=0,
    open_claim=True,
    support_vyper=0,
    yield_to_owner=False,
):
    return factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start,
        cliff,
        open_claim,
        support_vyper,
        owner,
        yield_to_owner,
        sender=funder,
    )


def test_factory_configuration(vesting_factory, vesting_target, vyper_donation):
    assert vesting_factory.version() == 2
    assert vesting_factory.TARGET() == vesting_target.address
    assert vesting_factory.VYPER() == vyper_donation


def test_legacy_minimal_deploy_overload(
    chain,
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)

    escrow_address = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)

    assert escrow.start_time() == chain.pending_timestamp
    assert escrow.cliff_length() == 0
    assert escrow.open_claim()
    assert escrow.owner() == owner
    assert not escrow.yield_to_owner()


def test_deploys_standard_escrow(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
    cliff_duration,
    open_claim,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    escrow_address = deploy_escrow(
        vesting_factory,
        token,
        owner,
        recipient,
        owner,
        amount,
        duration,
        start_time,
        cliff=cliff_duration,
        open_claim=open_claim,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    created = events(vesting_factory, "VestingEscrowCreated", include_child_logs=False)

    assert len(created) == 1
    event = created[0]
    configured = events(vesting_factory, "VestingEscrowConfigured", include_child_logs=False)[0]
    assert event.funder == owner
    assert event.token == token.address
    assert event.recipient == recipient
    assert event.escrow == escrow.address
    assert event.amount == amount
    assert event.vesting_start == start_time
    assert event.vesting_duration == duration
    assert event.cliff_length == cliff_duration
    assert event.open_claim == open_claim
    assert configured.escrow == escrow.address
    assert configured.owner == owner
    assert configured.asset == token.address
    assert not configured.yield_to_owner
    assert configured.principal == amount

    assert vesting_factory.escrows_length() == 1
    assert vesting_factory.escrows(0) == escrow.address

    assert escrow.version() == 2
    assert escrow.initialized()
    assert escrow.token() == token.address
    assert escrow.asset() == token.address
    assert escrow.recipient() == recipient
    assert escrow.owner() == owner
    assert escrow.yield_recipient() == ZERO_ADDRESS
    assert not escrow.yield_to_owner()
    assert escrow.total_locked() == amount
    assert escrow.total_principal() == amount
    assert token.balanceOf(escrow) == amount


def test_deploys_yield_escrow(
    vesting_factory,
    owner,
    recipient,
    vault,
    asset_token,
    amount,
    duration,
    start_time,
):
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    escrow_address = deploy_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        owner,
        amount,
        duration,
        start_time,
        yield_to_owner=True,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    event = events(vesting_factory, "VestingEscrowCreated", include_child_logs=False)[0]
    configured = events(vesting_factory, "VestingEscrowConfigured", include_child_logs=False)[0]

    assert event.escrow == escrow.address
    assert configured.escrow == escrow.address
    assert configured.owner == owner
    assert configured.yield_to_owner
    assert configured.asset == asset_token.address
    assert configured.principal == amount
    assert escrow.asset() == asset_token.address
    assert escrow.yield_recipient() == owner
    assert escrow.yield_to_owner()
    assert vault.balanceOf(escrow) == amount


def test_donation(
    vesting_factory,
    vyper_donation,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    support = 25
    donation = amount * support // 10_000
    token.mint(owner, amount + donation, sender=owner)
    token.approve(vesting_factory, amount + donation, sender=owner)

    deploy_escrow(
        vesting_factory,
        token,
        owner,
        recipient,
        owner,
        amount,
        duration,
        start_time,
        support_vyper=support,
    )

    assert token.balanceOf(vyper_donation) == donation


def test_donation_is_safe_at_amount_and_rate_limits(
    vesting_factory,
    vyper_donation,
    owner,
    recipient,
    token,
    duration,
    start_time,
):
    amount = 2**128 - 1
    token.mint(owner, amount * 2, sender=owner)
    token.approve(vesting_factory, amount * 2, sender=owner)

    deploy_escrow(
        vesting_factory,
        token,
        owner,
        recipient,
        owner,
        amount,
        duration,
        start_time,
        support_vyper=10_000,
    )

    assert token.balanceOf(vyper_donation) == amount


def test_zero_donation_recipient_is_allowed_when_support_is_zero(
    vesting_target,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    factory = deploy("VestingEscrowFactory", vesting_target, ZERO_ADDRESS, sender=owner)
    token.mint(owner, amount, sender=owner)
    token.approve(factory, amount, sender=owner)

    deploy_escrow(factory, token, owner, recipient, owner, amount, duration, start_time)


def test_donation_requires_recipient(
    vesting_target,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    factory = deploy("VestingEscrowFactory", vesting_target, ZERO_ADDRESS, sender=owner)
    token.mint(owner, amount * 2, sender=owner)
    token.approve(factory, amount * 2, sender=owner)

    with boa.reverts(dev="invalid donation recipient"):
        deploy_escrow(
            factory,
            token,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            support_vyper=1,
        )


def test_requires_allowance(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
        )


@pytest.mark.parametrize("support", [10_001, 2**256 - 1])
def test_rejects_invalid_donation_rate(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
    support,
):
    with boa.reverts(dev="donation exceeds 100%"):
        deploy_escrow(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            support_vyper=support,
        )


@pytest.mark.parametrize("bad_recipient", [ZERO_ADDRESS, "owner", "token"])
def test_rejects_invalid_recipient(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
    bad_recipient,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    resolved = owner if bad_recipient == "owner" else token if bad_recipient == "token" else bad_recipient

    with boa.reverts(dev="invalid recipient"):
        deploy_escrow(
            vesting_factory,
            token,
            owner,
            resolved,
            owner,
            amount,
            duration,
            start_time,
        )


def test_zero_owner_is_allowed_in_standard_mode(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)

    escrow_address = deploy_escrow(
        vesting_factory,
        token,
        owner,
        recipient,
        ZERO_ADDRESS,
        amount,
        duration,
        start_time,
    )
    escrow = at("VestingEscrowSimple", escrow_address)

    assert escrow.owner() == ZERO_ADDRESS
    assert escrow.yield_recipient() == ZERO_ADDRESS
    assert not escrow.yield_to_owner()


def test_yield_mode_requires_nonzero_owner(
    vesting_factory,
    owner,
    recipient,
    vault,
    amount,
    duration,
    start_time,
):
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    with boa.reverts(dev="invalid yield recipient"):
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            ZERO_ADDRESS,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )


@pytest.mark.parametrize(
    ("amount_override", "duration_override", "cliff_override", "error"),
    [
        (0, None, 0, "amount must be > 0"),
        (2**128, None, 0, "amount too large"),
        (None, 0, 0, "invalid vesting period"),
        (None, 2**64, 0, "duration too long"),
        (None, 10, 11, "invalid cliff"),
    ],
)
def test_rejects_invalid_schedule(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
    amount_override,
    duration_override,
    cliff_override,
    error,
):
    actual_amount = amount if amount_override is None else amount_override
    actual_duration = duration if duration_override is None else duration_override
    funding = max(amount, actual_amount)
    token.mint(owner, funding, sender=owner)
    token.approve(vesting_factory, funding, sender=owner)

    with boa.reverts(dev=error):
        deploy_escrow(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            actual_amount,
            actual_duration,
            start_time,
            cliff=cliff_override,
        )


def test_plain_token_cannot_enable_yield(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    balance_before = token.balanceOf(owner)
    allowance_before = token.allowance(owner, vesting_factory)
    escrows_before = vesting_factory.escrows_length()

    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )

    assert token.balanceOf(owner) == balance_before
    assert token.allowance(owner, vesting_factory) == allowance_before
    assert vesting_factory.escrows_length() == escrows_before
    assert events(vesting_factory, "VestingEscrowCreated", include_child_logs=False) == []


def test_partial_vault_cannot_enable_yield(
    vesting_factory,
    owner,
    recipient,
    asset_token,
    amount,
    duration,
    start_time,
):
    vault = deploy("test/PartialERC4626", asset_token, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    balance_before = vault.balanceOf(owner)
    allowance_before = vault.allowance(owner, vesting_factory)
    escrows_before = vesting_factory.escrows_length()

    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )

    assert vault.balanceOf(owner) == balance_before
    assert vault.allowance(owner, vesting_factory) == allowance_before
    assert vesting_factory.escrows_length() == escrows_before
    assert events(vesting_factory, "VestingEscrowCreated", include_child_logs=False) == []


def test_yield_mode_requires_contract_asset(
    vesting_factory,
    owner,
    recipient,
    amount,
    duration,
    start_time,
):
    vault = deploy("test/MockERC4626", owner, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    balance_before = vault.balanceOf(owner)
    allowance_before = vault.allowance(owner, vesting_factory)
    escrows_before = vesting_factory.escrows_length()

    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )

    assert vault.balanceOf(owner) == balance_before
    assert vault.allowance(owner, vesting_factory) == allowance_before
    assert vesting_factory.escrows_length() == escrows_before
    assert events(vesting_factory, "VestingEscrowCreated", include_child_logs=False) == []


def test_fee_charging_share_token_is_rejected(
    vesting_factory,
    owner,
    recipient,
    vault,
    amount,
    duration,
    start_time,
):
    vault.set_transfer_fee_bps(100, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    with boa.reverts(dev="escrow not funded"):
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )

    assert vault.balanceOf(owner) == amount


def test_rejects_zero_initial_principal(
    vesting_factory,
    owner,
    recipient,
    asset_token,
    duration,
    start_time,
):
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    vault.set_assets_per_share(1, sender=owner)
    vault.mint(owner, 1, sender=owner)
    vault.approve(vesting_factory, 1, sender=owner)

    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            1,
            duration,
            start_time,
            yield_to_owner=True,
        )


def test_rejects_principal_above_limit(
    vesting_factory,
    owner,
    recipient,
    vault,
    duration,
    start_time,
):
    amount = 10**18
    vault.set_assets_per_share(2**128, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    with boa.reverts():
        deploy_escrow(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start_time,
            yield_to_owner=True,
        )


def test_implementation_cannot_be_initialized(
    vesting_target,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    with boa.reverts(dev="can only initialize once"):
        vesting_target.initialize(
            owner,
            token,
            recipient,
            amount,
            start_time,
            start_time + duration,
            0,
            True,
            False,
            sender=owner,
        )


def test_initialized_proxy_cannot_be_reinitialized(
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
    start_time,
    end_time,
    cliff_duration,
    accounts,
):
    state = (
        yield_vesting.owner(),
        yield_vesting.recipient(),
        yield_vesting.token(),
        yield_vesting.total_locked(),
        yield_vesting.total_principal(),
        yield_vesting.start_time(),
        yield_vesting.end_time(),
    )

    with boa.reverts(dev="can only initialize once"):
        yield_vesting.initialize(
            owner,
            vault,
            recipient,
            amount,
            start_time,
            end_time,
            cliff_duration,
            True,
            True,
            sender=accounts[4],
        )

    assert (
        yield_vesting.owner(),
        yield_vesting.recipient(),
        yield_vesting.token(),
        yield_vesting.total_locked(),
        yield_vesting.total_principal(),
        yield_vesting.start_time(),
        yield_vesting.end_time(),
    ) == state
