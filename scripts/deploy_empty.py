import click
import ape
from ape.api.networks import LOCAL_NETWORK_NAME
from ape.types import AddressType
from ape import networks, project
from ape.cli import (
    NetworkBoundCommand,
    network_option,
    get_user_selected_account,
    ape_cli_context,
)


@click.group(short_help="Vesting factory and target deployment")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@ape_cli_context()
@network_option()
def deploy(cli_ctx, network):
    # check network
    ecosystem_name = networks.provider.network.ecosystem.name
    network_name = networks.provider.network.name
    provider_name = networks.provider.name

    print(network_name)

    if network == LOCAL_NETWORK_NAME or network_name.endswith("-fork"):
        account = cli_ctx.account_manager.test_accounts[0]
    else:
        account = get_user_selected_account()

    click.secho(
        f"You are connected to network '{ecosystem_name}:{network_name}:{provider_name}'.",
        fg="yellow",
    )
    click.secho(f"Deployer is set to '{account}'.", fg="yellow")

    vyper_donate = ape.convert("vyperlang.eth", AddressType)
    assert vyper_donate == "0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775"

    target = project.VestingEscrowSimple.deploy(sender=account)
    factory = project.VestingEscrowFactory.deploy(target, vyper_donate, sender=account)
