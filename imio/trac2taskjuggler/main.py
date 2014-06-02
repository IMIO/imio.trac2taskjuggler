# -*- coding: utf-8 -*-

from imio.pyutils.postgres_utilities import openConnection, selectAllInTable
from imio.pyutils.system_utilities import verbose


def generate(dsn):
    """ Generate taskjuggler files from trac """
    conn = openConnection(dsn)
    data = selectAllInTable(conn, 'enum', '*')
    verbose("Lines: %d" % len(data))
