# -*- coding: utf-8 -*-

import os
import re
import sys
from datetime import datetime, timedelta
from jinja2 import Environment, PackageLoader
from slugify import unique_slugify
from imio.pyutils.postgres import selectWithSQLRequest, selectAllInTable
from imio.pyutils.system import verbose, error, write_to, close_outfiles
from config import PROJECTS, TICKET_URL


TRACE = False
# 1528732800000000 = 11/06/2018
query = '''
select milestone
, case when mst.due != 0 then to_char(to_timestamp(mst.due/1000000), 'YYYY-MM-DD') else '' end as due
--, case when mst.completed != 0 then to_char(to_timestamp(mst.completed/1000000), 'YYYY-MM-DD') else '' end
, id, summary, status, owner, component
, (CASE WHEN EstimatedHours.value = '' OR EstimatedHours.value IS NULL THEN 0
         ELSE CAST( EstimatedHours.value AS DECIMAL ) END) as Estimated_work
, (CASE WHEN totalhours.value = '' OR totalhours.value IS NULL THEN 0
         ELSE CAST( totalhours.value AS DECIMAL ) END) as Total_work
, t.description
from ticket as t
LEFT JOIN ticket_custom as EstimatedHours ON EstimatedHours.name='estimatedhours'
      AND EstimatedHours.Ticket = t.Id
LEFT JOIN ticket_custom as totalhours ON totalhours.name='totalhours'
      AND totalhours.Ticket = t.Id
LEFT JOIN milestone as mst ON mst.name = t.milestone

where milestone != ''
and mst.due != 0 AND mst.completed = 0
and milestone not ilike '% - SUP - %' and milestone not ilike 'IMIO - %'
and mst.due < 1528732800000000
and status != 'CLOTURE'
order by mst.due, milestone, id
'''
env = Environment(loader=PackageLoader('imio.trac2taskjuggler', 'templates'),
                  trim_blocks=True, lstrip_blocks=True)
msts = {}
msts_due = {}
tkts = {}
tkts_links = {}
leaves = {}
resources = {}
date_pat = re.compile('^\d{4}-\d{2}-\d{2}$')
duration_pat = re.compile('^\+\d+(d|h|min)$')
PRJ_PATH = '%s/project' % os.environ.get('BUILDOUT', os.environ.get('PWD', '/Cannot_get_buildout_path'))
outfiles = {'tjp': {'file': '%s/trac.tjp' % PRJ_PATH},
            'resources': {'file': '%s/resources.tji' % PRJ_PATH},
            'reports': {'file': '%s/reports.tji' % PRJ_PATH},
            'tasks': {'file': '%s/tasks.tji' % PRJ_PATH},
            }
EFFORT_EXCEED_FACTOR = 0.5

#------------------------------------------------------------------------------


def cmp_mst(x, y):
    if msts[x[1]]['due'] < msts[y[1]]['due']:
        return 1
    elif msts[x[1]]['due'] == msts[y[1]]['due']:
        return 0
    else:
        return -1

#------------------------------------------------------------------------------


def getLeaves(dsn):
    """ Get the leaves encoded in trac """
    records = selectAllInTable(dsn, 'ticket', 'owner, description, id',
                               condition="milestone = 'IMIO - INT - Congés et absences'")
    for rec in records:
        (owner, description, id) = rec
        res = []
        try:
            lvs = description.split(',')
            for lv in lvs:
                lv = lv.strip('\r\n ')
                if not lv:
                    continue
                parts = lv.split(' ')
                if len(parts) == 4 and parts[3] in ('d', 'h', 'min'):
                    parts[2] += parts[3]
                if parts[0] not in ('annual', 'sick', 'special'):
                    error("Leaves problem in '%s' (%s, %s/%s): bad leave type" % (description, owner, TICKET_URL, id))
                    continue
                if not re.match(date_pat, parts[1]):
                    error("Leaves problem in '%s' (%s, %s/%s): bad date format" % (description, owner, TICKET_URL, id))
                    continue
                if not re.match(duration_pat, parts[2]):
                    error("Leaves problem in '%s' (%s, %s/%s): bad date format" % (description, owner, TICKET_URL, id))
                    continue
                res.append(' '.join(parts[:3]))
            if res:
                leaves[owner] = ', '.join(res)
        except Exception, exc:
            error("Leaves analysis exception in '%s' (%s, %s/%s): %s" % (description, owner, TICKET_URL, id, exc))

#------------------------------------------------------------------------------


def getBlockingTickets(dsn):
    """ Get the blocking tickets encoded in the trac """
    records = selectAllInTable(dsn, 'mastertickets', 'source, dest')
    for rec in records:
        (src, dest) = rec
        if dest not in tkts_links:
            tkts_links[dest] = []
        if src not in tkts_links[dest]:
            tkts_links[dest].append(src)

#------------------------------------------------------------------------------


def generate(dsn):
    """ Generate taskjuggler files from trac """
    now = datetime.now()
    prj_start = now - timedelta(minutes=now.minute) + timedelta(hours=1)
    min_mst_due = prj_start + timedelta(days=1)
    min_mst_due = datetime.strftime(min_mst_due, "%Y-%m-%d")
    getBlockingTickets(dsn)
    records = selectWithSQLRequest(dsn, query, TRACE=TRACE)
    verbose("Records number: %d" % len(records))
    print >> sys.stderr, "# Records number: %d" % len(records)
#("URBAN - DEV - Permis d'environnement classe 1", '2012-12-31', 5340, 'Ajouter le champ "Secteur d\'activit\xc3\xa9"',
#'NOUVEAU', 'sdelcourt', 'Urbanisme communes (URBAN)', Decimal('0.0'), Decimal('0'), "data grid avec au moins ")
    for rec in records:
        (mst, mst_due, id, summary, status, owner, prj, estimated, hours, description) = rec
        estimated = float(estimated)
        hours = float(hours)
        try:
            mst_list = mst.split(' - ')
            (mst_prj, mst_wrk) = (mst_list[0], mst_list[1])
            if mst_prj not in PROJECTS:
                error("Project '%s' not well extracted from '%s' (%s, %s/%s)" % (mst_prj, mst, owner, TICKET_URL, id))
        except:
            error("Project cannot be extracted from '%s' (%s, %s/%s)" % (mst, owner, TICKET_URL, id))
        #due = datetime.strptime(mst_due, '%Y/%m/%d').date()
        if mst_prj not in msts_due:
            msts_due[mst_prj] = {}
        if mst_wrk not in msts_due[mst_prj]:
            msts_due[mst_prj][mst_wrk] = {}
        if mst_due not in msts_due[mst_prj][mst_wrk]:
            msts_due[mst_prj][mst_wrk][mst_due] = []
        mst = mst.decode('utf8')
        if mst not in msts:
            mstid = unique_slugify(mst, separator='_', unique_id=True).encode('utf8')
            msts[mst] = {'prj': mst_prj, 'due': (mst_due <= min_mst_due and min_mst_due or mst_due),
                         't': [], 'own': {}, 'wrk': mst_wrk, 'dep': [], 'id': mstid, 'prty': 1}
            msts_due[mst_prj][mst_wrk][mst_due].append(mst)
        msts[mst]['t'].append(id)
        if id in tkts:
            error("Ticket '%s' already found in dict %s (%s, %s/%s)" % (id, tkts[id], owner, TICKET_URL, id))
            continue
        if not owner:
            error("Ticket '%s' has no owner (%s/%s)" % (id, TICKET_URL, id))
        tkts[id] = {'sum': summary, 'status': status, 'owner': owner, 'prj': prj,
                    'estim': estimated, 'hours': hours, 'mst': mst}
        if owner not in msts[mst]['own']:
            msts[mst]['own'][owner] = {'effort': 0.0, 't': [], 'done': 0.0}
        msts[mst]['own'][owner]['t'].append(id)
        msts[mst]['own'][owner]['done'] += hours
        if estimated == 0:
            error("Estimated hour not set for ticket (%s, %s/%s)" %
                  (owner, TICKET_URL, id))
            continue
        elif hours == 0:
            msts[mst]['own'][owner]['effort'] += estimated
        elif hours > estimated:
            msts[mst]['own'][owner]['effort'] += (estimated * EFFORT_EXCEED_FACTOR)
        else:
            msts[mst]['own'][owner]['effort'] += (estimated - hours)
        if owner not in resources:
            resources[owner] = {}
        if mst_prj not in resources[owner]:
            resources[owner][mst_prj] = 0

    # calculate mst order: set the priority
    for prj in msts_due:
        for wrk in msts_due[prj]:
            p = 1000
            for due in sorted(msts_due[prj][wrk]):  # sorted by due date
                for mst in msts_due[prj][wrk][due]:
                    if p > 1:
                        msts[mst]['prty'] = p
                p -= 50
    # find blocking milestone from blocking tickets
    for mst in msts:
        for tkt in msts[mst]['t']:
            if tkt not in tkts_links:
                continue  # no blocking
            for blck in tkts_links[tkt]:
                if not blck in tkts:
                    error("Blocking ticket '%s/%s' not found in due milestone tickets" % (TICKET_URL, blck))
                    continue
                blck_mst = msts[tkts[blck]['mst']]['id']
                # skipping self milestone dependency
                if tkts[blck]['mst'] != mst and blck_mst not in msts[mst]['dep']:
                    msts[mst]['dep'].append(blck_mst)

    # generate trac.tjp file
    template = env.get_template('trac.tjp')
    rendered = template.render(prj_start=datetime.strftime(prj_start, "%Y-%m-%d-%H:%M"))
    write_to(outfiles, 'tjp', rendered.encode('utf8'))
    # generate resources.tji
    getLeaves(dsn)
    template = env.get_template('resources.tji')
    rendered = template.render(leaves=leaves, resources=resources, prjs=msts_due)
    write_to(outfiles, 'resources', rendered.encode('utf8'))
    # generate reports.tji
    template = env.get_template('reports.tji')
    rendered = template.render(prjs=msts_due)
    write_to(outfiles, 'reports', rendered.encode('utf8'))
    # generate tasks.tji
    template = env.get_template('tasks.tji')
    rendered = template.render(prjs=msts_due, msts=msts)
    write_to(outfiles, 'tasks', rendered.encode('utf8'))

    close_outfiles(outfiles)
