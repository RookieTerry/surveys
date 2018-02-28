#!/usr/bin/python
import json

# variious utilities for surveying

# using a class needs way less memory than random dicts apparently
class OneFP():
    __slots__ = ['ip_record','ip','asn','asndec','amazon','fprints','nsrc','rcs']
    def __init__(self):
        self.ip_record=-1
        self.ip=''
        self.asn=''
        self.asndec=0
        self.clusternum=0
        self.amazon=False
        self.fprints={}
        self.nrcs=0
        self.rcs={}

# to save memory we'll encode port collision information in a 
# compact form, we have six ports to consider 22,25,110,143,443 and 993
# and 25==25 is diferent from 25==143
# we use five octets, one for each local port;
# values are bitmasks, a set bit means the key on the remote
# port is the same as this one, so octet values can be:
# 0x00 no match
# 0x02 local port matches remote p25
# 0x06 local port matches remote p25 and p143
# etc


# reverse map from bit# to string
# the above could be done better using this... but meh
portstrings=['p22','p25','p110','p143','p443','p993']

# very old way
portscols=[0x00000f,0x0000f0,0x000f00,0x00f000,0x0f0000,0xf00000]

# new way - this is manually made symmetric around the diagonal
# variant - make all the mail colours the same
merged_nportscols=[ \
        'black',     'bisque', 'yellow', 'aquamarine','darkgray',    'magenta', \
        'bisque',    'blue',   'blue',   'blue',      'violet',      'blue', \
        'yellow',    'blue',   'blue',   'blue',      'coral',       'blue', \
        'aquamarine','blue',   'blue',   'blue',      'darkkhaki',   'blue', \
        'darkgray',  'violet', 'coral',  'darkkhaki', 'orange', 'darkseagreen', \
        'magenta',    'blue',   'blue',   'blue',      'darkseagreen','blue', ] 

# new way - individual colours per port-pair  - this is manually made symmetric around the diagonal
unmerged_nportscols=[ \
        'black',     'bisque',        'yellow', 'aquamarine', 'darkgray',     'magenta', \
        'bisque',    'blue',          'blanchedalmond',  'crimson',    'violet',    'brown', \
        'yellow', 'blanchedalmond','chartreuse',      'cyan',       'coral',        'darkred', \
        'aquamarine','crimson',       'cyan',            'darkblue',   'darkkhaki',    'darksalmon', \
        'darkgray',  'violet',     'coral',           'darkkhaki',  'orange',  'darkseagreen', \
        'magenta',     'brown',         'darkred',         'darksalmon', 'darkseagreen', 'maroon', ]


# pick one of these - the first merges many mail port combos
# leading to clearer graphs, the 2nd keeps all the details
# nportscols=merged_nportscols
nportscols=unmerged_nportscols

def indexport(index):
    return portstrings[index]

def portindex(pname):
    for pind in range(0,len(portstrings)):
        if portstrings[pind]==pname:
            return pind
    print >>sys.stderr, "Error - unknown port: " + pname
    return -1

def collmask(mask,k1,k2):
    try:
        lp=portindex(k1)
        rp=portindex(k2)
        intmask=int(mask,16)
        intmask |= (1<<(rp+8*lp)) 
        newmask="0x%012x" % intmask
    except Exception as e: 
        print >> sys.stderr, "collmask exception, k1: " + k1 + " k2: " + k2 + " lp:" + str(lp) + " rp: " + str(rp) + " exception: " + str(e)  
        pass
    return newmask

def expandmask(mask):
    emask=""
    intmask=int(mask,16)
    portcount=len(portstrings)
    for i in range(0,portcount):
        for j in range(0,portcount):
            cmpmask = (1<<(j+8*i)) 
            if intmask & cmpmask:
                emask += indexport(i) + "==" + indexport(j) + ";"
    return emask

def readfprints(fname):
    try:
        f=open(fname,'r')
        fp=json.load(f)
        f.close()
        return fp
    except Exception as e: 
        print >> sys.stderr, "exception reading " + fname + " exception: " + str(e)  
        return None

def getnextfprint(fp):
    # read the next fingerprint from the file pointer
    # fprint is a json structure, pretty-printed, so we'll
    # read to the first line that's just an "{" until
    # the next line that's just a "}"
    line=fp.readline()
    while line:
        if line=="{\n":
            break
        line=fp.readline()
    jstr=""
    while line:
        jstr += line
        if line=="}\n":
            break
        line=fp.readline()
    if line:
        jthing=json.loads(jstr)
        return jthing
    else:
        return line

def mask2labels(mask, labels):
    intmask=int(mask,16)
    portcount=len(portstrings)
    for i in range(0,portcount):
        for j in range(0,portcount):
            cmpmask = (1<<(j+8*i)) 
            if intmask & cmpmask:
                labels.append(indexport(i) + "==" + indexport(j) )

# colours - return a list of logical-Or of port-specific colour settings
def mask2colours(mask, colours, dynleg):
    intmask=int(mask,16)
    portcount=len(portstrings)
    for i in range(0,portcount):
        for j in range(0,portcount):
            cmpmask = (1<<(j+8*i)) 
            if intmask & cmpmask:
                cnum=i*len(portstrings)+j
                colcode=nportscols[cnum]
                #colcode='#'+ "%06X" % (portscols[i]|portscols[j])
                if colcode not in colours:
                    colours.append(colcode)
                    if i>j:
                        dynleg.add(portstrings[i]+"-"+portstrings[j]+" "+colcode)
                    else:
                        dynleg.add(portstrings[j]+"-"+portstrings[i]+" "+colcode)

def printlegend():
    # make a fake graph with nodes for each port and coloured edges
    leg=gv.Graph(format=the_format,engine='neato',name="legend")
    leg.attr('graph',splines='true')
    leg.attr('graph',overlap='false')
    leg.attr('edge',overlap='false')
    portcount=len(portstrings)
    c=0
    for i in range(0,portcount):
        for j in range(0,portcount):
            #colcode='#'+ "%06X" % (portscols[i]|portscols[j])
            cnum=i*len(portstrings)+j
            colcode=nportscols[cnum]
            portpair = portstrings[i] + "-" + portstrings[j] 
            #print portstrings[i] + "-" + portstrings[j] + ": " + colcode 
            #leg.edge(portstrings[i],portstrings[j],label=str(cnum),color=colcode)
            leg.edge(portstrings[i],portstrings[j],color=colcode)
    leg.render("legend.dot")

def asn2colour(asn):
    return '#' + "%06X" % (int(asn)&0xffffff)

def ip2int(ip):
    sip=ip.split(".")
    sip=list(map(int,sip))
    iip=sip[0]*256**3+sip[1]*256**2+sip[2]*256+sip[3]
    del sip
    return iip

def edgename(ip1,ip2):
    # string form consumes more memory
    #return ip1+"|"+ip2
    int1=ip2int(ip1)
    int2=ip2int(ip2)
    int3=int2*2**32+int1
    del int1
    del int2
    return int3