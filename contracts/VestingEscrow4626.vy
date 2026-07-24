#pragma version 0.4.3
#pragma evm-version prague

"""
@title ERC-4626 Vesting Escrow
@author Yearn Finance
@license MIT
@notice Vests underlying-asset principal while holding and paying ERC-4626 shares
"""

from modules import vesting_math


interface IERC4626:
    def asset() -> address: view
    def convertToAssets(shares: uint256) -> uint256: view
    def convertToShares(assets: uint256) -> uint256: view
    def balanceOf(account: address) -> uint256: view
    def transfer(receiver: address, shares: uint256) -> bool: nonpayable


event PrincipalClaim:
    receiver: indexed(address)
    principal_assets: uint256
    shares: uint256


event YieldClaim:
    recipient: indexed(address)
    shares: uint256


event Revoked:
    recipient: indexed(address)
    revoker: indexed(address)
    receiver: indexed(address)
    unvested_principal_assets: uint256
    shares: uint256
    ts: uint256


event RevocationRenounced:
    revoker: indexed(address)


event PermissionlessClaimsSet:
    enabled: bool


MAX_PRINCIPAL: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1

recipient: public(address)
vault: public(IERC4626)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
principal_assets: public(uint256)
claimed_principal_assets: public(uint256)
# Zero until revocation; active escrows use end_time as their effective stop.
disabled_at: public(uint256)
claims_closed: bool
revoker: public(address)
yield_recipient: public(address)


@deploy
def __init__():
    # Prevent initialization of the implementation itself.
    self.recipient = self


@external
def initialize(
    revoker: address,
    vault: IERC4626,
    recipient: address,
    funded_shares: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    yield_recipient: address,
) -> bool:
    """Initialize one funded ERC-4626 minimal proxy."""
    assert self.recipient == empty(address)  # dev: can only initialize once

    assert funded_shares > 0  # dev: shares must be > 0
    assert recipient not in [empty(address), self, vault.address, revoker]  # dev: invalid recipient
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

    self.revoker = revoker
    self.vault = vault
    self.recipient = recipient
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length
    self.principal_assets = principal_assets
    self.claims_closed = not permissionless_claims
    self.yield_recipient = yield_recipient

    return True


@internal
@view
def _vesting_end() -> uint256:
    disabled_at: uint256 = self.disabled_at
    if disabled_at == 0:
        return self.end_time
    return disabled_at


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
    return self._vested_principal_assets(self._vesting_end()) - self.claimed_principal_assets


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
def _preview_principal_claim(time: uint256, max_principal_assets: uint256) -> (uint256, uint256):
    remaining_assets: uint256 = self._remaining_principal_assets()
    claimable_assets: uint256 = min(self._claimable_principal_assets(time), max_principal_assets)
    if claimable_assets == 0:
        return 0, 0

    principal_shares: uint256 = 0
    ignored_yield: uint256 = 0
    principal_shares, ignored_yield = self._split_principal_and_yield(remaining_assets)
    return (
        claimable_assets,
        vesting_math.payout_shares(
            principal_shares,
            remaining_assets,
            remaining_assets - claimable_assets,
        ),
    )


@external
@view
def claimable_principal_assets() -> uint256:
    return self._claimable_principal_assets(min(block.timestamp, self._vesting_end()))


@external
@view
def preview_principal_claim(max_principal_assets: uint256) -> (uint256, uint256):
    return self._preview_principal_claim(
        min(block.timestamp, self._vesting_end()),
        max_principal_assets,
    )


@external
@view
def claimable_yield_shares() -> uint256:
    ignored_principal: uint256 = 0
    yield_shares: uint256 = 0
    ignored_principal, yield_shares = self._split_principal_and_yield(self._remaining_principal_assets())
    return yield_shares


@external
@view
def permissionless_claims() -> bool:
    return not self.claims_closed


@external
@nonreentrant
def claim_principal(
    receiver: address,
    max_principal_assets: uint256,
) -> uint256:
    """Claim up to a requested amount of currently vested principal."""
    recipient: address = self.recipient
    assert receiver != empty(address)  # dev: invalid receiver
    assert msg.sender == recipient or not self.claims_closed and receiver == recipient  # dev: not authorized

    claimable_assets: uint256 = 0
    shares: uint256 = 0
    claimable_assets, shares = self._preview_principal_claim(
        min(block.timestamp, self._vesting_end()),
        max_principal_assets,
    )
    self.claimed_principal_assets += claimable_assets

    if shares > 0:
        assert extcall self.vault.transfer(receiver, shares, default_return_value=True)
        log PrincipalClaim(receiver=receiver, principal_assets=claimable_assets, shares=shares)
    return shares


@external
@nonreentrant
def claim_yield() -> uint256:
    """Send current yield shares to the fixed yield recipient."""
    yield_recipient: address = self.yield_recipient
    assert self.recipient != empty(address)  # dev: not initialized

    ignored_principal: uint256 = 0
    yield_shares: uint256 = 0
    ignored_principal, yield_shares = self._split_principal_and_yield(self._remaining_principal_assets())

    if yield_shares > 0:
        assert extcall self.vault.transfer(yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=yield_recipient, shares=yield_shares)
    return yield_shares


@external
@nonreentrant
def revoke(receiver: address):
    """Stop vesting and return unvested principal shares and current yield."""
    revoker: address = self.revoker
    assert msg.sender == revoker  # dev: not revoker
    assert receiver != empty(address)  # dev: invalid receiver
    assert block.timestamp < self.end_time  # dev: vesting complete

    remaining_assets: uint256 = self.principal_assets - self.claimed_principal_assets
    recipient_assets: uint256 = self._vested_principal_assets(block.timestamp) - self.claimed_principal_assets
    principal_shares: uint256 = 0
    yield_shares: uint256 = 0
    principal_shares, yield_shares = self._split_principal_and_yield(remaining_assets)
    unvested_shares: uint256 = vesting_math.payout_shares(
        principal_shares,
        remaining_assets,
        recipient_assets,
    )
    unvested_assets: uint256 = remaining_assets - recipient_assets

    self.disabled_at = block.timestamp
    self.revoker = empty(address)

    if unvested_shares > 0:
        assert extcall self.vault.transfer(receiver, unvested_shares, default_return_value=True)
    if yield_shares > 0:
        assert extcall self.vault.transfer(self.yield_recipient, yield_shares, default_return_value=True)
        log YieldClaim(recipient=self.yield_recipient, shares=yield_shares)

    log Revoked(
        recipient=self.recipient,
        revoker=revoker,
        receiver=receiver,
        unvested_principal_assets=unvested_assets,
        shares=unvested_shares,
        ts=block.timestamp,
    )


@external
def renounce_revocation():
    revoker: address = self.revoker
    assert msg.sender == revoker  # dev: not revoker
    self.revoker = empty(address)
    log RevocationRenounced(revoker=revoker)


@external
def set_permissionless_claims(enabled: bool):
    assert msg.sender == self.recipient  # dev: not recipient
    self.claims_closed = not enabled
    log PermissionlessClaimsSet(enabled=enabled)
