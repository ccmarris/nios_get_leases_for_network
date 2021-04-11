
#!/usr/local/bin/python3
'''
------------------------------------------------------------------------
 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI

 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: Chris Marrison & John Neerdael

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
__version__ = '0.4.7'
__author__ = 'Chris Marrison, John Neerdael'
__author_email__ = 'chris@infoblox.com, jneerdael@infoblox.com'

import tarfile, logging, re, time, sys, tqdm
import os
import collections
import yaml
import pandas as pd
import pprint
from lxml import etree
from itertools import (takewhile,repeat)


class DBCONFIG():
    '''
    Define Class for onedb.xml db objects
    '''

    def __init__(self, cfg_file='objects.yaml'):
        '''
        Initialise Class Using YAML config
        '''
        self.config = {}
   
        # Check for inifile and raise exception if not found
        if os.path.isfile(cfg_file):
            # Attempt to read api_key from ini file
            try:

                self.config = yaml.safe_load(open(cfg_file, 'r'))
            except yaml.YAMLError as err:
                logging.error(err)
                raise
        else:
            logging.error('No such file {}'.format(cfg_file))
            raise FileNotFoundError('YAML object file "{}" not found.'.format(cfg_file))

        return

    def keys(self):
        return self.config.keys()

    def objects(self):
        return self.config['objects'].keys()


    def obj_keys(self, dbobj):
        '''
        Return Objects Keys
        '''
        if self.included(dbobj):
             response = self.config['objects'][dbobj].keys()
        else:
            response = None
        
        return response


    def count(self):
        return len(self.config['objects'])  


    def included(self, dbobj):
        '''
        Check whether this dbobj is configured
        '''
        status = False
        if dbobj in self.objects():
            status = True
        else:
            status = False

        return status


    def obj_type(self, dbobj):
        '''
        Return simple name of object
        '''
        t = None
        if self.included(dbobj):
            t = self.config['objects'][dbobj]['type']
        else:
            t = None
        
        return t


    def header(self, dbobj):
        '''
        Return name of function for dbobj
        '''
        if self.included(dbobj):
            if 'header' in self.config['objects'][dbobj]:
                header = self.config['objects'][dbobj]['header']
            else:
                header = ''
        else:
            header = ''
            # Consider raising KeyError Exception

        return header


    def actions(self, dbobj):
        '''
        Get list of actions for dbobj
        '''
        actions = []
        if self.included(dbobj):
            actions = self.config['objects'][dbobj]['actions']
        else:
            actions = []
        
        return actions
    

    def func(self, dbobj):
        '''
        Return name of function for dbobj
        '''
        if self.included(dbobj):
            if 'func' in self.config['objects'][dbobj]:
                function = self.config['objects'][dbobj]['func']
            else:
                function = None
        else:
            function = None
            # Consider raising KeyError Exception

        return function


    def properties(self, dbobj):
        return self.config['objects'][dbobj]['properties']


    def feature(self, dbobj):
        '''
        Return 'feature' value if exists
        '''
        if self.included(dbobj):
            if 'feature' in self.obj_keys(dbobj):
                r = self.config['objects'][dbobj]['feature']
            else:
                r = None
        else:
            r = None
        
        return r


    def keypair(self, dbobj):
        '''
        Return Keypair as a list
        '''
        if 'keypair' in self.obj_keys(dbobj):
            response = self.config['objects'][dbobj]['keypair']
        else:
            response = None
        
        return response


    def report_types(self, dbobj):
        '''
        Return list of reports for dbobj
        '''
        reports = []
        if self.included(dbobj):
            reports = self.config['objects'][dbobj]['reports']
        else:
            reports = None
        
        return actions


    def incompatible_options(self):
        return self.config['incompatible_options']
   

    def validate_options(self):
        return self.config['validate_options']


class REPORT_CONFIG():
    '''
    Define Class for reporting db objects
    '''

    def __init__(self, cfg_file='report_config.yaml'):
        '''
        Initialise Class Using YAML config
        '''
        self.config = {}
   
        # Check for inifile and raise exception if not found
        if os.path.isfile(cfg_file):
            # Attempt to read api_key from ini file
            try:

                self.config = yaml.safe_load(open(cfg_file, 'r'))
            except yaml.YAMLError as err:
                logging.error(err)
                raise
        else:
            logging.error('No such file {}'.format(cfg_file))
            raise FileNotFoundError('YAML object file "{}" not found.'.format(cfg_file))

        return

    def report_sections(self):
        return self.config['report_sections']
  

# *** Functions ***

def check_feature(xmlobject, key_name='enabled', expected_value='true'):
    '''
    Check for feature enabled
    '''
    enabled = None
    for property in xmlobject:
        if property.attrib['NAME'] == key_name:
            if property.attrib['VALUE'] == expected_value:
                enabled = True
            else:
                enabled = False
            break
        else:
            enabled = None
    return enabled


def process_object(xmlobject, collect_properties):
    '''
    Generic Object Capture

    Parameters:
        xmlobject (obj): XML Object
        collect_properties (list): list of XML Properties to collect

    Returns:
        Dictionary of properties
    '''
    collected_data = collections.defaultdict()
    for property in xmlobject:
        if property.attrib['NAME'] == '__type':
            obj_value = property.attrib['VALUE']
        if property.attrib['NAME'] in collect_properties:
            collected_data[property.attrib['NAME']] = property.attrib['VALUE'] 
    return collected_data


def dump_object(xmlobject):
    '''
    Generic Object Capture

    Parameters:
        xmlobject (obj): XML Object

    Returns:
        Dictionary of properties
    '''
    collected_properties = collections.defaultdict()
    for property in xmlobject:
        obj_value = property.attrib['VALUE']
        collected_properties[property.attrib['NAME']] = property.attrib['VALUE'] 
    pprint.pprint(collected_properties)

    return collected_properties


def processdhcpoption(xmlobject, count):
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

    report = validatedhcpoption(type, parentobj, optionspace, optioncode, hexvalue, optionvalue, count)
    if len(report) == 1 and report[0] == '':
        report = None

    return report


def process_network(xmlobject, count):
    cidr = address = ''
    for property in xmlobject:
        if property.attrib['NAME'] == 'cidr':
            cidr = property.attrib['VALUE']
        elif property.attrib['NAME'] == 'address':
            address = property.attrib['VALUE']
    report = validatenetwork(address, cidr, count)
    if len(report) == 1 and report[0] == '':
        report = None
    return report


def process_leases(xmlobject, count):
    return

"""
def process_zone(xmlobject, count):
    '''
    Process zone info
    '''
    ztype = ''
    zone = ''
    for property in xmlobject:
        if property.attrib['NAME'] == 'zone_type':
            ztype = property.attrib['VALUE']
        if property.attrib['NAME'] == 'display_name':
            zone = property.attrib['VALUE']
    return [ zone, ztype, count ]
"""


def rawincount(filename):
    bufgen = takewhile(lambda x: x, (filename.raw.read(1024*1024) for _ in repeat(None)))
    return sum( buf.count(b'\n') for buf in bufgen )


def validateobject(xmlobject):
    '''
    Validate object type
    '''
    object = ''
    for property in xmlobject:
        if property.attrib['NAME'] == '__type' and property.attrib['VALUE'] == '.com.infoblox.dns.option':
            object = 'dhcpoption'
            break
        elif property.attrib['NAME'] == '__type' and property.attrib['VALUE'] == '.com.infoblox.dns.network':
            object = 'dhcpnetwork'
            break
        elif property.attrib['NAME'] == '__type' and property.attrib['VALUE'] == '.com.infoblox.dns.lease':
            object = 'dhcplease'
            break
        elif property.attrib['NAME'] == '__type':
            object = ''
            break
    return object

def get_object_value(xmlobject):
    '''
    Return the object value
    '''
    obj = ''
    for property in xmlobject:
        if property.attrib['NAME'] == '__type':
            obj = property.attrib['VALUE']
            break
    
    return str(obj)

def checkparentobject(parent):
    objects = re.search(r"(.*)\$(.*)", parent)
    type = parentobj = ''
    if objects:
        if objects.group(1) == '.com.infoblox.dns.network':
            type = 'NETWORK'
            parentobj = re.sub(r'\/0$', '', objects.group(2))
        elif objects.group(1) == '.com.infoblox.dns.fixed_address':
            type = 'FIXEDADDRESS'
            parentobj = re.sub(r'\.0\.\.$', '', objects.group(2))
        elif objects.group(1) == '.com.infoblox.dns.dhcp_range':
            type = 'DHCPRANGE'
            parentobj = re.sub(r'\/\/\/0\/$', '', objects.group(2))
        elif objects.group(1) == '.com.infoblox.dns.network_container':
            type = 'NETWORKCONTAINER'
            parentobj = re.sub(r'\/0$', '', objects.group(2))
    else:
        type = ''
        parentobj = ''

    return type, parentobj


def checkdhcpoption(dhcpoption):
    optioncodes = re.search(r"^(.*)\.\.(true|false)\.(\d+)$", dhcpoption)
    if optioncodes:
        optionspace = optioncodes.group(1)
        optioncode = int(optioncodes.group(3))
    else:
        optionspace = None
        optioncode = None

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


def validatedhcpoption(type, parentobj, optionspace, optioncode, hexvalue, optionvalue, count):
    '''
    Validate DHCP Options
    '''
    CONFIG = DBCONFIG()
    incompatible_options = CONFIG.incompatible_options()
    validate_options = CONFIG.validate_options()

    r = []

    if optioncode in incompatible_options:
        logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
        r = [ 'DHCPOPTION', 'INCOMPATIBLE', type, parentobj, optionspace, str(optioncode), optionvalue, str(count) ]
    elif optioncode in validate_options:
        if optioncode == 151:
            logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
            r = [ 'DHCPOPTION', 'VALIDATION_NEEDED', type, parentobj, optionspace, str(optioncode), optionvalue, str(count) ]
        elif optioncode == 43:
            if hexvalue == True:
                logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
                r = [ 'DHCPOPTION', 'VALIDATION_NEEDED', type, parentobj, optionspace, str(optioncode), optionvalue, str(count) ]
            elif hexvalue == False:
                logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
                r = [ 'DHCPOPTION', 'INCOMPATIBLE', type, parentobj, optionspace, str(optioncode), optionvalue, str(count) ]
    else:
        r = []
    
    validation = r
    
    return validation


def validatenetwork(address, cidr, count):
    if cidr == '32':
        logging.info('DHCPNETWORK,INCOMPATIBLE,' + address + '/' + cidr + ',' + str(count))
        report = 'DHCPNETWORK,INCOMPATIBLE,' + address + '/' + cidr + ',' + str(count)
    else:
        report = ''
    
    return [ report ]

def member_leases(xmlobject):
    '''
    Determine Lease State
    '''
    member = ''
    for property in xmlobject:
        count = False
        if property.attrib['NAME'] == 'node_id':
            node = property.attrib['VALUE']
        if property.attrib['NAME'] == 'binding_state' and property.attrib['VALUE'] == 'active':
            member = node

    return member


def writeheaders():
    logging.info('HEADER-DHCPOPTION,STATUS,OBJECTTYPE,OBJECT,OPTIONSPACE,OPTIONCODE,OPTIONVALUE')
    logging.info('HEADER-DHCPNETWORK,STATUS,OBJECT,OBJECTLINE')
    logging.info('HEADER-LEASECOUNT,MEMBER,ACTIVELEASES')
    return


def report_processed(report, REPORT_CONFIG, DBOBJECTS):
    '''
    Generate and Output report for processed content
    '''
    for obj in report['processed'].keys():
        if DBOBJECTS.header(obj):
            labels = DBOBJECTS.header(obj).split(',')
        else:
            labels = []
        print(DBOBJECTS.obj_type(obj))
        df = pd.DataFrame(report['processed'][obj], columns=labels)
        pprint.pprint(df)

    return


def report_collected(report, REPORT_CONFIG, DBOBJECTS):
    '''
    Generate and Output report for collected content
    '''
    for obj in report['collected'].keys():
        print(DBOBJECTS.obj_type(obj))
        df = pd.DataFrame(report['collected'][obj])
        pprint.pprint(df)
    return


def report_counters(report, REPORT_CONFIG, DBOBJECTS):
    '''
    Report Counters
    '''
    for counter in report.keys():
        print(report['counter'])
