from enoslib.api import run_command, run_ansible, generate_inventory, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from qpid_generator.graph import generate
from qpid_generator.distribute import round_robin
from qpid_generator.configurations import get_conf
from utils.roles import to_enos_roles

import os
import yaml

GRAPH_TYPE="complete_graph"
GRAPH_ARGS=[5]
BROKER="qpidd"

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["router-client", "router-server"]
}


# The two following tasks are exclusive either you choose to go with g5k or
# vagrant you can't mix the two of them in the future we might want to
# factorize it and have a switch on the command line to choose.
@enostask(new=True)
def g5k(env=None, broker=BROKER, force=False, **kwargs):
    with open("confs/g5k-%s.yaml" % broker) as f:
        g5k_config = yaml.load(f)
        provider = G5k(g5k_config)
        roles, networks = provider.init(force_deploy=force)
        env["roles"] = roles
        env["networks"] = networks


@enostask(new=True)
def vagrant(env=None, broker=BROKER, force=False, **kwargs):
    with open("confs/vagrant-%s.yaml" % broker) as f:
        vagrant_config = yaml.load(f)
        provider = Enos_vagrant(vagrant_config)
        roles, networks = provider.init(force_deploy=force)
        # saving the roles
        env["roles"] = roles
        env["networks"] = networks


@enostask()
def inventory(env=None, **kwargs):
    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = os.path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"] , check_networks=True)


@enostask()
def prepare(env=None, broker=BROKER, **kwargs):
    # Generate inventory
    extra_vars = {
        "registry": {
            "type": "internal"
        },
        "broker": broker
    }
    # Preparing the installation of the bus under evaluation
    # Need to pass specific options
    if broker == "rabbitmq":
        # Nothing to do
        pass
    elif broker == "qpidd":
        # Building the graph of routers
        roles = env["roles"]
        machines = [desc.alias for desc in roles["router"]]
        graph = generate(GRAPH_TYPE, *GRAPH_ARGS)
        confs = get_conf(graph, machines, round_robin)
        qpidd_confs = {"qpidd_confs": confs.values()}
        extra_vars.update(qpidd_confs)
        env.update(qpidd_confs)
    else:
        raise Exception("Unknown broker chosen")

    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})

    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)
    env["broker"] = broker


@enostask()
def test_case_1(nbr_clients, nbr_servers, call_type, nbr_calls, delay, env=None, **kwargs):
    # (avk) ombt needs queue addresses starting with the right transport protocol, (i.e. --url rabbit://<IP> for rabbitmq,  or --url amqp://<IP> for qpidd)
    print("Test-case1 deployment")
    #run_ansible(["ansible/ombt.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/ombt.yml"], env["inventory"], {"broker": env["broker"], "nbr_clients": nbr_clients, "ombt_args": "rpc-client", "enos_action": "deploy"})
    run_ansible(["ansible/ombt.yml"], env["inventory"], {"broker": env["broker"], "nbr_servers": nbr_servers, "ombt_args": "rpc-server", "enos_action": "deploy"})
    run_ansible(["ansible/ombt.yml"], env["inventory"], {"broker": env["broker"], "ombt_args": "controller",
                                                         "call_type": call_type,
                                                         "nbr_calls": nbr_calls,
                                                         "pause": delay,
                                                         "enos_action": "deploy"})

    output = run_command("ombt-control", "docker logs ombt-controller", env["inventory"])
    print(output["ok"]["enos-3"]["stdout"])

@enostask()
def emulate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    emulate_network(roles, inventory, tc)


@enostask()
def validate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    validate_network(roles, inventory)


@enostask()
def backup(env=None, **kwargs):
    extra_vars = {
        "enos_action": "backup",
        "backup_dir": os.path.join(os.getcwd(), "current")
    }
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)


@enostask()
def destroy(env=None, **kwargs):
    extra_vars = {}
    # Call destroy on each component
    extra_vars.update({
        "enos_action": "destroy",
        "broker": env["broker"],

    })
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/ombt.yml"], env["inventory"], extra_vars=extra_vars)

