#pragma version 0.4.3
#pragma evm-version prague
from ethereum.ercs import IERC20

implements: IERC20


interface VestingEscrow:
    def owner() -> address: view


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
watched_escrow: public(address)
observed_owner: public(address)
extra_debit: public(uint256)


@external
def transfer(receiver: address, amount: uint256) -> bool:
    if msg.sender == self.watched_escrow:
        self.observed_owner = staticcall VestingEscrow(msg.sender).owner()

    debit: uint256 = amount + self.extra_debit
    self.balanceOf[msg.sender] -= debit
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


@external
def configure(watched_escrow: address, extra_debit: uint256):
    self.watched_escrow = watched_escrow
    self.extra_debit = extra_debit
