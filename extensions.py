import httplib2, cherrypy
import os, sys, time, json, urllib, datetime, shutil, itertools, re, copy, cgi, operator
from util import *
from string import Template
from collections import defaultdict

import objects


# Processors that can be used with tokens.
# A processor could take a bit of data, break it up into parts, and create tokens from the parts.
# The processor should return its data in a format in a list or dict, or similar.
def commalist(d, token, data, context=''):
    """
    Example
    Input: token = 'SERVER_PLAYER_LIST_PLAYER_#', data = 'player1, player2'
    Creates tokens: { 'SERVER_PLAYER_LIST_PLAYER_1': 'player1', 'SERVER_PLAYER_LIST_PLAYER_2': 'player2' }
    """
    separated_items = []
    for i,v in enumerate(data.split(', ')):
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        tok = objects.Token(t)
        tok.source = 'text'
        tok.contexts[context] = v
        tok._timestamps[context] = time.time()
        d.tm.tokens[t] = tok
        separated_items.append(v)
    return separated_items

def inventory_name(d, token, data, context=''):
    separated_items = []
    for i,item_q in enumerate(data.split(', ')):
        item,qty = item_q.split(':')
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        tok.contexts[context] = item
        tok._timestamps[context] = time.time()
        separated_items.append(tok.contexts[context])
    return separated_items

def inventory_qty(d, token, data, context=''):
    separated_items = []
    for i,item_q in enumerate(data.split(', ')):
        item,qty = item_q.split(':')
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        tok.contexts[context] = qty
        tok._timestamps[context] = time.time()
        separated_items.append(tok.contexts[context])
    return separated_items

def inventory_image(d, token, data, context=''):
    config = cherrypy.request.app.config
    separated_items = []
    for i,item_q in enumerate(data.split(', ')):
        item,qty = item_q.split(':')
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        tok.contexts[context] = d.static['items_images_path'] +'/'+ item.replace(' ', '_') + '.png'
        tok._timestamps[context] = time.time()
        separated_items.append(tok.contexts[context])
    return separated_items

def buff_name(d, token, data, context=''):
    separated_items = []
    for i,buff in enumerate(data.split(', ')):
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        try:
            tok.contexts[context] = d.ids['buff_ids'][buff]
        except KeyError:
            print 'ERROR processing buff id #%s' % (buff)
        tok._timestamps[context] = time.time()
        separated_items.append(tok.contexts[context])
    return separated_items

def filter_world_files(d, token, data, context=''):
    # data is a list of dicts
    i = 0;
    for i,v in enumerate(data):
        now = time.time()
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        api_key = d.tm.tokens[token].api_key
        tok.contexts[v['filename']] = v[api_key]
        tok._timestamps[v['filename']] = now
    d.tm.tokens[token].contexts[context] = i+1
    return i+1

def filter_last_seen(d, token, data, context=''):
    # data is a dict of { name: last time seen } of each user
    data_sorted = sorted(data.iteritems(), key=operator.itemgetter(1), reverse=True)
    print 'Data Sorted: %s' % (data_sorted)
    for i,kv in (enumerate(data_sorted)):
        t = token.replace(d.spec_tokens['pattern_enumerator'], str(i+1))
        if t not in d.tm.tokens:
            d.tm.tokens[t] = objects.Token(t)
        tok = d.tm.tokens[t]
        tok.source = 'text'
        api_key = d.tm.tokens[token].api_key
        if api_key == 'key':
            tok.contexts[context] = kv[0]
        if api_key == 'value':
            v = kv[1]
            amount = int(time.time() - v)
            word = 'ago'
            unit = ''
            if amount < 60: # if less than a minute since we last saw this user
                amount = 'less than a minute ago'
                unit = ''
                word = ''
            elif amount < 60 * 60: # if more than a minute, but less than an hour since we last saw them
                amount = int(amount / 60)
                unit = 'minutes'
            elif amount < 60 * 60 * 24: # if within the past day
                amount = int((amount / 60) / 60)
                unit = 'hours'
            elif amount < 60 * 60 * 24 * 7:
                amount = int((amount / 60) / 60 / 24)
                unit = 'days'
            elif amount < 60 * 60 * 24 * 7 * 4:
                amount = int((amount / 60) / 60 / 24 / 7)
                unit = 'weeks'
            elif amount < 60 * 60 * 24 * 7 * 4 * 12:
                amount = int((amount / 60) / 60 / 24 / 7 / 4)
                unit = 'months'
            elif amount >= 60 * 60 * 24 * 7 * 4 * 12:
                amount = int((amount / 60) / 60 / 24 / 7 / 4 / 12)
                unit = 'years' # lol
            if amount == 1 and unit.endswith('s'): # fix plural if amount is 1
                unit = unit[:-1]
            v = '%s %s %s' % (str(amount), unit, word)
            tok.contexts[context] = v
                
    d.tm.tokens[token].contexts[context] = i+1
    return i+1



# Functions for function tokens


def last_seen(d):
    return d.last_seen
##    ls = {}
##    for k,v in d.last_seen.items():
##        amount = int(time.time() - v)
##        word = 'ago'
##        unit = ''
##        if amount < 60: # if less than a minute since we last saw this user
##            ls[k] = 'less than a minute ago'
##            continue
##            #amount = 'less than a minute ago'
##            #unit = ''
##            #word = ''
##        elif amount < 60 * 60: # if more than a minute, but less than an hour since we last saw them
##            amount = int(amount / 60)
##            unit = 'minutes'
##        elif amount < 60 * 60 * 24: # if within the past day
##            amount = int((amount / 60) / 60)
##            unit = 'hours'
##        elif amount < 60 * 60 * 24 * 7:
##            amount = int((amount / 60) / 60 / 24)
##            unit = 'days'
##        elif amount < 60 * 60 * 24 * 7 * 4:
##            amount = int((amount / 60) / 60 / 24 / 7)
##            unit = 'weeks'
##        elif amount < 60 * 60 * 24 * 7 * 4 * 12:
##            amount = int((amount / 60) / 60 / 24 / 7 / 4)
##            unit = 'months'
##        elif amount >= 60 * 60 * 24 * 7 * 4 * 12:
##            amount = int((amount / 60) / 60 / 24 / 7 / 4 / 12)
##            unit = 'years' # lol
##        else:
##            continue # bad value somehow, just skip it (shouldn't ever happen)
##
##        if amount == 1 and unit.endswith('s'): # fix plural if amount is 1
##            unit = unit[:-1]
##        ls[k] = '%s %s %s' % (str(amount), unit, word)
##        
##    return ls


def timestamp(d):
    return str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def log_tail(d):
    ## Snippet from the internet for listing all files in a directory, sorted by modification date
    from stat import S_ISREG, ST_MTIME, ST_MODE, ST_SIZE
    # path to the directory (relative or absolute)
    dirpath = d.server['log_path']
    # get all entries in the directory w/ stats
    try:
        entries = (os.path.join(dirpath, fn) for fn in os.listdir(dirpath))
    except OSError:
        print 'Error processing log_tail. Unable to access %s.' % (dirpath)
        return ''
    entries = ((os.stat(path), path) for path in entries)
    # leave only regular files, insert creation date
    entries = ((stat[ST_MTIME], stat[ST_SIZE], path)
               for stat, path in entries if S_ISREG(stat[ST_MODE]))
    lastlog = ''
    for mdate, size, path in sorted(entries, reverse=True):
        if str(os.path.basename(path)).endswith(d.server['log_ext']):
            lastlog = path
            break

    try:
        with open(lastlog) as f:
            #tailed = tail(f).replace('\n','<br>\n')
            tailed = tail(f)
    except IOError:
        print 'Error processing log_tail. Unable to access %s.' % (lastlog)
        return ''
    return tailed 


def get_session_username(d):
    return cherrypy.session['username']


def world_files_table(d):
    # get world file data
    ## Snippet from the internet for listing all files in a directory, sorted by modification date
    from stat import S_ISREG, ST_MTIME, ST_MODE, ST_SIZE
    # path to the directory (relative or absolute)
    dirpath = d.server['world_path']
    # get all entries in the directory w/ stats
    try:
        entries = (os.path.join(dirpath, fn) for fn in os.listdir(dirpath))
    except OSError:
        print 'Error processing world_files_table. Unable to access %s.' % (dirpath)
        return ''
    entries = ((os.stat(path), path) for path in entries)
    # leave only regular files, insert creation date
    entries = ((stat[ST_MTIME], stat[ST_SIZE], path)
               for stat, path in entries if S_ISREG(stat[ST_MODE]))
    ##
    total_size = 0
    files = []
    for mdate, size, path in sorted(entries, reverse=True):
        di = {}
        di['filename'] = str(os.path.basename(path))
        di['mdate'] = str(time.ctime(mdate))
        di['size_mb'] = '%10.1f' % float(((size)/1024.0)/1024.0)
        files.append(di)

    return files




# Post-Processors
# These should be kept lightweight, because they get called every time a page is loaded, even if they're not used on that page.

def line_break_to_br(data):
    return data.replace('\n', '<br>\n')












    
