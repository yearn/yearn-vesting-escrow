import boa
from eth_utils import keccak
import pytest

from tests.helpers import ZERO_ADDRESS, at, deploy, events


def first_create_address(sender):
    sender_bytes = bytes.fromhex(str(sender).removeprefix("0x"))
    return "0x" + keccak(b"\xd6\x94" + sender_bytes + b"\x01")[-20:].hex()


def deploy_standard(
    factory,
    token,
    funder,
    recipient,
    owner,
    amount,
    duration,
    start,
    *,
    cliff=0,
    open_claim=True,
):
    return factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start,
        cliff,
        open_claim,
        owner,
        sender=funder,
    )


def deploy_erc4626(
    factory,
    vault,
    funder,
    recipient,
    owner,
    yield_recipient,
    shares,
    duration,
    start,
    *,
    cliff=0,
    open_claim=True,
):
    return factory.deploy_erc4626_vesting(
        vault,
        recipient,
        shares,
        duration,
        start,
        cliff,
        open_claim,
        owner,
        yield_recipient,
        sender=funder,
    )


def test_factory_configuration(
    vesting_factory,
    standard_target,
    erc4626_target,
    owner,
):
    assert vesting_factory.STANDARD_TARGET() == standard_target.address
    assert vesting_factory.ERC4626_TARGET() == erc4626_target.address
    assert standard_target.implementation_kind() == 1
    assert erc4626_target.implementation_kind() == 2
    assert vesting_factory.escrow_kind(owner) == 0


def test_minimal_deploy_overloads(
    chain,
    vesting_factory,
    owner,
    recipient,
    token,
    vault,
    amount,
    duration,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    standard_address = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        sender=owner,
    )

    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    erc4626_address = vesting_factory.deploy_erc4626_vesting(
        vault,
        recipient,
        amount,
        duration,
        sender=owner,
    )

    standard = at("VestingEscrowSimple", standard_address)
    erc4626 = at("VestingEscrow4626", erc4626_address)
    assert standard.start_time() == chain.pending_timestamp
    assert standard.owner() == owner
    assert erc4626.start_time() == chain.pending_timestamp
    assert erc4626.revocation_owner() == owner
    assert erc4626.yield_recipient() == owner


def test_deploys_standard_escrow(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
    cliff_duration,
    open_claim,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    escrow_address = deploy_standard(
        vesting_factory,
        token,
        owner,
        recipient,
        owner,
        amount,
        duration,
        start_time,
        cliff=cliff_duration,
        open_claim=open_claim,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    event = events(vesting_factory, "TokenVestingEscrowCreated", include_child_logs=False)[0]

    assert event.escrow == escrow.address
    assert event.token == token.address
    assert event.recipient == recipient
    assert event.funder == owner
    assert event.owner == owner
    assert event.amount == amount
    assert event.vesting_start == start_time
    assert event.vesting_duration == duration
    assert event.cliff_length == cliff_duration
    assert event.open_claim == open_claim

    assert vesting_factory.escrows_length() == 1
    assert vesting_factory.escrows(0) == escrow.address
    assert vesting_factory.escrow_kind(escrow) == 1
    assert escrow.initialized()
    assert escrow.token() == token.address
    assert escrow.recipient() == recipient
    assert escrow.owner() == owner
    assert escrow.total_locked() == amount
    assert token.balanceOf(escrow) == amount


def test_deploys_erc4626_escrow_with_distinct_roles(
    vesting_factory,
    owner,
    recipient,
    cold_storage,
    vault,
    asset_token,
    amount,
    duration,
    start_time,
    cliff_duration,
):
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    escrow_address = deploy_erc4626(
        vesting_factory,
        vault,
        owner,
        recipient,
        owner,
        cold_storage,
        amount,
        duration,
        start_time,
        cliff=cliff_duration,
    )
    escrow = at("VestingEscrow4626", escrow_address)
    event = events(vesting_factory, "ERC4626VestingEscrowCreated", include_child_logs=False)[0]

    assert event.escrow == escrow.address
    assert event.vault == vault.address
    assert event.recipient == recipient
    assert event.funder == owner
    assert event.revocation_owner == owner
    assert event.yield_recipient == cold_storage
    assert event.asset_token == asset_token.address
    assert event.funded_shares == amount
    assert event.principal_assets == amount
    assert event.vesting_start == start_time
    assert event.vesting_duration == duration
    assert event.cliff_length == cliff_duration

    assert vesting_factory.escrows_length() == 1
    assert vesting_factory.escrows(0) == escrow.address
    assert vesting_factory.escrow_kind(escrow) == 2
    assert escrow.vault() == vault.address
    assert escrow.asset_token() == asset_token.address
    assert escrow.funded_shares() == amount
    assert escrow.principal_assets() == amount
    assert escrow.revocation_owner() == owner
    assert escrow.yield_recipient() == cold_storage
    assert vault.balanceOf(escrow) == amount


def test_zero_owner_is_allowed_for_irrevocable_escrows(
    vesting_factory,
    owner,
    recipient,
    token,
    vault,
    amount,
    duration,
    start_time,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)
    standard = deploy_standard(
        vesting_factory,
        token,
        owner,
        recipient,
        ZERO_ADDRESS,
        amount,
        duration,
        start_time,
    )

    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    erc4626 = deploy_erc4626(
        vesting_factory,
        vault,
        owner,
        recipient,
        ZERO_ADDRESS,
        owner,
        amount,
        duration,
        start_time,
    )

    assert at("VestingEscrowSimple", standard).owner() == ZERO_ADDRESS
    assert at("VestingEscrow4626", erc4626).revocation_owner() == ZERO_ADDRESS


def test_erc4626_rejects_invalid_yield_recipients(
    vesting_factory,
    owner,
    recipient,
    vault,
    asset_token,
    amount,
    duration,
    start_time,
):
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    proxy_address = first_create_address(vesting_factory.address)
    with boa.env.anchor():
        deployed = deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            amount,
            duration,
            start_time,
        )
        assert str(deployed).lower() == proxy_address.lower()

    for invalid_recipient in (
        ZERO_ADDRESS,
        proxy_address,
        vault.address,
        asset_token.address,
    ):
        with boa.reverts():
            deploy_erc4626(
                vesting_factory,
                vault,
                owner,
                recipient,
                owner,
                invalid_recipient,
                amount,
                duration,
                start_time,
            )


@pytest.mark.parametrize(
    "duration,cliff,error",
    [
        (0, 0, "invalid vesting period"),
        (100, 101, "invalid cliff"),
        (2**64, 0, "duration too long"),
    ],
)
def test_rejects_invalid_schedule(
    chain,
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    cliff,
    error,
):
    start = chain.pending_timestamp + 10
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)

    with boa.reverts(dev=error):
        deploy_standard(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            amount,
            duration,
            start,
            cliff=cliff,
        )


def test_plain_token_cannot_deploy_erc4626(
    vesting_factory,
    owner,
    recipient,
    token,
    amount,
    duration,
    start_time,
):
    token.mint(owner, amount, sender=owner)
    token.approve(vesting_factory, amount, sender=owner)

    with boa.reverts():
        deploy_erc4626(
            vesting_factory,
            token,
            owner,
            recipient,
            owner,
            owner,
            amount,
            duration,
            start_time,
        )

    assert token.balanceOf(owner) == amount
    assert vesting_factory.escrows_length() == 0


def test_partial_vault_cannot_deploy_erc4626(
    vesting_factory,
    owner,
    recipient,
    asset_token,
    amount,
    duration,
    start_time,
):
    vault = deploy("test/PartialERC4626", asset_token, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    with boa.reverts():
        deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            amount,
            duration,
            start_time,
        )

    assert vault.balanceOf(owner) == amount
    assert vesting_factory.escrows_length() == 0


def test_fee_charging_share_token_is_rejected(
    vesting_factory,
    owner,
    recipient,
    vault,
    amount,
    duration,
    start_time,
):
    vault.set_transfer_fee_bps(100, sender=owner)
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)

    with boa.reverts(dev="incorrect funding"):
        deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            amount,
            duration,
            start_time,
        )

    assert vault.balanceOf(owner) == amount


def test_erc4626_rejects_zero_or_excessive_principal(
    vesting_factory,
    owner,
    recipient,
    asset_token,
    duration,
    start_time,
):
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    vault.set_assets_per_share(1, sender=owner)
    vault.mint(owner, 1, sender=owner)
    vault.approve(vesting_factory, 1, sender=owner)
    with boa.reverts():
        deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            1,
            duration,
            start_time,
        )

    vault.set_assets_per_share(2**128, sender=owner)
    vault.mint(owner, 10**18, sender=owner)
    vault.approve(vesting_factory, 10**18, sender=owner)
    with boa.reverts():
        deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            10**18,
            duration,
            start_time,
        )


def test_erc4626_rejects_coarse_roundtrip_conversion(
    vesting_factory,
    owner,
    recipient,
    asset_token,
    duration,
    start_time,
):
    vault = deploy("test/MockERC4626", asset_token, sender=owner)
    vault.set_assets_per_share(15 * 10**17, sender=owner)
    vault.mint(owner, 1, sender=owner)
    vault.approve(vesting_factory, 1, sender=owner)

    with boa.reverts():
        deploy_erc4626(
            vesting_factory,
            vault,
            owner,
            recipient,
            owner,
            owner,
            1,
            duration,
            start_time,
        )


def test_implementations_cannot_be_initialized(
    standard_target,
    erc4626_target,
    owner,
    recipient,
    token,
    vault,
    amount,
    duration,
    start_time,
):
    with boa.reverts(dev="can only initialize once"):
        standard_target.initialize(
            owner,
            token,
            recipient,
            amount,
            start_time,
            start_time + duration,
            0,
            True,
            sender=owner,
        )

    with boa.reverts(dev="can only initialize once"):
        erc4626_target.initialize(
            owner,
            vault,
            recipient,
            amount,
            start_time,
            start_time + duration,
            0,
            True,
            owner,
            sender=owner,
        )


def test_factory_rejects_invalid_targets(
    standard_target,
    erc4626_target,
    owner,
):
    with boa.reverts(dev="duplicate target"):
        deploy(
            "VestingEscrowFactory",
            standard_target,
            standard_target,
            sender=owner,
        )

    with boa.reverts(dev="invalid standard target"):
        deploy(
            "VestingEscrowFactory",
            ZERO_ADDRESS,
            erc4626_target,
            sender=owner,
        )

    with boa.reverts(dev="invalid standard target"):
        deploy(
            "VestingEscrowFactory",
            erc4626_target,
            standard_target,
            sender=owner,
        )
