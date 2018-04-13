#!/usr/bin/python

# Copyright (C) 2018 Stephen Farrell, stephen.farrell@cs.tcd.ie
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Count keys that are (a) re-used for given port and (b) are/aren't browser-trusted
# and (c) where the x.509 names (DNs,SANs) are the same/differ

import sys
import os
import tempfile
import gc
import copy
import argparse
import datetime
import pytz # for adding back TZ info to allow comparisons

import time
import subprocess
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
import binascii

from pympler import asizeof

codedir=os.path.dirname(os.path.realpath(__file__))
pdir=os.path.dirname(codedir)

sys.path.insert(0,pdir)
from SurveyFuncs import *

def usage():
    print 'Count keys that are (a) re-used for given port and (b) are/aren\'t browser-trusted'
    print 'and (c) where the x.509 names (DNs,SANs) are the same/differ'
    print 'usage: ' + sys.argv[0] + ' -p <port> -i <space separated list of cluster files>'
    print '   port defaults to 443'
    sys.exit(99)

# command line arg handling 
parser=argparse.ArgumentParser(description='Anonymise all the IP addresses that don\'t belong to the given AS for the set of cluster files given')
parser.add_argument('-i','--infiles',     
                    dest='fnames',
                    help='space separated list of file names')
parser.add_argument('-p','--port',     
                    dest='port',
                    help='space separated list of file names')
args=parser.parse_args()

port='p443'
if args.port is not None:
    port='p'+args.port
    if port == 'p22':
        print "Port 22 isn't allowed sorry:-)"
        sys.exit(1)
    if port not in portstrings:
        print "Bad port ("+str(args.port)+") - only  25, 110, 143, 443, 587, 993  allowed"
        sys.exit(1)

    
if args.fnames is None:
    usage()
    sys.exit(2)

# main line processing ...

print "Starting for " + port

checkcount=0
fpsdone={}

dnstr=port+'dn'
sanstr=port+'san'

for fname in args.fnames.split(' '):
    print "Reading " + fname

    # open file
    fp=open(fname,"r")

    f=getnextfprint(fp)
    while f:

        try:
            if port in f.fprints:
                thisfp=f.fprints[port]
                certnames=set()
                bannerdns=set()
                # include banner, if there, for p25 or if banner is a besty
                if 'banner' in f.analysis['nameset'] and ('banner' in f.analysis['nameset']['besty'] or port=='p25'):
                    # scrub doofus names
                    if not name_bogon(f.analysis['nameset']['banner']):
                        bannerdns.add(f.analysis['nameset']['banner'])
                if 'rnds' in f.analysis['nameset']:
                    if not name_bogon(f.analysis['nameset']['rdns']):
                        bannerdns.add(f.analysis['nameset']['rdns'])
                if dnstr in f.analysis['nameset']:
                    if not name_bogon(f.analysis['nameset'][dnstr]):
                        certnames.add(f.analysis['nameset'][dnstr])
                for sanind in range(0,20):
                    sst=sanstr+str(sanind)
                    if sst in f.analysis['nameset']:
                        if not name_bogon(f.analysis['nameset'][sst]):
                            certnames.add(f.analysis['nameset'][sst])
                    else:
                        # get out of loop when we see 1st not there
                        break
                bt=f.analysis[port]["browser_trusted"]
                accum={}
                accum['ip']=f.ip
                accum['bt']=bt
                accum['certnames']=certnames
                accum['bannerdns']=bannerdns
                #if bt:
                    #print "browser_trusted:" + f.ip + "/" + port + " " + thisfp + " " + "names:" + str(names)
                #else:
                    #print "not browser_trusted:" + f.ip + "/" + port + " " + thisfp + " " + "names:" + str(names)
                    
                if thisfp not in fpsdone:
                    fpsdone[thisfp]=[]
                fpsdone[thisfp].append(accum)

        except Exception as e: 
            print "Error with " + f.ip + " " + str(e)
            pass

        # print something now and then to keep operator amused
        checkcount += 1
        if checkcount % 100 == 0:
            print >> sys.stderr, "Counting browser-trusted stuff, host: " + str(checkcount) 
        if checkcount % 1000 == 0:
            gc.collect()

        # read next fp
        f=getnextfprint(fp)

    # close file
    fp.close()

print "Overall:" + str(checkcount) 

#print "All fingerprints for port("+port+"):"
#for fp in fpsdone:
    #print "fp: " + fp
    #for val in fpsdone[fp]:
        #print "    " + str(val)

# see if there's any very dubious ones...
print "Dodgy browser-trusted fingerprints for port("+port+"):"
dodgycount=0
for fp in fpsdone:
    lv=len(fpsdone[fp])
    if lv<=1:
        continue
    somebt=False
    notallbt=False
    for val in fpsdone[fp]:
        if val['bt']:
            somebt=True
        else:
            notallbt=True
    if somebt:
        # maybe dodgy!!
        dodgycount += 1
        print "Dodgy-fp: " + fp 
        firstone=True
        vcp=set()
        lastbt=True
        somebtchange=False
        somenamediff=False
        for val in fpsdone[fp]:
            if firstone:
                vcp=val['certnames']
                lastbt=val['bt']
                firstone=False
                print "    " + str(val)
                #print vcp
            else:
                #print vcp,val['certnames']
                if vcp != val['certnames']: 
                    somenamediff=True
                if lastbt != val['bt']:
                    somebtchange=True
                print "    " + str(val)
                vcp=val['certnames']
                lastbt=val['bt']
        if somebtchange:
            print "    EEK - BT change above" 
        if somenamediff:
            print "    EEK - NameSet change from above"

print "Dodgy-count: " + str(dodgycount)