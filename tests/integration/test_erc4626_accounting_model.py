from dataclasses import dataclass

from hypothesis import given, settings, strategies as st


SCALE = 10**18
MAX_AMOUNT = 2**128 - 1
UINT256_MAX = 2**256 - 1


def mul_div_down(x, y, denominator):
    return (x // denominator) * y + (x % denominator) * y // denominator


def mul_div_up(x, y, denominator):
    if y == 0:
        return 0
    remainder = (x % denominator) * y
    return (x // denominator) * y + remainder // denominator + bool(remainder % denominator)


def principal_reserve(shares, remaining, basis):
    return mul_div_up(shares, remaining, basis) if shares and remaining else 0


@st.composite
def bounded_products(draw):
    denominator = draw(st.integers(min_value=1, max_value=MAX_AMOUNT))
    return (
        draw(st.integers(min_value=0, max_value=UINT256_MAX)),
        draw(st.integers(min_value=0, max_value=denominator)),
        denominator,
    )


@settings(deadline=None, max_examples=1_000)
@given(case=bounded_products())
def test_bounded_mul_div_matches_exact_full_width_math(case):
    x, y, denominator = case
    down = mul_div_down(x, y, denominator)
    up = mul_div_up(x, y, denominator)
    expected_up = (x * y + denominator - 1) // denominator if y else 0

    assert down == x * y // denominator
    assert up == expected_up
    assert 0 <= down <= up <= x


@settings(deadline=None, max_examples=1_000)
@given(
    shares=st.integers(min_value=1, max_value=UINT256_MAX),
    principal=st.integers(min_value=1, max_value=MAX_AMOUNT),
    checkpoints=st.lists(
        st.integers(min_value=0, max_value=10_000),
        min_size=1,
        max_size=20,
    ),
)
def test_checkpointed_claims_equal_one_shot_allocation(shares, principal, checkpoints):
    remaining = principal
    distributed = 0

    for vested_bps in sorted(checkpoints):
        target_remaining = principal - principal * vested_bps // 10_000
        target_remaining = min(target_remaining, remaining)
        before = principal_reserve(shares, remaining, principal)
        after = principal_reserve(shares, target_remaining, principal)
        distributed += before - after
        remaining = target_remaining

    vested = principal - remaining
    owner = mul_div_down(shares, remaining, principal)
    recipient_at_revoke = principal_reserve(shares, vested, principal)

    assert distributed == shares * vested // principal
    assert owner + recipient_at_revoke == shares
    assert distributed <= recipient_at_revoke
    assert recipient_at_revoke - distributed <= 1


@settings(deadline=None, max_examples=1_000)
@given(
    assets=st.integers(min_value=1, max_value=MAX_AMOUNT),
    assets_per_share=st.integers(min_value=1, max_value=MAX_AMOUNT),
)
def test_one_share_round_up_is_the_minimum_principal_reserve(assets, assets_per_share):
    shares = assets * SCALE // assets_per_share
    if shares * assets_per_share // SCALE < assets:
        shares += 1

    assert shares * assets_per_share <= UINT256_MAX
    assert shares * assets_per_share // SCALE >= assets
    assert shares == 0 or (shares - 1) * assets_per_share // SCALE < assets


@dataclass
class Accounting:
    principal: int
    balance: int
    rate: int = SCALE
    distributed: int = 0
    basis_shares: int = 0
    basis_principal: int = 0
    basis_minimum: int = 0
    credit: int = 0

    def __post_init__(self):
        self.basis_shares = self.balance
        self.basis_principal = self.principal
        self.basis_minimum = self.minimum_shares(self.principal)

    def to_assets(self, shares):
        return shares * self.rate // SCALE

    def to_shares(self, assets):
        return assets * SCALE // self.rate if self.rate else 0

    def reserve(self, remaining=None):
        remaining = self.principal if remaining is None else remaining
        return principal_reserve(self.basis_shares, remaining, self.basis_principal)

    def has_remainder(self):
        if not self.basis_principal or self.principal == self.basis_principal:
            return False
        claimed = self.basis_principal - self.principal
        return (self.basis_shares % self.basis_principal) * claimed % self.basis_principal > 0

    def minimum_shares(self, principal):
        if not principal:
            return 0
        shares = self.to_shares(principal)
        if not shares:
            if self.to_assets(1) >= principal:
                return 1
            return UINT256_MAX
        if shares < UINT256_MAX and self.to_assets(shares) < principal:
            shares += 1
        return shares

    def base_shares(self, available):
        return min(self.minimum_shares(self.principal), available)

    def allocation(self):
        credit = min(self.credit, self.balance)
        available = self.balance - credit
        reserve = self.reserve()
        base = self.base_shares(available)
        basis_stable = (
            self.minimum_shares(self.basis_principal) == self.basis_minimum
            if self.basis_principal
            else not self.principal
        )

        if reserve <= available and base <= reserve and basis_stable:
            return reserve, credit, available - reserve, False
        if self.has_remainder() and available:
            credit += 1
            if base == available:
                base -= 1
        return base, credit, self.balance - base - credit, True

    def sync(self):
        principal_shares, credit, yield_shares, reset = self.allocation()
        if reset:
            self.basis_shares = principal_shares
            self.basis_principal = self.principal
            self.basis_minimum = self.minimum_shares(self.principal)
        self.credit = credit
        return principal_shares, credit, yield_shares

    def claim(self, principal):
        _, credit, _ = self.sync()
        remaining_after = self.principal - principal
        shares = credit + self.reserve() - self.reserve(remaining_after)
        self.credit = 0
        self.principal = remaining_after
        self.balance -= shares
        self.distributed += shares
        return shares

    def claim_yield(self):
        _, _, shares = self.sync()
        self.balance -= shares
        self.distributed += shares
        return shares

    def donate(self, shares):
        self.balance += shares


@settings(deadline=None, max_examples=500)
@given(
    principal=st.integers(min_value=1, max_value=10**30),
    actions=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=4 * SCALE),
            st.integers(min_value=0, max_value=10_000),
            st.integers(min_value=0, max_value=10**24),
            st.booleans(),
        ),
        min_size=1,
        max_size=20,
    ),
)
def test_rate_changes_losses_and_donations_always_settle(principal, actions):
    accounting = Accounting(principal, principal)
    total_shares = principal

    for rate, claim_bps, donation, collect_yield in actions:
        accounting.rate = rate
        accounting.donate(donation)
        total_shares += donation
        claimable = accounting.principal * claim_bps // 10_000
        accounting.claim(claimable)
        if collect_yield:
            accounting.claim_yield()

        principal_shares, credit, yield_shares, _ = accounting.allocation()
        assert principal_shares + credit + yield_shares == accounting.balance
        assert accounting.balance + accounting.distributed == total_shares

    accounting.claim(accounting.principal)
    accounting.claim_yield()

    assert accounting.balance == 0
    assert accounting.distributed == total_shares
