# -*- coding: utf-8 -*-

import os
from datetime import date
from jinja2 import Environment, PackageLoader
from imio.pyutils.system import verbose, error, write_to, close_outfiles, runCommand, read_file, read_dir

TRACE = False
env = Environment(loader=PackageLoader('imio.trac2taskjuggler', 'templates'),
                  trim_blocks=True, lstrip_blocks=True)
BUILD_PATH = os.environ.get('BUILDOUT', os.environ.get('PWD', '/Cannot_get_buildout_path'))
PRJ_PATH = '%s/project' % BUILD_PATH
base_rep_cmd = 'tj3 --silent -o DAY_DIR %s/trac.tjp' % PRJ_PATH
outfiles = {'index': {'file': 'index.html'},
            'error': {'file': 'report_errors.txt'},
            }

#------------------------------------------------------------------------------


def generate(output_dir):
    """ Generate taskjuggler report """
    verbose("Begin of taskjuggler report")
    output_dir = output_dir.rstrip('/')
    DAY_DIR = os.path.join(output_dir, date.strftime(date.today(), "%Y-%m-%d"))
    rep_cmd = base_rep_cmd.replace('DAY_DIR', DAY_DIR)
    if not os.path.exists(DAY_DIR):
        os.makedirs(os.path.join(DAY_DIR, 'css'))
        os.symlink('%s/custom.css' % BUILD_PATH, '%s/css/custom.css' % DAY_DIR)
    outfiles['index']['file'] = os.path.join(output_dir, outfiles['index']['file'])
    outfiles['index']['error'] = os.path.join(output_dir, outfiles['error']['file'])
    report_err = [outfiles['error']['file'], 0]
    verbose("Running command: %s" % rep_cmd)
    (cmd_out, cmd_err) = runCommand(rep_cmd)
    errors = [err for err in cmd_err if 'Error: ' in err]
    if errors:
        errors_str = '\n'.join(errors)
        error("error running command %s : %s" % (rep_cmd, errors_str))
        write_to(outfiles, 'error', errors_str)
        report_err[1] = len(errors)
    gen_err = ['%s/generation_errors.txt' % output_dir, 0]
    if os.path.exists(gen_err[0]):
        lines = read_file(gen_err[0], skip_empty=True)
        if lines:
            gen_err[1] = len(lines)
    olds = read_dir(output_dir, only_folders=True)
    template = env.get_template('index.html')
    rendered = template.render(report_err=report_err, gen_err=gen_err, olds=olds)
    write_to(outfiles, 'index', rendered.encode('utf8'))
    close_outfiles(outfiles)
    verbose("End of taskjuggler report")
