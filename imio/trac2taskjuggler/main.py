# -*- coding: utf-8 -*-

import os
from datetime import datetime, timedelta
from jinja2 import Environment, PackageLoader
from imio.pyutils.postgres_utilities import openConnection, selectWithSQLRequest
from imio.pyutils.system_utilities import verbose, error, write_to, close_outfiles
from config import PROJECTS


TRACE = False
query = '''
select milestone
, case when mst.due != 0 then to_char(to_timestamp(mst.due/1000000), 'YYYY/MM/DD') else '' end as due
--, case when mst.completed != 0 then to_char(to_timestamp(mst.completed/1000000), 'YYYY/MM/DD') else '' end
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
and milestone not ilike '% - SUP - %' and milestone != 'SUPPORT 1 semaine' and milestone not ilike 'IMIO - %'
and status != 'CLOTURE'
order by mst.due, milestone, id
'''
env = Environment(loader=PackageLoader('imio.trac2taskjuggler', 'templates'))
msts = {}
msts_prj = {}
PRJ_PATH = '%s/project' % os.environ.get('BUILDOUT', os.environ.get('PWD', '/Cannot_get_buildout_path'))
outfiles = {'tjp': {'file': '%s/trac.tjp' % PRJ_PATH},
            }


def cmp_mst(x, y):
    if msts[x]['due'] < msts[y]['due']:
        return 1
    elif msts[x]['due'] == msts[y]['due']:
        return 0
    else:
        return -1


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
            msts_prj[mst_prj].append(mst)
        msts[mst]['t'].append(id)

    # sort milestones by project and due date
    msts_prj[mst_prj].sort(cmp=cmp_mst)

    # generate tjp file
    template = env.get_template('trac.tjp')
    now = datetime.now()
    prj_start = now - timedelta(minutes=now.minute) + timedelta(hours=1)
    tjp = template.render(prj_start=datetime.strftime(prj_start, "%Y-%m-%d-%H:%M"))
    write_to(outfiles, 'tjp', tjp.encode('utf8'))
    close_outfiles(outfiles)
