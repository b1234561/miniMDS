import sys
import numpy as np
from tools import Tracker
import linear_algebra as la
import array_tools as at

class ChromParameters(object):
	"""Basic information on chromosome, inferred from input file"""
	def __init__(self, minPos, maxPos, res, name, size):
		self.minPos = minPos	#minimum genomic coordinate
		self.maxPos = maxPos	#maximum genomic coordinate
		self.res = res		#resolution (bp)
		self.name = name	#e.g. "chr22"
		self.size = size	#number of lines in file

	def getLength(self):
		"""Number of possible loci"""
		return (self.maxPos - self.minPos)/self.res + 1

	def getPointNum(self, genCoord):
		"""Converts genomic coordinate into point number"""
		if genCoord < self.minPos or genCoord > self.maxPos:
			return None
		else:
			#print genCoord
			#print self.minPos
			#print int((genCoord - self.minPos)/self.res)
			return int((genCoord - self.minPos)/self.res) 

	def reduceRes(self, resRatio):
		"""Creates low-res version of this chromosome"""
		lowRes = self.res * resRatio
		lowMinPos = (self.minPos/lowRes)*lowRes		#approximate at low resolution
		lowMaxPos = (self.maxPos/lowRes)*lowRes
		return ChromParameters(lowMinPos, lowMaxPos, lowRes, self.name, self.size)

class Structure(object):
	"""Intrachromosomal structure of points or substructures in 3-D space"""
	def __init__(self, points, structures, chrom, offset):
		self.points = points
		if len(structures) == 0 or structures is None:
			self.structures = []
		else:
			self.setstructures(structures)
		self.chrom = chrom	#chromosome parameters
		self.offset = offset	#indexing offset (for substructures only)

	def getCoords(self):
		return [point.pos for point in self.getPoints()]

	def setCoords(self, coords):
		for coord, point_num in zip(coords, self.getPointNums()):
			self.points[point_num - self.offset].pos = coord

	def getPointNums(self):
		return np.array([point.num for point in self.getPoints()])

	def getPoints(self):
		return self.points[np.where(self.points != 0)[0]]

	def getGenCoords(self):
		"""Non-null genomic coordinates of structure"""
		return [self.chrom.minPos + self.chrom.res * point_num for point_num in self.getPointNums()]

	def getIndex(self, genCoord):
		"""Converts genomic coordinate into index"""
		pointNum = self.chrom.getPointNum(genCoord)
		if pointNum is None:
			return None
		else:
			pointNum -= self.offset
			if pointNum >= 0 and pointNum < len(self.points):
				point = self.points[pointNum]
				if point == 0:
					return None
				else:
					return point.index
			else:
				return None
	
	def setstructures(self, structures):
		self.structures = structures
		self.points = np.zeros(max([max(structure.getPointNums()) for structure in structures]) + 1, dtype=np.object)	#reset
		for structure in self.structures:
			for point in structure.points:
				if point != 0:
					self.points[point.num] = point
		#self.indexPoints()

	def createSubstructure(self, points, offset):
		"""Creates substructure containing points"""
		substructure = Structure(points, [], self.chrom, offset)
		substructure.indexPoints()
		self.structures.append(substructure)

	def transform(self, r, t):
		"""Rotates by r; translates by t"""
		if r is None:	#default: no rotation
			r = np.mat(np.identity(3))
		if t is None:	#default: no translation
			t = np.mat(np.zeros(3)).T
		a = np.mat(self.getCoords())
		n = len(a)
		a_transformed = np.array(((r*a.T) + np.tile(t, (1, n))).T)
		for i, pointNum in enumerate(self.getPointNums()):
			self.points[pointNum - self.offset].pos = a_transformed[i]

	def write(self, outpath):
		with open(outpath, "w") as out:
			out.write(self.chrom.name + "\n")
			out.write(str(self.chrom.res) + "\n")
			out.write(str(self.chrom.minPos) + "\n")
			num = self.offset
			for point in self.points:
				if point == 0:
					out.write("\t".join((str(num), "nan", "nan", "nan")) + "\n")
				else:
					out.write("\t".join((str(num), str(point.pos[0]), str(point.pos[1]), str(point.pos[2]))) + "\n")
				num += 1
		out.close()

	def indexPoints(self):
		for i, point_num in enumerate(self.getPointNums()):
			self.points[point_num - self.offset].index = i

	def rescale(self):
		"""Rescale radius of gyration of structure to 1"""
		rg = la.radius_of_gyration(self)
		for i, point in enumerate(self.points):
			if point != 0:
				x, y, z = point.pos
				self.points[i].pos = (x/rg, y/rg, z/rg)

class Point(object):
	"""Point in 3-D space"""
	def __init__(self, pos, num, chrom, index):
		self.pos = pos	#3D coordinates
		self.num = num	#locus (not necessarily sequential)
		self.chrom = chrom	#chromosome parameters
		self.index = index	#sequential

def structureFromBed(path, chrom=None, start=None, end=None, offset=0, tads=None):
	"""Initializes structure from intrachromosomal BED file."""
	if chrom is None:
		chrom = chromFromBed(path)

	if start is None:
		start = chrom.minPos

	if end is None:
		end = chrom.maxPos

	structure = Structure([], [], chrom, offset)
	
	#get TAD for every locus
	#if tads is None:
#		tadNums = np.zeros(structure.chrom.getLength())
	#else:
	#	tadNums = []
	#	for i, tad in enumerate(tads):
	#		for j in range(tad[0], tad[1]):
	#			tadNums.append(i)

	#maxIndex = len(tadNums) - 1

	structure.points = np.zeros((end - start)/chrom.res + 1, dtype=object)	#true if locus should be added
	tracker = Tracker("Identifying loci", structure.chrom.size)

	#add loci
	with open(path) as listFile:
		for line in listFile:
			line = line.strip().split()
			pos1 = int(line[1])
			pos2 = int(line[4])
			if pos1 >= start and pos1 <= end and pos2 >= start and pos2 <= end:
				pointNum1 = structure.chrom.getPointNum(pos1)
				pointNum2 = structure.chrom.getPointNum(pos2)
				#tadNum1 = tadNums[min(pointNum1, maxIndex)]
				#tadNum2 = tadNums[min(pointNum2, maxIndex)]
				#if pointNum1 != pointNum2 and tadNum1 == tadNum2:		#must be in same TAD
				if pointNum1 != pointNum2:	#non-self-interacting
					structure.points[(pos1 - start)/chrom.res] = Point((0,0,0), pointNum1, structure.chrom, 0)
					structure.points[(pos2 - start)/chrom.res] = Point((0,0,0), pointNum2, structure.chrom, 0)
			tracker.increment()
		listFile.close()

	structure.indexPoints()
	
	return structure

def chromFromBed(path):
	"""Initialize ChromParams from intrachromosomal file in BED format"""
	minPos = sys.float_info.max
	maxPos = 0
	print "Scanning {}".format(path)
	with open(path) as infile:
		for i, line in enumerate(infile):
			line = line.strip().split()
			pos1 = int(line[1])
			pos2 = int(line[4])
			if pos1 < minPos:
				minPos = pos1
			elif pos1 > maxPos:
				maxPos = pos1
			if pos2 < minPos:
				minPos = pos2
			elif pos2 > maxPos:
				maxPos = pos2
			if i == 0:
				name = line[0]
				res = (int(line[2]) - pos1)	
		infile.close()
	minPos = int(np.floor(float(minPos)/res)) * res	#round
	maxPos = int(np.ceil(float(maxPos)/res)) * res
	return ChromParameters(minPos, maxPos, res, name, i)

def basicParamsFromBed(path):
	print "Scanning {}".format(path)
	with open(path) as infile:
		for i, line in enumerate(infile):
			if i == 0:
				line = line.strip().split()
				res = (int(line[2]) - int(line[1]))
		infile.close()
	return i, res

def matFromBed(path, structure=None):	
	"""Converts BED file to matrix. Only includes loci in structure."""
	if structure is None:
		structure = structureFromBed(path, None, None)

	pointNums = structure.getPointNums()

	numpoints = len(pointNums)
	mat = np.zeros((numpoints, numpoints))	

	maxPointNum = max(pointNums)
	assert maxPointNum - structure.offset < len(structure.points)

	with open(path) as infile:
		for line in infile:
			line = line.strip().split()
			loc1 = int(line[1])
			loc2 = int(line[4])
			index1 = structure.getIndex(loc1)
			index2 = structure.getIndex(loc2)
			if index1 is not None and index2 is not None:
				if index1 > index2:
					row = index1
					col = index2
				else:
					row = index2
					col = index1
				mat[row, col] += float(line[6])
		infile.close()

	at.makeSymmetric(mat)	
	rowsums = np.array([sum(row) for row in mat])
	if len(np.where(rowsums == 0)[0]) != 0:
		print np.array(structure.getGenCoords())[np.where(rowsums == 0)[0]]
		sys.exit(1)
	assert len(np.where(rowsums == 0)[0]) == 0

	return mat

def highToLow(highstructure, resRatio):
	"""Reduces resolution of structure"""
	lowChrom = highstructure.chrom.reduceRes(resRatio)

	low_n = len(highstructure.points)/resRatio + 1

	lowstructure = Structure(np.zeros(low_n, dtype=np.object), [], lowChrom, highstructure.offset/resRatio)

	allPointsToMerge = [[] for i in range(low_n)]
	
	for highPoint in highstructure.getPoints():
		pointsToMerge = []
		highNum = highPoint.num	- highstructure.offset
		lowNum = highNum/resRatio
		allPointsToMerge[lowNum].append(highPoint)

	index = lowstructure.offset
	for i, pointsToMerge in enumerate(allPointsToMerge):
		if len(pointsToMerge) > 0:
			meanCoord = np.mean(np.array([point.pos for point in pointsToMerge]), axis=0)
			lowstructure.points[i] = Point(meanCoord, i + lowstructure.offset, lowChrom, index)
			index += 1

	return lowstructure

def structure_from_file(path):
	hasMore = True
	with open(path) as infile:
		name = infile.readline().strip()
		res = int(infile.readline().strip())
		minPos = int(infile.readline().strip())
		chrom = ChromParameters(minPos, None, res, name, None)
		structure = Structure([], [], chrom, 0)
		index = 0
		while hasMore:
			line = infile.readline().strip().split()
			if len(line) == 0:
				hasMore = False
			else:
				num = int(line[0])
				if line[1] == "nan":
					point = 0
				else:
					x = float(line[1])
					y = float(line[2])
					z = float(line[3])
					point = Point((x,y,z), num, chrom, index)
					index += 1
				structure.points.append(point)
		infile.close()
	structure.points = np.array(structure.points)
	structure.chrom.maxPos = structure.chrom.minPos + structure.chrom.res*num	#max pos is last point num
	return structure

def make_compatible(structures):
	"""Enforce that points be shared by all structures"""
	gen_coord_dict = {}
	for i, structure in enumerate(structures):
		for gen_coord in structure.getGenCoords():
			if gen_coord in gen_coord_dict:
				gen_coord_dict[gen_coord] += 1
			else:
				gen_coord_dict[gen_coord] = 1
	
	consensus = []
	n = len(structures)
	for gen_coord in gen_coord_dict.keys():
		if gen_coord_dict[gen_coord] == n:
			consensus.append(gen_coord)

	consensus = np.sort(consensus)
	
	for structure in structures:
		new_chrom = ChromParameters(consensus[0], consensus[-1] + structure.chrom.res, structure.chrom.res, structure.chrom.name, structure.chrom.size)
		new_points = np.zeros(new_chrom.getLength(), dtype=object)
		for i, gen_coord in enumerate(consensus):
			old_point_num = structure.chrom.getPointNum(gen_coord)
			new_point_num = new_chrom.getPointNum(gen_coord)
			pos = structure.points[old_point_num].pos
			new_points[new_point_num] = Point(pos, new_point_num, new_chrom, i)
		structure.points = new_points
		structure.chrom = new_chrom

def normalized_dist_mat(path, structure):
	"""Standard processing for creating distance matrix"""
	contacts = matFromBed(path, structure)
	dists = at.contactToDist(contacts, 4)
	at.makeSymmetric(dists)
	return dists/np.mean(dists)	#normalize
