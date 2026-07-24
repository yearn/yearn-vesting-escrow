"""Compile every contract with the version pinned by its source pragma."""

from hashlib import sha256

import boa

from yearn_vesting_escrow.paths import contracts_path


def pragma(path):
    for line in path.read_text().splitlines():
        if "version" in line and line.startswith("#"):
            return line.lstrip("# ")
    raise ValueError(f"No compiler version pragma in {path}")


def main():
    contracts = contracts_path()
    # Modules are compiled transitively by their importing deployable contracts.
    sources = sorted(path for path in contracts.rglob("*.vy") if "modules" not in path.parts)
    if not sources:
        raise SystemExit(f"no Vyper contracts found in {contracts}")

    for source in sources:
        compiler_data = boa.load_partial(source).compiler_data
        creation = compiler_data.bytecode
        runtime = compiler_data.bytecode_runtime
        print(
            f"compiled {source.relative_to(contracts)} ({pragma(source)}) "
            f"creation={len(creation)} runtime={len(runtime)} "
            f"creation_sha256={sha256(creation).hexdigest()} "
            f"runtime_sha256={sha256(runtime).hexdigest()}"
        )
    print(f"compiled {len(sources)} contracts")
