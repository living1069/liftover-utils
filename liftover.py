"""
Usage:
  liftover.py <file> <release1> <release2> (bcf|vcf|gff|bed|refflat)
  liftover.py <file> <release1> <release2> <chrom_col> <start_pos_column> [<end_pos_column>] [options]

Options:
  -h --help     Show this screen.
  --delim=<delim>  File Delimiter; Default is a tab [default: TAB].

"""


# Liftover 
import sys, os
import tempfile
import gzip
import subprocess
from subprocess import *
from pprint import pprint as pp
from docopt import docopt

if __name__ == '__main__':
    # Fetch Arguments
    arguments = docopt(__doc__, version='Liftover Utilities 1.0')

# Pipeing function
def pipe_out(line):
    try:
        sys.stdout.write(line + "\n")
    except IOError:
        try:
            sys.stdout.close()
        except IOError:
            pass
        try:
            sys.stderr.close()
        except IOError:
            pass


def unzip_gz(filename):
    # For some files, unzip first as temp files.
    if (filename.endswith(".gz")):
        tmp_gz = tempfile.NamedTemporaryFile().name
        os.system("gunzip -c %s > %s" % (filename, tmp_gz))
        return tmp_gz
    else:
        return filename

# Check to see if CHROM DIFFs are available.
if os.path.isfile("remap_gff_between_releases.pl") == False:
    os.system("wget ftp://ftp.sanger.ac.uk/pub2/wormbase/software/Remap-between-versions/remap.tar.bz2 && gunzip -f remap.tar.bz2 && tar -xf remap.tar")
    os.system("mv Remap-for-other-groups/remap_gff_between_releases.pl remap_gff_between_releases.pl")
    os.system("mv Remap-for-other-groups/CHROMOSOME_DIFFERENCES/ CHROMOSOME_DIFFERENCES/")
    os.system("rm -f -r Remap-for-other-groups/")
    os.remove("remap.tar")


# Define some necessary variables.
release1, release2 = arguments["<release1>"], arguments["<release2>"]
gff_temp = tempfile.NamedTemporaryFile().name
gff_liftover = tempfile.NamedTemporaryFile().name
gff = file(gff_temp, 'w+')
if arguments["--delim"] == "TAB":
   arguments["--delim"] = "\t" 

#
# BCF / VCF
#
vcf = any([arguments["vcf"],arguments["bcf"]])
if vcf:
    chrom_col, start_col, end_col = 0, 1, 1
    delim = "\t"
    bcf_pos = tempfile.NamedTemporaryFile().name
    os.system("bcftools query -f '%%CHROM\t%%POS\n' %s > %s" % (sys.argv[1], bcf_pos))
    variant_positions = file(bcf_pos,'r')
elif arguments["gff"]:
    chrom_col, start_col, end_col = 0, 3, 4
    delim = "\t"
    arguments["<file>"] = unzip_gz(arguments["<file>"])
    variant_positions = file(arguments["<file>"],'r')
elif arguments["bed"]:
    chrom_col, start_col, end_col = 0, 1, 2
    delim = "\t"
    arguments["<file>"] = unzip_gz(arguments["<file>"])
    variant_positions = file(arguments["<file>"],'r')
elif arguments["refflat"]:
    refflat_temp = tempfile.NamedTemporaryFile().name
    # Process refflat file for liftover.
    with open(refflat_temp, "w+") as temp_ref:
        with open(arguments["<file>"]) as f:
            for n, l in enumerate(f):
                l = l.strip().split("\t")
                geneName = l[0]
                name = l[1]
                chrom = l[2]
                strand = l[3]
                txStart = l[4]
                txEnd = l[5]
                cdsStart = l[6]
                cdsEnd = l[7]
                exonCount = l[8]
                exonStarts = l[9].strip(",").split(",")
                exonEnds = l[10].strip(",").split(",")
                # Write a line for starts and ends
                temp_ref.write("{chrom}\t{txStart}\t{txEnd}\ttx\t{n}\n".format(**locals()))
                temp_ref.write("{chrom}\t{cdsStart}\t{cdsEnd}\tcds\t{n}\n".format(**locals()))
                exons = zip(exonStarts, exonEnds)
                for exonStart, exonEnd in exons:
                    temp_ref.write("{chrom}\t{exonStart}\t{exonEnd}\texon\t{n}\n".format(**locals()))
    delim = "\t"
    chrom_col, start_col, end_col  = 0, 1, 2
    #arguments["<file>"] = "temp.txt"
    variant_positions = file(refflat_temp,"r")
else:
    variant_positions = file(arguments["<file>"],'r')
    chrom_col, start_col = int(arguments["<chrom_col>"])-1, int(arguments["<start_pos_column>"])-1
    if arguments["<end_pos_column>"] is not None:
        end_col = int(arguments["<end_pos_column>"])-1
    else:
        end_col = int(arguments["<start_pos_column>"])-1
for l in variant_positions.xreadlines():
    l = l.replace("\n","").split(arguments["--delim"])
    if l[0].startswith("#") == False and len(l) >= 2:
        if l[0].lower() == "chrm":
            l[0] = "CHROMOSOME_MtDNA"
        # Write out the coordinates in temporary gff file.
        line_out = "%s\t.\t.\t%s\t%s\t.\t+\t.\t%s\t%s\t%s\n" % tuple([l[chrom_col], l[start_col], l[end_col]]*2)
        gff.write(line_out)

gff.close()


# Generate Liftover Coordinates
perl_script = "remap_gff_between_releases.pl"

release1 = release1.upper().replace("WS","")
release2 = release2.upper().replace("WS","")

if int(release2) < int(release1):
    raise Exception("Can only lift forward")

remap_command = "perl %s -gff=%s -release1=%s -release2=%s -output=%s" % (perl_script, gff_temp, release1, release2, gff_liftover)
subprocess.check_output(remap_command, shell=True)

gff_liftover = file(gff_liftover, 'r')

# Replace original coordinates
if vcf == True:
    proc = Popen("bcftools view %s" % arguments["<file>"], stdout=PIPE, stdin=PIPE, shell=True)
    for line in proc.stdout:
        print line
        line = line.replace("\n", "")
        if line.startswith("#") == True:
            pipe_out(line)
        else:
            # Add checks
            l = gff_liftover.readline().replace("\n","").split("\t")
            pos_orig = l[9]
            pos_new = l[3]
            line = line.split("\t")
            if line[1] != pos_orig:
                raise Exception("Coordinates Off")
            else:
                line[1] = pos_new
                pipe_out('\t'.join(line))
elif arguments["refflat"]:
    orig_file = file(arguments["<file>"], 'r')

    # Organize liftover positions
    org_pos = dict()
    new_pos = [x.split("\t") for x in open(refflat_temp, "r").read().strip().split("\n")]
    for i in new_pos:
        i[4] = int(i[4])
        if i[4] not in org_pos:
            org_pos[i[4]] = {}
        if i[3] == "tx":
            org_pos[i[4]]["tx"] = [i[1], i[2]]
        elif i[3] == "cds":
            org_pos[i[4]]["cds"] = [i[1], i[2]]
        elif i[3] == "exon":
            if "exon" not in org_pos[i[4]]:
                org_pos[i[4]]["exon"] = {}
                org_pos[i[4]]["exon"]["start"] = []
                org_pos[i[4]]["exon"]["end"] = []
            else:
                org_pos[i[4]]["exon"]["start"].extend([i[1]])
                org_pos[i[4]]["exon"]["end"].extend([i[2]])
    for n,l in enumerate(orig_file.xreadlines()):
            l = l.strip().split("\t")
            l[4] = org_pos[n]["tx"][0]
            l[5] = org_pos[n]["tx"][1]
            l[6] = org_pos[n]["cds"][1]
            l[7] = org_pos[n]["cds"][1]
            l[9] = ','.join(org_pos[n]["exon"]["start"])
            l[10] = ','.join(org_pos[n]["exon"]["end"])
            pipe_out('\t'.join(l))

else:
    orig_file = file(arguments["<file>"], 'r')
    for line in orig_file.xreadlines():
        line = line.replace("\n", "")
        if line.startswith("#") == True or line.startswith(">") == True:
            pipe_out(line)
        else:
            # Add checks
            l = gff_liftover.readline().split(arguments["--delim"])
            # Ensure this isn't some strange line...
            if len(l) >= 2:
                pos_orig = l[9]
                pos_new = l[3]
                pos_end_orig = l[10]
                pos_end_new = l[4]
                line = line.split("\t")
                print line
                if line[start_col] != pos_orig:
                    raise Exception("Coordinates Off")
                else:
                    line[start_col] = pos_new
                    line[end_col] = pos_end_new
                    pipe_out('\t'.join(line))
            else:
                pipe_out(line)









