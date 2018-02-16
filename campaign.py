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
    params = sorted(parameters, key=operator.itemgetter(key))
    return (p for p in params if condition(p))


TEST_CASES = {
    'test_case_1': {'defn': t.test_case_1, 'filtr': filter_1},
    'test_case_2': {'defn': t.test_case_2, 'filtr': filter_2},
    'test_case_3': {'defn': t.test_case_3, 'filtr': filter_3},
    'test_case_4': {'defn': t.test_case_4, 'filtr': filter_2}  # same as tc2
}


def campaign(broker, force, provider, conf, test, env):

    def generate_id(params):
        """Generate a unique ID based on the provided parameters.

        :param params: JSON parameters of an execution.
        :return: A unique ID.
        """

        def clean(s):
            return str(s).replace("/", "_sl_").replace(":", "_sc_")

        return "-".join([
            "%s__%s" % (clean(k), clean(v)) for k, v in sorted(params.items())
        ])

    def dump_parameters(params):
        """Dump each parameter set in the backup directory.

        All parameters are dumped in the file <test>/params.json.
        If previous are found new ones are appended.

        :param params: JSON parameters to dump.
        """
        if not path.exists("%s/params.json" % test):
            with open("%s/params.json" % test, 'w') as f:
                json.dump([], f)
        # Add current parameters
        with open("%s/params.json" % test, 'r') as f:
            all_params = json.load(f)
        all_params.append(params)
        with open("%s/params.json" % test, 'w') as f:
            json.dump(all_params, f)

    config = t.load_config(conf)
    parameters = config['campaign'][test]
    sweeps = sweep(parameters)
    sweeper = ParamSweeper(
        # Maybe puts the sweeper under the experimentation directory
        # This should be current/sweeps
        persistence_dir=path.join("%s/sweeps" % test),
        sweeps=sweeps,
        save_sweeps=True,
        name=test
    )

    current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])
    t.PROVIDERS[provider](broker=broker, force=force, config=config, env=env)
    t.inventory()
    while current_parameters:
        try:
            current_parameters.pop('backup_dir', None)
            current_parameters.update({'backup_dir': generate_id(current_parameters)})
            t.prepare(broker=broker)
            TEST_CASES[test]['defn'](**current_parameters)
            sweeper.done(current_parameters)
            dump_parameters(current_parameters)
            current_parameters = sweeper.get_next(TEST_CASES[test]['filtr'])
        except (EnosError, RuntimeError, ValueError, KeyError, OSError) as error:
            print(error, file=sys.stderr)
            print(error.args, file=sys.stderr)
        finally:
            sweeper.skip(current_parameters)
            t.destroy()
