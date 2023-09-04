import click
import ape
from ape import networks, project
from ape.cli import (
    NetworkBoundCommand,
    ape_cli_context,
)


YEAR = int(365.25 * 24 * 60 * 60)
NUMBER_OF_VESTS = 10
ESCROWS = {
    "duration": 3 * YEAR,
    "start_time": 1650990522,
    "cliff_duration": YEAR // 3,
    "open_claim": True,
    "support_vyper": 100,
    "recipients": {
        k.address: 2**v * 10**18 for k, v in zip(ape.utils.generate_dev_accounts(), range(NUMBER_OF_VESTS))
    },
}


@click.group(short_help="Vesting escrow deployment")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@ape_cli_context()
def deploy(cli_ctx):
    # check network
    ecosystem_name = networks.provider.network.ecosystem.name
    network_name = networks.provider.network.name
    provider_name = networks.provider.name

    owner = cli_ctx.account_manager.test_accounts[0]

    click.secho(
        f"You are connected to network '{ecosystem_name}:{network_name}:{provider_name}'.",
        fg="yellow",
    )
    click.secho(f"Deployer is set to '{owner}'.", fg="yellow")

    vyper_donate = "0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775"

    target = project.VestingEscrowSimple.deploy(sender=owner)
    factory = project.VestingEscrowFactory.deploy(target, vyper_donate, sender=owner)

    token = project.MockToken.deploy(sender=owner)
    target = project.VestingEscrowSimple.deploy(sender=owner)
    factory = project.VestingEscrowFactory.deploy(target, vyper_donate, sender=owner)

    amount = sum(ESCROWS["recipients"].values())
    support_amount = sum(ESCROWS["recipients"].values()) * ESCROWS["support_vyper"] // 10_000
    total_amount = amount + support_amount

    token.mint(owner, total_amount, sender=owner)
    token.approve(factory, total_amount, sender=owner)

    for recipient, amount in ESCROWS["recipients"].items():
        if recipient == owner:
            continue

        tx = factory.deploy_vesting_contract(
            token,
            recipient,
            amount,
            ESCROWS["duration"],
            ESCROWS["start_time"],
            ESCROWS["cliff_duration"],
            ESCROWS["open_claim"],
            ESCROWS["support_vyper"],
            sender=owner,
        )

        escrow = project.VestingEscrowSimple.at(tx.return_value)

        assert token.balanceOf(escrow) == amount
        assert escrow.recipient() == recipient
        assert escrow.end_time() == ESCROWS["start_time"] + ESCROWS["duration"]
        assert escrow.start_time() == ESCROWS["start_time"]
        assert escrow.cliff_length() == ESCROWS["cliff_duration"]
        assert escrow.open_claim() == ESCROWS["open_claim"]

        print(f"progress {escrow.unclaimed() / escrow.total_locked():.3%}")
        print("locked", escrow.locked())
        print("unclaimed", escrow.unclaimed())
