#!/usr/bin/python3

# Copyright 2014 Unvanquished Development
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, os, re, argparse


class TextureSet():
	colorRE = re.compile("^[0-9a-f]{6}$")

	def __init__(self, radToAddExponent = 1.0, heightNormalsMod = 1.0):
		self.header           = ""
		self.suffixes         = dict() # map type -> suffix
		self.lightColors      = dict() # color name -> RGB color triple
		self.lightIntensities = dict() # intensity name -> intensity
		self.mapping          = dict() # set name -> shader name -> key -> value
		self.radToAddExp      = radToAddExponent # used to convert radiosity RGB values into addition map colors
		self.heightNormalsMod = heightNormalsMod # used when generating normals from height maps

		# set default suffixes
		self.setSuffixes()

	def setHeader(self, text):
		"Sets a header text to be put at the top of the shader file."
		self.header = text

	def setSuffixes(self, diffuse = "_d", normal = "_n", height = "_h", specular = "_s", addition = "_a", preview = "_p"):
		"Sets the filename suffixes for the different texture map types."
		self.suffixes["diffuse"]  = diffuse
		self.suffixes["normal"]   = normal
		self.suffixes["height"]   = height
		self.suffixes["specular"] = specular
		self.suffixes["addition"] = addition
		self.suffixes["preview"]  = preview

	def addLightColor(self, name, color):
		"Adds a light color with a given name to be used for light emitting shaders."
		if not self.colorRE.match(color):
			print("Not a valid color: "+color+". Format is [0-9][a-f]{6}.", file = sys.stderr)
			return

		r = int(color[0:2], 16)
		g = int(color[2:4], 16)
		b = int(color[4:6], 16)

		if name in self.lightColors and (r, g, b) != self.lightColors[name]:
			print("Overwriting light color "+name+": "+"%02x%02x%02x" % self.lightColors[name]+" -> "+color, file = sys.stderr)

		self.lightColors[name] = (r, g, b)

	def addLightIntensity(self, intensity):
		"Adds a light intensity to be used for light emitting shaders."
		intensity = int(intensity)

		if intensity < 0:
			print("Ignoring negative light intensity.", file = sys.stderr)
			return

		if intensity >= 10000:
			name = str(int(intensity / 1000)) + "k"
		elif intensity >= 1000:
			if (intensity % 1000) < 50:
				name = str(int(intensity / 1000)) + "k"
			else:
				name = ("%.1f" % (intensity / 1000)) + "k"
		elif intensity == 0:
			name = "norad"
		else:
			name = str(intensity)

		if name in self.lightIntensities and intensity != self.lightIntensities[name]:
			print("Overwriting light intensity "+name+": "+str(self.lightIntensities[name])+" -> "+str(intensity), file = sys.stderr)

		self.lightIntensities[name] = intensity

	def __expandLightShaders(self, setname):
		"Replaces every non-virtual shader with an addition map with a set of virtual shaders for each light "
		"color/intensity combination as well as a not glowing (non-virtual) version."
		if len(self.lightColors) == 0 or len(self.lightIntensities) == 0:
			return

		newShaders = dict()
		delNames   = set()

		for shadername in self.mapping[setname]:
			shader = self.mapping[setname][shadername]

			if shader["virtual"]:
				continue

			if shader["addition"]:
				# mark original shader for deletion
				delNames.add(shadername)

				# add addition map shaders
				for colorName, (r, g, b) in self.lightColors.items():
					for intensityName, intensity in self.lightIntensities.items():
						newShader = dict()

						# copy metadata and maps from original
						for object in list(self.suffixes.keys()) + ["path"]:
							newShader[object] = shader[object]

						newShader["virtual"] = True
						newShader["keywords"] = dict()
						newShader["keywords"]["lightColor"] = dict()
						newShader["keywords"]["lightColor"]["r"] = r
						newShader["keywords"]["lightColor"]["g"] = g
						newShader["keywords"]["lightColor"]["b"] = b
						newShader["keywords"]["lightIntensity"] = intensity

						newShaders[shadername+"_"+colorName+"_"+intensityName] = newShader

				# remove addition map from original shader and append "_off" to its name
				shader["addition"] = None
				newShaders[shadername+"_off"] = shader

		# delete old reference to the original
		for shadername in delNames:
			self.mapping[setname].pop(shadername)

		# add new shaders (adds back original shader under new name, without addition map)
		self.mapping[setname].update(newShaders)

	def __guessKeywords(self, setname):
		"Guesses some keywords based on shader (meta)data."
		for shadername in self.mapping[setname]:
			shader = self.mapping[setname][shadername]

			# surfaceParm metalSteps
			for metal in ("metal", "steel", "iron", "wall"):
				if metal in shadername:
					shader["keywords"].setdefault("surfaceParm", set())
					shader["keywords"]["surfaceParm"].add("metalSteps")

	def generateSet(self, path, setname = None, cutextension = None):
		"Generates shader data for a given texture source folder."
		root = os.path.basename(os.path.abspath(path+os.path.sep+os.path.pardir))

		if not setname:
			if cutextension and len(cutextension) > 0:
				setname = root+"/"+os.path.basename(os.path.abspath(path)).rsplit(cutextension)[0]
			else:
				setname = root+"/"+os.path.basename(os.path.abspath(path))

		self.mapping.setdefault(setname, dict())

		maplist = [os.path.splitext(filename)[0] for filename in os.listdir(path)] # filenames without extension
		maps    = dict() # map type -> set of filenames without extentions

		# retrieve all maps by type
		for map_ in maplist:
			for (maptype, suffix) in self.suffixes.items():
				maps.setdefault(maptype, set())

				if map_.endswith(suffix):
					maps[maptype].add(map_)

		# add a shader for each diffuse map
		for diffusemap in maps["diffuse"]:
			shadername = diffusemap.rsplit(self.suffixes["diffuse"])[0]
			shader     = self.mapping[setname][shadername] = dict()

			shader["diffuse"]  = diffusemap
			shader["path"]     = root+"/"+os.path.basename(os.path.abspath(path))
			shader["virtual"]  = False
			shader["keywords"] = dict()

			# attempt to find a map of every known non-diffuse type
			# assumes that non-diffuse maps have the same name as the diffuse or form a start of it, prefers longer names
			for maptype, suffix in self.suffixes.items():
				basename = shadername

				while basename != "":
					mapname = basename+suffix

					if mapname in maps[maptype]:
						self.mapping[setname][shadername][maptype] = mapname
						break

					basename = basename[:-1]

				if basename == "": # no map of this type found
					self.mapping[setname][shadername][maptype] = None

		self.__expandLightShaders(setname)
		self.__guessKeywords(setname)

		print("Added set "+setname+" with "+str(len(self.mapping[setname]))+" shaders.", file = sys.stderr)

	def clearSets(self):
		"Forgets about all shader data that has been generated."
		self.mapping.clear()

	def __radToAdd(self, r, g = None, b = None):
		"Given light colors, return modified colors to be used in the blend phase of the addition map."
		if g and b:
			return (r**self.radToAddExp, g**self.radToAddExp, b**self.radToAddExp)
		else:
			return r**self.radToAddExp

	def getShader(self):
		"Assembles and returns the shader file content."
		content = ""

		for line in self.header.splitlines():
			if line.startswith("//"):
				content += line+"\n"
			else:
				content += "// "+line+"\n"

		for setname in self.mapping:
			content += "\n"+\
			           "// "+"-"*len(setname)+"\n"+\
			           "// "+setname+"\n"+\
			           "// "+"-"*len(setname)+"\n"

			names = list(self.mapping[setname].keys())
			names.sort()

			for shadername in names:
				# prepare content
				shader = self.mapping[setname][shadername]
				path   = shader["path"]+"/"

				if shader["preview"]:
					preview = shader["preview"]
				elif shader["diffuse"]:
					preview = shader["diffuse"]
				else:
					preview = None

				if "lightColor" in shader["keywords"]:
					r = shader["keywords"]["lightColor"]["r"] / 0xff
					g = shader["keywords"]["lightColor"]["g"] / 0xff
					b = shader["keywords"]["lightColor"]["b"] / 0xff
				else:
					r = g = b = None

				# assemble shader entry
				content += "\n"+setname+"/"+shadername+"\n{\n"

				if preview:
					content += "\tqer_EditorImage    "+path+preview+"\n\n"

				if "lightIntensity" in shader["keywords"] and shader["keywords"]["lightIntensity"] > 0 \
				   and "lightColor" in shader["keywords"]:
					content += "\tq3map_surfacelight "+"%d" % shader["keywords"]["lightIntensity"]+"\n"
					content += "\tq3map_lightRGB     "+"%.2f %.2f %.2f" % (r, g, b)+"\n\n"

				if shader["diffuse"]:
					content += "\tdiffuseMap         "+path+shader["diffuse"]+"\n"

				if shader["normal"]:
					if shader["height"] and self.heightNormalsMod > 0:
						content += "\tnormalMap          addnormals ( "+path+shader["normal"]+\
						           ", heightmap ( "+path+shader["height"]+", "+"%.2f" % self.heightNormalsMod+" ) )\n"
					else:
						content += "\tnormalMap          "+path+shader["normal"]+"\n"
				elif shader["height"] and self.heightNormalsMod > 0:
					content += "\tnormalMap          heightmap ( "+path+shader["height"]+", "+"%.2f" % self.heightNormalsMod+" )\n"

				if shader["specular"]:
					content += "\tspecularMap        "+path+shader["specular"]+"\n"

				if shader["addition"]:
					content += "\n\t{\n"+\
							   "\t\tmap   "+path+shader["addition"]+"\n"+\
							   "\t\tblend add\n"
					if "lightColor" in shader["keywords"]:
						content += \
							   "\t\tred   "+"%.2f" % self.__radToAdd(r)+"\n"+\
							   "\t\tgreen "+"%.2f" % self.__radToAdd(g)+"\n"+\
							   "\t\tblue  "+"%.2f" % self.__radToAdd(b)+"\n"
					content += \
							   "\t}\n"

				content += "}\n"

		return content


if __name__ == "__main__":
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	                                 description="Generates XreaL/Daemon shader files from directories of texture maps.")

	parser.add_argument("pathes", metavar="PATH", nargs="+",
	                    help="Path to a source directory that should be added to the set")

	parser.add_argument("-d", "--diff", metavar="SUF", default="_d",
	                    help="Suffix used by diffuse maps")

	parser.add_argument("-n", "--normal", metavar="SUF", default="_n",
	                    help="Suffix used by normal maps")

	parser.add_argument("-z", "--height", metavar="SUF", default="_h",
	                    help="Suffix used by height maps")

	parser.add_argument("-s", "--spec", metavar="SUF", default="_s",
	                    help="Suffix used by specular maps")

	parser.add_argument("-a", "--add", metavar="SUF", default="_a",
	                    help="Suffix used by addition/glow maps")

	parser.add_argument("-p", "--prev", metavar="SUF", default="_p",
	                    help="Suffix used by preview images")

	parser.add_argument("-c", "--colors", metavar="NAME:COLOR", nargs="+", default=["white:ffffff"],
	                    help="Add light colors with the given name, using a RGB hex triplet")

	parser.add_argument("-i", "--intensities", metavar="VALUE", type=int, nargs="+", default=[1000,2000,5000],
	                    help="Add light intensities")

	parser.add_argument("-e", "--exp", metavar="EXP", type=float, default=1.0,
	                    help="Exponent used to transform light color channels for use in the addition map blend phase")

	parser.add_argument("-m", "--heightnormals", metavar="MOD", type=float, default=1.0,
	                    help="Modifier used for generating normals from a heightmap")

	parser.add_argument("-o", "--out", metavar="DEST", type=argparse.FileType("w"),
	                    help="write shader to this file")

	parser.add_argument("-r", "--root",
	                    help="Force set root to this, by default the last two directories of the source pathes are used")

	parser.add_argument("-x", "--strip", metavar="SUF", default="_src",
	                    help="Strip suffix from source folder names when generating the set name")

	parser.add_argument("-t", "--header", metavar="FILE", type=argparse.FileType("r"),
	                    help="Use file content as a header, \"// \" will be prepended to each line")

	args = parser.parse_args()

	ts = TextureSet(radToAddExponent = args.exp, heightNormalsMod = args.heightnormals)

	ts.setSuffixes(diffuse = args.diff, normal = args.normal, height = args.height,
	               specular = args.spec, addition = args.add, preview = args.prev)

	if args.header:
		ts.setHeader(args.header.read())
		args.header.close()

	for (name, color) in [item.split(":") for item in args.colors]:
		ts.addLightColor(name, color)

	for intensity in args.intensities:
		ts.addLightIntensity(intensity)

	for path in args.pathes:
		ts.generateSet(path, setname = args.root, cutextension = args.strip)

	shader = ts.getShader()

	if args.out:
		args.out.write(shader)
		args.out.close()
	else:
		print(shader)
