#!/usr/bin/env python

import logging
import os

import click
import yaml

import campaign as c
import tasks as t

logging.basicConfig(level=logging.DEBUG)

DEFAULT_CONF = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CONF = os.path.join(DEFAULT_CONF, "conf.yaml")
PROVIDERS = {
    "g5k": t.g5k,
    "vagrant": t.vagrant,
    "chameleon": t.chameleon
}


def load_config(path):
    """
    Read configuration from a file in YAML format.
    :param path: Path of the configuration file.
    :return:
    """
    with open(path) as f:
        configuration = yaml.safe_load(f)
    return configuration


# cli part
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
    config = load_config(conf)
    p = PROVIDERS[provider]
    p(broker=broker, force=force, config=config, env=env)
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


@cli.command(help="Runs the test case 1: one single large (distributed) target.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="Rpc_call (blocking) or rpc_cast (non blocking) [client] ")
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
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
def test_case_1(nbr_clients, nbr_servers, call_type, nbr_calls, pause, timeout, version, length, executor):
    t.test_case_1(nbr_clients=nbr_clients,
                  nbr_servers=nbr_servers,
                  call_type=call_type,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  version=version,
                  length=length,
                  executor=executor)


@cli.command(help="Runs the test case 2: multiple distributed targets")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="Number of topics that will set")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="Rpc_call (blocking) or rpc_cast (non blocking) [client] ")
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
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
def test_case_2(nbr_topics, call_type, nbr_calls, pause, timeout, version, length, executor):
    t.test_case_2(nbr_topics=nbr_topics,
                  call_type=call_type,
                  nbr_calls=nbr_calls,
                  pause=pause,
                  timeout=timeout,
                  version=version,
                  length=length,
                  executor=executor)


#TODO check cli for tc3
@cli.command(help="Runs the test case 1: one single large (distributed) target.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="Rpc_call (blocking) or rpc_cast (non blocking) [client] ")
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
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
def test_case_3(nbr_clients, nbr_servers, call_type, nbr_calls, pause, timeout, version, length, executor):
    t.test_case(nbr_clients=nbr_clients,
                nbr_servers=nbr_servers,
                nbr_topics=1,
                call_type=call_type,
                nbr_calls=nbr_calls,
                pause=pause,
                timeout=timeout,
                version=version,
                length=length,
                executor=executor)


@cli.command(help="Runs the test case 1: one single large (distributed) target.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will be deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will be deployed")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="Number of topics that will set")
@click.option("--call_type",
              default=t.CALL_TYPE,
              type=click.Choice(["rpc-call", "rpc-cast", "rpc-fanout"]),
              help="Rpc_call (blocking) or rpc_cast (non blocking) [client] ")
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
              help="type of executor the server will use")
@click.option("--version",
              default=t.VERSION,
              help="Version of ombt to use as a docker tag (will use beyondtheclouds:'vesion')")
def test_case_4(nbr_clients, nbr_servers, nbr_topics, call_type, nbr_calls, pause, timeout, version, length, executor):
    t.test_case(nbr_clients=nbr_clients, # actually clients = clients*topics
                nbr_servers=nbr_servers, # actually servers = servers*topics
                nbr_topics=nbr_topics,
                call_type=call_type,
                nbr_calls=nbr_calls,
                pause=pause,
                timeout=timeout,
                version=version,
                length=length,
                executor=executor)


@cli.command()
@click.argument('broker')
@click.option("--provider",
              default="vagrant",
              help="Deploy with the given provider")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="Configuration file to use")
@click.option("--test",
              default="test_case_1",
              help="Launch a test campaign given a test")
@click.option("--env",
              help="Use this environment directory instead of the default one")
def campaign(broker, provider, conf, test, env):
    c.campaign(broker=broker,
               provider=provider,
               conf=conf,
               test=test,
               env=env)


if __name__ == "__main__":
    cli()
