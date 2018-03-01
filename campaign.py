from __future__ import print_function

import json
import operator
from os import path
import sys

from enoslib.errors import EnosError
from execo_engine import sweep, ParamSweeper

import tasks as t


def filter_1(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] <= x['nbr_clients'])


def filter_2(parameters):
    return filter_params(parameters, key='nbr_topics')


def filter_3(parameters):
    return filter_params(parameters, condition=lambda x: x['nbr_servers'] >= x['nbr_clients'])


def filter_params(parameters, key='nbr_clients', condition=lambda unused: True):
    # sort by 'driver' first, then by 'call type' and finally use the key
    # (i.e., group executions by driver-call_type and sort incrementally by key)
    params = sorted(parameters, key=operator.itemgetter('driver', 'call_type', key))
    return (p for p in params if condition(p))


TEST_CASES = {
    'test_case_1': {'defn': t.test_case_1, 'filtr': filter_1},
    'test_case_2': {'defn': t.test_case_2, 'filtr': filter_2},
    'test_case_3': {'defn': t.test_case_3, 'filtr': filter_3},
    'test_case_4': {'defn': t.test_case_4, 'filtr': filter_2}  # same as tc2
}

ZIP_ARGS = {
    'test_case_1': ['nbr_servers', 'nbr_clients', 'pause'],
    'test_case_2': ['nbr_topics, pause']
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
            t.prepare(broker=current_parameters['driver'])
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


def zip_parameters(parameters, *args):
    tuples = zip(*[[(k, v) for v in parameters[k]] for k in args])
    return {'tuple': [dict(t) for t in tuples]}


def incremental_campaign(test, provider, force, conf, env):
    config = t.load_config(conf)
    parameters = config['campaign'][test]
    args = ZIP_ARGS[test]
    result = zip_parameters(parameters, *args)
    filtered_parameters = {k: v for k, v in parameters.items() if k not in args}
    filtered_parameters.update(result)
    sweeps = sweep(filtered_parameters)
    for e in sweeps:
        d = e.pop('tuple')
        e.update(d)
    print(sweeps)
