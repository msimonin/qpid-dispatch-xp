#!/usr/bin/env python
import click
from execo_engine import sweep, ParamSweeper
import logging
import os
import tasks as t
import yaml
import json

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
    with open(path) as file:
        configuration = yaml.safe_load(file)
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


@cli.command(help="Configure the resources.[after g5k,vagrant and inventory]")
def prepare():
    t.prepare()


@cli.command(help="Runs the test case 1: one single large (distributed) target.")
@click.option("--nbr_clients",
              default=t.NBR_CLIENTS,
              help="Number of clients that will de deployed")
@click.option("--nbr_servers",
              default=t.NBR_SERVERS,
              help="Number of servers that will de deployed")
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


@cli.command(help="Runs the test case 2: multiple distributed targets.")
@click.option("--nbr_topics",
              default=t.NBR_TOPICS,
              help="Number of topics (according to ombt) that will de deployed")
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


@cli.command(help="Destroy all the running dockers (not destroying the resources)")
def destroy():
    t.destroy()


@cli.command(help="Backup the environment")
def backup():
    t.backup()


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

    def generate_id(params):
        def clean(s):
            return str(s).replace("/", "_sl_") \
                .replace(":", "_sc_")

        return "-".join([
            "%s__%s" % (clean(k), clean(v)) for k, v in sorted(params.items())
        ])

    def accept(params):
        call_ratio_max = 3
        cast_ratio_max = 3
        call_type = params["call_type"]
        if params["nbr_servers"] > params["nbr_clients"]:
            return False
        if call_type == "rpc-call":
            if not params["pause"]:
                # maximum rate
                return call_ratio_max * params["nbr_servers"] >= params["nbr_clients"]
            else:
                # we can afford more clients
                # based on our estimation a client sends 200msgs at full rate
                return call_ratio_max * params["nbr_servers"] >= params["nbr_clients"] * 200 * params["pause"]
        else:
            if not params["pause"]:
                # maximum rate
                return cast_ratio_max * params["nbr_servers"] >= params["nbr_clients"]
            else:
                # we can afford more clients
                # based on our estimation a client sends 200msgs at full rate
                return cast_ratio_max * params["nbr_servers"] >= params["nbr_clients"] * 1000 * params["pause"]

    # Function to pass in parameter to ParamSweeper.get_next()
    # Give the illusion that the Set of params is sorted by nbr_clients
    def sort_params_by_nbr_clients(set):
        return sorted((list(set)), key=lambda k: k['nbr_clients'])

    # Dump each params in the backup dir
    def dump_param(params):
        if not os.path.exists("%s/params.json" % test):
            with open("%s/params.json" % test, 'w') as outfile:
                json.dump([], outfile)
        # Add the current params to the json
        with open("%s/params.json" % test, 'r') as outfile:
            all_params = json.load(outfile)
        all_params.append(params)
        with open("%s/params.json" % test, 'w') as outfile:
            json.dump(all_params, outfile)

    config = load_config(conf)
    parameters = config["campaign"][test]

    sweeps = sweep(parameters)
    filtered_sweeps = [param for param in sweeps if accept(param)]
    sweeper = ParamSweeper(
        # Maybe puts the sweeper under the experimentation directory
        # This should be current/sweeps
        persistence_dir=os.path.join("%s/sweeps" % test),
        sweeps=filtered_sweeps,
        save_sweeps=True,
        name=test
    )
    params = sweeper.get_next(sort_params_by_nbr_clients)
    PROVIDERS[provider](broker=broker, config=config, env=test)
    t.inventory()

    while params:
        params.pop("backup_dir", None)
        params.update({"backup_dir": generate_id(params)})
        t.prepare(broker=broker)
        t.test_case_1(**params)
        sweeper.done(params)
        dump_param(params)
        params = sweeper.get_next(sort_params_by_nbr_clients)
        t.destroy()


if __name__ == "__main__":
    cli()
