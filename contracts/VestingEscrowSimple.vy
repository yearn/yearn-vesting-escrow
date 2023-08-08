# @version 0.3.9
"""
@title Simple Vesting Escrow
@author Curve Finance, Yearn Finance
@license MIT
@notice Vests ERC20 tokens for a single address
@dev Intended to be deployed many times via `VotingEscrowFactory`
"""

from vyper.interfaces import ERC20


event Claim:
    recipient: indexed(address)
    claimed: uint256

event RugPull:
    recipient: address
    rugged: uint256
    timestamp: uint256

event SetFree:
    admin: address

event SetOpenClaim:
    state: bool


recipient: public(address)
token: public(ERC20)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
total_locked: public(uint256)
total_claimed: public(uint256)
disabled_at: public(uint256)
open_claim: public(bool)

admin: public(address)

@external
def __init__(
    admin: address,
    token: address,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    open_claim: bool,
):
    """
    @notice Initialize the contract.
    @dev This function is seperate from `__init__` because of the factory pattern
         used in `VestingEscrowFactory.deploy_vesting_contract`. It may be called
         once per deployment.
    @param admin Admin address
    @param token Address of the ERC20 token being distributed
    @param recipient Address to vest tokens for
    @param amount Amount of tokens being vested for `recipient`
    @param start_time Epoch time at which token distribution starts
    @param end_time Time until everything should be vested
    @param cliff_length Duration after which the first portion vests
    """
    self.token = ERC20(token)
    self.admin = admin
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length

    self.recipient = recipient
    self.disabled_at = end_time  # Set to maximum time
    self.total_locked = amount
    self.open_claim = open_claim


@external
def seed(amount: uint256):
    # probably should guard this one
    # callable only during init
    assert self.token.transferFrom(msg.sender, self, amount, default_return_value=True)  # dev: could not fund escrow

    # log Fund(self.recipient, amount)


@internal
@view
def _total_vested_at(time: uint256 = block.timestamp) -> uint256:
    start: uint256 = self.start_time
    end: uint256 = self.end_time
    locked: uint256 = self.total_locked
    if time < start + self.cliff_length:
        return 0
    return min(locked * (time - start) / (end - start), locked)


@internal
@view
def _unclaimed(time: uint256 = block.timestamp) -> uint256:
    return self._total_vested_at(time) - self.total_claimed


@external
@view
def unclaimed() -> uint256:
    """
    @notice Get the number of unclaimed, vested tokens for recipient
    """
    # NOTE: if `rug_pull` is activated, limit by the activation timestamp
    return self._unclaimed(min(block.timestamp, self.disabled_at))


@internal
@view
def _locked(time: uint256 = block.timestamp) -> uint256:
    return min(self.token.balanceOf(self) - self._unclaimed(time), self.total_locked - self._total_vested_at(time))


@external
@view
def locked() -> uint256:
    """
    @notice Get the number of locked tokens for recipient
    """
    # NOTE: if `rug_pull` is activated, limit by the activation timestamp
    return self._locked(min(block.timestamp, self.disabled_at))


@external
def claim(beneficiary: address = msg.sender, amount: uint256 = max_value(uint256)):
    """
    @notice Claim tokens which have vested
    @param beneficiary Address to transfer claimed tokens to
    @param amount Amount of tokens to claim
    """
    recipient: address = self.recipient
    assert msg.sender == recipient or (self.open_claim and recipient == beneficiary)  # dev: not authorized

    claim_period_end: uint256 = min(block.timestamp, self.disabled_at)
    claimable: uint256 = min(self._unclaimed(claim_period_end), amount)
    self.total_claimed += claimable

    assert self.token.transfer(beneficiary, claimable, default_return_value=True)
    log Claim(beneficiary, claimable)


@external
def rug_pull(ts: uint256 = block.timestamp):
    """
    @notice Disable further flow of tokens and clawback the unvested part to admin.
        Rugging more than once is futile.
    @dev Admin is set to zero address.
    @param ts Timestamp of the clawback.
    """
    admin: address = self.admin
    assert msg.sender == admin  # dev: admin only
    assert ts >= block.timestamp and ts < self.end_time # dev: no back to the future

    self.disabled_at = ts
    ruggable: uint256 = self._locked(ts)

    assert self.token.transfer(admin, ruggable, default_return_value=True)

    self.admin = empty(address)

    log SetFree(admin)
    log RugPull(self.recipient, ruggable, ts)


@external
def set_free():
    """
    @notice Renounce admin control of the escrow
    """
    admin: address = self.admin
    assert msg.sender == admin  # dev: admin only
    self.admin = empty(address)

    log SetFree(admin)


@external
def set_open_claim(open_claim: bool):
    assert msg.sender == self.recipient  # dev: not recipient
    self.open_claim = open_claim

    log SetOpenClaim(open_claim)


@external
def collect_dust(token: address, beneficiary: address = msg.sender):
    recipient: address = self.recipient
    assert msg.sender == recipient or (self.open_claim and recipient == beneficiary) # dev: not authorized
    assert (token != self.token.address or block.timestamp > self.disabled_at) # dev: can't collect
    assert ERC20(token).transfer(beneficiary, ERC20(token).balanceOf(self), default_return_value=True)
