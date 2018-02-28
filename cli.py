#!/usr/bin/env python

import logging
from os import path

import click

import campaign as c
import tasks as t

logging.basicConfig(level=logging.DEBUG)

DEFAULT_CONF = path.join(path.dirname(path.realpath(__file__)), 'conf.yaml')


@click.group()
def cli():
    pass


@cli.command(help="Claim resources from a PROVIDER and configure them.")
@click.argument('provider')
@click.option("--driver",
              default=t.DRIVER,
              help="communication bus driver")
@click.option("--force",
              is_flag=True,
              help='force redeployment')
@click.option("--conf",
              default=DEFAULT_CONF,
              help="alternative configuration file")
@click.option("--env",
              help="alternative environment directory")
def deploy(provider, driver, force, conf, env):
    config = t.load_config(conf)
    t.PROVIDERS[provider](force=force, config=config, env=env)
    t.inventory()
    t.prepare(driver=driver, env=env)


@cli.command(help="Claim resources on Grid'5000 (frontend).")
@click.option("--force",
              is_flag=True,
              help="force redeployment")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="alternative configuration file")
@click.option("--env",
              help="alternative environment directory")
def g5k(force, config, env):
    t.g5k(force=force, config=config, env=env)


@cli.command(help="Claim resources on vagrant (localhost).")
@click.option("--force",
              is_flag=True,
              help="force redeployment")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="alternative configuration file")
@click.option("--env",
              help="alternative environment directory")
def vagrant(force, config, env):
    t.vagrant(force=force, config=config, env=env)


@cli.command(help="Generate the Ansible inventory [after g5k, and vagrant].")
def inventory():
    t.inventory()


@cli.command(help="Configure available resources [after g5k, vagrant, and inventory].")
def prepare():
    t.prepare()


@cli.command(help="Destroy all the running dockers (keeping deployed resources).")
def destroy():
    t.destroy()


@cli.command(help="Backup environment logs [after test_case_*].")
@click.option("--backup",
              default=t.BACKUP_DIR,
              help="alternative backup directory")
def backup(backup):
    t.backup(backup_dir=backup)


@cli.command(help="Run the test case 1: one single large (distributed) target.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="number of clients")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="number of servers")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="call type (client): rpc_call (blocking), rpc_cast (non-blocking), or rpc-fanout (broadcast)")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="number of execution calls (client)")
@click.option("--pause",
              default=t.PAUSE,
              help="pause between calls in seconds (client)")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="max allowed time for benchmark in second (controller)")
@click.option("--length",
              default=t.LENGTH,
              help="size of payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="executor type (server): evenlet or threading")
@click.option("--version",
              default=t.VERSION,
              help="ombt version as a docker tag")
@click.option("--env",
              default=None,
              help="alternative environment directory")
def test_case_1(nbr_clients, nbr_servers, call_type, nbr_calls, pause, timeout, length, executor, version, env):
    t.test_case_1(nbr_clients=nbr_clients,
                  nbr_servers=nbr_servers,
                  call_type=call_type,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  length=length,
                  executor=executor,
                  version=version,
                  env=env)


@cli.command(help="Run the test case 2: multiple distributed targets.")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="number of topics")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="call type (client): rpc_call (blocking), rpc_cast (non-blocking), or rpc-fanout (broadcast)")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="number of execution calls (client)")
@click.option("--pause",
              default=t.PAUSE,
              help="pause between calls in seconds (client)")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="max allowed time for benchmark in second (controller)")
@click.option("--length",
              default=t.LENGTH,
              help="size of payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="executor type (server): evenlet or threading")
@click.option("--version",
              default=t.VERSION,
              help="ombt version as a docker tag")
@click.option("--env",
              default=None,
              help="alternative environment directory")
def test_case_2(nbr_topics, call_type, nbr_calls, pause, timeout, length, executor, version, env):
    t.test_case_2(nbr_topics=nbr_topics,
                  call_type=call_type,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  length=length,
                  executor=executor,
                  version=version,
                  env=env)


@cli.command(help="Run the test case 3: one single large distributed fanout.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="number of clients")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="Number of calls/cast to execute [client]")
@click.option("--pause",
              default=t.PAUSE,
              help="pause between calls in seconds (client)")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="max allowed time for benchmark in second (controller)")
@click.option("--length",
              default=t.LENGTH,
              help="size of payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="executor type (server): evenlet or threading")
@click.option("--version",
              default=t.VERSION,
              help="ombt version as a docker tag")
@click.option("--env",
              default=None,
              help="alternative environment directory")
def test_case_3(nbr_clients, nbr_servers, nbr_calls, pause, timeout, length, executor, version, env):
    t.test_case_3(nbr_clients=nbr_clients,
                  nbr_servers=nbr_servers,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  length=length,
                  executor=executor,
                  version=version,
                  env=env)


@cli.command(help="Run the test case 4: multiple distributed fanouts")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="number of clients per topic")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="number of servers per topic")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="number of topics")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="number of execution calls (client)")
@click.option("--pause",
              default=t.PAUSE,
              help="pause between calls in seconds (client)")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="max allowed time for benchmark in second (controller)")
@click.option("--length",
              default=t.LENGTH,
              help="size of payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="executor type (server): evenlet or threading")
@click.option("--version",
              default=t.VERSION,
              help="ombt version as a docker tag")
@click.option("--env",
              default=None,
              help="alternative environment directory")
def test_case_4(nbr_clients, nbr_servers, nbr_topics, nbr_calls, pause, timeout, length, executor, version, env):
    t.test_case_4(nbr_clients=nbr_clients,
                  nbr_servers=nbr_servers,
                  nbr_topics=nbr_topics,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  length=length,
                  executor=executor,
                  version=version,
                  env=env)


@cli.command(help="Perform a TEST according to the (swept) parameters described in configuration.")
@click.argument('test')
@click.option("--provider",
              default="vagrant",
              help="target deployment infrastructure")
@click.option("--force",
              is_flag=True,
              help="force initial redeployment")
@click.option("--incremental",
              is_flag=True,
              help="reuse of resources in next iteration")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="alternative configuration file")
@click.option("--env",
              default=None,
              help="alternative environment directory")
def campaign(test, provider, force, incremental, conf, env):
    if incremental:
        c.incremental_campaign(test=test,
                               provider=provider,
                               force=force,
                               conf=conf,
                               env=env)
    else:
        c.campaign(test=test,
                   provider=provider,
                   force=force,
                   conf=conf,
                   env=env)


if __name__ == "__main__":
    cli()
