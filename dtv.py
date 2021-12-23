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

from xdg import BaseDirectory

from includetree import includeTree
from helper import loadConfig, annotateDTS

from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QDialog, QHeaderView, QMessageBox
from PyQt5.uic import loadUi

DELETED_TAG = "__[|>*DELETED*<|]__"

def getTopLevelItem(trwDT):
    return trwDT.topLevelItem(trwDT.topLevelItemCount()-1)

def populateDTS(trwDT, trwIncludedFiles, filename):

    # Clear remnants from previously opened file
    trwDT.clear()
    trwIncludedFiles.expandAll()

    with open (filename) as f:

        # Read each line in the DTS file
        lineNum = 1
        for line in f:

            # Look for the code (part before the "/*" comment)
            idx = line.rfind("/*")

            if idx < 0:
                lineContents = line.strip()
            else:
                lineContents = line[:idx].rstrip()

            if idx > 0:
                # Now pick the comment part of the line
                commentFileList = line[idx+2:].strip()[:-2]
                # Remove false positive
                if "<no-file>:<no-line>" in commentFileList:
                    commentFileList = None
            else:
                commentFileList = None

            # If found, then clean-up
            if commentFileList:
                # The last (rightmost) file in the comma-separted list of filename:lineno
                # Line numbers are made-up of integers after a ":" colon.
                listOfSourcefiles = list(map(lambda f: os.path.realpath(f.strip()), commentFileList.split(',')))
                fileWithLineNums = listOfSourcefiles[-1]

                if fileWithLineNums:
                    # Filename is the last (rightmost) word in a forward-slash-separetd path string
                    includedFilename = fileWithLineNums.split(':', 1)[0].split('/')[-1]
            else:
                fileWithLineNums = ''

            if not fileWithLineNums:
                includedFilename = ''

                # skip empty line
                if not (lineContents.lstrip()):
                    lineNum += 1
                    continue

            # find deleted tag
            isDeleted = DELETED_TAG in lineContents
            if isDeleted:
                # remove deleted tag and uncomment content
                lineContents = lineContents.replace('/* ' + DELETED_TAG + ' */ ', '')
                lineContents = re.sub('/\*(.*)?\*/\s*', r'\g<1>', lineContents, flags=re.S)

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

            rowItem.setBackground(1, bgColor)

            if isDeleted:
                rowItem.setForeground(1, QColor(255, 0, 0))
                f = rowItem.font(0)
                f.setStrikeOut(True)
                f.setBold(True)
                rowItem.setFont(1, f)

            # Include parents
            if commentFileList:
                # Skip add parents for close bracket of node
                if not (isDeleted and "};" in lineContents.strip()):
                    for fileWithLineNums in listOfSourcefiles[-2::-1]:
                        strippedLineNums = fileWithLineNums.split(':', 1)[0]
                        includedFilename = strippedLineNums.split('/')[-1]
                        rowItem = QtWidgets.QTreeWidgetItem([str(lineNum), "", includedFilename, fileWithLineNums])
                        trwDT.addTopLevelItem(rowItem)
                        item = getTopLevelItem(trwDT)
                        item.setForeground(0, QColor(255, 255, 255));
            elif not isDeleted:
                item = getTopLevelItem(trwDT)
                item.setForeground(1, QColor(175, 175, 175))
                f = item.font(0)
                item.setFont(1, f)

            lineNum += 1

def populateIncludedFiles(trwIncludedFiles, dtsFile, inputIncludeDirs):

    trwIncludedFiles.clear()
    dtsIncludeTree = includeTree(dtsFile, inputIncludeDirs)
    dummyItem = QtWidgets.QTreeWidgetItem()
    dtsIncludeTree.populateChildrenFileNames(dummyItem)
    trwIncludedFiles.addTopLevelItem(dummyItem.child(0).clone())

def highlightFileInTree(trwIncludedFiles, fileWithLineNums):
    filePath = fileWithLineNums.split(':', 1)[0]
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

    filePath = fileWithLineNums.split(':', 1)[0]

    # extract line numbers in source-file
    # TODO: Special Handling for opening and closing braces in DTS
    #       (no need to show ENTIRE node, right?)
    startLineNum = int(re.split('[[:-]', fileWithLineNums)[-4].strip())
    endLineNum = int(re.split('[[:-]', fileWithLineNums)[-2].strip())
    #print('Line='+str(lineNum), 'Source='+filePath, startLineNum, 'to', endLineNum)
    lblDT.setText(getLines(filePath, startLineNum, endLineNum))

def center(window):

    # Determine the center of mainwindow
    centerPoint = QtCore.QPoint()
    centerPoint.setX(Main.x() + (Main.width()/2))
    centerPoint.setY(Main.y() + (Main.height()/2))

    # Calculate the current window's top-left such that
    # its center co-incides with the mainwindow's center
    frameGm = window.frameGeometry()
    frameGm.moveCenter(centerPoint)

    # Align current window as per above calculations
    window.move(frameGm.topLeft())

class Main(QMainWindow):


    def __init__(self):
        super().__init__()
        self.ui = None
        self.load_ui()
        self.load_signals()
        self.findStr = None
        self.foundList = []
        self.foundIndex = 0

        if len(sys.argv) > 1:
            self.openDTSFile(sys.argv[1])

    def getRecentFilenames():
        cache_dir = BaseDirectory.save_cache_path("device-tree-visualiser")
        try:
            file = open( os.path.join(cache_dir, "recent.list") )
            return file.readlines()
        except:
            return []

    def pushToRecentFilenames(filename):
        cache_dir = BaseDirectory.save_cache_path("device-tree-visualiser")
        with open( os.path.join(cache_dir, "recent.list"), 'a' ) as file:
            try:
                # If filename is not a relative/absolute path to existing file
                # this may fail
                filepath = os.path.realpath(filename)
                file.write(filepath + '\n')
            except:
                print("WARNING: Invalid or non existent file passed to"
                    "pushToRecentFilenames: ", filename, file=sys.stderr)

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

            self.findStr = None
            self.foundList = []
            self.foundIndex = 0

            annotatedTmpDTSFileName = None
            try:
                # Current parser "plugin" claims to support DTS files under arch/* only
                baseDirPath = re.search('^.*(?=arch\/)', fileName).group(0)
                incIncludes = loadConfig(baseDirPath)

                annotatedTmpDTSFileName = annotateDTS(fileName, incIncludes)
                populateIncludedFiles(self.ui.trwIncludedFiles, fileName, incIncludes)
                populateDTS(self.ui.trwDT, self.ui.trwIncludedFiles, annotatedTmpDTSFileName)
            except Exception as e:
                print('EXCEPTION!', e)
                exit(1)
            finally:
                # Delete temporary file if created
                if annotatedTmpDTSFileName:
                    try:
                        os.remove(annotatedTmpDTSFileName)
                    except OSError:
                        pass

            self.trwDT.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.trwDT.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            self.trwDT.header().setSectionHidden(3, True)
            self.trwDT.header().resizeSection(1, 500)

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
        dtsiFileName = fileWithLineNums.split(':')[0].strip()
        if dtsiFileName == '':
            QMessageBox.information(self,
                                    'DTV',
                                    'No file for the curent line',
                                    QMessageBox.Ok)
            return

        dtsiLineNum = int(re.split('[[:-]', fileWithLineNums)[-4].strip())
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

main = Main()

# Blocks till Qt app is running, returns err code if any
qtReturnVal = app.exec_()

#Main.pushToRecentFilenames("screenshot/dtv-demo_dtc_original.png")

sys.exit(qtReturnVal)

