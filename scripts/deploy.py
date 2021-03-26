from brownie import VestingEscrowSimple, VestingEscrowFactory, ERC20, accounts, chain

YEAR = 365 * 86400
VESTING_ESCROWS = [
    {
        "duration": 3 * YEAR,
        "start": 1594972885,
        "cliff": YEAR / 2,
        "recipients": {
            accounts[1]: 275 * 10 ** 18,
            accounts[2]: 140 * 10 ** 18,
            accounts[3]: 60 * 10 ** 18,
            accounts[4]: 40 * 10 ** 18,
            accounts[5]: 25 * 10 ** 18,
            accounts[6]: 13 * 10 ** 18,
            accounts[7]: 10 * 10 ** 18,
        },
    }
]


def main():
    admin = accounts[0]
    token = ERC20.deploy("StakeWise", "SWISE", 18, {"from": admin})
    template = VestingEscrowSimple.deploy({"from": admin})
    factory = VestingEscrowFactory.deploy(template, admin, {"from": admin})

    total_amount = sum(sum(x["recipients"].values()) for x in VESTING_ESCROWS)
    token._mint_for_testing(total_amount)
    token.approve(factory, total_amount)
    for x in VESTING_ESCROWS:
        for recipient, amount in x["recipients"].items():
            tx = factory.deploy_vesting_contract(
                token,
                recipient,
                amount,
                x["duration"],
                x["start"],
                x["cliff"],
            )
            escrow = VestingEscrowSimple.at(tx.new_contracts[0])
            assert token.balanceOf(escrow) == amount
            assert escrow.recipient() == recipient
            print(f"progress {escrow.unclaimed() / escrow.total_locked():.3%}")
            print("locked", escrow.locked().to("ether"))
            print("unclaimed", escrow.unclaimed().to("ether"))
            escrow.claim({"from": escrow.recipient()})
            print("tokens of recipient", token.balanceOf(recipient).to("ether"))
