#!/usr/local/bin/python3
'''
------------------------------------------------------------------------
 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI
 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: John Neerdael

 Date Last Updated: 20210407

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
__version__ = '0.4.6'
__author__ = 'John Neerdael, Chris Marrison'
__author_email__ = 'jneerdael@infoblox.com'

import dblib
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


def process_onedb(xmlfile, iterations):
    '''
    Process onedb.xml
    '''
    # parser = etree.XMLPullParser(target=AttributeFilter())
    report = {}
    object_counts = collections.Counter()
    member_counts = collections.Counter()
    feature_enabled = collections.defaultdict(bool)

    report['processed'] = collections.defaultdict(list)
    report['collected'] = collections.defaultdict(list)
    report['counters'] = object_counts
    report['features'] = feature_enabled
    report['member_counts'] = collections.defaultdict()
    # node_lease_count = collections.Counter()

    OBJECTS = dblib.DBCONFIG()
    with tqdm.tqdm(total=iterations) as pbar:
        count = 0
        #xmlfile.seek(0)
        context = etree.iterparse(xmlfile, events=('start','end'))
        for event, elem in context:
            if event == 'start' and elem.tag == 'OBJECT':
                count += 1
                try:
                    obj_value = dblib.get_object_value(elem)
                    obj_type = OBJECTS.obj_type(obj_value)
                    if OBJECTS.included(obj_value):
                        logging.debug('Processing object {}'.format(obj_value))
                        for action in OBJECTS.actions(obj_value):
                            if action == 'count':
                                object_counts[obj_value] += 1

                            elif action == 'feature':
                                feature = OBJECTS.feature(obj_value)
                                keypair = OBJECTS.keypair(obj_value)
                                if not feature_enabled[feature]:
                                    if len(keypair) == 2:
                                        # Assume valid keypair
                                        feature_enabled[feature] = dblib.check_feature(elem,
                                                                                        key_name=keypair[0],
                                                                                        expected_value=keypair[1])
                                    else:
                                        # Try default check
                                        feature_enabled[feature] = dblib.check_feature(elem)
                                else:
                                    # Feature has already been found
                                    None

                            elif action == 'process':
                                process_object = getattr(dblib, OBJECTS.func(obj_value))
                                # onsider using a pandas dataframe
                                response = process_object(elem, count)
                                if response:
                                    report['processed'][obj_value].append(response)

                            elif action == 'collect':
                                collect_properties = OBJECTS.properties(obj_value)
                                response = dblib.process_object(elem, collect_properties)
                                if response:
                                    report['collected'][obj_value].append(response)

                            elif action == 'member':
                                process_object = getattr(dblib, OBJECTS.func(obj_value))
                                if obj_type not in report['member_counts'].keys():
                                    report['member_counts'][obj_value] = collections.Counter()
                                member = process_object(elem)
                                if member:
                                    report['member_counts'][obj_value][member] += 1
                                    
                            else:
                                logging.warning('Action: {} not implemented'.format(action))
                                None
                    else:
                        logging.debug('Object: {} not defined'.format(obj_value))
                    
                        
                except:
                    raise
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
    OBJECTS = dblib.DBCONFIG()
    REPORT_CONFIG = dblib.REPORT_CONFIG()

    for section in REPORT_CONFIG.report_sections():
        if section in report.keys():
            if section == 'collected':
                dblib.report_collected(report, REPORT_CONFIG, OBJECTS)
            elif section == 'processed':
                dblib.report_processed(report, REPORT_CONFIG, OBJECTS)
        else:
            logging.error('Report {} not implemented'.format(section))
            print('Report {} not implemented'.format(section))


    '''
    logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
    logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
    logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
    logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
    logging.info('DHCPNETWORK,INCOMPATIBLE,' + address + '/' + cidr + ',' + str(count))
    logging.info('LEASECOUNT,{},{}'.format(key, node_lease_count[key]))
    '''

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

        iterations = dblib.rawincount(xmlfile)
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