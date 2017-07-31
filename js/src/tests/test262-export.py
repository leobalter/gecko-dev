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
import yaml

from functools import partial
from itertools import chain, imap

# Skip all common files used to support tests for jstests
# These files are listed in the README.txt
SUPPORT_FILES = set(["browser.js", "shell.js", "template.js", "user.js",
    "js-test-driver-begin.js", "js-test-driver-end.js"])

FRONTMATTER_WRAPPER_PATTERN = re.compile(
    r'/\*\---\n([\s]*)((?:\s|\S)*)[\n\s*]---\*/',
    flags=re.DOTALL|re.MULTILINE)

def convertTestFile(source):
    """
    Convert a jstest test to a compatible Test262 test file.
    """

    source = parseReportCompare(source)
    source = updateMeta(source)

    return source

def parseReportCompare(source):
    """
    Captures all the reportCompare and convert them accordingly.

    Cases with reportCompare calls where the arguments are the same and one of
    0, true, or null, will be discarded as they are not necessary for Test262.

    Otherwise, reportCompare will be replaced with assert.sameValue, as the
    equivalent in Test262
    """
    p = re.compile(
        r'^.*reportCompare\s*\(\s*(0|true|null)\s*,\s*(0|true|null)\s*(,\s*\S*)?\s*\)\s*;*\s*',
        re.MULTILINE
    )

    token = p.finditer(source)

    newSource = source

    for part in token:
        actual = part.group(1)
        expected = part.group(2)

        if actual == expected:
            newSource = newSource.replace(part.group(), "", 1)
            continue;

    for part in re.finditer(r'(\.|\W)?(reportCompare)\W?', newSource, re.MULTILINE):
        newSource = newSource.replace(part.group(2), "assert.sameValue")

    return newSource

def fetchReftestEntries(reftest):
    """
    Collects and stores the entries from the reftest header.
    """

    # TODO: fails, slow, skip, random, random-if

    features = []
    error = None
    comments = None
    module = False

    # should capture conditions to skip
    matchesSkip = re.search(r'skip-if\((.*)\)', reftest)
    if matchesSkip:
        matches = matchesSkip.group(1).split("||")
        for match in matches:
            # captures a features list
            dependsOnProp = re.search(
                r'!this.hasOwnProperty\([\'\"](.*)[\'\"]\)', match)
            if dependsOnProp:
                features.append(dependsOnProp.group(1))
            # TODO: how do we parse the other skip conditions?

    # should capture the expected error
    matchesError = re.search(r'error:\s*(\w*)', reftest)
    if matchesError:
        # issue: we can't say it's a runtime or an early error.
        # If it's not a SyntaxError or a ReferenceError,
        # assume it's a runtime error(?)
        error = matchesError.group(1)

    # just tells if it's a module
    matchesModule = re.search(r'\smodule(\s|$)', reftest)
    if matchesModule:
        module = True

    # captures any comments
    matchesComments = re.search(r' -- (.*)', reftest)
    if matchesComments:
        comments = matchesComments.group(1)

    return {
        "features": features,
        "error": error,
        "module": module,
        "info": comments
    }

def parseHeader(source):
    """
    Parse the source to return it with the extracted the header
    """
    from lib.manifest import TEST_HEADER_PATTERN_INLINE

    # Bail early if we do not start with a single comment.
    if not source.startswith("//"):
        return (source, {})

    # Extract the token.
    part, _, _ = source.partition("\n")
    matches = TEST_HEADER_PATTERN_INLINE.match(part)

    if matches and matches.group(0):
        reftest = matches.group(0)

        # Remove the found header from the source;
        # Fetch and return the reftest entries
        return (source.replace(reftest + "\n", ""), fetchReftestEntries(reftest))

    return (source, {})

def fetchMeta(source):
    """
    Capture the frontmatter metadata as yaml if it exists.
    Returns a new dict if it doesn't.
    """

    match = FRONTMATTER_WRAPPER_PATTERN.search(source)
    if not match:
        return {}

    unindented = re.sub('^' + match.group(1), '',
        match.group(2), flags=re.MULTILINE)

    return yaml.safe_load(unindented)

def updateMeta(source):
    """
    Captures the reftest meta and a pre-existing meta if any and merge them
    into a single dict.
    """

    # Extract the reftest data from the source
    source, reftest = parseHeader(source)

    # Collect the frontmatter data from the source
    frontmatter = fetchMeta(source)

    # Merge the reftest and frontmatter
    merged = mergeMeta(reftest, frontmatter)

    # Cleanup the metadata
    properData = cleanupMeta(merged)

    return insertMeta(source, properData)

def cleanupMeta(meta):
    """
    Clean up all the frontmatter meta tags. This is not a lint tool, just a
    simple cleanup to remove trailing spaces and duplicate entries from lists.
    """

    # Populate required tags
    for tag in ("description", "esid"):
        if tag not in meta:
            meta[tag] = "pending"

    # Trim values on each string tag
    for tag in ("description", "esid", "es5id", "es6id", "info", "author"):
        if tag in meta:
            meta[tag] = meta[tag].strip()

    # Remove duplicate entries on each list tag
    for tag in ("features", "flags", "includes"):
        if tag in meta:
            # We need the list back for the yaml dump
            meta[tag] = list(set(meta[tag]))

    if "negative" in meta:
        # If the negative tag exists, phase needs to be present and set
        if "phase" not in meta["negative"] or \
            meta["negative"]["phase"] not in ("early", "runtime"):
                print("Warning: the negative.phase is not properly set.\n" + \
                    "Ref https://github.com/tc39/test262/blob/master/INTERPRETING.md#negative")
        # If the negative tag exists, type is required
        if "type" not in meta["negative"]:
            print("Warning: the negative.type is not set.\n" + \
                "Ref https://github.com/tc39/test262/blob/master/INTERPRETING.md#negative")

    return meta

def mergeMeta(reftest, frontmatter):
    """
    Merge the metadata from reftest and an existing frontmatter and populate
    required frontmatter fields properly.
    """

    # Merge the meta from reftest to the frontmatter

    if "features" in reftest:
        if "features" in frontmatter:
            frontmatter["features"] += reftest["features"]
        else:
            frontmatter["features"] = reftest["features"]

    # Only add the module flag if the value from reftest is truish
    if reftest.get("module"):
        if "flags" in frontmatter:
            frontmatter["flags"].append("module")
        else:
            frontmatter["flags"] = ["module"]

    # Add any comments to the info tag
    if reftest.get("info"):
        info = reftest["info"]

        # Open some space in an existing info text
        if "info" in frontmatter:
            frontmatter["info"] += "\n\n  "

        frontmatter["info"] = info
    
    # Set the negative flags
    if "error" in reftest:
        error = reftest["error"]
        if "negative" not in frontmatter:
            frontmatter["negative"] = {
                "phase": "early",
                "type": error
            }
        # Print a warning if the errors don't match
        elif frontmatter["negative"].get("type") != error:
            print("Warning: The reftest error doesn't match the existing " + \
                "frontmatter error. %s != %s" % (error,
                frontmatter["negative"]["type"]))

    return frontmatter

def insertMeta(source, frontmatter):
    """
    Insert the formatted frontmatter into the file, use the current existing
    space if any
    """
    lines = []

    lines.append("/*---")

    for (key, value) in frontmatter.items():
        if key in ("description", "info"):
            lines.append("%s: |" % key)
            lines.append("  " + yaml.dump(value, encoding="utf8",
                ).strip().replace('\n...', ''))
        else:
            lines.append(yaml.dump({key: frontmatter[key]}, encoding="utf8",
                default_flow_style=False).strip())


    #lines.append(yaml.dump(frontmatter, encoding='utf8',
    #    default_flow_style=False).strip())
    lines.append("---*/")

    match = FRONTMATTER_WRAPPER_PATTERN.search(source)

    if match:
        return source.replace(match.group(0), "\n".join(lines))
    else:
        return "\n".join(lines) + source

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

            if not testSource:
                print("SKIPPED %s" % testName)
                continue

            newSource = convertTestFile(testSource)

            with io.open(os.path.join(outDir, testName), "wb") as output:
                output.write(newSource)

            print("SAVED %s" % testName)

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
