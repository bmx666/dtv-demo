import os
import re
from PyQt5 import QtWidgets
import traceback

class includeTree(object):

    def addChild(self, obj):
        self.children.append(obj)

    # Search for a file within a list of directories
    # If found, return the full-path to the file
    def locate(self, name, paths):

        for path in paths:
            fullPath = path + '/' + name
            if (os.path.isfile(fullPath)):
                # File found!
                return os.path.realpath(fullPath)

        # File not found
        return None

    # Populate the currentNode.children[] list with a list of nodes.
    # - Each child node contains the details of a file directly #included.
    # - Each child node contains the files it further includes as its children.
    def findIncludedFiles(currentNode, includeDirs, includeMacros=([])):

        # NOTE: currentNode is the 'self' param here.

        currentFile = currentNode.file
        currDir = os.path.realpath(os.path.dirname(currentFile))

        # Add directory of the currentFile to
        # the list of dirs to search for included files
        includeDirs.append(currDir)

        #print('Parsing:', currentFile)
        try:
            with open(currentFile) as file:

                for line in file:
                    # Start collecting #defined macros.
                    # Latter dtsi files may attempt to #include files using these macros.
                    if ('#define' in line):
                        listOfTokens = line.split()
                        macro = listOfTokens[1]
                        if (len(listOfTokens) == 3):
                            expansion = listOfTokens[2]
                        else:
                            expansion = ''
                        includeMacros.append([macro, expansion])

                    if ('#include' in line):

                        # perform replacements of any macros
                        for includeMacro in includeMacros:
                            line = line.replace(includeMacro[0], includeMacro[1])

                        # extract filename
                        includeFound = re.search('(?<=^#include.(<|")).*(?=(>|")$)',
                                                 line.strip())
                        if includeFound:
                            includeFile = includeFound.group(0)

                        #print('Looking for included-file:', includeFile)

                        # search for the file
                        includeFileFull = currentNode.locate(includeFile,
                                                             includeDirs)

                        # if found, include it
                        if (includeFileFull):
                            #print('Found!', includeFileFull)

                            # This triggers findIncludedFiles()
                            # for the child node.
                            includeFileNode = includeTree(includeFileFull,
                                                          includeDirs,
                                                          includeMacros)

                            # NOTE: By now, the child node contains
                            # all its children (further included files).
                            currentNode.addChild(includeFileNode)

        except Exception as e:
            print('EXCEPTION!', e)
            print(traceback.format_exc())
            print('Continuing...')
            pass

        return currentNode

    def fileName(self):
        return self.file.split('/')[-1]

    def populateChildrenFileNames(self, parentRowItem):

        # skip header files
        if self.fileName().split('.')[-1] == 'h':
            return

        # add curent node...
        currItem = QtWidgets.QTreeWidgetItem([self.fileName()])
        currItem.setToolTip(0, self.file)
        parentRowItem.addChild(currItem)

        # ...and recursively look for any children nodes to print
        for node in self.children:
            node.populateChildrenFileNames(currItem)

    def printFileName(self, level=0):
        print('\t' * level, self.fileName())

    def printChildrenFileNames(self, level=0):
        # print curent node...
        self.printFileName(level)

        # ...and recursively look for any children nodes to print
        for node in self.children:
            node.printChildrenFileNames(level + 1)

    def printChildrenFilePaths(self, level=0):
        # print curent node...
        print('\t' * level, self.file)

        # ...and recursively look for any children nodes to print
        for node in self.children:
            node.printChildrenFilePaths(level + 1)

    def __init__(self, topFile, includeDirs, includeMacros=([])):
        self.file = topFile
        self.includeDirs = includeDirs
        self.children = []
        self.findIncludedFiles(includeDirs, includeMacros)

