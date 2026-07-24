#pragma version 0.4.3
#pragma evm-version prague

"""
@title No-return ERC-20 test token
@notice Exercises compatibility with tokens that omit transfer return data
"""

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256


balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)


@external
def transfer(receiver: address, amount: uint256):
    self.balanceOf[msg.sender] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=msg.sender, receiver=receiver, value=amount)


@external
def transferFrom(owner: address, receiver: address, amount: uint256):
    self.balanceOf[owner] -= amount
    self.balanceOf[receiver] += amount
    self.allowance[owner][msg.sender] -= amount
    log Transfer(sender=owner, receiver=receiver, value=amount)
    log Approval(owner=owner, spender=msg.sender, value=self.allowance[owner][msg.sender])


@external
def approve(spender: address, amount: uint256):
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)


@external
def mint(receiver: address, amount: uint256):
    assert receiver != empty(address)
    self.totalSupply += amount
    self.balanceOf[receiver] += amount
    log Transfer(sender=empty(address), receiver=receiver, value=amount)
