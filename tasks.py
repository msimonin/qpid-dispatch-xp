from abc import ABCMeta, abstractmethod
from enoslib.api import run_ansible, generate_inventory, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from qpid_generator.graph import generate
from qpid_generator.distribute import round_robin
from qpid_generator.configurations import get_conf

import os
import yaml

BROKER = "qdr"

# DEFAULT PARAMETERS
NBR_CLIENTS = 1
NBR_SERVERS = 1
NBR_TOPICS = 1
CALL_TYPE = "rpc-call"
NBR_CALLS = "100"
PAUSE = 0
TIMEOUT = 60
VERSION = "beyondtheclouds/ombt:latest"
BACKUP_DIR = "backup"
LENGTH = "1024"
EXECUTOR = "threading"

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}


class BusConf(object):
    """Common class to modelize bus configuration"""

    __metaclass__ = ABCMeta

    def __init__(self, conf):
        self.conf = conf
        self.transport = self.get_transport()

    @abstractmethod
    def get_listener(self, conf):
        pass

    @abstractmethod
    def get_transport(self):
        pass

    def to_dict(self):
        return self.conf


class RabbitMQConf(BusConf):

    def __init__(self, conf):
        super(RabbitMQConf, self).__init__(conf)

    def get_listener(self, **kwargs):
        """Returns the listener for rabbitmq.
        :param kwargs:
        """
        return {
            "machine": self.conf["machine"],
            "port": self.conf["port"]
        }

    def get_transport(self):
        return "rabbit"


class QdrConf(BusConf):

    def __init__(self, conf):
        super(QdrConf, self).__init__(conf)
        self.transport = "amqp"

    def get_listener(self, **kwargs):
        """Returns the listener for qdr.

        This is where external client can connect to.
        The contract is that this kind of listener has the role "normal"
        and there is exactly one such listener per router
        :param kwargs:
        """
        listeners = self.conf["listeners"]
        listener = [l for l in listeners if l["role"] == "normal"]
        return {
            "machine": listener[0]["host"],
            "port": listener[0]["port"]

        }

    def get_transport(self):
        return "amqp"


class OmbtAgent(object):
    """Modelize an ombt agent"""

    __metaclass__ = ABCMeta

    def __init__(self, **kwargs):
        # NOTE(msimonin): maybe use __getattr__ at some point
        self.agent_id = kwargs["agent_id"]
        self.machine = kwargs["machine"]
        self.control_agents = kwargs["control_agents"]
        self.bus_agents = kwargs["bus_agents"]
        self.timeout = kwargs["timeout"]
        # generated
        self.agent_type = self.get_type()
        # docker
        self.detach = True
        self.topic = kwargs["topic"]
        # calculated attr
        self.name = self.agent_id
        # where to log inside the container
        self.docker_log = "/home/ombt/ombt-data/agent.log"
        # where to log outside the container (mount)
        self.log = os.path.join("/tmp/ombt-data", "%s.log" % self.agent_id)
        # the command to run
        self.command = self.get_command()

    def to_dict(self):
        d = self.__dict__
        d.update({
            "control_agents": [a.to_dict() for a in self.control_agents],
            "bus_agents": [a.to_dict() for a in self.bus_agents],
        })
        return d

    @abstractmethod
    def get_type(self):
        pass

    def generate_connections(self):
        connections = {}
        for agents, agent_type in zip([self.control_agents, self.bus_agents], ["control", "url"]):
            connection = []
            for agent in agents:
                listener = agent.get_listener()
                transport = agent.transport
                connection.append("{{ hostvars['%s']['ansible_' + control_network]['ipv4']['address'] }}:%s" %
                                  (listener["machine"], listener["port"]))
            connections[agent_type] = "%s://%s" % (transport, ",".join(connection))
        return "--control %s --url %s" % (connections["control"], connections["url"])

    def get_command(self):
        """Build the command for the ombt agent."""
        command = []
        command.append("--timeout %s " % self.timeout)
        command.append("--topic %s " % self.topic)
        command.append(self.generate_connections())
        command.append(self.get_type())
        # NOTE(msimonin): we don't use verbosity for client/server
        # if self.verbose:
        #    command.append("--output %s " % self.docker_log)
        return command


class OmbtClient(OmbtAgent):

    def get_type(self):
        return "rpc-client"


class OmbtServer(OmbtAgent):

    def __init__(self, **kwargs):
        self.executor = kwargs["executor"]
        super(OmbtServer, self).__init__(**kwargs)

    def get_command(self):
        """Build the command for the ombt server"""
        command = super(OmbtServer, self).get_command()
        command.append("--executor %s" % self.executor)
        return command

    def get_type(self):
        return "rpc-server"


class OmbtController(OmbtAgent):

    def __init__(self, **kwargs):
        self.timeout = kwargs["timeout"]
        self.call_type = kwargs["call_type"]
        self.nbr_calls = kwargs["nbr_calls"]
        self.pause = kwargs["pause"]
        self.length = kwargs["length"]
        super(OmbtController, self).__init__(**kwargs)
        # that smells a bit
        self.detach = False

    def get_type(self):
        return "controller"

    def get_command(self):
        """Build the command for the ombt controller"""
        command = super(OmbtController, self).get_command()
        # We always dump stat per agents
        command.append("--output %s" % self.docker_log)
        command.append(self.call_type)
        command.append("--calls %s" % self.nbr_calls)
        command.append("--pause %s" % self.pause)
        command.append("--length %s" % self.length)
        return " ".join(command)


def get_current_directory(filename='current'):
    cwd = os.getcwd()
    return os.path.join(cwd, filename)


def get_topics(number):
    """Create a list of topic names.

    The names have the following format: topic_<id>. Where the id is a normalized number preceded by leading zeros.
    >>> get_topics(1)
    ['topic_1']
    >>> get_topics(10)
    ['topic_01', 'topic_02', 'topic_03', 'topic_04', 'topic_05', 'topic_06', 'topic_07', 'topic_08', 'topic_09', 'topic_10']
    """
    size = len(str(number))
    sequence = ('{number:0{width}}'.format(number=n+1, width=size) for n in range(number))
    return ['topic_' + e for e in sequence]


# The two following tasks are exclusive either you choose to go with g5k or
# vagrant you can't mix the two of them in the future we might want to
# factorize it and have a switch on the command line to choose.
@enostask(new=True)
def g5k(env=None, broker=BROKER, force=False, config=None, **kwargs):
    provider = G5k(config["g5k"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks


@enostask(new=True)
def vagrant(env=None, broker=BROKER, force=False, config=None, **kwargs):
    provider = Enos_vagrant(config["vagrant"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks


@enostask(new=True)
def chameleon(env=None, broker=BROKER, force=False, config=None, **kwargs):
    provider = Chameleonkvm(config["chameleon"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks


@enostask()
def inventory(env=None, **kwargs):
    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = os.path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"], check_networks=True)


@enostask()
def prepare(env=None, broker=BROKER, **kwargs):
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "broker": broker
    }
    # Preparing the installation of the bus under evaluation
    # Need to pass specific options
    # We generate a configuration dict that captures the minimal set of
    # parameters of each agents of the bus
    # This configuration dict is used in subsequent test* tasks to configure the
    # ombt agents.
    roles = env["roles"]
    machines = [desc.alias for desc in roles["bus"]]
    # Get the specific configuration from the file
    config = env["config"][broker]

    if broker == "rabbitmq":
        # NOTE(msimonin): generate the configuration for rabbitmq
        # Assuming only one node for now
        bus_conf = [{
            "port": 5672,
            "management_port": 15672,
            "machine": machines[0]
        }]
        # saving the conf object
        env.update({"bus_conf": [RabbitMQConf(c) for c in bus_conf]})
        # but passing its serialization to ansible
        ansible_bus_conf = {"bus_conf": bus_conf}
    elif broker == "qdr":
        # Building the graph of routers
        graph = generate(config["type"], *config["args"])
        bus_conf = get_conf(graph, machines, round_robin)
        env.update({"bus_conf": [QdrConf(c) for c in bus_conf.values()]})
        ansible_bus_conf = {"bus_conf": list(bus_conf.values())}
    else:
        raise Exception("Unknown broker chosen")

    # Let's do the same for the control bus
    machines = [desc.alias for desc in roles["control-bus"]]
    control_bus_conf = [{
        "port": 5672,
        "management_port": 15672,
        "machine": machines[0]
    }]
    env.update({"control_bus_conf": [RabbitMQConf(c) for c in control_bus_conf]})
    ansible_control_bus_conf = {"control_bus_conf": control_bus_conf}

    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    extra_vars.update(ansible_bus_conf)
    extra_vars.update(ansible_control_bus_conf)

    # Finally let's give ansible the bus_conf
    if config:
        extra_vars.update(config)

    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)
    env["broker"] = broker


@enostask()
def test_case_1(
        nbr_clients=NBR_CLIENTS,
        nbr_servers=NBR_SERVERS,
        nbr_topics=NBR_TOPICS,
        call_type=CALL_TYPE,
        nbr_calls=NBR_CALLS,
        pause=PAUSE,
        timeout=TIMEOUT,
        version=VERSION,
        backup_dir=BACKUP_DIR,
        length=LENGTH,
        executor=EXECUTOR,
        env=None, **kwargs):
    iteration_id = str("-".join([
        "nbr_servers__%s" % nbr_servers,
        "nbr_clients__%s" % nbr_clients,
        "nbr_topics__%s" % nbr_topics,
        "call_type__%s" % call_type,
        "nbr_calls__%s" % nbr_calls,
        "pause__%s" % pause]))

    # Create the backup dir for this experiment
    # NOTE(msimonin): We don't need to identify the backup dir we could use a
    # dedicated env name for that
    backup_dir = os.path.join(os.getcwd(), "current/%s" % backup_dir)
    os.system("mkdir -p %s" % backup_dir)
    extra_vars = {
        "backup_dir": backup_dir,
        "ombt_version": version,
    }

    topics = get_topics(nbr_topics)

    descs = [
        {
            "agent_type": "rpc-client",
            "number": int(nbr_clients),
            "machines": env["roles"]["ombt-client"],
            "klass": OmbtClient,
            "kwargs": {
                "timeout": timeout,
                "topic": "topic"
            }
        },
        {
            "agent_type": "rpc-server",
            "number": int(nbr_servers),
            "machines": env["roles"]["ombt-server"],
            "klass": OmbtServer,
            "kwargs": {
                "timeout": timeout,
                "executor": executor,
                "topic": "topic"
            }
        },
        {
            "agent_type": "controller",
            "number": 1,
            "machines": env["roles"]["ombt-control"],
            "klass": OmbtController,
            "kwargs": {
                "call_type": call_type,
                "nbr_calls": nbr_calls,
                "pause": pause,
                "timeout": timeout,
                "length": length,
                "topic": "topic"
            }
        }]
    # Below we build the specific variables for each client/server
    # ombt_conf = {
    #   "machine01": [confs],
    # ...
    #
    # }
    ombt_confs = {}
    bus_conf = env["bus_conf"]
    control_bus_conf = env["control_bus_conf"]
    for agent_desc in descs:
        machines = agent_desc["machines"]
        # make sure all the machines appears in the ombt_confs
        for machine in machines:
            ombt_confs.setdefault(machine.alias, [])
        for agent_index in range(agent_desc["number"]):
            agent_id = "%s-%s-%s" % (agent_desc["agent_type"], agent_index, iteration_id)
            # choose a machine
            machine = machines[agent_index % len(machines)].alias
            # choose a bus agent
            bus_agent = bus_conf[agent_index % len(bus_conf)]
            # choose a topic
            topic = topics[agent_index % len(topics)]
            control_agent = control_bus_conf[agent_index % len(control_bus_conf)]
            kwargs = agent_desc["kwargs"]
            kwargs.update({
                "agent_id": agent_id,
                "machine": machine,
                "bus_agents": [bus_agent],
                "topic": topic,
                "control_agents": [control_agent]  # TODO
            })
            ombt_confs[machine].append(agent_desc["klass"](**kwargs))

    ansible_ombt_confs = {}
    for m, confs in ombt_confs.items():
        ansible_ombt_confs[m] = [o.to_dict() for o in confs]

    extra_vars.update({'ombt_confs': ansible_ombt_confs})
    run_ansible(["ansible/test_case_1.yml"], env["inventory"], extra_vars=extra_vars)
    # saving the conf
    env["ombt_confs"] = ombt_confs


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
        "backup_dir": get_current_directory()
    }
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)


@enostask()
def destroy(env=None, **kwargs):
    extra_vars = {}
    # Call destroy on each component
    extra_vars.update({
        "enos_action": "destroy",
        "broker": env["broker"],
        "bus_conf": [o.to_dict() for o in env.get("bus_conf")]
    })
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/ombt.yml"], env["inventory"], extra_vars=extra_vars)
