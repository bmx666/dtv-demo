import ast
import configparser
import os
import re
import subprocess
from subprocess import PIPE
import sys
import tempfile

def loadConfig(baseDirPath):

    # Load configuration for the conf file
    config = configparser.ConfigParser()
    config.read('dtv.conf')

    # Add or remove projects from this list
    # Only the gerrit-events of changes to projects in this list will be processed.
    includeDirStubs =  ast.literal_eval(config.get('dtv', 'include_dir_stubs'))

    incIncludes = list()

    for includeDirStub in includeDirStubs:
        incIncludes.append(baseDirPath + includeDirStub)

    return incIncludes

def annotateDTS(dtsFile, incIncludes):

    # force include dir of dtsFile
    cppIncludes = ' -I ' + os.path.dirname(dtsFile)
    dtcIncludes = ' -i ' + os.path.dirname(dtsFile)

    for includeDir in incIncludes:
        cppIncludes += ' -I ' + includeDir
        dtcIncludes += ' -i ' + includeDir

    # cpp ${cpp_flags} ${cpp_includes} ${dtx} | ${DTC} ${dtc_flags} ${dtc_include} -I dts
    try:
        cpp = 'cpp'
        cppFlags = ' -nostdinc -undef -D__DTS__ -x assembler-with-cpp '
        cppResult = subprocess.run(cpp + cppIncludes + cppFlags + dtsFile,
                                   stdout=PIPE, stderr=PIPE, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print('EXCEPTION!', e)
        print('stdout: {}'.format(e.output.decode(sys.getfilesystemencoding())))
        print('stderr: {}'.format(e.stderr.decode(sys.getfilesystemencoding())))
        exit(e.returncode)

    dtsPlugin = True if re.findall(r'\s*\/plugin\/\s*;', cppResult.stdout.decode('utf-8')) else False
    if dtsPlugin:
        print('DTS file is plugin')

    try:
        dtc = 'dtc'
        dtcFlags = ' -@ -I dts -O dts -f -s -T -T -T -T -T -o - '
        dtcResult = subprocess.run(dtc + dtcIncludes + dtcFlags,
                                   stdout=PIPE, stderr=PIPE, input=cppResult.stdout, shell=True, check=True)

    except subprocess.CalledProcessError as e:
        print('EXCEPTION!', e)
        print('stdout: {}'.format(e.output.decode(sys.getfilesystemencoding())))
        print('stderr: {}'.format(e.stderr.decode(sys.getfilesystemencoding())))
        exit(e.returncode)

    # Create a temporary file in the current working directory
    (tmpAnnotatedFile, tmpAnnotatedFileName) = tempfile.mkstemp(dir=os.path.dirname(os.path.realpath(__file__)),
                                                                prefix=os.path.basename(dtsFile) + '-',
                                                                suffix='.dts.annotated')
    with os.fdopen(tmpAnnotatedFile, 'w') as output:
        output.write(dtcResult.stdout.decode('utf-8') )

    return tmpAnnotatedFileName
