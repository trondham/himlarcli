#!/usr/bin/env python

from himlarcli import tests as tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.gnocchi import Gnocchi
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from datetime import date, timedelta, datetime
from collections import defaultdict
import time
import pprint

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
nc = Nova(options.config, debug=options.debug, log=logger)
nc.set_dry_run(options.dry_run)

def action_instance():
    start = himutils.get_date(options.start, date.today() - timedelta(days=1))
    stop = himutils.get_date(options.end, date.today() + timedelta(days=1))
    gc = Gnocchi(options.config, debug=options.debug, log=logger)
    instance = nc.get_instance(options.instance)
    resources = gc.get_resource(resource_type='instance', resource_id=instance.id)
    metrics = resources['metrics']
    del resources['metrics']
    printer.output_dict({'header': 'instance metadata'})
    printer.output_dict(resources)
    printer.output_dict({'header': 'instance metrics'})
    output = defaultdict(int)
    for k, v in metrics.iteritems():
        measurement = gc.get_client().metric.get_measures(metric=v,
                                                          aggregation='max',
                                                          start=start,
                                                          stop=stop)
        if measurement:
            output[k] += measurement[0][2]
    printer.output_dict(output)

def action_list_metrics():
    gc = Gnocchi(options.config, debug=options.debug, log=logger)
    res = gc.list_metrics()
    print res

def action_get_cpu_util():
    start = himutils.get_date(options.start, date.today() - timedelta(days=1))
    stop = himutils.get_date(options.end, date.today() + timedelta(days=1))
    host = nc.get_host(nc.get_fqdn(options.host))
    if not host:
        himutils.sys_error('Could not find valid host %s' % options.host)

    search_opts = dict(all_tenants=1, host=host.hypervisor_hostname)
    instances = nc.get_all_instances(search_opts=search_opts)

    gc = Gnocchi(options.config, debug=options.debug, log=logger)

    for instance in instances:
        cpu_util = gc.get_client().metric.get_measures('cpu_util',
                                                       resource_id=instance.id,
                                                       aggregation='max',
                                                       start=start,
                                                       stop=stop)
        timeseries = {}
        for i in range (len(cpu_util)):
            timeseries[int(time.mktime(cpu_util[i][0].timetuple()))] = cpu_util[i][2]
#            cpu_util[i][0]=time.mktime(cpu_util[i][0].timetuple())
#            try:
#                cpu_util[i]=time.mktime(cpu_util[i].timetuple())
#            except ValueError:
#                next

        #print timeseries
        timeseries.pprint()
        
# Run local function with the same name as the action
action = locals().get('action_' + options.action)
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
