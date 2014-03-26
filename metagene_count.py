#!/usr/bin/python
'''The first step of metagene_analysis, metagene_count.py compiles read abundance
over genomic features to create the input for metagene_windows.py. Please 
see README for full details and examples.

Based on Perl code by Karl F. Erhard, Jr Copyright (c) 2011
Modified to Python by Joy-El R.B. Talbot Copyright (c) 2014

The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

import sys, re, datetime, subprocess
import argparse		# to parse the command line arguments

PROGRAM = "metagene_count.py"
VERSION = "0.1.2"
UPDATED = "140325 JRBT"

class Error(Exception):
    pass

##TODO fix error handling for MetageneErrors: print error and exit!
class MetageneError(Error):
    '''For illegal/illogical metagene attributes.'''
    def __init__(self, obj, message):
        self.obj = obj
        self.message = message
    
    def __str__(self):
        return "MetageneError: {}".format(self.message)


class Metagene(object):
    '''Feature defined by an interval of interest and padding around said interval (will be 0-based). Regardless of padding side (left or right), negative padding values will shorten the interval, positive padding values will extend the interval. Minimum metagene length is 1.'''

    ##TODO add functionality for negative paddings!!
    # restrict attributes for each instance
    __slots__ = ['padding_left','interval','padding_right', 'length']
    
    def __init__(self, interval, padding_left, padding_right):
        '''Initiate lengths from the interval and padding.'''
        
        # confirm interval is INT > 0
        try: 
            interval = int(interval)
            if interval < 1:
                raise MetageneError(interval, "Minimum interval length is 1.")
        except ValueError:
            raise MetageneError(interval, "Interval must be an integer greater than zero")
        except MetageneError as m:
            print m
        
        # confirm paddings are INTs
        try: 
            padding_left = int(padding_left)
            padding_right = int(padding_right)
            if padding_left < 0 or padding_right < 0:
                raise MetageneError((padding_left, padding_right), "Padding values must be positive")
        except ValueError:
            raise MetageneError((padding_left, padding_right), "Padding lengths must be integers")
        except MetageneError as m:
            print m
        
        # confirm resulting metagene has at least a length of 1  
        try:
            length = interval + padding_left + padding_right  
            if length < 1:
                raise MetageneError(length, "Invalid final length to metagene (interval + padding_left + padding_right = {})".format(length))
        except MetageneError as m:
            print m
            
        # everything checks out; store the object
        self.interval = interval
        self.padding_left = padding_left
        self.padding_right = padding_right
        self.length = length
    # end __init__ function
    
    def get_interval_start(self):
        return (self.padding_left)
    
    def get_interval_end(self):
        return (self.padding_left + self.interval - 1)

# end Metagene class


    
        

def metagene_count():
    '''Chain of command for metagene_count analysis.'''
    
    arguments = get_arguments()
    #print "Current arguments: \n{}".format(arguments)
    
    # confirm BAM file and extract chromosome sizes
    chromosomes = get_chromosome_sizes(arguments.alignment)
    #print "Current chromosomes: \n{}".format(chromosomes)
    
    # create chromosome conversion dictionary for feature (GFF/BED) to alignment (BAM)
    if arguments.chromosome_names != "None":
        chromosome_conversion_table = get_chromosome_conversions(arguments.chromosome_names, chromosomes.keys())
    #print "Current conversion table: \n{}".format(chromosome_conversion_table)
    
    # define the metagene array shape (left padding, start, internal, end, right padding)
    # metagene = padding ---- internal region ---- padding 
    metagene = Metagene(arguments.interval_size, arguments.padding, arguments.padding)
    
    print metagene.padding_left, metagene.interval, metagene.padding_right, metagene.length
    print metagene.get_interval_start()
    print metagene.get_interval_end()
       
        # for each feature
    for feature in get_features(arguments.feature):
        # create an empty metagene
        
        # define genomic positions
        feature_region = define_genomic(feature, arguments.padding)
        
        for read in get_reads(feature_region):
            # read = array of genomic positions to tally back to the feature_metagene
            feature_metagene = add_read(read, feature_metagene)
            
        # output feature_metagene          
   
    
    
    
def get_arguments():
    '''Collect and parse information from the user's command line arguments.'''
    
    date = datetime.datetime.now().strftime('%y%m%d-%H%M%S')
    
    parser = argparse.ArgumentParser(description=
    '''The first step of metagene_analysis, metagene_count.py compiles read abundance
over genomic features to create the input for metagene_windows.py. Please 
see README for full details and examples.''')

    parser.add_argument("-v","--version",
                        action = 'version',
                        version = "{} {}\tUpdated {}".format(PROGRAM, VERSION, UPDATED))
    parser.add_argument("-a","--alignment",
                        help = "Alignment file, must be an indexed BAM file",
                        metavar = 'BAM',
                        required = True)
    parser.add_argument("-f","--feature",
                        help = "Feature file, must be a BED or GFF file",
                        metavar = 'BED/GFF',
                        required = True)
    parser.add_argument("-o", "--output_prefix",
                        help = "Prefix for output files",
                        default = "{}.metagene.".format(date))
    
    parser.add_argument("--feature_count",
                        help = "Examine only the start, end or all of a feature",
                        choices = ['start','end','all'],
                        default = 'all')                    
    parser.add_argument("--count_method",
                        help = "Count the start, end or all of a read",
                        choices = ['start','end','all'],
                        default = 'all')
    
    parser.add_argument("--padding",
                        help = "Padding in nt to add around the feature, default = 1000",
                        default = 1000,
                        type = int,
                        metavar = 'NT')
    parser.add_argument("--interval_size",
                        help = "Normalized size of the feature, default = 1000",
                        default = 1000,
                        type = int,
                        metavar = 'NT')

    parser.add_argument("-c","--chromosome_names",
                        help = "Chromosome conversion file (feature_chromosome {tab} alignment_chromosome)",
                        metavar = 'TAB',
                        default = "None")
    
    arguments = parser.parse_args()
    
    # adjust internal_size if only the start or end of the feature will be counted
    if arguments.feature_count != 'all':
        arguments.interal_size = 1
    
                         
    return arguments

def get_chromosome_sizes(bamfile):
    '''Uses samtools view -H to get the header information and returns a 
    dictionary of the chromosome names and sizes.'''
    
    chromosome_sizes = {}

##Need to add error handling for subprocess!!    
    header = subprocess.check_output(['samtools', 'view', "-H", bamfile]).split("\n")
    
    for line in header:
        if line[0:3] == "@SQ":
            # parse out chromosome information from @SQ lines
            # format example (tab-delimited):
            # @SQ   SN:chromosome_name  LN:chromosome_size
            line_parts = line.split("\t")
            chromosome_sizes[line_parts[1][3:]] = int(line_parts[2][3:])
    
    return chromosome_sizes

def get_chromosome_conversions(tabfile, bam_chromosomes):
    '''Import TAB delimited conversion table for the chromosome names in the 
    feature file (column 0) and in the alignment file (column 1).  Return said
    table as a dictionary with the feature file chromosome names as keys and the 
    alignment file chromosome names as values.'''

##Need to add checking of conversion file!!
    
    conversion_table = {}
    
    if arguments.chromosome_names:
        infile = open(tabfile)
    
        rows = infile.read().strip().split("\n")
        for r in rows:
            if r[0] != "#": # don't process comments
                row_parts = r.split("\t")
                conversion_table[row_parts[0]] = row_parts[1]
    
        infile.close()
    else:
        for c in bam_chromosomes:
            conversion_table[c] = c
    
    return conversion_table






#def count_reads_around_features(arguments, chromosomes, chromosome_conversion):
    '''For each feature count the number of alignments (5' most base of each
    alignment only is counted) at each position {INTERVAL} nucleotides around
    the reference point-- start {-s} or end {-e} of the feature.
    
    Brief note about coordinate systems:
    The reference position is 0 with + and - {INTERVAL} positions on either side.
    However, the array storing the data runs from 0 to 2*{INTERVAL} with a length
    of 2*{INTERVAL} + 1.
    
    {INTERVAL} = 5
    Feature Index: -5 -4 -3 -2 -1  0  1  2  3  4  5    length = 11 
      Array Index:  0  1  2  3  4  5  6  7  8  9  10   length = 11
     Genome Index:  10 11 12 13 14 15 16 17 18 19 20   length = 11
      
    Therefore: array_index(reference point) = {INTERVAL}
    and the reference point is the ({INTERVAL} + 1)-ith value in the list
    
    More importantly, if the reference point is really 15 (1-based position) then
    genome_index(start) = genome_index(reference point) - ({INTERVAL} + 1) + 1
                        = 15 - (5+1) + 1 = 10
        (treating reference point as end and INTERVAL + 1 as length)
    genome_index(end)   = genome_index(start) + ({INTERVAL}*2 + 1) - 1
                        = 10 + (5*2 + 1) - 1 = 20
        (where the length = {INTERVAL} * 2 + 1 )'''
    

 

    
if __name__ == "__main__":
    metagene_count()    
   
    

