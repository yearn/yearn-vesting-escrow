# @version 0.2.8
"""
@title Vesting Escrow Factory
@author Curve Finance, Yearn Finance
@license MIT
@notice Stores and distributes ERC20 tokens by deploying `VestingEscrowSimple` contracts
"""

from vyper.interfaces import ERC20

MIN_VESTING_DURATION: constant(uint256) = 86400 * 365


interface VestingEscrowSimple:
    def initialize(
        admin: address,
        token: address,
        recipient: address,
        amount: uint256,
        start_time: uint256,
        end_time: uint256,
        cliff_length: uint256,
    ) -> bool: nonpayable


event CommitOwnership:
    admin: address

event ApplyOwnership:
    admin: address


admin: public(address)
future_admin: public(address)
target: public(address)

@external
def __init__(target: address, admin: address):
    """
    @notice Contract constructor
    @dev Prior to deployment you must deploy one copy of `VestingEscrowSimple` which
         is used as a library for vesting contracts deployed by this factory
    @param target `VestingEscrowSimple` contract address
    @param admin Account which funds and deploys new vesting contracts
    """
    self.target = target
    self.admin = admin


@external
def deploy_vesting_contract(
    token: address,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256 = block.timestamp,
    cliff_length: uint256 = 0,
) -> address:
    """
    @notice Deploy a new vesting contract
    @dev Each contract holds tokens which vest for a single account. Tokens
         must be sent to this contract via the regular `ERC20.transfer` method
         prior to calling this method.
    @param token Address of the ERC20 token being distributed
    @param recipient Address to vest tokens for
    @param amount Amount of tokens being vested for `recipient`
    @param vesting_duration Time period over which tokens are released
    @param vesting_start Epoch time when tokens begin to vest
    """
    assert msg.sender == self.admin  # dev: admin only
    assert vesting_duration >= MIN_VESTING_DURATION  # dev: duration too short
    assert cliff_length <= vesting_duration  # dev: incorrect vesting cliff

    escrow: address = create_forwarder_to(self.target)
    assert ERC20(token).approve(escrow, amount)  # dev: approve failed
    VestingEscrowSimple(escrow).initialize(
        self.admin,
        token,
        recipient,
        amount,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
    )

    return escrow


@external
def commit_transfer_ownership(addr: address) -> bool:
    """
    @notice Transfer ownership of GaugeController to `addr`
    @param addr Address to have ownership transferred to
    """
    assert msg.sender == self.admin  # dev: admin only
    self.future_admin = addr
    log CommitOwnership(addr)

    return True


@external
def apply_transfer_ownership() -> bool:
    """
    @notice Apply pending ownership transfer
    """
    assert msg.sender == self.future_admin  # dev: future admin only
    self.admin = msg.sender
    log ApplyOwnership(msg.sender)

    return True
