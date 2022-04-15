#!/usr/bin/env python3
#vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
'''

 Description:

    NIOS WAPI Benchmark Script
    Uses threading with multiple sessions

 Requirements:
   Python 3.6+

 Author: Chris Marrison

 Date Last Updated: 20220415

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
__version__ = '0.1.0'
__author__ = 'Chris Marrison'
__author_email__ = 'chris@infoblox.com'
__license__ = 'BSD'

import logging
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
    parse.add_argument('-n', '--network', type=str, required=True,
                        help="Specify network to get IP information")
    parse.add_argument('-v', '--view', type=str, default="default",
                        help="Specify the network view")
    parse.add_argument('-t', '--threads', type=int, default=5,
                        help="Number of Threads")
    parse.add_argument('-s', '--sessions', type=int, default=1,
                        help="Number of HTTP Session to create")
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


def make_wapi_calls(sessions, url):
    '''
    '''
    results = {}

    for z in range(0, (len(sessions)-1)):
        results.append(wapi_call(sessions[z], url=url))

    return results


def get_network_leases(config, 
                       network, 
                       net_view="default", 
                       threads=5, 
                       no_of_sessions=1):
    '''
    Get the active leases for a network

    Parameters:
        config (dict): config from inifile
        network (str): network address
        net_view (str): network view
        threads (int): number of threads to execute
        no_of_sessions (int): number of http sessions used by threads

    Returns:
        runt_time (time): execution time
    '''
    run_time = 0
    results = []
    lease_objects = []
    sessions = []
    tasks = []
    base_url = f'https://{config.get("gm")}/wapi/{config.get("api_version")}'
    lease_fields = ( '_return_fields=address,binding_state,hardware,' +
                     'cltt,ends,served_by,client_hostname' )

    # Create one or more HTTP sessions, this may improve performance
    if no_of_sessions > 10:
        # Reset to max recommended
        no_of_sessions = 10

    for i in range(0, (no_of_sessions)):
        sessions.append(create_session(config))

    # Get network with IPs
    url = f'{base_url}/ipv4address?network={network}&network_view={net_view}'
    # Use base session
    logging.info(f'Retrieving network: {network}')
    net_data = wapi_call(sessions[0], url=url)
    if net_data:
        logging.info('Network retrieved successfully')
        lease_objects = process_network(net_data)
    else:
        logging.error('Failed to retrieve network')
        lease_objects = []
    
    # Get lease objects
    logging.info(f'Retrieving {len(lease_objects)} leases')
    if lease_objects:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            index = 0
            max_index = len(lease_objects) - 1
            while index <= max_index:
                for i in range(0, (no_of_sessions)):
                    url = f'{base_url}/{lease_objects[index]}?{lease_fields}'
                    logging.debug(f'Lease URL: {url}')
                    tasks.append(executor.submit(wapi_call, 
                                                 session=sessions[i], 
                                                 url=url))
                    index += 1
                    if index > max_index:
                        break
    
        # results = process_tasks(tasks)
        for task in concurrent.futures.as_completed(tasks):
            results.append(task.result())
    else:
        results = []
    
    return results


def process_network(net_data):
    '''
    Generate the set of lease objects from the network

    Parameters:
        net_data (dict): Dict from json data
    
    Returns:

    '''
    lease_objects = []

    logging.info('Processing network')
    for element in net_data:
        if element.get('status') == "USED":
            if element.get('usage'):
                if "DHCP" in element.get('usage'):
                    # Gather lease objects
                    if element.get('objects'):
                        for obj in element.get('objects'):
                            if 'lease' in obj:
                                logging.debug(f'Lease object found for: element.get("ip_address")')
                                lease_objects.append(obj)
                                break
    logging.debug(f'Lease Objects: {lease_objects}§')
    
    return lease_objects

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
    network_leases = {}

    # Parse CLI arguments
    args = parseargs()
    setup_logging(args.debug)

    # Read inifile
    config = read_ini(args.config)

    t1 = time.perf_counter()
    network_leases = get_network_leases(config, 
                                        args.network, 
                                        net_view=args.view,
                                        threads=args.threads)
    run_time = time.perf_counter() - t1
    
    print(network_leases)
    print(f'{len(network_leases)} leases retrieved')
    print('Run time: {}'.format(run_time))

    return exitcode


### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)
## End Main ###
