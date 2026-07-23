from pathlib import Path

from vyper.compiler import compile_code

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def compile_abi(name):
    path = CONTRACTS / f"{name}.vy"
    return compile_code(path.read_text(), contract_path=path, output_formats=["abi"])["abi"]


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


def test_escrow_preserves_deployed_abi():
    abi = compile_abi("VestingEscrowSimple")
    actual = functions(abi)
    expected = {
        ("initialize", ("address", "address", "address", "uint256", "uint256", "uint256", "uint256", "bool")): (
            ("bool",),
            "nonpayable",
        ),
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
    expected.update(
        {
            ("version", ()): (("uint256",), "pure"),
            (
                "initialize",
                ("address", "address", "address", "uint256", "uint256", "uint256", "uint256", "bool", "bool"),
            ): (("bool",), "nonpayable"),
            ("asset", ()): (("address",), "view"),
            ("vested_principal", ()): (("uint256",), "view"),
            ("claimable_principal", ()): (("uint256",), "view"),
            ("claimable_yield", ()): (("uint256",), "view"),
            ("claim_yield", ()): (("uint256",), "nonpayable"),
            ("total_principal", ()): (("uint256",), "view"),
            ("principal_claimed", ()): (("uint256",), "view"),
            ("yield_recipient", ()): (("address",), "view"),
            ("yield_to_owner", ()): (("bool",), "view"),
        }
    )
    assert actual == expected

    expected_events = {
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
    expected_events.add(("YieldClaim", (("recipient", "address", True), ("claimed", "uint256", False))))
    assert events(abi) == expected_events

    constructor = next(item for item in abi if item["type"] == "constructor")
    assert constructor["inputs"] == []


def test_factory_preserves_deployed_abi():
    abi = compile_abi("VestingEscrowFactory")
    actual = functions(abi)
    prefix = ("address", "address", "uint256", "uint256")
    optional = ("uint256", "uint256", "bool", "uint256", "address")
    expected = {
        ("deploy_vesting_contract", prefix + optional[:count]): (("address",), "nonpayable")
        for count in range(len(optional) + 1)
    }
    expected.update(
        {
            ("version", ()): (("uint256",), "pure"),
            ("deploy_vesting_contract", prefix + optional + ("bool",)): (("address",), "nonpayable"),
            ("TARGET", ()): (("address",), "view"),
            ("VYPER", ()): (("address",), "view"),
            ("escrows_length", ()): (("uint256",), "view"),
            ("escrows", ("uint256",)): (("address",), "view"),
        }
    )
    assert actual == expected

    expected_event = (
        "VestingEscrowCreated",
        (
            ("funder", "address", True),
            ("token", "address", True),
            ("recipient", "address", True),
            ("escrow", "address", False),
            ("amount", "uint256", False),
            ("vesting_start", "uint256", False),
            ("vesting_duration", "uint256", False),
            ("cliff_length", "uint256", False),
            ("open_claim", "bool", False),
        ),
    )
    assert events(abi) == {
        expected_event,
        (
            "VestingEscrowConfigured",
            (
                ("escrow", "address", True),
                ("owner", "address", True),
                ("asset", "address", True),
                ("yield_to_owner", "bool", False),
                ("principal", "uint256", False),
            ),
        ),
    }

    constructor = next(item for item in abi if item["type"] == "constructor")
    assert [arg["type"] for arg in constructor["inputs"]] == ["address", "address"]
