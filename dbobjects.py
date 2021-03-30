
#!/usr/local/bin/python3
'''
------------------------------------------------------------------------
 Description:
   Python script to search for feature gaps between NIOS and BloxOne DDI

 Requirements:
   Python3 with lxml, argparse, tarfile, logging, re, time, sys, tqdm

 Author: Chris Marrison & John Neerdael

 Date Last Updated: 20210321
 
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
__version__ = '0.4.0'
__author__ = 'Chris Marrison, John Neerdael'
__author_email__ = 'chris@infoblox.com, jneerdael@infoblox.com'

import tarfile, logging, re, time, sys, tqdm
import os
import collections
import yaml
from lxml import etree
from itertools import (takewhile,repeat)


class DBOBJECTS():
    '''
    Define Class for onedb.xml db objects
    '''

    def __init__(self, cfg_file='objects.yaml'):
        '''
        Initialise Class Using YAML config
        '''
        self.dbobjects = {}
   
        # Check for inifile and raise exception if not found
        if os.path.isfile(cfg_file):
            # Attempt to read api_key from ini file
            try:

                self.dbobjects = yaml.safe_load(open(cfg_file, 'r'))
            except yaml.YAMLError as err:
                logging.error(err)
                raise
        else:
            logging.error('No such file {}'.format(cfg_file))
            raise FileNotFoundError('YAML object file "{}" not found.'.format(cfg_file))

        return


    def keys(self):
        return self.dbobjects['objects'].keys()


    def count(self):
        return len(self.dbobjects['objects'])  


    def included(self, dbobj):
        '''
        Check whether this dbobj is configured
        '''
        status = False
        if dbobj in self.keys():
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
            t = self.dbobjects['objects'][dbobj]['type']
        else:
            t = None
        
        return t


    def header(self, dbobj):
        '''
        Return name of function for dbobj
        '''
        if self.included(dbobj):
            if 'header' in self.dbobjects['objects'][dbobj]:
                header = self.dbobjects['objects'][dbobj]['header']
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
            actions = self.dbobjects['objects'][dbobj]['actions']
        else:
            actions = []
        
        return actions
    

    def func(self, dbobj):
        '''
        Return name of function for dbobj
        '''
        if self.included(dbobj):
            if 'func' in self.dbobjects['objects'][dbobj]:
                function = self.dbobjects['objects'][dbobj]['func']
            else:
                function = None
        else:
            function = None
            # Consider raising KeyError Exception

        return function


    def reports(self, dbobj):
        '''
        Return list of reports for dbobj
        '''
        reports = []
        if self.included(dbobj):
            reports = self.dbobjects['objects'][dbobj]['reports']
        else:
            reports = []
        
        return actions
   
            


# *** Functions ***

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
    incompatible_options = [ 12, 124, 125, 146, 159, 212 ]
    validate_options = [ 43, 151 ]
    if optioncode in incompatible_options:
        logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
        r = 'DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count)
    elif optioncode in validate_options:
        if optioncode == 151:
            logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
            r = 'DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count)
        elif optioncode == 43:
            if hexvalue == True:
                logging.info('DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
                r = 'DHCPOPTION,VALIDATION_NEEDED,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count)
            elif hexvalue == False:
                logging.info('DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count))
                r = 'DHCPOPTION,INCOMPATIBLE,' + type + ',' + parentobj + ',' + optionspace + ',' + str(optioncode) + ',' + optionvalue + ',' + str(count)
    else:
        r = ''
    
    validation = [ r ]
    
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


def writeheaders():
    logging.info('HEADER-DHCPOPTION,STATUS,OBJECTTYPE,OBJECT,OPTIONSPACE,OPTIONCODE,OPTIONVALUE')
    logging.info('HEADER-DHCPNETWORK,STATUS,OBJECT,OBJECTLINE')
    logging.info('HEADER-LEASECOUNT,MEMBER,ACTIVELEASES')
    return


if __name__ == '__main__':
    main()