#!/usr/local/bin/python3
'''
------------------------------------------------------------------------
 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI
 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: John Neerdael

 Date Last Updated: 20210419

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
__version__ = '0.5.1'
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
    parser.add_argument('-d', '--database', action="store", help="Path to database file", default='database.bak')
    parser.add_argument('-c', '--customer', action="store", help="Customer name (optional)")
    parser.add_argument('--dump', type=str, default='', help="Dump Object")
    parser.add_argument('--silent', action='store_true', help="Silent Mode")
    parser.add_argument('-v', '--version', action='store_true', help="Silent Mode")
    parser.add_argument('--debug', help="Enable debug logging", action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.INFO)

    return parser.parse_args()

def report_versions():
    '''
    Rerport code and config versions
    '''
    DBCONFIG = dblib.DBCONFIG()
    RCONFIG = dblib.REPORT_CONFIG()
    version_report = { 'main': __version__, 
                       'dblib': dblib.__version__, 
                       'DB Config': DBCONFIG.version(), 
                       'Report Config': RCONFIG.version() 
                      }
    return version_report


def process_onedb(xmlfile, iterations, silent_mode=False):
    '''
    Process onedb.xml
    '''
    # parser = etree.XMLPullParser(target=AttributeFilter())
    report = {}
    object_counts = collections.Counter()
    member_counts = collections.Counter()
    enabled_features = collections.defaultdict(bool)

    report['processed'] = collections.defaultdict(list)
    report['collected'] = collections.defaultdict(list)
    report['counters'] = object_counts
    report['features'] = enabled_features
    report['member_counts'] = collections.defaultdict()
    # node_lease_count = collections.Counter()

    OBJECTS = dblib.DBCONFIG()
    with tqdm.tqdm(total=iterations, disable=silent_mode) as pbar:
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
                            # Action Count
                            if action == 'count':
                                object_counts[obj_value] += 1

                            # Action Enabled
                            elif action == 'feature':
                                feature = OBJECTS.feature(obj_value)
                                keypair = OBJECTS.keypair(obj_value)
                                if not enabled_features[feature]:
                                    if keypair and len(keypair) == 2:
                                        # Assume valid keypair
                                        enabled_features[feature] = dblib.check_feature(elem,
                                                                                        key_name=keypair[0],
                                                                                        expected_value=keypair[1])
                                    else:
                                        # Try default check
                                        enabled_features[feature] = dblib.check_feature(elem)
                                else:
                                    # Feature has already been found
                                    None

                            # Action Process
                            elif action == 'process':
                                process_object = getattr(dblib, OBJECTS.func(obj_value))
                                # onsider using a pandas dataframe
                                response = process_object(elem, count)
                                if response:
                                    report['processed'][obj_value].append(response)

                            # Action Collect 
                            elif action == 'collect':
                                collect_properties = OBJECTS.properties(obj_value)
                                response = dblib.process_object(elem, collect_properties)
                                if response:
                                    report['collected'][obj_value].append(response)

                            # Action Member Count
                            elif action == 'member':
                                process_object = getattr(dblib, OBJECTS.func(obj_value))
                                if obj_type not in report['member_counts'].keys():
                                    report['member_counts'][obj_value] = collections.Counter()
                                member = process_object(elem)
                                if member:
                                    report['member_counts'][obj_value][member] += 1
                                    
                            # Action Not Implemented
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


def output_reports(report, outfile):
    '''
    Generate and output reports
    '''
    OBJECTS = dblib.DBCONFIG()
    REPORT_CONFIG = dblib.REPORT_CONFIG()

    for section in REPORT_CONFIG.report_sections():
        if section in report.keys():
            if section == 'collected':
                collected_dfs = dblib.report_collected(report, REPORT_CONFIG, OBJECTS)
                dblib.output_to_excel(collected_dfs, title='Collected_Properties', filename=outfile)
            elif section == 'processed':
                processed_dfs = dblib.report_processed(report, REPORT_CONFIG, OBJECTS)
                dblib.output_to_excel(processed_dfs, title='Processed_Objects', filename=outfile)
            elif section == 'counters':
                # counters_dfs = dblib.report_counters(report, REPORT_CONFIG, OBJECTS)
                # pprint.pprint(counters_dfs)
                dblib.report_counters(report, REPORT_CONFIG, OBJECTS)
            elif section == 'member_counts':
                # mcounters_dfs = dblib.report_counters(counters_dfs, REPORT_CONFIG, OBJECTS)
                # pprint.pprint(mcounters_dfs
                pprint.pprint(report['member_counts'])
            elif section == 'features':
                pprint.pprint(report['features'])
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


def process_backup(database, outfile, silent_mode=False, dump_obj=None):
    '''
    Determine whether backup File or XML

    Parameters:
        database (str): Filename
        outfile (str): postfix for output files
        silent_mode (bool): Do not log to console
        dump_obj(bool): Dump object from database
    '''
    status = False
    t = time.perf_counter()

    if tarfile.is_tarfile(database):
        # Extract db from backup
        logging.info('EXTRACTING DATABASE FROM BACKUP')
        with tarfile.open(database, "r:gz") as tar:
            xmlfile = tar.extractfile('onedb.xml')
            status = process_file(xmlfile, 
                                  outfile,
                                  silent_mode=silent_mode, 
                                  dump_obj=dump_obj)

        t2 = time.perf_counter() - t
        logging.info(f'EXTRACTED DATABASE FROM BACKUP IN {t2:0.2f}S')
    else:
        # Assume onedb.xml
        logging.info('ATTEMPTING TO PROCESS AS onedb.xml')
        with open(database, 'rb') as xmlfile:
            status = process_file(xmlfile, 
                                  outfile,
                                  silent_mode=silent_mode, 
                                  dump_obj=dump_obj)

    return status


def process_file(xmlfile, outfile, silent_mode=False, dump_obj=False):
    '''
    Process file

    Parameters:
        xmlfile (file): file handler
        outfile (str): postfix for output files
        silent_mode (bool): Do not log to console
        dump_obj(bool): Dump object from database
    '''
    status = False

    if not dump_obj:

        iterations = dblib.rawincount(xmlfile)
        xmlfile.seek(0)
        t3 = time.perf_counter() - t2

        logging.info(f'COUNTED {iterations} OBJECTS IN {t3:0.2f}S')
        writeheaders()

        # searchrootobjects(xmlfile, iterations)
        db_report = process_onedb(xmlfile, iterations, silent_mode=silent_mode)
        output_reports(db_report, outfile)

        t4 = time.perf_counter() - t
        logging.info(f'FINISHED PROCESSING IN {t4:0.2f}S, LOGFILE: {logfile}')
        status = True

    else:
        if dblib.dump_object(dump_obj, xmlfile):
            status = True

    return status


def main():
    '''
    Core logic
    '''
    exitcode = 0
    logfile = ''
    options = parseargs()
    database = options.database

    # Set up logging & reporting
    # log events to the log file and to stdout
    # dateTime=time.strftime("%H%M%S-%d%m%Y")
    dateTime = time.strftime('%Y%m%d-%H%M%S')
    if options.customer:
        outfile = f'{options.customer}-{dateTime}.xlsx'
    else:
        outfile = f'-{dateTime}.xlsx'
    logfile = f'{dateTime}.log'
    file_handler = logging.FileHandler(filename=logfile)
    stdout_handler = logging.StreamHandler(sys.stdout)
    # Output to CLI and config
    handlers = [file_handler, stdout_handler]
    # Output to config only
    filehandler = [file_handler]
    if options.silent:
        logging.basicConfig(
            level=options.loglevel,
            format='%(message)s',
            handlers=filehandler
            )
    else:
        logging.basicConfig(
            level=options.loglevel,
            format='%(message)s',
            handlers=handlers
            )

    # Check run mode
    if options.version:
       v = report_versions()
       pprint.pprint(v)
    else:
       process_backup(database, outfile, silent_mode=options.silent, dump_obj=options.dump)

    return exitcode

### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)