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


def create_yield_escrow(
    factory,
    vault,
    owner,
    recipient,
    shares,
    duration,
    start,
    cliff=0,
):
    vault.mint(owner, shares, sender=owner)
    vault.approve(factory, shares, sender=owner)
    address = factory.deploy_vesting_contract(
        vault,
        recipient,
        shares,
        duration,
        start,
        cliff,
        True,
        0,
        owner,
        True,
        sender=owner,
    )
    return at("VestingEscrowSimple", address)


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

    assert yield_vesting.claim(sender=recipient) == vested
    assert vault.balanceOf(recipient) == vested
    assert vault.balanceOf(owner) == 0
    assert yield_vesting.principal_claimed() == vested

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)

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

    claimed = yield_vesting.claim(cold_storage, 2**256 - 1, sender=recipient)

    assert claimed > 0
    assert vault.balanceOf(cold_storage) == claimed


def test_share_cap_is_all_or_nothing(
    chain,
    yield_vesting,
    recipient,
    vault,
    start_time,
    end_time,
):
    chain.pending_timestamp = start_time + (end_time - start_time) // 2
    claimable = yield_vesting.unclaimed()
    principal_claimed = yield_vesting.principal_claimed()
    total_claimed = yield_vesting.total_claimed()
    escrow_balance = vault.balanceOf(yield_vesting)

    with boa.reverts(dev="share cap too low"):
        yield_vesting.claim(recipient, claimable - 1, sender=recipient)

    assert yield_vesting.principal_claimed() == principal_claimed
    assert yield_vesting.total_claimed() == total_claimed
    assert vault.balanceOf(yield_vesting) == escrow_balance
    assert yield_vesting.claim(recipient, claimable, sender=recipient) == claimable


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

    assert yield_vesting.claim(sender=recipient) == expected_claim
    assert events(yield_vesting, "YieldClaim") == []
    assert vault.balanceOf(recipient) == expected_claim
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(yield_vesting) == balance - expected_claim
    assert yield_vesting.claimable_yield() > 0
    assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= amount - vested

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)
    yield_shares = vault.balanceOf(yield_vesting)

    assert yield_shares > 0
    assert yield_vesting.claimable_yield() == yield_shares
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(recipient) + yield_shares == amount

    assert yield_vesting.claim_yield(sender=recipient) == yield_shares
    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(recipient) + vault.balanceOf(owner) == amount


def test_claim_yield_without_claiming_principal(
    yield_vesting,
    owner,
    recipient,
    accounts,
    vault,
    amount,
):
    vault.set_assets_per_share(125 * SCALE // 100, sender=owner)
    expected = amount * (125 - 100) // 125

    assert yield_vesting.claimable_yield() == expected
    assert yield_vesting.claim_yield(sender=accounts[4]) == expected
    assert vault.balanceOf(owner) == expected
    assert vault.balanceOf(yield_vesting) == amount - expected
    assert yield_vesting.principal_claimed() == 0
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

    assert yield_vesting.claim(sender=recipient) == expected
    assert vault.balanceOf(recipient) == expected
    assert vault.balanceOf(owner) == 0

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)
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

    assert yield_vesting.claimable_yield() == 0
    assert yield_vesting.unclaimed() == vested
    assert yield_vesting.claim(sender=recipient) == vested
    assert vault.balanceOf(recipient) == vested

    chain.pending_timestamp = end_time
    assert yield_vesting.claim(sender=recipient) == amount - vested
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

    assert yield_vesting.claim(sender=recipient) == vested
    remaining_principal = amount - vested

    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    balance = vault.balanceOf(yield_vesting)
    principal_pool, expected_yield = split(
        balance,
        vault.convertToAssets(balance),
        remaining_principal,
    )

    assert yield_vesting.claimable_yield() == expected_yield
    assert yield_vesting.claim_yield(sender=recipient) == expected_yield
    assert vault.balanceOf(owner) == expected_yield
    assert vault.balanceOf(yield_vesting) == principal_pool
    assert vault.convertToAssets(principal_pool) >= remaining_principal

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)
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

    assert vault.balanceOf(owner) == yield_shares + clawback
    assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= recipient_principal
    assert yield_vesting.owner() == ZERO_ADDRESS
    assert yield_vesting.yield_to_owner()

    yield_vesting.claim(sender=recipient)
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
    assert yield_vesting.yield_to_owner()

    yield_vesting.claim(sender=recipient)
    assert vault.balanceOf(recipient) == amount - expected_owner
    assert vault.balanceOf(yield_vesting) == 0


def test_disown_does_not_change_yield_recipient(
    chain,
    yield_vesting,
    owner,
    recipient,
    vault,
    amount,
    end_time,
):
    yield_vesting.disown(sender=owner)
    vault.set_assets_per_share(125 * SCALE // 100, sender=owner)

    yield_vesting.claim_yield(sender=recipient)

    assert yield_vesting.owner() == ZERO_ADDRESS
    assert yield_vesting.yield_recipient() == owner
    assert yield_vesting.yield_to_owner()
    assert vault.balanceOf(owner) == amount * (125 - 100) // 125

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)
    assert vault.balanceOf(yield_vesting) == 0


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
    with boa.reverts(dev="use claim_yield"):
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
        yield_vesting.claim(sender=owner)

    assert yield_vesting.claim(sender=recipient) > 0


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
    escrow_address = vesting_factory.deploy_vesting_contract(
        vault,
        recipient,
        maximum,
        duration,
        start,
        0,
        True,
        0,
        owner,
        True,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    chain.pending_timestamp = start + duration // 2
    expected = maximum * (chain.pending_timestamp - start) // duration

    assert escrow.claim(sender=recipient) == expected
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
        yield_vesting.claim(sender=recipient)
        remaining = yield_vesting.total_principal() - yield_vesting.principal_claimed()
        assert vault.convertToAssets(vault.balanceOf(yield_vesting)) >= remaining

    chain.pending_timestamp = end_time
    yield_vesting.claim(sender=recipient)

    yield_shares = vault.balanceOf(yield_vesting)
    assert yield_shares > 0
    assert yield_vesting.claimable_yield() == yield_shares
    assert vault.balanceOf(owner) == 0

    yield_vesting.claim_yield(sender=recipient)
    assert vault.balanceOf(yield_vesting) == 0


def test_coarse_shares_carry_principal_rounding_between_claims(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 4
    duration = 8
    vault.set_assets_per_share(2 * SCALE, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    chain.pending_timestamp = start_time + 3
    assert escrow.claim(recipient, sender=owner) == 1
    assert escrow.principal_claimed() == 3
    assert escrow.claimable_yield() == 0

    chain.pending_timestamp = start_time + 6
    assert escrow.claim(recipient, sender=owner) == 2
    assert escrow.principal_claimed() == 6
    assert escrow.claimable_yield() == 0

    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == 1
    assert vault.balanceOf(recipient) == shares
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(escrow) == 0


def test_rate_gain_does_not_turn_claim_rounding_into_yield(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 10
    duration = 100
    vault.set_assets_per_share(10 * SCALE, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )
    vault.set_assets_per_share(15 * SCALE, sender=owner)

    assert escrow.total_principal() == 100
    assert escrow.claimable_yield() == 3

    chain.pending_timestamp = start_time + duration // 4
    assert escrow.claim(sender=recipient) == 1
    assert escrow.claimable_yield() == 3
    assert escrow.claim_yield(sender=owner) == 3

    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == 6
    assert vault.balanceOf(recipient) == 7
    assert vault.balanceOf(owner) == 3
    assert vault.balanceOf(escrow) == 0


def test_zero_share_claim_carries_entitlement_without_exposing_yield(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 2
    duration = 400
    vault.set_assets_per_share(100 * SCALE, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    chain.pending_timestamp = start_time + duration // 4
    assert escrow.claim(recipient, sender=owner) == 0
    assert escrow.principal_claimed() == 50
    assert escrow.claimable_principal() == 0
    assert escrow.claimable_yield() == 0
    assert escrow.claim_yield(sender=owner) == 0

    chain.pending_timestamp = start_time + duration // 2
    assert escrow.claim(recipient, sender=owner) == 1
    assert escrow.principal_claimed() == 100
    assert escrow.claimable_yield() == 0

    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == 1
    assert vault.balanceOf(recipient) == shares
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(escrow) == 0


def test_revoke_preserves_principal_from_zero_share_claim(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 2
    duration = 400
    vault.set_assets_per_share(100 * SCALE, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    chain.pending_timestamp = start_time + duration // 4
    assert escrow.claim(recipient, sender=owner) == 0
    assert escrow.principal_claimed() == 50

    escrow.revoke(sender=owner)
    assert vault.balanceOf(owner) == 1
    assert vault.balanceOf(escrow) == 1
    assert escrow.claim(sender=recipient) == 1
    assert vault.balanceOf(recipient) == 1
    assert vault.balanceOf(escrow) == 0


def test_revoke_after_prior_claim_always_settles(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 100
    duration = 400

    for rate in (0, 8 * SCALE // 10, SCALE, 12 * SCALE // 10, 2 * SCALE):
        with boa.env.anchor():
            escrow = create_yield_escrow(
                vesting_factory,
                vault,
                owner,
                recipient,
                shares,
                duration,
                start_time,
            )
            vault.set_assets_per_share(rate, sender=owner)

            chain.pending_timestamp = start_time + duration // 4
            escrow.claim(sender=recipient)
            chain.pending_timestamp = start_time + duration // 2
            escrow.revoke(sender=owner)
            escrow.claim(sender=recipient)

            assert vault.balanceOf(escrow) == 0
            assert vault.balanceOf(recipient) + vault.balanceOf(owner) == shares


def test_claim_history_does_not_change_revoke_allocation(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    cases = (
        (5, 14 * SCALE // 10, 7, 4),
        (7, 3 * SCALE // 10, 2, 1),
        (3, 15 * SCALE // 10, 4, 3),
    )

    for shares, rate, duration, elapsed in cases:
        allocations = []
        for claim_first in (False, True):
            with boa.env.anchor():
                vault.set_assets_per_share(rate, sender=owner)
                escrow = create_yield_escrow(
                    vesting_factory,
                    vault,
                    owner,
                    recipient,
                    shares,
                    duration,
                    start_time,
                )
                chain.pending_timestamp = start_time + elapsed

                if claim_first:
                    escrow.claim(recipient, sender=owner)
                    assert escrow.claim(recipient, sender=owner) == 0
                    assert escrow.claim_yield(sender=owner) == 0
                escrow.revoke(sender=owner)
                escrow.claim(sender=recipient)
                escrow.claim_yield(sender=owner)

                allocations.append((vault.balanceOf(recipient), vault.balanceOf(owner)))
                assert vault.balanceOf(escrow) == 0

        assert allocations[1] == allocations[0]


def test_rate_change_preserves_fractional_recipient_entitlement(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    allocations = []

    for claim_before_gain in (False, True):
        with boa.env.anchor():
            vault.set_assets_per_share(15 * SCALE // 10, sender=owner)
            escrow = create_yield_escrow(
                vesting_factory,
                vault,
                owner,
                recipient,
                3,
                4,
                start_time,
            )
            chain.pending_timestamp = start_time + 1

            if claim_before_gain:
                assert escrow.claim(sender=recipient) == 0
            vault.set_assets_per_share(3 * SCALE, sender=owner)

            assert escrow.unclaimed() == int(claim_before_gain)
            assert escrow.claimable_yield() == 1
            escrow.claim_yield(sender=owner)
            escrow.revoke(sender=owner)
            escrow.claim(sender=recipient)

            allocations.append((vault.balanceOf(recipient), vault.balanceOf(owner)))
            assert vault.balanceOf(escrow) == 0

    assert allocations == [(1, 2), (1, 2)]


def test_post_revoke_growth_and_donation_do_not_lock_principal(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 100
    duration = 400
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    chain.pending_timestamp = start_time + duration // 2
    escrow.revoke(sender=owner)
    vault.set_assets_per_share(2 * SCALE, sender=owner)
    vault.transfer(escrow, 10, sender=owner)

    assert escrow.claim_yield(sender=recipient) == 35
    assert vault.balanceOf(escrow) == 25
    assert escrow.claim(sender=recipient) == 25
    assert vault.balanceOf(recipient) == 25
    assert vault.balanceOf(owner) == 75
    assert vault.balanceOf(escrow) == 0


def test_future_revoke_keeps_interim_principal_and_views_live(
    chain,
    vesting_factory,
    owner,
    recipient,
    cold_storage,
    accounts,
    vault,
    start_time,
):
    shares = 100
    donation = 10
    duration = 100
    donor = accounts[4]
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    def assert_partition():
        assert escrow.unclaimed() + escrow.locked() + escrow.claimable_yield() == vault.balanceOf(escrow)

    chain.pending_timestamp = start_time + duration // 4
    disabled_at = start_time + 3 * duration // 4
    escrow.revoke(disabled_at, cold_storage, sender=owner)

    assert escrow.disabled_at() == disabled_at
    assert escrow.owner() == ZERO_ADDRESS
    assert vault.balanceOf(cold_storage) == shares // 4
    assert escrow.unclaimed() == shares // 4
    assert escrow.locked() == shares // 2
    assert_partition()

    assert escrow.claim(sender=recipient) == shares // 4
    assert_partition()

    vault.set_assets_per_share(2 * SCALE, sender=owner)
    vault.mint(donor, donation, sender=owner)
    vault.transfer(escrow, donation, sender=donor)

    assert escrow.unclaimed() == 0
    assert escrow.locked() == shares // 4
    assert escrow.claimable_yield() == 35
    assert_partition()
    assert escrow.claim_yield(sender=donor) == 35
    assert_partition()

    chain.pending_timestamp = start_time + duration // 2
    assert escrow.unclaimed() == 12
    assert escrow.locked() == 13
    assert escrow.claim(sender=recipient) == 12
    assert_partition()

    chain.pending_timestamp = disabled_at
    assert escrow.unclaimed() == 13
    assert escrow.locked() == 0
    assert escrow.claim(sender=recipient) == 13

    assert vault.balanceOf(recipient) == 50
    assert vault.balanceOf(owner) == 35
    assert vault.balanceOf(cold_storage) == 25
    assert vault.balanceOf(escrow) == 0
    assert_partition()


def test_temporary_share_transfer_failure_rolls_back_and_can_retry(
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
    chain.pending_timestamp = start_time + (end_time - start_time) // 2
    vault.set_transfers_enabled(False, sender=owner)
    principal_claimed = yield_vesting.principal_claimed()
    total_claimed = yield_vesting.total_claimed()
    balance = vault.balanceOf(yield_vesting)

    with boa.reverts(dev="transfers disabled"):
        yield_vesting.claim(sender=recipient)
    with boa.reverts(dev="transfers disabled"):
        yield_vesting.claim_yield(sender=recipient)
    with boa.reverts(dev="transfers disabled"):
        yield_vesting.revoke(sender=owner)

    assert yield_vesting.principal_claimed() == principal_claimed
    assert yield_vesting.total_claimed() == total_claimed
    assert yield_vesting.owner() == owner
    assert yield_vesting.disabled_at() == end_time
    assert vault.balanceOf(yield_vesting) == balance

    vault.set_transfers_enabled(True, sender=owner)
    yield_vesting.revoke(sender=owner)
    yield_vesting.claim(sender=recipient)

    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(recipient) + vault.balanceOf(owner) == amount


def test_second_revoke_transfer_failure_rolls_back_and_can_retry(
    chain,
    yield_vesting,
    owner,
    recipient,
    cold_storage,
    vault,
    amount,
    start_time,
    end_time,
):
    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    chain.pending_timestamp = start_time + (end_time - start_time) // 2
    principal_claimed = yield_vesting.principal_claimed()
    total_claimed = yield_vesting.total_claimed()
    disabled_at = yield_vesting.disabled_at()
    escrow_balance = vault.balanceOf(yield_vesting)
    owner_balance = vault.balanceOf(owner)
    recipient_balance = vault.balanceOf(recipient)
    cold_storage_balance = vault.balanceOf(cold_storage)
    views = (
        yield_vesting.unclaimed(),
        yield_vesting.locked(),
        yield_vesting.claimable_yield(),
    )

    vault.set_failing_receiver(owner, sender=owner)
    with boa.reverts(dev="receiver disabled"):
        yield_vesting.revoke(chain.pending_timestamp, cold_storage, sender=owner)

    assert yield_vesting.principal_claimed() == principal_claimed
    assert yield_vesting.total_claimed() == total_claimed
    assert yield_vesting.owner() == owner
    assert yield_vesting.disabled_at() == disabled_at
    assert vault.balanceOf(yield_vesting) == escrow_balance
    assert vault.balanceOf(owner) == owner_balance
    assert vault.balanceOf(recipient) == recipient_balance
    assert vault.balanceOf(cold_storage) == cold_storage_balance
    assert (
        yield_vesting.unclaimed(),
        yield_vesting.locked(),
        yield_vesting.claimable_yield(),
    ) == views

    vault.set_failing_receiver(ZERO_ADDRESS, sender=owner)
    yield_vesting.revoke(chain.pending_timestamp, cold_storage, sender=owner)
    yield_vesting.claim(sender=recipient)

    assert vault.balanceOf(cold_storage) > 0
    assert vault.balanceOf(owner) > 0
    assert vault.balanceOf(recipient) > 0
    assert vault.balanceOf(yield_vesting) == 0
    assert vault.balanceOf(cold_storage) + vault.balanceOf(owner) + vault.balanceOf(recipient) == amount


def test_yield_revoke_before_vesting_or_cliff_leaves_no_residue(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    amount,
    duration,
    start_time,
    cliff_duration,
):
    for revoke_time in (chain.pending_timestamp, start_time + cliff_duration - 1):
        with boa.env.anchor():
            escrow = create_yield_escrow(
                vesting_factory,
                vault,
                owner,
                recipient,
                amount,
                duration,
                start_time,
                cliff_duration,
            )
            vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
            chain.pending_timestamp = revoke_time
            escrow.revoke(sender=owner)

            assert escrow.claim(sender=recipient) == 0
            assert vault.balanceOf(owner) == amount
            assert vault.balanceOf(recipient) == 0
            assert vault.balanceOf(escrow) == 0


def test_cliff_equal_to_duration_settles_at_end(
    chain,
    vesting_factory,
    owner,
    recipient,
    vault,
    start_time,
):
    shares = 7
    duration = 100
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
        duration,
    )

    chain.pending_timestamp = start_time + duration - 1
    assert escrow.claim(sender=recipient) == 0
    assert escrow.principal_claimed() == 0

    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == shares
    assert vault.balanceOf(recipient) == shares
    assert vault.balanceOf(escrow) == 0


def test_recipient_and_yield_views_partition_every_share(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    vault,
    start_time,
):
    shares = 100
    duration = 400
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    def assert_partition():
        assert escrow.unclaimed() + escrow.locked() + escrow.claimable_yield() == vault.balanceOf(escrow)

    assert_partition()
    vault.set_assets_per_share(12 * SCALE // 10, sender=owner)
    vault.mint(accounts[4], 10, sender=owner)
    vault.transfer(escrow, 10, sender=accounts[4])
    chain.pending_timestamp = start_time + duration // 4
    assert_partition()
    escrow.claim(sender=recipient)
    assert_partition()
    escrow.claim_yield(sender=accounts[4])
    assert_partition()

    vault.set_assets_per_share(8 * SCALE // 10, sender=owner)
    chain.pending_timestamp = start_time + duration // 2
    assert_partition()
    escrow.revoke(sender=owner)
    assert_partition()

    vault.set_assets_per_share(15 * SCALE // 10, sender=owner)
    assert_partition()
    escrow.claim(sender=recipient)
    escrow.claim_yield(sender=accounts[4])
    assert_partition()
    assert vault.balanceOf(escrow) == 0


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
    escrow_address = vesting_factory.deploy_vesting_contract(
        vault,
        recipient,
        maximum,
        duration,
        start,
        0,
        True,
        0,
        owner,
        True,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    vault.mint(attacker, donation, sender=owner)
    vault.transfer(escrow, donation, sender=attacker)

    chain.pending_timestamp = start + duration // 2
    vested = maximum * (chain.pending_timestamp - start) // duration

    assert escrow.claimable_yield() == donation
    assert escrow.unclaimed() == vested
    assert escrow.locked() == maximum - vested
    assert escrow.claim_yield(sender=attacker) == donation
    assert vault.balanceOf(owner) == donation
    assert escrow.claim(sender=recipient) == vested


def test_large_share_donation_under_total_loss_still_settles(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    asset_token,
):
    principal_shares = 2**128 - 1
    donated_shares = 2**129
    duration = 100
    start = chain.pending_timestamp + 10
    donor = accounts[4]
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        principal_shares,
        duration,
        start,
    )
    vault.mint(donor, donated_shares, sender=owner)
    vault.transfer(escrow, donated_shares, sender=donor)
    vault.set_assets_per_share(0, sender=owner)

    chain.pending_timestamp = start + duration // 2
    first = escrow.claim(sender=recipient)
    assert first > 0
    assert escrow.claimable_yield() == 0

    chain.pending_timestamp = start + duration
    second = escrow.claim(sender=recipient)

    assert first + second == principal_shares + donated_shares
    assert vault.balanceOf(recipient) == principal_shares + donated_shares
    assert vault.balanceOf(escrow) == 0


def test_donation_after_loss_checkpoint_restores_principal_reserve(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    vault,
    start_time,
):
    shares = 100
    donation = 10
    duration = 100
    donor = accounts[4]
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )
    vault.set_assets_per_share(0, sender=owner)

    chain.pending_timestamp = start_time + duration // 2
    assert escrow.claim(sender=recipient) == shares // 2

    vault.mint(donor, donation, sender=owner)
    vault.transfer(escrow, donation, sender=donor)

    assert escrow.claimable_yield() == 0
    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == shares // 2 + donation
    assert vault.balanceOf(recipient) == shares + donation
    assert vault.balanceOf(escrow) == 0


def test_total_loss_donation_materializes_fractional_credit(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    vault,
    start_time,
):
    shares = 2
    donation = 1
    duration = 400
    donor = accounts[4]
    vault.set_assets_per_share(100 * SCALE, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start_time,
    )

    chain.pending_timestamp = start_time + duration // 4
    assert escrow.claim(sender=recipient) == 0
    assert escrow.principal_claimed() == 50

    vault.set_assets_per_share(0, sender=owner)
    vault.mint(donor, donation, sender=owner)
    vault.transfer(escrow, donation, sender=donor)

    assert escrow.claimable_principal() == 0
    assert escrow.unclaimed() == 1
    assert escrow.locked() == 2
    assert escrow.claimable_yield() == 0
    assert escrow.unclaimed() + escrow.locked() == vault.balanceOf(escrow)
    assert escrow.claim(sender=recipient) == 1
    assert escrow.principal_claimed() == 50

    chain.pending_timestamp = start_time + duration
    assert escrow.claim(sender=recipient) == 2
    assert vault.balanceOf(recipient) == shares + donation
    assert vault.balanceOf(owner) == 0
    assert vault.balanceOf(escrow) == 0


def test_recycled_full_width_balance_cannot_overflow_or_lock_claims(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    asset_token,
):
    shares = 3
    maximum = 2**256 - 1
    duration = 3
    start = chain.pending_timestamp + 10
    donor = accounts[4]
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start,
    )
    vault.mint(donor, maximum - shares, sender=owner)
    vault.transfer(escrow, maximum - shares, sender=donor)
    vault.set_assets_per_share(0, sender=owner)

    chain.pending_timestamp = start + 1
    first = escrow.claim(sender=recipient)
    vault.transfer(escrow, first, sender=recipient)

    # Rebase the share checkpoint without advancing the vesting clock.
    vault.set_assets_per_share(SCALE, sender=owner)
    assert escrow.claim(sender=recipient) == 0
    vault.set_assets_per_share(0, sender=owner)

    chain.pending_timestamp = start + 2
    second = escrow.claim(sender=recipient)
    vault.transfer(escrow, second, sender=recipient)

    vault.set_assets_per_share(SCALE, sender=owner)
    credit = escrow.claim(sender=recipient)
    vault.transfer(escrow, credit, sender=recipient)
    vault.set_assets_per_share(0, sender=owner)

    chain.pending_timestamp = start + duration
    final = escrow.claim(sender=recipient)

    assert first + second + credit + final > maximum
    assert escrow.total_claimed() == maximum
    assert escrow.principal_claimed() == shares
    assert vault.balanceOf(recipient) == maximum
    assert vault.balanceOf(escrow) == 0


def test_full_width_donation_does_not_overflow_conversion_views(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    asset_token,
):
    shares = 3
    maximum = 2**256 - 1
    duration = 3
    start = chain.pending_timestamp + 10
    donor = accounts[4]
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    escrow = create_yield_escrow(
        vesting_factory,
        vault,
        owner,
        recipient,
        shares,
        duration,
        start,
    )
    vault.mint(donor, maximum - shares, sender=owner)
    vault.transfer(escrow, maximum - shares, sender=donor)
    vault.set_assets_per_share(2 * SCALE, sender=owner)

    assert escrow.claimable_yield() == maximum - 2
    assert escrow.locked() == 2
    assert escrow.unclaimed() == 0
    assert escrow.claim_yield(sender=donor) == maximum - 2

    chain.pending_timestamp = start + duration
    assert escrow.claim(sender=recipient) == 2
    assert vault.balanceOf(escrow) == 0


def test_full_width_recovery_exposes_yield_after_loss_checkpoint(
    chain,
    vesting_factory,
    owner,
    recipient,
    accounts,
    asset_token,
):
    maximum = 2**256 - 1
    principal_shares = (maximum + 1) // 2
    yield_shares = maximum // 2
    duration = 100
    start = chain.pending_timestamp + 10
    donor = accounts[4]
    vault = deploy("test/FullWidthERC4626", asset_token, owner, donor, sender=owner)

    vault.approve(vesting_factory, 3, sender=owner)
    escrow_address = vesting_factory.deploy_vesting_contract(
        vault,
        recipient,
        3,
        duration,
        start,
        0,
        True,
        0,
        owner,
        True,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    assert escrow.total_principal() == 1

    vault.set_total_assets(1, sender=owner)
    vault.transfer(escrow, maximum - 3, sender=donor)

    # Persist a full-width principal basis while the vault is at near-total loss.
    assert escrow.claim(sender=recipient) == 0
    assert escrow.principal_claimed() == 0
    assert escrow.claimable_yield() == 0

    vault.set_total_assets(2, sender=owner)

    assert escrow.claimable_yield() == yield_shares
    assert escrow.locked() == principal_shares
    assert escrow.claim_yield(sender=donor) == yield_shares
    assert vault.balanceOf(owner) == yield_shares

    chain.pending_timestamp = start + duration
    assert escrow.claim(sender=recipient) == principal_shares
    assert vault.balanceOf(recipient) == principal_shares
    assert vault.balanceOf(escrow) == 0
