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


@cli.command(help="Claim resources from a provider and configure them")
@click.argument('broker')
@click.option("--provider",
              default="vagrant",
              help="Deploy with the given provider")
@click.option("--force",
              is_flag=True)
@click.option("--conf",
              default=DEFAULT_CONF,
              help="Configuration file to use")
@click.option("--env",
              help="Use this environment directory instead of the default one")
def deploy(broker, provider, force, conf, env):
    config = t.load_config(conf)
    t.PROVIDERS[provider](broker=broker, force=force, config=config, env=env)
    t.inventory()
    t.prepare(broker=broker)


@cli.command(help="Claim resources on Grid'5000 (from a frontend)")
@click.option("--force",
              is_flag=True,
              help="force redeploy")
def g5k(force):
    t.g5k(force)


@cli.command(help="Claim resources on vagrant (local machine)")
@click.option("--force",
              is_flag=True,
              help="force redeploy")
def vagrant(force):
    t.vagrant(force)


@cli.command(help="Generate the Ansible inventory file. [after g5k,vagrant]")
def inventory():
    t.inventory()


@cli.command(help="Configure the resources. [after g5k,vagrant and inventory]")
def prepare():
    t.prepare()


@cli.command(help="Destroy all the running dockers (not destroying the resources)")
def destroy():
    t.destroy()


@cli.command(help="Backup the environment")
def backup():
    t.backup()


@cli.command(help="Runs the test case 1: one single large (distributed) target")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="call type [client]: rpc_call (blocking), rpc_cast (non-blocking), or  rpc-fanout (broadcast)")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="Number of calls/cast to execute [client]")
@click.option("--pause",
              default=t.PAUSE,
              help="Pause in second between each call [client]")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="Total time in second of the benchmark [controller]")
@click.option("--length",
              default=t.LENGTH,
              help="The size of the payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="type of executor on the server: evenlet or threading")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
@click.option("--env",
              default=None,
              help="Use this environment directory instead of the default one")
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


@cli.command(help="Runs the test case 2: multiple distributed targets")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="Number of topics that will set")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="call type [client]: rpc_call (blocking), rpc_cast (non-blocking), or  rpc-fanout (broadcast)")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="Number of calls/cast to execute [client]")
@click.option("--pause",
              default=t.PAUSE,
              help="Pause in second between each call [client]")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="Total time in second of the benchmark [controller]")
@click.option("--length",
              default=t.LENGTH,
              help="The size of the payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
@click.option("--env",
              default=None,
              help="Use this environment directory instead of the default one")
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


@cli.command(help="Runs the test case 3: one single large distributed fanout")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="Number of calls/cast to execute [client]")
@click.option("--pause",
              default=t.PAUSE,
              help="Pause in second between each call [client]")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="Total time in second of the benchmark [controller]")
@click.option("--length",
              default=t.LENGTH,
              help="The size of the payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
@click.option("--env",
              default=None,
              help="Use this environment directory instead of the default one")
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


@cli.command(help="Runs the test case 4: multiple distributed fanouts")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed per topic")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed per topic")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="Number of topics that will set")
@click.option("--nbr_calls",
              default=t.NBR_CALLS,
              help="Number of calls/cast to execute [client]")
@click.option("--pause",
              default=t.PAUSE,
              help="Pause in second between each call [client]")
@click.option("--timeout",
              default=t.TIMEOUT,
              help="Total time in second of the benchmark [controller]")
@click.option("--length",
              default=t.LENGTH,
              help="The size of the payload in bytes")
@click.option("--executor",
              default=t.EXECUTOR,
              type=click.Choice(["eventlet", "threading"]),
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
@click.option("--env",
              default=None,
              help="Use this environment directory instead of the default one")
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


@cli.command(help="Performs tests according to the (swept) parameters described in configuration")
@click.argument('broker')
@click.option("--provider",
              default="vagrant",
              help="Deploy with the given provider")
@click.option("--force",
              is_flag=True,
              help="force redeploy")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="Configuration file to use")
@click.option("--test",
              default="test_case_1",
              help="Launch a test campaign given a test")
@click.option("--env",
              default=None,
              help="Use this environment directory instead of the default one")
def campaign(broker, force, provider, conf, test, env):
    c.campaign(broker=broker,
               provider=provider,
               force=force,
               conf=conf,
               test=test,
               env=env)


if __name__ == "__main__":
    cli()
