from __future__ import print_function
from __future__ import generators

import json
import operator
import string
from os import path
import sys

import time

import itertools
from enoslib.errors import EnosError
from execo_engine import sweep, ParamSweeper, HashableDict

import tasks as t


PAUSE = 1.0


def filter_1(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] <= x['nbr_clients'])


def filter_2(parameters):
    return filter_params(parameters, key='nbr_topics')


def filter_3(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] >= x['nbr_clients'])


def filter_params(parameters, key='nbr_clients', condition=lambda unused: True):
    filtered_parameters = (p for p in parameters if condition(p))
    return sort_parameters(filtered_parameters, key)


def sort_parameters(parameters, key):
    """
    Sort a list of parameters containing dictionaries.

    This kind of sort is performed to dictionaries containing at least elements with keys 'driver'
    and 'call_type'. It may also include other provided key as item for grouping by.

    >>> parameters = [
    ... {'other': 6, 'driver': 'router', 'call_type': 'rpc_cast', 'topic':'topic-1', 'nbr_clients': 60},
    ... {'other': 5, 'driver': 'router', 'call_type': 'rpc_cast', 'topic':'topic-2', 'nbr_clients': 40},
    ... {'other': 4, 'driver': 'router', 'call_type': 'rpc_call', 'topic':'topic-3', 'nbr_clients': 50},
    ... {'other': 3, 'driver': 'broker', 'call_type': 'rpc_cast', 'topic':'topic-4', 'nbr_clients': 30},
    ... {'other': 2, 'driver': 'broker', 'call_type': 'rpc_call', 'topic':'topic-5', 'nbr_clients': 20},
    ... {'other': 1, 'driver': 'router', 'call_type': 'rpc_cast', 'topic':'topic-6', 'nbr_clients': 70}]
    >>> sort_parameters(parameters, 'nbr_clients')
    [\
{'topic': 'topic-5', 'nbr_clients': 20, 'other': 2, 'driver': 'broker', 'call_type': 'rpc_call'}, \
{'topic': 'topic-4', 'nbr_clients': 30, 'other': 3, 'driver': 'broker', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-3', 'nbr_clients': 50, 'other': 4, 'driver': 'router', 'call_type': 'rpc_call'}, \
{'topic': 'topic-2', 'nbr_clients': 40, 'other': 5, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-1', 'nbr_clients': 60, 'other': 6, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-6', 'nbr_clients': 70, 'other': 1, 'driver': 'router', 'call_type': 'rpc_cast'}]
    >>> sort_parameters(parameters, key='topic')
    [\
{'topic': 'topic-5', 'nbr_clients': 20, 'other': 2, 'driver': 'broker', 'call_type': 'rpc_call'}, \
{'topic': 'topic-4', 'nbr_clients': 30, 'other': 3, 'driver': 'broker', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-3', 'nbr_clients': 50, 'other': 4, 'driver': 'router', 'call_type': 'rpc_call'}, \
{'topic': 'topic-1', 'nbr_clients': 60, 'other': 6, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-2', 'nbr_clients': 40, 'other': 5, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-6', 'nbr_clients': 70, 'other': 1, 'driver': 'router', 'call_type': 'rpc_cast'}]
    >>> sort_parameters(parameters, 'other')
    [\
{'topic': 'topic-5', 'nbr_clients': 20, 'other': 2, 'driver': 'broker', 'call_type': 'rpc_call'}, \
{'topic': 'topic-4', 'nbr_clients': 30, 'other': 3, 'driver': 'broker', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-3', 'nbr_clients': 50, 'other': 4, 'driver': 'router', 'call_type': 'rpc_call'}, \
{'topic': 'topic-6', 'nbr_clients': 70, 'other': 1, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-2', 'nbr_clients': 40, 'other': 5, 'driver': 'router', 'call_type': 'rpc_cast'}, \
{'topic': 'topic-1', 'nbr_clients': 60, 'other': 6, 'driver': 'router', 'call_type': 'rpc_cast'}]

    :param parameters: a list of sub-dictionaries containing 'driver' and 'call_type' keys
    :param key:
    :return:
    """
    return sorted(parameters, key=operator.itemgetter('driver', 'call_type', key))


def get_current_values(params, current, key):
    plist = params.get(key)
    state = current.get(key)
    index = plist.index(state)
    return (0, state) if index == 0 else (plist[index-1], state)


def fix_1(parameters, current_parameters):
    previous_clients, current_clients = get_current_values(parameters, current_parameters, 'nbr_clients')
    previous_servers, current_servers = get_current_values(parameters, current_parameters, 'nbr_servers')
    current_parameters.update({'topics': ['topic-0']})
    current_parameters.update({'nbr_clients': current_clients - previous_clients})
    current_parameters.update({'nbr_servers': current_servers - previous_servers})


def fix_2(parameters, current_parameters):
    topics_list = parameters.get('nbr_topics')
    max_topics = max(topics_list)
    all_topics = t.get_topics(max_topics)
    previous_nbr_topics, nbr_topics = get_current_values(parameters, current_parameters, 'nbr_topics')
    current_topics = all_topics[previous_nbr_topics:nbr_topics]
    current_parameters.update({'topics': current_topics})
    current_parameters.update({'nbr_clients': len(current_topics)})
    current_parameters.update({'nbr_servers': len(current_topics)})


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
    t.PROVIDERS[provider](force=force, config=config, env=current_env_dir)
    t.inventory()
    current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])
    while current_parameters:
        try:
            current_parameters.update({'backup_dir': generate_id(current_parameters)})
            t.prepare(driver=current_parameters['driver'], env=current_env_dir)
            TEST_CASES[test]['defn'](**current_parameters)
            sweeper.done(current_parameters)
            dump_parameters(current_env_dir, current_parameters)
        except (EnosError, RuntimeError, ValueError, KeyError, OSError) as error:
            sweeper.skip(current_parameters)
            print(error, file=sys.stderr)
            print(error.args, file=sys.stderr)
        finally:
            t.destroy()
            current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])


def zip_parameters(parameters, arguments):
    """
    Select elements from a dictionary and group them as a list of
    sub-dictionaries preserving the original keys.

    The selected elements are defined in a list of arguments. That list is
    not validated against the keys of the original dictionary raising a
    'KeyError' exception if an element is not found in the dictionary. The
    elements are grouped using a 'zip' operation in a list of sub-dictionaries.
    In other words the zip performs a cross product between the key and each
    element of the value-list and a dot product between the results of the
    cross product of each argument.

    >>> parameters = {
    ... 'other': [6],
    ... 'nbr_servers': [1, 2, 3],
    ... 'call_type': ['rpc-call', 'rpc_cast'],
    ... 'topic':['topic-1', 'topic-2', 'topic-3', 'topic-4', 'topic-5'],
    ... 'pause': [0.1, 0.3, 0.5],
    ... 'nbr_clients': [10, 20, 30]}
    >>> arguments = ['nbr_servers', 'nbr_clients', 'pause']
    >>> zip_parameters(parameters, arguments)
    [\
{'nbr_servers': 1, 'pause': 0.1, 'nbr_clients': 10}, \
{'nbr_servers': 2, 'pause': 0.3, 'nbr_clients': 20}, \
{'nbr_servers': 3, 'pause': 0.5, 'nbr_clients': 30}]
    >>> arguments = ['topic', 'pause']
    >>> zip_parameters(parameters, arguments)
    [\
{'topic': 'topic-1', 'pause': 0.1}, \
{'topic': 'topic-2', 'pause': 0.3}, \
{'topic': 'topic-3', 'pause': 0.5}]
    >>> arguments = ['topic', 'call_type','other']
    >>> zip_parameters(parameters, arguments)
    [{'topic': 'topic-1', 'other': 6, 'call_type': 'rpc-call'}]
    >>> arguments = ['call_type']
    >>> zip_parameters(parameters, arguments)
    [{'call_type': 'rpc-call'}, {'call_type': 'rpc_cast'}]
    >>> arguments = []
    >>> zip_parameters(parameters, arguments)
    []
    >>> arguments = ['nonexistent']
    >>> zip_parameters(parameters, arguments) # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    KeyError:

    :param parameters: dictionary containing 'key:<list of values>' elements
    :param arguments: list of keys of the elements in the dictionary to zip
    :return: a list containing sub-dictionaries of zipped arguments
    """
    tuples = zip(*[[(k, v) for v in parameters[k]] for k in arguments])
    return [dict(z) for z in tuples]


def sweep_with_lists(parameters, arguments):
    # pack arguments to zip in lists to avoid sweep over them
    parameters = {k: ([v] if k in arguments else v) for k, v in parameters.items()}
    sweeps = sweep(parameters)
    # transform list to immutable object
    sweeps = ({k: (tuple(v) if k in arguments else v) for k, v in l.items()} for l in sweeps)
    # transform dictionaries to hashable objects
    return [HashableDict(d) for d in sweeps]


def incremental_campaign(test, provider, force, pause, conf, env):
    """Execute a test incrementally (reusing deployment).

    :param test: name of the test to execute
    :param provider: target infrastructure
    :param force: override deployment configuration
    :param pause: break between iterations in seconds
    :param conf: file configuration
    :param env: directory containing the environment configuration
    """
    config = t.load_config(conf)
    parameters = config['campaign'][test]
    arguments = TEST_CASES[test]['zip']
    sweeps = sweep_with_lists(parameters, arguments)
    env_dir = env if env else '{}-incremental'.format(test)
    sweeper = ParamSweeper(persistence_dir=path.join(env_dir, 'sweeps'),
                           sweeps=sweeps, save_sweeps=True, name=test)
    t.PROVIDERS[provider](force=force, config=config, env=env_dir)
    t.inventory()
    current_group = sweeper.get_next(TEST_CASES[test].get('filtr'))
    # use uppercase letters to identify groups
    groups = itertools.cycle(string.ascii_uppercase)
    while current_group:
        group_id = groups.next()
        # use numbers (incremental) to identify iterations by group
        iterations = itertools.count()
        try:
            current_driver = current_group.get('driver')
            t.prepare(driver=current_driver, env=env_dir)
            for fixed_parameters in zip_parameters(current_group, arguments):
                current_parameters = current_group.copy()
                current_parameters.update(fixed_parameters)
                current_parameters.update({'iteration_id': '{}-{}'.format(group_id, iterations.next())})
                current_parameters.update({'backup_dir': generate_id(current_parameters)})
                # fix number of clients and servers (or topics) to deploy
                TEST_CASES[test]['fixp'](parameters, current_parameters)
                TEST_CASES[test]['defn'](**current_parameters)
                time.sleep(pause)
            sweeper.done(current_group)
            dump_parameters(env_dir, current_group)
        except (EnosError, RuntimeError, ValueError, KeyError, OSError) as error:
            sweeper.skip(current_group)
            print(error, file=sys.stderr)
            print(error.args, file=sys.stderr)
        finally:
            t.destroy()
            current_group = sweeper.get_next(TEST_CASES[test]['filtr'])
