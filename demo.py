#!/usr/bin/env python

from datetime import date, datetime, timedelta
from email.mime.text import MIMEText

from himlarcli import tests
tests.is_virtual_env()

from himlarcli.keystone import Keystone
from himlarcli.nova import Nova
from himlarcli.cinder import Cinder
from himlarcli.mail import Mail
from himlarcli.parser import Parser
from himlarcli.printer import Printer
from himlarcli import utils as himutils
from himlarcli.global_state import GlobalState, DemoInstance

parser = Parser()
options = parser.parse_args()
printer = Printer(options.format)

kc = Keystone(options.config, debug=options.debug)
kc.set_domain(options.domain)
kc.set_dry_run(options.dry_run)
logger = kc.get_logger()
regions = himutils.get_regions(options, kc)

# Today's date in ISO format
today_iso = date.today().isoformat()

# Initialize database connection
db = himutils.get_client(GlobalState, options, logger)

# Age and notification config
MAX_AGE             = 90 # Max age of a demo instance, in days
FIRST_NOTIFICATION  = 30 # Days until deletion for 1st notification
SECOND_NOTIFICATION = 14 # Days until deletion for 2nd notification
THIRD_NOTIFICATION  = 7  # Days until deletion for 3rd notification

#---------------------------------------------------------------------
# Action functions
#---------------------------------------------------------------------
def action_projects():
    projects = kc.get_projects(type='demo')
    printer.output_dict({'header': 'Demo project (instances, vcpus, volumes, gb, name)'})
    count = {'size': 0, 'vcpus': 0, 'instances': 0}
    for project in projects:
        ins_data = {'count': 0, 'vcpu': 0}
        vol_data = dict({'count': 0, 'size': 0})
        for region in regions:
            nc = himutils.get_client(Nova, options, logger, region)
            cc = himutils.get_client(Cinder, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            ins_data = {'count': 0, 'vcpus': 0}
            for i in instances:
                ins_data['vcpus'] += i.flavor['vcpus']
                ins_data['count'] += 1
            volumes = cc.get_volumes(detailed=True, search_opts={'project_id': project.id})
            for volume in volumes:
                vol_data['size'] += volume.size
                vol_data['count'] += 1
        output = {
            '5': project.name,
            '1': ins_data['count'],
            '2': ins_data['vcpus'],
            '3': vol_data['count'],
            '4': vol_data['size']
        }
        printer.output_dict(output, one_line=True)
        count['size'] += vol_data['size']
        count['vcpus'] += ins_data['vcpus']
        count['instances'] += ins_data['count']
    printer.output_dict({
        'header': 'Count',
        'instances': count['instances'],
        'volume_gb': count['size'],
        'vcpus': count['vcpus']})

def action_instances():
    projects = kc.get_projects(type='demo')
    printer.output_dict({'header': 'Demo instances (id, lifetime in days, name, flavor)'})
    count = 0
    for project in projects:
        for region in regions:
            nc = himutils.get_client(Nova, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            for i in instances:
                created = himutils.get_date(i.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                if int(active_days) < int(options.day):
                    continue
                output = {
                    '0': i.id,
                    '2': i.name,
                    '1': (date.today() - created).days,
                    '3': i.flavor['original_name']
                }
                count += 1
                printer.output_dict(output, one_line=True)
    printer.output_dict({'header': 'Count', 'count': count})

# Notify user when:
#   - 1st: instance age >= 60 days and notification 1 has not been sent
#   - 2nd: 16 days since notification 1 was sent
#   - 3rd: 7 days since notification 2 was sent
def action_expired():
    projects = kc.get_projects(type='demo')

    # Interactive confirmation
    question = f'Really send emails to users?'
    if options.notify and not options.force and not options.dry_run and not himutils.confirm_action(question):
        return

    for region in regions:
        nc = himutils.get_client(Nova, options, logger, region)
        for project in projects:
            instances = nc.get_project_instances(project_id=project.id)
            for instance in instances:
                created = himutils.get_date(instance.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                kc.debug_log(f'{instance.id} running for {active_days} days')

                # Send first notification?
                if int(active_days) >= (MAX_AGE - FIRST_NOTIFICATION):
                    if options.notify:
                        dbadd = add_to_db(
                            instance_id = instance.id,
                            project_id  = project.id,
                            region      = region
                        )
                        if dbadd:
                            notify_user(instance, project, region, active_days, notification_type='first')
                    else:
                        p_warning(f"[1st] Expired instance in {project.name} (active: {active_days})")
                    continue
                else:
                    p_info(f"OK instance in {project.name} (active: {active_days})")

                # Get existing db entry
                entry = db.get_first(DemoInstance,
                                     instance_id=instance.id,
                                     project_id=project.id,
                                     region=region)
                if entry is None:
                    continue

                # Send second notification?
                if entry.notified2 is None and datetime.now() > entry.notified1 + timedelta(days=(MAX_AGE - SECOND_NOTIFICATION)):
                    if options.notify:
                        dbupate = update_db(
                            instance_id = instance.id,
                            project_id  = project.id,
                            region      = region,
                            notified2   = datetime.now()
                        )
                        if dbupdate:
                            notify_user(instance, project, region, active_days, notification_type='second')
                    else:
                        p_warning(f"[2nd] Expired instance in {project.name} (active: {active_days})")
                    continue

                # Send third notification?
                if entry.notified3 is None and datetime.now() > entry.notified2 + timedelta(days=(MAX_AGE - THIRD_NOTIFICATION)):
                    if options.notify:
                        dbupate = update_db(
                            instance_id = instance.id,
                            project_id  = project.id,
                            region      = region,
                            notified3   = datetime.now()
                        )
                        if dbupdate:
                            notify_user(instance, project, region, active_days, notification_type='third')
                    else:
                        p_warning(f"[3rd] Expired instance in {project.name} (active: {active_days})")
                    continue


# Delete instance when
#   - 7 days since notification 3 was sent
# NB! We only care about when notifications were sent when deciding to delete instances
def action_delete():
    days = 90
    question = f'Delete demo instances older than {days} days?'
    if not options.force and not himutils.confirm_action(question):
        return
    projects = kc.get_projects(type='demo')
    logfile = f'logs/demo-logs/deleted_instances/deleted-expired-demo-instances-{today_iso}.log'
    for region in regions:
        for project in projects:
            nc = himutils.get_client(Nova, options, logger, region)
            instances = nc.get_project_instances(project_id=project.id)
            for instance in instances:
                created = himutils.get_date(instance.created, None, '%Y-%m-%dT%H:%M:%SZ')
                active_days = (date.today() - created).days
                kc.debug_log(f'Found instance {instance.id} for user {project.admin}')
                if int(active_days) >= days:
                    nc.delete_instance(instance)
                    if not options.dry_run:
                        himutils.append_to_logfile(logfile, "deleted:", project.name, instance.name, "active for:", active_days)


#---------------------------------------------------------------------
# Helper functions
#---------------------------------------------------------------------

# Print info message
def p_info(string):
    himutils.info(string)

# Print warning message
def p_warning(string):
    himutils.warning(string)

# Print error message
def p_error(string):
    himutils.error(string)

def notify_user(instance, project, region, active_days, notification_type):
    # Template to use
    template = 'notify/demo/instance_expiration.txt'

    # logfile
    logfile = f'logs/demo-logs/expired_instances/demo-notify-expired-instances-{today_iso}.log'

    # mail parameters
    mail = himutils.get_client(Mail, options, logger)
    mail = Mail(options.config, debug=options.debug)
    mail.set_dry_run(options.dry_run)
    fromaddr = mail.get_config('mail', 'from_addr')
    bccaddr = 'iaas-logs@usit.uio.no'
    ccaddr = None

    # Calculate the days until deletion
    enddate = {
        'first'  : FIRST_NOTIFICATION,
        'second' : SECOND_NOTIFICATION,
        'third'  : THIRD_NOTIFICATION,
    }

    mapping = {
        'project'  : project.name,
        'enddate'  : enddate[notification_type],
        'activity' : int(active_days),
        'region'   : region.upper(),
        'instance' : instance.name
    }
    body_content = himutils.load_template(inputfile=template,
                                          mapping=mapping,
                                          log=logger)
    msg = MIMEText(body_content, 'plain')
    msg['subject'] = '[NREC] Your demo instance is due for deletion in {FIXME} days'

    # Send mail to user
    #mail.send_mail(project.admin, msg, fromaddr, ccaddr, bccaddr)
    #kc.debug_log(f'Sending mail to {instance.id} that has been active for {active_days} days')
    #himutils.append_to_logfile(logfile, date.today(), region, project.admin, instance.name, active_days)
    if options.dry_run:
        print(f"Did NOT send spam to {project.admin}")
        print(f"Subject: {msg['subject']}")
        print(f"To: {project.admin}")
        if bccaddr:
            print(f"Bcc: {bccaddr}")
        print(f"From: {fromaddr}")
        print('---')
        print(body_content)
    else:
        print(f"Spam sent to {project.admin}")


# Add entry to the database if it doesn't already exists. Returns True
# if database was updated
def add_to_db(instance_id, project_id, region):
    existing_object = db.get_first(DemoInstance,
                                   instance_id=rule_id,
                                   project_id=project_id,
                                   region=region)
    if existing_object is None:
        demo_instance_entry = {
            'instance_id' : instance_id,
            'project_id'  : project_id,
            'region'      : region,
            'created'     : datetime.now(),
            'notified1'   : datetime.now(),
            'notified2'   : None,
            'notified3'   : None,
        }
        demo_instance_object = DemoInstance.create(demo_instance_entry)
        db.add(demo_instance_object)
        return True

    return False

# Update entry in the database. Returns True if database was updated
def update_db(instance_id, project_id, region, **kwargs):
    try:
        existing_object = db.get_first(DemoInstance,
                                       instance_id=rule_id,
                                       project_id=project_id,
                                       region=region)
    except:
        print("error updating database")
        return False

    demo_instance_entry = {
        'instance_id' : instance_id,
        'project_id'  : project_id,
        'region'      : region,
        **kwargs,
    }
    demo_instance_object = DemoInstance.create(demo_instance_entry)
    db.add(demo_instance_object)
    return True


#---------------------------------------------------------------------
# Run local function with the same name as the action (Note: - => _)
#---------------------------------------------------------------------
action = locals().get('action_' + options.action.replace('-', '_'))
if not action:
    himutils.fatal(f"Function action_{options.action} not implemented")
action()
