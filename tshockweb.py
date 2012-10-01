# TShockweb - a web interface for TShock, the Terraria server mod.
# http://radishes.org/tshockweb

import httplib2, cherrypy
import os, sys, time, json, urllib, datetime, shutil, itertools, re, copy, cgi
from string import Template
#from collections import defaultdict

from util import *
from objects import *
from extensions import *


application_properties_file = 'tshockweb.properties'


def validate_token(redirect='/'):
    """
    Checks the user's stored session token. Returns True if valid, redirects or returns False if invalid.
    If an invalid token is received, redirect the user to a given URL.
    ("Token" in this context being a temporary authorization code received from the TShock API.)
    """ 
    h = httplib2.Http()
    try:
        resp, content = h.request(d.server['api_url']+'/tokentest?token='+cherrypy.session['token'])
        content = json.loads(content)
    except KeyError:
        if redirect is not None:
            raise cherrypy.HTTPRedirect(redirect)
        return False
    if content['status'] != '200':
        if redirect is not None:
            raise cherrypy.HTTPRedirect(redirect)
        return False
    else: # 200 response
        # update the last_seen timestamp for this user
        if 'username' in cherrypy.session:
            d.last_seen[cherrypy.session['username']] = time.time()
        return True



def process_template(template, context, **args):
    """
    template : String. The text of the template to process.
    context  : String. Optionally specify one of the arguments from args to use to obtain a context value.
               For example, if context is set to 'player_name', and one of the key/value pairs in args is
               'player_name=Someone', then the context value will be 'Someone'. This is used, for example,
               to return a page with information about a specific player.
    args     : Dict. Key is a parameter from the page request, value is the value of that parameter.
    This function 
    """
    processed_tmpl = ''

    if 'status_msg' not in cherrypy.session:
        cherrypy.session['status_msg'] = []

    #found_tokens = set() # Set of token objects
    context_val = ''
    if context in args:
        context_val = args[context]

    # parse template and find tokens for which we need values
    for token in d.tm.tokens.keys(): # look for each of the tokens we know about
        prefixed_token = '$'+token
        if template.find(prefixed_token) > -1: # found the token
            d.tm.get(token, context_val)

    # parse the template for special tokens
    start_token = d.spec_tokens['token_prefix'] + d.spec_tokens['pattern_start_token'] # marks the start of a pattern
    end_token = d.spec_tokens['token_prefix'] + d.spec_tokens['pattern_end_token'] # marks the end of a pattern
    patterns = [] # patterns are bordered by #_START and $_END tokens.
    i = -1 # search marker indicating character index of current place in search
    while True: # search until we haven't found any more special tokens
        i = template.find(start_token, i+1)
        if i == -1:
            break
        j = template.find(end_token, i)
        if j == -1:
            break
        pattern = template[i+len(start_token):j]
        enums = []
        pattern_replaced = ''
        for token in d.tm.make_str_dict(context_val).keys(): # look for enumerator tokens (tokens containing '#')
            dtoken = d.spec_tokens['token_prefix']+token
            if token.find(d.spec_tokens['pattern_enumerator']) > -1:
                if pattern.find(dtoken) > -1:
                    enums.append(token) # store the token we found in a list
        if len(enums) > 0: # Found enumerator tokens
            num_rows = 0
            try:
                all_rows = d.tm.tokens[enums[0]].contexts[context_val]
            except KeyError:
                all_rows = '' # player doesn't exist, etc
            if type(all_rows) == type([]) or type(all_rows) == type({}): # it's a container type, meaning we need to get the length ourselves
                num_rows = len(all_rows)
            elif type(all_rows) == type(1): # it's an integer representing the count of rows, probably from a function sourced token
                    num_rows = int(all_rows) # hopefully an integer is stored here...

            for n in range(num_rows): # note - if there are more than one enumerator token in a pattern, the length of the payload of the first will be used to enumerate
                replaced = pattern
                for enum in enums: # loop through enumerator tokens replacing '#' with a number
                    replaced = replaced.replace(enum, enum.replace(d.spec_tokens['pattern_enumerator'], str(n+1)) ) 
                pattern_replaced += replaced

        template = template[:i] + pattern_replaced + template[j+len(end_token):]
        i = j # move the search marker past the end token

    sd = d.tm.make_str_dict(context_val)
    for k,v in sd.items(): # make each token's value safe for HTML
        sd[k] = cgi.escape(str(v)) # replace '<', '>', and '&' with HTML escaped versions
        # I feel like there must be an easier way to apply a function to all values in a dict, but I don't know what it is :P
        if len(d.tm.tokens[k].post_processor) > 0:
            sd[k] = getattr(extensions, d.tm.tokens[k].post_processor)(sd[k])

    try:
        for sm in cherrypy.session['status_msg'].reverse():
            if 'STATUS_MSG' not in sd:
                sd['STATUS_MSG'] = ''
            sd['STATUS_MSG'] += sm + '<br>'
    except TypeError:
        pass

    processed_tmpl = Template(template).safe_substitute(sd)
    return processed_tmpl



# This object is used with CherryPy to serve HTTP requests.
class Root(object):
    def index(self, **args): # serves requests to '/' and '/index'
        T = None # Tmpl object
        page_content = ''
        user_message = ''
        login_fail_redirect = d.ui['page'] + d.ui['login_fail_redirect']
        login_success_redirect = d.ui['page'] + d.ui['login_success_redirect']

        # check if the user is trying to log in
        try:
            if args['username'] == '' or args['password'] == '':
               user_message += '<br>Enter login credentials.<br>'
            else: # we have received a username and password - try to log in with them
                h = httplib2.Http()
                # try to get token
                url = d.server['api_url'] + '/v2/token/create/%s?username=%s'  % (args['password'], args['username'])
                # TODO: currently if the TShock server is unavailable, this will hang for a long time, and it shouldn't.
                # ideally the timeout value would be configurable by the administrator.
                try:
                    resp, content = h.request(url, 'GET')
                    content = json.loads(content)
                    if content['status'] == '200': # success, logging user in
                        cherrypy.session['token'] = content['token']
                        cherrypy.session['username'] = args['username']

                        raise cherrypy.HTTPRedirect(login_success_redirect)
                        return 'Logged in successfully; redirecting...'
                    else: # login fail
                        page_content += '<br>Login failed.<br>'
                except AttributeError as detail:
                    page_content += '<br><span font="red">Unable to login at this time. Failed to contact TShock server.</span><br>'
                    print 'ERROR - Exception: ' + str(detail) # debug message to log
        except KeyError:
            pass # this exception will fire if no username or password arguments are found

        # check if the user requested a template with '/?page=<template>' or configured equivalent, and serve the requested template
        if 'page' in args:
            if args['page'] in d.tmpl:
                T = d.tmpl[args['page']]
                if T.auth: # if this template requires authentication, then we need to check their token
                    validate_token(login_fail_redirect) # this will redirect the user if validation fails.
                # user is now authenticated if necessary.
                page_content = process_template(T.template, T.context, **args)
            else:
                T = d.tmpl[d.ui['page'] + d.ui['default_page']]
        else: # URL did not include a page argument. No specific, known template was requested - give em the default page.
            raise cherrypy.HTTPRedirect(d.ui['page'] + d.ui['default_page'])


        return page_content
    index.exposed = True


    # Responds to requests to '/logout'
    def logout(self):
        cherrypy.lib.sessions.expire()
        h = httplib2.Http()
        resp, content = h.request(d.server['api_url']+'/token/destroy?token='+cherrypy.session['token'], 'GET')
        raise cherrypy.HTTPRedirect(d.ui['page'] + d.ui['default_page'])
    logout.exposed = True

    def do(self, **args):
        validate_token()
        h = httplib2.Http()
        api_call = ''
        status_msg = ''
        if d.ui['show_admin_name_on_action']:
            web_user = '<%s>' % (cherrypy.session['username'])
            reason = urllib.quote('By %s via web.' % (web_user))
        else:
            web_user = ''
            reason = urllib.quote('Via web.')
        if 'player' in args:
            player = urllib.quote(args['player'])
        if 'text' in args:
            text = urllib.quote(args['text'])
        if 'reason' in args:
            reason = urllib.quote('%s%s' % (web_user, args['reason']))
        try:
            action = args['action'] # action to take on player
        except KeyError:
            return 'No action received.'
        parameters = '?token='+cherrypy.session['token']
        if action == 'kick':
            api_call = d.server['api_url']+'/v2/players/kick'+parameters+'&player='+player+'&reason='+reason
            status_msg = 'Kicked player: %s' % (player)
        elif action == 'ban':
            api_call = d.server['api_url']+'/v2/players/ban'+parameters+'&player='+player+'&reason='+reason
            status_msg = 'Banned player: %s' % (player)
        elif action == 'kill':
            api_call = d.server['api_url']+'/v2/players/kill'+parameters+'&from='+urllib.quote(web_user)+'&player='+player+'&reason='+reason
            status_msg = 'Killed player: %s' % (player)
        elif action == 'mute':
            api_call = d.server['api_url']+'/v2/players/mute'+parameters+'&player='+player+'&reason='+reason
            status_msg = 'Muted player: %s' % (player)
        elif action == 'unmute':
            api_call = d.server['api_url']+'/v2/players/unmute'+parameters+'&player='+player+'&reason='+reason
            status_msg = 'Unmuted player: %s' % (player)
        elif action == 'broadcast':
            msg_text = '%s%s%s' % (web_user, '%20', text)
            api_call = '%s/v2/server/broadcast%s&msg=%s' % (d.server['api_url'], parameters, msg_text)
            status_msg = 'Broadcast message to server: %s' % (msg_text)
        elif action == 'cmd':
            api_call = '%s/v2/server/rawcmd%s&cmd=%s' % (d.server['api_url'], parameters, text)
            status_msg = 'Issued console command: %s' % (text)
        elif action == 'bloodmoon':
            bm_bool = not d.tm.tokens['WORLD_BLOODMOON'].contexts['']
            api_call = '%s/world/bloodmoon/%s%s' % (d.server['api_url'], bm_bool, parameters)
            d.tm.tokens['WORLD_BLOODMOON'].contexts[''] = bm_bool
            status_msg = 'Rloodmoon set to %s.' % (bm_bool)
        elif action == 'butcher':
            api_call = '%s/v2/world/butcher%s&killfriendly=false' % (d.server['api_url'], parameters)
            status_msg = 'Enemies butchered.'
        elif action == 'meteor':
            api_call = '%s/world/meteor%s' % (d.server['api_url'], parameters)
            status_msg = 'Meteor spawned.'
        else:
            return 'Invalid action received: ' + str(action)

        resp, content = h.request(api_call, 'GET')
        #print 'Code %s Action [%s] executed against player [%s]. Reason: %s' % (str(resp), action, player, reason)
        cherrypy.session['status_msg'].append(status_msg)

        if 'Referer' in cherrypy.request.headers:
            raise cherrypy.HTTPRedirect(cherrypy.request.headers['Referer'])
        raise cherrypy.HTTPRedirect(d.ui['page'] + d.ui['login_success_redirect'])

        return ''
    do.exposed = True
        


    # Responds to '/do_backup'
    def do_backup(self, **args):
        """
        Copy a world file from the production location to a backup.         
        """
        validate_token()

        try:
            filename = args['file']
        except KeyError:
            return 'No file specified.'

        if os.path.exists(d.server['world_backup_path']) and os.path.exists(d.server['world_path']):
            now = time.time()
            #global d.backup_time
            if now > d.backup_time + float(d.server['file_backup_buffer']):
                print 'Attempting backup of %s...' % (filename)
                shutil.copyfile(d.server['world_path']+'/'+filename, d.server['world_backup_path']+'/'+filename)
                d.backup_time = now
        else:
            print 'ERROR while backing up file. world_path and/or world_backup_path invalid. Unable to backup world file.'

        page_content = """
            <html><head><script type="text/javascript">
            window.history.back()
            </script></head></html>
            """
        return page_content
    do_backup.exposed = True


# I'm planning on calling this more from initialize()
def get_from_config(config, key1, key2=''):
    r = '' # default value is empty string

    try:
        if key1 == '':
            pass
        elif key2 == '':
            r = config[key1]
        else:
            r = config[key1][key2]
    except KeyError:
        pass
    return r


#### Startup ####
def initialize():
    config = cherrypy.request.app.config


    # [templates] section of config
    for k,v in config['templates'].items():
        tf = load_file(config['static']['templates_path'] + '/' + v['file']) # load templates from file into string
        c = ''
        if 'context_arg' in v:
            c = v['context_arg']
        d.tmpl[k] = Tmpl(name=k, template=tf, auth=v['auth'], context=c)

    # [server] section of config
    d.server.update(config['server'])

    # [ids] section of config
    d.ids.update(config['ids'])

    # [ui] section of config
    d.ui.update(config['ui'])
    d.ui['page'] = '/?' + d.ui['page_argument'] + '='

    # [static] section of config
    d.static.update(config['static'])

    # [ids] section of config
    d.buff_ids = get_from_config(config, 'ids', 'buff_ids')
#    buff_ids = config['ids']['buff_ids']

    # [special tokens] section of config
    d.spec_tokens.update(config['special tokens'])

    # [tokens] section of config
    for token,info in config['tokens'].items():
        t = Token(token)
        t.source = info['source']
        try:
            t.api_key = info['key']
        except KeyError:
            pass
        if 'processor' in info.keys():
            t.processor = info['processor']
        if 'post_processor' in info.keys():
            t.post_processor = info['post_processor']
        if 'cache' in info.keys():
            t.cache = float(info['cache'])
        elif 'default_cache' in config['server']:
            t.cache = float(config['server']['default_cache'])
        if t.source == 'text':
            t.contexts[''] = info['value']
        elif t.source == 'api':
            t.api_endpoint = info['endpoint']
            try:
                t.parameter = info['parameter']
            except KeyError:
                pass
        elif t.source == 'function':
            t.func = info['func']
        d.tm.tokens[token] = t



import os.path
conf = os.path.join(os.path.dirname(sys.argv[0]), application_properties_file)
cherrypy.config.update(conf)
cherrypy.tree.mount(Root(), '/', conf)

cherrypy.engine.start()

initialize()

cherrypy.engine.block()

