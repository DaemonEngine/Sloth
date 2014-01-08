Sloth
=====

Generates XreaL/Daemon shader files from directories of texture maps

Features
--------

Sloth is a Python console application that generates XreaL/Deamon (e.g.
Unvanquished) compatible shader files given a texture map source directory.

* Allows configuration of map type file suffixes
* Can generate multiple sets at once or merge different source folders into one set
* Generates light emitting shaders from addition/glow maps given a number of named colors and intensities
* Can prepend a header to the resulting shader file
* Can transform light colors to addition map blend phase colors given an exponent applied to each channel
* Autodetects texture variants (shaders sharing non-diffuse maps)
* It's not slow, it's named Sloth because it's made for lazy mappers!

Dependencies
------------

* Python >= 3.0

Installation
------------

Just run sloth.py with Python.

Usage
-----

	usage: sloth.py [-h] [-d SUF] [-n SUF] [-s SUF] [-a SUF] [-p SUF]
	                [-c NAME:COLOR [NAME:COLOR ...]] [-i VALUE [VALUE ...]]
	                [-e EXP] [-o DEST] [-r ROOT] [-x SUF] [-t FILE]
	                PATH [PATH ...]
	
	Generates XreaL/Daemon shader files from directories of texture maps.
	
	positional arguments:
	  PATH                  Path to a source directory that should be added to the
	                        set
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -d SUF, --diff SUF    Suffix used by diffuse maps (default: _d)
	  -n SUF, --normal SUF  Suffix used by normal maps (default: _n)
	  -s SUF, --spec SUF    Suffix used by specular maps (default: _s)
	  -a SUF, --add SUF     Suffix used by addition/glow maps (default: _a)
	  -p SUF, --prev SUF    Suffix used by preview images (default: _p)
	  -c NAME:COLOR [NAME:COLOR ...], --colors NAME:COLOR [NAME:COLOR ...]
	                        Add light colors with the given name, using a RGB hex
	                        triplet (default: ['white:ffffff'])
	  -i VALUE [VALUE ...], --intensities VALUE [VALUE ...]
	                        Add light intensities (default: [0, 1000, 2000, 5000])
	  -e EXP, --exp EXP     Exponent used to transform light color channels for
	                        use in the addition map blend phase (default: 1.0)
	  -o DEST, --out DEST   write shader to this file (default: None)
	  -r ROOT, --root ROOT  Force set root to this, by default the last two
	                        directories of the source pathes are used (default:
	                        None)
	  -x SUF, --strip SUF   Strip suffix from source folder names when generating
	                        the set name (default: _src)
	  -t FILE, --header FILE
	                        Use file content as a header, "// " will be prepended
	                        to each line (default: None)

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
