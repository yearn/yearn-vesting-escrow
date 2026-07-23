#pragma version 0.4.3
#pragma evm-version prague

"""
@title ERC-4626 Vesting Escrow
@author Yearn Finance
@license MIT
@notice Vests underlying-asset principal while holding and paying ERC-4626 shares
"""

from ethereum.ercs import IERC20
from modules import vesting_math


interface IERC4626:
    def asset() -> address: view
    def convertToAssets(shares: uint256) -> uint256: view
    def convertToShares(assets: uint256) -> uint256: view
    def balanceOf(account: address) -> uint256: view
    def transfer(receiver: address, shares: uint256) -> bool: nonpayable


event PrincipalClaim:
    beneficiary: indexed(address)
    principal_assets: uint256
    shares: uint256


event YieldClaim:
    recipient: indexed(address)
    shares: uint256


event Revoked:
    recipient: indexed(address)
    revocation_owner: indexed(address)
    beneficiary: indexed(address)
    clawed_back_principal_assets: uint256
    shares: uint256
    ts: uint256


event RevocationRenounced:
    revocation_owner: indexed(address)


event SetOpenClaim:
    state: bool


MAX_PRINCIPAL: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1
IMPLEMENTATION_KIND: constant(uint256) = 2

recipient: public(address)
vault: public(IERC4626)
asset_token: public(address)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
funded_shares: public(uint256)
principal_assets: public(uint256)
claimed_principal_assets: public(uint256)
disabled_at: public(uint256)
open_claim: public(bool)
initialized: public(bool)
revocation_owner: public(address)
yield_recipient: public(address)


@deploy
def __init__():
    # Prevent initialization of the implementation itself.
    self.initialized = True


@external
@pure
def implementation_kind() -> uint256:
    return IMPLEMENTATION_KIND


@external
def initialize(
    revocation_owner: address,
    vault: IERC4626,
    recipient: address,
    funded_shares: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    open_claim: bool,
    yield_recipient: address,
) -> bool:
    """Initialize one funded ERC-4626 minimal proxy."""
    assert not self.initialized  # dev: can only initialize once
    self.initialized = True

    assert funded_shares > 0  # dev: shares must be > 0
    assert recipient not in [empty(address), self, vault.address, revocation_owner]  # dev: invalid recipient
    assert end_time > block.timestamp and end_time > start_time  # dev: invalid vesting period
    duration: uint256 = end_time - start_time
    assert duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= duration  # dev: invalid cliff
    assert staticcall vault.balanceOf(self) >= funded_shares  # dev: escrow not funded

    asset_token: address = staticcall vault.asset()
    assert asset_token.is_contract  # dev: invalid asset
    assert yield_recipient not in [
        empty(address),
        self,
        vault.address,
        asset_token,
    ]  # dev: invalid yield recipient
    principal_assets: uint256 = staticcall vault.convertToAssets(funded_shares)
    assert principal_assets > 0  # dev: zero principal
    assert principal_assets <= MAX_PRINCIPAL  # dev: principal too large
    roundtrip_shares: uint256 = staticcall vault.convertToShares(principal_assets)
    assert roundtrip_shares > 0 and roundtrip_shares <= funded_shares  # dev: invalid conversion

    self.revocation_owner = revocation_owner
    self.vault = vault
    self.asset_token = asset_token
    self.recipient = recipient
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length
    self.funded_shares = funded_shares
    self.principal_assets = principal_assets
    self.disabled_at = end_time
    self.open_claim = open_claim
    self.yield_recipient = yield_recipient

    return True


@internal
@view
def _vested_principal_assets(time: uint256) -> uint256:
    return vesting_math.vested_at(
        self.principal_assets,
        self.start_time,
        self.end_time,
        self.cliff_length,
        time,
    )


@internal
@view
def _remaining_principal_assets() -> uint256:
    return self._vested_principal_assets(self.disabled_at) - self.claimed_principal_assets


@internal
@view
def _claimable_principal_assets(time: uint256) -> uint256:
    return self._vested_principal_assets(time) - self.claimed_principal_assets


@internal
@view
def _split_principal_and_yield(remaining_assets: uint256) -> (uint256, uint256):
    balance: uint256 = staticcall self.vault.balanceOf(self)
    if remaining_assets == 0:
        return 0, balance

    value: uint256 = staticcall self.vault.convertToAssets(balance)
    if value <= remaining_assets:
        return balance, 0

    principal_shares: uint256 = staticcall self.vault.convertToShares(remaining_assets)
    if staticcall self.vault.convertToAssets(principal_shares) < remaining_assets:
        principal_shares += 1
    return principal_shares, balance - principal_shares


@internal
@view
def _claimable_shares(time: uint256) -> uint256:
    remaining_assets: uint256 = self._remaining_principal_assets()
    claimable_assets: uint256 = self._claimable_principal_assets(time)
    if claimable_assets == 0:
        return 0

    principal_shares: uint256 = 0
    ignored_yield: uint256 = 0
    principal_shares, ignored_yield = self._split_principal_and_yield(remaining_assets)
    return vesting_math.payout_shares(
        principal_shares,
        remaining_assets,
        remaining_assets - claimable_assets,
    )


@external
@view
def vested_principal_assets() -> uint256:
    return self._vested_principal_assets(min(block.timestamp, self.disabled_at))


@external
@view
def claimable_principal_assets() -> uint256:
    return self._claimable_principal_assets(min(block.timestamp, self.disabled_at))


@external
@view
def claimable_shares() -> uint256:
    return self._claimable_shares(min(block.timestamp, self.disabled_at))


@external
@view
def locked_shares() -> uint256:
    time: uint256 = min(block.timestamp, self.disabled_at)
    remaining_assets: uint256 = self._remaining_principal_assets()
    if remaining_assets == 0:
        return 0

    principal_shares: uint256 = 0
    ignored_yield: uint256 = 0
    principal_shares, ignored_yield = self._split_principal_and_yield(remaining_assets)
    claimable_assets: uint256 = self._claimable_principal_assets(time)
    claimable_shares: uint256 = vesting_math.payout_shares(
        principal_shares,
        remaining_assets,
        remaining_assets - claimable_assets,
    )
    return principal_shares - claimable_shares


@external
@view
def claimable_yield_shares() -> uint256:
    ignored_principal: uint256 = 0
    yield_shares: uint256 = 0
    ignored_principal, yield_shares = self._split_principal_and_yield(self._remaining_principal_assets())
    return yield_shares


@external
@nonreentrant
def claim_principal(
    beneficiary: address = msg.sender,
    max_principal_assets: uint256 = max_value(uint256),
) -> uint256:
    """Claim up to a requested amount of currently vested principal."""
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized

    claim_period_end: uint256 = min(block.timestamp, self.disabled_at)
    remaining_assets: uint256 = self._remaining_principal_assets()
    claimable_assets: uint256 = min(
        self._claimable_principal_assets(claim_period_end),
        max_principal_assets,
    )

    principal_shares: uint256 = 0
    ignored_yield: uint256 = 0
    principal_shares, ignored_yield = self._split_principal_and_yield(remaining_assets)
    shares: uint256 = vesting_math.payout_shares(
        principal_shares,
        remaining_assets,
        remaining_assets - claimable_assets,
    )
    self.claimed_principal_assets += claimable_assets

    if shares > 0:
        assert extcall self.vault.transfer(beneficiary, shares, default_return_value=True)
    log PrincipalClaim(beneficiary=beneficiary, principal_assets=claimable_assets, shares=shares)
    return shares


@external
@nonreentrant
def claim_yield() -> uint256:
    """Send current yield shares to the fixed yield recipient."""
    yield_recipient: address = self.yield_recipient
    assert self.initialized  # dev: not initialized

    ignored_principal: uint256 = 0
    yield_shares: uint256 = 0
    ignored_principal, yield_shares = self._split_principal_and_yield(self._remaining_principal_assets())

    if yield_shares > 0:
        assert extcall self.vault.transfer(yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=yield_recipient, shares=yield_shares)
    return yield_shares


@external
@nonreentrant
def revoke(
    ts: uint256 = block.timestamp,
    beneficiary: address = msg.sender,
):
    """Stop vesting and return unvested principal shares and current yield."""
    revocation_owner: address = self.revocation_owner
    assert msg.sender == revocation_owner  # dev: not revocation owner
    assert ts >= block.timestamp and ts < self.end_time  # dev: no back to the future

    remaining_assets: uint256 = self.principal_assets - self.claimed_principal_assets
    recipient_assets: uint256 = self._vested_principal_assets(ts) - self.claimed_principal_assets
    principal_shares: uint256 = 0
    yield_shares: uint256 = 0
    principal_shares, yield_shares = self._split_principal_and_yield(remaining_assets)
    clawback_shares: uint256 = vesting_math.payout_shares(
        principal_shares,
        remaining_assets,
        recipient_assets,
    )
    clawback_assets: uint256 = remaining_assets - recipient_assets

    self.disabled_at = ts
    self.revocation_owner = empty(address)

    if clawback_shares > 0:
        assert extcall self.vault.transfer(beneficiary, clawback_shares, default_return_value=True)
    if yield_shares > 0:
        assert extcall self.vault.transfer(self.yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=self.yield_recipient, shares=yield_shares)

    log Revoked(
        recipient=self.recipient,
        revocation_owner=revocation_owner,
        beneficiary=beneficiary,
        clawed_back_principal_assets=clawback_assets,
        shares=clawback_shares,
        ts=ts,
    )


@external
def renounce_revocation():
    revocation_owner: address = self.revocation_owner
    assert msg.sender == revocation_owner  # dev: not revocation owner
    self.revocation_owner = empty(address)
    log RevocationRenounced(revocation_owner=revocation_owner)


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
    """Recover unrelated tokens without touching any vault shares."""
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized
    assert token.address != self.vault.address  # dev: vault shares protected

    protected_shares: uint256 = staticcall self.vault.balanceOf(self)
    amount: uint256 = staticcall token.balanceOf(self)
    if amount > 0:
        assert extcall token.transfer(beneficiary, amount, default_return_value=True)
    assert staticcall self.vault.balanceOf(self) >= protected_shares
