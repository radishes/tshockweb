# This is used to compile an exe with py2exe.
# Run like so: python setup.py py2exe

from distutils.core import setup
import py2exe

py2exe_options = dict(includes=['cherrypy', 'httplib2'],
                      excludes=['pyreadline', 'difflib', 'doctest',
                                'optparse', 'pickle', 'Tkinter']
                      )

setup(console=['tshockweb.py'], options={'py2exe': py2exe_options})
