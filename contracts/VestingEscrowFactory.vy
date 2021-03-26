# @version 0.2.8
"""
@title Vesting Escrow Factory
@author Curve Finance, Yearn Finance, StakeWise Labs
@license MIT
@notice Stores and distributes ERC20 tokens by deploying `VestingEscrowSimple` contracts
"""

from vyper.interfaces import ERC20


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
    def unclaimed() -> uint256: view


event VestingEscrowCreated:
    funder: indexed(address)
    token: indexed(address)
    recipient: indexed(address)
    escrow: address
    amount: uint256
    vesting_start: uint256
    vesting_duration: uint256
    cliff_length: uint256

MAX_ESCROWS: constant(int128) = 128

admin: public(address)
target: public(address)

escrows: public(HashMap[address, address[MAX_ESCROWS]])
escrow_counts: public(HashMap[address, int128])

@external
def __init__(target: address, admin: address):
    """
    @notice Contract constructor
    @dev Prior to deployment you must deploy one copy of `VestingEscrowSimple` which
         is used as a library for vesting contracts deployed by this factory
    @param target `VestingEscrowSimple` contract address
    @param admin Address of the factory admin
    """
    self.target = target
    self.admin = admin

@view
@external
def balanceOf(user: address) -> uint256:
    """
    @notice Get the total amount of unclaimed tokens for `user`
    @param user User wallet address
    @return Total amount of unclaimed tokens
    """
    total: uint256 = 0
    for i in range(MAX_ESCROWS):
        escrow: address = self.escrows[user][i]
        if escrow == ZERO_ADDRESS:
            break

        total += VestingEscrowSimple(escrow).unclaimed()

    return total

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
    @param token Address of the ERC20 token being distributed
    @param recipient Address to vest tokens for
    @param amount Amount of tokens being vested for `recipient`
    @param vesting_duration Time period over which tokens are released
    @param vesting_start Epoch time when tokens begin to vest
    """
    assert msg.sender == self.admin  # dev: admin only
    assert cliff_length <= vesting_duration  # dev: incorrect vesting cliff
    escrow: address = create_forwarder_to(self.target)

    # Add escrow to mapping of recipient's escrows
    num_escrows: int128 = self.escrow_counts[recipient]
    assert num_escrows < MAX_ESCROWS  # dev: too many escrows
    self.escrows[recipient][num_escrows] = escrow
    self.escrow_counts[recipient] += 1

    assert ERC20(token).transferFrom(msg.sender, self, amount)  # dev: funding failed
    assert ERC20(token).approve(escrow, amount)  # dev: approve failed
    VestingEscrowSimple(escrow).initialize(
        msg.sender,
        token,
        recipient,
        amount,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
    )
    log VestingEscrowCreated(msg.sender, token, recipient, escrow, amount, vesting_start, vesting_duration, cliff_length)
    return escrow
