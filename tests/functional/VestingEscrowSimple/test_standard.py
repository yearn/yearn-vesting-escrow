import boa

from tests.helpers import ZERO_ADDRESS, at, deploy


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

    assert vesting.unclaimed() == expected
    assert vesting.locked() == amount - expected
    assert vesting.claim(sender=recipient) == expected
    assert token.balanceOf(recipient) == expected
    assert vesting.total_claimed() == expected

    chain.pending_timestamp = end_time
    assert vesting.claim(sender=recipient) == amount - expected
    assert token.balanceOf(recipient) == amount
    assert token.balanceOf(vesting) == 0
    assert vesting.unclaimed() == 0
    assert vesting.locked() == 0


def test_partial_claim_to_recipient_selected_beneficiary(
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
    assert vesting.unclaimed() == amount - partial


def test_cliff_blocks_claims(
    chain,
    vesting,
    recipient,
    amount,
    start_time,
    cliff_duration,
):
    chain.pending_timestamp = start_time + cliff_duration - 1

    assert vesting.unclaimed() == 0
    assert vesting.locked() == amount
    assert vesting.claim(sender=recipient) == 0


def test_open_claim_for_recipient(
    chain,
    vesting,
    owner,
    recipient,
    token,
    start_time,
    end_time,
):
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    claimed = vesting.claim(recipient, sender=owner)

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
    vesting.set_open_claim(False, sender=recipient)
    chain.pending_timestamp = start_time + (end_time - start_time) // 2

    with boa.reverts(dev="not authorized"):
        vesting.claim(sender=owner)

    assert vesting.claim(sender=recipient) > 0


def test_only_recipient_changes_open_claim(vesting, owner, recipient):
    with boa.reverts(dev="not recipient"):
        vesting.set_open_claim(False, sender=owner)

    vesting.set_open_claim(False, sender=recipient)
    assert not vesting.open_claim()


def test_revoke_uses_current_time_and_fixed_owner(
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

    vesting.revoke(sender=owner)

    assert vesting.disabled_at() == midpoint
    assert vesting.owner() == ZERO_ADDRESS
    assert token.balanceOf(owner) == amount - recipient_principal
    assert token.balanceOf(vesting) == recipient_principal

    vesting.claim(sender=recipient)
    assert token.balanceOf(recipient) == recipient_principal
    assert token.balanceOf(vesting) == 0


def test_revoke_accepts_future_time_and_beneficiary(
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
    ts = start_time + (end_time - start_time) // 2
    vested = amount * (ts - start_time) // (end_time - start_time)

    vesting.revoke(ts, cold_storage, sender=owner)

    assert vesting.disabled_at() == ts
    assert token.balanceOf(cold_storage) == amount - vested
    assert token.balanceOf(vesting) == vested

    chain.pending_timestamp = ts
    vesting.claim(sender=recipient)
    assert token.balanceOf(recipient) == vested


def test_only_owner_can_revoke(vesting, recipient):
    with boa.reverts(dev="not owner"):
        vesting.revoke(sender=recipient)


def test_cannot_revoke_after_completion(chain, vesting, owner, end_time):
    chain.pending_timestamp = end_time
    with boa.reverts(dev="no back to the future"):
        vesting.revoke(sender=owner)


def test_revoke_clears_owner_before_transfer(
    chain,
    standard_target,
    erc4626_target,
    vyper_donation,
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
        vyper_donation,
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
        0,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    token.configure(escrow, 0, sender=owner)
    chain.pending_timestamp = start_time + duration // 2

    escrow.revoke(sender=owner)

    assert token.observed_owner() == ZERO_ADDRESS


def test_disown_is_final(vesting, owner):
    vesting.disown(sender=owner)
    assert vesting.owner() == ZERO_ADDRESS

    with boa.reverts(dev="not owner"):
        vesting.disown(sender=owner)
    with boa.reverts(dev="not owner"):
        vesting.revoke(sender=owner)


def test_collect_dust_sends_unrelated_token_to_recipient(
    vesting,
    owner,
    recipient,
    another_token,
):
    amount = 123
    another_token.mint(vesting, amount, sender=owner)

    vesting.collect_dust(another_token, recipient, sender=owner)

    assert another_token.balanceOf(recipient) == amount
    assert another_token.balanceOf(vesting) == 0


def test_collect_dust_accepts_recipient_selected_beneficiary(
    vesting,
    owner,
    recipient,
    cold_storage,
    another_token,
):
    amount = 123
    another_token.mint(vesting, amount, sender=owner)

    vesting.collect_dust(another_token, cold_storage, sender=recipient)

    assert another_token.balanceOf(cold_storage) == amount


def test_collect_dust_preserves_vesting_reserve(vesting, token, owner, recipient, amount):
    donation = amount // 4
    token.mint(owner, donation, sender=owner)
    token.transfer(vesting, donation, sender=owner)

    vesting.collect_dust(token, sender=recipient)

    assert token.balanceOf(recipient) == donation
    assert token.balanceOf(vesting) == amount


def test_collect_dust_cannot_make_escrow_insolvent(
    standard_target,
    erc4626_target,
    vyper_donation,
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
        vyper_donation,
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
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    excess = amount // 10
    token.mint(escrow, excess, sender=owner)
    token.configure(escrow, 1, sender=owner)

    with boa.reverts():
        escrow.collect_dust(token, sender=recipient)

    assert token.balanceOf(escrow) == amount + excess
    assert token.balanceOf(recipient) == 0


def test_extra_standard_tokens_remain_dust(
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

    vesting.claim(sender=recipient)

    assert token.balanceOf(recipient) == amount
    assert token.balanceOf(vesting) == donation

    vesting.collect_dust(token, sender=recipient)
    assert token.balanceOf(recipient) == amount + donation
    assert token.balanceOf(vesting) == 0


def test_large_direct_donation_keeps_partial_claims_live(
    chain,
    standard_target,
    erc4626_target,
    vyper_donation,
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
        vyper_donation,
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
        0,
        owner,
        sender=owner,
    )
    escrow = at("VestingEscrowSimple", escrow_address)
    token.mint(attacker, donation, sender=owner)
    token.transfer(escrow, donation, sender=attacker)

    chain.pending_timestamp = start + 1
    vested = maximum // duration
    assert escrow.unclaimed() == vested
    assert escrow.locked() == maximum - vested
    assert escrow.claim(sender=recipient) == vested
    assert token.balanceOf(recipient) == vested

    escrow.collect_dust(token, sender=recipient)
    assert token.balanceOf(recipient) == vested + donation
