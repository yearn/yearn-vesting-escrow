from pathlib import Path

from vyper.compiler import compile_code

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def compile_abi(name):
    path = CONTRACTS / f"{name}.vy"
    return compile_code(
        path.read_text(),
        contract_path=path,
        output_formats=["abi"],
    )["abi"]


def functions(abi):
    return {
        (item["name"], tuple(arg["type"] for arg in item["inputs"])): (
            tuple(result["type"] for result in item["outputs"]),
            item["stateMutability"],
        )
        for item in abi
        if item["type"] == "function"
    }


def events(abi):
    return {
        (
            item["name"],
            tuple((arg["name"], arg["type"], arg["indexed"]) for arg in item["inputs"]),
        )
        for item in abi
        if item["type"] == "event"
    }


def test_standard_escrow_has_one_explicit_lifecycle_surface():
    abi = compile_abi("VestingEscrowSimple")
    actual = functions(abi)
    expected = {
        ("initialize", ("address", "address", "address", "uint256", "uint256", "uint256", "uint256", "bool")): (
            ("bool",),
            "nonpayable",
        ),
        ("claimable", ()): (("uint256",), "view"),
        ("locked", ()): (("uint256",), "view"),
        ("permissionless_claims", ()): (("bool",), "view"),
        ("claim", ("address", "uint256")): (("uint256",), "nonpayable"),
        ("revoke", ("address",)): ((), "nonpayable"),
        ("renounce_revocation", ()): ((), "nonpayable"),
        ("set_permissionless_claims", ("bool",)): ((), "nonpayable"),
        ("recipient", ()): (("address",), "view"),
        ("token", ()): (("address",), "view"),
        ("start_time", ()): (("uint256",), "view"),
        ("end_time", ()): (("uint256",), "view"),
        ("cliff_length", ()): (("uint256",), "view"),
        ("total_locked", ()): (("uint256",), "view"),
        ("total_claimed", ()): (("uint256",), "view"),
        ("disabled_at", ()): (("uint256",), "view"),
        ("revoker", ()): (("address",), "view"),
    }
    assert actual == expected

    assert events(abi) == {
        ("Claim", (("receiver", "address", True), ("amount", "uint256", False))),
        (
            "Revoked",
            (
                ("recipient", "address", True),
                ("revoker", "address", True),
                ("receiver", "address", True),
                ("unvested_amount", "uint256", False),
                ("ts", "uint256", False),
            ),
        ),
        ("RevocationRenounced", (("revoker", "address", True),)),
        ("PermissionlessClaimsSet", (("enabled", "bool", False),)),
    }
    assert next(item for item in abi if item["type"] == "constructor")["inputs"] == []


def test_erc4626_escrow_uses_explicit_asset_and_share_units():
    abi = compile_abi("VestingEscrow4626")
    actual = functions(abi)
    expected = {
        (
            "initialize",
            ("address", "address", "address", "uint256", "uint256", "uint256", "uint256", "bool", "address"),
        ): (("bool",), "nonpayable"),
        ("claimable_principal_assets", ()): (("uint256",), "view"),
        ("preview_principal_claim", ("uint256",)): (("uint256", "uint256"), "view"),
        ("claimable_yield_shares", ()): (("uint256",), "view"),
        ("permissionless_claims", ()): (("bool",), "view"),
        ("claim_principal", ("address", "uint256")): (("uint256",), "nonpayable"),
        ("claim_yield", ()): (("uint256",), "nonpayable"),
        ("revoke", ("address",)): ((), "nonpayable"),
        ("renounce_revocation", ()): ((), "nonpayable"),
        ("set_permissionless_claims", ("bool",)): ((), "nonpayable"),
        ("recipient", ()): (("address",), "view"),
        ("vault", ()): (("address",), "view"),
        ("start_time", ()): (("uint256",), "view"),
        ("end_time", ()): (("uint256",), "view"),
        ("cliff_length", ()): (("uint256",), "view"),
        ("principal_assets", ()): (("uint256",), "view"),
        ("claimed_principal_assets", ()): (("uint256",), "view"),
        ("disabled_at", ()): (("uint256",), "view"),
        ("revoker", ()): (("address",), "view"),
        ("yield_recipient", ()): (("address",), "view"),
    }
    assert actual == expected

    assert events(abi) == {
        (
            "PrincipalClaim",
            (
                ("receiver", "address", True),
                ("principal_assets", "uint256", False),
                ("shares", "uint256", False),
            ),
        ),
        ("YieldClaim", (("recipient", "address", True), ("shares", "uint256", False))),
        (
            "Revoked",
            (
                ("recipient", "address", True),
                ("revoker", "address", True),
                ("receiver", "address", True),
                ("unvested_principal_assets", "uint256", False),
                ("shares", "uint256", False),
                ("ts", "uint256", False),
            ),
        ),
        ("RevocationRenounced", (("revoker", "address", True),)),
        ("PermissionlessClaimsSet", (("enabled", "bool", False),)),
    }
    assert next(item for item in abi if item["type"] == "constructor")["inputs"] == []


def test_factory_exposes_two_explicit_deployment_paths():
    abi = compile_abi("VestingEscrowFactory")
    actual = functions(abi)
    expected = {
        (
            "deploy_vesting_contract",
            ("address", "address", "uint256", "uint256", "uint256", "uint256", "bool", "address"),
        ): (("address",), "nonpayable"),
        (
            "deploy_erc4626_vesting",
            ("address", "address", "uint256", "uint256", "uint256", "uint256", "bool", "address", "address"),
        ): (("address",), "nonpayable"),
        ("STANDARD_TARGET", ()): (("address",), "view"),
        ("ERC4626_TARGET", ()): (("address",), "view"),
    }
    assert actual == expected

    assert events(abi) == {
        (
            "TokenVestingEscrowCreated",
            (
                ("escrow", "address", True),
                ("token", "address", True),
                ("recipient", "address", True),
                ("funder", "address", False),
                ("revoker", "address", False),
                ("amount", "uint256", False),
                ("vesting_start", "uint256", False),
                ("vesting_duration", "uint256", False),
                ("cliff_length", "uint256", False),
                ("permissionless_claims", "bool", False),
            ),
        ),
        (
            "ERC4626VestingEscrowCreated",
            (
                ("escrow", "address", True),
                ("vault", "address", True),
                ("recipient", "address", True),
                ("funder", "address", False),
                ("revoker", "address", False),
                ("yield_recipient", "address", False),
                ("asset_token", "address", False),
                ("funded_shares", "uint256", False),
                ("principal_assets", "uint256", False),
                ("vesting_start", "uint256", False),
                ("vesting_duration", "uint256", False),
                ("cliff_length", "uint256", False),
                ("permissionless_claims", "bool", False),
            ),
        ),
    }

    constructor = next(item for item in abi if item["type"] == "constructor")
    assert [arg["type"] for arg in constructor["inputs"]] == ["address", "address"]
