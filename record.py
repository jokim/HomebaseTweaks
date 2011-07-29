#!/bin/env python
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
import getopt, sys, os
import urllib, urllib2
from BeautifulSoup import BeautifulSoup

import config

class HomebaseRecord:
    """Class for handling the record communication with homebase."""

    def __init__(self):
        # TODO: add logon credentials as parameters to init?
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        urllib2.install_opener(self.opener)
        if not self.logon():
            raise Exception("Could not log on")

    def logon(self):
        """Logs on homebase and stores the session cookie."""
        # TODO: do not store the password here!
        username = config.username
        password = config.password
        params = urllib.urlencode({'action': 'login', 
                'username': username,
                'password': password,
                'savelogin': 'save',})
        page = self.opener.open('https://min.homebase.no/login.php', params)
        # Correctly logged on:
        #   https://min.homebase.no/index.php?userLoggedIn=1 when
        # Failed logon:
        #   https://min.homebase.no/index.php?page=loginform&e=p&username=USERNAME&gotopage=
        return page.url.find('userLoggedIn=1') > 0

    def record_program(self, id):
        """Set a given program to be recorded."""
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

    def get_programs(self, daysfromnow=0):
        """Return a list of the shown programs on a given day."""
        # ts2 is timestamp to get the next few (six?) hours with shows
        target = 'ts=0'# %d' % daysfromnow
        ret = []
        for i in range((daysfromnow + 1) * 5): # each run views 5.5 hours
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
                target = a['href'].split('?')[1]
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
        pass

    def print_program(self, program):
        """Return a human-readable string of a program."""
        return u"%s (%s) [%s-%s]" % (program['title'], program['channel'],
                                    program['start'], program['end'])

def main(args):
    #for p in get_programs():
    #    print "%20s %s" % (p['href'], p['title'])
    h = Homebase()
    programs = h.get_programs(1)
    for serie in config.series:
        for program in programs:
            if serie.has_key('channel') and serie['channel'] != program['channel']:
                continue
            if serie['title'] == program['title']:
                print "Recording %s - %s" % (program['title'], program['id'])
                h.record_program(program['id'])
    #print h.record_program('20110703/tv2/20110703173500-20110703180000')
    for p in programs:
        print h.print_program(p)

if __name__ == '__main__':
    main(sys.argv)
