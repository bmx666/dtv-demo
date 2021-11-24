#!/usr/bin/env python3

import ast
import configparser
import hashlib
import os
import re
import string
import subprocess
from subprocess import PIPE
import sys
import tempfile

from includetree import includeTree

from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QDialog, QHeaderView, QMessageBox
from PyQt5.uic import loadUi

includedFiles = list()

DELETED_TAG = "__[|>*DELETED*<|]__"

def getTopLevelItem(trwDT):
    return trwDT.topLevelItem(trwDT.topLevelItemCount()-1)

def populateDTS(trwDT, trwIncludedFiles, filename):

    # Clear remnants from previously opened file
    includedFiles.clear()
    trwDT.clear()
    trwIncludedFiles.expandAll()

    with open (filename) as f:

        # Read each line in the DTS file
        lineNum = 1
        for line in f:

            # Look for the code (part before the "/*" comment)
            lineContents = re.search('^.*(;|(?=\/\*))', line)

            # If found, then clean-up
            if (lineContents):
                lineContents= lineContents.group(0).rstrip()
            else:
                lineContents = ""

            # Now pick the comment part of the line
            codeComment = re.search('(?<=\/\*).*(?=\*\/)', line.strip())

            # Remove false positive
            if codeComment:
                codeComment = codeComment.group(0).strip()
                if "<no-file>:<no-line>" in codeComment:
                    codeComment = None

            # If found, then clean-up
            if codeComment:
                # The last (rightmost) file in the comma-separted list of filename:lineno
                # Line numbers are made-up of integers after a ":" colon.
                listOfSourcefiles = []
                for file in codeComment.split(','):
                    if not DELETED_TAG in file:
                        listOfSourcefiles.append(os.path.realpath(file.strip()))

                includedFiles.append(listOfSourcefiles)

                if listOfSourcefiles[-1]:
                    fileWithLineNums = listOfSourcefiles[-1]
                    strippedLineNums = re.search('.*?(?=:)', listOfSourcefiles[-1]).group(0).strip()
                    # Filename is the last (rightmost) word in a forward-slash-separetd path string
                    includedFilename = strippedLineNums.split('/')[-1]
                else:
                    fileWithLineNums = ''
                    strippedLineNums = ''
                    includedFilename = ''

            else:
                fileWithLineNums = ''
                includedFilename = ''
                includedFiles.append([''])
                strippedLineNums = ''

                # skip empty line
                if not (lineContents.strip()):
                    lineNum += 1
                    continue


            # Add line to the list
            rowItem = QtWidgets.QTreeWidgetItem([str(lineNum), lineContents, includedFilename, fileWithLineNums])
            trwDT.addTopLevelItem(rowItem)

            # Pick a different background color for each filename
            if includedFilename:
                colorHash = (int(hashlib.sha1(includedFilename.encode('utf-8')).hexdigest(), 16) % 16) * 4
                prevColorHash = colorHash
                bgColor = QColor(255-colorHash*2, 240, 192+colorHash)
            else:
                bgColor = QColor(255, 255, 255)

            item = getTopLevelItem(trwDT)
            item.setBackground(1, bgColor)

            # Include parents
            if codeComment:

                if DELETED_TAG in codeComment:
                    item = getTopLevelItem(trwDT)
                    item.setForeground(1, QColor(255, 0, 0))
                    f = item.font(0)
                    f.setStrikeOut(True)
                    item.setFont(1, f)

                # Skip add parents for close bracket of node
                if not (DELETED_TAG in codeComment and "};" in lineContents.strip()):
                    for fileWithLineNums in listOfSourcefiles[:-1]:
                        strippedLineNums = os.path.realpath(re.search('.*?(?=:)', fileWithLineNums).group(0).strip())
                        includedFilename = strippedLineNums.split('/')[-1]
                        rowItem = QtWidgets.QTreeWidgetItem([str(lineNum), "", includedFilename, fileWithLineNums])
                        trwDT.addTopLevelItem(rowItem)
                        item = getTopLevelItem(trwDT)
                        item.setForeground(0, QColor(255, 255, 255));

            lineNum += 1

def populateIncludedFiles(trwIncludedFiles, dtsFile, inputIncludeDirs):

    trwIncludedFiles.clear()
    dtsIncludeTree = includeTree(dtsFile, inputIncludeDirs)
    dummyItem = QtWidgets.QTreeWidgetItem()
    dtsIncludeTree.populateChildrenFileNames(dummyItem)
    trwIncludedFiles.addTopLevelItem(dummyItem.child(0).clone())

def annotateDTS(trwIncludedFiles, dtsFile):

    # Load configuration for the conf file
    config = configparser.ConfigParser()
    config.read('dtv.conf')

    # Add or remove projects from this list
    # Only the gerrit-events of changes to projects in this list will be processed.
    includeDirStubs =  ast.literal_eval(config.get('dtv', 'include_dir_stubs'))

    cppFlags = ''
    cppIncludes = ''
    dtcIncludes = ''
    incIncludes = list()

    # Current parser "plugin" claims to support DTS files under arch/arm* only
    baseDir = re.search('^.*(?=arch\/arm)', dtsFile)
    if baseDir:
        baseDirPath = baseDir.group(0)

    for includeDirStub in includeDirStubs:
        cppIncludes += ' -I ' + baseDirPath + includeDirStub
        dtcIncludes += ' -i ' + baseDirPath + includeDirStub
        incIncludes.append(baseDirPath + includeDirStub)

    populateIncludedFiles(trwIncludedFiles, dtsFile, incIncludes)

    # cpp ${cpp_flags} ${cpp_includes} ${dtx} | ${DTC} ${dtc_flags} ${dtc_include} -I dts
    try:
        cpp = 'cpp '
        cppFlags += '-nostdinc -undef -D__DTS__ -x assembler-with-cpp '
        cppResult = subprocess.run(cpp + cppFlags + cppIncludes + ' ' + dtsFile,
                                   stdout=PIPE, stderr=PIPE, shell=True, check=True)

        dtc = 'dtc '
        dtcFlags = '-I dts -O dts -f -s -T -T -o - '
        dtcResult = subprocess.run(dtc + dtcFlags + dtcIncludes, stdout=PIPE, stderr=PIPE, input=cppResult.stdout, shell=True, check=True)

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

def highlightFileInTree(trwIncludedFiles, fileWithLineNums):
    filePath = re.search('.*?(?=:)', fileWithLineNums).group(0).strip()
    fileName = filePath.split('/')[-1]
    items = trwIncludedFiles.findItems(fileName, QtCore.Qt.MatchRecursive)
    currItem = next(item for item in items if item.toolTip(0) == filePath)

    # highlight/select current item
    trwIncludedFiles.setCurrentItem(currItem)

    # highlight/select all its parent items
    while (currItem.parent()):
        currItem = currItem.parent()
        currItem.setSelected(True)

def getLines(fileName, startLineNum, endLineNum):

    lines = ''

    with open(fileName) as f:
        fileLines = f.readlines()

        if (startLineNum == endLineNum):
            lines = fileLines[startLineNum-1]
        else:
            for line in range(startLineNum-1, endLineNum):
                lines += fileLines[line]

    return lines

def showOriginalLineinLabel(lblDT, lineNum, fileWithLineNums):

    includedFile = next(f for f in includedFiles[lineNum-1] if fileWithLineNums == f)
    filePath = re.search('.*?(?=:)', fileWithLineNums).group(0).strip()

    # extract line numbers in source-file
    # TODO: Special Handling for opening and closing braces in DTS
    #       (no need to show ENTIRE node, right?)
    startLineNum = int(re.split('[[:-]', includedFile)[-4].strip())
    endLineNum = int(re.split('[[:-]', includedFile)[-2].strip())
    #print('Line='+str(lineNum), 'Source='+filePath, startLineNum, 'to', endLineNum)
    lblDT.setText(getLines(filePath, startLineNum, endLineNum))

def center(window):

    # Determine the center of mainwindow
    centerPoint = QtCore.QPoint()
    centerPoint.setX(main.x() + (main.width()/2))
    centerPoint.setY(main.y() + (main.height()/2))

    # Calculate the current window's top-left such that
    # its center co-incides with the mainwindow's center
    frameGm = window.frameGeometry()
    frameGm.moveCenter(centerPoint)

    # Align current window as per above calculations
    window.move(frameGm.topLeft())

class main(QMainWindow):


    def __init__(self):
        super().__init__()
        self.ui = None
        self.load_ui()
        self.load_signals()
        self.annotatedTmpDTSFileName = None  # Deleted upon exit
        self.annotatedDTSFileName = None     # Retained upon exit
        self.findStr = None
        self.foundList = []
        self.foundIndex = 0

        if len(sys.argv) > 1:
            self.openDTSFile(sys.argv[1])

    def closeEvent(self, event):
        # Delete temporary file if created
        if self.annotatedTmpDTSFileName:
            try:
                os.remove(self.annotatedTmpDTSFileName)
            except OSError:
                pass

    def openDTSFileUI(self):

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,
                                                  "Select a DTS file to visualise...",
                                                  "", "All DTS Files (*.dts)",
                                                  options=options)
        self.openDTSFile(fileName)

    def openDTSFile(self, fileName):

        # If user selected a file then process it...
        if fileName:
            # Resolve symlinks
            filename = os.path.realpath(fileName)

            self.ui.setWindowTitle("DTV - " + fileName)

            # Delete temporary file if created (from a previous "open")
            if self.annotatedTmpDTSFileName:
                try:
                    os.remove(self.annotatedTmpDTSFileName)
                except OSError:
                    pass

            self.findStr = None
            self.foundList = []
            self.foundIndex = 0

            self.annotatedTmpDTSFileName = annotateDTS(self.ui.trwIncludedFiles, fileName)
            populateDTS(self.ui.trwDT, self.ui.trwIncludedFiles, self.annotatedTmpDTSFileName)

            self.trwDT.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.trwDT.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)

    def highlightSourceFile(self):

        # Skip if no "current" row
        if self.ui.trwDT.currentItem() is None:
            return

        # Skip if current row is "whitespace"
        if self.ui.trwDT.currentItem().text(2) == '':
            self.ui.lblDT.setText('')
            return

        # Else identify and highlight the source file of the current row
        if self.ui.trwDT.currentItem():
            highlightFileInTree(self.ui.trwIncludedFiles, self.ui.trwDT.currentItem().text(3))
            showOriginalLineinLabel(self.ui.lblDT, int(self.ui.trwDT.currentItem().text(0)), self.ui.trwDT.currentItem().text(3))

    def launchEditor(self, srcFileName, srcLineNum):

        # Load configuration for the conf file
        config = configparser.ConfigParser()
        config.read('dtv.conf')

        # Launch user-specified editor
        editorCommand = ast.literal_eval(config.get('dtv', 'editor_cmd'))
        editorCommandEvaluated = string.Template(editorCommand).substitute(locals())

        try:
            launchEditor = subprocess.Popen(editorCommandEvaluated.split(),
                                        stdin=None, stdout=None, stderr=None,
                                        close_fds=True)
        except FileNotFoundError:
            QMessageBox.warning(self,
                            'DTV',
                            'Failed to launch editor!\n\n' +
                            editorCommandEvaluated +
                            '\n\nPlease modify "dtv.conf" using any text editor.',
                            QMessageBox.Ok)

    def editSourceFile(self):

        # TODO: Refactor. Same logic used by showOriginalLineinLabel() too
        lineNum = int(self.ui.trwDT.currentItem().text(0))
        fileWithLineNums = self.ui.trwDT.currentItem().text(3)
        includedFile = next(file for file in includedFiles[lineNum-1] if fileWithLineNums == file)
        dtsiFileName = includedFile.split(':')[0].strip()
        if dtsiFileName == '':
            QMessageBox.information(self,
                                    'DTV',
                                    'No file for the curent line',
                                    QMessageBox.Ok)
            return

        dtsiLineNum = int(re.split('[[:-]', includedFile)[-4].strip())
        self.launchEditor(dtsiFileName, dtsiLineNum)

    def editIncludedFile(self):
        includedFileName = self.ui.trwIncludedFiles.currentItem().toolTip(0)
        self.launchEditor(includedFileName, '0')

    def findTextinDTS(self):

        findStr = self.txtFindText.text()

        # Very common for use to click Find on empty string
        if findStr == "":
            return


        # New search string ?
        if findStr != self.findStr:
            self.findStr = findStr
            self.foundList = self.trwDT.findItems(self.findStr, QtCore.Qt.MatchContains | QtCore.Qt.MatchRecursive, column=1)
            self.foundIndex = 0
            numFound = len(self.foundList)
        else:
            numFound = len(self.foundList)
            if numFound:
                if ('Prev' in self.sender().objectName()):
                    # handles btnFindPrev
                    self.foundIndex = (self.foundIndex - 1) % numFound
                else:
                    # handles btnFindNext and <Enter> on txtFindText
                    self.foundIndex = (self.foundIndex + 1) % numFound

        if numFound:
            self.trwDT.setCurrentItem(self.foundList[self.foundIndex])

    def showSettings(self):
        QMessageBox.information(self,
                            'DTV',
                            'Settings GUI NOT supported yet.\n'
                            'Please modify "dtv.conf" using any text editor.',
                            QMessageBox.Ok)
        return

    def center(self):
        frameGm = self.frameGeometry()
        screen = QtWidgets.QApplication.desktop().screenNumber(QtWidgets.QApplication.desktop().cursor().pos())
        centerPoint = QtWidgets.QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def load_ui(self):
        self.ui = loadUi('dtv.ui', self)
        self.ui.openDTS.triggered.connect(self.openDTSFileUI)
        self.ui.exitApp.triggered.connect(self.close)
        self.ui.optionsSettings.triggered.connect(self.showSettings)
        self.ui.trwDT.currentItemChanged.connect(self.highlightSourceFile)
        self.ui.trwDT.itemDoubleClicked.connect(self.editSourceFile)
        self.ui.trwIncludedFiles.itemDoubleClicked.connect(self.editIncludedFile)
        self.ui.btnFindPrev.clicked.connect(self.findTextinDTS)
        self.ui.btnFindNext.clicked.connect(self.findTextinDTS)
        self.ui.txtFindText.returnPressed.connect(self.findTextinDTS)

        self.trwDT.setHeaderLabels(['Line No.', 'DTS content ....', 'Source File', 'Full path'])

        self.center()
        self.show()

    def load_signals(self):
        pass

try:
    subprocess.run('which cpp dtc', stdout=PIPE, stderr=PIPE, shell=True, check=True)
except subprocess.CalledProcessError as e:
    print('EXCEPTION!', e)
    print('stdout: {}'.format(e.output.decode(sys.getfilesystemencoding())))
    print('stderr: {}'.format(e.stderr.decode(sys.getfilesystemencoding())))
    exit(e.returncode)

try:
    subprocess.run('dtc --annotate -h', stdout=PIPE, stderr=PIPE, shell=True, check=True)
except subprocess.CalledProcessError as e:
    print('EXCEPTION!', e)
    print('EXCEPTION!', 'dtc version it too old and it doesn\'t support "annotate" option')
    exit(e.returncode)

app = QApplication(sys.argv)

main = main()

# Blocks till Qt app is running, returns err code if any
qtReturnVal = app.exec_()

sys.exit(qtReturnVal)

