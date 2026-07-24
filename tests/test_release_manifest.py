import hashlib
import json
from pathlib import Path

import pytest
from vyper.compiler import compile_code


ROOT = Path(__file__).parents[1]
MANIFEST = json.loads(
    (ROOT / "deployments/ethereum/0.4.0.json").read_text()
)


@pytest.mark.parametrize("contract", MANIFEST["contracts"].values())
def test_v040_contract_sources_and_bytecode_are_frozen(contract):
    path = ROOT / contract["source"]
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == contract["source_sha256"]

    output = compile_code(
        source.decode(),
        contract_path=path,
        output_formats=("bytecode", "bytecode_runtime"),
    )
    creation = bytes.fromhex(output["bytecode"].removeprefix("0x"))
    runtime = bytes.fromhex(output["bytecode_runtime"].removeprefix("0x"))

    assert len(creation) == contract["creation_bytecode_size"]
    assert (
        hashlib.sha256(creation).hexdigest()
        == contract["creation_bytecode_sha256"]
    )
    assert len(runtime) == contract["compiler_runtime_bytecode_size"]
    assert (
        hashlib.sha256(runtime).hexdigest()
        == contract["compiler_runtime_bytecode_sha256"]
    )
