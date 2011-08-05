#!/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Joakim Hovlandsvåg <joakim.hovlandsvag@gmail.com>
#
# This file is part of HomebaseTweaks.
# 
# HomebaseTweaks is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HomebaseTweaks is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HomebaseTweaks. If not, see <http://www.gnu.org/licenses/>.
"""
Script for automating the recording of programs at homebase.no, since they don't
support automatic recording of series. It could for instance be run in a cronjob
every other night.

Recorder settings, e.g. logon credentials and what programs to record, should be
put in the file `config.py`.
"""
import sys, os, time, optparse
import urllib, urllib2
from math import ceil
from BeautifulSoup import BeautifulSoup

try:
    import config
except ImportError:
    print "Config not created (config.py)."
    sys.exit(1)

class HomebaseRecord:
    """Class for handling the record communication with homebase."""

    def __init__(self):
        # TODO: add logon credentials as parameters to init?
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        self.opener.addheaders = [('User-Agent', 'HomebaseTweaks - https://github.com/jokim/HomebaseTweaks')]
        urllib2.install_opener(self.opener)
        self.loggedon = False

    def logon(self):
        """Logs on homebase and stores the session cookie."""
        if self.loggedon:
            return
        params = urllib.urlencode({'action': 'login', 
                'username': config.username,
                'password': config.password,
                'savelogin': 'save',})
        page = self.opener.open('https://min.homebase.no/login.php', params)
        # Correctly logged on:
        #   https://min.homebase.no/index.php?userLoggedIn=1 when
        # Failed logon:
        #   https://min.homebase.no/index.php?page=loginform&e=p&username=USERNAME&gotopage=
        if page.url.find('userLoggedIn=1') <= 0:
            raise Exception('Could not log on (username=%s)' % config.username)
        self.loggedon = True

    def record_program(self, id):
        """Set a given program to be recorded."""
        self.logon()
        url = urllib2.urlopen('https://min.homebase.no/epg/lib/addRecording.php?action=add&FR=%s' % id)
        # Sample error messages:
        # ['<br/>Caught by sanitizeInput: Array\n', '(\n', '    [0] => Array\n', '        (\n', '        )\n', '\n', ')\n', '<br/>\n', '\n', 'Du m\xe5 logge inn f\xf8rst.']
        # ['<br/>Caught by sanitizeInput: Array\n', '(\n', '    [0] => Array\n', '        (\n', '        )\n', '\n', ')\n', '<br/>\n', '\n', 'Opptak p\xe5 denne kanalen krever abonnement. Du kan kj\xf8pe et PVR-produkt p\xe5 homebase.no']
        # ['Du m\xe5 logge inn f\xf8rst.']
        #
        # Correct feedback:
        # ['Programmet er blitt satt til opptak.']
        data = url.readlines()
        url.close()
        if data == ['Programmet er blitt satt til opptak.']:
            return True
        print "Failed: %s" % data
        return False

    def get_programs(self, days=1):
        """Return a list of future programs.
        @param days The number of days we should fetch programs from
        """
        # Since each call at epg.php only returns 5.5 hours with shows, we need
        # to loop it 4.36 loops per day.
        #
        # ts  defines the number of days from today (0)
        # ts2 is timestamp to start from
        target = 'ts=0'
        ret = []
        sys.stdout.write("Getting programs")
        for i in range(int(ceil(days * 4.4))):
            sys.stdout.write('.')
            # TODO: should check hour of day, as when ts=0 you only get the rest
            # of the day - not necessary to loop for 24 hours then, but works
            url = urllib2.urlopen('https://min.homebase.no/epg/epg.php?%s' % target)
            soup = BeautifulSoup(''.join(url.readlines()))
            url.close()
            # TODO: check if empty or too further into the future and break
            for prog in soup.findAll('span', {'class': 'progBox'}):
                if not prog.span.span.a['href']:
                    continue
                # e.g: 20110629/nrktv1/20110629204500-20110629205500
                meta = self.parse_id(prog.span.span.a['href'])
                meta['title'] = prog.span.span.a.string
                ret.append(meta)
            for a in soup.findAll('a', {'class': 'nextDay'}):
                target = a['href'].split('?')[1] # = ts2=XXXXXX
        sys.stdout.write('\n')
        return tuple(ret)

    def parse_id(self, tag):
        """Parse an tag into its elements."""
        date, channel, time = tag.split('/')
        start, end = time.split('-')
        return {'id': tag,
                'date': date,
                'channel': channel, 
                'time': time,
                'start': start, 
                'end': end}

    def get_channels(self):
        """Return a dict with the different available channels."""
        url = urllib2.urlopen('https://min.homebase.no/epg/epg.php')
        soup = BeautifulSoup(''.join(url.readlines()))
        channels = {}
        for channel in soup.findAll('div', {'class': 'channelName'}):
            name = channel['id'][1:]
            channels[name] = channel.a.string
        return channels

    def print_channels(self, *args):
        channels = self.get_channels()
        for channel in sorted(channels):
            print "%20s: %s" % (channel, channels[channel])
        # TODO: remove this when model and presenter has been split
        sys.exit()

    def get_time(self, timestr):
        """Convert a time string from homebase to a standard time tuple."""
        return time.strptime(timestr, '%Y%m%d%H%M%S')

    def print_program(self, program):
        """Return a human-readable string of a program."""
        start = time.strftime('%Y-%m-%d %H:%M', self.get_time(program['start']))
        end   = time.strftime('%H:%M', self.get_time(program['end']))
        return u"%s @ %s (%s-%s)" % (program['title'], program['channel'],
                                     start, end)

def main(args):
    # TODO: validate the config? E.g. check that the defined 'channel's exists?
    h = HomebaseRecord()
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action='store_true', default=False, dest='verbose',
                      help="Be more verbose?")
    parser.add_option('--list-channels', 
                      action='callback', callback=h.print_channels,
                      help="list the available channels")
    options, remainder = parser.parse_args()

    # TODO: development, reading in the programstemp.py file with a dump of
    # returned results instead of asking homebase.no each time.
    programs = h.get_programs(1)
    #import programstemp
    #programs = programstemp.p

    #for serie in config.series:
    #    for program in programs:
    #        if serie.has_key('channel') and serie['channel'] != program['channel']:
    #            continue
    #        if serie['title'] == program['title']:
    #            print "Recording: %s" % h.print_program(program)
    #            #h.record_program(program['id'])

if __name__ == '__main__':
    main(sys.argv)
