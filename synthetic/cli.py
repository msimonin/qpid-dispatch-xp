#!/usr/bin/env python
import click
import logging
import tasks as t

logging.basicConfig(level=logging.DEBUG)

## cli part
@click.group()
def cli():
    pass


@cli.command()
@click.argument('broker')
@click.option("--provider",
    default="vagrant",
    help="Deploy with the given provider")
@click.option("--force",
    is_flag=True)
def deploy(broker, provider, force):
    providers = {
        "g5k": t.g5k,
        "vagrant": t.vagrant
    }
    p = providers[provider]

    p(broker=broker, force=force)
    t.inventory()
    t.prepare(broker=broker)


@cli.command()
@click.option("--force", is_flag=True, help="force redeploy")
def g5k(force):
    t.g5k(force)


@cli.command()
@click.option("--force",is_flag=True, help="force redeploy")
def vagrant(force):
    t.vagrant(force)


@cli.command()
def inventory():
    t.inventory()


@cli.command()
def prepare():
    t.prepare()


@cli.command()
@click.option("--nbr_clients",
    default="1",
    help="Number of clients that will de deployed")
@click.option("--nbr_servers",
    default="1",
    help="Number of servers that will de deployed")
@click.option("--call_type",
    default="rpc_call",
    help="Rpc_call (blocking) or rpc_cast (non blocking) ")
@click.option("--nbr_calls",
    default="100",
    help="Number of calls/cast to execute ")
@click.option("--delay",
    default="0",
    help="Delay in seconds between each call/cast (default 0)")
def test_case_1(nbr_clients, nbr_servers, call_type, nbr_calls, delay):
    t.test_case_1(nbr_clients=nbr_clients, nbr_servers=nbr_servers, call_type=call_type,
                  nbr_calls=nbr_calls, delay=delay)

@cli.command()
def destroy():
    t.destroy()

@cli.command()
def backup():
    t.backup()


if __name__ == "__main__":
    cli()
