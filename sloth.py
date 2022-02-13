#!/usr/bin/python3

# Copyright 2014 Maximilian Stahlberg
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

import sys, os, re, argparse, copy, configparser

from PIL import Image

defaultSuffixes = {
	"diffuse":      "_d",
	"normal":       "_n",
	"normalheight": "_nh",
	"height":       "_h",
	"physical":     "_orm",
	"specular":     "_s",
	"addition":     "_a",
	"preview":      "_p",
}

class ShaderGenerator(dict):

	# valid color format
	colorRE = re.compile("^[0-9a-f]{6}$")
	binaryAlphaRE = re.compile(b"^[\x00\xff]*$")

	# mapping from surfaceparm values to words that trigger their use when keyword guessing is enabled
	surfaceParms = \
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

	defaultRenderer    = "xreal"
	supportedRenderers = ("quake3", defaultRenderer, "daemon")

	# extension for (per-shader) option files
	slothFileExt     = ".sloth"

	# basename of the per-set option file
	defaultSlothFile = "options"+slothFileExt

	# common file extensions for image source
	extBlackList = \
	[
		".ora",
		".psd",
		".xcf",
	]


	def __init__(self, verbosity = 0):
		self.verbosity        = verbosity
		self.sets             = dict() # set name -> shader name -> key -> value
		self.header           = ""     # header to be prepended to output
		self.suffixes         = dict() # map type -> suffix
		self.setSuffixes()

		# default options that can be overwritten on a per-directory/shader basis
		self["options"]                     = dict()
		self["options"]["lightColors"]      = dict() # color name -> RGB color triple
		self["options"]["customLights"]     = dict() # intensity name -> intensity; for grayscale addition maps
		self["options"]["predefLights"]     = dict() # intensity name -> intensity; for non-grayscale addition maps
		self["options"]["precalcColors"]    = False  # whether to precalculate fixed light colors
		self["options"]["guessKeywords"]    = False  # whether to try to guess additional keywords based on shader (meta)data
		self["options"]["radToAddExp"]      = 1.0    # exponent used to convert radiosity RGB values into addition map color modifiers
		self["options"]["heightNormalsMod"] = 1.0    # modifier used when generating normals from height maps
		self["options"]["editorOpacity"]    = 1.0    # in-editor opacity of transparent shaders
		self["options"]["alphaTest"]        = None   # whether to use an alphaFunc/alphaTest keyword or smooth blending (default)
		self["options"]["alphaShadows"]     = True   # whether to add the alphashadows surfaceparm keyword to relevant shaders
		self["options"]["renderer"]         = self.defaultRenderer


	#############
	# DEBUGGING #
	#############


	def verbose(self, text):
		if self.verbosity > 0:
			print(text, file = sys.stderr)


	def debug(self, text):
		if self.verbosity > 1:
			print(text, file = sys.stderr)


	def error(self, text):
		print("Error: "+text, file = sys.stderr)


	##################
	# GLOBAL OPTIONS #
	##################


	def setHeader(self, text):
		"Sets a header text to be put at the top of the shader file."
		self.header = text

	def setSuffixes(self, diffuse = defaultSuffixes["diffuse"], normal = defaultSuffixes["normal"], normalheight = defaultSuffixes["normalheight"], height = defaultSuffixes["height"], physical = defaultSuffixes["physical"], specular = defaultSuffixes["specular"], addition = defaultSuffixes["addition"], preview = defaultSuffixes["preview"]):
		"Sets the filename suffixes for the different texture map types."
		self.suffixes["diffuse"]      = diffuse
		self.suffixes["normal"]       = normal
		self.suffixes["normalheight"] = normalheight
		self.suffixes["height"]       = height
		self.suffixes["physical"]     = physical
		self.suffixes["specular"]     = specular
		self.suffixes["addition"]     = addition
		self.suffixes["preview"]      = preview


	def readConfig(self, fp):
		self.debug("Parsing global options file...")
		self.__parseSlothFile(self, fp)


	######################
	# PER-SHADER OPTIONS #
	######################


	def __setKeywordGuessing(self, value, shader = None):
		if not shader:
			shader = self

		shader["options"]["guessKeywords"] = value

	def setKeywordGuessing(self, value = True):
		"Whether to try to guess additional keywords based on shader (meta)data"
		self.__setKeywordGuessing(value)


	def __setRadToAddExponent(self, value, shader = None):
		if not shader:
			shader = self

		shader["options"]["radToAddExp"] = value

	def setRadToAddExponent(self, value):
		"Set the exponent used to convert radiosity RGB values into addition map color modifiers"
		self.__setRadToAddExponent(value)


	def __setHeightNormalsMod(self, value, shader = None):
		if not shader:
			shader = self

		shader["options"]["heightNormalsMod"] = value

	def setHeightNormalsMod(self, value):
		"Set the modifier used when generating normals from height maps"
		self.__setHeightNormalsMod(value)


	def __setEditorOpacity(self, value, shader = None):
		if not shader:
			shader = self

		if type(value) == float and 0 < value <= 1:
			shader["options"]["editorOpacity"] = value
		else:
			self.error("Editor transparency must be a float in ]0,1].")

	def setEditorOpacity(self, value):
			"Set the in-editor opacity of transparent shaders"
			self.__setEditorOpacity(value)


	def __setAlphaTest(self, test, shader = None):
		if not shader:
			shader = self

		if type(test) == float and 0 <= test <= 1:
			shader["options"]["alphaTest"] = test
		elif type(test) == str and test in ("GT0", "GE128", "LT128"):
			shader["options"]["alphaTest"] = test
		elif test == None:
			shader["options"]["alphaTest"] = None
		else:
			shader["options"]["alphaTest"] = None
			self.error("Alpha test must be either None, a valid string or a float in [0,1].")

	def setAlphaTest(self, test):
		"Set the alpha test method used, blend smoothly if None."
		self.__setAlphaTest(test)


	def __setAlphaShadows(self, value, shader = None):
		if not shader:
			shader = self

		shader["options"]["alphaShadows"] = value

	def setAlphaShadows(self, value = True):
		"Whether to add the alphashadows surfaceparm keyword to relevant shaders"
		self.__setAlphaShadows(value)


	def __addLightColor(self, name, color, shader = None):
		if not shader:
			shader = self

		if not self.colorRE.match(color):
			self.error("Not a valid color: "+color+". Format is [0-9][a-f]{6}.")
			return

		r = int(color[0:2], 16)
		g = int(color[2:4], 16)
		b = int(color[4:6], 16)

		if name in shader["options"]["lightColors"] and (r, g, b) != shader["options"]["lightColors"][name]:
			self.verbose("Overwriting light color "+name+": "+"%02x%02x%02x" % shader["options"]["lightColors"][name]+\
			             " -> "+color)

		shader["options"]["lightColors"][name] = (r, g, b)

	def addLightColor(self, name, color):
		"Adds a light color with a given name to be used for light emitting shaders."
		self.__addLightColor(name, color)


	def __addLightIntensity(self, intensity, custom, shader = None):
		if not shader:
			shader = self

		intensity = int(intensity)

		if intensity < 0:
			self.verbose("Ignoring negative light intensity.")
			return

		if intensity >= 10000:
			name = str(int(intensity / 1000)) + "k"
		elif intensity == 0:
			name = "norad"
		else:
			name = str(intensity)

		if custom:
			shader["options"]["customLights"][name] = intensity
		else:
			shader["options"]["predefLights"][name] = intensity

	def addCustomLightIntensity(self, intensity):
		"Adds a light intensity to be used for light emitting shaders with grayscale addition maps."
		self.__addLightIntensity(intensity, True)

	def addPredefLightIntensity(self, intensity):
		"Adds a light intensity to be used for light emitting shaders with non-grayscale addition maps."
		self.__addLightIntensity(intensity, False)


	def __setPrecalcColors(self, value, shader = None):
		if not shader:
			shader = self

		shader["options"]["precalcColors"] = value

	def setPrecalcColors(self, value = True):
		"Whether to precalculate light colors for light emitting shaders with predefined colors."
		self.__setPrecalcColors(value)


	def __setRenderer(self, renderer, shader = None):
		if not shader:
			shader = self

		if renderer in self.supportedRenderers:
			shader["options"]["renderer"] = renderer
		else:
			self.error("Renderer "+renderer+" not supported. Supported renderers are "+str(self.supportedRenderers)+".")

	def setRenderer(self, renderer):
		self.__setRenderer(renderer)


	#################
	# FUNCTIONALITY #
	#################


	def __copyOptions(self, source, target):
		"Copies initial shader options."
		target["options"] = copy.deepcopy(source["options"])


	def __parseSlothFile(self, shader, path):
		"Parses a per-directory/shader options file. path can also be a file pointer."
		config = configparser.ConfigParser(allow_no_value = True)

		# be case sensitive
		config.sectionsxform = lambda option: option
		config.optionxform   = lambda option: option

		# parse file
		try:
			if hasattr(path, "read"):
				config.read_string(path.read())
			else:
				with open(path, "r") as fp:
					config.read_file(fp)
		except IOError:
			self.error("Couldn't read "+path+".")
			return
		except (configparser.ParsingError, configparser.DuplicateOptionError) as error:
			self.error(str(error))
			return

		# parse options
		for section in config:
			options = config[section]

			if section == "options":
				for option in options:
					if option == "colors":
						shader["options"]["lightColors"].clear()

						for nameAndColor in options[option].split():
							try:
								name, color = nameAndColor.split(":")
							except ValueError:
								continue
							self.__addLightColor(name, color, shader)

					elif option == "addColors":
						for nameAndColor in options[option].split():
							try:
								name, color = nameAndColor.split(":")
							except ValueError:
								continue
							self.__addLightColor(name, color, shader)

					elif option == "predefLights":
						shader["options"][option].clear()

						for intensity in options["predefLights"].split():
							self.__addLightIntensity(int(intensity), False, shader)

					elif option == "precalcColors":
						self.__setPrecalcColors(options.getboolean(option), shader)

					elif option == "addPredefLights":
						for intensity in options[option].split():
							self.__addLightIntensity(int(intensity), False, shader)

					elif option == "customLights" in options:
						shader["options"][option].clear()

						for intensity in options[option].split():
							self.__addLightIntensity(int(intensity), True, shader)

					elif option == "addCustomLights":
						for intensity in options[option].split():
							self.__addLightIntensity(int(intensity), True, shader)

					elif option == "colorBlendExp":
						self.__setRadToAddExponent(options.getfloat(option), shader)

					elif option == "alphaFunc":
						self.__setAlphaTest(options[option], shader)

					elif option == "alphaTest":
						self.__setAlphaTest(options.getfloat(option), shader)

					elif option == "alphaShadows":
						self.__setAlphaShadows(options.getboolean(option), shader)

					elif option == "heightNormalsMod":
						self.__setHeightNormalsMod(options.getfloat(option), shader)

					elif option == "editorOpacity":
						self.__setEditorOpacity(options.getfloat(option), shader)

					elif option == "renderer":
						self.__setRenderer(options[option], shader)

					else:
						self.error("Invalid option "+option+" in section "+section+".")

			elif section in ("keywords", "addKeywords", "delKeywords"):
				for key, value in config[section].items():
					shader["options"].setdefault(section, dict())

					if value:
						shader["options"][section].setdefault(key, set())
						shader["options"][section][key].update(value.split())
					else:
						shader["options"][section][key] = None

			elif section != "DEFAULT":
				self.error("Invalid section "+section+".")


	def __analyzeMaps(self, shader):
		"Retrieves metadata from a shader's maps, such as whether there's an alpha channel on the diffuse map."
		# diffuse map
		img = Image.open(shader["abspath"]+os.path.sep+shader["diffuse"]+shader["ext"]["diffuse"], "r")

		# look for transparency
		if img.mode in ("RGBA", "LA"):
			if img.getextrema()[-1][0] == 255:
				self.verbose("Found completely white alpha channel in "+img.filename+".")
				shader["meta"]["diffuseAlpha"] = False
			else:
				shader["meta"]["diffuseAlpha"] = True
		elif img.mode == "p" and "transparency" in img.info:
			shader["meta"]["diffuseAlpha"] = True
		else:
			shader["meta"]["diffuseAlpha"] = False

		# check if transparency is binary
		shader["meta"]["diffuseAlphaBin"] = False
		if shader["meta"]["diffuseAlpha"]:
			alphaSequence = img.split()[-1].tobytes()
			if self.binaryAlphaRE.match(alphaSequence):
				shader["meta"]["diffuseAlphaBin"] = True

		# addition map
		if shader["addition"]:
			img = Image.open(shader["abspath"]+os.path.sep+shader["addition"]+shader["ext"]["addition"], "r")

			gray = ( img.mode in ("L", "LA") )

			img = img.convert("RGB")

			# check for RGB images with no actual non-gray color
			if not gray:
				colors = img.getcolors(maxcolors = 256)
				if colors:
					gray = True
					for _, rgb in colors:
						if not rgb[0] == rgb[1] == rgb[2]:
							gray = False
							break

			shader["meta"]["additionGrayscale"] = gray

			# get average color if needed
			if shader["options"]["precalcColors"]:
				value = channel = 0
				average = [0, 0, 0]
				for count in img.histogram():
					average[channel] += count * ( value / 0xff )
					value += 1
					if value > 0xff:
						average[channel] /= img.size[0] * img.size[1]
						value = 0
						channel += 1
						if channel == 3:
							break

				if gray:
					shader["meta"]["additionAverage"] = (average[0], average[0], average[0])
				else:
					shader["meta"]["additionAverage"] = tuple(average)


	def __addKeywords(self, shader):
		"Adds keywords based on knowledge (and potentially assumptions) about the shader (meta)data. Doesn't overwrite existing keywords."
		shader.setdefault("keywords", dict())
		keywords = shader["keywords"]
		options  = shader["options"]

		# handle transparent diffuse map
		if shader["meta"]["diffuseAlpha"]:
			keywords.setdefault("surfaceparm", set())
			keywords["surfaceparm"].add("trans")
			keywords["cull"] = {"none"}

			if options["alphaShadows"]:
				keywords["surfaceparm"].add("alphashadow")

		# attempt to guess additional keywords
		if options["guessKeywords"]:
			for surfaceParm, words in self.surfaceParms.items():
				for word in words:
					if word in shader["name"]:
						keywords.setdefault("surfaceparm", set())
						keywords["surfaceparm"].add(surfaceParm)

		# overlay keywords defined in options, overwrite on conflict
		if "keywords" in options:
			for key, value in options["keywords"].items():
				keywords[key] = value

		# overlay keywords defined in options, if possible extend on conflict
		if "addKeywords" in options:
			for key, value in options["addKeywords"].items():
				if not key in keywords:
					keywords[key] = value
				else:
					keywords[key].update(value)

		# delete specified keywords
		if "delKeywords" in options:
			for key, value in options["delKeywords"].items():
				if key in keywords:
					if value == None:
						keywords.pop(key)
					else:
						keywords[key].difference_update(value)

						if len(keywords[key]) == 0:
							keywords.pop(key)


	def __expandLightShaders(self, setname):
		"Replaces every shader with an addition map with a set of shaders for each light color/intensity combination "
		"(only intensity for non-grayscale addition maps) as well as a not glowing version."
		newShaders = dict()
		delNames   = set()

		for shadername in self.sets[setname]:
			shader = self.sets[setname][shadername]

			if shader["addition"]:
				# mark original shader for deletion
				delNames.add(shadername)

				if shader["meta"]["additionGrayscale"]:
					# the addition map is grayscale, use custom light colors
					for colorName, (r, g, b) in shader["options"]["lightColors"].items():
						for intensityName, intensity in shader["options"]["customLights"].items():
							newShader = copy.deepcopy(shader)

							newShader["meta"]["lightIntensity"]  = intensity
							newShader["meta"]["lightColor"]      = {"r": r, "g": g, "b": b}

							newShaders[shadername+"_"+colorName+"_"+intensityName] = newShader
				else:
					for intensityName, intensity in shader["options"]["predefLights"].items():
						newShader = copy.deepcopy(shader)

						newShader["meta"]["lightIntensity"]  = intensity

						newShaders[shadername+"_"+intensityName] = newShader

				# remove addition map from original shader and append "_off" to its name
				shader["addition"] = None
				newShaders[shadername+"_off"] = shader

		# delete old reference to the original
		for shadername in delNames:
			self.sets[setname].pop(shadername)

		# add new shaders (adds back original shader under new name, without addition map)
		self.sets[setname].update(newShaders)


	def generateSet(self, path, setname = None, cutextension = None):
		"Generates shader data for a given texture source folder."
		abspath    = os.path.abspath(path)
		root       = os.path.basename(os.path.abspath(path+os.path.sep+os.path.pardir))
		relpath    = root+"/"+os.path.basename(abspath)
		filelist   = os.listdir(abspath)
		mapsbytype = dict() # map type -> set of filenames without extentions
		mapext     = dict() # map name (no extension) -> map filename (with extension)
		slothfiles = set()  # sloth per-shader config file names (no extension)

		# retrieve all maps by type
		for filename in filelist:
			mapname, ext = os.path.splitext(filename)

			# check if this file extension is not among known unsupported ones
			if ext.lower() in self.extBlackList:
				self.verbose(filename + ": Unsupported format")
				continue	

			if ext == self.slothFileExt:
				slothfiles.add(mapname)
			else:
				for (maptype, suffix) in self.suffixes.items():
					mapsbytype.setdefault(maptype, set())

					if mapname.endswith(suffix):
						mapext[mapname] = ext
						mapsbytype[maptype].add(mapname)

		# add a new set or extend the current one
		if not setname:
			if cutextension and len(cutextension) > 0:
				setname = relpath.rsplit(cutextension, 1)[0]
			else:
				setname = relpath

		self.sets.setdefault(setname, dict())

		# parse per-directory options
		options = dict()

		self.__copyOptions(self, options)

		if self.defaultSlothFile in filelist:
			self.debug("Parsing per-directory options file for "+relpath+"...")
			self.__parseSlothFile(options, abspath+os.path.sep+self.defaultSlothFile)

		# add a shader for each diffuse map
		for diffusename in mapsbytype["diffuse"]:
			shadername = diffusename.rsplit(self.suffixes["diffuse"], 1)[0]

			# add a new shader
			shader = self.sets[setname][shadername] = dict()

			# copy default options
			self.__copyOptions(options, shader)

			# init shader data
			shader["name"]            = shadername
			shader["relpath"]         = relpath
			shader["abspath"]         = abspath
			shader["diffuse"]         = diffusename
			shader["ext"]             = {"diffuse": mapext[diffusename]}
			shader["meta"]            = dict()

			# attempt to find per-prefix/shader options file
			slothname  = ""
			for pos in range(len(shadername)):
				slothname += shadername[pos]
				if slothname in slothfiles:
					if slothname != shadername:
						self.debug("Parsing per-prefix options file for "+shadername+" ("+slothname+"*)...")
					else:
						self.debug("Parsing per-shader options file for "+shadername+"...")
					self.__parseSlothFile(shader, abspath+os.path.sep+slothname+self.slothFileExt)

			# attempt to find a map of every known non-diffuse type
			# assumes that non-diffuse map names form the start of diffuse map names
			for maptype, suffix in self.suffixes.items():
				basename = shadername

				while basename != "":
					mapname = basename+suffix

					if mapname in mapsbytype[maptype]:
						shader[maptype]        = mapname
						shader["ext"][maptype] = mapext[mapname]
						break

					basename = basename[:-1]

				if basename == "": # no map of this type found
					shader[maptype]        = None
					shader["ext"][maptype] = None

			# retrieve more metadata from the maps
			self.__analyzeMaps(shader)

			# now that we have enough knowledge about the shader, add keywords
			self.__addKeywords(shader)

		numVariants = str(len(self.sets[setname]))

		# expand relevant shaders into multiple light emitting ones
		self.__expandLightShaders(setname)

		numShaders = str(len(self.sets[setname]))

		self.verbose(setname+": Added "+numShaders+" shaders for "+numVariants+" texture variants.")


	def clearSets(self):
		"Forgets about all shader data that has been generated."
		self.sets.clear()

		self.verbose("Cleared all sets.")


	def __radToAdd(self, shader, r, g = None, b = None):
		"Given light colors, return modified colors to be used in the blend phase of the addition map."
		exp = shader["options"]["radToAddExp"]

		if g and b:
			return (r**exp, g**exp, b**exp)
		else:
			return r**exp


	def getShader(self, setname = None, shadername = None):
		"Assembles and returns the shader file content."
		content = ""

		for line in self.header.splitlines():
			if line.startswith("//"):
				content += line+"\n"
			else:
				content += "// "+line+"\n"

		if setname:
			if setname in self.sets:
				setnames = (setname, )
			else:
				self.error("Unknown set "+str(setname)+".")
				return
		else:
			setnames = self.sets.keys()

		for setname in setnames:
			if shadername:
				if shadername in self.sets[setname]:
					names = (shadername, )
				else:
					continue
			else:
				content += "\n"+\
				           "// "+"-"*len(setname)+"\n"+\
				           "// "+setname+"\n"+\
				           "// "+"-"*len(setname)+"\n"

				names = sorted(self.sets[setname].keys())

			# is a stage currently opened?
			in_stage = False

			for shadername in names:
				# prepare content
				shader = self.sets[setname][shadername]
				path   = shader["relpath"]+"/"
				stage_keys = ""

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
					content += "\tqer_editorImage     "+path+preview+"\n"

					# in-editor transparency
					if shader["meta"]["diffuseAlpha"] and shader["options"]["editorOpacity"] < 1:
						content += "\tqer_trans           "+"%.2f"%shader["options"]["editorOpacity"]+"\n"

					content += "\n"

				# keywords
				if "keywords" in shader and len(shader["keywords"]) > 0:
					for key, value in sorted(shader["keywords"].items()):
						if type(value) != str and hasattr(value, "__iter__"):
							for value in sorted(value):
								content += "\t"+key+" "*max(1, 20-len(key))+str(value)+"\n"
						elif value == None:
							content += "\t"+key+"\n"
						else:
							content += "\t"+key+" "*max(1, 20-len(key))+str(value)+"\n"

					content += "\n"

				# surface light
				if "lightIntensity" in shader["meta"] and shader["meta"]["lightIntensity"] > 0:
					# intensity
					content += "\tq3map_surfacelight  "+"%d" % shader["meta"]["lightIntensity"]+"\n"

					# color
					if "lightColor" in shader["meta"]:
						content += "\tq3map_lightRGB      "+"%.3f %.3f %.3f" % (r, g, b)+"\n\n"
					elif "additionAverage" in shader["meta"]:
						content += "\tq3map_lightRGB      "+"%.3f %.3f %.3f" % shader["meta"]["additionAverage"]+"\n\n"
					elif shader["addition"]:
						content += "\tq3map_lightImage    "+path+shader["addition"]+"\n\n"
					elif shader["diffuse"]:
						content += "\tq3map_lightImage    "+path+shader["diffuse"]+"\n\n"
					else:
						content += "\tq3map_lightRGB      1.000 1.000 1.000\n\n"

				# diffuse map
				if shader["diffuse"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tdiffuseMap      "+path+shader["diffuse"]+"\n"

					# with alpha channel
					if shader["meta"]["diffuseAlpha"]:
						if shader["options"]["renderer"] != "daemon":
							content += "\t{\n"+\
							           "\t\tmap       "+path+shader["diffuse"]+"\n"

							if shader["options"]["renderer"] != "quake3":
								content += "\t\tstage     diffuseMap\n"

						# alphatest forced
						if shader["options"]["alphaTest"]:
							if type(shader["options"]["alphaTest"]) == str:
								stage_keys += "\t\talphaFunc "+shader["options"]["alphaTest"]+"\n"
							else:
								stage_keys += "\t\talphaTest "+"%.2f"%shader["options"]["alphaTest"]+"\n"

						# alphatest implied by binary alpha values
						elif shader["meta"]["diffuseAlphaBin"]:
							stage_keys += "\t\talphaFunc GE128\n"

						# smooth blending
						else:
							stage_keys += "\t\tblend     blend\n"

						if shader["options"]["renderer"] != "daemon":
							content += stage_keys;
							content += "\t}\n"

					# without alpha channel
					elif shader["options"]["renderer"] == "xreal":
						content += "\tdiffuseMap          "+path+shader["diffuse"]+"\n"
					elif shader["options"]["renderer"] == "quake3":
						content += "\t{\n"+\
						           "\t\tmap   "+path+shader["diffuse"]+"\n"+\
						           "\t}\n"

				# normal & height map
				if shader["normal"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tnormalMap       "+path+shader["normal"]+"\n"

					elif shader["options"]["renderer"] == "xreal":
						if shader["height"] and shader["options"]["heightNormalsMod"] > 0:
							content += "\tnormalMap           addnormals ( "+path+shader["normal"]+\
									   ", heightmap ( "+path+shader["height"]+", "+\
									   "%.2f" % shader["options"]["heightNormalsMod"]+" ) )\n"
						else:
							content += "\tnormalMap           "+path+shader["normal"]+"\n"

				if not shader["normal"] and shader["height"] and shader["options"]["heightNormalsMod"] > 0 and shader["options"]["renderer"] == "xreal":
						content += "\tnormalMap           heightmap ( "+path+shader["height"]+", "+\
								   "%.2f" % shader["options"]["heightNormalsMod"]+" )\n"

				if shader["normalheight"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tnormalHeightMap       "+path+shader["normalheight"]+"\n"

				if shader["height"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\theightMap       "+path+shader["height"]+"\n"

				# physical map
				if shader["physical"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tphysicalMap     "+path+shader["physical"]+"\n"

				# specular map
				if shader["specular"]:
					if shader["options"]["renderer"] == "daemon":
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tspecularMap     "+path+shader["specular"]+"\n"

					elif shader["options"]["renderer"] == "xreal":
						content += "\tspecularMap         "+path+shader["specular"]+"\n"

				# addition map
				if shader["addition"]:
					has_light_color = "lightColor" in shader["meta"] and r + g + b < 3.0

					if shader["options"]["renderer"] == "daemon" and not has_light_color:
						if not in_stage:
							content += "\t{\n"
							in_stage = True

						content += "\t\tglowMap         "+path+shader["addition"]+"\n"

					elif shader["options"]["renderer"] == "xreal" and not has_light_color:
						content += "\tglowMap             "+path+shader["addition"]+"\n"

					elif shader["options"]["renderer"] == "quake3"\
					or (shader["options"]["renderer"] == "daemon" and has_light_color)\
					or (shader["options"]["renderer"] == "xreal" and has_light_color):
						if in_stage:
							content += stage_keys
							content += "\t}\n"
							in_stage = False

						stage_keys += "\t{\n"+\
						           "\t\tmap   "+path+shader["addition"]+"\n"+\
						           "\t\tblend add\n"
						in_stage = True

					if shader["options"]["renderer"] in ["daemon", "xreal", "quake3"] and has_light_color:
							stage_keys += \
							       "\t\tred   "+"%.3f" % self.__radToAdd(shader, r)+"\n"+\
							       "\t\tgreen "+"%.3f" % self.__radToAdd(shader, g)+"\n"+\
							       "\t\tblue  "+"%.3f" % self.__radToAdd(shader, b)+"\n"

					if shader["options"]["renderer"] in ["daemon", "xreal", "quake3"]:
						content += stage_keys;

					stage_keys = ""

				if in_stage:
					if shader["options"]["renderer"] in ["daemon"]:
						content += stage_keys
					content += "\t}\n"
					in_stage = False

				content += "}\n"

		return content


class ExampleConfig(argparse.Action):
	example = \
"""
# This is a per-directory/shader configuration file for Sloth.
#
# Sloth is a Python tool that generates XreaL/Daemon shader files from
# directories of texture maps. Sloth is free software and can be found at
# https://github.com/Unvanquished/Sloth
#
# The command line arguments used to invoke Sloth are global defaults for all
# shaders. They can be changed on a per-directory level by putting a file
# named "options.sloth" in the texture source folder. Other files ending in
# ".sloth" are read when their basename forms the beginning of the shader name
# in question. It is possible to have multiple sloth files overlay each other
# in a hierarchical order, for example one named "metal.sloth" that adds the
# "metalsteps" surface parameter to every shader starting with "metal" and one
# named "metaleatingbacteria.sloth" that removes it and adds the "flesh"
# surfaceparm instead for shaders starting with the respective string.
#
# An example configuration can be generated with the -e/--example-config
# argument. Be aware that sloth files are case-sensitive.

# The "options" section contains mostly keywords that correspond to command
# line options. For a detailed description of their function invoke Sloth with
# the -h/--help option.
[options]
# Corresponds to --colors
#colors = red:ff0000 green:00ff00

# Like "colors" but doesn't clear previous values
#addColors = blue:0000ff white:ffffff

# Corresponds to --custom-lights
#customLights = 1000 2000

# Like "customLights" but doesn't clear previous values
#addCustomLights = 3000 4000

# Corresponds to --predef-lights
#predefLights = 100 200

# Corresponds to --precalc-colors
#precalcColors = on

# Like "predefLights" but doesn't clear previous values
#addPredefLights = 300 400

# Corresponds to --color-blend-exp
#colorBlendExp = 1.2

# Correspond to --gt0, --ge128 and --lt128, respectively
#alphaFunc = GT0
#alphaFunc = GE128
#alphaFunc = LT128

# Corresponds to --alpha-test
#alphaTest = 0.5

# Value "off" corresponds to --no-alpha-shadows
#alphaShadows = off

# Corresponds to --height-normals
#heightNormalsMod = 0.8

# One of "quake3", "xreal" (default), "daemon"
#renderer = daemon

# Corresponds to --editor-opacity
#editorOpacity = 0.5

# The "keywords" section sets custom key/value pairs. This overwrites
# everything between qer_* keywords and the texture map definitions.
# Multiple values will be expanded to multiple lines with the same keyword.
# The value can also be omitted, so that only the keyword gets added.
[keywords]
#alphashadows
#cull = none
#surfaceparm = metalsteps trans

# Like "keywords", but previous key/value pairs will be preserved.
# Useful for adding surface parameters to groups of shaders that represent a
# certain material
[addKeywords]
#surfaceparm = metalsteps

# The opposite of "addKeywords": These key/value pairs or keywords will be
# removed. If only a key is given, all key/value pairs matching the keyword as
# well as keywords without a value will be removed. If a value is given, only
# the exact key/value pairs are matched.
[delKeywords]
#surfaceparm = metalsteps
"""

	def __call__(self, parser, namespace, values, option_string=None):
		print(self.example.strip("\n"))
		exit()


if __name__ == "__main__":
	# parse command line options
	p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	                            description="Generates XreaL/Daemon shader files from directories of texture maps.")

	# Misc arguments
	p.add_argument("-e", "--example-config", action=ExampleConfig, nargs=0,
	               help="Prints an example per-directory/shader configuration file")

	p.add_argument("-v", "--verbose", action="count",
	               help="Print debug information to stderr. Supply twice for more verbosity.")

	p.add_argument("-f", "--config", metavar="FILE", type=argparse.FileType("r"),
	               help="Read global configuration (takes precedence over command line arguments)")

	p.add_argument("pathes", metavar="PATH", nargs="+",
	               help="Path to a source directory that should be added to the set")

	p.add_argument("-g", "--guess", action="store_true",
	               help="Guess additional keywords based on shader (meta)data")

	p.add_argument("--height-normals", metavar="VALUE", type=float, default=1.0,
	               help="Modifier used for generating normals from a heightmap")

	p.add_argument("--editor-opacity", metavar="VALUE", type=float, default=0.5,
	               help="In-editor opacity of transparent shaders")

	# Renderers
	g = p.add_argument_group("Renderers")

	gm = g.add_mutually_exclusive_group()

	gm.add_argument("--daemon", action="store_true",
	                help="Use renderer features of the Daemon engine. Makes the shaders incompatible with XreaL and Quake3.")

	gm.add_argument("--xreal", action="store_true",
	               help="Use renderer features of the XreaL engine. Makes the shaders incompatible with Quake3. This is the default.")

	gm.add_argument("--quake3", action="store_true",
	                help="Use renderer features of the vanilla Quake3 engine only.")

	# Texture map suffixes
	g = p.add_argument_group("Texture map suffixes")

	g.add_argument("--diffuse",         metavar="SUF", default=defaultSuffixes["diffuse"],      help="Suffix used by diffuse maps")
	g.add_argument("--normal",          metavar="SUF", default=defaultSuffixes["normal"],       help="Suffix used by normal maps")
	g.add_argument("--normalheight",    metavar="SUF", default=defaultSuffixes["normalheight"], help="Suffix used by normal+height maps")
	g.add_argument("--height",          metavar="SUF", default=defaultSuffixes["height"],       help="Suffix used by height maps")
	g.add_argument("--physical",        metavar="SUF", default=defaultSuffixes["physical"],     help="Suffix used by physical maps")
	g.add_argument("--specular",        metavar="SUF", default=defaultSuffixes["specular"],     help="Suffix used by specular maps")
	g.add_argument("--addition",        metavar="SUF", default=defaultSuffixes["addition"],     help="Suffix used by addition/glow maps")
	g.add_argument("--preview",         metavar="SUF", default=defaultSuffixes["preview"],      help="Suffix used by preview images")

	# Light emitting shaders
	g = p.add_argument_group("Light emitting shaders")

	g.add_argument("--colors", metavar="NAME:COLOR", nargs="+", default=["white:ffffff"],
	               help="Add light colors with the given name, using a RGB hex triplet. "
	                    "They will only be used in combination with grayscale addition maps.")

	g.add_argument("--custom-lights", metavar="VALUE", type=int, nargs="+", default=[1000,2000,4000],
	               help="Add light intensities for light emitting shaders with custom colors (grayscale addition map)")

	g.add_argument("--predef-lights", metavar="VALUE", type=int, nargs="+", default=[0,200],
	               help="Add light intensities for light emitting shaders with predefined colors (non-grayscale addition map)")

	g.add_argument("--precalc-colors", action="store_true",
                   help="Precalculate light colors for light emitting shaders with predefined colors.")

	g.add_argument("--color-blend-exp", metavar="VALUE", type=float, default=1.0,
	               help="Exponent applied to custom light color channels for use in the addition map blend phase")

	# Alpha blending
	g = p.add_argument_group("Alpha blending")
	gm = g.add_mutually_exclusive_group()

	gm.add_argument("--gt0", action="store_true",
	               help="Always use alphaFunc GT0 instead of smooth alpha blending.")

	gm.add_argument("--ge128", action="store_true",
	               help="Always use alphaFunc GE128 instead of smooth alpha blending.")

	gm.add_argument("--lt128", action="store_true",
	               help="Always use alphaFunc LT128 instead of smooth alpha blending.")

	gm.add_argument("--alpha-test", metavar="VALUE", type=float,
	               help="Always use alphaTest instead of smooth alpha blending.")

	g.add_argument("--no-alpha-shadows", action="store_true",
	               help="Don't add the alphashadows surfaceparm.")

	# Input & Output
	g = p.add_argument_group("Input & Output")
	gm = g.add_mutually_exclusive_group()

	gm.add_argument("-r", "--root",
	               help="Sets the namespace for the set (e.g. textures/setname). "
	                    "Can be used to merge source folders into a single set.")

	gm.add_argument("--strip", metavar="SUF", default="_src",
	               help="Strip suffix from source folder names when generating the set name")

	g.add_argument("--header", metavar="FILE", type=argparse.FileType("r"),
	               help="Use file content as a header, \"// \" will be prepended to each line")

	g.add_argument("-o", "--out", metavar="DEST", type=argparse.FileType("w"),
	               help="Write shader to this file")

	a = p.parse_args()

	# init generator
	if a.verbose:
		verbosity = a.verbose
	else:
		verbosity = 0

	sg = ShaderGenerator(verbosity)

	sg.setSuffixes(diffuse = a.diffuse, normal = a.normal, height = a.height,
	               specular = a.specular, addition = a.addition, preview = a.preview)

	if a.quake3:
		sg.setRenderer("quake3")
	elif a.xreal:
		sg.setRenderer("xreal")
	else:
		sg.setRenderer("daemon")

	sg.setKeywordGuessing(a.guess)
	sg.setRadToAddExponent(a.color_blend_exp)
	sg.setHeightNormalsMod(a.height_normals)
	sg.setAlphaShadows(not a.no_alpha_shadows)
	sg.setEditorOpacity(a.editor_opacity)
	sg.setPrecalcColors(a.precalc_colors)

	if a.header:
		sg.setHeader(a.header.read())
		a.header.close()

	for (name, color) in [item.split(":") for item in a.colors]:
		sg.addLightColor(name, color)

	for intensity in a.custom_lights:
		sg.addCustomLightIntensity(intensity)

	for intensity in a.predef_lights:
		sg.addPredefLightIntensity(intensity)

	if a.alpha_test:
		sg.setAlphaTest(a.alpha_test)
	elif a.gt0:
		sg.setAlphaTest("GT0")
	elif a.ge128:
		sg.setAlphaTest("GE128")
	elif a.lt128:
		sg.setAlphaTest("LT128")

	# read global configuration
	if a.config:
		sg.readConfig(a.config)

	# generate
	for path in a.pathes:
		sg.generateSet(path, setname = a.root, cutextension = a.strip)

	# output
	shader = sg.getShader()

	if a.out:
		a.out.write(shader)
		a.out.close()
	else:
		print(shader)
