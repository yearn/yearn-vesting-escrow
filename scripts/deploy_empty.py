from brownie import VestingEscrowSimple, VestingEscrowFactory, accounts

def main():
    admin = accounts.load('deployer')
    template = VestingEscrowSimple.deploy({"from": admin})
    VestingEscrowFactory.deploy(template, admin, {"from": admin})
