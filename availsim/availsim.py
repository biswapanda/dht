#!/usr/bin/env python

from __future__ import generators	# only 2.2 or newer
import sys

from utils import size_rounder
from simulator import event, simulator, event_generator
import dhash

do_spread = 0

def file_evgen (fname):
    lineno = 0
    fh = open (fname)
    for l in fh:
        lineno += 1
        # Rudimentary comment parsing
        if l[0] == '#': continue
        a = l.strip ().split ()
        try:
            ev = event (int(a[0]), a[1].lower (), a[2:])
            yield ev
        except Exception, e:
            sys.stderr.write ("Bad event at line %d: %s\n" % (lineno, e))

def calc_spread (dh, stats):
    """Helper function for _monitor to calculate how far apart blocks get.
       Adds spread_min, spread_max, and spread_avg keys to stats table.
    """
    ssum = 0
    smin = 64
    smax = -1
    for b in dh.blocks:
        succs = dh.succ (b, 2*dh.look_ahead())
        found = 0
        examined = 0
        for s in succs:
            examined = examined + 1
            if b in s.blocks:
                found = found + 1
                if (found == dh.read_pieces()):
                    break
        ssum += examined
        if examined < smin: smin = examined
        if examined > smax: smax = examined
    stats['spread_min'] = smin
    if (len(dh.blocks) > 0): stats['spread_avg'] = ssum/len(dh.blocks)
    else: stats['spread_avg'] = 0
    stats['spread_max'] = smax
    
sbkeys = ['insert', 'join_repair_write', 'join_repair_read',
	  'failure_repair_write', 'failure_repair_read', 'pm']
def _monitor (dh):
    stats = {}
    allnodes = dh.allnodes.values ()

    stats['usable_bytes'] = sum (dh.blocks.values ())
    stats['sent_bytes']   = sum ([n.sent_bytes for n in allnodes])
    stats['disk_bytes']   = sum ([n.bytes      for n in allnodes])
    stats['avail_bytes']  = sum ([n.bytes      for n in dh.nodes])

    #bdist = [len(n.blocks) for n in dh.nodes]
    #bdist.sort ()
    #ab = sum(bdist) / float (len(dh.nodes))
    #sys.stderr.write ("%5.2f blocks/node on avg; max = %d, med = %d, min = %d (%d)\n" % (ab, max(bdist), bdist[len(bdist)/2], min(bdist), bdist.count(min(bdist))))

    for k in sbkeys:
	stats['sent_bytes::%s' % k] = \
		sum ([n.sent_bytes_breakdown.get (k, 0) for n in allnodes])

    extant = filter (lambda x: x > 0, dh.available.values ())
    stats['avail_blocks'] = len (extant)
#    assert stats['avail_blocks'] == dh.available_blocks ()

#    blocks = {}
#    for n in dh.nodes:
#	for b in n.blocks:
#	    blocks[b] = blocks.get (b, 0) + 1
#    extant = blocks.values ()
    try: 
	avg = sum (extant, 0.0) / len (extant)
	minimum = min (extant)
	maximum = max (extant)
    except:
	avg, minimum, maximum = 0, 0, 0
    stats['extant_avg'] = avg
    stats['extant_min'] = minimum
    stats['extant_max'] = maximum                      

    if do_spread:
	calc_spread (dh, stats)
    return stats

def print_monitor (t, dh):
    s = _monitor (dh)

    print "%4d" % t, "%4d nodes;" % len(dh.nodes),
    print "%sB sent;" % size_rounder (s['sent_bytes']),
    print "%sB put;" % size_rounder (s['usable_bytes']),
    print "%sB avail;" % size_rounder (s['avail_bytes']),
    print "%sB stored;" % size_rounder (s['disk_bytes']),
    print "%d/%5.2f/%d extant;" % (s['extant_min'], s['extant_avg'], s['extant_max']),
    print "%d/%d blocks avail" % (s['avail_blocks'], len (dh.blocks))
    if do_spread:
	print "%d/%d avg %5.2f block spread" % (s['spread_min'],
						s['spread_max'],
						s['spread_avg'])
    for k in sbkeys:
	print "%sB sent[%s];" % (size_rounder(s['sent_bytes::%s' % k]), k)

def parsable_monitor (t, dh):
    s = _monitor (dh)

    print t, len(dh.nodes), 
    print ' '.join(["%d" % s[k] for k in ['sent_bytes','usable_bytes','avail_bytes','disk_bytes']]),
    print s['extant_min'], "%5.2f" % s['extant_avg'], s['extant_max'],
    print s['avail_blocks'], len (dh.blocks),
    for k in sbkeys:
	print "%d" % s['sent_bytes::%s' % k],
    print

def usage ():
    sys.stderr.write ("%s [-i] [-m] [-s] events.txt type args\n" % sys.argv[0])
    sys.stderr.write ("where type is:\n")
    a = dhash.known_types.keys ()
    a.sort ()
    for t in a:
	sys.stderr.write ("\t%s\n" % t)

if __name__ == '__main__':
    import getopt
    # no threads or signals really
    sys.setcheckinterval (10000000)

    # default monitor, every 12 hours
    monitor = print_monitor
    monint  = 12 * 60 * 60
    try:
	opts, cmdv = getopt.getopt (sys.argv[1:], "b:i:ms")
    except getopt.GetoptError:
        usage ()
        sys.exit (1)
    for o, a in opts:
	if o == '-b':
	    dhash.BANDWIDTH_HACK = int (a)
	elif o == '-i':
	    monint = int (a)
        elif o == '-m':
            monitor = parsable_monitor
	elif o == '-s':
	    do_spread = 1
            
    if len(cmdv) < 2:
        usage ()
	sys.exit (1)

    print "# bw =", dhash.BANDWIDTH_HACK
    print "# args =", cmdv
    evfile = cmdv[0]
    dtype  = cmdv[1]
    gdh = None
    try:
	dhashclass = dhash.known_types[dtype]
	gdh = dhashclass (cmdv[2:])
    except KeyError, e:
	sys.stderr.write ("invalid dhash type\n")
        usage ()
	sys.exit (1)

    sim = simulator (gdh)
    evfh = open (evfile)
    eg = event_generator (evfh)
    sim.run (eg, monitor, monint)
