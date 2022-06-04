from brownie import VestingEscrowFactory, accounts

def main():
    account = accounts.load(2);
    return VestingEscrowFactory.deploy("0xf2d5d643EF2Ee22C3f899D2ccA4e815b2D07F995", {'from': account})