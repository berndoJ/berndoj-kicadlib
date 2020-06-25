#
# Modified KiCad BOM generation script for berndoj_kicadlib
#

"""
    @package
    BOM CSV list for BerndoJ-KiCadLib
    Components are sorted by ref
    One component per line
    Fields are (if exist)
    Ref, value, Part, footprint, Datasheet, Manufacturer, Vendor

    Command line:
    python3 "pathToFile/bom_csv_sorted_by_ref.py" "%I" "database_ip" "username" "password" "database_project_id"
"""

from __future__ import print_function

# Import the KiCad python helper module
import kicad_netlist_reader
import sys
import requests
import json

db_ipaddr = sys.argv[2]
db_username = sys.argv[3]
db_password = sys.argv[4]
db_project_id = int(sys.argv[5])

# Generate an instance of a generic netlist, and load the netlist tree from
# the command line option. If the file doesn't exist, execution will stop
net = kicad_netlist_reader.netlist(sys.argv[1])
components = net.getInterestingComponents()
stacked_components = {}

# Stack all components.
for c in components:
    cur_ipn = c.getField('IPN')
    if not (cur_ipn in stacked_components):
        stacked_components[cur_ipn] = {}
        stacked_components[cur_ipn]['component'] = c
        stacked_components[cur_ipn]['count'] = 1
    else:
        stacked_components[cur_ipn]['count'] += 1

print('Acquired all BOM-components from the netlist file.')

print('Querying parts from PartKeepr database @ ' + db_ipaddr + '...')
# Retrieve all component database IDs from the PartKeepr database.
for cur_ipn in stacked_components:
    print('Querying part with IPN "' + cur_ipn + '"...')

    req = requests.get('http://' + db_ipaddr + '/api/parts?filter={"property":"internalPartNumber","operator":"=","value":"' + cur_ipn + '"}', auth=(db_username, db_password))

    if (req.status_code != 200):
        print('Part request for IPN ' + cur_ip + ' failed. GET status code: ' + str(req.status_code))
        exit()
    
    try:
        req_response_json = json.loads(req.text)
        req_partid = req_response_json['hydra:member'][0]['@id']
    except Exception:
        print('Could not interpret the query response for IPN ' + cur_ipn + '.')
        exit()
    
    stacked_components[cur_ipn]['db_id'] = req_partid

print('Query complete.')

print('Assembling new project BOM...')
project_parts_json = ''
# Assemble raw json for project parts.
for cur_ipn in stacked_components:
    if (project_parts_json != ''):
        project_parts_json += ','
    
    part_qty = stacked_components[cur_ipn]['count']
    part_id = stacked_components[cur_ipn]['db_id']

    project_parts_json += '{"quantity":' + str(part_qty) + ',"remarks":"' + cur_ipn + '","overageType":"","overage":0,"lotNumber":"","part":"' + part_id + '"}'

print('Querying the database project...')

req = requests.get('http://' + db_ipaddr + '/api/projects/' + str(db_project_id), auth=(db_username, db_password))

if (req.status_code != 200):
    print('Project query for project id ' + str(db_project_id) + ' failed. GET status code: ' + str(req.status_code))
    exit()

try:
    req_response_json = json.loads(req.text)
    project_name = req_response_json['name']
    project_descr = req_response_json['description']
    project_attachments = json.dumps(req_response_json['attachments'])
except Exception:
    print('Could not interpret the query response for project id ' + str(db_project_id) + '.')
    exit()

print('Modifying database project BOM...')

req_payload = payload = '{"name":"' + project_name + '","description":"' + project_descr + '","@context":"/api/contexts/Project","@type":"Project","projectPartKeeprProjectBundleEntityProjectAttachments":[],"attachments":' + project_attachments + ',"projectPartKeeprProjectBundleEntityProjectParts":[],"parts":[' + project_parts_json + '],"projectPartKeeprProjectBundleEntityProjectRuns":[],"projectPartKeeprProjectBundleEntityReportProjects":[]}'
req = requests.put('http://' + db_ipaddr + '/api/projects/' + str(db_project_id), auth=(db_username, db_password), data=req_payload)

if (req.status_code != 200):
    print('Project modification for id ' + str(db_project_id) + ' failed. PUT status code: ' + str(req.status_code))
    exit()

print('Successfully modified project BOM! (ID ' + str(db_project_id) + ')')