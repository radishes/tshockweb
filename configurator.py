import util,os
from string import Template

class cfg(object):
    def __init__(self, token, default, desc):
        self.token = str(token)
        self.default = str(default)
        self.value = str(default)
        self.desc = str(desc)
    def __str__(self):
        return 'Token: %s\nDesc: %s\nDefault: %s\nValue: %s' % (self.token, self.desc, self.default, self.value)

def make_cfg_dict(cfgs):
    d = {}
    for c in cfgs:
        d[c.token] = c.value
    return d

default_config_file = 'default_config.data'
props_file_name = 'tshockweb.properties'
templates_properties = 'templates.properties'

configs = [ cfg('IP', '0.0.0.0', 'The IP address on which to listen for HTTP requests. "0.0.0.0" means all IPs.'),
            cfg('PORT', '17070', 'The port on which to listen for HTTP connections'),
            cfg('API_URL', 'http://localhost:7878', 'The URL of the TShock server API, "http://address:port".'),
            cfg('STATIC_PATH', os.getcwd().replace('\\', '/'), 'The root directory for sourcing static content. This should be the directory that the TShockweb executable or source is in.'),
            cfg('TSHOCK_LOG_PATH', '', 'The path to the TShock log file. UNC paths are permitted. If the TShock log files are not available from here, then enter blank.'),
            cfg('TSHOCK_WORLD_PATH', '', 'The path to the TShock world files. UNC paths are allowed. Leave blank if not needed.'),
            cfg('TSHOCK_WORLD_BACKUP_PATH', '', 'A path to a location where TShockweb can back up TShock world files. UNC paths are allowed. Leave blank if not needed.')
                 ]



def make_cfg():
    print ' * * * TShockweb configurator * * * '
    print ''
    print 'TShockweb requires a configuration file called "%s" to function. This file was not found, but we can make a configuration file for you. I just need some information about your environment, and I will generate a %s file. If you want to run this configurator again later, simply remove the %s file from the tshockweb folder.' % (props_file_name, props_file_name, props_file_name)
    for q in configs:
        print '\n\n************************************'
        print q.token
        print 'Description: %s \n' % (q.desc)
        ans = raw_input('Enter a value, or leave blank to accept the default of "%s" >>> ' % (q.default))
        ans = ans.replace('\\', '/').strip()
        if ans is not None and len(ans) > 0:
            q.value = ans

    print '\n\nGenerating tshockweb.properties...'
    default_config = util.load_file(default_config_file)
    tokens = make_cfg_dict(configs)
    modified_config = Template(default_config).safe_substitute(tokens)
    print modified_config
    print 'Done!'
    
