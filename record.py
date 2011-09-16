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
put in a file `config.py`. See config.example.py for the config variables.

TODO: be able to specify the config file.
"""
import sys, os, time, logging

import urllib, urllib2
from math import ceil
from BeautifulSoup import BeautifulSoup

try:
    import argparse
    has_argparse = True
except ImportError:
    has_argparse = False


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
        logging.debug('Logging on as: %s', config.username)
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

    def record_programs(self, days=None):
        """Find all the available programs and record those that match the
        selectors from config."""
        self.get_record_list()
        programs = self.get_programs(days)
        for serie in config.series:
            for program in programs:
                if serie.has_key('channel') and serie['channel'] != program['channel']:
                    continue
                if serie.has_key('dow') and time.strptime(program['date'],
                                              '%Y%m%d').tm_wday != serie['dow']:
                    continue
                if serie.has_key('title') and serie['title'] != program['title']:
                    continue
                if (serie.has_key('title_regex') and
                        not re.match(serie['title_regex'], program['title'])):
                    continue
                self.record_program(program)

    def record_program(self, program):
        """Set a given program to be recorded."""
        self.logon()
        if program['id'] in self.already_recorded:
            logging.info("Already recorded: %s", self.print_program(program))
            return True
        logging.info('Recording %s', self.print_program(program))
        url = urllib2.urlopen('https://min.homebase.no/epg/lib/addRecording.php',
                       urllib.urlencode({'action': 'add', 'FR': program['id']}))
        # Sample error messages:
        # ['<br/>Caught by sanitizeInput: Array\n', '(\n', '    [0] => Array\n', '        (\n', '        )\n', '\n', ')\n', '<br/>\n', '\n', 'Du m\xe5 logge inn f\xf8rst.']
        # ['<br/>Caught by sanitizeInput: Array\n', '(\n', '    [0] => Array\n', '        (\n', '        )\n', '\n', ')\n', '<br/>\n', '\n', 'Opptak p\xe5 denne kanalen krever abonnement. Du kan kj\xf8pe et PVR-produkt p\xe5 homebase.no']
        # ['Du m\xe5 logge inn f\xf8rst.']
        #
        # Correct feedback:
        # ['Programmet er blitt satt til opptak.']
        data = url.readlines()
        url.close()
        logging.debug("record_program: returned answer: %s", data)
        if data == ['Programmet er blitt satt til opptak.']:
            return True
        logging.warning("Failed recording %s: %s", program['id'], data)
        return False

    def get_programs(self, days=None):
        """Return a list of future programs.
        @param days The number of days we should fetch programs from
        """
        if not days:
            days = getattr(config, 'days', 1)
        # Since each call at epg.php only returns 5.5 hours with shows, we need
        # to loop it 4.36 loops per day.
        #
        # ts  defines the number of days from today (0)
        # ts2 is timestamp to start from
        logging.info("Getting programs for %s days (%d calls)", days, int(ceil(days*4.4)))
        target = 'ts=0'
        ret = []
        for i in range(int(ceil(days * 4.4))):
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
                meta = self.parse_id(unicode(prog.span.span.a['href']))
                meta['title'] = unicode(prog.span.span.a.string)
                ret.append(meta)
            for a in soup.findAll('a', {'class': 'nextDay'}):
                target = a['href'].split('?')[1] # = ts2=XXXXXX
        return tuple(ret)

    def get_record_list(self):
        """Get the list from homebase.no of the programs that is already
        recorded or set to be recorded."""
        # TODO: not sure if this works perfectly. Maybe programs are split into
        # several pages, if there are a lot of them?
        logging.debug('Getting already recorded programs')
        if not hasattr(self, 'already_recorded'):
            self.already_recorded = list()
        if self.already_recorded:
            return
        self.logon()
        url = urllib2.urlopen('https://min.homebase.no/index.php?page=storage')
        soup = BeautifulSoup(''.join(url.readlines()))
        for program in soup.findAll('input', {'type': 'hidden', 'name': 'pid[]'}):
            logging.debug("Getting already recorded: %s", program['value'])
            self.already_recorded.append(program['value'])

    def parse_id(self, tag):
        """Parse an id tag into its elements.
        
        Example id: 20110629/nrktv1/20110629204500-20110629205500"""
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
            name = unicode(channel['id'][1:])
            channels[name] = unicode(channel.a.string)
        return channels

    def print_channels(self):
        channels = self.get_channels()
        for channel in sorted(channels):
            print "%20s: %s" % (channel.encode('utf8'),
                                channels[channel].encode('utf8'))

    def get_time(self, timestr):
        """Convert a time string from homebase to a standard time tuple."""
        return time.strptime(timestr, '%Y%m%d%H%M%S')

    def print_program(self, program):
        """Return a human-readable string of a program."""
        start = time.strftime('%Y-%m-%d %H:%M', self.get_time(program['start']))
        end   = time.strftime('%H:%M', self.get_time(program['end']))
        return u"%s @ %s (%s-%s)" % (program['title'],
                                    program['channel'],
                                    start, end)

    def print_programs(self, days=None):
        """Get all the programs from the given days and print them out."""
        if not days:
            days = getattr(config, 'days', 1)
        programs = self.get_programs(days=days)
        for prog in sorted(programs, key=lambda x: x['title']):
            print self.print_program(prog).encode('utf8')

def main(args):
    # TODO: validate the config? E.g. check that the defined 'channel's exists?
    parser = argparse.ArgumentParser(description="Set programs/series to record at homebase.no.")
    parser.add_argument('-v', '--verbose',
                      action='store_true', dest='verbose',
                      help="Be more verbose?")
    parser.add_argument('--debug', type=int, default=0,
                      help="Print debug info, 1 gives INFO, 2+ gives DEBUG level")
    parser.add_argument('--days', type=float,
                        help="set the number of days to check programs")
    parser.add_argument('--list-channels', action='store_true', 
                        help="list the available channels and exit")
    parser.add_argument('--list-programs', action='store_true', 
                        help="list the available programs and exit")
    # TODO: add argument for setting config file

    # TODO: add support for "already recorded"-file, where all the programs set
    #       to be recorded are put. Those are not set to be recorded anymore.
    #       This is to avoid that programs deleted from the record list are put
    #       back in again later on.

    args = parser.parse_args()

    if args.debug >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.INFO)

    h = HomebaseRecord()

    if args.list_channels:
        h.print_channels()
        sys.exit()
    if args.list_programs:
        h.print_programs(args.days)
        sys.exit()
    h.record_programs(args.days)

def main_deprecated(args):
    """The deprecated version of main, if argparse can't be imported. Supports
    only some standard behaviour."""
    if '-h' in args or '--help' in args:
        print """Options: --list-programs or --list-channels

        Install python-argparse to make full use of this program.
        
        """
        sys.exit()

    debug = 0
    for arg in args:
        if arg == '--debug':
            debug += 1

    if debug >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif debug >= 1:
        logging.basicConfig(level=logging.INFO)

    h = HomebaseRecord()
    if '--list-programs' in args:
        h.print_programs()
        sys.exit()
    if '--list-channels' in args:
        h.print_channels()
        sys.exit()
    h.record_programs()

if __name__ == '__main__':
    if has_argparse:
        main(sys.argv)
    else:
        print "Missing argparse module, using deprecated main version"
        main_deprecated(sys.argv)
