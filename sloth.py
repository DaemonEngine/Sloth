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


	def __init__(self, radToAddExponent = 1.0, heightNormalsMod = 1.0, guessKeywords = False):
		self.header           = ""
		self.suffixes         = dict() # map type -> suffix
		self.lightColors      = dict() # color name -> RGB color triple
		self.customLights     = dict() # intensity name -> intensity
		self.predefLights     = dict() # intensity name -> intensity
		self.mapping          = dict() # set name -> shader name -> key -> value
		self.radToAddExp      = radToAddExponent # used to convert radiosity RGB values into addition map colors
		self.heightNormalsMod = heightNormalsMod # used when generating normals from height maps
		self.guessKeywords    = guessKeywords    # try to guess keywords based on shader (meta)data

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


	def __guessKeywords(self, setname):
		"Guesses some keywords based on shader (meta)data."
		for shadername in self.mapping[setname]:
			shader = self.mapping[setname][shadername]

			shader.setdefault("keywords", dict())

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

			# guess surfaceparms
			for surfaceparm, words in surfaceparms.items():
				for word in words:
					if word in shadername:
						shader["keywords"].setdefault("surfaceparm", set())
						shader["keywords"]["surfaceparm"].add(surfaceparm)

			# remove the keywords dict if it's empty
			if len(shader["keywords"]) == 0:
				shader.pop("keywords")


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

			shader["diffuse"]         = diffusename
			shader["diffuseExt"]      = mapext[diffusename]

			shader["path"]            = root+"/"+os.path.basename(os.path.abspath(path))
			shader["abspath"]         = path

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

		# expand relevant shaders into multiple light emitting ones
		self.__expandLightShaders(setname)

		# attempt to guess keywords based on clues
		if self.guessKeywords:
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
				if "keywords" in shader:
					for key, value in shader["keywords"].items():
						if hasattr(value, "__iter__"):
							for value in value:
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
					content += "\n\t{\n"+\
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
	p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	                            description="Generates XreaL/Daemon shader files from directories of texture maps.")

	p.add_argument("pathes", metavar="PATH", nargs="+",
	               help="Path to a source directory that should be added to the set")

	p.add_argument("-m", "--height-normals", metavar="MOD", type=float, default=1.0,
	               help="Modifier used for generating normals from a heightmap")

	p.add_argument("-g", "--guess", action="store_true",
	               help="Guess additional keywords based on shader (meta)data")

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

	g.add_argument("-l", "--custom-lights", metavar="VALUE", type=int, nargs="+", default=[1000,2000,5000],
	               help="Add light intensities for light emitting shaders with custom colors (grayscale addition map)")

	g.add_argument("-i", "--predefined-lights", metavar="VALUE", type=int, nargs="+", default=[0,200],
	               help="Add light intensities for light emitting shaders with predefined colors (non-grayscale addition map)")

	g.add_argument("-e", "--color-blend-exp", metavar="VALUE", type=float, default=1.0,
	               help="Exponent used to transform custom light color channels for use in the addition map blend phase")

	# Input & Output
	g = p.add_argument_group("Input & Output")

	g.add_argument("-r", "--root",
	               help="Sets the namespace for the set (e.g. textures/setname). "
	                    "Can be used to merge source folders into a single set.")

	g.add_argument("-x", "--strip", metavar="SUF", default="_src",
	               help="Strip suffix from source folder names when generating the set name")

	g.add_argument("-t", "--header", metavar="FILE", type=argparse.FileType("r"),
	               help="Use file content as a header, \"// \" will be prepended to each line")

	g.add_argument("-o", "--out", metavar="DEST", type=argparse.FileType("w"),
	               help="Write shader to this file")

	a = p.parse_args()

	ts = TextureSet(radToAddExponent = a.color_blend_exp, heightNormalsMod = a.height_normals,
	                guessKeywords = a.guess)

	ts.setSuffixes(diffuse = a.diff, normal = a.normal, height = a.height,
	               specular = a.spec, addition = a.add, preview = a.prev)

	if a.header:
		ts.setHeader(a.header.read())
		a.header.close()

	for (name, color) in [item.split(":") for item in a.colors]:
		ts.addLightColor(name, color)

	for intensity in a.custom_lights:
		ts.addCustomLightIntensity(intensity)

	for intensity in a.predefined_lights:
		ts.addPredefLightIntensity(intensity)

	for path in a.pathes:
		ts.generateSet(path, setname = a.root, cutextension = a.strip)

	shader = ts.getShader()

	if a.out:
		a.out.write(shader)
		a.out.close()
	else:
		print(shader)
