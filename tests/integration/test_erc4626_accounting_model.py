import boa
from hypothesis import given, settings, strategies as st

from tests.helpers import at, deploy


SCALE = 10**18
UINT256_MAX = 2**256 - 1


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


def split_at_rate(balance, assets_per_share, remaining):
    """Mirror MockERC4626 conversions exactly, including integer rounding."""
    if remaining == 0:
        return 0, balance

    value = balance * assets_per_share // SCALE
    if value <= remaining:
        return balance, 0

    principal_shares = remaining * SCALE // assets_per_share
    if principal_shares * assets_per_share // SCALE < remaining:
        principal_shares += 1
    return principal_shares, balance - principal_shares


@st.composite
def payout_cases(draw):
    remaining_before = draw(st.integers(min_value=1, max_value=2**128 - 1))
    return (
        draw(st.integers(min_value=0, max_value=UINT256_MAX)),
        remaining_before,
        draw(st.integers(min_value=0, max_value=remaining_before)),
    )


@settings(deadline=None, max_examples=1_000)
@given(
    principal=st.integers(min_value=1, max_value=2**128 - 1),
    balance=st.integers(min_value=1, max_value=UINT256_MAX),
    claim_bps=st.integers(min_value=0, max_value=10_000),
    value=st.integers(min_value=0, max_value=UINT256_MAX),
)
def test_split_conserves_shares_and_rounds_toward_principal(
    principal,
    balance,
    claim_bps,
    value,
):
    claimable = principal * claim_bps // 10_000
    principal_pool, yield_shares = split(balance, value, principal)
    claim_shares = payout(principal_pool, principal, principal - claimable)
    remaining_shares = balance - yield_shares - claim_shares

    assert yield_shares + claim_shares + remaining_shares == balance
    assert min(yield_shares, claim_shares, remaining_shares) >= 0

    if value > principal:
        # For a proportional ERC-4626 conversion, floor rounding leaves at least
        # the unclaimed principal after yield and vested shares are removed.
        assert remaining_shares * value // balance >= principal - claimable


@settings(deadline=None, max_examples=1_000)
@given(case=payout_cases())
def test_payout_matches_exact_math_for_full_uint256_share_balance(case):
    principal_shares, remaining_before, remaining_after = case
    remainder = principal_shares % remaining_before

    assert remainder * remaining_after <= UINT256_MAX
    assert payout(principal_shares, remaining_before, remaining_after) == principal_shares - (
        principal_shares * remaining_after + remaining_before - 1
    ) // remaining_before


@settings(deadline=None, max_examples=1_000)
@given(
    assets=st.integers(min_value=1, max_value=2**128 - 1),
    assets_per_share=st.integers(min_value=1, max_value=2**128 - 1),
)
def test_one_share_round_up_is_the_minimum_principal_reserve(assets, assets_per_share):
    principal_shares = assets * SCALE // assets_per_share
    if principal_shares * assets_per_share // SCALE < assets:
        principal_shares += 1

    assert principal_shares * assets_per_share <= UINT256_MAX
    assert principal_shares * assets_per_share // SCALE >= assets
    assert principal_shares == 0 or (principal_shares - 1) * assets_per_share // SCALE < assets


def test_monthly_claim_rounding_is_bounded_for_expected_vault_precision():
    def settle(share_unit, claims):
        initial_shares = 1_000_000 * share_unit
        initial_principal = initial_shares
        balance = initial_shares
        remaining = initial_principal
        recipient = 0

        for index in range(1, claims + 1):
            remaining_after = initial_principal - initial_principal * index // claims
            value = balance * 3 // 2
            principal_shares, _ = split(balance, value, remaining)
            claimed = payout(principal_shares, remaining, remaining_after)
            balance -= claimed
            recipient += claimed
            remaining = remaining_after

        return initial_shares, recipient, balance

    for share_unit in (10**6, 10**18):
        total, one_shot_recipient, one_shot_yield = settle(share_unit, 1)
        _, monthly_recipient, monthly_yield = settle(share_unit, 12)

        assert monthly_recipient + monthly_yield == total
        assert one_shot_recipient + one_shot_yield == total
        assert 0 <= one_shot_recipient - monthly_recipient < 12


@settings(deadline=None, max_examples=500)
@given(
    principal=st.integers(min_value=1, max_value=10**36),
    actions=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=4 * SCALE),
            st.integers(min_value=0, max_value=10_000),
            st.integers(min_value=0, max_value=10**24),
        ),
        min_size=1,
        max_size=20,
    ),
)
def test_lifecycle_conserves_every_share_and_explicit_yield_claim_drains(principal, actions):
    balance = principal
    remaining = principal
    distributed = 0
    total_shares = principal

    for assets_per_share, claim_bps, donation in actions:
        balance += donation
        total_shares += donation
        claimable = remaining * claim_bps // 10_000
        value = balance * assets_per_share // SCALE
        remaining_before = remaining
        principal_pool, _ = split(balance, value, remaining_before)
        claim_shares = payout(principal_pool, remaining, remaining - claimable)
        balance -= claim_shares
        remaining -= claimable
        distributed += claim_shares

        assert balance + distributed == total_shares
        if value > remaining_before:
            assert balance * assets_per_share // SCALE >= remaining

    assets_per_share = actions[-1][0]
    value = balance * assets_per_share // SCALE
    principal_pool, _ = split(balance, value, remaining)
    claim_shares = principal_pool
    distributed += claim_shares
    balance -= claim_shares

    # Once principal reaches zero, every retained share is claimable yield.
    yield_shares = balance
    distributed += yield_shares
    balance -= yield_shares

    assert balance == 0
    assert distributed == total_shares


@settings(deadline=None, max_examples=50)
@given(
    principal=st.integers(min_value=10**6, max_value=10**24),
    actions=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=9_999),
            st.integers(min_value=0, max_value=4 * SCALE),
            st.integers(min_value=0, max_value=10**24),
            st.integers(min_value=0, max_value=10_000),
            st.booleans(),
        ),
        min_size=1,
        max_size=8,
    ),
    revoke_bps=st.integers(min_value=0, max_value=10_000),
)
def test_deployed_erc4626_lifecycle_matches_model(principal, actions, revoke_bps):
    """Differentially exercise the deployed escrow against the accounting model."""
    with boa.env.anchor():
        owner = boa.env.generate_address("differential-owner")
        recipient = boa.env.generate_address("differential-recipient")
        donor = boa.env.generate_address("differential-donor")
        asset = deploy("test/MockToken", sender=owner)
        vault = deploy("test/MockERC4626", asset, sender=owner)
        standard_target = deploy("VestingEscrowSimple", sender=owner)
        erc4626_target = deploy("VestingEscrow4626", sender=owner)
        factory = deploy(
            "VestingEscrowFactory",
            standard_target,
            erc4626_target,
            sender=owner,
        )

        duration = 10_000
        start = boa.env.evm.patch.timestamp + 1
        vault.mint(owner, principal, sender=owner)
        vault.approve(factory, principal, sender=owner)
        escrow_address = factory.deploy_erc4626_vesting(
            vault,
            recipient,
            principal,
            duration,
            start,
            0,
            True,
            owner,
            owner,
            sender=owner,
        )
        escrow = at("VestingEscrow4626", escrow_address)

        balance = principal
        total_shares = principal
        claimed_assets = 0
        recipient_shares = 0
        owner_shares = 0
        assets_per_share = SCALE

        for time_bps, new_rate, donation, claim_bps, take_yield in sorted(actions):
            if time_bps > revoke_bps:
                break

            timestamp = start + time_bps
            boa.env.time_travel(seconds=timestamp - boa.env.evm.patch.timestamp)
            assets_per_share = new_rate
            vault.set_assets_per_share(assets_per_share, sender=owner)

            if donation > 0:
                vault.mint(donor, donation, sender=owner)
                vault.transfer(escrow, donation, sender=donor)
                balance += donation
                total_shares += donation

            vested_assets = principal * time_bps // 10_000
            available_assets = vested_assets - claimed_assets
            claim_assets = available_assets * claim_bps // 10_000
            remaining_assets = principal - claimed_assets
            principal_pool, _ = split_at_rate(balance, assets_per_share, remaining_assets)
            expected_claim_shares = payout(
                principal_pool,
                remaining_assets,
                remaining_assets - claim_assets,
            )

            assert (
                escrow.claim_principal(recipient, claim_assets, sender=recipient)
                == expected_claim_shares
            )
            balance -= expected_claim_shares
            claimed_assets += claim_assets
            recipient_shares += expected_claim_shares

            if take_yield:
                remaining_assets = principal - claimed_assets
                _, expected_yield_shares = split_at_rate(
                    balance,
                    assets_per_share,
                    remaining_assets,
                )
                assert escrow.claim_yield(sender=donor) == expected_yield_shares
                balance -= expected_yield_shares
                owner_shares += expected_yield_shares

            remaining_assets = principal - claimed_assets
            claimable_assets = vested_assets - claimed_assets
            principal_pool, expected_yield_shares = split_at_rate(
                balance,
                assets_per_share,
                remaining_assets,
            )
            expected_claimable_shares = payout(
                principal_pool,
                remaining_assets,
                remaining_assets - claimable_assets,
            )

            assert escrow.claimed_principal_assets() == claimed_assets
            assert escrow.claimable_principal_assets() == claimable_assets
            assert escrow.claimable_shares() == expected_claimable_shares
            assert escrow.locked_shares() == principal_pool - expected_claimable_shares
            assert escrow.claimable_yield_shares() == expected_yield_shares
            assert vault.balanceOf(escrow) == balance
            assert vault.balanceOf(recipient) == recipient_shares
            assert vault.balanceOf(owner) == owner_shares

        final_vested_assets = principal
        if revoke_bps < 10_000:
            timestamp = start + revoke_bps
            boa.env.time_travel(seconds=timestamp - boa.env.evm.patch.timestamp)
            final_vested_assets = principal * revoke_bps // 10_000
            remaining_assets = principal - claimed_assets
            recipient_assets = final_vested_assets - claimed_assets
            principal_pool, yield_shares = split_at_rate(
                balance,
                assets_per_share,
                remaining_assets,
            )
            clawback_shares = payout(
                principal_pool,
                remaining_assets,
                recipient_assets,
            )

            escrow.revoke(sender=owner)
            balance -= clawback_shares + yield_shares
            owner_shares += clawback_shares + yield_shares

        else:
            timestamp = start + duration
            boa.env.time_travel(seconds=timestamp - boa.env.evm.patch.timestamp)

        remaining_assets = final_vested_assets - claimed_assets
        principal_pool, _ = split_at_rate(balance, assets_per_share, remaining_assets)
        assert escrow.claim_principal(sender=recipient) == principal_pool
        balance -= principal_pool
        recipient_shares += principal_pool
        claimed_assets = final_vested_assets

        _, final_yield_shares = split_at_rate(balance, assets_per_share, 0)
        assert escrow.claim_yield(sender=donor) == final_yield_shares
        balance -= final_yield_shares
        owner_shares += final_yield_shares

        assert escrow.claimed_principal_assets() == claimed_assets
        assert balance == vault.balanceOf(escrow) == 0
        assert vault.balanceOf(recipient) == recipient_shares
        assert vault.balanceOf(owner) == owner_shares
        assert recipient_shares + owner_shares == total_shares
