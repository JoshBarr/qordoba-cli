#!/usr/bin/env python
# -*- coding: utf-8 -*-s
import os
import sys


def read(path, size=-1, encoding="utf-8"):
    """return file content if file exists"""
    if not path:
        return
    if not os.path.exists(path):
        return
    if sys.version_info >= (3, 0):
        r = open(path, encoding=encoding).read(size)
    else:
        r = open(path).read(size)
    return r

def isshebang(l):
    """return True if line is shebang"""
    return l and l.find("#!") == 0

def isbinaryfile(path):
    if path is None:
        return None
    try:
        if not os.path.exists(path):
            return
    except Exception:
        return
    fin = open(path, 'rb')
    try:
        CHUNKSIZE = 1024
        while True:
            chunk = fin.read(CHUNKSIZE)
            if b'\0' in chunk:  # found null byte
                return True
            if len(chunk) < CHUNKSIZE:
                break  # done
        return False
    finally:
        fin.close()

def shebang(path):
    """return file/string shebang"""
    if not path:
        return
    path = str(path)
    if not os.path.exists(path):
        return
    if isbinaryfile(path):
        return
    content = read(path)
    lines = content.splitlines()
    if lines:
        l = lines[0]  # first line
        if isshebang(l):
            l = l.replace("#!", "", 1)
            return l.lstrip().rstrip()
