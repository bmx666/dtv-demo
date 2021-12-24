import os
import re
import shutil
import subprocess
from subprocess import PIPE
import sys
import tempfile

from helper import loadConfig, annotateDTS, getFileName
from fdt.__main__ import diff as fdt_diff

def mergeDts(dts_files):

    baseDirPath = re.search('^.*(?=arch\/)', dts_files[0]).group(0)
    incIncludes = loadConfig(baseDirPath)

    for dts in dts_files:
        incIncludes.append(os.path.dirname(os.path.realpath(dts)))

    out_dir = os.path.dirname(os.path.realpath(__file__)) + '/tmp'
    shutil.rmtree(out_dir, True)
    os.makedirs(out_dir, exist_ok=True)

    ovmerge_list = []

    # sort and generate base dts as tmp dts
    # sort, merge each overlay with base dts and generate as tmp dts
    for i, dts in enumerate(dts_files):
        try:
            ovmerge = os.path.dirname(os.path.realpath(__file__)) + '/ovmerge'
            ovmergeFlags = '-s'
            cmd = [ovmerge, ovmergeFlags, dts_files[0]]
            if i > 0: cmd.append(dts)
            ovmergeResult = subprocess.run(' '.join(cmd),
                                    stdout=PIPE, stderr=PIPE, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print('EXCEPTION!', e)
            print('stdout: {}'.format(e.output.decode(sys.getfilesystemencoding())))
            print('stderr: {}'.format(e.stderr.decode(sys.getfilesystemencoding())))
            exit(e.returncode)

        prefix = getFileName(dts_files[0])
        if i > 0: prefix += '-' + getFileName(dts)
        prefix += '-ovmerge-'

        # Create a temporary file
        (tmpFile, tmpFileName) = tempfile.mkstemp(dir=out_dir, prefix=prefix, suffix='.dts')
        with os.fdopen(tmpFile, 'w') as output:
            output.write(ovmergeResult.stdout.decode('utf-8'))

        ovmerge_list.append(tmpFileName)

    annotated_ovmerge_list = []
    for dts in ovmerge_list:
        try:
            annotated_ovmerge_list.append(annotateDTS(dts, incIncludes, out_dir, 0))
        except Exception as e:
            print('EXCEPTION!', e)
            exit(1)

    # move final overlays in this folder
    out_overlay_dir = out_dir + '/overlay'
    os.makedirs(out_overlay_dir, exist_ok=True)

    for i, dts in enumerate(annotated_ovmerge_list):
        # base dts
        if i == 0:
            final_dts_content = '#include "{}"\n'.format(os.path.relpath(dts_files[i], out_overlay_dir))
        else:
            out_diff_dir = out_dir + '/diff_' + getFileName(dts)
            fdt_diff(annotated_ovmerge_list[0], dts, 'dts', out_diff_dir)
            overlay_dts = out_diff_dir + '/' + getFileName(dts) + '.dts'

            if os.path.exists(overlay_dts):
                with open(overlay_dts, 'r') as fin:
                    data = fin.read().splitlines(True)

                # Create a temporary file
                (tmpFile, tmpFileName) = tempfile.mkstemp(dir=out_overlay_dir,
                    prefix=getFileName(dts_files[i]) + '-', suffix='.dts')
                with os.fdopen(tmpFile, 'w') as output:
                    output.writelines(data[1:])

                final_dts_content += '#include "{}"\n'.format(os.path.basename(tmpFileName))

    final_dts = out_overlay_dir + '/final.dts'
    with open(final_dts, 'w') as output:
        output.write(final_dts_content)

    return final_dts
