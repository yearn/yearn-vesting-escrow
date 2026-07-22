#pragma version 0.4.3
#pragma evm-version prague

"""
@title Full-width ERC-4626 recovery mock
@notice Exact-transfer shares with floor conversions across a uint256-wide supply
@dev Models an initial exchange rate, near-total loss, and recovery without
    multiplying two full-width values.
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


MAX_UINT: constant(uint256) = max_value(uint256)
INITIAL_ASSETS: constant(uint256) = MAX_UINT // 3

asset: public(address)
totalAssets: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)


@deploy
def __init__(asset: address, owner: address, donor: address):
    assert asset != empty(address)
    assert owner not in [empty(address), donor]
    assert donor != empty(address)

    self.asset = asset
    self.totalAssets = INITIAL_ASSETS
    self.totalSupply = MAX_UINT
    self.balanceOf[owner] = 3
    self.balanceOf[donor] = MAX_UINT - 3
    log Transfer(sender=empty(address), receiver=owner, value=3)
    log Transfer(sender=empty(address), receiver=donor, value=MAX_UINT - 3)


@external
@view
def convertToAssets(shares: uint256) -> uint256:
    assets: uint256 = self.totalAssets
    if assets == INITIAL_ASSETS:
        # MAX_UINT is exactly divisible by three.
        return shares // 3
    if assets == 1:
        return convert(shares == MAX_UINT, uint256)

    # Recovery checkpoint: assets == 2.
    assert assets == 2
    if shares == MAX_UINT:
        return 2
    return convert(shares >= MAX_UINT // 2 + 1, uint256)


@external
@view
def convertToShares(assets: uint256) -> uint256:
    total_assets: uint256 = self.totalAssets
    if total_assets == INITIAL_ASSETS:
        if assets >= INITIAL_ASSETS:
            return MAX_UINT
        return assets * 3
    if total_assets == 1:
        return MAX_UINT if assets > 0 else 0

    # Recovery checkpoint: total_assets == 2.
    assert total_assets == 2
    if assets == 0:
        return 0
    if assets == 1:
        return MAX_UINT // 2
    return MAX_UINT


@external
def set_total_assets(total_assets: uint256):
    assert total_assets in [1, 2, INITIAL_ASSETS]
    self.totalAssets = total_assets


@internal
def _transfer(owner: address, receiver: address, amount: uint256):
    self.balanceOf[owner] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=owner, receiver=receiver, value=amount)


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
