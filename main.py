#!/usr/local/bin/python3
'''
------------------------------------------------------------------------
 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI
 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: John Neerdael

 Date Last Updated: 20210305

 Copyright (c) 2021 John Neerdael / Infoblox
 Redistribution and use in source and binary forms,
 with or without modification, are permitted provided
 that the following conditions are met:
 1. Redistributions of source code must retain the above copyright
 notice, this list of conditions and the following disclaimer.
 2. Redistributions in binary form must reproduce the above copyright
 notice, this list of conditions and the following disclaimer in the
 documentation and/or other materials provided with the distribution.
 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 CAUSED AND ON ANY THEORY OF LIABILITY, WHetreeHER IN CONTRACT, STRICT
 LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.
------------------------------------------------------------------------
'''
__version__ = '0.3.3'
__author__ = 'John Neerdael, Chris Marrison'
__author_email__ = 'jneerdael@infoblox.com'

import dbobjects
import argparse, tarfile, logging, re, time, sys, tqdm
import collections
import pprint
from itertools import (takewhile,repeat)
from lxml import etree


def parseargs():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Validate NIOS database backup for B1DDI compatibility')
    parser.add_argument('-d', '--database', action="store", help="Path to database file", required=True)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s '+ __version__)
    parser.add_argument('-c', '--customer', action="store", help="Customer name (optional)")
    parser.add_argument('--debug', help="Enable debug logging", action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.INFO)

    return parser.parse_args()


def searchrootobjects(xmlfile, iterations):
    # parser = etree.XMLPullParser(target=AttributeFilter())
    node_lease_count = collections.Counter()
    with tqdm.tqdm(total=iterations) as pbar:
        count = 0
        #xmlfile.seek(0)
        context = etree.iterparse(xmlfile, events=('start','end'))
        for event, elem in context:
            if event == 'start' and elem.tag == 'OBJECT':
                count += 1
                try:
                    object = validateobject(elem)
                    if object == 'dhcpoption':
                        type, parentobj, optionspace, optioncode, hexvalue, optionvalue = processdhcpoption(elem)
                        validatedhcpoption(type, parentobj, optionspace, optioncode, hexvalue, optionvalue, count)
                    elif object == 'dhcpnetwork':
                        address, cidr = processnetwork(elem)
                        validatenetwork(address, cidr, count)
                    elif object == 'dhcplease':
                        node = dhcplease_node(elem)
                        if node:
                            node_lease_count[node] += 1
                    else:
                        None
                except:
                    None
                pbar.update(1)
            elem.clear()

        # Log lease info
        for key in node_lease_count:
            logging.info('LEASECOUNT,{},{}'.format(key, node_lease_count[key]))

    return


def process_onedb(xmlfile, iterations):
    '''
    Process onedb.xml
    '''
    # parser = etree.XMLPullParser(target=AttributeFilter())
    report = collections.defaultdict(list)
    object_counts = collections.Counter()
    member_counts = collections.Counter()
    feature_enabled = collections.defaultdict(bool)

    report['counts'] = object_counts
    report['features'] = feature_enabled
    report['member_counts'] = collections.defaultdict()
    # node_lease_count = collections.Counter()

    OBJECTS = dbobjects.DBOBJECTS()
    with tqdm.tqdm(total=iterations) as pbar:
        count = 0
        #xmlfile.seek(0)
        context = etree.iterparse(xmlfile, events=('start','end'))
        for event, elem in context:
            if event == 'start' and elem.tag == 'OBJECT':
                count += 1
                try:
                    obj_value = dbobjects.get_object_value(elem)
                    obj_type = OBJECTS.obj_type(obj_value)
                    if OBJECTS.included(obj_value):
                        logging.debug('Processing object {}'.format(obj_value))
                        for action in OBJECTS.actions(obj_value):
                            if action == 'count':
                                object_counts[obj_value] += 1
                            elif action == 'enabled':
                                feature_enabled[obj_value] = True
                            elif action == 'process':
                                process_object = getattr(dbobjects, OBJECTS.func(obj_value))
                                # onsider using a pandas dataframe
                                response = process_object(elem, count)
                                if response:
                                    report[obj_value].append(response)
                            elif action == 'member':
                                process_object = getattr(dbobjects, OBJECTS.func(obj_value))
                                if obj_type not in report['member_counts'].keys():
                                    report['member_counts'][obj_type] = collections.Counter()
                                member = process_object(elem)
                                if member:
                                    report['member_counts'][obj_type][member] += 1
                            else:
                                logging.warning('Action: {} not implemented'.format(action))
                                None
                    else:
                        logging.debug('Object: {} not defined'.format(obj_value))
                    
                        
                except:
                    raise
                    print("Shouldn't be here")
                    None
                pbar.update(1)
            elem.clear()

        '''
        # Log lease info
        for key in node_lease_count:
            logging.info('LEASECOUNT,{},{}'.format(key, node_lease_count[key]))
        '''

    return report


def output_reports(report):
    '''
    Generate and output reports
    '''
    pprint.pprint(report)

    return

def writeheaders():
    logging.info('HEADER-DHCPOPTION,STATUS,OBJECTTYPE,OBJECT,OPTIONSPACE,OPTIONCODE,OPTIONVALUE')
    logging.info('HEADER-DHCPNETWORK,STATUS,OBJECT,OBJECTLINE')
    logging.info('HEADER-LEASECOUNT,MEMBER,ACTIVELEASES')
    return


def main():
    '''
    Core logic
    '''
    logfile = ''
    options = parseargs()
    t = time.perf_counter()
    database = options.database

    # Set up logging
    # log events to the log file and to stdout
    dateTime=time.strftime("%H%M%S-%d%m%Y")
    if options.customer != '':
        logfile = f'{options.customer}-{dateTime}.csv'
    else:
        logfile = f'{dateTime}.csv'
    file_handler = logging.FileHandler(filename=logfile)
    stdout_handler = logging.StreamHandler(sys.stdout)
    # Output to CLI and config
    handlers = [file_handler, stdout_handler]
    # Output to config only
    filehandler = [file_handler]
    logging.basicConfig(
        level=options.loglevel,
        format='%(message)s',
        handlers=filehandler
    )

    # Extract db from backup
    print('EXTRACTING DATABASE FROM BACKUP')

    with tarfile.open(database, "r:gz") as tar:
        xmlfile = tar.extractfile('onedb.xml')
        t2 = time.perf_counter() - t
        print(f'EXTRACTED DATABASE FROM BACKUP IN {t2:0.2f}S')

        iterations = dbobjects.rawincount(xmlfile)
        xmlfile.seek(0)
        t3 = time.perf_counter() - t2

        print(f'COUNTED {iterations} OBJECTS IN {t3:0.2f}S')
        writeheaders()
        # searchrootobjects(xmlfile, iterations)
        db_report = process_onedb(xmlfile, iterations)
        output_reports(db_report)

        t4 = time.perf_counter() - t
        print(f'FINISHED PROCESSING IN {t4:0.2f}S, LOGFILE: {logfile}')

    return

if __name__ == '__main__':
    main()