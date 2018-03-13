# Message bus evaluation framework

## Context

This is a framework to benchmark the communication middleware supported by [oslo.messaging](https://docs.openstack.org/oslo.messaging/latest/). It's primary goal is to address the evaluation of https://docs.openstack.org/performance-docs/latest/test_plans/massively_distribute_rpc/plan.html.

It is build on top of: 

- [EnOSlib](https://github.com/beyondtheclouds/enoslib). This library helps to describe the experimental workflow and enforce it : from the deployment to the performance metrics analysis.
- [ombt](https://github.com/kgiusti/ombt). This will coordinate the benchmark once all the agents are up and running.

From a high level point of view the framework is able to deploy

* a communication bus (e.g RabbitMQ, qdr aka qpid-dispatch-router), 
* a set of client/server that will communicate
* start a benchmark while gathering metrics


A typical test consists in the following components:

```
Client 1---------+      +----------------------+     +-----> Server 1
                 |      |                      |     |
                 +----> |  Communication       | ----+-----> Server 2
Client 2--------------> |  Middleware          |     |
                 +----> |  (e.g qdr, rabbitms) |     |
...              |      |                      |     |
                 |      +----------------------+     +------> Server n
Client n---------+              |                             /
  \                                                         /
    \                           |                         / 
      \  --  --  --  --  -- Monitoring --  --  --  --  --
```

## Installation

* Clone the repository: 

```
git clone https://github.com/msimonin/ombt-orchestrator
cd ombt-orchestrator
```

* Install the dependencies

```
virtualenv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

> On Grid'5000 you can launch this command from any frontend.

## Configuration

The default configurations are currently defined in the `conf.yaml` file.

## Command line interface

```
> cli.py 
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  backup       Backup environment logs [after test_case_*].
  campaign     Perform a TEST according to the (swept)...
  deploy       Claim resources from a PROVIDER and configure...
  destroy      Destroy all the running dockers (keeping...
  g5k          Claim resources on Grid'5000 (frontend).
  inventory    Generate the Ansible inventory [after g5k,...
  prepare      Configure available resources [after g5k,...
  test_case_1  Run the test case 1: one single large...
  test_case_2  Run the test case 2: multiple distributed...
  test_case_3  Run the test case 3: one single large...
  test_case_4  Run the test case 4: multiple distributed...
  vagrant      Claim resources on vagrant (localhost).
```

## Workflow to run a test case


* Deploying and launching the benchmark.

```
# default confs.yaml on $PWD will be read
> cli.py deploy --driver=rabbitmq vagrant

# Launch the one benchmark
> cli.py test_case_1 --nbr_clients 10 --nbr_servers 2
```

> Adapt to the relevant provider (e.g `g5k`)

* Real-time metrics visualisation

Grafana is available on the port 3000 of the control node (check the inventory file).

* Backuping the environment

```
> cli.py backup
```

> The files retrieved by this action are located in `current/backup` dir by default.

* Some cleaning and preparation for the next run

```
# Preparing the next run by cleaning the environment
> cli.py destroy
> cli.py deploy --driver=rabbitmq vagrant

# Next run
> cli.py test_case_1 --nbr_clients 20 --nbr_servers 2
```

> It's possible to force an experimentation dir with `--env mydir`

> Note also that scripting from python is also possible using the function defined in `task.py`


## Workflow to run a campaign

* A campaign is a batch execution of several configurations for a given test case.
  Deployment and execution of a benchmark is read from a configuration file. For example,
  to run the first test case enabled on the framework run: 

``` shell
> cli.py campaign --provider g5k test_case_1
``` 

* Alternatively a campaign can be executed in a _incremental_ mode in which deployments are
  performed only when a different `driver` or `call_type` is defined. Incremental campaigns
  are executed with a different semantic on the parameters defined in the configuration.
  With the incremental option the semantics is based on the combination of parameters by 
  means of a dot product between a set of them in the configuration file (i.e., a `zip` 
  operation between the lists of parameters). These parameters are defined by test case
  as follows:

    * Test case 1: `nbr_clients`, `nbr_servers` and `pause`
    * Test case 2: `nbr_topics` and `pause`
    * Test case 3: `nbr_clients`, `nbr_servers` and `pause` (only `rpc-cast` calls)
    * Test case 4: `nbr_topics` and `pause` (only `rpc-cast` calls)
   
* To execute an incremental campaign be sure to use the ombt version `msimonin/ombt:singleton`
  instead of the default and execute:  

``` shell
> cli.py campaign --incremental --provider g5k test_case_1
``` 

## Misc.

* Bound clients or servers to specific bus agents:

To bind ombt-clients to a specific bus instance you can declare the following
`roles: [bus, bus-client]`. 

Following the same idea ombt-servers can be bound to a specific bus instance using 
`roles: [bus, bus-server]`
