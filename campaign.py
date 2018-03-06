from __future__ import print_function

import json
import operator
from os import path
import sys

from enoslib.errors import EnosError
from execo_engine import sweep, ParamSweeper

import tasks as t


def get_topics(number):
    """Create a list of topic names.

    The names have the following format: topic_<id>. Where the id is a normalized number preceded by leading zeros.

    >>> get_topics(1)
    ['topic-0']
    >>> get_topics(2)
    ['topic-0', 'topic-1']
    >>> get_topics(0)
    []
    >>> get_topics(10)
    ['topic-0', 'topic-1', 'topic-2', 'topic-3', 'topic-4', 'topic-5', 'topic-6', 'topic-7', 'topic-8', 'topic-9']
    >>> (get_topics(11)
    ['topic-00', 'topic-01', 'topic-02', 'topic-03', 'topic-04', 'topic-05', 'topic-06', 'topic-07', 'topic-08', 'topic-09', 'topic-10']

    :param number: Number of topic names to generate.
    :return: A list of topic names.
    """
    length = len(str(number)) if number % 10 else len(str(number)) - 1
    sequence = ('{number:0{width}}'.format(number=n, width=length) for n in range(number))
    return ['topic-' + e for e in sequence]


def filter_1(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] <= x['nbr_clients'])


def filter_2(parameters):
    return filter_params(parameters, key='nbr_topics')


def filter_3(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] >= x['nbr_clients'])


def filter_params(parameters, key='nbr_clients', condition=lambda unused: True):
    sorted_parameters = (p for p in parameters if condition(p))
    return sort_parameters(sorted_parameters, key)


def sort_parameters(parameters, key):
    # sort by 'driver' first, then by 'call type' and finally use the key
    # (i.e., group executions by driver-call_type and sort incrementally by key)
    return sorted(parameters, key=operator.itemgetter('driver', 'call_type', key))


def get_current_values(params, current, key):
    plist = params.get(key)
    state = current.get(key)
    index = plist.index(state)
    return (0, state) if index == 0 else (plist[index-1], state)


def fix_1(parameters, current_parameters):
    previous_clients, current_clients = get_current_values(parameters, current_parameters, 'nbr_clients')
    previous_servers, current_servers = get_current_values(parameters, current_parameters, 'nbr_servers')
    # import uuid
    # suffix = uuid.uuid1()
    # current_parameters.update({'topics': ['topic-{}'.format(suffix)]})
    current_parameters.update({'topics': ['topic-0']})
    current_parameters.update({'nbr_clients': current_clients - previous_clients})
    current_parameters.update({'nbr_servers': current_servers - previous_servers})


def fix_2(parameters, current_parameters):
    topics_list = parameters.get('nbr_topics')
    max_topics = max(topics_list)
    all_topics = get_topics(max_topics)
    previous_nbr_topics, nbr_topics = get_current_values(parameters, current_parameters, 'nbr_topics')
    current_topics = all_topics[previous_nbr_topics:nbr_topics]
    current_parameters.update({'topics': current_topics})
    current_parameters.update({'nbr_clients': nbr_topics})
    current_parameters.update({'nbr_servers': nbr_topics})


TEST_CASES = {
    'test_case_1': {'defn': t.test_case_1,
                    'filtr': filter_1,
                    'fixp': fix_1,
                    'key': 'nbr_clients',
                    'zip': ['nbr_servers', 'nbr_clients', 'pause']},
    'test_case_2': {'defn': t.test_case_2,
                    'filtr': filter_2,
                    'fixp': fix_2,
                    'key': 'nbr_topics',
                    'zip': ['nbr_topics', 'pause']},
    'test_case_3': {'defn': t.test_case_3,
                    'filtr': filter_3,
                    'key': 'nbr_clients'},
    'test_case_4': {'defn': t.test_case_4,
                    'filtr': filter_2,  # same as tc2
                    'key': 'nbr_topics'}
}


def dump_parameters(directory, params):
    """Dump each parameter set in the backup directory.

    All parameters are dumped in the file <test>/params.json.
    If previous are found new ones are appended.

    :param directory: working directory
    :param params: JSON parameters to dump
    """
    json_params = path.join(directory, 'params.json')
    if not path.exists(json_params):
        with open(json_params, 'w') as f:
            json.dump([], f)
    # Add current parameters
    with open(json_params, 'r') as f:
        all_params = json.load(f)
    all_params.append(params)
    with open(json_params, 'w') as f:
        json.dump(all_params, f)


def generate_id(params):
    """Generate a unique ID based on the provided parameters.

        :param params: JSON parameters of an execution.
        :return: A unique ID.
        """
    def replace(s):
        return str(s).replace("/", "_sl_").replace(":", "_sc_")

    return '-'.join(["%s__%s" % (replace(k), replace(v)) for k, v in sorted(params.items())])


def campaign(test, provider, force, conf, env):
    config = t.load_config(conf)
    parameters = config['campaign'][test]
    sweeps = sweep(parameters)
    current_env_dir = env if env else test
    sweeper = ParamSweeper(persistence_dir=path.join(current_env_dir, "sweeps"),
                           sweeps=sweeps,
                           save_sweeps=True,
                           name=test)
    t.PROVIDERS[provider](force=force,
                          config=config,
                          env=current_env_dir)
    t.inventory()
    current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])
    while current_parameters:
        try:
            current_parameters.update({'backup_dir': generate_id(current_parameters)})
            t.prepare(driver=current_parameters['driver'], env=current_env_dir)
            TEST_CASES[test]['defn'](**current_parameters)
            sweeper.done(current_parameters)
            dump_parameters(current_env_dir, current_parameters)
            current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])
        except (EnosError, RuntimeError, ValueError, KeyError, OSError) as error:
            sweeper.skip(current_parameters)
            print(error, file=sys.stderr)
            print(error.args, file=sys.stderr)
        finally:
            t.destroy()


def zip_parameters(parameters, args):
    tuples = zip(*[[(k, v) for v in parameters[k]] for k in args])
    return {'zip': [dict(z) for z in tuples]}


def flat_sweep(parameters):
    sweeps = sweep(parameters)
    pops = [e.pop('zip') for e in sweeps]
    return map(dict.update, sweeps, pops)


def incremental_campaign(test, provider, force, conf, env):
    config = t.load_config(conf)
    raw_parameters = config['campaign'][test]
    args = TEST_CASES[test]['zip']
    parameters = {k: v for k, v in raw_parameters.items() if k not in args}
    zips = zip_parameters(raw_parameters, args)
    parameters.update(zips)
    sweeps = flat_sweep(parameters)
    sweeps = sort_parameters(sweeps, TEST_CASES[test]['key'])
    current_env_dir = env if env else test
    t.PROVIDERS[provider](force=force, config=config, env=current_env_dir)
    t.inventory()
    current_parameters = sweeps.pop(0)
    # only the driver of the first iteration is used for all the campaign
    t.prepare(driver=current_parameters.get('driver'), env=current_env_dir)
    while current_parameters:
        try:
            current_parameters.update({'backup_dir': generate_id(current_parameters)})
            # fix number of clients and servers (or topics) to deploy
            TEST_CASES[test]['fixp'](raw_parameters, current_parameters)
            TEST_CASES[test]['defn'](**current_parameters)
            dump_parameters(current_env_dir, current_parameters)
            current_parameters = sweeps.pop(0)
        except (EnosError, RuntimeError, ValueError, KeyError, OSError) as error:
            print(error, file=sys.stderr)
            print(error.args, file=sys.stderr)
