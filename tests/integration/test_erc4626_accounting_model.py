from hypothesis import given, settings, strategies as st


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
