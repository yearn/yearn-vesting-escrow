#pragma version 0.4.3
#pragma evm-version prague

"""
@title Rational-rate ERC-4626 test token
@notice Models asset/share unit ratios without assuming a 1e18 scale
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


asset: public(address)
asset_units: public(uint256)
share_units: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)


@deploy
def __init__(asset: address, asset_units: uint256, share_units: uint256):
    assert asset != empty(address)
    assert asset_units > 0 and share_units > 0
    self.asset = asset
    self.asset_units = asset_units
    self.share_units = share_units


@external
@view
def convertToAssets(shares: uint256) -> uint256:
    return shares * self.asset_units // self.share_units


@external
@view
def convertToShares(assets: uint256) -> uint256:
    return assets * self.share_units // self.asset_units


@external
def set_ratio(asset_units: uint256, share_units: uint256):
    assert asset_units > 0 and share_units > 0
    self.asset_units = asset_units
    self.share_units = share_units


@external
def transfer(receiver: address, amount: uint256) -> bool:
    self.balanceOf[msg.sender] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=msg.sender, receiver=receiver, value=amount)
    return True


@external
def transferFrom(owner: address, receiver: address, amount: uint256) -> bool:
    self.balanceOf[owner] -= amount
    self.balanceOf[receiver] += amount
    self.allowance[owner][msg.sender] -= amount
    log Transfer(sender=owner, receiver=receiver, value=amount)
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
