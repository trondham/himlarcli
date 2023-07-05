#!/usr/bin/env python

from himlarcli import tests as tests
tests.is_virtual_env()

import re
import ipaddress
from himlarcli.keystone import Keystone
from himlarcli.neutron import Neutron
from himlarcli.nova import Nova
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as utils

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_domain(options.domain)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
regions = utils.get_regions(options, kc)

def action_list():
    # pylint: disable=W0612

    blacklist, whitelist, notify = load_config()
    for region in regions:
        nova = utils.get_client(Nova, options, logger, region)
        neutron = utils.get_client(Neutron, options, logger, region)
        rules = neutron.get_security_group_rules(1000)
        question = f'Are you sure you will check {len(rules)} security group rules in {region}?'
        if not options.assume_yes and not utils.confirm_action(question):
            return

        printer.output_dict({'header': f'Rules in {region} (project, port, ip)'})

        for rule in rules:
            if str(rule['remote_ip_prefix']).endswith('/0'):
                ip = ipaddress.ip_interface(rule['remote_ip_prefix']).ip
                if ip.compressed == '0.0.0.0' or ip.compressed == '::':
                    True
                else:
                    print(f"WARNING: {project.name}: {rule['remote_ip_prefix']}\n")
#            else:
#                continue

            if is_whitelist(rule, whitelist):
                continue
            if is_blacklist(rule, blacklist):
                continue
            sec_group = neutron.get_security_group(rule['security_group_id'])
            if not rule_in_use(sec_group, nova):
                continue
            # check if project exists
            project = kc.get_by_id('project', rule['project_id'])
            if not project:
                kc.debug_log(f'could not find project {rule["project_id"]}')
                continue
            output = {
                '0': project.name,
                '1': "{}-{}".format(rule['port_range_min'], rule['port_range_max']),
                '2': rule['remote_ip_prefix']
            }
            printer.output_dict(output, one_line=True)
            #printer.output_dict(rule)


def rule_in_use(sec_group, nova):
    instances = nova.get_project_instances(sec_group['project_id'])
    for i in instances:
        if not hasattr(i, 'security_groups'):
            continue
        for group in i.security_groups:
            if group['name'] == sec_group['name']:
                return True
    return False

def notify_rule(rule, notify):
    # pylint: disable=W0613
    # TODO
    return False

def is_blacklist(rule, blacklist):
    # pylint: disable=W0613
    # TODO
    return False

def is_whitelist(rule, whitelist):
    #valid_none_check = ['remote_ip_prefix']
    for k, v in whitelist.items():
        # whitelist none empty property
        if "!None" in v and rule[k]:
            return True
        # port match: both port_range_min and port_range_max need to match
        if k == 'port':
            if rule['port_range_min'] in v and rule['port_range_max'] in v:
                return True
        # regex remote ip
        #elif k == 'remote_ip_prefix_regex':
        #    for regex in v:
        #        pattern = re.compile(rf'^{regex}$')
        #        if pattern.search(str(rule['remote_ip_prefix'])):
        #            return True
        elif k == 'remote_ip_prefix':
            rule_network = ipaddress.ip_network(rule['remote_ip_prefix'])
            for r in v:
                rule_white   = ipaddress.ip_network(r)
                if rule_network.version != rule_white.version:
                    continue
                # NOTE: If python is 3.7 or newer, replace with subnet_of()
                return (rule_network.network_address <= rule_white.network_address and
                        rule_network.broadcast_address >= rule_white.broadcast_address)
        # whitelist match
        elif rule[k] in v:
            return True
    return False


def load_config():
    config_files = {
        'blacklist': 'config/security_group/blacklist.yaml',
        'whitelist': 'config/security_group/whitelist.yaml',
        'notify': 'config/security_group/notify.yaml'}
    config = dict()
    for file_type, config_file in config_files.items():
        config[file_type] = utils.load_config(config_file)
        kc.debug_log('{}: {}'.format(file_type, config[file_type]))
    return [(v) for v in config.values()]

# From ipaddress module in python >= 3.7
def _is_subnet_of(a, b):
    try:
        # Always false if one is v4 and the other is v6.
        if ipaddress.a._version != ipaddress.b._version:
            raise TypeError(f"{a} and {b} are not of the same version")
        return (ipaddress.b.network_address <= ipaddress.a.network_address and
                ipaddress.b.broadcast_address >= ipaddress.a.broadcast_address)
    except AttributeError:
        raise TypeError(f"Unable to test subnet containment "
                        f"between {a} and {b}")

# Run local function with the same name as the action (Note: - => _)
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    utils.sys_error("Function action_%s() not implemented" % options.action)
action()
