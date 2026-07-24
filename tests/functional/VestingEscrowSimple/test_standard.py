import boa

from tests.helpers import ZERO_ADDRESS, at, deploy

UINT256_MAX = 2**256 - 1


def test_claims_standard_tokens(
    chain,
    vesting,
    recipient,
    token,
    amount,
    start_time,
    end_time,
):
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    expected = amount * (midpoint - start_time) // (end_time - start_time)

    assert vesting.claimable() == expected
    assert vesting.locked() == amount - expected
    assert vesting.claim(recipient, UINT256_MAX, sender=recipient) == expected
    assert token.balanceOf(recipient) == expected
    assert vesting.total_claimed() == expected

    chain.pending_timestamp = end_time
    assert vesting.claim(recipient, UINT256_MAX, sender=recipient) == amount - expected
    assert token.balanceOf(recipient) == amount
    assert token.balanceOf(vesting) == 0
    assert vesting.claimable() == 0
    assert vesting.locked() == 0


def test_partial_claim_to_recipient_selected_receiver(
    chain,
    vesting,
    recipient,
    cold_storage,
    token,
    amount,
    end_time,
):
    chain.pending_timestamp = end_time
    partial = amount // 10

    assert vesting.claim(cold_storage, partial, sender=recipient) == partial
    assert token.balanceOf(cold_storage) == partial
    assert vesting.claimable() == amount - partial


def test_cliff_blocks_claims(
    chain,
    vesting,
    recipient,
    amount,
    start_time,
    cliff_duration,
):
    chain.pending_timestamp = start_time + cliff_duration - 1

    assert vesting.claimable() == 0
    assert vesting.locked() == amount
    assert vesting.claim(recipient, UINT256_MAX, sender=recipient) == 0


def test_permissionless_claim_for_recipient(
    chain,
    vesting,
    owner,
    recipient,
    cold_storage,
    token,
    start_time,
    end_time,
):
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    with boa.reverts():
        vesting.claim(cold_storage, UINT256_MAX, sender=owner)

    claimed = vesting.claim(recipient, UINT256_MAX, sender=owner)

    assert claimed > 0
    assert token.balanceOf(recipient) == claimed
    assert token.balanceOf(owner) == 0


def test_closed_claim_only_allows_recipient(
    chain,
    vesting,
    owner,
    recipient,
    start_time,
    end_time,
):
    vesting.set_permissionless_claims(False, sender=recipient)
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    with boa.reverts():
        vesting.claim(recipient, UINT256_MAX, sender=owner)

    assert vesting.claim(recipient, UINT256_MAX, sender=recipient) > 0


def test_only_recipient_changes_permissionless_claims(vesting, owner, recipient):
    with boa.reverts():
        vesting.set_permissionless_claims(False, sender=owner)

    vesting.set_permissionless_claims(False, sender=recipient)
    assert not vesting.permissionless_claims()


def test_revoke_uses_current_time_and_explicit_receiver(
    chain,
    vesting,
    owner,
    recipient,
    token,
    amount,
    start_time,
    end_time,
):
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    recipient_principal = amount * (midpoint - start_time) // (end_time - start_time)

    vesting.revoke(owner, sender=owner)

    assert vesting.disabled_at() == midpoint
    assert vesting.revoker() == ZERO_ADDRESS
    assert token.balanceOf(owner) == amount - recipient_principal
    assert token.balanceOf(vesting) == recipient_principal

    vesting.claim(recipient, UINT256_MAX, sender=recipient)
    assert token.balanceOf(recipient) == recipient_principal
    assert token.balanceOf(vesting) == 0


def test_revoke_accepts_custom_receiver(
    chain,
    vesting,
    owner,
    recipient,
    cold_storage,
    token,
    amount,
    start_time,
    end_time,
):
    midpoint = start_time + (end_time - start_time) // 2
    chain.pending_timestamp = midpoint
    vested = amount * (midpoint - start_time) // (end_time - start_time)

    vesting.revoke(cold_storage, sender=owner)

    assert vesting.disabled_at() == midpoint
    assert token.balanceOf(cold_storage) == amount - vested
    assert token.balanceOf(vesting) == vested

    vesting.claim(recipient, UINT256_MAX, sender=recipient)
    assert token.balanceOf(recipient) == vested


def test_only_revoker_can_revoke(vesting, recipient):
    with boa.reverts():
        vesting.revoke(recipient, sender=recipient)


def test_cannot_revoke_after_completion(chain, vesting, owner, end_time):
    chain.pending_timestamp = end_time
    with boa.reverts():
        vesting.revoke(owner, sender=owner)


def test_revoke_clears_revoker_before_transfer(
    chain,
    standard_target,
    erc4626_target,
    owner,
    recipient,
    amount,
    duration,
    start_time,
):
    token = deploy("test/AdversarialToken", sender=owner)
    factory = deploy(
        "VestingEscrowFactory",
        standard_target,
        erc4626_target,
        sender=owner,
    )
    token.mint(owner, amount, sender=owner)
    token.approve(factory, amount, sender=owner)
    escrow_address = factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        0,
        True,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    token.configure(escrow, 0, sender=owner)
    chain.pending_timestamp = start_time + duration // 2

    escrow.revoke(owner, sender=owner)

    assert token.observed_revoker() == ZERO_ADDRESS


def test_renounce_revocation_is_final(vesting, owner):
    vesting.renounce_revocation(sender=owner)
    assert vesting.revoker() == ZERO_ADDRESS

    with boa.reverts():
        vesting.renounce_revocation(sender=owner)
    with boa.reverts():
        vesting.revoke(owner, sender=owner)


def test_extra_standard_tokens_remain_unsupported(
    chain,
    vesting,
    owner,
    recipient,
    token,
    amount,
    end_time,
):
    donation = amount // 4
    token.mint(owner, donation, sender=owner)
    token.transfer(vesting, donation, sender=owner)
    chain.pending_timestamp = end_time

    vesting.claim(recipient, UINT256_MAX, sender=recipient)

    assert token.balanceOf(recipient) == amount
    assert token.balanceOf(vesting) == donation


def test_large_direct_donation_keeps_partial_claims_live(
    chain,
    standard_target,
    erc4626_target,
    owner,
    recipient,
    accounts,
):
    maximum = 2**128 - 1
    duration = 2**64 - 1
    donation = 2**64 + 5
    start = chain.pending_timestamp + 10
    attacker = accounts[4]
    token = deploy("test/MockToken", sender=owner)
    factory = deploy(
        "VestingEscrowFactory",
        standard_target,
        erc4626_target,
        sender=owner,
    )

    token.mint(owner, maximum, sender=owner)
    token.approve(factory, maximum, sender=owner)
    escrow_address = factory.deploy_vesting_contract(
        token,
        recipient,
        maximum,
        duration,
        start,
        0,
        True,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    token.mint(attacker, donation, sender=owner)
    token.transfer(escrow, donation, sender=attacker)

    chain.pending_timestamp = start + 1
    vested = maximum // duration
    assert escrow.claimable() == vested
    assert escrow.locked() == maximum - vested
    assert escrow.claim(recipient, UINT256_MAX, sender=recipient) == vested
    assert token.balanceOf(recipient) == vested
    assert token.balanceOf(escrow) == maximum - vested + donation
