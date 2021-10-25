from brownie import VestingEscrowSimple, VestingEscrowFactory, accounts


def main():
    admin = accounts.load("deployer")
    template = VestingEscrowSimple.deploy({"from": admin})
    factory = VestingEscrowFactory.deploy(template, {"from": admin})
