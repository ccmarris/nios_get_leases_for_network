#!/usr/bin/env python3
#vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
'''

 Description:

    Retrieve leases for a network based on a seed IP address

 Requirements:
   Python 3.6+

 Author: Chris Marrison

 Date Last Updated: 20220420

 Todo:

 Copyright (c) 2022 Chris Marrison / Infoblox

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
 CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.

'''
__version__ = '0.2.0'
__author__ = 'Chris Marrison'
__author_email__ = 'chris@infoblox.com'
__license__ = 'BSD'

import logging
from multiprocessing.dummy import active_children
from rich import print
import requests
import argparse
import configparser
import time
import concurrent.futures


def parseargs():
    '''
    Parse Arguments Using argparse

    Parameters:
        None

    Returns:
        Returns parsed arguments
    '''
    description = 'Retrieve leases for specified network.' 
    parse = argparse.ArgumentParser(description=description)
    parse.add_argument('-c', '--config', type=str, default='gm.ini',
                        help="Override ini file")
    parse.add_argument('-i', '--ip4addr', type=str, required=True,
                        help="Specify network to get IP information")
    parse.add_argument('-v', '--view', type=str, default="default",
                        help="Specify the network view")
    parse.add_argument('-a', '--active_only', action='store_true',
                        help="Show active leases only")
    parse.add_argument('-d', '--debug', action='store_true', 
                        help="Enable debug messages")

    return parse.parse_args()


def read_ini(ini_filename):
    '''
    Open and parse ini file

    Parameters:
        ini_filename (str): name of inifile

    Returns:
        config :(dict): Dictionary of BloxOne configuration elements

    '''
    # Local Variables
    cfg = configparser.ConfigParser()
    config = {}
    ini_keys = ['gm', 'api_version', 'valid_cert', 'user', 'pass' ]

    # Attempt to read api_key from ini file
    try:
        cfg.read(ini_filename)
    except configparser.Error as err:
        logging.error(err)

    # Look for NIOS section
    if 'NIOS' in cfg:
        for key in ini_keys:
            # Check for key in BloxOne section
            if key in cfg['NIOS']:
                config[key] = cfg['NIOS'][key].strip("'\"")
                logging.debug('Key {} found in {}: {}'.format(key, ini_filename, config[key]))
            else:
                logging.warning('Key {} not found in NIOS section.'.format(key))
                config[key] = ''
    else:
        logging.warning('No BloxOne Section in config file: {}'.format(ini_filename))
        config['api_key'] = ''

    return config


def setup_logging(debug):
    '''
     Set up logging

     Parameters:
        debug (bool): True or False.

     Returns:
        None.

    '''
    # Set debug level
    if debug:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s: %(message)s')

    return


def create_session(config):
    '''
    Create request session

    Parameters:
        config (dict): GM config
    
    Return:
        wapi_session (obj): request session object
    '''
    headers = { 'content-type': "application/json" }

    if config['valid_cert'] == 'true':
        valid_cert = True
    else:
        valid_cert = False

    # Avoid error due to a self-signed cert.
    if not valid_cert:
        requests.packages.urllib3.disable_warnings()
    
    wapi_session = requests.session()
    wapi_session.auth = (config['user'], config['pass'])
    wapi_session.verify = valid_cert
    wapi_session.headers = headers

    return wapi_session


def wapi_call(session, **params):
    '''
    Make wapi call

    Parameters:
        session (obj): Session object to use
        **params: parameters for request.get
    
i   Returns:
        data: JSON response as object (list/dict) or None
    '''
    status_codes_ok = [ 200, 201 ]

    response = session.get(**params)
    if response.status_code in [ 200, 201 ]:
        data = response.json()
    else:
        logging.debug(f'HTTP response: {response.status_code}')
        logging.debug(f'Body: {response.content}')
        data = None

    return data


def get_network_leases(config, ipaddr, net_view="default"):
    '''
    Get the active leases for a network

    Parameters:
        config (dict): config from inifile
        network (str): network address
        net_view (str): network view

    Returns:
        List of leases objects
    '''
    lease_objects = []
    base_url = f'https://{config.get("gm")}/wapi/{config.get("api_version")}'
    net_fields = '_return_fields=ip_address,network,network_view,status,types'
    lease_fields = ( '_return_fields=address,network,network_view,' +
                     'binding_state,hardware,cltt,ends,served_by,' +
                     'client_hostname' )

    session = create_session(config)

    # Get network with IPs
    url = ( f'{base_url}/ipv4address?ip_address={ipaddr}' +
            f'&network_view={net_view}&{net_fields}&_max_results=1' )
    # Use base session
    logging.info(f'Retrieving network for IP: {ipaddr}')
    net_data = wapi_call(session, url=url)
    if net_data:
        logging.info('Network retrieved successfully')
        logging.debug(f'Response: {net_data}')
        network = net_data[0].get('network')
        logging.debug(f'Network: {network}')
    else:
        logging.error('Failed to retrieve network')
        network = []
    
    # Get lease objects
    if network:
        logging.info(f'Retrieving leases')
        url = f'{base_url}/lease?network={network}&{lease_fields}'
        lease_objects = wapi_call(session, url=url)
    else:
        lease_objects = []
    
    return lease_objects


def process_network(lease_objects):
    '''
    Generate the set of active leases

    Parameters:
        lease_objects (list): list of dict of lease objects
    
    Returns:
        List of active leases

    '''
    active_leases = []

    logging.info('Processing leases for network')
    for lease in lease_objects:
        if lease.get('binding_state') == "ACTIVE":
            active_leases.append(lease)

    logging.debug(f'Active Leases: {active_leases}')
    
    return active_leases


'''
    url = mainurl+"lease?address="+ip+"&_return_fields=binding_state,hardware,client_hostname,starts,ends&_max_results=1&_return_as_object=1"


        response_time = session.get(url=url, headers=headers, cookies=session.cookies, verify=True)
        response_time_dict = json.loads(response_time.text)
        for item in response_time_dict['result']:
            starts=item['starts']
            ends=item['ends']
            dt_object_starts = datetime.fromtimestamp(starts)
            dt_object_ends = datetime.fromtimestamp(ends)
'''

def main():
    '''
    Code logic
    '''
    exitcode = 0
    run_time = 0
    network_leases = []
    active_leases = []

    # Parse CLI arguments
    args = parseargs()
    setup_logging(args.debug)

    # Read inifile
    config = read_ini(args.config)

    t1 = time.perf_counter()
    network_leases = get_network_leases(config, 
                                        args.ip4addr, 
                                        net_view=args.view)

    # Active Only
    if network_leases and args.active_only:
        active_leases = process_network(network_leases)
        print(active_leases)

    run_time = time.perf_counter() - t1
    
    if active_leases:
        print(active_leases)
        print(f'{len(active_leases)} active leases retrieved')
    else:
        print(network_leases)
        print(f'{len(network_leases)} leases retrieved')

    print('Run time: {}'.format(run_time))

    return exitcode


### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)
## End Main ###
