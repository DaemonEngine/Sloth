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

import sys, os, re, argparse, copy

from PIL import Image


class TextureSet():

	colorRE = re.compile("^[0-9a-f]{6}$")

	# mapping from surfaceparm values to words that trigger their use
	surfaceparms = \
	{
		"donotenter": ["lava", "slime"],
		"dust":       ["sand", "dust"],
		"flesh":      ["flesh", "meat", "organ"],
		"ladder":     ["ladder"],
		"lava":       ["lava"],
		"metalsteps": ["metal", "steel", "iron", "tread", "grate"],
		"slick":      ["ice"],
		"slime":      ["slime"],
		"water":      ["water"],
	}


	def __init__(self, radToAddExponent = 1.0, heightNormalsMod = 1.0, guessKeywords = False):
		self.suffixes         = dict() # map type -> suffix
		self.lightColors      = dict() # color name -> RGB color triple
		self.customLights     = dict() # intensity name -> intensity; for grayscale addition maps
		self.predefLights     = dict() # intensity name -> intensity; for non-grayscale addition maps
		self.mapping          = dict() # set name -> shader name -> key -> value

		# set defaults
		self.header           = ""     # header to be prepended to output
		self.guessKeywords    = False  # whether to try to guess additional keywords based on shader (meta)data
		self.radToAddExp      = 1.0    # exponent used to convert radiosity RGB values into addition map color modifiers
		self.heightNormalsMod = 1.0    # modifier used when generating normals from height maps
		self.alphaTest        = None   # whether to use an alphaFunc/alphaTest keyword or smooth blending (default)
		self.alphaShadows     = True   # whether to add the alphashadows surfaceparm keyword to relevant shaders
		self.setSuffixes()


	def setHeader(self, text):
		"Sets a header text to be put at the top of the shader file."
		self.header = text


	def setKeywordGuessing(self, value = True):
		"Whether to try to guess additional keywords based on shader (meta)data"
		self.guessKeywords = value


	def setRadToAddExponent(self, value):
		"Set the exponent used to convert radiosity RGB values into addition map color modifiers"
		self.radToAddExp = value


	def setHeightNormalsMod(self, value):
		"Set the modifier used when generating normals from height maps"
		self.heightNormalsMod = value


	def setAlphaTest(self, test):
		"Set the alpha test method used, blend smoothly if None."
		if type(test) == float and 0 <= test <= 1:
			self.alphaTest = test
		elif type(test) == str and test in ("GT0", "GE128", "LT128"):
			self.alphaTest = test
		elif test == None:
			self.alphaTest = None
		else:
			print("Alpha test must be either None, a valid string or a float between 0 and 1.", file = sys.stderr)


	def setAlphaShadows(self, value = True):
		"Whether to add the alphashadows surfaceparm keyword to relevant shaders"
		self.alphaShadows = value


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


	def __addLightIntensity(self, intensity, custom):
		"Adds a light intensity to be used for light emitting shaders."
		intensity = int(intensity)

		if intensity < 0:
			print("Ignoring negative light intensity.", file = sys.stderr)["meta"]
			return

		if intensity >= 10000:
			name = str(int(intensity / 1000)) + "k"
		elif intensity == 0:
			name = "norad"
		else:
			name = str(intensity)

		if custom:
			self.customLights[name] = intensity
		else:
			self.predefLights[name] = intensity


	def addCustomLightIntensity(self, intensity):
		self.__addLightIntensity(intensity, True)


	def addPredefLightIntensity(self, intensity):
		self.__addLightIntensity(intensity, False)


	def __analyzeMaps(self, shader):
		"Retrieves metadata from a shader's maps, such as whether there's an alpha channel on the diffuse map."
		# diffuse map
		img = Image.open(shader["abspath"]+os.path.sep+shader["diffuse"]+shader["diffuseExt"], "r")
		shader["meta"]["diffuseAlpha"] = ( img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info) )

		# addition map
		if shader["addition"]:
			img = Image.open(shader["abspath"]+os.path.sep+shader["addition"]+shader["additionExt"], "r")
			shader["meta"]["additionGrayscale"] = ( img.mode in ("L", "LA") )
		else:
			shader["meta"]["additionGrayscale"] = False


	def __expandLightShaders(self, setname):
		"Replaces every shader with an addition map with a set of shaders for each light color/intensity combination "
		"(only intensity for non-grayscale addition maps) as well as a not glowing version."
		newShaders = dict()
		delNames   = set()

		for shadername in self.mapping[setname]:
			shader = self.mapping[setname][shadername]

			if shader["addition"]:
				# mark original shader for deletion
				delNames.add(shadername)

				if shader["meta"]["additionGrayscale"]:
					# the addition map is grayscale, so
					for colorName, (r, g, b) in self.lightColors.items():
						for intensityName, intensity in self.customLights.items():
							newShader = copy.deepcopy(shader)

							newShader["meta"]["lightIntensity"]  = intensity
							newShader["meta"]["lightColor"]      = {"r": r, "g": g, "b": b}

							newShaders[shadername+"_"+colorName+"_"+intensityName] = newShader
				else:
					for intensityName, intensity in self.predefLights.items():
						newShader = copy.deepcopy(shader)

						newShader["meta"]["lightIntensity"]  = intensity

						newShaders[shadername+"_"+intensityName] = newShader

				# remove addition map from original shader and append "_off" to its name
				shader["addition"] = None
				newShaders[shadername+"_off"] = shader

		# delete old reference to the original
		for shadername in delNames:
			self.mapping[setname].pop(shadername)

		# add new shaders (adds back original shader under new name, without addition map)
		self.mapping[setname].update(newShaders)

	def __addKeywords(self, shader):
		"Adds keywords based on knowledge (and potentially assumptions) about the shader (meta)data."
		shader.setdefault("keywords", dict())

		# transparent diffuse map
		if shader["meta"]["diffuseAlpha"]:
			shader["keywords"]["cull"] = "none"

			if self.alphaTest:
				if type(self.alphaTest) == str:
					shader["keywords"]["alphaFunc"] = self.alphaTest
				else:
					shader["keywords"]["alphaTest"] = "%.2f" % self.alphaTest

			if self.alphaShadows:
				shader["keywords"].setdefault("surfaceparm", set())
				shader["keywords"]["surfaceparm"].add("alphashadows")

		if self.guessKeywords:
			# guess surfaceparms
			for surfaceparm, words in self.surfaceparms.items():
				for word in words:
					if word in shader["name"]:
						shader["keywords"].setdefault("surfaceparm", set())
						shader["keywords"]["surfaceparm"].add(surfaceparm)


	def generateSet(self, path, setname = None, cutextension = None):
		"Generates shader data for a given texture source folder."
		root = os.path.basename(os.path.abspath(path+os.path.sep+os.path.pardir))

		# generate the set name
		if not setname:
			if cutextension and len(cutextension) > 0:
				setname = root+"/"+os.path.basename(os.path.abspath(path)).rsplit(cutextension)[0]
			else:
				setname = root+"/"+os.path.basename(os.path.abspath(path))

		self.mapping.setdefault(setname, dict())

		filelist   = os.listdir(path)
		mapsbytype = dict() # map type -> set of filenames without extentions
		mapext     = dict() # map name (no extension) -> map filename (with extension)

		# retrieve all maps by type
		for filename in filelist:
			mapname, ext = os.path.splitext(filename)

			for (maptype, suffix) in self.suffixes.items():
				mapsbytype.setdefault(maptype, set())

				if mapname.endswith(suffix):
					mapext[mapname] = ext
					mapsbytype[maptype].add(mapname)

		# add a shader for each diffuse map
		for diffusename in mapsbytype["diffuse"]:
			shadername = diffusename.rsplit(self.suffixes["diffuse"])[0]
			shader     = self.mapping[setname][shadername] = dict()

			shader["name"]            = shadername
			shader["path"]            = root+"/"+os.path.basename(os.path.abspath(path))
			shader["abspath"]         = path

			shader["diffuse"]         = diffusename
			shader["diffuseExt"]      = mapext[diffusename]

			shader["meta"]            = dict()

			# attempt to find a map of every known non-diffuse type
			# assumes that non-diffuse map names form the start of diffuse map names, prefers longer names
			for maptype, suffix in self.suffixes.items():
				basename = shadername

				while basename != "":
					mapname = basename+suffix

					if mapname in mapsbytype[maptype]:
						shader[maptype]       = mapname
						shader[maptype+"Ext"] = mapext[mapname]
						break

					basename = basename[:-1]

				if basename == "": # no map of this type found
					self.mapping[setname][shadername][maptype] = None

			# retrieve more metadata from the maps
			self.__analyzeMaps(shader)

			# now that we have enough knowledge about the shader, add keywords
			self.__addKeywords(shader)

		numVariants = str(len(self.mapping[setname]))

		# expand relevant shaders into multiple light emitting ones
		self.__expandLightShaders(setname)

		numShaders = str(len(self.mapping[setname]))

		print(setname+": Added "+numShaders+" shaders for "+numVariants+" texture variants.", file = sys.stderr)


	def clearSets(self):
		"Forgets about all shader data that has been generated."
		self.mapping.clear()


	def __radToAdd(self, r, g = None, b = None):
		"Given light colors, return modified colors to be used in the blend phase of the addition map."
		if g and b:
			return (r**self.radToAddExp, g**self.radToAddExp, b**self.radToAddExp)
		else:
			return r**self.radToAddExp


	def getShader(self, setname = None, shadername = None):
		"Assembles and returns the shader file content."
		content = ""

		for line in self.header.splitlines():
			if line.startswith("//"):
				content += line+"\n"
			else:
				content += "// "+line+"\n"

		if setname:
			if setname in self.mapping:
				setnames = (setname, )
			else:
				print("Unknown set "+str(setname)+".", file = sys.stderr)
				return
		else:
			setnames = self.mapping.keys()

		for setname in setnames:
			if shadername:
				if shadername in self.mapping[setname]:
					names = (shadername, )
				else:
					continue
			else:
				content += "\n"+\
				           "// "+"-"*len(setname)+"\n"+\
				           "// "+setname+"\n"+\
				           "// "+"-"*len(setname)+"\n"

				names = sorted(self.mapping[setname].keys())

			for shadername in names:
				# prepare content
				shader = self.mapping[setname][shadername]
				path   = shader["path"]+"/"

				# decide on a preview image
				if shader["preview"]:
					preview = shader["preview"]
				elif shader["diffuse"]:
					preview = shader["diffuse"]
				else:
					preview = None

				# extract light color if available
				if "lightColor" in shader["meta"]:
					r = shader["meta"]["lightColor"]["r"] / 0xff
					g = shader["meta"]["lightColor"]["g"] / 0xff
					b = shader["meta"]["lightColor"]["b"] / 0xff

				content += "\n"+setname+"/"+shadername+"\n{\n"

				# preview image
				if preview:
					content += "\tqer_editorImage     "+path+preview+"\n\n"

				# keywords
				if "keywords" in shader and len(shader["keywords"]) > 0:
					for key, value in sorted(shader["keywords"].items()):
						if type(value) != str and hasattr(value, "__iter__"):
							for value in sorted(value):
								content += "\t"+key+" "*max(1, 20-len(key))+str(value)+"\n"
						else:
							content += "\t"+key+" "*max(1, 20-len(key))+str(value)+"\n"
					content += "\n"

				# surface light
				if "lightIntensity" in shader["meta"] and shader["meta"]["lightIntensity"] > 0:
					# intensity
					content += "\tq3map_surfacelight  "+"%d" % shader["meta"]["lightIntensity"]+"\n"

					# color
					if "lightColor" in shader["meta"]:
						content += "\tq3map_lightRGB      "+"%.2f %.2f %.2f" % (r, g, b)+"\n\n"
					elif shader["addition"]:
						content += "\tq3map_lightImage    "+shader["addition"]+"\n\n"
					elif shader["diffuse"]:
						content += "\tq3map_lightImage    "+shader["diffuse"]+"\n\n"
					else:
						content += "\tq3map_lightRGB      1.00 1.00 1.00\n\n"

				# diffuse map
				if shader["diffuse"]:
					if shader["meta"]["diffuseAlpha"] and not self.alphaTest:
						content += "\t{\n"+\
						           "\t\tmap   "+path+shader["diffuse"]+"\n"+\
						           "\t\tblend blend\n"+\
						           "\t}\n"
					else:
						content += "\tdiffuseMap          "+path+shader["diffuse"]+"\n"

				# normal & height map
				if shader["normal"]:
					if shader["height"] and self.heightNormalsMod > 0:
						content += "\tnormalMap           addnormals ( "+path+shader["normal"]+\
						           ", heightmap ( "+path+shader["height"]+", "+"%.2f" % self.heightNormalsMod+" ) )\n"
					else:
						content += "\tnormalMap           "+path+shader["normal"]+"\n"
				elif shader["height"] and self.heightNormalsMod > 0:
					content += "\tnormalMap           heightmap ( "+path+shader["height"]+", "+"%.2f" % self.heightNormalsMod+" )\n"

				# specular map
				if shader["specular"]:
					content += "\tspecularMap         "+path+shader["specular"]+"\n"

				# addition map
				if shader["addition"]:
					content += "\t{\n"+\
							   "\t\tmap   "+path+shader["addition"]+"\n"+\
							   "\t\tblend add\n"
					if "lightColor" in shader["meta"]:
						content += \
							   "\t\tred   "+"%.2f" % self.__radToAdd(r)+"\n"+\
							   "\t\tgreen "+"%.2f" % self.__radToAdd(g)+"\n"+\
							   "\t\tblue  "+"%.2f" % self.__radToAdd(b)+"\n"
					content += \
							   "\t}\n"

				content += "}\n"

		return content


if __name__ == "__main__":
	# parse command line options
	p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	                            description="Generates XreaL/Daemon shader files from directories of texture maps.")

	p.add_argument("pathes", metavar="PATH", nargs="+",
	               help="Path to a source directory that should be added to the set")

	p.add_argument("-g", "--guess", action="store_true",
	               help="Guess additional keywords based on shader (meta)data")

	p.add_argument("--height-normals", metavar="VALUE", type=float, default=1.0,
	               help="Modifier used for generating normals from a heightmap")

	# Texture map suffixes
	g = p.add_argument_group("Texture map suffixes")

	g.add_argument("-d", "--diff", metavar="SUF", default="_d",
	               help="Suffix used by diffuse maps")

	g.add_argument("-n", "--normal", metavar="SUF", default="_n",
	               help="Suffix used by normal maps")

	g.add_argument("-z", "--height", metavar="SUF", default="_h",
	               help="Suffix used by height maps")

	g.add_argument("-s", "--spec", metavar="SUF", default="_s",
	               help="Suffix used by specular maps")

	g.add_argument("-a", "--add", metavar="SUF", default="_a",
	               help="Suffix used by addition/glow maps")

	g.add_argument("-p", "--prev", metavar="SUF", default="_p",
	               help="Suffix used by preview images")

	# Light emitting shaders
	g = p.add_argument_group("Light emitting shaders")

	g.add_argument("-c", "--colors", metavar="NAME:COLOR", nargs="+", default=["white:ffffff"],
	               help="Add light colors with the given name, using a RGB hex triplet. "
	                    "They will only be used in combination with grayscale addition maps.")

	g.add_argument("-l", "--custom-lights", metavar="VALUE", type=int, nargs="+", default=[1000,2000,4000],
	               help="Add light intensities for light emitting shaders with custom colors (grayscale addition map)")

	g.add_argument("-i", "--predefined-lights", metavar="VALUE", type=int, nargs="+", default=[0,200],
	               help="Add light intensities for light emitting shaders with predefined colors (non-grayscale addition map)")

	g.add_argument("--color-blend-exp", metavar="VALUE", type=float, default=1.0,
	               help="Exponent applied to custom light color channels for use in the addition map blend phase")

	# Alpha blending
	g = p.add_argument_group("Alpha blending")
	gm = g.add_mutually_exclusive_group()

	gm.add_argument("--gt0", action="store_true",
	               help="Use alphaFunc GT0 instead of smooth alpha blending.")

	gm.add_argument("--ge128", action="store_true",
	               help="Use alphaFunc GE128 instead of smooth alpha blending.")

	gm.add_argument("--lt128", action="store_true",
	               help="Use alphaFunc LT128 instead of smooth alpha blending.")

	gm.add_argument("--alpha-test", metavar="VALUE", type=float,
	               help="Use alphaTest instead of smooth alpha blending.")

	g.add_argument("--no-alpha-shadows", action="store_true",
	               help="Don't add the alphashadows surfaceparm.")

	# Input & Output
	g = p.add_argument_group("Input & Output")
	gm = g.add_mutually_exclusive_group()

	gm.add_argument("-r", "--root",
	               help="Sets the namespace for the set (e.g. textures/setname). "
	                    "Can be used to merge source folders into a single set.")

	gm.add_argument("-x", "--strip", metavar="SUF", default="_src",
	               help="Strip suffix from source folder names when generating the set name")

	g.add_argument("-t", "--header", metavar="FILE", type=argparse.FileType("r"),
	               help="Use file content as a header, \"// \" will be prepended to each line")

	g.add_argument("-o", "--out", metavar="DEST", type=argparse.FileType("w"),
	               help="Write shader to this file")

	a = p.parse_args()

	# init generator
	ts = TextureSet()

	ts.setSuffixes(diffuse = a.diff, normal = a.normal, height = a.height,
	               specular = a.spec, addition = a.add, preview = a.prev)

	ts.setKeywordGuessing(a.guess)
	ts.setRadToAddExponent(a.color_blend_exp)
	ts.setHeightNormalsMod(a.height_normals)
	ts.setAlphaShadows(not a.no_alpha_shadows)

	if a.header:
		ts.setHeader(a.header.read())
		a.header.close()

	for (name, color) in [item.split(":") for item in a.colors]:
		ts.addLightColor(name, color)

	for intensity in a.custom_lights:
		ts.addCustomLightIntensity(intensity)

	for intensity in a.predefined_lights:
		ts.addPredefLightIntensity(intensity)

	if a.alpha_test:
		ts.setAlphaTest(a.alpha_test)
	elif a.gt0:
		ts.setAlphaTest("GT0")
	elif a.ge128:
		ts.setAlphaTest("GE128")
	elif a.lt128:
		ts.setAlphaTest("LT128")

	# generate
	for path in a.pathes:
		ts.generateSet(path, setname = a.root, cutextension = a.strip)

	# output
	shader = ts.getShader()

	if a.out:
		a.out.write(shader)
		a.out.close()
	else:
		print(shader)
