import brownie


def test_reinit_impossible(vesting, accounts, token):
    vesting.renounce_ownership({"from": accounts[0]})
    with brownie.reverts("dev: can only initialize once"):
        vesting.initialize(
            accounts[1], token, accounts[1], 0, 0, 0, 0, {"from": accounts[1]}
        )
