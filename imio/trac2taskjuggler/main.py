# -*- coding: utf-8 -*-

import os
from datetime import datetime, timedelta
from jinja2 import Environment, PackageLoader
from slugify import slugify
from imio.pyutils.postgres import openConnection, selectWithSQLRequest
from imio.pyutils.system import verbose, error, write_to, close_outfiles
from config import PROJECTS


TRACE = False
query = '''
select milestone
, case when mst.due != 0 then to_char(to_timestamp(mst.due/1000000), 'YYYY-MM-DD') else '' end as due
--, case when mst.completed != 0 then to_char(to_timestamp(mst.completed/1000000), 'YYYY-MM-DD') else '' end
, id, summary, status, owner, component
, dec_to_hour(CASE WHEN EstimatedHours.value = '' OR EstimatedHours.value IS NULL THEN 0
         ELSE CAST( EstimatedHours.value AS DECIMAL ) END) as Estimated_work
, dec_to_hour(CASE WHEN totalhours.value = '' OR totalhours.value IS NULL THEN 0
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
and status != 'CLOTURE'
order by mst.due, milestone, id
'''
env = Environment(loader=PackageLoader('imio.trac2taskjuggler', 'templates'), trim_blocks=True,
                  lstrip_blocks=True)
msts = {}
msts_prj = {}
PRJ_PATH = '%s/project' % os.environ.get('BUILDOUT', os.environ.get('PWD', '/Cannot_get_buildout_path'))
outfiles = {'tjp': {'file': '%s/trac.tjp' % PRJ_PATH},
            'resources': {'file': '%s/resources.tji' % PRJ_PATH},
            'tasks': {'file': '%s/tasks.tji' % PRJ_PATH},
            }

#------------------------------------------------------------------------------


def cmp_mst(x, y):
    if msts[x[1]]['due'] < msts[y[1]]['due']:
        return 1
    elif msts[x[1]]['due'] == msts[y[1]]['due']:
        return 0
    else:
        return -1

#------------------------------------------------------------------------------


def generate(dsn):
    """ Generate taskjuggler files from trac """
    conn = openConnection(dsn)
    records = selectWithSQLRequest(conn, query, TRACE=TRACE)
    conn.close()
    verbose("Records number: %d" % len(records))
#("INFRA - MEP - Demande d'instance", 7919, 'Instance PST Walcourt', 'NOUVEAU', 'fngaha',
#'Serveur, infrastructure (INFRA)', '15/05/2020', '2h', '', 'walcourt-prj.imio-app.be')
    for rec in records:
        (mst, mst_due, id, summary, status, owner, prj, estimated, hours, description) = rec
        mst = mst.decode('utf8')
        try:
            mst_prj = mst.split(' - ')[0]
            if mst_prj not in PROJECTS:
                error("Project 'mst_prj' not well extracted from '%s'" % (mst_prj, mst))
        except:
            error("Project cannot be extracted from '%s'" % (mst))
        #due = datetime.strptime(mst_due, '%Y/%m/%d').date()
        if mst_prj not in msts_prj:
            msts_prj[mst_prj] = []
        if mst not in msts:
            msts[mst] = {'prj': mst_prj, 'due': mst_due, 't': []}
            mstid = slugify(mst, separator='_', unique_id=True).encode('utf8')
            msts_prj[mst_prj].append((mstid, mst))
        msts[mst]['t'].append(id)

    # sort milestones by project and due date
    msts_prj[mst_prj].sort(cmp=cmp_mst)

    # generate trac.tjp file
    now = datetime.now()
    prj_start = now - timedelta(minutes=now.minute) + timedelta(hours=1)
    template = env.get_template('trac.tjp')
    rendered = template.render(prj_start=datetime.strftime(prj_start, "%Y-%m-%d-%H:%M"))
    write_to(outfiles, 'tjp', rendered.encode('utf8'))
    # generate resources.tji
    template = env.get_template('resources.tji')
    rendered = template.render()
    write_to(outfiles, 'resources', rendered.encode('utf8'))
    # generate tasks.tji
    template = env.get_template('tasks.tji')
    rendered = template.render(prjs=msts_prj, msts=msts)
    write_to(outfiles, 'tasks', rendered.encode('utf8'))

    close_outfiles(outfiles)
