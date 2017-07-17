#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function

import contextlib
import io
import os
import re
import tempfile
import shutil
import sys

from functools import partial
from itertools import chain, imap

# Skip all common files used to support tests for jstests
# These files are listed in the README.txt
SUPPORT_FILES = set(["browser.js", "shell.js", "template.js", "user.js",
    "js-test-driver-begin.js", "js-test-driver-end.js"])

def convertTestFile(testSource):
    """
    Convert a jstest test to a compatible Test262 test file.
    """

    newSource = captureHeader(testSource)
    newSource = captureReportCompare(newSource)
    return newSource

def captureReportCompare(source):
    p = re.compile(r'reportCompare\(\s*(\S*)\s*,\s*(\S*)\s*(,\s*\S*)?\);* ?(.*)$', re.MULTILINE)

    token = p.finditer(source)

    newSource = source

    for part in token:
        actual = part.group(1)
        expected = part.group(2)

        if actual == expected:
            if actual == "true" or actual == "0":
                newSource = newSource.replace(part.group(), part.group(4), 1)
                continue;
        
        newSource = newSource.replace("reportCompare(", "assert.sameValue(", 1)

    return newSource

def collectRefTestEntries(reftest):
    """
    Collects and stores the entries from the reftest header.
    """

    terms = []
    comments = []

    # should capture conditions to skip
    matchesSkip = re.search(r'skip-if\((.*)\)', reftest)
    if matchesSkip:
        matches = matchesSkip.group(1).split('||')
        for match in matches:
            # TODO: can we use this to populate a features list?
            dependsOnProp = re.search(r'!this.hasOwnProperty\([\'\"](.*)[\'\"]\)', match)
            if dependsOnProp:
                print("DEPENDS: %s" % dependsOnProp.group(1))

    # should capture the expected error
    matchesError = re.search(r'error:\s*(\w*)', reftest)
    if matchesError:
        # TODO: populate the yaml negative flags
        # issue: we can't say it's a runtime or an early error.
        # If it's not a SyntaxError or a ReferenceError, assume it's a runtime error (?)
        print("error: %s" % matchesError.group(1))

    # just tells if it's a module
    matchesModule = re.search(r'\smodule(\s|$)', reftest)
    if matchesModule:
        # TODO: flags: module
        print("is module")

    # captures any comments
    matchesComments = re.search(r' -- (.*)', reftest)
    if matchesComments:
        # TODO: use the comments on the yaml info tag
        print("comments: %s" % matchesComments.group(1))

    return None

def captureHeader(source):
    from lib.manifest import TEST_HEADER_PATTERN_INLINE, \
            TEST_HEADER_PATTERN_MULTI

    # Bail early if we do not start with a single comment.
    if not source.startswith("//"):
        return source

    # Extract the token.
    part, _, _ = source.partition('\n')
    matches = TEST_HEADER_PATTERN_INLINE.match(part)

    if not matches:
        # Search for a header using the /* */ pattern.
        matches = TEST_HEADER_PATTERN_MULTI.match(part)
        if not matches:
            return source

    # Remove the header from the source
    newSource = source.replace(matches.group(0) + "\n", "")

    collectRefTestEntries(part)

    return newSource

def exportTest262(args):
    src = args.src
    outDir = args.out

    if not os.path.isabs(src):
        src = os.path.join(os.getcwd(), src)

    if not os.path.isabs(outDir):
        outDir = os.path.join(os.getcwd(), outDir)

    # Create the output directory from scratch.
    if os.path.isdir(outDir):
        shutil.rmtree(outDir)

    # Process all test directories recursively.
    for (dirPath, _, fileNames) in os.walk(src):
        relPath = os.path.relpath(dirPath, src)

        # This also creates the own outDir folder
        if not os.path.exists(os.path.join(outDir, relPath)):
            os.makedirs(os.path.join(outDir, relPath))

        for fileName in fileNames:
            # Skip browser.js and shell.js files
            if fileName == "browser.js" or fileName == "shell.js":
                continue

            filePath = os.path.join(dirPath, fileName)
            testName = os.path.relpath(filePath, src) # captures folder/fileName

            # Copy non-test files as is.
            (_, fileExt) = os.path.splitext(fileName)
            if fileExt != ".js":
                shutil.copyfile(filePath, os.path.join(outDir, testName))
                print("C %s" % testName)
                continue

            # Read the original test source and preprocess it for Test262
            with io.open(filePath, "rb") as testFile:
                testSource = testFile.read()

            newSource = convertTestFile(testSource)

            with io.open(os.path.join(outDir, testName), "wb") as output:
                output.write(newSource)

            print("S %s" % testName)

if __name__ == "__main__":
    import argparse

    # This script must be run from js/src/tests to work correctly.
    if "/".join(os.path.normpath(os.getcwd()).split(os.sep)[-3:]) != "js/src/tests":
        raise RuntimeError("%s must be run from js/src/tests" % sys.argv[0])

    parser = argparse.ArgumentParser(description="Export tests to match Test262 file compliance.")
    parser.add_argument("--out", default="test262/export",
                        help="Output directory. Any existing directory will be removed! (default: %(default)s)")
    parser.add_argument("src", nargs="?", help="Source folder with test files to export")
    parser.set_defaults(func=exportTest262)
    args = parser.parse_args()
    args.func(args)
