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


def test_standard_escrow_keeps_the_legacy_token_lifecycle_abi():
    abi = compile_abi("VestingEscrowSimple")
    actual = functions(abi)
    expected = {
        ("initialize", ("address", "address", "address", "uint256", "uint256", "uint256", "uint256", "bool")): (
            ("bool",),
            "nonpayable",
        ),
        ("implementation_kind", ()): (("uint256",), "pure"),
        ("unclaimed", ()): (("uint256",), "view"),
        ("locked", ()): (("uint256",), "view"),
        ("claim", ()): (("uint256",), "nonpayable"),
        ("claim", ("address",)): (("uint256",), "nonpayable"),
        ("claim", ("address", "uint256")): (("uint256",), "nonpayable"),
        ("revoke", ()): ((), "nonpayable"),
        ("revoke", ("uint256",)): ((), "nonpayable"),
        ("revoke", ("uint256", "address")): ((), "nonpayable"),
        ("disown", ()): ((), "nonpayable"),
        ("set_open_claim", ("bool",)): ((), "nonpayable"),
        ("collect_dust", ("address",)): ((), "nonpayable"),
        ("collect_dust", ("address", "address")): ((), "nonpayable"),
        ("recipient", ()): (("address",), "view"),
        ("token", ()): (("address",), "view"),
        ("start_time", ()): (("uint256",), "view"),
        ("end_time", ()): (("uint256",), "view"),
        ("cliff_length", ()): (("uint256",), "view"),
        ("total_locked", ()): (("uint256",), "view"),
        ("total_claimed", ()): (("uint256",), "view"),
        ("disabled_at", ()): (("uint256",), "view"),
        ("open_claim", ()): (("bool",), "view"),
        ("initialized", ()): (("bool",), "view"),
        ("owner", ()): (("address",), "view"),
    }
    assert actual == expected

    assert events(abi) == {
        ("Claim", (("recipient", "address", True), ("claimed", "uint256", False))),
        (
            "Revoked",
            (
                ("recipient", "address", False),
                ("owner", "address", False),
                ("rugged", "uint256", False),
                ("ts", "uint256", False),
            ),
        ),
        ("Disowned", (("owner", "address", False),)),
        ("SetOpenClaim", (("state", "bool", False),)),
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
        ("implementation_kind", ()): (("uint256",), "pure"),
        ("vested_principal_assets", ()): (("uint256",), "view"),
        ("claimable_principal_assets", ()): (("uint256",), "view"),
        ("claimable_shares", ()): (("uint256",), "view"),
        ("locked_shares", ()): (("uint256",), "view"),
        ("claimable_yield_shares", ()): (("uint256",), "view"),
        ("claim_principal", ()): (("uint256",), "nonpayable"),
        ("claim_principal", ("address",)): (("uint256",), "nonpayable"),
        ("claim_principal", ("address", "uint256")): (("uint256",), "nonpayable"),
        ("claim_yield", ()): (("uint256",), "nonpayable"),
        ("revoke", ()): ((), "nonpayable"),
        ("revoke", ("uint256",)): ((), "nonpayable"),
        ("revoke", ("uint256", "address")): ((), "nonpayable"),
        ("renounce_revocation", ()): ((), "nonpayable"),
        ("set_open_claim", ("bool",)): ((), "nonpayable"),
        ("collect_dust", ("address",)): ((), "nonpayable"),
        ("collect_dust", ("address", "address")): ((), "nonpayable"),
        ("recipient", ()): (("address",), "view"),
        ("vault", ()): (("address",), "view"),
        ("asset_token", ()): (("address",), "view"),
        ("start_time", ()): (("uint256",), "view"),
        ("end_time", ()): (("uint256",), "view"),
        ("cliff_length", ()): (("uint256",), "view"),
        ("funded_shares", ()): (("uint256",), "view"),
        ("principal_assets", ()): (("uint256",), "view"),
        ("claimed_principal_assets", ()): (("uint256",), "view"),
        ("disabled_at", ()): (("uint256",), "view"),
        ("open_claim", ()): (("bool",), "view"),
        ("initialized", ()): (("bool",), "view"),
        ("revocation_owner", ()): (("address",), "view"),
        ("yield_recipient", ()): (("address",), "view"),
    }
    assert actual == expected

    assert events(abi) == {
        (
            "PrincipalClaim",
            (
                ("beneficiary", "address", True),
                ("principal_assets", "uint256", False),
                ("shares", "uint256", False),
            ),
        ),
        ("YieldClaim", (("recipient", "address", True), ("shares", "uint256", False))),
        (
            "Revoked",
            (
                ("recipient", "address", True),
                ("revocation_owner", "address", True),
                ("beneficiary", "address", True),
                ("clawed_back_principal_assets", "uint256", False),
                ("shares", "uint256", False),
                ("ts", "uint256", False),
            ),
        ),
        ("RevocationRenounced", (("revocation_owner", "address", True),)),
        ("SetOpenClaim", (("state", "bool", False),)),
    }
    assert next(item for item in abi if item["type"] == "constructor")["inputs"] == []


def test_factory_exposes_two_explicit_deployment_paths():
    abi = compile_abi("VestingEscrowFactory")
    actual = functions(abi)
    prefix = ("address", "address", "uint256", "uint256")
    standard_optional = ("uint256", "uint256", "bool", "address")
    erc4626_optional = ("uint256", "uint256", "bool", "address", "address")
    expected = {
        ("deploy_vesting_contract", prefix + standard_optional[:count]): (("address",), "nonpayable")
        for count in range(len(standard_optional) + 1)
    }
    expected.update(
        {
            ("deploy_erc4626_vesting", prefix + erc4626_optional[:count]): (("address",), "nonpayable")
            for count in range(len(erc4626_optional) + 1)
        }
    )
    expected.update(
        {
            ("STANDARD_TARGET", ()): (("address",), "view"),
            ("ERC4626_TARGET", ()): (("address",), "view"),
            ("escrows_length", ()): (("uint256",), "view"),
            ("escrows", ("uint256",)): (("address",), "view"),
            ("escrow_kind", ("address",)): (("uint256",), "view"),
        }
    )
    assert actual == expected

    assert events(abi) == {
        (
            "TokenVestingEscrowCreated",
            (
                ("escrow", "address", True),
                ("token", "address", True),
                ("recipient", "address", True),
                ("funder", "address", False),
                ("owner", "address", False),
                ("amount", "uint256", False),
                ("vesting_start", "uint256", False),
                ("vesting_duration", "uint256", False),
                ("cliff_length", "uint256", False),
                ("open_claim", "bool", False),
            ),
        ),
        (
            "ERC4626VestingEscrowCreated",
            (
                ("escrow", "address", True),
                ("vault", "address", True),
                ("recipient", "address", True),
                ("funder", "address", False),
                ("revocation_owner", "address", False),
                ("yield_recipient", "address", False),
                ("asset_token", "address", False),
                ("funded_shares", "uint256", False),
                ("principal_assets", "uint256", False),
                ("vesting_start", "uint256", False),
                ("vesting_duration", "uint256", False),
                ("cliff_length", "uint256", False),
                ("open_claim", "bool", False),
            ),
        ),
    }

    constructor = next(item for item in abi if item["type"] == "constructor")
    assert [arg["type"] for arg in constructor["inputs"]] == ["address", "address"]
