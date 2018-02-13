import operator
import json
import os

import itertools
from execo_engine import sweep, ParamSweeper

#from cli import load_config


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


def sort_params_by_nbr_clients(_set):
    return sorted((list(_set)), key=lambda k: k['nbr_clients'])


def dump_param(params):
        if not os.path.exists("test_case_31"):
            with open("test_case_31", 'w') as outfile:
                json.dump([], outfile)
        # Add the current params to the json
        with open("test_case_31", 'r') as outfile:
            all_params = json.load(outfile)
        all_params.append(params)
        with open("test_case_31", 'w') as outfile:
            json.dump(all_params, outfile)


def test():
    config = load_config("conf.yaml")
    parameters = config["campaign"]["test_case_1"]
    sweeps = sweep(parameters)
    print(sweeps)
    # filtered_sweeps = [param for param in sweeps if accept(param)]
    filtered_sweeps = [param for param in sweeps]
    # print(filtered_sweeps)
    sweeper = ParamSweeper(
        # Maybe puts the sweeper under the experimentation directory
        # This should be current/sweeps
        persistence_dir="test_case_21",
        sweeps=filtered_sweeps,
        save_sweeps=True,
        name=test
    )
    params = sweeper.get_next(sort_params_by_nbr_clients)
    while params:
        params.pop("backup_dir", None)
        params.update({"backup_dir": generate_id(params)})
        sweeper.done(params)
        dump_param(params)
        params = sweeper.get_next(sort_params_by_nbr_clients)


def tc1(parameterset):
    params = sorted(parameterset, key=operator.itemgetter("param1"))
    for param in params:
        if param["param1"] < param["param2"]:
            yield param


def tc2(parameters):
    return filter(parameters, lambda x: x["param1"] == x["param2"])


def filter(parameters, condition=lambda unused: True):
    params = sorted(parameters, key=operator.itemgetter("param1"))
    return (p for p in params if condition(p))



filters = {
    "test_case_1": tc1,
    "test_case_2": tc2
}


def test_sweep(filter):

    parameters = {
        "param1": [0, 1, 2, 3],
        "param2": [0, 1, 2, 3]
    }

    sweeps = sweep(parameters)
    sweeper = ParamSweeper(
        persistence_dir=os.path.join("%s/sweeps" % test),
        sweeps=sweeps,
        name=test)

    params = sweeper.get_next(filters[filter])
    while params:
        print params
        params = sweeper.get_next(filters[filter])


if __name__ == "__main__":
    test_sweep('test_case_1')
