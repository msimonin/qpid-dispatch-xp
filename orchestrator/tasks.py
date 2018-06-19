import itertools
import json
import os
import pathlib
import uuid
from os import path

from enoslib.api import run_ansible, generate_inventory, emulate_network, \
    validate_network, reset_network
# NOTE()msimonin) dropping the chameleon support temporary
# from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.task import enostask

from orchestrator.constants import BACKUP_DIR, ANSIBLE_DIR, DRIVER, VERSION, MODE
from orchestrator.ombt import OmbtClient, OmbtController, OmbtServer, \
    RabbitMQConf, QdrConf
from orchestrator.qpid_dispatchgen import get_conf, generate, round_robin


def shard_value(value, shards, include_zero=False):
    """Shard a value in multiple values.

    >>> shard_value(10, 2)
    [5, 5]
    >>> shard_value(10, 3)
    [4, 3, 3]
    >>> shard_value(5, 10, include_zero=True)
    [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    >>> shard_value(5, 10, include_zero=False)
    [1, 1, 1, 1, 1]

    :param value: The value to shard
    :param shards: The number of shards
    :param include_zero:
    """
    q = [value // shards] * shards
    for i in range(value % shards):
        q[i] = q[i] + 1

    if not include_zero:
        q = [qq for qq in q if qq != 0]

    return q


def shard_list(l, shards, include_empty=False):
    """Shard a list in multiple sub-list.

    >>> shard_list([1, 2, 3, 4], 2)
    [[1, 3], [2, 4]]
    >>> shard_list([1, 2, 3, 4], 3)
    [[1, 4], [2], [3]]
    >>> shard_list([1], 3, include_empty=True)
    [[1], [], []]
    >>> shard_list([1], 3, include_empty=False)
    [[1]]

    :param l: The list to shard
    :param shards: The number of shards
    :param include_empty:
    """
    s_list = [l[i::shards] for i in range(shards) if i < len(l)]
    if include_empty:
        # We add the missing pieces
        empty = itertools.repeat([], shards - len(s_list))
        s_list.extend(empty)

    return s_list


def merge_ombt_confs(ombt_confs, ombt_conf):
    """Merge an ombt_conf (of one shard) to the global ombt_confs (of all shards).

    >>> ombt_confs = {'rpc-client': {'machine01': [1]}}
    >>> ombt_conf = {'rpc-client': {'machine01': [2]}}
    >>> merge_ombt_confs(ombt_confs, ombt_conf)
    {'rpc-client': {'machine01': [1, 2]}}

    >>> ombt_confs = {}
    >>> ombt_conf = {'rpc-client': {'machine01': [2]}}
    >>> merge_ombt_confs(ombt_confs, ombt_conf)
    {'rpc-client': {'machine01': [2]}}

    >>> import pprint
    >>> ombt_confs = {'rpc-client': {'machine01': [1]}}
    >>> ombt_conf = {'rpc-client': {'machine02': [2]}}
    >>> pprint.pprint(merge_ombt_confs(ombt_confs, ombt_conf))
    {'rpc-client': {'machine01': [1], 'machine02': [2]}}
    """
    for agent_type, machines in ombt_conf.items():
        if agent_type not in ombt_confs:
            ombt_confs.update({agent_type: machines})
            continue

        confs = ombt_confs[agent_type]
        for machine, conf in machines.items():
            if machine not in confs:
                confs.update({machine: conf})
                continue

            confs[machine].extend(conf)

    return ombt_confs


def get_topics(number):
    """Create a list of topic names.

    The names have the following format: topic_<id>. Where the id is a
    normalized number preceded by leading zeros.

    >>> get_topics(1)
    ['topic-0']
    >>> get_topics(2)
    ['topic-0', 'topic-1']
    >>> get_topics(0)
    []
    >>> get_topics(10) # doctest: +ELLIPSIS
    ['topic-0', 'topic-1', 'topic-2', 'topic-3', ..., 'topic-8', 'topic-9']
    >>> get_topics(11) # doctest: +ELLIPSIS
    ['topic-00', 'topic-01', 'topic-02', 'topic-03', ..., 'topic-09', 'topic-10']
    >>> get_topics(1000) # doctest: +ELLIPSIS
    ['topic-000', 'topic-001', 'topic-002', 'topic-003', ..., 'topic-999']

    :param number: Number of topic names to generate.
    :return: A list of topic names.
    """
    length = len(str(number)) if number % 10 else len(str(number)) - 1
    sequence = ("{number:0{width}}".format(number=n, width=length)
                for n in range(number))
    return ["topic-{}".format(e) for e in sequence]


def generate_ansible_conf(key, bus_conf, configuration=None):
    ansible_conf = {key: [b.to_dict() for b in bus_conf]}
    # inject the bus configuration taken from the configuration
    if configuration:
        ansible_conf.update(configuration)

    return ansible_conf


def get_backup_directory(backup_dir):
    cwd = os.getcwd()
    # current directory name is constant because of enoslib implementation
    current_directory = path.join(cwd, "current")
    backup_dir = path.join(current_directory, backup_dir)
    pathlib.Path(backup_dir).mkdir(parents=True, exist_ok=True)
    return backup_dir


# g5k and vagrant are mutually exclusive, in the future we might want
# to factorize it and have a switch on the command line to choose.
@enostask(new=True)
def g5k(**kwargs):
    # Here **kwargs strictly means (force, config, env), no more no less
    init_provider(G5k, "g5k", **kwargs)


@enostask(new=True)
def vagrant(**kwargs):
    # Here **kwargs strictly means (force, config, env), no more no less
    init_provider(Enos_vagrant, "vagrant", **kwargs)


@enostask(new=True)
def static(**kwargs):
    # Here **kwargs strictly means (force, config, env), no more no less
    init_provider(Static, "static", **kwargs)

# @enostask(new=True)
#def chameleon(**kwargs):
#    # Here **kwargs strictly means (force, config, env), no more no less
#    init_provider(Chameleonkvm, "chameleon", **kwargs)


def init_provider(provider, name, force, config, env):
    instance = provider(config[name])
    roles, networks = instance.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks


PROVIDERS = {
    "g5k": g5k,
    "vagrant": vagrant,
    "static": static
#    "chameleon": chameleon
}


@enostask()
def inventory(**kwargs):
    env = kwargs["env"]
    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"], check_networks=True)


def generate_bus_conf(config, role_machines, context=""):
    """Generate the bus configuration.

    Args:
        config(dict): Configuration of the bus (Mostly extracted from the global config)
        role_machines(list): machines on which the bus agents will be installed
        context:

    Returns:
        List of configurations to use for each machine.
    """
    machines = [desc.alias for desc in role_machines]
    if config["type"] == "rabbitmq":
        # To pack several rabbit agent on the same node we follow
        # https://www.rabbitmq.com/clustering.html#single-machine
        number = config.get("number", len(role_machines))
        # Distributing the rabbitmq instances
        bus_conf = [{
            "agent_id": "rabbitmq-%s-%s" % (context, index),
            "port": 5672 + index,
            "management_port": 15672 + index,
            "machine": machines[index % len(machines)]
        } for index in range(number)]
        # We inject the cluster nodes
        cluster_nodes = []
        mode = config.get("mode", MODE)
        if mode == "cluster":
            cluster_nodes = [(b["agent_id"], b["machine"]) for b in bus_conf]

        for b in bus_conf:
            b["cluster_nodes"] = cluster_nodes

        # saving the conf object
        bus_conf = [RabbitMQConf(c) for c in bus_conf]

    elif config["type"] == "qdr":
        # Building the graph of routers
        graph = generate(config["topology"], *config["args"])
        bus_conf = get_conf(graph, machines, round_robin)
        bus_conf = [QdrConf(c) for c in bus_conf.values()]

    else:
        raise TypeError("Unknown broker chosen")

    return bus_conf


@enostask()
def prepare(**kwargs):
    env = kwargs["env"]
    driver = kwargs["driver"]
    # Generate inventory
    config = env["config"]["drivers"].get(driver, DRIVER)
    extra_vars = {
        "registry": env["config"]["registry"],
        "broker": config["type"]
    }

    # Preparing the installation of the bus under evaluation. Need to pass
    # specific options. We generate a configuration dict that captures the
    # minimal set of parameters of each agents of the bus. This configuration
    # dict is used in subsequent test* tasks to configure the ombt agents.
    bus_conf = generate_bus_conf(config, env["roles"]["bus"], context="bus")
    env["bus_conf"] = bus_conf
    ansible_bus_conf = generate_ansible_conf("bus_conf", bus_conf, config)

    # NOTE(msimonin): still hardcoding the control_bus configuration for now
    control_config = DRIVER
    control_bus_conf = generate_bus_conf(control_config,
                                         env["roles"]["control-bus"],
                                         context="control-bus")
    env["control_bus_conf"] = control_bus_conf
    ansible_control_bus_conf = generate_ansible_conf("control_bus_conf",
                                                     control_bus_conf, config)

    extra_vars.update({"enos_action": "deploy"})
    extra_vars.update(ansible_bus_conf)
    extra_vars.update(ansible_control_bus_conf)

    run_ansible([path.join(ANSIBLE_DIR, "site.yml")],
                env["inventory"], extra_vars=extra_vars)
    # broker is a ansible-required variable
    env["broker"] = config["type"]


@enostask()
def test_case_1(**kwargs):
    if "iteration_id" not in kwargs:
        kwargs["iteration_id"] = uuid.uuid4()

    if "topics" not in kwargs:
        kwargs["topics"] = get_topics(1)

    # Sharding
    # Here it means we distribute the clients and servers
    # accross the different available shards
    env = kwargs["env"]
    shards = len(env["control_bus_conf"])
    ombt_confs = {}
    s_clients = shard_value(kwargs["nbr_clients"], shards, include_zero=True)
    s_servers = shard_value(kwargs["nbr_servers"], shards, include_zero=True)
    for shard_index, s_client, s_server in zip(range(shards), s_clients, s_servers):
        if not s_clients and not s_servers:
            # no need to start a single controller to control nothing
            continue

        # NOTE(msimonin): one corner case would be if s_clients = 0
        # and s_servers = 0. This would prevent ombt-controller to function normally
        # but is unlikely to happen since nbr_clients >= nbr_servers
        kwargs["nbr_clients"] = s_client
        kwargs["nbr_servers"] = s_server
        ombt_conf = generate_shard_conf(
            shard_index,
            sum(s_servers[0:shard_index]),
            sum(s_clients[0:shard_index]),
            **kwargs)
        merge_ombt_confs(ombt_confs, ombt_conf)

    test_case(ombt_confs, **kwargs)


@enostask()
def test_case_2(**kwargs):
    if "iteration_id" not in kwargs:
        kwargs["iteration_id"] = uuid.uuid4()

    if "topics" not in kwargs:
        nbr_topics = kwargs["nbr_topics"]
        kwargs["topics"] = get_topics(nbr_topics)

    topics = kwargs["topics"]
    # Sharding
    # Here it means we distribute the topics
    # accross the different available shards
    env = kwargs["env"]
    shards = len(env["control_bus_conf"])
    # NOTE(msimonin): No topic means no client and no servers
    # Thus no test
    s_topics = shard_list(topics, shards, include_empty=False)
    ombt_confs = {}
    for shard_index, s_topic in zip(range(shards), s_topics):
        kwargs["nbr_clients"] = len(s_topic)
        kwargs["nbr_servers"] = len(s_topic)
        kwargs["topics"] = s_topic
        ombt_conf = generate_shard_conf(
            shard_index,
            len(s_topic[0:shard_index]),
            len(s_topic[0:shard_index]),
            **kwargs)
        merge_ombt_confs(ombt_confs, ombt_conf)

    test_case(ombt_confs, **kwargs)


@enostask()
def test_case_3(**kwargs):
    if "iteration_id" not in kwargs:
        kwargs["iteration_id"] = uuid.uuid4()

    if "topics" not in kwargs:
        kwargs["topics"] = get_topics(1)

    kwargs["call_type"] = "rpc-fanout"
    # Sharding
    # We need to replicate the client on every controller
    env = kwargs["env"]
    shards = len(env["control_bus_conf"])
    s_servers = shard_value(kwargs["nbr_servers"], shards, include_zero=False)
    ombt_confs = {}
    for shard_index, s_server in zip(range(shards), s_servers):
        # kwargs["nbr_clients"] = 1
        kwargs["nbr_servers"] = s_server
        ombt_conf = generate_shard_conf(
            shard_index,
            sum(s_server[0:shard_index]),
            shard_index,
            **kwargs)
        merge_ombt_confs(ombt_confs, ombt_conf)

    test_case(ombt_confs, **kwargs)


@enostask()
def test_case_4(**kwargs):
    if "iteration_id" not in kwargs:
        kwargs["iteration_id"] = uuid.uuid4()

    kwargs["call_type"] = "rpc-cast"
    if "topics" not in kwargs:
        nbr_topics = kwargs["nbr_topics"]
        kwargs["topics"] = get_topics(nbr_topics)

    topics = kwargs["topics"]
    # Sharding
    # We shard based on the topics.
    # So that a broadcast domains will belong to a single controller
    env = kwargs["env"]
    shards = len(env["control_bus_conf"])
    nbr_clients = kwargs["nbr_clients"]
    nbr_servers = kwargs["nbr_servers"]
    s_topics = shard_list(topics, shards, include_empty=False)
    ombt_confs = {}
    for shard_index, s_topic in zip(range(shards), s_topics):
        kwargs["nbr_clients"] = nbr_clients * len(s_topic)
        kwargs["nbr_servers"] = nbr_servers * len(s_topic)
        kwargs["topics"] = s_topic
        ombt_conf = generate_shard_conf(
            shard_index,
            len(s_topic[0:shard_index]) * nbr_servers,
            len(s_topic[0:shard_index]) * nbr_clients,
            **kwargs)
        merge_ombt_confs(ombt_confs, ombt_conf)

    test_case(ombt_confs, **kwargs)


def generate_shard_conf(shard_index_ctl, shard_index_server, shard_index_client,
                        nbr_clients, nbr_servers, call_type,
                        nbr_calls, pause, timeout, length, executor, env,
                        topics, iteration_id, **kwargs):
    """Generates the configuration of the agents of 1 shard (for 1 controller)."""
    # build the specific variables for each client/server:
    # ombt_conf = {
    #   "rpc-client": {
    #       "machine01": [confs],
    #        ...
    #   },
    #   "rpc-server": {
    #
    #   },
    #   "controller": {
    #
    #   }
    #   ...
    # }

    ombt_confs = {"rpc_client": {}, "rpc-server": {}, "controller": {}}
    if not topics:
        return ombt_confs

    bus_conf = env["bus_conf"]
    control_bus_conf = [env["control_bus_conf"][shard_index_ctl]]
    machine_client = env["roles"]["bus"]
    if "bus-client" in env["roles"]:
        machine_client = env["roles"]["bus-client"]

    machine_client = [m.alias for m in machine_client]
    machine_server = env["roles"]["bus"]
    if "bus-server" in env["roles"]:
        machine_server = env["roles"]["bus-server"]

    machine_server = [m.alias for m in machine_server]
    # description template of agents
    descs = [
        {
            "agent_type": "rpc-client",
            "number": nbr_clients,
            "machines": env["roles"]["ombt-client"],
            "bus_agents": [b for b in bus_conf
                           if b.get_listener()["machine"] in machine_client],
            "klass": OmbtClient,
            "kwargs": {
                "timeout": timeout,
            },
            "shard_index": shard_index_client,
        },
        {
            "agent_type": "rpc-server",
            "number": nbr_servers,
            "machines": env["roles"]["ombt-server"],
            "bus_agents": [b for b in bus_conf
                           if b.get_listener()["machine"] in machine_server],
            "klass": OmbtServer,
            "kwargs": {
                "timeout": timeout,
                "executor": executor,
            },
            "shard_index": shard_index_server,
        },
        {
            "agent_type": "controller",
            "number": 1,
            "machines": env["roles"]["ombt-control"],
            "bus_agents": bus_conf,
            "klass": OmbtController,
            "kwargs": {
                "call_type": call_type,
                "nbr_calls": nbr_calls,
                "pause": pause,
                "timeout": timeout,
                "length": length,
            },
            "shard_index": shard_index_ctl
        }]

    for agent_desc in descs:
        agent_type = agent_desc["agent_type"]
        machines = agent_desc["machines"]
        ombt_confs.setdefault(agent_type, {})
        shard_index = agent_desc["shard_index"]
        for agent_index in range(agent_desc["number"]):
            # Taking into account a shard index has several benefit:
            # first the distribution accross nodes or bus agent is more balanced
            # -> the first agents of to distinct shard doesn't land on the same node
            # second this provide some unicity for the agent_id
            #
            # Edit 04/29(msimonin)
            # considering the case where we have 10 machines, 4 shards, 20 servers to start
            # We'd like to have an homogeneous distribution
            # Without shard_index only the first 5 machines will get the servers
            # With shard_index:
            # - the first 5 machines will get 1 server each for the 1st shard (shard_index=0)
            # - the next 5 machines will get 1 server each for the 2nd shard (shard_index=5)
            # - the next 5 machines (= the first 5 machines) will get 1 more
            # server each (shard_index=10)
            # etc
            idx = agent_index + shard_index
            # choose a topic
            topic = topics[idx % len(topics)]
            # choose a machine
            machine = machines[idx % len(machines)].alias
            # choose a bus agent
            bus_agent = agent_desc["bus_agents"][idx % len(agent_desc["bus_agents"])]
            agent_id = "%s-%s-%s-%s-%s" % (agent_type, agent_index,
                                           topic, iteration_id, shard_index)
            control_agent = control_bus_conf[agent_index % len(control_bus_conf)]
            kwargs = agent_desc["kwargs"]
            kwargs.update({"agent_id": agent_id,
                           "machine": machine,
                           "bus_agents": [bus_agent],
                           "topic": topic,
                           "control_agents": [control_agent]})
            agent_conf = agent_desc["klass"](**kwargs)
            ombt_confs[agent_type].setdefault(machine, []).append(agent_conf)

    return ombt_confs


def test_case(ombt_confs, version=VERSION, env=None, backup_dir=BACKUP_DIR, **kwargs):

    def serialize_ombt_confs(_ombt_confs):
        ansible_ombt_confs = {}
        for agent_type, machines in _ombt_confs.items():
            ansible_ombt_confs.setdefault(agent_type, {})

            for machine, confs in machines.items():
                ansible_ombt_confs[agent_type].update(
                    {machine: [c.to_dict() for c in confs]})

        return ansible_ombt_confs

    backup_dir = get_backup_directory(backup_dir)
    extra_vars = {
        "backup_dir": backup_dir,
        # NOTE(msimonin): This could be moved in each conf
        "ombt_version": version,
        "broker": env["broker"],
        "ombt_confs": serialize_ombt_confs(ombt_confs)
    }

    run_ansible([path.join(ANSIBLE_DIR, "test_case.yml")],
                env["inventory"], extra_vars=extra_vars)


@enostask()
def emulate(**kwargs):
    env = kwargs.pop("env")
    configuration_name = kwargs.pop("configuration_name")
    network_constraints = env["config"]["traffic"].get(configuration_name)
    for name, value in kwargs.items():
        network_constraints[name] = value

    roles = env["roles"]
    _inventory = env["inventory"]
    emulate_network(roles, _inventory, network_constraints)


@enostask()
def validate(**kwargs):
    env = kwargs["env"]
    _inventory = env["inventory"]
    roles = env["roles"]
    directory = kwargs.get("directory", BACKUP_DIR)
    backup_dir = get_backup_directory(directory)
    validate_network(roles, _inventory, output_dir=backup_dir)


@enostask()
def reset(**kwargs):
    env = kwargs["env"]
    _inventory = env["inventory"]
    roles = env["roles"]
    reset_network(roles, _inventory)


@enostask()
def backup(**kwargs):
    env = kwargs["env"]
    backup_dir = kwargs["backup_dir"]
    backup_dir = get_backup_directory(backup_dir)
    extra_vars = {
        "enos_action": "backup",
        "backup_dir": backup_dir,
        # NOTE(msimonin): this broker variable should be renamed
        # This corresponds to driver.type, or maybe embed this in the bus conf
        "broker": env["broker"],
    }

    ansible_bus_conf = generate_ansible_conf("bus_conf", env.get("bus_conf"))
    ansible_control_bus_conf = generate_ansible_conf("control_bus_conf",
                                                     env.get("control_bus_conf"))
    extra_vars.update(ansible_bus_conf)
    extra_vars.update(ansible_control_bus_conf)
    run_ansible([path.join(ANSIBLE_DIR, "site.yml")],
                env["inventory"], extra_vars=extra_vars)


@enostask()
def destroy(**kwargs):
    env = kwargs["env"]
    # Call destroy on each component
    extra_vars = {
        "enos_action": "destroy",
        # NOTE(msimonin): this broker variable should be renamed
        # This corresponds to driver.type or maybe embed this in the bus_conf
        "broker": env["broker"]
    }

    ansible_bus_conf = generate_ansible_conf("bus_conf", env.get("bus_conf"))
    ansible_control_bus_conf = generate_ansible_conf("control_bus_conf",
                                                     env.get("control_bus_conf"))
    extra_vars.update(ansible_bus_conf)
    extra_vars.update(ansible_control_bus_conf)
    run_ansible([path.join(ANSIBLE_DIR, "site.yml")],
                env["inventory"], extra_vars=extra_vars)
    run_ansible([path.join(ANSIBLE_DIR, "ombt.yml")],
                env["inventory"], extra_vars=extra_vars)


@enostask()
def info(**kwargs):
    env = kwargs["env"]
    ansible_bus_conf = generate_ansible_conf("bus_conf", env.get("bus_conf"))
    print(json.dumps(ansible_bus_conf))
