import json
import operator
import os

from execo_engine import sweep, ParamSweeper

import tasks as t
from cli import load_config, PROVIDERS


def filter_1(parameters):
    filterp(parameters, lambda x: x['nbr_servers'] < x['nbr_clients'])


def filter_2(parameters):
    filterp(parameters, lambda x: x['nbr_servers'] == x['nbr_clients'])


def filterp(parameters, condition=lambda unused: True):
    params = sorted(parameters, key=operator.itemgetter("nbr_clients"))
    return (p for p in params if condition(p))


tc_filters = {
    'test_case_1': filter_1,
    'test_case_2': filter_2
}


def campaign(broker, provider, conf, test, env):
    """

    :param broker:
    :param provider:
    :param conf:
    :param test:
    :param env:
    :return:
    """
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
        if not os.path.exists("%s/params.json" % test):
            with open("%s/params.json" % test, 'w') as f:
                json.dump([], f)
        # Add current parameters
        with open("%s/params.json" % test, 'r') as f:
            all_params = json.load(f)
        all_params.append(params)
        with open("%s/params.json" % test, 'w') as f:
            json.dump(all_params, f)

    config = load_config(conf)
    parameters = config['campaign'][test]
    sweeps = sweep(parameters)
    sweeper = ParamSweeper(
        # Maybe puts the sweeper under the experimentation directory
        # This should be current/sweeps
        persistence_dir=os.path.join("%s/sweeps" % test),
        sweeps=sweeps,
        save_sweeps=True,
        name=test
    )

    current_parameters = sweeper.get_next(tc_filters[test])
    PROVIDERS[provider](broker=broker, config=config, env=test)
    t.inventory()
    while current_parameters:
        current_parameters.pop('backup_dir', None)
        current_parameters.update({'backup_dir': generate_id(current_parameters)})
        t.prepare(broker=broker)
        t.test_case(**current_parameters)
        sweeper.done(current_parameters)
        dump_parameters(current_parameters)
        current_parameters = sweeper.get_next(tc_filters[test])
        t.destroy()
