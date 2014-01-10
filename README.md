Sloth
=====

Generates XreaL/Daemon shader files from directories of texture maps

Features
--------

Sloth is a Python console application that generates XreaL/Deamon (e.g.
Unvanquished) compatible shader files given a texture map source directory.

* Supports diffuse, normal, height, specular and addition maps as well as preview images
* Generates light emitting shaders from addition maps given a number of named colors and intensities
* Autodetects texture variants (shaders sharing non-diffuse maps)
* Can generate multiple sets at once or merge different source folders into one set
* Can prepend a header to the resulting shader file
* It's not slow, it's named Sloth because it's made for lazy mappers!

Dependencies
------------

* Python >= 3.0
* Python Pillow

Installation
------------

Just run sloth.py with Python.

Usage
-----

	usage: sloth.py [-h] [-m MOD] [-g] [-d SUF] [-n SUF] [-z SUF] [-s SUF]
	                [-a SUF] [-p SUF] [-c NAME:COLOR [NAME:COLOR ...]]
	                [-l VALUE [VALUE ...]] [-i VALUE [VALUE ...]] [-e VALUE]
	                [-r ROOT] [-x SUF] [-t FILE] [-o DEST]
	                PATH [PATH ...]
	
	Generates XreaL/Daemon shader files from directories of texture maps.
	
	positional arguments:
	  PATH                  Path to a source directory that should be added to the
	                        set
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -m MOD, --height-normals MOD
	                        Modifier used for generating normals from a heightmap
	                        (default: 1.0)
	  -g, --guess           Guess additional keywords based on shader (meta)data
	                        (default: False)
	
	Texture map suffixes:
	  -d SUF, --diff SUF    Suffix used by diffuse maps (default: _d)
	  -n SUF, --normal SUF  Suffix used by normal maps (default: _n)
	  -z SUF, --height SUF  Suffix used by height maps (default: _h)
	  -s SUF, --spec SUF    Suffix used by specular maps (default: _s)
	  -a SUF, --add SUF     Suffix used by addition/glow maps (default: _a)
	  -p SUF, --prev SUF    Suffix used by preview images (default: _p)
	
	Light emitting shaders:
	  -c NAME:COLOR [NAME:COLOR ...], --colors NAME:COLOR [NAME:COLOR ...]
	                        Add light colors with the given name, using a RGB hex
	                        triplet. They will only be used in combination with
	                        grayscale addition maps. (default: ['white:ffffff'])
	  -l VALUE [VALUE ...], --custom-lights VALUE [VALUE ...]
	                        Add light intensities for light emitting shaders with
	                        custom colors (grayscale addition map) (default:
	                        [1000, 2000, 5000])
	  -i VALUE [VALUE ...], --predefined-lights VALUE [VALUE ...]
	                        Add light intensities for light emitting shaders with
	                        predefined colors (non-grayscale addition map)
	                        (default: [0, 200])
	  -e VALUE, --color-blend-exp VALUE
	                        Exponent used to transform custom light color channels
	                        for use in the addition map blend phase (default: 1.0)
	
	Input & Output:
	  -r ROOT, --root ROOT  Sets the namespace for the set (e.g.
	                        textures/setname). Can be used to merge source folders
	                        into a single set. (default: None)
	  -x SUF, --strip SUF   Strip suffix from source folder names when generating
	                        the set name (default: _src)
	  -t FILE, --header FILE
	                        Use file content as a header, "// " will be prepended
	                        to each line (default: None)
	  -o DEST, --out DEST   Write shader to this file (default: None)

To make use of the texture variant autodetection, add different suffixes to
your diffuse map names (e.g. wall1\_d.tga, wall2\_d.tga, wall\_n.tga, wall\_s.tga).

License
-------

> Copyright 2014 Unvanquished Development
>
> This program is free software: you can redistribute it and/or modify
> it under the terms of the GNU General Public License as published by
> the Free Software Foundation, either version 3 of the License, or
> at your option) any later version.
>
> This program is distributed in the hope that it will be useful,
> but WITHOUT ANY WARRANTY; without even the implied warranty of
> MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
> GNU General Public License for more details.
>
> You should have received a copy of the GNU General Public License
> along with this program.  If not, see <http://www.gnu.org/licenses/>.
