import json
import os

from execo_engine import sweep, ParamSweeper

import tasks as t
from cli import load_config, PROVIDERS


def generate_id(parameters):
    """Generate a unique ID based on the provided parameters.

    :param parameters: JSON parameters of an execution.
    :return: A unique ID.
    """

    def clean(s):
        return str(s).replace("/", "_sl_").replace(":", "_sc_")

    return "-".join([
        "%s__%s" % (clean(k), clean(v)) for k, v in sorted(parameters.items())
    ])


def dump_parameters(parameters, test):
    """Dump each parameter set in the backup directory.

    All parameters are dumped in the file <test>/params.json.
    If previous are found new ones are appended.

    :param parameters: JSON parameters to dump.
    :param test: Name of the test case.
    """
    if not os.path.exists("%s/params.json" % test):
        with open("%s/params.json" % test, 'w') as f:
            json.dump([], f)
    # Add current parameters
    with open("%s/params.json" % test, 'r') as f:
        all_params = json.load(f)
    all_params.append(parameters)
    with open("%s/params.json" % test, 'w') as f:
        json.dump(all_params, f)


def campaign(broker, provider, conf, test, env):
    """

    :param broker:
    :param provider:
    :param conf:
    :param test:
    :param env:
    :return:
    """
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
    # TODO add filter
    current_parameters = sweeper.get_next()
    PROVIDERS[provider](broker=broker, config=config, env=test)
    t.inventory()
    while current_parameters:
        current_parameters.pop('backup_dir', None)
        current_parameters.update({'backup_dir': generate_id(current_parameters)})
        t.prepare(broker=broker)
        t.test_case(**current_parameters)
        sweeper.done(current_parameters)
        dump_parameters(current_parameters, test)
        # TODO add filter
        current_parameters = sweeper.get_next()
        t.destroy()
