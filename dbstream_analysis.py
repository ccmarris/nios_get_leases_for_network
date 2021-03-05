#!/usr/local/bin/python3
'''
------------------------------------------------------------------------

 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI

 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: John Neerdael

 Date Last Updated: 20210227

 Changelog:
 - 0.1.0: Created new definitions to allow support for more objects and moved logfile to a CSV file
 - 0.2.0: Added support for /32 networks
 - 0.2.1: Test with lxml as XML parser for increased speed and performance
 - 0.2.2: Clean-up old code snippets
 - 0.2.3: Added demo code for using iterparse instead of parse (stream vs load database to memory)
 - 0.3.0: Forked to seperate version for testing iterparse

 ToDo:
 - Move code to use a iterparse loop for increased efficiency and memory usage and test speed on big databases

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
__version__ = '0.2.5'
__author__ = 'John Neerdael, Chris Marrison'
__author_email__ = 'jneerdael@infoblox.com'

import argparse, tarfile, logging, re, time, sys, tqdm
from itertools import (takewhile,repeat)
from lxml import etree


def parseargs():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Validate NIOS database backup for B1DDI compatibility')
    parser.add_argument('-d', '--database', action="store", help="Path to database file", required=True)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s '+ __version__)
    parser.add_argument('-c', '--customer', action="store", help="Customer name (optional)")

    return parser.parse_args()


def rawincount(filename):
    bufgen = takewhile(lambda x: x, (filename.raw.read(1024*1024) for _ in repeat(None)))
    return sum( buf.count(b'\n') for buf in bufgen )


def processdhcpoption(xmlobject):
    parent = optiondef = value = ''
    for property in xmlobject:
        if property.attrib['NAME'] == 'parent':
            parent = property.attrib['VALUE']
        elif property.attrib['NAME'] == 'option_definition':
            optiondef = property.attrib['VALUE']
        elif property.attrib['NAME'] == 'value':
            value = property.attrib['VALUE']
    type, parentobj = checkparentobject(parent)
    optionspace, optioncode = checkdhcpoption(optiondef)
    hexvalue, optionvalue = validatehex(value)
    return type, parentobj, optionspace, optioncode, hexvalue, optionvalue


def processnetwork(xmlobject):
    cidr = address = ''
    for property in xmlobject:
        if property.attrib['NAME'] == 'cidr':
            cidr = property.attrib['VALUE']
        elif property.attrib['NAME'] == 'address':
            address = property.attrib['VALUE']
    return address, cidr


def validateobject(xmlobject):
    object = ''
    for property in xmlobject:
        if property.attrib['NAME'] == '__type' and property.attrib['VALUE'] == '.com.infoblox.dns.option':
            object = 'dhcpoption'
            log.debug("Type = {}, Attirb = {}".format(object, property.attrib))
        elif property.attrib['NAME'] == '__type' and property.attrib['VALUE'] == '.com.infoblox.dns.network':
            object = 'dhcpnetwork'
            log.debug("Type = {}, Attirb = {}".format(object, property.attrib))
        elif property.attrib['NAME'] == '__type' and property.attrib['VALUE'] != '.com.infoblox.dns.option':
            object = ''

    return object


def checkparentobject(parent):
    objects = re.search(r"(.*)\$(.*)", parent)
    if objects.group(1) == '.com.infoblox.dns.network':
        type = 'NetreeWORK'
        parentobj = re.sub(r'\/0$', '', objects.group(2))
        return type, parentobj
    elif objects.group(1) == '.com.infoblox.dns.fixed_address':
        type = 'FIXEDADDRESS'
        parentobj = re.sub(r'\.0\.\.$', '', objects.group(2))
        return type, parentobj
    elif objects.group(1) == '.com.infoblox.dns.dhcp_range':
        type = 'DHCPRANGE'
        parentobj = re.sub(r'\/\/\/0\/$', '', objects.group(2))
        return type, parentobj


def checkdhcpoption(dhcpoption):
    optioncodes = re.search(r"^(.*)\.\.(true|false)\.(\d+)$", dhcpoption)
    optionspace = optioncodes.group(1)
    optioncode = int(optioncodes.group(3))
    return optionspace, optioncode


def validatehex(values):
    if re.search(r"^[0-9a-fA-F:\s]*$", values):
        # Normalize the HEX
        values = values.replace(':', '')
        values = values.replace(' ', '')
        values = values.lower()
        list = iter(values)
        values = ':'.join(a + b for a, b in zip(list, list))
        hexvalue = True
        return hexvalue, values
    else:
        hexvalue = False
        return hexvalue, values


def validatedhcpoption(type, parentobj, optionspace, optioncode, hexvalue, optionvalue):
    incompatible_options = [ 12, 124, 125, 146, 159, 212 ]
    validate_options = [ 43 ]
    if optioncode in incompatible_options:
        logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue)
    elif optioncode in validate_options:
        if hexvalue == True:
            logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue)
        elif hexvalue == False:
            logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue)
    elif optioncode == 151:
        logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue)
    else:
        None


def validatenetwork(address, cidr):
    if cidr == '32':
        logging.info('DHCPNetreeWORK,INCOMPATIBLE,' + address + '/' + cidr)
    else:
        None


def searchrootobjects(xmlfile, iterations):
    # parser = etree.XMLPullParser(target=AttributeFilter())
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
                        validatedhcpoption(type, parentobj, optionspace, optioncode, hexvalue, optionvalue)
                    elif object == 'dhcpnetwork':
                        address, cidr = processnetwork(elem)
                        validatenetwork(address, cidr)
                    else:
                        None
                except:
                    None

            pbar.update(1)
            elem.clear()
    return


def writeheaders():
    logging.info('HEADER-DHCPOPTION,STATUS,OBJECTTYPE,OBJECT,OPTIONSPACE,OPTIONCODE,OPTIONVALUE')
    logging.info('HEADER-DHCPNetreeWORK,STATUS,OBJECT')
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
        level=logging.INFO,
        format='%(message)s',
        handlers=filehandler
    )

    # Extract db from backup
    print('EXTRACTING DATABASE FROM BACKUP')
    with tarfile.open(database, "r:gz") as tar:
        #tar = tarfile.open(options.database, "r:gz")
        xmlfile = tar.extractfile('onedb.xml')
        t2 = time.perf_counter() - t
        print(f'EXTRACTED DATABASE FROM BACKUP IN {t2:0.2f}S')

        iterations = rawincount(xmlfile)
        xmlfile.seek(0)
        t3 = time.perf_counter() - t2
        print(f'COUNTED {iterations} OBJECTS IN {t3:0.2f}S')
        writeheaders()
        searchrootobjects(xmlfile, iterations)
        t4 = time.perf_counter() - t
        print(f'FINISHED PROCESSING IN {t4:0.2f}S, LOGFILE: {logfile}')

    return
'''
    count = 0
    xmlfile.seek(0)
    for event, elem in etree.iterparse(xmlfile):
        if event == 'end':
            if elem.tag == 'OBJECT':
                count += 1
        elem.clear()
    print(count)
'''

if __name__ == '__main__':
    main()
