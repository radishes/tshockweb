import httplib2, cherrypy
import os, sys, time, json, urllib, datetime, shutil, itertools, re, copy, cgi
from util import *
from string import Template
from collections import defaultdict

import extensions

# This exception should be thrown if an invalid REST endpoint format is detected.
class ApiEndpointError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# A template object to hold templates and their metadata.
class Tmpl(object): 
    def __init__(self, name='', template='', auth=False, context=''):
        self.name = name # A string. The name of this template. Example: 'status'
        self.template = template # A string of template data. Example: '<html><body>This is a template!</body></html>'
        self.auth = auth # Boolean. Does this template require authentication to view?
        self.context = context
    def __str__(self):
        return 'name = %s; auth = %s; template(10) = %s;' % (self.name, self.auth, self.template[:9].replace('\n', ''))

# A token in this context represents a variable that can be used in a template to achieve dynamic content functionality.
class Token(object):
    def __init__(self, token):
        self.token = token  # A string. Example: 'PLAYER_IP'
        self.contexts = {} # A dict of values, indexed by context name. Default context is empty string "". Example: { 'radishes': '123.45.67.89' }

        self.cache = 5 # Numeric. Desired maximum time to cache data for this token, in seconds.
        self._timestamps = {} # Key = context; Value = timestamp for that context. Records the last time this bit of data was retrieved from its source.

        # data source information
        self.source = '' # A string. A source type, such as 'api', or 'function'.
        self.parameter = '' # A string. Optionally specify a parameter key for the data source call. Example: parameter of  'player' will result in '&player=sally' for an API call when context is 'sally'.
        # for api sourced tokens
        self.api_endpoint = '' # A string. Examples: '/status', or '/playerinfo'
        self.api_key = '' # A string. Example: 'inventory'

        self.processor = '' # A string - the name of a function to process this data when we read it.
        self.post_processor = '' # A string - the name of a function to process the data just before we serve it.
        # for function sourced tokens
        self.func = '' # A string - the name of a function to call.
    def __str__(self):
        return 'token: %s; contexts: %s' % (self.token, str(self.contexts))
    def __eq__(self, T):
        if self.token == T.token and self.context == T.context:
            return True
        else:
            return False
##        except AttributeError:
##            return False


class Token_Mgr(object):
    def __init__(self):
        self.tokens = {}
    def __str__(self):
        s = ''
        for t in self.tokens.values():
            s += 'Token: %s \n' % (str(t.token))
            s += 'Contexts: %s\n' % (str(t.contexts))
        return s



    def make_str_dict(self, context=''):
        """
        Returns a reduced version of self.tokens in the form of { self.tokens.token: self.tokens.context }
        For use with Template.safe_substitute.
        """
        kv_dict = {}
        for k,v in self.tokens.items():
            if len(v.contexts) == 0:
                continue
         #   try:
            tcontext = context
            if v.parameter == '' and v.source == 'api':
                tcontext = ''
            elif v.processor != '' and v.source == 'function':
        #        tcontext = v.api_key
                tcontext = v.contexts.keys()[0] # hack alert!
            try:
                kv_dict[k] = v.contexts[tcontext]
            except KeyError:
                kv_dict[k] = v.contexts.values()[0] # hack derp
         #   except KeyError:
            pass
        return kv_dict

    def set_from_source(self, token, context):
        """
        Looks at the data source of the specified token and retrieves this token's value from that source.
        In the case fo API calls, all the returned data will be looked at, not just the value needed to
        fulfill this particular request.
        """
        now = time.time()
        results = {}
        t = self.tokens[token]

        if t.source == 'api':
            h = httplib2.Http()
            if t.api_endpoint.startswith('/') == False:
                raise ApiEndpointError(t.api_endpoint)
            api_token_parm = '' # optionally build a 'token=' parameter for passing user's API token
            parm = '' # optionally build a parameter for passing context-specific information, such as a player name
            if 'token' in cherrypy.session: # if the user has an API token, we'll send it with the request
                api_token_parm = '?token=' + cherrypy.session['token']
                if context != '':
                    parm = '&' + urllib.quote(t.parameter) + '=' + urllib.quote(context)
            api_call = d.server['api_url'] + t.api_endpoint + api_token_parm + parm
            #dprint('CALLING URL', api_call)
            resp, content = h.request(api_call)
            results = json.loads(content) # data from the API, in a dict
            if results['status'] == '500':
                print 'ERROR - response code 500 received from API. Error description:', results['error']
            elif results['status'] == '400': # Possibly a 'player not found' or similar error
                print 'ERROR - response code 400 received from API. Error description:', results['error']
            for t2 in self.tokens.values():
                if t2.api_endpoint == t.api_endpoint and t2.api_key in results:
                    t2.contexts[context] = results[t2.api_key]
                    t2._timestamps[context] = now
                    if t2.processor != '': # processor specified - process the data. The processor will store it for us.
                        #t2.contexts[context] = globals()[t2.processor](d, t2.token, results[t2.api_key], context)
                        t2.contexts[context] = getattr(extensions, t2.processor)(d, t2.token, results[t2.api_key], context)
                      #  globals()[t2.processor](t2.token, results[t2.api_key], context)

        elif t.source == 'function':
           # try:
                #r = globals()[t.func]()
                r = getattr(extensions, t.func)(d)
                if t.processor != '':
                    r = getattr(extensions, t.processor)(d, t.token, r, context)
                    #r = globals()[t.processor](d, t.token, r, context)
                t.contexts[context] = r
              #  t.contexts[''] = r
                t._timestamps[context] = now
          #  except:
          #      t.contexts[''] = 'Function %s failed.' % (t.func)



    def get(self, token, context):
        """
        Retrieve a token for use in a template. This will do the magic of
        of looking up the data for this token and storing all the data from the
        API call. (Even the data that's not called for here should be stored.)
        token   : a string corresponding to a pre-defined token.
        context : a string representing some context for this value, such as a player name.
        """
        t = None # shortcut for the token
        now = time.time()
        try:
            if token in self.tokens:
                t = self.tokens[token]
                if context not in t._timestamps:
                    t._timestamps[context] = 0
                time_delta = now - t._timestamps[context]
                if time_delta > t.cache: # is cache TTL expired?
                    # print "%s Retrieving data for token %s from source." % (str(now), token)
                    self.set_from_source(token, context) # cache is expired, let's go to source
            else:
                print 'WARNING: Token %s not found! Context: %s' % (token, str(**args))
        except ApiEndpointError as e:
            print 'Bad API call to:', e

        return t


# just a global variable for passing around the program data :P
class data(object):
    def __init__(self):
        # set from the properties file
        self.ids = {}
        self.tmpl = {}
        self.static = {}
        self.server = {}
        self.ui = {}
        self.spec_tokens = {}
        self.tm = Token_Mgr()
        self.buff_ids = {}

        # globals
        self.last_seen = {} # key: username, value: last time that user was seen
        self.backup_time = 0 # time of the last world file backup

d = data()
