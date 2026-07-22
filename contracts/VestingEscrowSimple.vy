#pragma version 0.4.3
#pragma evm-version prague

"""
@title Simple Vesting Escrow
@author Curve Finance, Yearn Finance
@license MIT
@notice Vests ERC-20 tokens or the principal value of ERC-4626 shares
"""

from ethereum.ercs import IERC20


interface ERC4626:
    def asset() -> address: view
    def convertToAssets(shares: uint256) -> uint256: view
    def convertToShares(assets: uint256) -> uint256: view
    def balanceOf(account: address) -> uint256: view
    def transfer(receiver: address, shares: uint256) -> bool: nonpayable


event Claim:
    recipient: indexed(address)
    claimed: uint256


event YieldClaim:
    recipient: indexed(address)
    claimed: uint256


event Revoked:
    recipient: address
    owner: address
    rugged: uint256
    ts: uint256


event Disowned:
    owner: address


event SetOpenClaim:
    state: bool


MAX_AMOUNT: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1

recipient: public(address)
token: public(ERC4626)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
total_locked: public(uint256)
total_claimed: public(uint256)
total_principal: public(uint256)
principal_claimed: public(uint256)
disabled_at: public(uint256)
open_claim: public(bool)
initialized: public(bool)
owner: public(address)
yield_recipient: public(address)
share_basis: uint256
principal_basis: uint256
basis_minimum: uint256
rounding_credit: uint256


@deploy
def __init__():
    # Prevent initialization of the implementation itself.
    self.initialized = True


@external
@pure
def version() -> uint256:
    return 2


@internal
@view
def _yield_enabled() -> bool:
    return self.yield_recipient != empty(address)


@external
@view
def yield_to_owner() -> bool:
    return self._yield_enabled()


@external
def initialize(
    owner: address,
    token: ERC4626,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    open_claim: bool,
    yield_to_owner: bool = False,
) -> bool:
    """
    @notice Initialize a funded minimal proxy
    @dev Called once by `VestingEscrowFactory.deploy_vesting_contract`
    @param owner Revocation authority and, in yield mode, fixed yield recipient
    @param token ERC-20 token or ERC-4626 share token held by the escrow
    @param recipient Address receiving vested tokens or principal shares
    @param amount Number of tokens or shares funded into the escrow
    @param start_time Timestamp when vesting begins
    @param end_time Timestamp when vesting completes
    @param cliff_length Seconds after `start_time` before the first claim
    @param open_claim Whether anyone may trigger claims to `recipient`
    @param yield_to_owner Whether `token` uses ERC-4626 principal/yield accounting
    """
    assert not self.initialized  # dev: can only initialize once
    self.initialized = True

    assert amount > 0  # dev: amount must be > 0
    assert amount <= MAX_AMOUNT  # dev: amount too large
    assert not yield_to_owner or owner != empty(address)  # dev: invalid yield recipient
    assert recipient not in [empty(address), self, token.address, owner]  # dev: invalid recipient
    assert end_time > block.timestamp and end_time > start_time  # dev: invalid vesting period
    duration: uint256 = end_time - start_time
    assert duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= duration  # dev: invalid cliff
    assert staticcall token.balanceOf(self) >= amount  # dev: escrow not funded

    principal: uint256 = amount
    yield_recipient: address = empty(address)
    if yield_to_owner:
        asset: address = staticcall token.asset()
        assert asset.is_contract  # dev: invalid asset
        principal = staticcall token.convertToAssets(amount)
        assert principal > 0  # dev: zero principal
        assert principal <= MAX_AMOUNT  # dev: principal too large
        # Fail atomically if a partial vault lacks a conversion used by later claims.
        conversion_probe: uint256 = staticcall token.convertToShares(principal)
        yield_recipient = owner

    self.owner = owner
    self.token = token
    self.recipient = recipient
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length
    self.total_locked = amount
    self.total_principal = principal
    self.disabled_at = end_time
    self.open_claim = open_claim
    self.yield_recipient = yield_recipient
    if yield_to_owner:
        self.share_basis = amount
        self.principal_basis = principal
        self.basis_minimum = self._minimum_principal_shares(principal)

    return True


@internal
@view
def _total_vested_at(time: uint256) -> uint256:
    start: uint256 = self.start_time
    if time < start + self.cliff_length:
        return 0
    if time >= self.end_time:
        return self.total_principal
    return self.total_principal * (time - start) // (self.end_time - start)


@internal
@view
def _remaining_principal() -> uint256:
    return self._total_vested_at(self.disabled_at) - self.principal_claimed


@internal
@view
def _claimable_principal(time: uint256) -> uint256:
    return self._total_vested_at(time) - self.principal_claimed


@internal
@pure
def _mul_div_down(
    x: uint256,
    y: uint256,
    denominator: uint256,
) -> uint256:
    """Floor x * y / denominator without overflowing for bounded principal."""
    whole: uint256 = x // denominator
    remainder: uint256 = (x % denominator) * y
    return whole * y + remainder // denominator


@internal
@pure
def _mul_div_up(
    x: uint256,
    y: uint256,
    denominator: uint256,
) -> uint256:
    """Ceil x * y / denominator without overflowing for bounded principal."""
    if y == 0:
        return 0

    whole: uint256 = x // denominator
    remainder: uint256 = (x % denominator) * y
    result: uint256 = whole * y + remainder // denominator
    return result + convert(remainder % denominator > 0, uint256)


@internal
@view
def _basis_reserve(remaining: uint256) -> uint256:
    if remaining == 0 or self.share_basis == 0:
        return 0
    return self._mul_div_up(self.share_basis, remaining, self.principal_basis)


@internal
@view
def _basis_has_remainder(remaining: uint256) -> bool:
    basis: uint256 = self.principal_basis
    if basis == 0 or remaining == basis:
        return False
    claimed: uint256 = basis - remaining
    return (self.share_basis % basis) * claimed % basis > 0


@internal
@view
def _minimum_principal_shares(principal: uint256) -> uint256:
    if principal == 0:
        return 0

    principal_shares: uint256 = staticcall self.token.convertToShares(principal)
    if principal_shares == 0:
        if staticcall self.token.convertToAssets(1) >= principal:
            return 1
        return max_value(uint256)
    if principal_shares < max_value(uint256) and staticcall self.token.convertToAssets(
        principal_shares
    ) < principal:
        principal_shares += 1
    return principal_shares


@internal
@view
def _base_principal_shares(balance: uint256, remaining: uint256) -> uint256:
    return min(self._minimum_principal_shares(remaining), balance)


@internal
@view
def _allocation(remaining: uint256) -> (uint256, uint256, uint256, bool):
    """Split balance into nominal principal, recipient rounding, and yield."""
    balance: uint256 = staticcall self.token.balanceOf(self)
    credit: uint256 = min(self.rounding_credit, balance)
    available: uint256 = balance - credit
    reserve: uint256 = self._basis_reserve(remaining)
    base: uint256 = self._base_principal_shares(available, remaining)

    basis_stable: bool = self._minimum_principal_shares(
        self.principal_basis
    ) == self.basis_minimum if self.principal_basis > 0 else remaining == 0
    if reserve <= available and base <= reserve and basis_stable:
        return reserve, credit, available - reserve, False

    # A rate change can invalidate the old share basis. Settle any fractional
    # recipient entitlement as one whole share before starting a new basis.
    if self._basis_has_remainder(remaining) and available > 0:
        credit += 1
        if base == available:
            base -= 1

    return base, credit, balance - base - credit, True


@internal
def _sync_allocation(remaining: uint256) -> (uint256, uint256, uint256):
    principal_shares: uint256 = 0
    credit: uint256 = 0
    yield_shares: uint256 = 0
    reset_basis: bool = False
    principal_shares, credit, yield_shares, reset_basis = self._allocation(remaining)

    if reset_basis:
        self.share_basis = principal_shares
        self.principal_basis = remaining
        self.basis_minimum = self._minimum_principal_shares(remaining)
    self.rounding_credit = credit
    return principal_shares, credit, yield_shares


@internal
def _record_claimed(shares: uint256):
    """Keep the legacy counter informative without allowing it to lock claims."""
    room: uint256 = max_value(uint256) - self.total_claimed
    if shares >= room:
        self.total_claimed = max_value(uint256)
    else:
        self.total_claimed += shares



@internal
@view
def _unclaimed_shares(time: uint256) -> uint256:
    remaining: uint256 = self._remaining_principal()
    claimable: uint256 = self._claimable_principal(time)
    principal_shares: uint256 = 0
    credit: uint256 = 0
    ignored_yield: uint256 = 0
    reset_basis: bool = False
    principal_shares, credit, ignored_yield, reset_basis = self._allocation(remaining)

    if reset_basis:
        return credit + principal_shares - self._mul_div_up(
            principal_shares,
            remaining - claimable,
            remaining,
        ) if remaining > 0 else credit

    return credit + self._basis_reserve(remaining) - self._basis_reserve(remaining - claimable)


@external
@view
def asset() -> address:
    if self._yield_enabled():
        return staticcall self.token.asset()
    return self.token.address


@external
@view
def vested_principal() -> uint256:
    return self._total_vested_at(min(block.timestamp, self.disabled_at))


@external
@view
def claimable_principal() -> uint256:
    return self._claimable_principal(min(block.timestamp, self.disabled_at))


@external
@view
def unclaimed() -> uint256:
    time: uint256 = min(block.timestamp, self.disabled_at)
    if not self._yield_enabled():
        return self._total_vested_at(time) - self.total_claimed
    return self._unclaimed_shares(time)


@external
@view
def locked() -> uint256:
    time: uint256 = min(block.timestamp, self.disabled_at)
    if not self._yield_enabled():
        return self._total_vested_at(self.disabled_at) - self._total_vested_at(time)

    remaining: uint256 = self._remaining_principal()
    if remaining == 0:
        return 0

    principal_shares: uint256 = 0
    credit: uint256 = 0
    ignored_yield: uint256 = 0
    reset_basis: bool = False
    principal_shares, credit, ignored_yield, reset_basis = self._allocation(remaining)
    return principal_shares + credit - self._unclaimed_shares(time)


@external
@view
def claimable_yield() -> uint256:
    if not self._yield_enabled():
        return 0
    ignored_principal: uint256 = 0
    ignored_credit: uint256 = 0
    yield_shares: uint256 = 0
    reset_basis: bool = False
    ignored_principal, ignored_credit, yield_shares, reset_basis = self._allocation(
        self._remaining_principal()
    )
    return yield_shares


@external
@nonreentrant
def claim(
    beneficiary: address = msg.sender,
    amount: uint256 = max_value(uint256),
) -> uint256:
    """
    @notice Claim vested tokens or principal shares
    @param beneficiary Address receiving the claim
    @param amount Maximum tokens to claim in standard mode, or maximum shares
        accepted for the full currently vested principal claim in yield mode
    """
    assert self.initialized  # dev: not initialized
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized

    claim_period_end: uint256 = min(block.timestamp, self.disabled_at)
    if not self._yield_enabled():
        claimable: uint256 = min(self._total_vested_at(claim_period_end) - self.total_claimed, amount)
        self.total_claimed += claimable
        self.principal_claimed += claimable

        assert extcall self.token.transfer(beneficiary, claimable, default_return_value=True)
        log Claim(recipient=beneficiary, claimed=claimable)
        return claimable

    remaining: uint256 = self._remaining_principal()
    claimable: uint256 = self._claimable_principal(claim_period_end)

    principal_shares: uint256 = 0
    credit: uint256 = 0
    ignored_yield: uint256 = 0
    principal_shares, credit, ignored_yield = self._sync_allocation(remaining)
    claim_shares: uint256 = credit + self._basis_reserve(remaining) - self._basis_reserve(
        remaining - claimable
    )
    assert amount >= claim_shares  # dev: share cap too low

    self.rounding_credit = 0
    self.principal_claimed += claimable
    self._record_claimed(claim_shares)

    if claim_shares > 0:
        assert extcall self.token.transfer(beneficiary, claim_shares, default_return_value=True)

    log Claim(recipient=beneficiary, claimed=claim_shares)
    return claim_shares


@external
@nonreentrant
def claim_yield() -> uint256:
    """Send current yield to the fixed original owner."""
    yield_recipient: address = self.yield_recipient
    assert self.initialized and yield_recipient != empty(address)  # dev: yield disabled

    remaining: uint256 = self._remaining_principal()
    ignored_principal: uint256 = 0
    ignored_credit: uint256 = 0
    yield_shares: uint256 = 0
    ignored_principal, ignored_credit, yield_shares = self._sync_allocation(remaining)

    if yield_shares > 0:
        assert extcall self.token.transfer(yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=yield_recipient, claimed=yield_shares)
    return yield_shares


@external
@nonreentrant
def revoke(
    ts: uint256 = block.timestamp,
    beneficiary: address = msg.sender,
):
    """Stop vesting and return unvested wrapper tokens."""
    owner: address = self.owner
    assert msg.sender == owner  # dev: not owner
    assert ts >= block.timestamp and ts < self.end_time  # dev: no back to the future

    yield_recipient: address = self.yield_recipient
    if yield_recipient == empty(address):
        ruggable: uint256 = self._total_vested_at(self.disabled_at) - self._total_vested_at(ts)
        self.disabled_at = ts
        self.owner = empty(address)

        assert extcall self.token.transfer(beneficiary, ruggable, default_return_value=True)
        log Disowned(owner=owner)
        log Revoked(recipient=self.recipient, owner=owner, rugged=ruggable, ts=ts)
        return

    remaining: uint256 = self.total_principal - self.principal_claimed
    recipient_remaining: uint256 = self._total_vested_at(ts) - self.principal_claimed
    principal_shares: uint256 = 0
    credit: uint256 = 0
    yield_shares: uint256 = 0
    principal_shares, credit, yield_shares = self._sync_allocation(remaining)
    unvested: uint256 = remaining - recipient_remaining
    clawback_shares: uint256 = self._mul_div_down(
        self.share_basis,
        unvested,
        self.principal_basis,
    ) if unvested > 0 else 0
    retained_shares: uint256 = principal_shares - clawback_shares

    # Materialize a carried fraction before changing the vesting basis.
    if self._basis_has_remainder(remaining) and retained_shares > 0:
        credit += 1
        retained_shares -= 1

    self.disabled_at = ts
    self.owner = empty(address)
    self.rounding_credit = credit
    self.share_basis = retained_shares
    self.principal_basis = recipient_remaining
    self.basis_minimum = self._minimum_principal_shares(recipient_remaining)

    if clawback_shares > 0:
        assert extcall self.token.transfer(beneficiary, clawback_shares, default_return_value=True)
    if yield_shares > 0:
        assert extcall self.token.transfer(yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=yield_recipient, claimed=yield_shares)

    log Disowned(owner=owner)
    log Revoked(recipient=self.recipient, owner=owner, rugged=clawback_shares, ts=ts)


@external
def disown():
    owner: address = self.owner
    assert msg.sender == owner  # dev: not owner
    self.owner = empty(address)
    log Disowned(owner=owner)


@external
def set_open_claim(open_claim: bool):
    assert msg.sender == self.recipient  # dev: not recipient
    self.open_claim = open_claim
    log SetOpenClaim(state=open_claim)


@external
@nonreentrant
def collect_dust(
    token: IERC20,
    beneficiary: address = msg.sender,
):
    """Recover tokens that are not reserved for vesting."""
    assert self.initialized  # dev: not initialized
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized

    yield_enabled: bool = self._yield_enabled()
    protected_balance: uint256 = 0
    if yield_enabled:
        protected_balance = staticcall self.token.balanceOf(self)
    amount: uint256 = staticcall token.balanceOf(self)
    if token.address == self.token.address:
        assert not yield_enabled  # dev: use claim_yield
        required: uint256 = self._total_vested_at(self.disabled_at) - self.total_claimed
        assert amount >= required  # dev: insolvent
        amount -= required

    assert extcall token.transfer(beneficiary, amount, default_return_value=True)
    balance_after: uint256 = staticcall self.token.balanceOf(self)
    if yield_enabled:
        assert balance_after >= protected_balance
    else:
        required_balance: uint256 = self._total_vested_at(self.disabled_at) - self.total_claimed
        assert balance_after >= required_balance
