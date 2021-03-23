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
        try:
            cpu_util = gc.get_client().metric.get_measures('memory.usage',
                                                           resource_id=instance.id,
                                                           aggregation='max',
                                                           start=start,
                                                           stop=stop)
        except:
            print "ERROR: cpu_util (memory.usage) not found."
            continue
        
        timeseries = {}
        for i in range (len(cpu_util)):
            if len(cpu_util[i]) < 3:
                continue
            timeseries[int(time.mktime(cpu_util[i][0].timetuple()))] = cpu_util[i][2]
        #print timeseries

        foo = nc.get_instance(instance)
        #print foo.to_dict()
        print "Name:       %s" % foo.name
        print "ID:         %s" % foo.id
        print "User ID:    %s" % foo.user_id
        print "Flavor:     %s" % foo.flavor['original_name']
        print "Project ID: %s" % foo.tenant_id
        print "Status:     %s" % foo.status
        pprint.pprint(timeseries, width=1)
        
# Run local function with the same name as the action
action = locals().get('action_' + options.action)
if not action:
    himutils.sys_error("Function action_%s() not implemented" % options.action)
action()
