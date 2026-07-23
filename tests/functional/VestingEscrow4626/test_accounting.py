import boa

from tests.helpers import ZERO_ADDRESS, at, deploy, events

SCALE = 10**18


def split(balance, value, remaining):
    if remaining == 0:
        return 0, balance
    if value <= remaining:
        return balance, 0
    principal_shares = remaining * balance // value
    if principal_shares * value // balance < remaining:
        principal_shares += 1
    return principal_shares, balance - principal_shares


def payout(principal_shares, remaining_before, remaining_after):
    if remaining_after == 0:
        return principal_shares
    whole = principal_shares // remaining_before
    remainder = principal_shares % remaining_before
    scaled_remainder = remainder * remaining_after
    reserve = whole * remaining_after + scaled_remainder // remaining_before
    if scaled_remainder % remaining_before:
        reserve += 1
    return principal_shares - reserve


def test_flat_rate_claims_shares(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)

    assert yield_vesting.claim_principal(sender=recipient) == vested
    assert vault.balanceOf(recipient) == vested
    assert vault.balanceOf(owner) == 0
    assert yield_vesting.claimed_principal_assets() == vested

    chain.pending_timestamp = end_time
    yield_vesting.claim_principal(sender=recipient)

    assert vault.balanceOf(recipient) == amount
    assert vault.balanceOf(yield_vesting) == 0


def test_claim_accepts_recipient_selected_beneficiary(
    chain,
    yield_vesting,
    recipient,
    cold_storage,
    vault,
    start_time,
    end_time,
):
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    claimed = yield_vesting.claim_principal(cold_storage, 2**256 - 1, sender=recipient)

    assert claimed > 0
    assert vault.balanceOf(cold_storage) == claimed


def test_partial_principal_claim_is_accounted_in_asset_units(
    chain,
    yield_vesting,
    recipient,
    vault,
    start_time,
    end_time,
):
    chain.pending_timestamp = start_time + (end_time - start_time) // 2
    claimable_assets = yield_vesting.claimable_principal_assets()
    partial_assets = claimable_assets // 3

    assert yield_vesting.claim_principal(recipient, partial_assets, sender=recipient) == partial_assets
    event = events(yield_vesting, "PrincipalClaim")[0]
    assert event.beneficiary == recipient
    assert event.principal_assets == partial_assets
    assert event.shares == partial_assets
    assert yield_vesting.claimed_principal_assets() == partial_assets
    assert vault.balanceOf(recipient) == partial_assets
    assert yield_vesting.claimable_principal_assets() == claimable_assets - partial_assets

    assert yield_vesting.claim_principal(sender=recipient) == claimable_assets - partial_assets
    assert yield_vesting.claimed_principal_assets() == claimable_assets


def test_regular_claim_preserves_yield_until_explicit_claim(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)
    balance = vault.balanceOf(yield_vesting)
    principal_pool, _ = split(balance, vault.convertToAssets(balance), amount)
    expected_claim = payout(principal_pool, amount, amount - vested)

    assert yield_vesting.claim_principal(sender=recipient) == expected_claim
    assert events(yield_vesting, "YieldClaim") == []
    assert vault.balanceOf(recipient) == expected_claim
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(yield_vesting) == balance - expected_claim
    assert yield_vesting.claimable_yield_shares() > 0
    assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= amount - vested

    chain.pending_timestamp = end_time
    yield_vesting.claim_principal(sender=recipient)
    yield_shares = vault.balanceOf(yield_vesting)

    assert yield_shares > 0
    assert yield_vesting.claimable_yield_shares() == yield_shares
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(recipient) + yield_shares == amount

    assert yield_vesting.claim_yield(sender=recipient) == yield_shares
    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(recipient) + vault.balanceOf(owner) == amount


def test_claim_yield_without_claiming_principal(
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
):
    vault.set_assets_per_share(125 * SCALE // 100, sender=owner)
    expected = amount * (125 - 100) // 125

    assert yield_vesting.claimable_yield_shares() == expected
    assert yield_vesting.claim_yield(sender=recipient) == expected
    assert vault.balanceOf(owner) == expected
    assert vault.balanceOf(yield_vesting) == amount - expected
    assert yield_vesting.claimed_principal_assets() == 0
    assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= amount


def test_loss_is_shared_proportionally(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(8 * SCALE // 10, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)
    expected = payout(amount, amount, amount - vested)

    assert yield_vesting.claim_principal(sender=recipient) == expected
    assert vault.balanceOf(recipient) == expected
    assert vault.balanceOf(owner) == 0

    chain.pending_timestamp = end_time
    yield_vesting.claim_principal(sender=recipient)
    assert vault.balanceOf(recipient) == amount
    assert vault.balanceOf(yield_vesting) == 0


def test_total_loss_does_not_brick_principal_claims(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(0, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)

    assert yield_vesting.claimable_yield_shares() == 0
    assert yield_vesting.claimable_shares() == vested
    assert yield_vesting.claim_principal(sender=recipient) == vested
    assert vault.balanceOf(recipient) == vested

    chain.pending_timestamp = end_time
    assert yield_vesting.claim_principal(sender=recipient) == amount - vested
    assert yield_vesting.claim_yield(sender=recipient) == 0
    assert vault.balanceOf(recipient) == amount
    assert vault.balanceOf(yield_vesting) == 0


def test_loss_then_recovery_only_exposes_surplus_as_yield(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(8 * SCALE // 10, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)

    assert yield_vesting.claim_principal(sender=recipient) == vested
    remaining_principal = amount - vested

    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    balance = vault.balanceOf(yield_vesting)
    principal_pool, expected_yield = split(
        balance,
        vault.convertToAssets(balance),
        remaining_principal,
    )

    assert yield_vesting.claimable_yield_shares() == expected_yield
    assert yield_vesting.claim_yield(sender=recipient) == expected_yield
    assert vault.balanceOf(owner) == expected_yield
    assert vault.balanceOf(yield_vesting) == principal_pool
    assert vault.convertToAssets(principal_pool) >= remaining_principal

    chain.pending_timestamp = end_time
    yield_vesting.claim_principal(sender=recipient)
    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(recipient) + vault.balanceOf(owner) == amount


def test_donated_shares_are_yield(
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
):
    donation = amount // 4
    vault.mint(recipient, donation, sender=owner)
    vault.transfer(yield_vesting, donation, sender=recipient)

    assert yield_vesting.claim_yield(sender=recipient) == donation
    assert vault.balanceOf(owner) == donation
    assert vault.balanceOf(yield_vesting) == amount


def test_revoke_combines_clawback_and_yield_for_owner(
    chain,
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    recipient_principal = amount * (midpoint - start_time) // (end_time - start_time)
    principal_pool, yield_shares = split(amount, vault.convertToAssets(amount), amount)
    clawback = payout(principal_pool, amount, recipient_principal)

    yield_vesting.revoke(sender=owner)

    event = events(yield_vesting, "Revoked")[0]
    assert event.recipient == recipient
    assert event.revocation_owner == owner
    assert event.beneficiary == owner
    assert event.clawed_back_principal_assets == amount - recipient_principal
    assert event.shares == clawback
    assert events(yield_vesting, "RevocationRenounced") == []
    assert vault.balanceOf(owner) == yield_shares + clawback
    assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= recipient_principal
    assert yield_vesting.revocation_owner() == ZERO_ADDRESS
    assert yield_vesting.yield_recipient() == owner

    yield_vesting.claim_principal(sender=recipient)
    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(recipient) + vault.balanceOf(owner) == amount


def test_revoke_shares_loss(
    chain,
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(8 * SCALE // 10, sender=owner)
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    recipient_principal = amount * (midpoint - start_time) // (end_time - start_time)
    expected_owner = payout(amount, amount, recipient_principal)

    yield_vesting.revoke(sender=owner)
    assert vault.balanceOf(owner) == expected_owner
    assert yield_vesting.yield_recipient() == owner

    yield_vesting.claim_principal(sender=recipient)
    assert vault.balanceOf(recipient) == amount - expected_owner
    assert vault.balanceOf(yield_vesting) == 0


def test_renouncing_revocation_does_not_change_yield_recipient(
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
):
    yield_vesting.renounce_revocation(sender=owner)
    event = events(yield_vesting, "RevocationRenounced")[0]
    vault.set_assets_per_share(125 * SCALE // 100, sender=owner)

    yield_vesting.claim_yield(sender=recipient)

    assert yield_vesting.revocation_owner() == ZERO_ADDRESS
    assert event.revocation_owner == owner
    assert yield_vesting.yield_recipient() == owner
    assert vault.balanceOf(owner) == amount * (125 - 100) // 125


def test_share_transfer_cannot_reenter_accounting(
    yield_vesting,
    owner,
    recipient,
    vault,
):
    vault.set_assets_per_share(125 * SCALE // 100, sender=owner)
    vault.set_reentry_target(yield_vesting, sender=owner)

    yield_vesting.claim_yield(sender=recipient)

    assert not vault.reentry_succeeded()


def test_collect_dust_cannot_remove_vault_shares(yield_vesting, recipient, vault):
    with boa.reverts(dev="vault shares protected"):
        yield_vesting.collect_dust(vault, sender=recipient)


def test_collect_dust_recovers_unrelated_token(
    yield_vesting,
    owner,
    recipient,
    another_token,
):
    amount = 123
    another_token.mint(yield_vesting, amount, sender=owner)

    yield_vesting.collect_dust(another_token, sender=recipient)

    assert another_token.balanceOf(recipient) == amount
    assert another_token.balanceOf(yield_vesting) == 0


def test_closed_claim_only_allows_recipient(
    chain,
    yield_vesting,
    owner,
    recipient,
    start_time,
    end_time,
):
    yield_vesting.set_open_claim(False, sender=recipient)
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    with boa.reverts(dev="not authorized"):
        yield_vesting.claim_principal(sender=owner)


def test_vesting_at_amount_limit(
    chain,
    vesting_factory,
    owner,
    recipient,
    asset_token,
):
    maximum = 2**128 - 1
    duration = 100
    start = chain.pending_timestamp + 10
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    vault.mint(owner, maximum, sender=owner)
    vault.approve(vesting_factory, maximum, sender=owner)
    escrow_address = vesting_factory.deploy_erc4626_vesting(
        vault,
        recipient,
        maximum,
        duration,
        start,
        0,
        True,
        owner,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrow4626", escrow_address)
    chain.pending_timestamp = start + duration // 2
    expected = maximum * (chain.pending_timestamp - start) // duration

    assert escrow.claim_principal(sender=recipient) == expected
    assert vault.balanceOf(recipient) == expected
    assert vault.balanceOf(escrow) == maximum - expected


def test_repeated_claims_keep_rounding_in_the_reserve(
    chain,
    yield_vesting,
    recipient,
    owner,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(13 * SCALE // 10, sender=owner)
    step = (end_time - start_time) // 4

    for index in range(1, 4):
        chain.pending_timestamp = start_time + step * index
        yield_vesting.claim_principal(sender=recipient)
        remaining = yield_vesting.principal_assets() - yield_vesting.claimed_principal_assets()
        assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= remaining

    chain.pending_timestamp = end_time
    yield_vesting.claim_principal(sender=recipient)

    yield_shares = vault.balanceOf(yield_vesting)
    assert yield_shares > 0
    assert yield_vesting.claimable_yield_shares() == yield_shares
    assert vault.balanceOf(owner) == 0

    yield_vesting.claim_yield(sender=recipient)
    assert vault.balanceOf(yield_vesting) == 0


def test_large_share_donation_keeps_yield_accounting_live(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    asset_token,
):
    maximum = 2**128 - 1
    donation = 2**129
    duration = 1_000
    start = chain.pending_timestamp + 10
    attacker = accounts[4]
    vault = deploy("test/MockERC4626", asset_token, sender=owner)

    vault.mint(owner, maximum, sender=owner)
    vault.approve(vesting_factory, maximum, sender=owner)
    escrow_address = vesting_factory.deploy_erc4626_vesting(
        vault,
        recipient,
        maximum,
        duration,
        start,
        0,
        True,
        owner,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrow4626", escrow_address)
    vault.mint(attacker, donation, sender=owner)
    vault.transfer(escrow, donation, sender=attacker)

    chain.pending_timestamp = start + duration // 2
    vested = maximum * (chain.pending_timestamp - start) // duration

    assert escrow.claimable_yield_shares() == donation
    assert escrow.claimable_shares() == vested
    assert escrow.locked_shares() == maximum - vested
    assert escrow.claim_yield(sender=attacker) == donation
    assert vault.balanceOf(owner) == donation
    assert escrow.claim_principal(sender=recipient) == vested
