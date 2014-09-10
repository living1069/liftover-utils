from peewee import * 

db = SqliteDatabase('chrom_diff.db')
db.connect()

# Define Classes
class BaseModel(Model):
    class Meta:
        database = db

class liftover(BaseModel):
    build = IntegerField()
    organism = CharField()
    chromosome = CharField()
    mismatch_start1 = IntegerField()
    mismatch_end1 = IntegerField()
    length1 = IntegerField()
    mismatch_start2 = IntegerField()
    mismatch_end2 = IntegerField()
    length2 = IntegerField()
    flipped = BooleanField()



# Remap Coordinates
def shift_pos(pos, mis_start1, mis_end1, length1, mis_start2, mis_end2, length2, shift_direction):
	# Shift Right if beyond end position
	if ((length1 > 0 and pos >= mis_end1) or
		(length1 == 0 and pos > mis_end1)):
		return pos + ((length2 - length1) * shift_direction)
	else:
		return pos

def remap_coords(organism, release1, release2, chromosome, start, end = None):

	# Determine direction
	if (release1 > release2):
		# Reverse liftover
		liftover_direction = liftover.build.desc()
		release1, release2 = release2, release1
		shift_direction = -1
	else:
		# Forward liftover
		liftover_direction = liftover.build.asc()
		shift_direction = 1

	# Read Mapping Data
	mapping_coords = liftover.select().where(liftover.build >= release1, liftover.build <= release2, liftover.chromosome==chromosome).order_by(liftover_direction).dicts()
	for i in mapping_coords:
		# If start or end lie beyond change region, apply shift.
		start = shift_pos(start, i["mismatch_start1"], i["mismatch_end1"], i["length1"], i["mismatch_start2"], i["mismatch_end2"],  i["length2"], shift_direction)
		end = shift_pos(end, i["mismatch_start1"], i["mismatch_end1"], i["length1"], i["mismatch_start2"], i["mismatch_end2"],  i["length2"], shift_direction)

		#print start, end, start - end, i["build"]
	return start, end

def debug():
	import csv
	test_gff = csv.DictReader(open("test/test_coords.txt"), delimiter="\t")
	for k,v in enumerate(test_gff):
		if k < 10:
			#print k,v[0], v[1], v[5]

			# Map Forward
			start, end = remap_coords("C. elegans", 220, 235, v["old_chrom"], int(v["old_start"]), int(v["old_end"]))
			if (int(v["new_start"]) != start):
				print "Remap Start Fail - forward %s - %s" % (v["new_start"], start)
			
			# Map Backwards
			start, end = remap_coords("C. elegans", 235, 220, v["old_chrom"], int(v["new_start"]), int(v["new_end"]))
			if (int(v["old_start"]) != start):
				print "Remap Start Fail - reverse %s - %s" % (v["new_start"], start)

			#print "End remap failed: %s - %s" % (v["old_end"], end)

			


debug()

remap_coords("C. elegans", 220, 235,"CHROMOSOME_IV", 9403845, 9403855)
remap_coords("C. elegans", 220, 235,"CHROMOSOME_IV", 9403845, 9403855)