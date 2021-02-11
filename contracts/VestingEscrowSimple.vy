# @version 0.2.8
"""
@title Simple Vesting Escrow
@author Curve Finance, Yearn Finance
@license MIT
@notice Vests ERC20 tokens for a single address
@dev Intended to be deployed many times via `VotingEscrowFactory`
"""

from vyper.interfaces import ERC20

event Fund:
    recipient: indexed(address)
    amount: uint256

event Claim:
    recipient: indexed(address)
    claimed: uint256

event Rug:
    recipient: address
    rugged: uint256

event AdminSet:
    admin: address


recipient: public(address)
token: public(address)
start_time: public(uint256)
end_time: public(uint256)
initial_locked: public(uint256)
total_claimed: public(uint256)
disabled_at: public(uint256)

admin: public(address)
future_admin: public(address)

@external
def __init__():
    # ensure that the original contract cannot be initialized
    self.admin = msg.sender


@external
@nonreentrant('lock')
def initialize(
    _admin: address,
    _token: address,
    _recipient: address,
    _amount: uint256,
    _start_time: uint256,
    _end_time: uint256
) -> bool:
    """
    @notice Initialize the contract.
    @dev This function is seperate from `__init__` because of the factory pattern
         used in `VestingEscrowFactory.deploy_vesting_contract`. It may be called
         once per deployment.
    @param _admin Admin address
    @param _token Address of the ERC20 token being distributed
    @param _recipient Address to vest tokens for
    @param _amount Amount of tokens being vested for `_recipient`
    @param _start_time Epoch time at which token distribution starts
    @param _end_time Time until everything should be vested
    """
    assert self.admin == ZERO_ADDRESS  # dev: can only initialize once

    self.token = _token
    self.admin = _admin
    self.start_time = _start_time
    self.end_time = _end_time

    assert ERC20(_token).transferFrom(msg.sender, self, _amount)

    self.recipient = _recipient
    self.initial_locked = _amount
    log Fund(_recipient, _amount)

    return True


@internal
@view
def _total_vested_at(_time: uint256 = block.timestamp) -> uint256:
    start: uint256 = self.start_time
    end: uint256 = self.end_time
    locked: uint256 = self.initial_locked
    if _time < start:
        return 0
    return min(locked * (_time - start) / (end - start), locked)


@external
@view
def vestedOf() -> uint256:
    """
    @notice Get the number of tokens which have vested for a given address
    """
    return self._total_vested_at()


@external
@view
def balanceOf() -> uint256:
    """
    @notice Get the number of unclaimed, vested tokens for a given address
    """
    return self._total_vested_at() - self.total_claimed


@external
@view
def lockedOf() -> uint256:
    """
    @notice Get the number of locked tokens for a given address
    """
    return self.initial_locked - self._total_vested_at()


@external
def claim(amount: uint256 = MAX_UINT256):
    """
    @notice Claim tokens which have vested
    @param amount Amount of tokens to claim
    """
    assert msg.sender == self.recipient  # dev: not recipient

    t: uint256 = self.disabled_at
    if t == 0:
        t = block.timestamp
    claimable: uint256 = min(self._total_vested_at(t) - self.total_claimed, amount)
    self.total_claimed += claimable
    assert ERC20(self.token).transfer(msg.sender, claimable)

    log Claim(msg.sender, claimable)


@external
def rug_pull():
    """
    @notice Disable further flow of tokens and clawback the unvested part to admin
    """
    assert msg.sender == self.admin  # dev: admin only
    assert self.disabled_at == 0  # dev: already rugged, have mercy

    self.disabled_at = block.timestamp
    ruggable: uint256 = self.initial_locked - self._total_vested_at()

    assert ERC20(self.token).transfer(self.admin, ruggable)
    log Rug(self.recipient, ruggable)


@external
def set_admin(addr: address):
    """
    @notice Transfer admin controls to another address
    @param addr Address to have ownership transferred to
    """
    assert msg.sender == self.admin  # dev: admin only
    self.admin = addr
    log AdminSet(addr)
