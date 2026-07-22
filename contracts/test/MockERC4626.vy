#pragma version 0.4.3
#pragma evm-version prague

"""
@title Controllable ERC-4626 Share Mock
@notice ERC20 shares with a configurable asset conversion rate for vesting tests
"""

from ethereum.ercs import IERC20

implements: IERC20


event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256


SCALE: constant(uint256) = 10**18

asset: public(address)
assets_per_share: public(uint256)
transfer_fee_bps: public(uint256)
reentry_target: public(address)
reentry_succeeded: public(bool)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)


@deploy
def __init__(asset: address):
    assert asset != empty(address)
    self.asset = asset
    self.assets_per_share = SCALE


@external
@view
def convertToAssets(shares: uint256) -> uint256:
    if self.assets_per_share == SCALE:
        return shares
    return shares * self.assets_per_share // SCALE


@external
@view
def convertToShares(assets: uint256) -> uint256:
    if self.assets_per_share == SCALE:
        return assets
    return assets * SCALE // self.assets_per_share


@external
def set_assets_per_share(assets_per_share: uint256):
    self.assets_per_share = assets_per_share


@external
def set_transfer_fee_bps(transfer_fee_bps: uint256):
    assert transfer_fee_bps <= 10_000
    self.transfer_fee_bps = transfer_fee_bps


@external
def set_reentry_target(reentry_target: address):
    self.reentry_target = reentry_target
    self.reentry_succeeded = False


@internal
def _transfer(owner: address, receiver: address, amount: uint256):
    self.balanceOf[owner] -= amount

    fee: uint256 = amount * self.transfer_fee_bps // 10_000
    received: uint256 = amount - fee
    self.balanceOf[receiver] += received
    log Transfer(sender=owner, receiver=receiver, value=received)

    if fee > 0:
        self.totalSupply -= fee
        log Transfer(sender=owner, receiver=empty(address), value=fee)

    if self.reentry_target != empty(address) and owner == self.reentry_target:
        self.reentry_succeeded = raw_call(
            self.reentry_target,
            method_id("claim_yield()"),
            max_outsize=0,
            revert_on_failure=False,
        )


@external
def transfer(receiver: address, amount: uint256) -> bool:
    self._transfer(msg.sender, receiver, amount)
    return True


@external
def transferFrom(owner: address, receiver: address, amount: uint256) -> bool:
    self.allowance[owner][msg.sender] -= amount
    self._transfer(owner, receiver, amount)
    log Approval(owner=owner, spender=msg.sender, value=self.allowance[owner][msg.sender])
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)
    return True


@external
def mint(receiver: address, amount: uint256):
    assert receiver != empty(address)
    self.totalSupply += amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=empty(address), receiver=receiver, value=amount)
