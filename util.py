def load_file(filename):
    with open(filename) as f:
        return f.read()

def tail(f, n=20, offset=None):
    """Reads a n lines from f with an offset of offset lines.  The return
    value is a tuple in the form ``(lines, has_more)`` where `has_more` is
    an indicator that is `True` if there are more lines in the file.
    """
    avg_line_length = 74
    to_read = n + (offset or 0)

    while 1:
        try:
            f.seek(-(avg_line_length * to_read), 2)
        except IOError:
            # woops.  apparently file is smaller than what we want
            # to step back, go to the beginning instead
            f.seek(0)
        pos = f.tell()
        lines = f.read().splitlines()
        if len(lines) >= to_read or pos == 0:
            return '\n'.join(lines[-to_read:offset and -offset or None])
##            return lines[-to_read:offset and -offset or None], \
##                   len(lines) > to_read or pos > 0
        avg_line_length *= 1.3



def dprint(string1, string2='', more=False):
    if str(string2) != '':
        string2 = ': ' + str(string2)
    print '------------'
    print str(string1) + str(string2)
    if more == False:
        print '------------'
