#!/usr/bin/env python
#
# This script provides a few options, as examples, to interact with a
# Jolokia-enabled GemFire JMX manager.
#
# The only pre-requisite is the 'requests' module which you should be able to
# install with:
#
#     pip install requests

import argparse
import requests
import time

conn_map = {}

DEFAULT_PORT = 8778

def get_jmx(host, path, **args):
    # Set some defaults if necessary
    args['port'] = args.get('port', 8778)
    args['op'] = args.get('op', 'read')

    jmx_url = 'http://{0}:{1}/jolokia/{2}/{3}'.format(host, args['port'], args['op'], path)
    session = conn_map.get(host)
    if not session:
        session = requests.Session()
        conn_map[host] = session

    r = session.get(jmx_url)
    if r.status_code != 200:
        raise RuntimeError('URL {0} responded with status: {1}'.format(
                jmx_url, r.status_code))

    j = r.json()
    if not j.has_key('value'):
        raise RuntimeError('URL {0} JSON has invalid JMX result'.format(jmx_url))

    return j


# Retrieve the number of members (excluding any locators) in the cluster
def get_member_count(host, port=DEFAULT_PORT):
    jmx = get_jmx(host, 'GemFire:service=System,type=Distributed/MemberCount,LocatorCount', port=port)['value']
    members = int(jmx['MemberCount'])
    members -= int(jmx['LocatorCount'])
    return members


# Return a list of region names
def get_regions(host, port=DEFAULT_PORT):
    regions = []
    json = get_jmx(host, 'GemFire:type=Distributed,service=Region,*/FullPath', port=port)['value']

    for v in json.values():
        regions.append(v['FullPath'])

    return regions


def __get_bucket_map(host, port, region):
    results = {}
    member_regions = get_jmx(host, 'GemFire:service=Region,type=Member,name={},member=*/Member,FullPath,BucketCount'.format(region.replace('/', '!/')), port=port)['value']
    for m_r in member_regions.values():
        results[m_r['Member'] + '-' + m_r['FullPath']] = int(m_r['BucketCount'])

    return results


# Wait for rebalancing to finish. Do this by checking successive BucketCounts
# for each member + region. The returned value is an indicator of how many
# buckets changed during this call. If 0 is returned then rebalancing is
# complete.
def check_rebalance_in_progress(host, port, region):
    first_bucket_map = __get_bucket_map(host, port, region)
    time.sleep(5)
    next_bucket_map = __get_bucket_map(host, port, region)

    delta = 0
    for k, v in next_bucket_map.items():
        delta += abs(first_bucket_map.get(k, 0) - v)

    return delta


def get_queue_size(host, port, queue):
    json = get_jmx(host, 'GemFire:service=AsyncEventQueue,queue={},type=Member,member=*/EventQueueSize'.format(queue), port=port)['value']
    q_size = 0
    for v in json.values():
        q_size += int(v['EventQueueSize'])

    return q_size


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('host', help='the host to connect to')
    parser.add_argument('-p', '--port', help='the port jolokia is listening on',
            type=int, default=8778)
    parser.add_argument('-r', '--raw', help='raw jolokia string')
    parser.add_argument('-m', '--mode', help='jolokia mode',
            choices=['read', 'exec', 'list', 'search'], default='read')
    parser.add_argument('--member-count', help='return the number of members', action='store_true')
    parser.add_argument('--get-regions', help='return a list of regions', action='store_true')
    parser.add_argument('--check-rebalance', help='check if regions have finished rebalancing',
            metavar='/REGION', nargs='?', default=None, const='*')
    parser.add_argument('--queue-size', help='check the size of an async event queue',
            metavar='/QUEUE', nargs='?', default=None, const='*')
    parser.add_argument('-c', '--count', help='repeat the command with an interval',
            metavar='interval', default=None, const=1, nargs='?', type=int)
    args = parser.parse_args()

    while True:
        if args.raw:
            json = get_jmx(args.host, args.raw, port=args.port, op=args.mode)
            print json['value']

        elif args.member_count:
            print get_member_count(args.host, args.port)

        elif args.get_regions:
            print ' '.join(get_regions(args.host, args.port))

        elif args.check_rebalance:
            print check_rebalance_in_progress(args.host, args.port, args.check_rebalance)

        elif args.queue_size:
            print get_queue_size(args.host, args.port, args.queue_size)

        if args.count:
            time.sleep(args.count)
        else:
            break
