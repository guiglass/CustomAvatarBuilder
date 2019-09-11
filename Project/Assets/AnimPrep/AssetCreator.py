#!/usr/bin/python3

__author__ = "Grant Olsen"
__copyright__ = "Copyright 2019, Animation Prep Studios"
__credits__ = [""]
__license__ = "GPL"
__version__ = "2.0.1"
__title__ = 'AnimPrep Asset Project Creator'
import os, sys, json, time, pickle

from shutil import copyfile

import traceback

import subprocess

from PIL import ImageEnhance, ImageTk, Image, ImageDraw

from distutils.dir_util import copy_tree

from tkinter import Tk, StringVar, Button, Frame, OptionMenu, Scrollbar, Text, Entry, Label, BOTH, LEFT, RIGHT, TOP, BOTTOM, END, SUNKEN, DISABLED, NORMAL, INSERT, YES, NO, Y, X, N, W, S, E
#import tkFileDialog
from tkinter import filedialog as tkFileDialog

import shutil

from tempfile import mkdtemp

import base64
"""
To build using pyinstaller, first delete the build and dist directories, then cd to the  use this commend:

for Python 2.7:
pyinstaller -w -F --icon=logo.ico AssetCreator.py

for Python 3.4:
/path/to/python3 -m PyInstaller -w -F --icon=logo.ico AssetCreator.py

eg.
c:\Python34\python.exe -m PyInstaller -w -F --icon=logo.ico AssetCreator.py

"""

#This is the raw text for the blenderscript.py script that is run from within the user's .blend file from subprocess launches the scene file. Dont forget this file becomes a temporary file and is saved into a temp directory.
blenderscript_avatar = r"""
#This file is pushed into a headless subprocess of the user's .blend via command line args, this automatically export .fbx file and material infos json

# !/usr/bin/env python2.7
import bpy, json, os, re
from mathutils import *

bpy.ops.file.unpack_all(method='WRITE_LOCAL')

def applyTransform(obj):
	mat = obj.getMatrix()
	me = obj.getData(mesh=True)
	for v in me.verts:
		v.co = v.co*mat
	mat.identity()

def FindRootRecursive(obj):
	if obj.parent is not None:
		obj = FindRootRecursive(obj.parent)
	return obj

armObjs = [o for o in bpy.data.objects if o.type == 'ARMATURE']

# remove all scene objects that are not connected to a valid armature modifier (eg lamps, cameras, rogue cubes)
armature = None

for obj in bpy.data.objects:
	if obj.type == 'ARMATURE':
		armature = obj
		continue

	connectedToArmature = False
	if hasattr(obj, 'modifiers'): #first check if it has an armature modifier on the mesh object
		for modifier in obj.modifiers:
			if modifier.type == 'ARMATURE':
				if modifier.object is not None:
					connectedToArmature = True
					break

	if not connectedToArmature: #last chance to check if it is instead parented to a bone of an armature
		root = FindRootRecursive(obj)
		if (root in armObjs):
			connectedToArmature = True

	if not connectedToArmature:
		bpy.data.scenes[0].objects.unlink(obj)
		bpy.data.objects.remove(obj)

# build the material json file:
material_data = []

for m in bpy.data.materials:
	if (m.users == 0 ):
		continue

	used_texture_slots = []
	for i, slot in enumerate(m.texture_slots):

		if slot is not None and hasattr(slot.texture, 'image'):
			filename = slot.texture.image.filepath #.encode('ascii','ignore').decode()  # the filename and extension of the image, strip dir info
			filename = os.path.basename(filename.replace('//', ''))  # Extract file name from path

			texture_data = {
				"filename": filename,
				"material": m.name,
				"slot": i,

				# "use_map_color_diffuse" : texture_data.image.use_map_color_diffuse,
				# "diffuse_color_factor" : texture_data.image.diffuse_color_factor,

				"use_map_color_diffuse": slot.use_map_color_diffuse,

				"use_map_specular": slot.use_map_specular,
				"specular_factor": slot.specular_factor,

				"use_map_normal": slot.use_map_normal,
				"normal_factor": slot.normal_factor,

				"use_map_emit": slot.use_map_emit,
				"emit_factor": slot.emit_factor,

				"use_map_alpha": slot.use_map_alpha,
				"alpha_factor": slot.alpha_factor,
			}

			used_texture_slots.append(texture_data)

	mat = {
		"key": m.name,
		"texture": None,
		"alpha": m.alpha,
		"use_transparency": m.use_transparency,

		"diffuse_intensity": m.diffuse_intensity,
		"specular_intensity": m.specular_intensity,
		"specular_hardness": m.specular_hardness,
		"specular_color": {'r': m.specular_color.r, 'g': m.specular_color.g, 'b': m.specular_color.b},

		"texture_slots": used_texture_slots,
	}
	material_data.append(mat)

	if (used_texture_slots.__len__() is not 0):
		mat['texture'] = used_texture_slots[0]['filename'] #default to using the filename of the first slot
		mat['alpha'] = used_texture_slots[0]['alpha_factor']
		#key = used_texture_slots[0]['filename'] #default to using the filename of the first slot

		for slot in used_texture_slots: #scan through all slots for to find the slot used for the color diffuse texture
			if slot["use_map_color_diffuse"]:
				mat['texture'] = slot['filename']
				mat['alpha'] = slot['alpha_factor']

# create an empty dictionary to store all found bones and drivers in
boneDict = {}

if armature is not None:

	#apply the aramture scale as 1,1,1 then fix Rellusion pose offsets caused by applying the new scale
	armature.select = True
	bpy.context.scene.objects.active = armature

	for bone in armature.pose.bones:
		#all rellusion characters have twist bones, they look strange after applying scale (unless they are completely reset)
		if "Twist" in bone.name:
			bone.location = Vector( (0,0,0) )
			bone.rotation_quaternion = Quaternion( (0, 0, 0), 0 )
			bone.scale = Vector( (1, 1, 1) )
			bone.keyframe_insert(data_path="location")#also make sure to update the keyframes
			bone.keyframe_insert(data_path="rotation_quaternion")
			bone.keyframe_insert(data_path="scale")

	hipBoneIndex = 1 #CC_Base_Hip

	#First save the hip's world position
	pose_bone = armature.pose.bones[hipBoneIndex]
	obj = pose_bone.id_data
	matrix_final = obj.matrix_world * pose_bone.matrix

	#apply the armature scale
	bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
	bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
	bpy.ops.object.mode_set(mode='POSE', toggle=False)

	#store the delta hip position, it will be used to offset objects parented to any bones
	t1 = matrix_final.translation
	t2 = (obj.matrix_world * pose_bone.matrix).translation
	deltaLocation = t1 - t2

	#move the hip back to where it belongs
	matrix_reverse = obj.matrix_world * matrix_final
	pose_bone.matrix = matrix_reverse
	pose_bone.scale = Vector((1,1,1))
	pose_bone.keyframe_insert(data_path="location")

	#now search for any objects that are a child of a bone, but does not have any weightpainting (armature modifiers)
	for obj in bpy.data.objects:
		if obj.type == 'ARMATURE':
			armature = obj
			continue
		skip = False
		if hasattr(obj, 'modifiers'): #first check if it has an armature modifier on the mesh object
			for modifier in obj.modifiers:
				if modifier.type == 'ARMATURE':
					if modifier.object is not None:
						skip = True
						break
		if skip:
			continue #the object has weightpainting applied, do not move this as it could cause weird mesh offsets to occur

		root = FindRootRecursive(obj) # check if it is instead parented to a bone of an armature
		if (root in armObjs):
			obj.location -= deltaLocation #apply the hip delta positon, fix issue where the eyes shoot off upward after the action has been applied later on, apply all rotations to this object now...

	#Create the rest pose used for the bvh export reference pose
	for action in bpy.data.actions: #Delete all actions
		bpy.data.actions.remove(action)

	armature.animation_data_create()

	armature.animation_data.action = bpy.data.actions.new(name="APose")

	for bone in armature.data.bones:
		bonename = bone.name

		for i in range(3):
			data_path = 'pose.bones["%s"].location'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, armature.pose.bones[bonename].location[i]#0.0, 0.0

		for i in range(3):
			data_path = 'pose.bones["%s"].scale'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, armature.pose.bones[bonename].scale[i]# 0.0, 1.0

		for i in range(4):
			data_path = 'pose.bones["%s"].rotation_quaternion'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, armature.pose.bones[bonename].rotation_quaternion[i]# 0.0, 1.0 if i is 0 else 0.0

	previousAction = armature.animation_data.action


	armature.animation_data.action = bpy.data.actions.new(name="RestPose")

	for bone in armature.data.bones:
		bonename = bone.name

		for i in range(3):
			data_path = 'pose.bones["%s"].location'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, 0.0

		for i in range(3):
			data_path = 'pose.bones["%s"].scale'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, 1.0


		for i in range(4):
			data_path = 'pose.bones["%s"].rotation_quaternion'%(bonename)

			fcu_z = armature.animation_data.action.fcurves.new(data_path=data_path, index=i)
			fcu_z.keyframe_points.add(1)
			fcu_z.keyframe_points[0].co = 0.0, 1.0 if i is 0 else 0.0

	armature.animation_data.action = previousAction #revert back to the a-pose action






	if not hasattr(armature.animation_data, "drivers"):
		print("ERROR! THERE WERE NO FACE RIG DRIVERS. You must import your .mhx2 models with \"Face Shapes\" and \"Face Shapes Drivers\" checkboxes checked!!!")
		exit()

	# iterate over all bones of the active object
	highestBonePoint = 0

	for bone in armature.pose.bones:
		highestBonePoint = max(highestBonePoint, bone.head.z * armature.scale.z)
		# iterate over all drivers now
		# this should give better performance than the other way around
		# as most armatures have more bones than drivers
		foundDrivers = []
		for d in armature.animation_data.drivers:

			# a data path looks like this: 'pose.bones["Bone.002"].scale'
			# search for the full bone name including the quotation marks!
			if ('"%s"' % bone.name) in d.data_path:
				# we now have identified that there is a driver
				# which refers to a bone channel
				foundDrivers.append(d)

		# if there are drivers, add an item to the dictionary
		if foundDrivers:
			# print ('adding drivers of bone %s to Dictionary' % bone.name)

			# the dictionary uses the bone name as the key, and the
			# found FCurves in a list as the values
			boneDict[bone.name] = foundDrivers

	# now you have a dictionary in hand, which you can use to
	# retrieve all driver info from
	# print ('bonedict: %s' % boneDict)



	# usage examples

	# get all drivers of the active bone, if it has some
	# boneName = bpy.context.active_bone.name

	#expression_data = []

	expressions_json = {}

	# first check if it has drivers at all

	for boneName in boneDict.keys():

		#print(boneName)
		# if so, access the drivers list by using the bone name as the key
		activeBoneDrivers = boneDict[boneName]

		# get number of drivers:
		# print('Number of drivers for bone %s: %i' % (boneName, len(activeBoneDrivers)))

		# iterate over those drivers only:

		for n, d in enumerate(activeBoneDrivers):

			if len(d.driver.variables) == 0: #was probaly w axis
				continue

			variable = []

			# print the expression
			if d.driver.is_valid and d.driver.type == "SCRIPTED":  # print if driver actually works and the type is SCRIPTED
				# print('expression: %s' % d.driver.expression)

				# print the variables
				for var in d.driver.variables:

					# print('variables: name %s, type %s, data %s' % (var.name, var.type, var.targets[0].data_path))

					# for target in var.targets:
					#   # you can also iterate over the targets
					#   # if you use Pythons dir() function, you will see what methods and properties you
					#   # can access:
					#   print ('target methods: %s' % (target.data_path))

					text = var.targets[0].data_path
					pattern = r'"Mfa([A-Za-z0-9_\./\\-]+)"'
					match = re.search(pattern, text)

					if match:

						variable.append([n, match.group(1)])
						#print(variable)
						#print(match.group(1) )

			polyText = d.driver.expression
			#print(polyText)
			expressions = re.compile(r'( [+-] [0-9.]+)\*x([0-9]+)')
			expressions = expressions.findall(polyText)
			expressions = [ [float(x[0].replace(" ", "")), variable[int(x[1]) - 1][1], variable[int(x[1]) - 1][0]] for x in expressions ]
			#print(expressions)

			if len(expressions) == 0:
				continue

			for i, expression in enumerate(expressions):
				#print(expressions[i])


				if not boneName in expressions_json:
					expressions_json[boneName] = {'x':[], 'y':[], 'z':[]}

				axisNames = ['x', 'y', 'z']

				axis = axisNames[expression[2] - 1]
				variable = expression[1]
				constant = expression[0]

				expressions_json[boneName][axis].append({'c': constant, 'v': variable})

				#expressions[i] = {'constant': expression[0], 'variable': expression[1], 'axis': expression[2]}



			#expression_data.append({
			#   'bone_name': boneName,
			#   'drivers': expressions
			#})


	expressions_data = []
	for boneName in expressions_json:
		expressions_data.append({
			   'bone_name': boneName,
			   'drivers': expressions_json[boneName]
			})

filepath = bpy.data.filepath
directory = os.path.dirname(filepath)
dataPath = os.path.join(directory, 'blender.json')

with open(dataPath, 'w') as outfile:
	outdata = {
		'materials': material_data,
		'expressions': expressions_data,
	}

	json.dump(outdata, outfile)

for lamp in [o for o in bpy.data.objects if o.type == 'LAMP']:
	bpy.data.scenes[0].objects.unlink(lamp)
	bpy.data.objects.remove(lamp)

# Export fbx character:
# filepath = os.path.join(r"X:\\Arduino MOCAP\\Headless Blender Django Makehuman\\", export_file_name)

[[obj.modifiers.remove(mod) for mod in obj.modifiers if mod.type == "SUBSURF"] for obj in bpy.data.objects] #remove all subsufr modifiers so that they can not be applied (they would remove all blendshapes by keeping them)

#bpy.ops.object.select_all(action='DESELECT')
#bpy.ops.object.select_all(action='SELECT')

tallest_human_ever = 8.11 * 0.3048
if highestBonePoint >= 2*tallest_human_ever: #impossibly tall character, must be scaled down (maybe user accidentally selected decimeters instead of meters)
	bpy.ops.transform.resize(value=(0.1, 0.1, 0.1), constraint_axis=(False, False, False), constraint_orientation='GLOBAL', mirror=False, proportional='DISABLED', proportional_edit_falloff='SMOOTH', proportional_size=1)
	bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)




for obj in bpy.data.objects:
	if obj.type == 'ARMATURE':
		armature = obj
		continue

	connectedToArmature = False
	if hasattr(obj, 'modifiers'): #first check if it has an armature modifier on the mesh object
		for modifier in obj.modifiers:
			if modifier.type == 'ARMATURE':
				if modifier.object is not None:
					connectedToArmature = True
					break

	if not connectedToArmature: #last chance to check if it is instead parented to a bone of an armature
		root = FindRootRecursive(obj)
		if (root in armObjs):
			connectedToArmature = True

	if connectedToArmature: #fix issue where the eyes shoot off upward after the action has been applied later on, apply all rotations to this object now...
		obj.select = True
		print("OBJ " + str(obj))
		bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
		bpy.ops.object.select_all(action='DESELECT')
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)





filepath = os.path.join(os.path.dirname(bpy.data.filepath), os.path.splitext(bpy.data.filepath)[0] + '.fbx')

apply_scale_options = 'FBX_SCALE_ALL'
check_existing = False
axis_forward = '-Z'
axis_up = 'Y'
filter_glob = "*.fbx"
use_selection = False

bpy.ops.export_scene.fbx(
	filepath=filepath,
	apply_scale_options=apply_scale_options,
	check_existing=check_existing,
	axis_forward=axis_forward,
	axis_up=axis_up,
	filter_glob=filter_glob,
	use_selection=use_selection
)

bpy.data.use_autopack = True
bpy.ops.file.pack_all()

bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print("\nSaved Done!")
"""

blenderscript_prop = r"""

#This file is pushed into a headless subprocess of the user's .blend via command line args, this automatically export .fbx file and material infos json

# !/usr/bin/env python2.7
import bpy, json, os, re

bpy.ops.file.unpack_all(method='WRITE_LOCAL')

# build the material json file:
material_data = []

for m in bpy.data.materials:
	if (m.users == 0 ):
		continue

	used_texture_slots = []
	for slot in m.texture_slots:

		if slot is not None and hasattr(slot.texture, 'image'):
			filename = slot.texture.image.filepath #.encode('ascii','ignore').decode()  # the filename and extension of the image, strip dir info
			filename = os.path.basename(filename.replace('//', ''))  # Extract file name from path

			texture_data = {
				"filename": filename,

				# "use_map_color_diffuse" : texture_data.image.use_map_color_diffuse,
				# "diffuse_color_factor" : texture_data.image.diffuse_color_factor,

				"use_map_color_diffuse": slot.use_map_color_diffuse,

				"use_map_specular": slot.use_map_specular,
				"specular_factor": slot.specular_factor,

				"use_map_normal": slot.use_map_normal,
				"normal_factor": slot.normal_factor,

				"use_map_emit": slot.use_map_emit,
				"emit_factor": slot.emit_factor,

				"use_map_alpha": slot.use_map_alpha,
				"alpha_factor": slot.alpha_factor,
			}

			used_texture_slots.append(texture_data)

	mat = {
		"key": m.name,
		"texture": None,
		"alpha": m.alpha,
		"use_transparency": m.use_transparency,

		"diffuse_intensity": m.diffuse_intensity,
		"specular_intensity": m.specular_intensity,
		"specular_hardness": m.specular_hardness,
		"specular_color": {'r': m.specular_color.r, 'g': m.specular_color.g, 'b': m.specular_color.b},

		"texture_slots": used_texture_slots,
	}
	material_data.append(mat)

	if (used_texture_slots.__len__() is not 0):
		mat['texture'] = used_texture_slots[0]['filename'] #default to using the filename of the first slot
		mat['alpha'] = used_texture_slots[0]['alpha_factor']
		#key = used_texture_slots[0]['filename'] #default to using the filename of the first slot

		for slot in used_texture_slots: #scan through all slots for to find the slot used for the color diffuse texture
			if slot["use_map_color_diffuse"]:
				mat['texture'] = slot['filename']
				mat['alpha'] = slot['alpha_factor']

filepath = bpy.data.filepath
directory = os.path.dirname(filepath)
dataPath = os.path.join(directory, 'blender.json')

with open(dataPath, 'w') as outfile:
	outdata = {
		'materials': material_data,
	}

	json.dump(outdata, outfile)

for lamp in [o for o in bpy.data.objects if o.type == 'LAMP']:
	bpy.data.scenes[0].objects.unlink(lamp)
	bpy.data.objects.remove(lamp)

# Export fbx character:
# filepath = os.path.join(r"X:\\Arduino MOCAP\\Headless Blender Django Makehuman\\", export_file_name)

filepath = os.path.join(os.path.dirname(bpy.data.filepath), os.path.splitext(bpy.data.filepath)[0] + '.fbx')

#bpy.ops.object.select_all(action='DESELECT')
#bpy.ops.object.select_all(action='SELECT')

apply_scale_options = 'FBX_SCALE_ALL'
check_existing = False
axis_forward = '-Z'
axis_up = 'Y'
filter_glob = "*.fbx"
use_selection = False

bpy.ops.export_scene.fbx(
	filepath=filepath,
	apply_scale_options=apply_scale_options,
	check_existing=check_existing,
	axis_forward=axis_forward,
	axis_up=axis_up,
	filter_glob=filter_glob,
	use_selection=use_selection
)

bpy.data.use_autopack = True
bpy.ops.file.pack_all()

bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print("\nSaved Done!")
"""

blenderscript_scene = r"""

"""

blenderscript_nodes = r"""

######## BI to Cycles Shaders Conversion ########

# system_cycles_material_text_node.py Copyright (C) 5-mar-2012, Silvio Falcinelli, additional fixes by others
#
#
# special thanks to user blenderartists.org cmomoney
#
#
# Show Information About the Blend.
# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

bl_info = {
    "name": "Cycles Auto Material Texures Node Editor",
    "author": "Silvio Falcinelli",
    "version": (0,6),
    "description": "automatic cycles texture map",
    "warning": "beta",
    "wiki_url": 'http://blenderartists.org/forum/showthread.php?247271-Cycles-Automatic-Material-Textures-Node'}


import bpy
import os.path


def AutoNodeOn():
    mats = bpy.data.materials
    for cmat in mats:
        cmat.use_nodes=True
    bpy.context.scene.render.engine='CYCLES'

def AutoNodeOff():
    mats = bpy.data.materials
    for cmat in mats:
        cmat.use_nodes=False
    bpy.context.scene.render.engine='BLENDER_RENDER'


def BakingText(tex,mode):
    print('________________________________________')
    print('INFO start bake texture ' + tex.name)
    bpy.ops.object.mode_set(mode='OBJECT')
    sc=bpy.context.scene
    tmat=''
    img=''
    Robj=bpy.context.active_object
    for n in bpy.data.materials:

        if n.name=='TMP_BAKING':
            tmat=n

    if not tmat:
        tmat = bpy.data.materials.new('TMP_BAKING')
        tmat.name="TMP_BAKING"


    bpy.ops.mesh.primitive_plane_add()
    tm=bpy.context.active_object
    tm.name="TMP_BAKING"
    tm.data.name="TMP_BAKING"
    bpy.ops.object.select_pattern(extend=False, pattern="TMP_BAKING", case_sensitive=False)
    sc.objects.active = tm
    bpy.context.scene.render.engine='BLENDER_RENDER'
    tm.data.materials.append(tmat)
    if len(tmat.texture_slots.items()) == 0:
        tmat.texture_slots.add()
    tmat.texture_slots[0].texture_coords='UV'
    tmat.texture_slots[0].use_map_alpha=True
    tmat.texture_slots[0].texture = tex.texture
    tmat.texture_slots[0].use_map_alpha=True
    tmat.texture_slots[0].use_map_color_diffuse=False
    tmat.use_transparency=True
    tmat.alpha=0
    tmat.use_nodes=False
    tmat.diffuse_color=1,1,1
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap()

    for n in bpy.data.downloadedimages:
        if n.name=='TMP_BAKING':
            n.user_clear()
            bpy.data.downloadedimages.remove(n)


    if mode == "ALPHA" and tex.texture.type=='IMAGE':
        sizeX=tex.texture.image.size[0]
        sizeY=tex.texture.image.size[1]
    else:
        sizeX=600
        sizeY=600
    bpy.ops.image.new(name="TMP_BAKING", width=sizeX, height=sizeY, color=(0.0, 0.0, 0.0, 1.0), alpha=True, uv_test_grid=False, float=False)
    bpy.data.screens['UV Editing'].areas[1].spaces[0].image = bpy.data.downloadedimages["TMP_BAKING"]
    sc.render.engine='BLENDER_RENDER'
    img = bpy.data.downloadedimages["TMP_BAKING"]
    img=bpy.data.downloadedimages.get("TMP_BAKING")
    img.file_format = "JPEG"
    if mode == "ALPHA" and tex.texture.type=='IMAGE':
        img.filepath_raw = tex.texture.image.filepath + "_BAKING.jpg"

    else:
        img.filepath_raw = tex.texture.name + "_PTEXT.jpg"

    sc.render.bake_type = 'ALPHA'
    sc.render.use_bake_selected_to_active = True
    sc.render.use_bake_clear = True
    bpy.ops.object.bake_image()
    img.save()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.delete()
    bpy.ops.object.select_pattern(extend=False, pattern=Robj.name, case_sensitive=False)
    sc.objects.active = Robj
    img.user_clear()
    bpy.data.downloadedimages.remove(img)
    bpy.data.materials.remove(tmat)

    print('INFO : end Bake ' + img.filepath_raw )
    print('________________________________________')

def AutoNode():

    mats = bpy.data.materials
    sc = bpy.context.scene

    for cmat in mats:

        cmat.use_nodes=True
        TreeNodes=cmat.node_tree
        links = TreeNodes.links

        shader=''
        shmix=''
        shtsl=''
        Add_Emission=''
        Add_Translucent=''
        Mix_Alpha=''
        sT=False
        lock=True

        for n in TreeNodes.nodes:
            if n.type == 'ShaderNodeOutputMaterial':
                if n.label == 'Lock':
                    lock=False


        if lock:
            for n in TreeNodes.nodes:
                TreeNodes.nodes.remove(n)



            if not shader :
                shader = TreeNodes.nodes.new('ShaderNodeBsdfDiffuse')
                shader.location = 0,470

                shout = TreeNodes.nodes.new('ShaderNodeOutputMaterial')
                shout.location = 200,400
                links.new(shader.outputs[0],shout.inputs[0])

            textures = cmat.texture_slots
            sM=True

            for tex in textures:
                if tex:
                    if tex.use:
                        if tex.use_map_alpha:
                            sM=False

                            if sc.EXTRACT_ALPHA:

                                if tex.texture.type =='IMAGE' and tex.texture.use_alpha:

                                    if not os.path.exists(bpy.path.abspath(tex.texture.image.filepath + "_BAKING.jpg")) or sc.EXTRACT_OW:

                                        BakingText(tex,'ALPHA')
                                else:
                                    if not tex.texture.type =='IMAGE':

                                        if not os.path.exists(bpy.path.abspath(tex.texture.name + "_PTEXT.jpg")) or sc.EXTRACT_OW:

                                            BakingText(tex,'PTEXT')






            if  cmat.use_transparency and cmat.raytrace_transparency.ior == 1 and not cmat.raytrace_mirror.use  and sM:
                if not shader.type == 'ShaderNodeBsdfTransparent':
                    print("INFO:  Make TRANSPARENT shader node " + cmat.name)
                    TreeNodes.nodes.remove(shader)
                    shader = TreeNodes.nodes.new('ShaderNodeBsdfTransparent')
                    shader.location = 0,470
                    links.new(shader.outputs[0],shout.inputs[0])



            if not cmat.raytrace_mirror.use and not cmat.use_transparency:
                if not shader.type == 'ShaderNodeBsdfDiffuse':
                    print("INFO:  Make DIFFUSE shader node" + cmat.name)
                    TreeNodes.nodes.remove(shader)
                    shader = TreeNodes.nodes.new('ShaderNodeBsdfDiffuse')
                    shader.location = 0,470
                    links.new(shader.outputs[0],shout.inputs[0])



            if cmat.raytrace_mirror.use and cmat.raytrace_mirror.reflect_factor>0.001 and cmat.use_transparency:
                if not shader.type == 'ShaderNodeBsdfGlass':
                    print("INFO:  Make GLASS shader node" + cmat.name)
                    TreeNodes.nodes.remove(shader)
                    shader = TreeNodes.nodes.new('ShaderNodeBsdfGlass')
                    shader.location = 0,470
                    links.new(shader.outputs[0],shout.inputs[0])




            if cmat.raytrace_mirror.use and not cmat.use_transparency and cmat.raytrace_mirror.reflect_factor>0.001 :
                if not shader.type == 'ShaderNodeBsdfGlossy':
                    print("INFO:  Make MIRROR shader node" + cmat.name)
                    TreeNodes.nodes.remove(shader)
                    shader = TreeNodes.nodes.new('ShaderNodeBsdfGlossy')
                    shader.location = 0,520
                    links.new(shader.outputs[0],shout.inputs[0])



            if cmat.emit > 0.001 :
                if not shader.type == 'ShaderNodeEmission' and not cmat.raytrace_mirror.reflect_factor>0.001 and not cmat.use_transparency:
                    print("INFO:  Mix EMISSION shader node" + cmat.name)
                    TreeNodes.nodes.remove(shader)
                    shader = TreeNodes.nodes.new('ShaderNodeEmission')
                    shader.location = 0,450
                    links.new(shader.outputs[0],shout.inputs[0])

                else:
                    if not Add_Emission:
                        print("INFO:  Add EMISSION shader node" + cmat.name)
                        shout.location = 550,330
                        Add_Emission = TreeNodes.nodes.new('ShaderNodeAddShader')
                        Add_Emission.location = 370,490

                        shem = TreeNodes.nodes.new('ShaderNodeEmission')
                        shem.location = 180,380

                        links.new(Add_Emission.outputs[0],shout.inputs[0])
                        links.new(shem.outputs[0],Add_Emission.inputs[1])
                        links.new(shader.outputs[0],Add_Emission.inputs[0])

                        shem.inputs['Color'].default_value=cmat.diffuse_color.r,cmat.diffuse_color.g,cmat.diffuse_color.b,1
                        shem.inputs['Strength'].default_value=cmat.emit




            if cmat.translucency > 0.001 :
                print("INFO:  Add BSDF_TRANSLUCENT shader node" + cmat.name)
                shout.location = 770,330
                Add_Translucent = TreeNodes.nodes.new('ShaderNodeAddShader')
                Add_Translucent.location = 580,490

                shtsl = TreeNodes.nodes.new('ShaderNodeBsdfTranslucent')
                shtsl.location = 400,350

                links.new(Add_Translucent.outputs[0],shout.inputs[0])
                links.new(shtsl.outputs[0],Add_Translucent.inputs[1])


                if Add_Emission:
                    links.new(Add_Emission.outputs[0],Add_Translucent.inputs[0])

                    pass
                else:

                    links.new(shader.outputs[0],Add_Translucent.inputs[0])
                    pass
                shtsl.inputs['Color'].default_value=cmat.translucency, cmat.translucency,cmat.translucency,1




            shader.inputs['Color'].default_value=cmat.diffuse_color.r,cmat.diffuse_color.g,cmat.diffuse_color.b,1

            if shader.type=='ShaderNodeBsdfDiffuse':
                shader.inputs['Roughness'].default_value=cmat.specular_intensity

            if shader.type=='ShaderNodeBsdfGlossy':
                shader.inputs['Roughness'].default_value=1-cmat.raytrace_mirror.gloss_factor


            if shader.type=='ShaderNodeBsdfGlass':
                shader.inputs['Roughness'].default_value=1-cmat.raytrace_mirror.gloss_factor
                shader.inputs['IOR'].default_value=cmat.raytrace_transparency.ior


            if shader.type=='ShaderNodeEmission':
                shader.inputs['Strength'].default_value=cmat.emit



            textures = cmat.texture_slots
            for tex in textures:
                sT=False
                pText=''
                if tex:
                    if tex.use:
                        if tex.texture.type=='IMAGE':
                            img = tex.texture.image
                            shtext = TreeNodes.nodes.new('ShaderNodeTexImage')
                            shtext.location = -200,400
                            shtext.image=img
                            sT=True
                        else:
                            if sc.EXTRACT_PTEX:
                                print('INFO : Extract Procedural Texture  ' )

                                if not os.path.exists(bpy.path.abspath(tex.texture.name + "_PTEXT.jpg")) or sc.EXTRACT_OW:
                                    BakingText(tex,'PTEX')

                                img=bpy.data.downloadedimages.load(tex.texture.name + "_PTEXT.jpg")
                                shtext = TreeNodes.nodes.new('ShaderNodeTexImage')
                                shtext.location = -200,400
                                shtext.image=img
                                sT=True


                if sT:
                        if tex.use_map_color_diffuse :
                            links.new(shtext.outputs[0],shader.inputs[0])


                        if tex.use_map_emit:
                            if not Add_Emission:
                                print("INFO:  Mix EMISSION + Texure shader node " + cmat.name)

                                intensity=0.5+(tex.emit_factor / 2)

                                shout.location = 550,330
                                Add_Emission = TreeNodes.nodes.new('ShaderNodeAddShader')
                                Add_Emission.name="Add_Emission"
                                Add_Emission.location = 370,490

                                shem = TreeNodes.nodes.new('ShaderNodeEmission')
                                shem.location = 180,380

                                links.new(Add_Emission.outputs[0],shout.inputs[0])
                                links.new(shem.outputs[0],Add_Emission.inputs[1])
                                links.new(shader.outputs[0],Add_Emission.inputs[0])

                                shem.inputs['Color'].default_value=cmat.diffuse_color.r,cmat.diffuse_color.g,cmat.diffuse_color.b,1
                                shem.inputs['Strength'].default_value=intensity * 2

                            links.new(shtext.outputs[0],shem.inputs[0])


                        if tex.use_map_mirror:
                            links.new(shader.inputs[0],shtext.outputs[0])


                        if tex.use_map_translucency:
                            if not Add_Translucent:
                                print("INFO:  Add Translucency + Texure shader node " + cmat.name)

                                intensity=0.5+(tex.emit_factor / 2)

                                shout.location = 550,330
                                Add_Translucent = TreeNodes.nodes.new('ShaderNodeAddShader')
                                Add_Translucent.name="Add_Translucent"
                                Add_Translucent.location = 370,290

                                shtsl = TreeNodes.nodes.new('ShaderNodeBsdfTranslucent')
                                shtsl.location = 180,240

                                links.new(shtsl.outputs[0],Add_Translucent.inputs[1])

                                if Add_Emission:
                                    links.new(Add_Translucent.outputs[0],shout.inputs[0])
                                    links.new(Add_Emission.outputs[0],Add_Translucent.inputs[0])
                                    pass
                                else:
                                    links.new(Add_Translucent.outputs[0],shout.inputs[0])
                                    links.new(shader.outputs[0],Add_Translucent.inputs[0])

                            links.new(shtext.outputs[0],shtsl.inputs[0])


                        if tex.use_map_alpha:
                            if not Mix_Alpha:
                                print("INFO:  Mix Alpha + Texure shader node " + cmat.name)

                                shout.location = 750,330
                                Mix_Alpha = TreeNodes.nodes.new('ShaderNodeMixShader')
                                Mix_Alpha.name="Add_Alpha"
                                Mix_Alpha.location = 570,290
                                sMask = TreeNodes.nodes.new('ShaderNodeBsdfTransparent')
                                sMask.location = 250,180

                                links.new(Mix_Alpha.inputs[0],shtext.outputs[1])
                                links.new(shout.inputs[0],Mix_Alpha.outputs[0])
                                links.new(sMask.outputs[0],Mix_Alpha.inputs[1])

                                if not Add_Emission and not Add_Translucent:
                                    links.new(Mix_Alpha.inputs[2],shader.outputs[0])

                                if Add_Emission and not Add_Translucent:
                                    links.new(Mix_Alpha.inputs[2],Add_Emission.outputs[0])

                                if Add_Translucent:
                                    links.new(Mix_Alpha.inputs[2],Add_Translucent.outputs[0])



                        if tex.use_map_normal:
                            t = TreeNodes.nodes.new('ShaderNodeRGBToBW')
                            t.location = -0,300
                            links.new(t.outputs[0],shout.inputs[2])
                            links.new(shtext.outputs[0],t.inputs[0])
    bpy.context.scene.render.engine='CYCLES'

from bpy.props import *
sc = bpy.types.Scene
sc.EXTRACT_ALPHA= BoolProperty(attr="EXTRACT_ALPHA",default= False)
sc.EXTRACT_PTEX= BoolProperty(attr="EXTRACT_PTEX",default= False)
sc.EXTRACT_OW= BoolProperty(attr="Overwrite",default= False)


print ('\n\n\nNow Running: system_cycles_material_text_node.py')
print ('This will add node setups for cycles and EEVEE engine using the Blender Internal shaders parameters.\n')
print ('Author Info:')
for key in bl_info.keys():
	print(key, ':', bl_info[key])

AutoNode()
AutoNodeOff()
print("\nMaterial Nodes Created Successfully!")

"""

#Theme colors
COLOR_BACKGROUND = '#4E4E4E'
COLOR_GREEN  = '#00DB1D'
COLOR_RED    = '#C43F3F'
COLOR_BLUE   = '#4077FF'
COLOR_YELLOW = '#FFE802'

def ProcessModelFile(context, filepath, blenderpath, LogMessage):

	cwd = os.path.dirname(os.path.realpath(__file__))

	basename_extension=os.path.basename(filepath)
	basename=os.path.splitext(basename_extension)[0]

	source_directory = os.path.dirname(filepath)# os.path.dirname(os.path.realpath(__file__))
	dest_directory = os.path.join(source_directory, basename.lower() + "_%s" % context.tkvar.get().lower() )

	try:
		temp_dir = mkdtemp()

		if not os.path.exists(temp_dir): #if the user's upload folder exists (normally should not exist)
			os.makedirs(temp_dir) #create the user's uplaod folder
			LogMessage("CREATED DIRECTORY: " + temp_dir)
		else:
			LogMessage("Directory %s already exists??" % temp_dir, 'warning')

		LogMessage("Copying .blend character to project directory.")

		filepathcopy = os.path.join(temp_dir, basename_extension) #change to the copied file
		copyfile(filepath, filepathcopy)


		#temp_dir = mkdtemp()
		tempfilepath = os.path.join(temp_dir, "blenderscript.py ")

		tempfile = open(tempfilepath, "w")

		blenderScriptText = blenderscript_nodes + context.get_blendscript()

		tempfile.write(blenderScriptText)
		tempfile.close()

		copyfile(filepath, filepathcopy) #move a copy of the .blend into a temp directory for processing

		LogMessage("Running blenderscript.py to build export data.")
		out = subprocess.check_output([
			blenderpath,
			filepathcopy,
			r"--background",
			r"--python",
			tempfilepath, #the path to the temporary blenderscript.py file
		], shell=True, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

		os.remove(tempfilepath)

		LogMessage(out, 'stdout') #logs all the stdout messages from blender subprocess to this tkinter scrolltext

		LogMessage("Success! A .json file has just been created containing the model information necessary for this project.", 'success')

	except subprocess.CalledProcessError as e:
		#raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
		LogMessage("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output), 'warning') #logs all the stdout messages from blender subprocess to this tkinter scrolltext
		LogMessage("Attempting to continue...", 'grayed')
	except:
		LogMessage("Error! Something went wrong trying to run the blenderscript.py from the subprocess.", 'error') #logs all the stdout messages from blender subprocess to this tkinter scrolltext
		LogMessage("Parameters Dump: %s" % str([
				blenderpath,
				filepathcopy,
			]), 'grayed') #logs all the stdout paramenters to this tkinter scrolltext
		raise
	finally:
		#os.rmdir(temp_dir) #note that rmdir fails unless it's empty, which is why rmtree is so convenient:
		if (os.path.exists(dest_directory)): #if this avatar has been processed before, a directory may still exists with old processing files
			shutil.rmtree(dest_directory)# remove everything

		shutil.move(temp_dir, dest_directory) #move the temp files to a processing folder located next to the original .blend file
		#shutil.rmtree(temp_dir)# remove everything
		pass

	LogMessage("Attempting to copy textures from source directoy")
	textures_directory = os.path.join(dest_directory, "textures")
	source_textures_directory = os.path.join(source_directory, "textures")

	if os.path.isdir(source_textures_directory):
		LogMessage("Found some source textures, copying folder now.")
		#copy_tree (source_textures_directory, textures_directory)
		os.makedirs(os.path.dirname(textures_directory + r"\\"), exist_ok=True) #do not raise the target directory already exists error

		src_files = os.listdir(source_textures_directory)
		for file_name in src_files:
			full_file_name = os.path.join(source_textures_directory, file_name)
			if os.path.isfile(full_file_name):
				shutil.copy(full_file_name, textures_directory )
	else:
		LogMessage("Could not find a \"Textures\" directory for this model.", 'warning')


	blender_json_path = os.path.join(dest_directory, "blender.json")

	LogMessage("Parsing the blender.json file for material and texture information.\n%s" % blender_json_path)

	with open(blender_json_path) as f:
		blenderJson = json.load(f)
		materialsJson = blenderJson['materials']


	alphaTexturesList = []


	LogMessage("Preparing to process image textures.")

	def ProcessImages():
		imageCounter = 0 #total number of downloadedimages processed (if still zero when done, means no downloadedimages were processed)

		for folder, subs, files in os.walk(textures_directory):
			for filename in files:
				file_path = os.path.join(folder, filename)

				if (not os.path.isfile(file_path)):#how to check if a file is a directory - https://stackoverflow.com/a/3204819/3961748
					continue

				try:
					Image.open(file_path).verify()
				except Exception as e:
					LogMessage('Invalid image ' + str(e), 'error')
					if file_path.lower().endswith(".fbx"):
						pass
					elif os.path.basename(file_path) == "blender.json":
						pass #skip deleting the materials.json file that might have been created from BuildCharacterExportJson
					else:
						LogMessage("Deleting file: " + file_path, 'grayed')
						os.remove(file_path)#it is not a texture or the .fbx (so delete this file)
					continue

				#if im is not None:# or imghdr.what(file_path) is not None: #check if a file is a valid image file? - https://stackoverflow.com/a/902779/3961748
				LogMessage("Optimizing image: " + file_path)

				try:
					im = Image.open(file_path)
				except Exception as e:
					LogMessage('Image could not be opened. ' + str(e), 'error')
					continue

				size = 1024, 1024 #the maximum size of the texture downloadedimages
				im.thumbnail(size, Image.ANTIALIAS)

				im.convert('P') #prevents strange error: "ValueError: unknown raw mode" - known bug: https://github.com/python-pillow/Pillow/issues/646

				#TODO For Unity - if use_map_alpha is true for this image, then need to seek for any images in the same material/slot that uses diffuse use_map_color_diffuse and apply the alpha mask
				for item in materialsJson:
					for slot in item['texture_slots']:
						if slot['filename'] == filename:
							if slot['use_map_specular']:
								im = ImageEnhance.Brightness(im).enhance(0.5) #default values are way too high for Standard shader so multiply by 0.5
								LogMessage("Optimizing for \"use_map_specular\"", 'notice')
							if slot['use_map_alpha']:
								for subitem in materialsJson: #search for a corresponding diffuse/color image to apply the alpha mask to
									for subslot in subitem['texture_slots']:
										if subslot['material'] == slot['material']:
											if subslot['slot'] != slot['slot']:
												if subslot['use_map_color_diffuse'] is True:

													sub_file_path = os.path.join(folder, subslot['filename']) #path to the diffuse image
													diff = Image.open(sub_file_path) #the diffuse image

													if diff is not None:
														mask = im.copy()

														if diff.size > mask.size:
															mask = mask.resize(diff.size, Image.ANTIALIAS)
														else:
															diff = diff.resize(mask.size, Image.ANTIALIAS)

														mask.convert('1')
														mask.mode = "1"

														diff.putalpha(mask)

														os.path.splitext(subslot['filename'])

														newFileName = os.path.splitext(subslot['filename'])[0] + '.png'
														subitem['texture'] = subslot['filename'] = newFileName
														subslot['use_map_alpha'] = True #modify this so that the new diffuse image will use alpha when imported into Unity

														os.remove(sub_file_path)

														savePath = os.path.join(folder, newFileName)
														diff.save(savePath)

														LogMessage("Created a new alpha masked composite image: %s " % subslot['filename'])


				if (im.mode == "RGBA"):#check if the alpha is being used in this image by looking at if the alpha pixels overlay colors other than the default empty color

					imageUpdated = False
					for item in materialsJson:
						if (item['texture'] == filename):

							if item['texture'] in alphaTexturesList:
								continue #some object has already set it to use alpha, thus it should remain as such even if another object says it is not transpareant
							elif item['use_transparency']:
								alphaTexturesList.append(item['texture'])

							im.mode = "RGBA" if item['use_transparency'] else "RGB"

							imageUpdated = True
					if not imageUpdated:
						im.mode = "RGB"

				LogMessage("SIZE W:%s H:%s MODE:%s" % (im.width, im.height, im.mode))

				save_path = os.path.join(textures_directory, filename)


				try:
					im.save(save_path)
				except Exception as e:
					LogMessage('Image could not be saved. ' + str(e), 'error')
					continue

				imageCounter += 1 #was a valid image, so count it

		return imageCounter


	imageCounter = ProcessImages()

	with open(blender_json_path, 'w') as outfile:
		json.dump(blenderJson, outfile) #update the blender.json file with any modified values
		LogMessage("Re-saved blender.json file if there were any modified values.")



	if imageCounter is 0 and False:#check if any textures exist
		if(os.path.isdir(textures_directory)):
			LogMessage("No Textures Were Packed! Did you forget to enable the \"Automatically pack into .blend\" checkbox?", 'warning')
		else:
			LogMessage("Textures directory was not copied and no downloadedimages were processed.", 'warning')
		#LogMessage("Attempting to copy textures from source directoy")
		#source_textures_directory = os.path.join(source_directory, "textures")

		#if os.path.isdir(source_textures_directory):
		#	LogMessage("Found some source textures, copying folder now.")
		#	copy_tree (source_textures_directory, textures_directory)
		#	imageCounter = ProcessImages()
		#	if imageCounter is 0:#check if any textures exist
		#		LogMessage("Im sorry, but still no textures were processed.", 'warning')
		#	else:
		#		LogMessage("Finished processing %d downloadedimages." % imageCounter)
		#else:
		#	LogMessage("The path: \"%s\" does not exist." % source_textures_directory, 'warning')
	else:
		LogMessage("Finished processing %d downloadedimages." % imageCounter)

	LogMessage("Creating readme.txt")

	text_file = open( os.path.join(dest_directory,"readme.txt"), "w")

	readme = "%s Version: %s " % (__title__, __version__)
	readme += "\n\nCreated Timestamp: %s" % time.strftime("%Y,%m,%d,%H,%M,%S")
	readme += "\n\nThe files in this directory are for the %s AnimPrep %s project." % (basename_extension, context.tkvar.get().lower())

	text_file.write(readme)
	text_file.close()

	LogMessage("Completed Successfully!", 'success')



def ProcessPropFile(filepath, blenderpath, LogMessage):
	pass

def ProcessSceneFile(filepath, blenderpath, LogMessage):
	pass


class scrollTxtArea:
	def __init__(self,root):
		frame=Frame(root)
		frame.pack(fill=BOTH, expand=YES)
		self.textPad(frame)

	def textPad(self,frame):

		#add a frame and put a text area into it
		textPad=Frame(frame)
		self.text=Text(textPad,height=0,width=0,foreground="green",background="black",font=("Courier", 8))

		self.text.tag_config('error', background=COLOR_RED, foreground="white",font=("Courier", 10, 'bold') )
		self.text.tag_config('traceback', foreground=COLOR_RED,font=("Courier", 10, 'bold') )
		self.text.tag_config('stdout', foreground="white" )

		self.text.tag_config('warning', foreground=COLOR_YELLOW)
		self.text.tag_config('notice', background=COLOR_BLUE, foreground="white", font=("Courier", 10, 'italic'))
		self.text.tag_config('success', font=("Courier", 12, 'bold'))
		self.text.tag_config('grayed', foreground="gray", font=("Courier", 8, 'italic'))

		# add a vertical scroll bar to the text area
		scroll=Scrollbar(textPad)
		self.text.configure(yscrollcommand=scroll.set)
		scroll.config(command=self.text.yview)

		#pack everything
		self.text.pack(side=LEFT,fill=BOTH, expand=YES)
		scroll.pack(side=RIGHT,fill=Y,  expand=NO)
		textPad.pack(fill=BOTH, expand=YES)

	def yview_pickplace(self, *what):
		self.text.yview_pickplace(what)

	def insert(self,text, tag=None):
		self.text.insert(INSERT, text, tag)

	def clear(self):
		self.text.delete('0.0', END)

class Interface:

	pickle_data = { #the default directories to intialize to when the user presses on button to open a file browser
		#'browsefile_0': "/",
		'browseapp': "C:\\Program Files\\Blender Foundation\\Blender\\",
		'blenderpath': "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
	}

	def __init__(self):
		self.start_time = -1

		self.root = Tk()
		self.root.title(__title__)
		self.root.geometry("550x250") #You want the size of the app to be 500x500
		self.root.minsize(550, 200) #Don't allow resizing in the x or y direction

		##The Base64 icon version as a string
		icon = """AAABAAEAlpYAAAEAIABwawEAFgAAACgAAACWAAAALAEAAAEAIAAAAAAAkF8BABMLAAATCwAAAAAAAAAAAAD////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+//7+/v/+/v7//v7+//79/f/9/f3//f39//z8/f/8/Pz//Pz8//z8/P/8/Pz//Pz7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7/Pz/+/z8//z8/P/8/Pz//Pz8//38/f/9/f3//f39//39/f/+/v3//v7+//7+/v/+/v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/+/v7//f39//39/f/9/P3//Pz8//z8/P/8/Pz/+/v8//v7+//7+/v/+/v6//v7+v/6+vr/+vr6//r6+v/6+vr/+vr6//r6+v/5+vn/+fn5//r5+v/6+vr/+vr6//r6+v/6+vr/+vr6//r6+v/6+vr/+vr6//r7+v/7+/r/+/v7//v7+//7+/v//Pv8//z8/P/8/Pz//Pz9//39/f/9/f3//v39//7+/v/+//7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7//v7///7+/v/+/f3//f39//39/f/8/Pz//Pz8//v7+//7+/v/+/v7//r7+v/6+vr/+vr6//r5+v/6+vn/+fn5//n5+f/5+fn/+fj5//n5+P/4+fn/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+fn/+fn5//n5+P/5+fn/+fn5//n6+v/6+vr/+vr6//r6+v/7+/r/+/v7//v7+//8/Pz//Pz8//z8/f/9/f3//f39//7+/f///v7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/v7//f39//39/f/8/Pz//Pz8//z7+//7+/v/+/r7//r6+v/6+vr/+fr5//n5+f/5+fn/+Pn4//j4+P/4+Pj/+Pj4//f39//39/j/9/f4//f39//39/f/9/f3//f39//29/b/9vf3//b39v/29vb/9/f3//f39//39/f/9/f3//f39//39/f/9/f3//f39//4+Pj/+Pj4//j4+P/5+Pj/+fn4//n5+f/5+fn/+fn5//r6+v/6+vr/+/r6//v7+//8+/z//Pz8//z8/P/9/f3//f79//7+/v/+/v7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+///+/v7//f39//39/f/8/Pz//Pz8//v7+//7+/v/+vr6//r6+v/5+fr/+fn5//j4+f/4+Pj/+Pj4//j4+P/39/f/9/f3//f39//29/b/9vb2//b29v/29fb/9vb2//b19f/19fb/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//X29f/29vb/9vb1//b29v/29vb/9vb2//f29//39/f/9/f3//f4+P/4+Pj/+Pj4//j5+P/5+fn/+fn5//n5+v/6+vr/+/r7//v7+//7/Pv//Pz8//z9/f/9/f3//v7+//7+/v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+//7//v7+//39/f/8/fz//Pz8//v7+//7+/v/+vr6//n6+v/5+fn/+fn5//j4+P/4+Pj/9/f3//f39//39/b/9/b2//b29v/29vb/9fX1//X19f/19fX/9fX1//T09P/09PT/9PT0//T09P/09PT/9PTz//P09P/z9PT/9PP0//Tz9P/z8/T/9PTz//Tz8//08/P/9PTz//T09P/09PT/9PT0//T09P/19PT/9fX1//X19f/19fX/9vb2//b29v/29vb/9vf3//f39//39/f/+Pj4//j4+P/5+fn/+fn5//r5+v/6+vr/+vv7//v7+//8/Pz//Pz8//39/f/+/v3//v7+///+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//7+/v/9/f3//Pz8//z8/P/7+/v/+vr7//r6+v/5+vn/+fn5//j4+f/4+Pj/9/f3//f39//39/f/9vb2//b29v/19fX/9fX1//X19f/09PT/9PT0//T09P/z8/T/8/Pz//Pz8//z8/P/8/Py//Lz8v/y8/L/8vPy//Ly8//y8vL/8vLy//Ly8v/y8vL/8vLy//Ly8v/y8vL/8vLz//Ly8//y8/L/8/Pz//Pz8//z8/P/9PP0//T09P/09PT/9PT0//T09P/19fX/9fX1//X29v/29vb/9vb3//f29//39/f/+Pj4//j4+P/5+Pn/+fn5//r6+v/6+/r/+/v7//v7/P/8/Pz//f39//79/v/+/v7////+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/+/v7//f39//38/P/8/Pv/+/v7//r6+v/6+vn/+fn5//n5+P/4+Pj/+Pf3//f39//29vb/9vb2//b29f/19fX/9fX1//T09P/09PT/8/P0//Pz8//y8/P/8/Py//Ly8v/y8vL/8vLy//Hx8f/x8fL/8fHx//Hx8f/x8fH/8fDx//Hx8f/w8fD/8PDw//Dx8f/x8PH/8PDx//Hx8f/x8fH/8fHx//Hx8f/x8fH/8fHx//Ly8f/y8vL/8vLy//Ly8v/y8/L/8/Pz//Pz8//z8/P/9PT0//T09P/19PX/9fX1//X19f/29vb/9/b2//f39//39/f/+Pj4//j5+f/5+fn/+vr6//r6+v/7+/v//Pv7//z8/P/9/f3//f39//7+/v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7//v7+//39/f/8/Pz//Pz8//v7+//6+vr/+vr6//n5+f/4+Pj/+Pj4//f39//29/f/9vb2//b19v/19fX/9PX0//T09P/08/T/8/Pz//Pz8//y8vP/8vLy//Ly8v/x8fH/8fHx//Hx8P/w8PD/8PDw//Dw8P/w7/D/7/Dw/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7/D/7+/w//Dw7//w8PD/8PDw//Dx8P/x8fH/8fHx//Hy8f/y8vL/8vLy//Py8v/z8/P/8/Pz//T09P/09PT/9fX1//X19f/29vb/9vb2//f39//4+Pf/+Pj4//n5+f/5+vr/+vr6//r7+v/7/Pv//Pz8//39/f/9/f7//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7///7+/v/9/f3//P38//z8+//7+/v/+vr6//r6+f/5+fn/+Pn4//j3+P/39/f/9vb2//b29v/19fX/9fT1//T09P/z9PT/8/Pz//Pz8v/y8vL/8vLy//Hx8f/x8fH/8fHx//Dw8P/w8PD/7/Dv/+/v7//v7+//7+/v/+7u7v/u7u7/7u7u/+7u7v/u7u7/7u7u/+3t7v/t7e7/7u3t/+7u7v/t7e7/7e7t/+7t7v/u7e7/7u7u/+7u7v/u7u7/7u7u/+7u7v/u7u7/7+/v/+/v7//w7/D/8PDw//Dw8P/w8fH/8fHx//Hx8f/y8vL/8vLy//Py8//z8/P/8/T0//T09P/19PT/9fX1//X19f/29vb/9/f3//f39//4+Pj/+fn5//n5+f/6+vr/+/v7//v7/P/8/Pz//f39//7+/v/+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v///v7+//z9/f/8/Pz/+/v7//r6+v/6+fr/+fn5//j4+P/3+Pj/9/f3//b29v/29vb/9fX1//X19P/09PT/8/Pz//Pz8v/y8vL/8vLy//Hx8f/x8PH/8PDw//Dw8P/v7+//7+/v/+/v7//u7+7/7u7u/+3u7v/t7e3/7e3t/+3t7f/t7e3/7e3t/+zs7P/s7Oz/7Ozt/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozt/+zs7P/s7Oz/7O3t/+3t7f/t7u3/7e7t/+3u7v/u7u7/7u7u/+7v7//v7+//7/Dv/+/w8P/w8PD/8fHx//Hx8f/y8vH/8vLy//Pz8//z8/P/8/T0//T09P/09fX/9fX1//b29v/39/f/9/f3//j4+P/5+Pn/+fn6//r6+v/7+/v/+/z8//38/P/9/f3//v7+//7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7///7+/v/9/f3//Pz8//v8+//6+/v/+vr6//n5+f/4+Pj/+Pj3//f39//29vb/9fX1//X19f/09PT/9PT0//Pz8//z8vP/8vLy//Hx8f/w8fH/8PDw/+/w8P/v8O//7u/v/+/u7v/u7u7/7e7u/+3t7f/t7e3/7O3t/+zs7P/s7Oz/7Ozs/+zs7P/r6+v/6+vr/+vr6//r6uv/6urr/+rq6//r6+v/6+vq/+vq6v/q6+v/6urr/+rq6//r6+v/6+vr/+vr6//r6+v/6+vr/+vr7P/s7Ov/7Ozs/+zs7P/s7Oz/7Ozt/+3t7f/t7e3/7u7u/+7u7v/v7+//7+/v//Dv8P/w8PD/8fDw//Hx8f/y8fH/8vLy//Pz8//z8/P/9PT0//T09f/19fX/9vb2//f39v/39/f/+Pj4//n5+P/6+fr/+vr6//v7+//8/Pz//f39//3+/v///v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+//7//v3+//38/f/8/Pz/+/v7//r6+v/6+fn/+fn5//j4+P/39/f/9/b2//b19v/19fX/9PT0//Pz9P/z8/P/8vLy//Ly8v/x8fH/8PDw//Dw8P/v7+//7+/v/+7v7//t7u7/7e3t/+3t7f/t7ez/7Ozs/+zs7P/r7Ov/6+vr/+vr6//r6+r/6urq/+rq6v/q6ur/6urq/+rp6f/p6en/6enp/+np6f/p6en/6enp/+np6f/p6en/6enp/+np6f/p6er/6enp/+np6v/p6ur/6urq/+rq6v/q6ur/6urr/+vr6//r6+v/6+vr/+vr7P/s7Oz/7Ozs/+3t7f/t7e3/7u7u/+7u7//v7+//7+/v/+/w8P/w8PD/8fHx//Hy8f/y8vL/8/Lz//Pz9P/09PT/9fX0//X19f/29vb/9/f3//j49//5+Pj/+fn5//r6+v/7+/r//Pz8//z8/P/9/f3//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v8/P/7+/r/+vr6//n5+f/4+Pj/9/f4//b29v/29vb/9fX1//T09P/z9PT/8/Pz//Ly8v/x8fL/8fHx//Dw8P/w8PD/7+/v/+/u7v/u7u7/7e7u/+3t7f/s7Oz/7Ozs/+zr7P/r6+v/6+vr/+rq6v/q6ur/6urp/+np6v/p6en/6enp/+jo6f/o6ej/6Ojo/+jo6P/o6Oj/5+jn/+jo6P/n6Oj/5+jn/+jn5//o5+j/6Ojn/+fn6P/n6Oj/6Ofo/+jo6P/o6Oj/6Ojp/+jo6P/p6On/6ejp/+np6f/p6en/6urp/+rq6v/q6+v/6+vr/+vr6//s7Oz/7Ozs/+3t7f/t7e3/7u7t/+7u7v/v7+//8O/v//Dw8P/x8fD/8fHx//Ly8v/z8vP/8/Pz//T09P/19fX/9fX2//b29v/39/f/9/j4//n4+f/5+vr/+/r6//v7+//8/Pz//f39//7+/v/+/v7//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v///v7+//39/f/8/Pz/+/v7//r6+v/5+vn/+Pj4//j4+P/39/f/9vb2//X19f/09fT/9PT0//Pz8//y8vL/8vHy//Hx8f/w8PD/8PDv/+/v7//u7u7/7u3u/+3t7f/s7Oz/7Ozs/+vr6//r6+v/6+rq/+rq6v/q6ur/6enp/+np6f/o6ej/6Ojo/+fo6P/o5+j/5+fn/+fn5//n5+f/5+bm/+fm5v/m5ub/5ubm/+bm5v/m5ub/5ubm/+bm5v/m5ub/5ubm/+bm5v/m5ub/5ubm/+bm5v/m5+b/5+fn/+fn5//n5+f/5+fn/+jo6P/o6Oj/6Ojo/+jp6f/p6en/6erp/+nq6v/q6ur/6+vr/+vr6//s7Oz/7Ozs/+3t7f/t7e3/7u7u/+7v7//v7+//8PDw//Hw8f/x8fH/8fLy//Lz8v/z8/P/9PT0//X19f/29vb/9vb3//f39//4+Pj/+fn5//r6+v/7+/v/+/z8//38/f/+/f3//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7////+/v7//fz9//z8/P/7+/r/+vr6//n5+f/4+Pj/9/f3//b39v/19fb/9fX1//T09P/z8/P/8/Ly//Ly8v/x8fH/8PDw//Dw8P/v7+//7u7u/+3u7f/t7e3/7Ozt/+zr7P/r6+v/6+vq/+rq6v/p6ur/6enp/+np6f/p6On/6Ojo/+fo6P/n5+f/5+fn/+bm5v/m5ub/5ubm/+bl5v/l5uX/5eXl/+Xl5f/l5eX/5eXl/+Xl5f/l5eT/5OTk/+Tl5f/l5eX/5eXk/+Xl5P/l5eT/5eXl/+Xl5f/l5eX/5uXl/+bl5f/m5ub/5ubm/+bm5v/n5ub/5+fn/+fn5//o5+f/6Ojo/+jp6P/p6en/6enp/+nq6v/q6uv/6+vr/+vr7P/s7Oz/7e3t/+3t7v/u7u7/7+7v/+/v7//w8PD/8PDx//Hx8f/y8vL/8/Pz//T09P/19PT/9fX1//b29v/39vf/+Pj4//j5+f/6+vr/+vr7//z7+//9/Pz//f39//7+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/P3//Pv8//v6+//6+vr/+Pn4//j4+P/39/f/9vb2//X19f/09PT/9PP0//Pz8//y8vL/8fHx//Dw8P/w8O//7+/v/+7u7v/t7e7/7e3t/+zs7P/r6+v/6+vr/+rq6v/q6ur/6enp/+np6P/o6Oj/6Ofo/+fn5//n5+b/5ufm/+bm5v/l5ub/5eXl/+Xl5f/l5eT/5OTk/+Tk5P/k5OT/5OTk/+Tj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/5OPk/+Tk5P/k5OT/5eTk/+Xl5f/l5eX/5ebl/+bm5v/m5ub/5+fm/+fn5//n6Of/6Ojo/+jo6P/o6en/6enq/+rq6v/r6+v/6+vs/+zs7P/t7O3/7e3t/+7u7v/v7u//7/Dv//Dw8P/x8fH/8vLx//Ly8v/z8/P/9PT0//X19f/29vb/9/f2//f49//5+Pj/+fn5//r6+v/7+/v//Pz8//39/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+/v/+vr6//n5+v/4+fj/9/j3//f29//29fb/9fX1//T09P/z8/P/8vLy//Hx8f/x8fH/8PDw/+/v7//u7u7/7e7u/+3t7f/s7Oz/6+vs/+vr6//q6ur/6enq/+np6f/p6Oj/6Ojo/+fn5//m5+f/5ubm/+bm5v/l5eX/5eXl/+Tk5P/k5OT/5OTk/+Pj4//j4+P/4+Pj/+Li4//i4uL/4uLi/+Li4v/i4uL/4eLi/+Hi4f/i4eH/4uHh/+Hh4f/h4eL/4eHh/+Hh4f/i4uL/4uLi/+Li4v/i4uL/4uLi/+Li4v/j4+P/4+Pi/+Pj4//j5OP/5OTk/+Tl5P/l5eX/5eXl/+Xl5v/m5ub/5ubn/+fn5//n6Of/6Ojo/+no6f/p6en/6urq/+vq6v/r6+v/7Ozs/+zs7P/t7e3/7u7u/+/v7//v8PD/8PDw//Hx8f/y8vL/8/Pz//Pz9P/09fX/9fX1//b29v/39/f/+Pj4//n5+f/6+vr/+/v7//z8/P/9/f3//v7+//7//v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v7+//6+vr/+fn5//j4+f/39/f/9vb2//X19f/19PT/9PP0//Py8//y8vL/8fHx//Dw8P/v7+//7+/v/+7u7v/t7e3/7Ozt/+vr7P/r6+v/6urq/+np6f/p6en/6Ojo/+fn6P/n5+f/5ubm/+bm5v/l5eX/5eXl/+Xl5P/k5OT/5OPk/+Pj4//j4+P/4uLi/+Li4v/i4uL/4eHh/+Hh4f/h4eH/4eHh/+Dh4f/g4OD/4ODg/+Dg4P/g4OD/4ODg/+Dg4P/g4OD/4ODg/+Dg4P/g4eD/4ODg/+Hg4P/g4eD/4eHh/+Hh4f/h4eH/4eHh/+Li4v/i4uL/4+Li/+Pj4//j4+P/5OTk/+Tk5P/l5eT/5eXl/+bm5v/m5+b/5+fn/+fn5//o6Oj/6Ojp/+np6f/q6ur/6+rr/+vr6//s7Oz/7e3t/+3t7f/u7u7/7+/v//Dw8P/x8PH/8vHy//Ly8//z8/P/9PT0//X19f/29vb/9/f3//j4+P/5+fn/+vr6//v7+v/8/Pz//f39//7+/v///v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/v7//r6+v/5+fn/+Pj4//f39//29vb/9fX1//T09P/z8/P/8vLy//Hy8f/w8PH/7/Dw/+/v7//u7u7/7u3t/+3t7f/s7Oz/6+vr/+rq6v/q6un/6enp/+jo6P/o5+j/5+fn/+bm5v/m5uX/5eXl/+Tk5P/k5OT/4+Pj/+Pj4//i4uL/4uLi/+Hi4v/h4eH/4eHh/+Hg4P/g4OD/4ODg/9/f3//f39//39/f/9/f3//f39//39/f/9/f3v/e39//3t7e/9/e3v/e3t7/397f/9/e3v/f397/397e/9/f3//f39//4N/f/9/g3//g4OD/4ODg/+Dh4f/h4OH/4eHh/+Lh4f/h4uL/4uLj/+Pj4//j4+P/5OTk/+Tk5P/l5eX/5eXm/+bm5v/m5+f/5+fn/+jo6P/p6ej/6enp/+rq6v/r6uv/7Ozs/+zs7P/t7e3/7u7t/+/u7v/v7+//8PDw//Hx8f/y8vL/8/Pz//T09P/09fX/9vb2//f39//4+Pj/+Pj4//n6+f/7+/v/+/z7//38/P/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+/v/+vr6//n5+f/4+Pj/9vf3//b29v/19fX/9PT0//Pz8//y8vL/8fHx//Dw8P/v7+//7u7v/+7u7v/t7e3/7Ozs/+vr6//q6+r/6urq/+np6f/o6Oj/6Ofn/+fn5//m5ub/5eXl/+Xl5f/k5OT/5OTj/+Pj4//i4uP/4uLi/+Hh4f/h4eH/4OHh/+Dg4P/g4OD/39/f/9/f3//e3t//3t/e/97e3v/e3d7/3t3e/93e3f/d3d3/3d3d/93d3f/d3d3/3d3d/93d3f/c3d3/3d3d/93d3f/d3d3/3d3d/93d3f/e3t7/3t3e/97e3v/e3t7/3t7e/9/f3//f39//39/g/+Dg4P/g4OD/4eHh/+Hh4f/i4uL/4uLi/+Pj4v/j4+P/5OTk/+Xk5f/l5eX/5ubm/+bm5v/n5+f/6Ojo/+jp6P/p6en/6urq/+vr6v/s7Ov/7O3s/+3t7f/u7u7/7+/v//Dw8P/x8fH/8vLy//Ly8v/z8/T/9PT0//b19f/39vb/9/f4//j4+f/5+vr/+vr6//v7+//9/f3//f3+//7+/v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v7+//6+vr/+fn5//j4+P/39/b/9vb2//X19f/09PT/8/Pz//Ly8v/x8fH/8PDw/+/v7//u7u7/7e3t/+zs7P/r7Oz/6uvr/+rq6v/p6en/6Ojo/+jn5//n5+f/5ubm/+Xm5f/l5eX/5OTk/+Tk4//j4+P/4uLi/+Li4v/h4eH/4OHh/+Dg4P/f4OD/39/f/9/f3//e3t7/3t7e/97d3v/d3d3/3d3d/93d3f/c3Nz/3Nzc/9zc3P/c3Nz/3Nzc/9vc3P/b29z/29vb/9vb3P/c29v/3Nzb/9vc3P/c3Nz/3Nzc/9zc3P/c3Nz/3Nzc/93d3P/d3dz/3d3d/93d3f/e3t7/3t7e/97e3v/f39//39/f/+Dg4P/h4OD/4eHh/+Hh4f/i4uL/4+Pi/+Pj4//j5OT/5OTk/+Xl5f/m5ub/5+fn/+fn5//o6Oj/6enp/+rp6v/q6+r/6+vr/+zs7P/t7e3/7u7u/+7u7//w7+//8PHx//Hy8f/y8vL/8/Pz//T09P/19fX/9vb2//f39//4+Pj/+fn5//r6+v/8+/z//P39//3+/v/+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/r7//n5+f/5+fn/9/j4//b39v/29vX/9PT0//Pz9P/z8vP/8vLy//Hx8f/w8PD/7+/v/+7u7f/t7e3/7Ozs/+vr6//q6ur/6erq/+np6f/o6Oj/5+fn/+bm5v/l5ub/5eXl/+Tk5P/j4+P/4+Pj/+Li4v/h4eH/4eHh/+Dg4P/g4OD/39/f/9/e3//e3t7/3d7e/93d3f/d3d3/3Nzc/9zc3P/b3Nz/29vb/9vb2//b29v/2trb/9ra2v/a2tv/2tra/9ra2v/a2tr/2tra/9ra2v/a2tr/2tra/9ra2v/a2tr/2tra/9ra2v/b2tv/29vb/9vb2//b29v/29zb/9zc3P/c3Nz/3dzd/93d3f/d3d7/3t7e/97e3v/f39//39/g/+Dg4P/h4OH/4eHh/+Li4v/i4uL/4+Pj/+Tk5P/l5OX/5eXl/+bm5v/n5+f/6Ojo/+jo6P/p6en/6urq/+vr6v/s7Oz/7ezs/+7t7v/v7u7/7+/v//Dx8P/x8fH/8vLy//Pz8//09PT/9fX1//b29v/39/f/+Pj4//n6+f/6+vr/+/v7//z9/f/9/v3//v/+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+/v/+vr6//j5+P/39/j/9vb2//b19f/09fT/8/P0//Ly8v/x8vH/8PDw/+/v8P/u7u7/7u3t/+3t7P/s7Oz/6+vq/+rq6v/p6en/6Ojo/+fn6P/n5uf/5ebm/+Xl5f/k5OT/4+Pj/+Pj4v/i4uL/4eLi/+Hh4f/g4OD/39/f/9/f3//e3t7/3d7d/93d3f/d3Nz/3Nzc/9zc3P/b29v/29vb/9va2//a2tr/2tra/9na2v/Z2dr/2dnZ/9nZ2f/Z2dn/2NjY/9jY2f/Z2Nj/2NjY/9jY2P/Y2dn/2NnZ/9nZ2P/Z2dn/2dnZ/9jZ2f/Z2dn/2dnZ/9rZ2v/a2tr/2tra/9ra2//b29v/29vb/9zb2//c3Nz/3Nzd/93d3f/e3d7/3t7e/9/e3//f39//4ODg/+Dg4P/h4eH/4uLi/+Lj4v/j4+P/5OTk/+Tl5P/l5eX/5ubm/+fn5//o6Oj/6enp/+nq6v/q6+r/6+vr/+zs7P/t7e3/7u7u/+/v7//w8PD/8fHx//Ly8v/z8/P/9PT0//X19f/29vb/9/f3//j5+P/5+fn/+vr7//v7+//9/P3//v3+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v7+v/6+vn/+fn5//j4+P/39/b/9vX1//T09P/z8/T/8vLy//Hx8f/w8PD/7+/w/+7u7v/t7e3/7Ozs/+vr7P/q6+v/6erp/+np6f/o5+j/5+fn/+bm5v/m5eX/5OXl/+Pk5P/j4+P/4uLi/+Hh4f/g4eH/4ODg/+Dg3//f39//3t7e/93d3f/d3dz/3Nzc/9zc3P/c29v/29vb/9ra2//a2tr/2dnZ/9nZ2f/Z2dn/2dnZ/9nZ2P/Y2Nj/2NjY/9jX2P/X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//Y19f/19fX/9fX1//X2Nj/2NjY/9jY2P/Y2Nj/2dnZ/9nZ2f/Z2dn/2tra/9ra2v/a29v/29vb/9zc2//c3Nz/3N3d/93d3f/e3t7/3t7e/9/f3//g4OD/4eDh/+Hh4f/i4uL/4+Pi/+Pj4//k5OT/5eXl/+bm5v/m5+f/5+jn/+jo6P/p6en/6urq/+vr6//s7Oz/7e3t/+7u7v/v7+//8PDw//Hx8f/y8vL/8/Pz//T09P/19fX/9vb2//f39//4+Pj/+fn5//r7+v/7/Pz//f39//7+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v/+//39/f/8/Pz/+/v7//r6+v/5+fn/+Pj3//f39v/29vX/9PT0//Pz8//y8vL/8fHx//Dw8P/v7+//7u7u/+3t7f/s7Oz/6+vr/+rq6v/q6en/6Ono/+fn5//n5+b/5ubm/+Xl5f/k5OT/4+Pj/+Lj4v/i4uH/4eHh/+Dg4P/f39//3t7f/97e3v/d3d3/3d3c/9zc3P/c3Nv/29vb/9ra2v/a2tr/2dnZ/9nZ2f/Y2Nj/2NjY/9fY1//X19f/19fX/9fX1//X19b/1tbW/9bW1v/V1tb/1tbW/9XW1v/V1tX/1tXW/9XV1f/V1tX/1tbV/9XW1f/W1tX/1tbW/9bW1v/W1tb/1tbX/9fX1//X19f/19fX/9fY1//Y2Nj/2NjY/9nZ2f/Z2dn/2drZ/9ra2v/b2tv/3Nvb/9zc3P/c3dz/3d3d/97e3v/e3t7/39/f/+Dg4P/h4OH/4eHh/+Li4v/j4uP/5OTk/+Tk5P/l5uX/5ubm/+fn5//o6Oj/6enp/+rq6v/r6+v/7Ozr/+3t7f/u7u7/7+/v//Dw8P/x8fH/8vLy//Pz8//09PT/9fX1//b29v/39/f/+Pj4//n6+v/6+/r//Pz7//39/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+//7//f39//z8/P/7+/v/+vr6//n5+f/49/j/9/f3//b19v/09PX/8/Pz//Ly8v/x8fH/8PDw/+/v7//u7u7/7e3t/+zs7P/r6+v/6urq/+np6f/o6Oj/5+fn/+bm5v/l5eX/5OXk/+Tk4//j4+P/4uLi/+Hh4f/h4OD/4N/g/9/f3//e3t7/3d3d/93c3P/c3Nz/29vb/9vb2//a2tr/2drZ/9nZ2f/Z2dj/2NjY/9fY1//X19f/19fX/9bW1v/W1tb/1dbV/9XV1f/V1dX/1NXU/9XU1P/U1NT/1NTU/9TU1P/U1NT/1NTU/9TU1P/U1NT/1NTT/9TU1P/U1NT/1NTU/9TU1P/U1NX/1dXV/9XV1f/V1dX/1tbW/9bW1v/W1tb/19fX/9fX1//Y2Nf/2NjY/9jZ2f/Z2dr/2tra/9ra2v/b29v/3Nzc/9zc3P/d3d3/3t7e/97e3v/f39//4ODg/+Hh4f/i4uL/4uLi/+Pj4//k5OT/5eXl/+bm5v/n5+f/6Ojo/+np6f/q6un/6+vr/+zs7P/s7ez/7u3t/+/v7v/w8PD/8fHx//Ly8v/z8/P/9PT0//X19f/29vb/9/f3//j4+P/5+vr/+/v7//z8/P/9/f3//v7+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f38//v7+//6+vr/+fn5//j4+P/39/f/9vb2//X09f/z8/P/8vLy//Hx8f/w8PD/7+/v/+7u7v/t7e3/7Ozs/+vr6//q6ur/6enp/+jo6P/n5+f/5ubm/+Xl5f/k5OT/4+Pj/+Li4v/h4uH/4OHh/+Dg4P/f39//3t7e/93d3v/d3d3/3Nzc/9vb2//b29v/2tra/9nZ2f/Z2dn/2NjY/9jX2P/X19f/1tbX/9bW1v/W1tb/1dXV/9XV1f/U1NT/1NTU/9TU1P/T09P/09PT/9PT0//T09P/09PT/9LS0v/T09L/0tLS/9LS0v/S0tL/0tLS/9LS0v/T09P/09PT/9PT0//T09P/09TT/9TU1P/U1NT/1NTU/9XV1f/V1dX/1dXV/9bW1v/W1tb/19bX/9fX2P/Y2Nj/2djY/9nZ2f/a2tr/2trb/9vb2//c3Nz/3Nzc/93d3f/e3t7/39/f/9/g4P/g4OD/4eHh/+Li4v/j4+P/4+Tk/+Tl5f/m5ub/5ufm/+jo6P/p6en/6unq/+vq6v/r6+v/7ezs/+7u7f/v7+//8PDw//Hx8f/y8vL/8/Pz//T09P/29fX/9/b2//f39//4+fn/+vr6//v7+//8/Pz//f39//7//v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz7//r6+v/5+fn/+Pj4//f39//29vb/9fX1//P08//y8vL/8fHx//Dw8P/v7+//7u7u/+3t7f/s7Oz/6+vq/+rq6v/p6en/6Ojo/+fn5//m5ub/5eXl/+Tk5P/j4+P/4uLi/+Hh4f/g4eD/3+Df/9/f3//e3d7/3d3d/9zc3P/b29v/2trb/9ra2v/Z2dn/2djY/9jY2P/X19j/19fX/9bW1v/W1tb/1dXV/9TU1f/U1NT/1NTU/9TT0//T09P/0tLT/9LS0v/S0tL/0tLS/9HR0f/R0dH/0dHR/9HR0f/R0dH/0dHR/9HR0f/R0dH/0dHR/9HR0f/R0dH/0dHR/9HR0v/R0tL/0tLS/9LS0v/S0tL/09LT/9PT0//T09P/1NTU/9TV1f/V1dX/1dXW/9bW1v/W1tf/19fX/9jY2P/Y2Nn/2dnZ/9ra2v/a2tr/29vb/9zc3P/d3N3/3d3e/97e3v/f39//4ODg/+Hh4f/i4uL/4uPj/+Pk5P/k5OT/5ebl/+bn5//n5+j/6Ojp/+np6f/r6ur/6+vs/+zs7P/t7u7/7u/v//Dw8P/x8fH/8vLy//Pz8//09PT/9fX1//f29//3+Pj/+fj5//r6+v/7+/v//fz8//39/f/+//7//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/v6//n5+f/4+Pn/9/f3//b29v/19fX/9PT0//Ly8v/x8fH/8PDw/+/v7//u7u7/7e3t/+zs7P/r6+v/6enp/+jp6f/o6Oj/5ubn/+bl5v/k5eT/5OPk/+Pi4//i4uL/4eHh/+Dg4P/f39//3t7e/93d3f/c3Nz/29vb/9vb2//a2tr/2dnZ/9nY2P/Y2Nj/19fX/9fX1//W1tb/1dXV/9XV1f/U1NT/1NTU/9PT0//S0tL/0tLS/9LS0v/S0tH/0dHR/9HR0f/Q0ND/0NDQ/9DQ0P/Q0ND/z9DQ/8/Pz//Pz8//z8/P/8/Pz//Pz8//z8/P/8/Qz//P0ND/0M/Q/9DQ0P/Q0ND/0NDQ/9DR0f/R0dH/0dHR/9HS0v/S0tL/0tLT/9PT0//T09P/1NTU/9TU1P/V1dX/1tXW/9bW1v/X19f/19fY/9jY2P/Z2dn/2tra/9va2v/b3Nv/3Nzc/93d3f/e3t7/39/f/+Dg4P/g4eH/4eHh/+Pi4v/j4+P/5OTk/+Xm5f/m5ub/5+fn/+jo6P/p6en/6urr/+vr6//s7e3/7u7u/+/v7v/w8PD/8fHx//Py8v/z8/P/9PT0//b19v/39/f/+Pj4//n5+f/6+vr/+/v7//z9/P/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v///f3+//z8/P/7+/v/+vr6//n4+f/39/f/9vb2//X19f/09PT/8/Pz//Lx8f/w8PD/7+/v/+7u7v/t7e3/7Ozs/+rr6//q6ur/6ejp/+jn5//m5+f/5eXm/+Xk5P/j4+P/4uPj/+Li4f/h4eD/4ODg/9/f3//e3t7/3d3d/9zc3P/b29v/2tra/9ra2f/Z2dn/2NjY/9fX1//W19f/1tbW/9XV1f/V1NX/1NTU/9PT0//T09P/0tLS/9LS0v/R0dH/0dHR/9DQ0P/Q0ND/0M/Q/8/P0P/Pz8//z8/P/87Pz//Pzs7/zs7O/87Ozv/Ozs7/zs7O/87Ozv/Ozs7/zs7O/87Ozv/Ozs7/zs7O/8/Oz//Pz8//z8/P/8/Pz//Pz8//0NDQ/9DQ0P/R0dH/0dHR/9HR0v/S0tL/09PS/9PT0//U1NP/1NTU/9XV1f/V1tb/1tbW/9fX1//Y2Nj/2NnZ/9nZ2f/a2tr/29vb/9zc3P/d3dz/3d7d/97f3v/f3+D/4ODg/+Hh4f/i4uL/4+Pj/+Tk5P/l5eX/5ubm/+fn5//o6ej/6erp/+rq6v/r6+v/7ezt/+7u7v/v7+//8PDw//Hx8f/y8vL/8/Pz//T09P/29vX/9/f3//j4+P/5+fn/+vv7//z8/P/9/f3//v7+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//Pz8//v7+//6+vr/+fn5//j3+P/29vb/9fX1//T09P/z8/P/8vLy//Hx8f/v7+//7u7u/+3t7f/s7Oz/6+vr/+rq6v/p6en/6Ofo/+fm5v/l5eX/5OXk/+Pj4//i4uL/4uHh/+Hg4P/f39//3t/f/97e3f/d3dz/3Nzc/9vb2//a2tr/2dnZ/9jY2P/Y19j/19fW/9bW1v/V1dX/1dXV/9TU1P/T09P/09PS/9LS0v/R0dH/0dHR/9DQ0P/Q0ND/z8/Q/8/Pz//Pzs//zs7O/87Ozv/Ozc3/zs3N/83Nzf/Nzc3/zc3N/8zMzf/NzM3/zMzM/8zNzP/NzM3/zM3N/83NzP/Nzcz/zczN/83Nzf/Nzc3/zc3O/87Ozv/Ozs7/zs7O/8/Pzv/Pz8//0NDQ/9DQ0P/R0ND/0dHR/9LS0v/S0tP/09PT/9TU1P/U1NT/1dXV/9bW1v/W19b/19fX/9jY2P/Z2dn/2dnZ/9rb2//b29v/3Nzc/93d3f/e3t7/39/f/+Dg4P/h4eH/4uLi/+Pj4//k5OT/5eXl/+bm5v/n5+f/6Ono/+np6f/q6uv/6+zr/+3t7f/u7u7/7+/v//Dw8P/x8fH/8vLy//P08//19fX/9vb2//f39//4+Pn/+vr6//v7+//8/Pz//f39//7+/v///////////////////////////////////////////////////////////////////////////////////////f3///Ly///q6v//5ub//+fn///x8f///f3///7//v/9/f3//Pz8//r6+v/5+fn/+Pj4//f39//29vb/9PX0//Pz8//y8vL/8fHx//Dw8P/u7+//7e3t/+zs7P/r6+v/6urq/+np6f/o5+f/5+bm/+bl5v/l5eX/4+Pj/+Li4v/i4eH/4ODg/9/f4P/e3t7/3d3d/9zc3f/b29v/2tra/9rZ2f/Z2Nn/2NjY/9fX1//W1tb/1dXV/9XV1f/U1NT/09PT/9LS0v/S0tL/0dHR/9DQ0f/Q0ND/z8/P/8/Pz//Ozs//zs7O/87Nzf/Nzc3/zc3N/8zMzP/LzMz/zMvM/8zMzP/Ly8v/y8vL/8vLy//Ly8v/y8vL/8vLy//Lysv/y8vL/8vLy//Ly8v/y8vL/8vLy//MzMz/zMzM/8zMzP/NzMz/zc3N/83Nzf/Ozc3/zs7O/87Pzv/Pz8//0NDP/9DQ0f/R0dH/0tHS/9LS0v/T09P/1NTT/9TU1P/V1dX/1tbW/9bX1//X2Nf/2NjY/9nZ2f/a2tr/29vb/9zc3P/d3d3/3t7e/9/f3//g4OD/4eHh/+Li4v/j4+P/5OTk/+Xl5f/m5ub/5+fn/+jo6P/p6er/6urq/+zs7P/t7e3/7u7u/+/v7//w8PD/8fLx//Lz8//09PT/9fX1//f29v/3+Pj/+fn5//r6+v/7+/v//P38//79/v////////////////////////////////////////////////////////////////////////////n5///Fxf//goL//01N//8uLv//ICD//yQk//9KSv//kpL+/+Xl/f/+/vz/+/v7//n6+f/4+Pj/9/f3//b29v/19fX/8/Pz//Ly8v/x8fH/8PDw/+/u7v/t7e7/7Ozs/+vr6//q6ur/6enp/+fo6P/n5ub/5ubm/+Tk5P/j4+P/4uLi/+Hh4f/g4OD/39/f/97e3v/d3d3/3Nzc/9vb3P/a2tr/2dnZ/9jZ2P/X2Nj/19fW/9bW1v/V1dX/1NTU/9TT0//T0tP/0tLS/9HR0f/Q0ND/0NDQ/8/Pz//Oz87/zs7O/83Ozv/Pzsz/zMzM/8nJzf/Jycz/zMzL/8zNy//Ky8r/ysrK/8rKyv/Kysr/ycnK/8rJyf/Jycn/ycnJ/8nJyv/Jycr/ycnJ/8rKyf/Kysr/ysrK/8rKyv/Kysr/ysvK/8vLy//Ly8v/y8zL/8zMzP/Mzcz/zc3N/83Nzf/Ozs7/zs7O/8/Pz//Q0ND/0NDQ/9HR0f/R0dH/0tPS/9PT0//T1NT/1dXV/9XV1v/W1tf/19fX/9jY2P/Z2dn/2tra/9vb2//c3Nz/3d3d/97e3f/f397/4ODg/+Hh4f/i4uL/4+Pj/+Tk5P/l5eX/5ubm/+fn5//p6Oj/6enp/+vr6//s7Oz/7e3t/+7u7v/v7/D/8PHx//Hy8v/z8/P/9PT0//X19f/39vf/+Pj4//n5+f/6+vr/+/v7//39/f/+/v7/////////////////////////////////////////////////////////////////3d3//2xs/v8aGv//AQH//wAA//8AAP//AAD//wAA//8AAP//BQX//0BA/f+9vfv/+vr6//n5+f/49/f/9vb2//X19f/09PT/8vPz//Hx8f/w8PD/7+/v/+7u7v/t7O3/6+vr/+rq6v/p6en/6Ojo/+fn5//m5ub/5OTl/+Tj5P/j4uL/4eHh/+Dg4P/f39//3t7e/93d3f/c3Nz/29vb/9ra2v/Z2dn/2NjY/9fX1//W1tf/1dXV/9XV1P/U1NT/09PT/9LS0v/R0dH/0dDQ/9DQ0P/Pz8//zs7O/87Ozv/Nzc3/zc3M/8zMzP+mptT/W1vn/zU18f9AQO3/cHDg/6+u0P/Jycn/ycnJ/8jIyf/IyMj/yMjI/8jIyP/IyMj/yMjI/8fIyP/IyMj/yMjI/8jIyP/IyMj/yMjI/8jIyP/JyMn/ycnJ/8nJyf/Jysr/ysrK/8vKyv/Ly8v/y8vL/8zMzP/MzMz/zczN/87Ozf/Ozs7/z8/P/8/Qz//Q0ND/0dHR/9LS0f/T0tP/09PT/9TU1P/V1dX/1tbW/9fX1//Y2Nj/2NnY/9rZ2v/a29v/3Nzb/93c3f/d3d7/39/e/+Dg4P/g4eD/4uLi/+Pj4//k5OT/5eXl/+bm5v/n5+j/6Ojp/+rq6v/r6+v/7Ozs/+3t7f/u7u7/8PDw//Hx8f/y8vL/8/Pz//T09P/29vb/9/f3//j4+P/5+fn/+/v7//z8/P/9/f3////+///////////////////////////////////////////////////////e3v//SUn//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8jI/3/r6/6//j4+P/39/f/9vX2//T09f/z8/P/8vLy//Dx8P/v7/D/7u7u/+3t7f/s6+z/6uvr/+np6f/o6Oj/5+fn/+bm5v/l5eT/4+Pk/+Li4v/h4eH/4ODg/9/f3//e3t7/3d3d/9zc3P/b29v/2tra/9nZ2f/Y2Nj/19fX/9bW1v/V1dX/1NTU/9PT0//T09L/0tLS/9HR0f/Q0ND/z8/P/8/Pz//Ozs7/zc3N/8zMzP/MzMz/ysrL/4qK2/8hIfb/AAD//wAA//8AAP//AQH+/ykp8/+TlNX/yMjH/8vLy//Ky8v/x8fH/8bGxv/Gxsb/xsbG/8bGxv/Gxsb/xsbG/8bGx//Hx8b/x8fH/8fHx//Hx8f/x8fH/8fIyP/IyMj/ycnI/8nJyf/Jycn/ysrK/8rLyv/Ly8v/y8zM/8zMzP/Nzc3/zs3O/87Ozv/Pz8//0NDP/9DQ0P/R0dH/0tLS/9PT0//U1NT/1dXV/9bV1v/X1tb/19fX/9jZ2f/Z2tr/2trb/9vb2//c3dz/3t7e/9/f3//g4OD/4eHh/+Li4v/j4+P/5OTk/+Xl5f/m5ub/5+jo/+np6f/q6ur/6+vr/+zs7P/u7e7/7+/v//Dw8P/x8fH/8vPy//T08//19fX/9vb2//f4+P/4+fn/+vr6//v7+//8/P3//v7+//////////////////////////////////////////////////n5//90dP7/AQH//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//JCT9/7W1+P/39/b/9fX1//Pz9P/y8vL/8fHx//Dv8P/v7u7/7e3t/+zs7P/r6+r/6erp/+jo6P/n5+f/5ubm/+Xl5f/k5OP/4uLi/+Hh4f/g4OD/39/f/97e3v/d3d3/3Nzc/9rb2//a2tr/2dnZ/9jX1//X19f/1tbW/9TV1f/U1NT/09PT/9LS0v/R0dH/0NDQ/8/Q0P/Pz8//zs7O/83Nzf/MzMz/zMzL/8vLy//MzMr/i4va/xcX+f8AAP//AAD//wAA//8AAP//AAD//wAA//8nJ/P/vr7f//Ly8P/y8vL/5eXl/9DQ0P/FxcX/xcXF/8XFxf/FxcX/xcXF/8XFxf/FxcX/xsbF/8XFxf/Gxsb/xsbG/8bGxv/Hx8f/x8fH/8jHx//IyMj/ycjJ/8nJyf/Kycn/ysrK/8vLy//LzMz/zMzM/83Nzf/Ozs3/zs7O/8/Pz//Q0ND/0dHR/9LS0f/T09P/09PU/9TU1P/V1dX/1tbW/9fX1//Y2Nj/2dnZ/9ra2v/b3Nz/3d3d/97e3f/f39//4ODg/+Hh4f/i4uL/4+Pj/+Tk5P/l5uX/5ufn/+jo6P/p6en/6urq/+vr6//t7O3/7u7u/+/v7//w8PD/8fLy//Pz8//09PT/9fX1//f39//4+Pj/+fn5//v6+//8/Pz//f39//7+/v///////////////////////////////////////////+np//8rK///AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//y0t/f/Cw/b/9vX0//Ly8//x8fH/8PDw/+/v7//u7e3/7Ozs/+vr6//q6ur/6Ojp/+jn5//m5ub/5eXl/+Tk5P/i4+P/4eHi/+Dg4P/f4N//3t7e/93d3f/c3Nz/29vb/9ra2v/Z2dn/19jX/9bW1v/W1tX/1dTV/9TU1P/T09P/0dLR/9HR0f/Q0ND/z8/P/87Ozv/Ozc7/zczM/8zMzP/Ly8v/ysrK/8vLyf+goNT/ISH2/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8jI/7/1dX9//////////////////X19f/S0tL/w8PD/8PDw//Dw8P/w8PD/8TDw//Ew8T/xMTE/8TExP/ExMT/xMTE/8XFxf/FxcX/xcbF/8bGxv/Hxsb/x8fH/8jIyP/IyMj/ycjJ/8rJyf/Kysr/y8vL/8zLzP/MzM3/zc3N/87Ozv/Pz8//z9DQ/9HQ0f/R0dL/0tPS/9PT0//U1NT/1dXV/9bW1v/X19f/2NjY/9nZ2v/a2tr/29zb/93d3P/e3t7/39/f/+Dg4P/h4eH/4+Li/+Pj4//k5eX/5ubm/+fn5//o6Oj/6enp/+vq6v/s7Oz/7e3t/+7u7v/w7/D/8fDx//Ly8v/z8/P/9PX0//b29v/39/f/+Pj4//r6+v/7+/v//fz8//7+/v///////////////////////////////////////////+zs//81Nf7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//89Pfz/09P0//T08v/w8PH/7+/v/+7u7v/t7e3/6+vr/+rq6v/p6en/6Ofo/+bm5//l5eb/5OTk/+Pj4//h4eH/4ODg/9/f3//e3t7/3d3d/9zc3P/b29v/2tna/9nY2f/Y2Nf/1tfX/9XV1f/U1NT/09TU/9LT0//R0dL/0NDQ/9DQz//Pz8//zs7O/83Nzf/MzMz/zMvL/8vLy//Kycr/ysrI/7m5zP89Pe3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//9RUf//9fX////////////////////////p6en/w8PE/8LCwv/CwcL/wsLC/8LCwv/CwsL/wsLC/8LCwv/Dw8P/w8PD/8PDw//DxMT/xMTE/8XFxP/FxcX/xcXF/8bGxv/Hx8f/x8fH/8jIyP/JyMn/ysnJ/8rKyv/Ly8v/zMzM/83Nzf/Nzc3/zs7O/8/Pz//Q0ND/0dHR/9LS0v/T09P/1NTU/9XV1f/W1tb/19fX/9jY2P/Z2dn/2tra/9vb2//c3d3/3d7e/9/f3//g4OD/4eHh/+Pj4v/k5OT/5eXl/+bm5v/n5+f/6Ojp/+rp6v/r6+v/7Ozs/+7t7f/v7+//8PDw//Hx8v/y8vL/9PT0//X19f/29vb/+Pj3//n5+f/6+vr//Pz7//39/f/+/v7///////////////////////////////////////39//+pqf7/Ly/+/wUF//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//XVz5/+Xk8v/w8fD/7u7u/+3t7f/s7Oz/6+rq/+np6f/o6Oj/5+fn/+bm5v/k5OT/4+Pj/+Li4v/h4eH/3+Df/97f3v/d3d3/3Nzc/9vb2//a2tr/2djZ/9fY1//X19f/1tbV/9TU1P/T09P/0tPS/9HR0f/Q0ND/z8/P/87Pzv/Ozc7/zc3N/8zMzP/Ly8v/ysrK/8nJyf/Jycj/yMfH/29v3/8FBf3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//9sbP7////////////////////////////q6ur/wsLC/8DAwP/AwMD/wcHB/8HAwP/AwcH/wcHB/8HBwf/BwsH/wsLB/8LCwv/CwsL/w8PC/8PDw//ExMT/xMTE/8XFxf/Gxcb/xsbG/8fHx//HyMf/yMnI/8nJyf/Kysr/y8vK/8vMy//MzMz/zc3N/87Ozv/Pz8//0NDQ/9HR0f/S0tL/09PT/9TU1P/V1dX/1tbW/9fX1//Y2Nj/2dnZ/9ra2v/b29v/3d3d/97e3v/f39//4ODg/+Lh4f/j4uP/5OTk/+Xl5f/m5ub/5+fn/+np6f/q6ur/7Ovr/+3s7P/u7u7/7+/v//Dx8f/y8vH/8/Pz//X09P/19vb/9/f3//j4+P/5+vn/+/v7//z8/P/+/v3////////////////////////////////////////////9/f//39///6qq/v90dP7/MzP+/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//CQn+/4aG9v/t7e//7u7t/+zs7P/r6+v/6urp/+jo6P/n5+f/5ubm/+Xl5P/j5OP/4uLi/+Hh4f/g4OD/3t/f/93d3f/c3Nz/29vb/9ra2v/Z2dn/2NjY/9bX1//V1db/1NTV/9PT0//S0tL/0dHR/9DQ0P/Pz8//z87O/83Nzf/NzMz/zMvM/8vLyv/Kysr/ycnJ/8jIyP/Jycf/paXP/x8f9v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wQE//+Li/////////////////////////7+/v/d3dz/vr6+/7++v/+/v7//v7+//7+/v/+/v7//v7+//8DAwP/AwMD/wMDA/8DBwP/BwcD/wcHB/8LCwv/CwsP/w8PD/8PExP/ExMT/xMXE/8XFxf/Gxsb/x8fH/8jIx//IyMj/ycnJ/8rKyv/Ly8z/zMzN/83Nzv/Ozs//0NDQ/9DR0f/R0tL/0tPS/9PT0//U1NT/1dXV/9bW1v/X19f/2NjY/9nZ2f/b29r/3Nzc/93d3f/e3t7/39/f/+Hg4f/i4uL/4+Pj/+Tk5P/m5eX/5+fn/+jo6P/q6en/6+rq/+vs7P/t7e3/7u7u/+/w8P/x8fH/8/Ly//Tz9P/19fX/9vb2//f49//5+fn/+vr6//z7+//9/f3//v7+////////////////////////////////////////////////////////////0dH//zEx//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//xwc/f+ysfL/7u7t/+zs6//q6ur/6enp/+jo6P/m5uf/5eXl/+Tk5P/j4+P/4eLi/+Dg4P/f39//3t7e/93d3P/b29v/2tra/9nZ2f/Y2Nj/1tfX/9bW1v/U1NT/09PT/9LS0v/R0dH/0NDQ/8/Pz//Ozs7/zc3N/8zMzP/Ly8v/ysrK/8nJyf/IyMn/yMjH/8fHx//Excb/W1vj/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//woK//+mpv////////////////////////n5+f/Kysr/vb29/729vf+9vb3/vb29/729vv+9vb7/vr6+/76+vv++vr7/v76//7+/v//Av7//wMDA/8DBwP/BwcH/wcHB/8LCwv/Dw8P/w8PD/8TExP/FxcX/xcXG/8bHxv/Hx8f/yMnJ/8rLzP/Jycn/x8TC/8bBvf/Fv7v/xr+6/8bAuv/Iwr3/ysbB/87KyP/S0ND/1dbX/9bX2P/X1tf/2NfX/9nY2f/a2dr/29vb/9zc3P/d3d3/3t7e/+Dg4P/h4eH/4uLi/+Pj4//l5eX/5ubm/+fn5//o6Oj/6enp/+vr6//s7Oz/7e7u/+/v7//w8PD/8fLx//Pz8//09PT/9fX1//b39//4+Pj/+fr5//v7+//8/Pz//v7+/////////////////////////////////////////////////////////////////7a2/v8eHv//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//9AQPn/1tbt/+3t6v/p6en/6Ojo/+fn5//m5ub/5OTk/+Pj4//i4uL/4OHg/9/f3//e3t7/3d3d/9vb3P/a2tr/2dnZ/9jY2P/X19f/1tbW/9TV1f/T09T/0tLS/9HR0f/Q0ND/z8/P/87Ozv/Nzc3/zMzM/8vLy//Kysr/ycnJ/8jIyP/Hx8f/xsbG/8fHxf+jo87/Gxz2/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//xAQ/v+9vfz//////////////////////+3t7f/AwMD/u7u7/7y8vP+8vLz/vLy8/7y8vP+8vLz/vby8/729vP+9vb3/vb29/769vv++vr7/vr6+/7+/v//Av7//wMDA/8HBwf/BwsH/wsLC/8PDw//Dw8T/xcXG/8bHx//Ew8L/vLKp/66Yhf+igGX/l2lF/45ZL/+ITh//hUgY/4VIGP+ITR//jlgt/5doQv+ifV//sZWA/8CxpP/Py8j/19fX/9na2v/Z2dr/2tra/9vb2//c3N3/3d3d/9/f3//g4OD/4eHh/+Li4//k5OT/5eXl/+bm5v/n6Oj/6enp/+rq6v/r6+z/7O3t/+7u7v/v7+//8fHx//Ly8v/z8/P/9fX1//f29v/49/j/+fn5//r6+v/8+/v//f39///+/v////////////////////////////////////////////////////////////39/v+bm/3/EBD+/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8DA///dnX0/+fn6v/p6en/5+jn/+bm5v/l5eX/4+Tj/+Li4v/h4eH/3+Dg/9/e3v/d3d3/3Nzc/9rb2//a2tn/2djY/9fX1//W1tb/1NTV/9PU1P/S0tP/0dHR/9DQ0P/Pz8//zs7O/83Nzf/MzMz/y8vL/8rKyv/Jycn/yMjI/8fHx//Gxsb/xcXF/8LCxf9gYOH/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//y4u9P/d3fT//////////////////////+Dg4P+7u7v/urq6/7q6uv+6urr/urq6/7q7uv+6u7v/uru7/7u7u/+7u7z/vLy8/7y8vP+8vbz/vb29/769vf++vr7/vr+//7+/wP/AwMD/wcHA/8HCwv/Cw8T/vbez/6yWhP+Vakb/h0we/388B/97NQD/ezUA/3s2AP97NgD/ezYA/3s2AP97NgD/ezYA/3s1AP97NQD/fDgC/4RGFf+QXDH/p4Ro/8Gxpf/Tz8z/2tvb/9vb2//c29z/3d3d/97e3v/f39//4eHg/+Hh4v/j4+P/5OXk/+bm5v/n5+f/6Ojo/+nq6v/q6+v/7Ozs/+7t7f/v7+7/8PDw//Hx8f/z8/P/9PT0//b19f/39/f/+Pj4//r5+v/7+/v//Pz8//7+/v/////////////////////////////////////////////////////////+//7+/v/39/z/fH38/wUF/v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Fhb8/6qq7v/p6uj/5+fm/+Xl5f/k5OT/4uPi/+Hh4f/g4OD/39/f/97e3f/c3dz/29vb/9ra2v/Z2dn/19fX/9bW1v/V1dX/09TU/9LT0v/R0dH/0NDQ/8/Pz//Ozs7/zc3N/8zMzP/Ly8v/ysrK/8nJyP/HyMf/x8bG/8bFxv/FxcX/xcXE/6moy/8fH/X/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Dg75/4OE1f/w8PD//////////////////////9fX1/+4uLj/ubm5/7m5uf+5ubn/ubm5/7i5uf+5ubn/ubm5/7q5uf+6urr/urq6/7q7u/+7u7v/u7y7/7y8vP+9vb3/vb2+/76+vv+/v7//wMDB/726uP+pkn//jlsz/347Bv97NgD/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP97NQD/fDYA/4NDEP+YaEP/t5+L/9LMyP/b29z/3Nzc/93d3f/f3t7/4ODf/+Hh4f/i4uL/4+Pj/+Xl5f/m5ub/5+jn/+np6f/q6ur/7Ovr/+zt7f/u7u7/8O/v//Hx8f/y8vL/8/Tz//X19f/29vb/+Pj4//n5+f/6+vr/+/z8//39/f/+//7//////////////////////////////////////////////////v7+//39/f/9/fz/5ub6/1BQ/P8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//zw8+P/Pz+n/6Ojm/+Xk5P/j4+P/4uLi/+Hg4f/f39//3t7e/93c3f/b3Nz/2tvb/9nZ2f/Y19j/1tbW/9XV1f/U1NT/09PT/9LR0v/R0dD/z9DP/87Ozv/Nzc3/zMzM/8vLy//Kysr/yMnJ/8jIyP/Hx8f/xsXF/8TExP/ExMT/xMTC/25u2/8EBP7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8CAv7/WFjd/7u7wP/x8fD//////////////////v7+/9LS0v+2trb/t7e4/7e3t/+3t7f/t7e3/7e3t/+3uLj/uLi4/7i4uP+4ubj/ubm5/7m5uf+5urr/urq6/7u7u/+7u7v/vLy8/729vf++v7//tayk/5ZsS/9/Pgr/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP97NQD/gD0J/5RhOP+4oI3/1dLP/93e3//e3t7/39/f/+Dg4P/h4eH/4uLj/+Tk5P/l5eX/5+bn/+jo6P/p6en/6+vq/+zs7P/t7e3/7+/v//Dw8P/x8fH/8/Pz//T09P/29fX/9/f3//j4+P/6+vn/+/v7//38/P/+/v7//////////////////////////////////////////////////v7+//z9/P/7+/v//Pz6/8nJ+f8qKv3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wMD/v9sbPL/4OHl/+bm5P/k4+L/4uLh/+Dg4P/f397/3d3d/9zc3P/b29v/2dnZ/9jY2P/X19f/1dXW/9TU1P/T09P/0tLS/9HR0f/P0ND/zs7O/83Nzf/MzMz/ysvL/8nKyv/Jycn/yMfI/8bGx//FxcX/xcTE/8PDw//ExML/sbLG/zEx7/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//80NOr/pqa+/7+/vf/w8PD//////////////////f39/8/Pz/+1tLX/trW1/7a1tf+2trX/tra2/7a2tv+2trb/tre2/7e3tv+3t7f/t7e3/7i3t/+4uLj/ubm5/7m5uf+6urr/u7u6/7u8vP+vopj/i1gv/3w2AP98NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s1AP+APgr/mmtG/8S0p//b29r/39/f/9/f4P/g4OD/4uLi/+Pj4//l5OX/5ubm/+fn5//o6en/6urq/+vr6//t7e3/7u7u//Dw7//x8fH/8vLy//Tz9P/19fX/9/f2//j4+P/5+fn/+vr6//z8/P/9/f3///7///////////////////////////////////////////7//f39//z8/P/7+/v/+fn5//j49/+fn/n/EBD+/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8REP3/fX3w/8C/5//Pz+T/1tXi/9zc3//h4d3/4ODc/93d2v/b29r/2dnY/9fX1//W1tb/1dXV/9PT1P/S0tL/0dHR/9DQ0P/Oz8//zc3N/8zMzP/Ly8v/ysrK/8nJyf/IyMj/xsbH/8bFxv/ExcX/w8PE/8LCwv/Dw8D/goLU/wcH/P8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//xMT9/+Kisj/uLi2/7y8vP/w8PD//////////////////f39/83Nzf+zs7P/tLS0/7S0tP+0tLT/tLS0/7S0tP+0tbT/tbW1/7W1tf+1tbX/tra2/7a2tv+3t7f/t7e3/7i4uP+4ubn/urq7/7Cmnv+KViz/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NgD/ezUA/4ZIF/+ti3D/1dDL/9/g4f/g4OD/4eHh/+Pj4v/k5OT/5eXl/+bn5v/o6Oj/6enp/+vr6//s7Oz/7e3t/+/v7//w8PD/8vLx//Pz8//09PT/9vb2//j39//5+Pn/+vr6//v8+//9/fz//v7+///////////////////////////////////////+/v7//f39//z7+//6+vr/+Pj5//f49//w8Pb/bm75/wEB//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Bwf+/xUV/P8pKfn/R0j0/2Zm7/+Cgur/mprl/7Cw4f/Gxtz/1NTY/9bW1//W1tX/19fT/9XV0v/T09H/0dHQ/8/Pz//Ozs7/zc3M/8vLy//Kysr/ycnJ/8jIyP/Gx8f/xcbG/8XFxP/ExMP/wsLC/8LBwf+6usL/Pz/p/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//1BQ3v+zsrf/tra1/7u7u//x8PD//////////////////f39/8zMzP+xsbH/s7Oz/7Kzs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7S0tP+0tLT/tbS0/7W1tf+1trX/tra2/7e3tv+3uLj/tbOx/5NqSf98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP99OgX/mmpE/8u+s//f4OD/4OHh/+Li4v/j4+P/5eXk/+bm5v/n5+f/6Ojp/+rq6v/s6+v/7e3t/+7u7v/v8O//8fHx//Ly8v/z9PT/9fX1//f29//4+Pj/+vn5//v7+//8/Pz//v7+///////////////////////////////////////+/v7//Pz8//v7+//5+fr/+Pj4//b39v/39/X/2dn0/0FB+/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8BAf//Cwv9/xoa+v8pKff/PT3z/1tb7f96eub/mJjf/6ys2v+7u9X/ysrQ/9HRzf/Pz8z/zc3L/8vLyv/Kysn/yMjI/8fHx//Gxcb/xMTE/8PDw//CwsL/wcLB/8LCv/+Xlsz/FRX4/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//FRX2/5CQw/+3t7T/tLS0/7q6uv/x8fH//////////////////Pz8/8vLy/+wsLD/sbGx/7Gxsf+xsbH/sbGx/7Gysf+ysbL/srKy/7Kysv+zs7P/s7Oz/7Ozs/+0tLT/tbS0/7W1tf+3t7j/ppSF/38/DP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP98NgD/ezYA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s2AP97NgD/fDYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/4xTJv++qJf/397d/+Li4v/j4uL/5OTk/+bl5f/m5uf/6Ojo/+np6f/r6+v/7Ozs/+7u7v/v7+//8PDx//Ly8v/z8/P/9PX1//b29v/3+Pf/+fn5//r7+v/8/Pz//f39//7+//////////////////////////////7////9/v7//Pz7//r6+v/5+fn/9/j4//b29v/19fX/9vbz/7m59P8gIP3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8BAf//BAT+/xUV+v8uLvT/R0fu/2Rk5v+EhN3/pqbU/7u7zv/ExMn/ysrG/8jHxf/FxcX/w8PD/8LCwv/BwcH/wMDA/7+/v/9mZtz/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Skrf/7Kytf+0s7P/s7Ky/7m5uf/y8vL//////////////////Pz8/8rKyf+ur67/r7Cw/7CwsP+wsLD/sK+w/7CwsP+wsLD/sLCx/7Gxsf+xsbH/srKx/7Kysv+ysrP/s7Oz/7S0tP+0tLT/lW9R/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NQD/fDgC/4BADP+ITyH/k2VB/5x4W/+igmn/pYhy/6WHb/+igGb/nHZX/5JiPP+ITiD/gUAN/3w4Av97NQD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s1AP+ERRP/tZiB/97c2//i4+P/4+Pj/+Xl5f/m5ub/5+jo/+np6f/q6ur/7Ovs/+3t7f/u7u//8PDw//Hx8f/z8/L/9PT0//b29f/39/f/+Pn4//r6+v/7+/v//Pz9//7+/v////////////////////////////7+/v/9/f3/+/v7//r6+v/5+Pj/9/f3//X19v/09PT/8/Pz//Dw8f+Kivb/CQn+/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wEB//8ICP3/EhL6/ywr8/9TU+f/f3/a/6enzf/AwMT/w8PC/8PDwf/CwsD/w8O+/7Ozwv8xMe3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8ODvn/h4fF/7W1sv+ysrL/sbGx/7i4uP/y8vL//////////////////Pz8/8jIyP+tra3/rq6v/66urv+urq7/rq6u/66urv+vr6//r6+v/6+vr/+wsLD/sLCw/7GxsP+xsbH/srKy/7Ozs/+ysrH/i1oz/3s1AP98NwD/fDcA/3w3AP97NgD/fDYA/38+Cv+MWDD/nHlf/62cjv+4sqz/vbq4/8C/v//Cw8T/xcbH/8bGx//Gxsb/xcTD/8TAvv/Cu7b/tqSW/6OBZv+RXzf/gD8L/3s2AP97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NgD/gUAN/7CPdf/e3Nr/4+Tk/+Tk5P/l5eX/5+fn/+jo6P/p6ur/6+vr/+3s7f/u7u7/7+/v//Dx8f/y8vL/9PT0//X19f/29vf/+Pj4//n5+f/7+/v//Pz8//79/f////////////////////////////79/v/8/Pz/+/v7//r6+f/4+Pj/9/f3//X19f/z8/T/8vLy//Ly8f/j5PD/WFj4/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Bgb9/x0d9v9BQer/amrd/3V12P97e9X/jo7O/3l51P8MDPr/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//87O+X/qqq1/7Kysf+xsbD/sK+w/7e2t//z8/P/////////////////+/v7/8bGxv+rq6v/rayt/62trf+tra3/ra2t/62trf+tra3/rq6t/66urv+urq7/r6+v/6+vr/+wsLD/sLGw/7Gxsf+xsK//ilYu/3s1AP98NwD/fDYA/3w4Av+ESBn/lGpK/6iVh/+1sKz/vLy9/72+v/++vr//v7/A/8DAwP/BwcH/wsLC/8TExP/FxcX/xsbG/8jIyP/Jycr/y8vM/8zMzf/Gwr7/tqOV/5xxUP+ERhX/ezYA/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/4E/C/+vjXL/3tza/+Tk5f/l5eX/5ubm/+jo6P/p6en/6+rq/+zs7P/t7e3/7+/u//Dw8P/x8vL/8/Pz//X09f/29vb/+Pf4//n5+f/6+vr//Pz8//39/f/////////////////////////+//79/f/8/Pz/+vr6//n5+f/4+Pj/9vb2//X19f/z8/P/8fLx//Dw8P/y8e//xsbw/yoq+/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AQH//wEB//8BAf7/Bwf8/w4O+f8BAf7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wcH+/91dcv/s7Ow/7CwsP+wsLD/rq6u/7W1tv/09PT/////////////////+/v7/8TFxP+qqqr/q6ur/6urq/+rq6v/q6ur/6urq/+srKz/rKys/6ysrP+tra3/ra2t/62urv+urq7/r6+v/7CwsP+wsK//kWhI/3w2AP9+PQj/iFIo/5t7Y/+soJf/trW1/7m6uv+6urv/urq6/7y7u/+9vb3/vr6+/7+/v//AwMD/wsLC/8PCw//ExMT/xcXF/8bGx//IyMj/ycnJ/8rLy//Mzc3/zs/P/8zLyv+7q57/m3BN/4FADf97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP+APQr/r41y/9/d3P/l5eb/5ubm/+fn5//p6ej/6urq/+vr6//t7ez/7u7u//Dw8P/x8fH/8vPy//T09P/19fX/9/f3//j4+P/6+vr/+/v8//38/f///////////////////////v/+//39/f/7/Pv/+vr6//j4+P/3+Pf/9fb2//T09P/z8/P/8fHx//Dw8P/v7+7/7u7t/5aW8v8MDP7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//yUl7v+fn7f/sbGv/6+vr/+urq7/ra2t/7W1tf/19fX/////////////////+vr6/8LDw/+oqKn/qqqq/6qqqf+qqqr/qqqq/6qqqv+qqqr/qqqq/6urq/+rq6v/rKys/6ysrf+tra3/rq6u/66vr/+vsLD/ppqR/5Z0Wf+ginn/rqij/7S0tP+2trb/tra2/7e3t/+4uLj/ubq5/7u6uv+8vLz/vb29/76+vv/Av7//wcHA/8LCwv/Dw8P/xcTE/8bGxv/Hx8f/yMjI/8nKyv/Ly8v/zczM/83Ozf/Q0dH/zcrI/7Sdi/+NViv/fDcB/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NgD/gT8L/7SWff/i4uH/5ubm/+fn5v/o6Oj/6unq/+vr6//t7Oz/7u7u/+/v7//x8fD/8vLy//T09P/19fX/9vb2//j4+P/5+fn/+/v7//z8/P///////////////////////v7+//38/P/7+/v/+fr6//j4+P/39/f/9fX1//T08//y8vL/8fHx/+/w7//u7u7/7e3t/9/f7P9QUPf/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//1lY1v+urrD/r6+u/66trv+tra3/rKus/7S0tP/29vb/////////////////+fn5/8HBwf+np6f/qKio/6ioqP+oqKj/qKio/6ioqP+pqaj/qamp/6mqqf+qqqr/qqur/6urq/+srKz/rK2t/62trv+urq7/r7Cw/7Cysv+xsrP/srKz/7Ozs/+0tLT/tbW1/7a2tv+3t7f/ubi4/7q5uv+7u7v/vLy8/729vf++vr7/wL/A/8HBwf/CwsL/xMTE/8XFxf/Gxsb/x8jI/8nJyf/Kysr/y8zM/83Nzf/Ozs7/0NDQ/9LS0v/GvLX/n3VU/388CP97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/4RFE/++ppL/5OTk/+bn5//o6Oj/6enp/+vr6//s7Oz/7e3t/+/v7//w8PD/8fLy//Pz8//09fX/9vb2//f4+P/5+fn/+/v7//z8/P///////////////////////v7+//z8/P/7+/v/+fn5//j4+P/29vf/9fX1//P08//y8vL/8fHw/+/v7//u7u7/7Ozs/+3s6/+4uO3/Hx/7/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8BAf//AQH//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Dw/4/4SDwv+wsK3/ra2t/62srP+sq6v/qqqq/7S0tP/39/f/////////////////+Pj4/76+vv+mpqb/p6en/6ampv+np6b/p6an/6emp/+np6f/p6io/6ioqP+pqaj/qamp/6qqqv+rqqr/q6ur/6ysrP+tra3/rq6u/6+urv+vsLD/sbGx/7Kysv+zs7P/tLS0/7W2tf+2trb/t7e3/7m5uf+6urr/u7u7/7y8vP+9vr7/v7+//8DBwP/CwsL/w8PD/8TExP/FxcX/x8fH/8nIyP/Kycn/y8vL/8zMzf/Ozs7/z8/P/9DR0f/T09T/z8vJ/6qJb/+CQhD/ezYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s1AP+ITBz/yLan/+fn5//n5+f/6eno/+rq6v/s7Oz/7e3t/+7u7v/w8PD/8fHy//Pz8//09PT/9vb2//f39//5+fn/+vr6//v8/P///////////////////////f39//z8/P/6+vr/+fn5//f39//29vb/9fT1//Pz8//y8vL/8PDw/+/v7//t7e3/7Ozs/+rq6//o6On/goLx/wYG/v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8FBf3/S0vv/19f6/9RUe7/Q0Pw/ysr9f8MDPz/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Jyfs/6Ghs/+trq3/rKys/6urq/+qqqr/qamp/7S0tf/39/f/////////////////9/f3/7y8vP+kpKT/paWl/6Wlpf+lpaX/paWl/6alpf+mpqb/pqam/6enp/+np6f/qKio/6ipqP+pqan/qqqq/6urqv+sq6z/rayt/66urf+urq7/sLCw/7Gxsf+ysrL/s7Oz/7S0tP+1trX/tra2/7i4uP+5ubn/urq6/7u8vP+9vb3/vr++/7/Av//BwcH/wsLC/8PExP/FxcX/xsbG/8jHyP/Jycn/ysrK/8zMzP/Nzc3/z87O/9DQ0P/R0dH/09PU/9LQz/+yl4L/g0MR/3s2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NQD/kVwx/9bMxP/o6On/6Ojo/+rq6v/r6+v/7e3t/+/u7v/w8PD/8fHx//Py8v/09PT/9fb1//f39//4+Pj/+fr6//v7+//////////////////+/v7//f39//v7+//6+vr/+Pn5//f39//29vX/9PT0//Pz8//x8fH/7/Dw/+7u7v/t7e3/7Ovs/+rq6v/q6uj/19fo/0lJ9v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Wlrs/9LS1P/T09L/ycnT/7m51f+cnNr/bGzk/zw87/8fH/b/Cwv8/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//U1TX/62trf+srKz/qqur/6qqqv+pqan/qKin/7W1tf/39/f/////////////////9vb2/7m5uf+joqP/pKSk/6OkpP+ko6P/o6Ok/6SkpP+kpKT/paWk/6Wlpf+lpqb/pqam/6enp/+oqKj/qaip/6qqqf+qqqr/rKur/62srP+tra3/rq+v/7CwsP+wsbH/srKy/7Szs/+0tLX/tra2/7e3t/+4uLj/ubm6/7u7u/+8vLz/vb6+/7+/v//AwMD/wcLB/8PDw//ExMT/xcbG/8fHx//IyMj/ysrK/8vLy//MzMz/zs7O/8/Pz//R0dH/0tLS/9PU1P/U09L/sZV//4JBD/97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcB/6R5V//g3dr/6Onp/+np6f/r6+r/7Ozs/+7u7v/v7+//8PHx//Ly8v/08/T/9fX1//b29v/4+Pj/+vr5//v7+//////////////////+/v7//f39//v7+//6+vr/+Pj4//f39//19fX/9PT0//Ly8v/x8fH/8O/v/+7u7v/s7O3/6+vr/+rp6v/o6Oj/6enm/7S06v8fH/v/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//EBD8/5aW4P/V1NL/0tLQ/9HRz//Q0c3/zc3N/8bGzP+trdH/jY7Y/21t3/9JSen/Jibz/w4O+v8EBP7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8LC/n/g4PA/66uq/+rq6v/qqqq/6mpqf+oqKj/pqam/7a2tf/4+Pf/////////////////9fX1/7a2t/+hoaH/oqKi/6Kiov+ioqL/oqKi/6Kiov+jo6P/o6Oj/6Sjo/+kpKT/paWl/6ampv+mpqf/p6eo/6ioqP+pqan/qqqq/6urrP+trKz/rq2t/6+ur/+wsLD/sbGx/7Kysv+ztLT/tbW1/7a2tv+3uLf/ubm5/7q6uv+7u7v/vby9/76+vv+/wL//wcHB/8LCwv/Dw8T/xcXF/8bGxv/IyMj/ycnJ/8vLy//MzMz/zc3N/8/Pz//Q0ND/0tLS/9PT0//V1db/1NPS/66Pdv+APgv/fDYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDYA/388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AP98NwD/fDcA/3w3AP98NwD/ezYA/7+kj//v8PH/7u7u/+/v7//x8fH/8vLz//T09P/29vb/9/f3//j5+P////////////39/f/8/Pz/+/r6//n5+f/3+Pj/9vb2//X19f/z8/P/8fHx//Dw8P/u7u//7e3t/+vr6//q6ur/6enp/+fn5//m5eX/5OTk/+Li4v/h4eH/39/g/97e3v/c3Nz/29vb/9nZ2f/Y2Nj/19jW/8rL1/9VVu3/AgL//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8BAf//Wlrj/7+/w//CwsH/wMDA/76+vv+/v7z/np7F/xsb9P8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//0dH3P+np6z/qamp/6ioqP+mpqb/paSk/6Ojo/+ioaL/oKCg/5+env+dnZ3/mpqa/8zMzP/+/v7////////////////////////////+/v7/9/f3/+Hh4f/AwMD/o6Oj/5KSkv+RkZH/k5OT/5WVlf+Wlpb/mJiY/5mamv+bm5v/nJyc/56env+foJ//oaGh/6Oiov+kpKT/pqWm/6enp/+oqKn/qqqq/6yrrP+tra3/rq+u/7CwsP+ysrL/s7Oz/7S1tP+2trb/t7i4/7m5uf+6urv/vLy8/76+vf+/v7//wcHA/8LCwv/Dw8T/xcXF/8fHx//IyMj/ysrJ/8vLy//Nzc3/zs7O/9DQ0P/R0dH/09PT/9TV1P/W1tb/2NfX/9nZ2f/a2tr/3d7e/9fT0P+bbEf/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fTkC/8Kplf/v8PH/7u7u//Dv8P/x8fH/8vLz//T09P/19fX/9/f3//j4+P////////////79/f/8/Pz/+/r6//n5+f/39/j/9vb2//T09P/z8/P/8fLx//Dw8P/u7u//7e3t/+vr6//q6ur/6ejo/+fn5//m5eX/5OTk/+Li4v/h4eH/39/f/97e3v/c3Nz/29vb/9nZ2f/Y2Nj/1tbW/9bX1f+5utj/NDTz/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Dw/6/4aF1P/CwsD/wMDA/76+vv++vrz/cnLV/wIC/v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//CAj7/3R0xv+tran/qamp/6eop/+mpqb/pKWl/6Ojo/+ioaH/oKCg/5+fn/+dnZ3/mpqa/87Ozv/////////////////////////////////////////////////9/f3/8PDw/9XV1P+zs7P/nZ2d/5SUlP+WlZb/mJiY/5qZmf+bm5v/nJyc/56env+fn5//oaGh/6Kiov+kpKT/paWl/6enp/+oqKj/qqqq/6urrP+tra3/rq+u/7CwsP+xsrL/s7Oz/7S1tP+2trb/uLi4/7m5uf+6urv/vLy8/72+vf+/v7//wMHB/8LCwv/Ew8T/xcXF/8fHx//IyMj/ycrJ/8vLy//Mzcz/zs7O/9DQ0P/R0dH/09LS/9TV1f/W1tb/2NjY/9na2v/b3Nz/0svF/6eCZP9/PAf/fDcA/3w3AP98NwD/fDcA/3w3AP97NgD/g0IP/8y4qP/u7/D/7u7u//Dv7//x8fH/8vPz//T09P/19fX/9/f3//j4+P////////////3+/f/8/Pz/+/v6//n5+f/3+Pf/9vb2//T09P/z8/P/8fLx//Dw8P/u7+7/7e3t/+vr6//q6ur/6Ojo/+fn5//l5eb/5OTk/+Li4v/h4eH/4N/f/97e3v/c3Nz/2tvb/9nZ2f/Y2Nj/1tbW/9XV1f/V1tP/mpvd/xUV+v8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//ygo8v+kpMr/wcG//76+vv+1tb//ODjq/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//ISLu/5ubtP+srKr/qamp/6enp/+mpqb/pKWk/6Ojo/+hoaL/oKCg/56env+dnZ3/mpqa/9HR0f/////////////////////////////////////////////////////////////////7+/v/5OTk/8PDw/+lpaX/mZmZ/5iYmP+bm5v/nJyc/56env+fn5//oaGh/6Kiov+ko6T/paWm/6enp/+oqKj/qqqq/6urrP+tra3/rq6u/7CwsP+xsbH/s7Oz/7W0tf+2trb/t7i3/7m5uf+7u7v/vb29/7+/wP/AwsP/wsTE/8PFxv/Fx8j/x8jK/8jKy//Ky8z/y83O/83O0P/O0NH/0NHT/9HT1P/T1NX/1NXW/9TU1P/U0tD/0s7K/8vAuP+0mIL/lGA3/305BP98NgD/fDcA/3w3AP98NwD/fDcA/3w3AP97NQD/jVMl/9vSyv/t7u7/7u7t/+/v7//x8fD/8vLy//T09P/19fX/9/f3//j4+P////////////7+/f/8/Pz/+vv6//n5+f/3+Pf/9vb2//T19P/z8/P/8vHx//Dw8P/u7u//7e3t/+vr6//q6ur/6eno/+fn5//m5eb/5OTk/+Li4v/h4eH/3+Df/97e3f/c3d3/29vb/9nZ2f/Y2Nj/1tbW/9XV1f/U1NP/zs/S/2Rl6P8DA/7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wEB//9LS+b/t7fD/8LBvf+QkMz/ERH4/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//TE3a/6ysrf+rqqv/qamp/6iop/+mpqb/pKWk/6Ojo/+ioqL/oKCg/56en/+dnZ3/mpqa/9PU0///////////////////////+fn5//39/f////////////////////////////////////////////39/f/u7u7/zs7O/66urv+dnJz/m5ub/56dnf+fn5//oaGh/6Oio/+kpKT/paWm/6enp/+pqKj/qqqq/6usq/+tra3/r66v/7CwsP+xsbL/s7Oz/7S1tP+2trb/uLm5/7m6uv+5uLb/s6mh/6uZiv+nj3v/pYp1/6aKdP+ni3X/p4x2/6iNdv+pjnf/qo54/6uPef+skHr/rZF7/66SfP+uknv/rI52/6iGa/+heFj/lGI6/4ZKGf9+Owb/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NQD/pHhW/+no5//s7Oz/7u3u/+/w7//x8fD/8/Ly//T09P/19fX/9/f3//j4+P////////////3+/f/8/Pz/+/v6//n5+f/3+Pj/9vb2//X19f/z8/P/8fLy//Dw8P/u7+//7e3t/+vr7P/q6ur/6ejo/+fn5//l5eb/5OTk/+Li4v/h4eH/39/f/97e3f/d3dz/29vb/9nZ2f/Y2Nj/1tbW/9XU1f/T09T/09PR/7m51f8xMfP/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8ICPz/c3LY/7y8v/9WVuD/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8ICPv/fn7D/66uq/+rq6v/qamp/6ioqP+mpqb/paWl/6Ojo/+ioqL/oKCh/5+fn/+dnZ3/m5qb/9bW1v/////////////////+/v7/wcHB/7Kysv/MzMz/5eXl//f39////////////////////////////////////////v7+//Pz8//Y2Nj/tbW1/6Kiov+en5//oaGh/6Ojo/+kpKT/pqWm/6enp/+pqKj/qqqq/6ysrP+tra3/rq+v/7CwsP+ysbL/s7Oz/7S1tf+2trf/sKei/6GGcf+PYDr/hUsc/4BADv99OQT/ezYA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezYA/3s2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP+DQxH/y7mq/+zt7v/s7O3/7u7u//Dv7//x8fH/8vLz//T09P/19fX/9/f3//j4+P////////////7+/v/8/Pz/+vv6//n5+f/3+Pj/9vb2//X19f/z8/P/8fLy//Dw8P/v7+7/7e3t/+zs7P/q6ur/6ejo/+fn5//l5eX/5OTk/+Pj4v/h4eH/39/f/97e3f/d3Nz/29vb/9rZ2f/Y2Nj/19bW/9XV1f/T1NP/0tLS/9LS0P+Ojt3/Dg77/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//HBz1/3Z21v8bG/X/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8oKOz/nZ21/66urP+rq6v/qamp/6ioqP+mp6b/paWl/6OjpP+ioqL/oaGg/5+fn/+enp3/nJyc/9nZ2f/////////////////+/v7/srGx/5CQkP+SkpL/mZmZ/66vrv/Kysr/6urq//v7+v//////////////////////////////////////+Pj4/9zc3P+5ubn/paWl/6Kiov+kpKT/pqam/6inp/+pqaj/qqqq/6ysrP+tra3/r6+v/7CwsP+ysrL/s7S0/7KvrP+fhXD/iFEl/304Av97NQD/ezUA/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w4Av+qg2T/5uTj/+vr7P/s7Oz/7u7u//Dv7//x8fH/8vPy//T09P/19vb/9/f3//j4+P////////////7+/v/8/Pz/+/v7//n5+f/4+Pf/9vb2//X09P/z8/P/8vLy//Dw8P/v7u//7e3t/+zs6//q6ur/6eno/+fn5//m5eX/5OTk/+Pj4v/i4eH/3+Dg/97e3v/d3d3/29vb/9ra2v/Y2dj/19fW/9XV1f/U1NP/0tLS/9HR0P/JydD/VFTq/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AQH//w0N+v8DA/7/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wEB/v9WVtf/r66u/62trf+rq6v/qamp/6moqP+np6f/paWl/6SkpP+joqL/oaGh/6CfoP+enp7/nZ6e/9vb2//////////////////+/v7/s7Kz/5OTk/+Tk5T/kpOT/5GRkf+UlJP/np6e/7i4uf/Z2dn/9PT0///////////////////////////////////////39/f/29vb/7e4t/+lpab/paWl/6ioqP+pqan/q6uq/6ysrP+tra3/r6+v/7GwsP+ys7P/rqij/5RsTP9/PQn/ezYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/5lnQP/b083/6uvs/+vr6//t7ez/7u7u//Dv7//x8fH/8vLy//T09P/19fX/9/f3//n4+f////////////7+/v/8/Pz/+/v7//n5+f/4+Pj/9vb2//X19f/z8/P/8vLy//Dw8P/v7+//7e3t/+zs6//q6ur/6Onp/+fn5//m5ub/5OTk/+Pj4//h4eH/3+Dg/97e3v/d3d3/29vb/9ra2v/Y2dj/19fW/9XV1f/U1NT/0tLS/9HR0f/R0c7/qqrW/yEh9/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//xER9/+MjMD/sLCu/62trf+sq6v/qqqq/6mpqf+np6f/pqam/6SkpP+jo6P/oqGi/6CgoP+fn5//oKCg/93d3f/////////////////+/v7/s7Oz/5SUlP+VlZX/lZWU/5SUlP+UlJT/lJSU/5SUlP+amZr/rKus/8zMzP/t7e3//f39//////////////////////////////////X19f/V1db/s7S0/6enqP+pqan/q6ur/62srP+urq7/r6+w/7Gysv+uqaX/kGRC/3w4Av98NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP98NwH/mWdA/9XKwf/o6en/6erq/+vr6//t7Oz/7u7u//Dw8P/x8fH/8/Lz//T19P/19vb/9/f3//n5+f////////////3+/v/8/fz/+/v7//n5+f/4+Pj/9vb3//X19f/z8/T/8vLy//Dw8P/v7+//7e3t/+zs7P/q6uv/6enp/+fn5//m5ub/5OTk/+Pj4//h4eH/4ODg/97e3v/d3d3/29vb/9ra2f/Y2Nj/19fX/9XV1f/U1NT/09LS/9HR0f/Q0M//zs7O/3R04v8FBf3/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//z095P+pqbP/r7Cv/66urf+srKz/q6ur/6mpqf+oqKj/pqam/6Wlpf+jo6T/oqKi/6Ghof+fn5//oaKi/9/f3//////////////////9/f3/srKy/5WVlf+Wl5b/lpaW/5aWlv+Wlpb/lpaW/5eXl/+Xl5f/l5eX/5mZmf+np6f/x8fH/+vr6//8/Pz/////////////////////////////////7+/v/8rKyv+ur67/q6ur/62trf+urq7/r7Cw/7Cwrv+Xdlv/fTkE/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NgD/ezUA/4NCD/+ogGH/2dHL/+jo6f/o6Oj/6urq/+vr7P/s7e3/7u7u//Dw8P/x8fH/8/Pz//T09P/29vb/9/f3//n5+f////////////7+/v/9/f3/+/v7//n5+v/4+Pj/9vb2//X19f/08/T/8vLy//Hw8P/v7+//7u3t/+zr7P/q6ur/6enp/+jo6P/m5ub/5eXk/+Pj4//i4uL/4ODg/9/e3//d3d3/3Nvc/9ra2v/Z2dn/19fX/9bW1v/U1NT/0tPT/9HR0f/Q0ND/z8/O/7u70f81NfH/AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Bgb8/3NzzP+zs7D/r6+v/66urv+trKz/q6ur/6qqqv+oqaj/p6en/6Wmpf+kpKT/o6Oj/6Kiof+goKD/pKSj/+Hh4f/////////////////9/f3/sbGx/5eXl/+YmJj/l5eX/5eXl/+Xl5f/mJiX/5iYmP+YmZn/mZma/5qamv+ampr/nJyc/6enp//Hx8f/7Ozs//7+/v////////////////////////////v7+//i4uL/vLy8/62srP+vrq7/sbGx/6aXjP+CRRX/fDYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP97NQD/ezUA/3w2AP+CQQ3/m2tG/8Ounv/g3tz/5ufn/+fn5//p6Oj/6urq/+zs7P/t7e3/7+7u//Dw8P/y8fH/8/Pz//T09f/29vb/+Pf4//n5+f////////////7+/v/9/f3/+/v7//r5+v/4+Pj/9/f2//X19f/09PT/8vLy//Hx8f/v7+//7u7u/+zs7P/r6+v/6unp/+jo6P/m5ub/5eXl/+Pj4//i4uL/4ODg/9/f3//e3d7/3Nzc/9ra2v/Z2dn/2NjX/9bW1v/U1NT/09PT/9HR0f/Q0ND/zs/O/87PzP+Kitz/DAz8/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//JSXv/6Cguv+ysrH/r7Cw/6+urv+tra3/rKys/6qqqv+pqan/p6in/6ampv+lpaX/pKSj/6Kiov+hoaH/pqam/+Pj4//////////////////7+/v/sLCw/5iYmP+ZmZn/mJmZ/5mZmP+ZmZn/mZmZ/5mamf+ampr/m5qb/5ubm/+cnJz/nZ2d/56env+fn5//ra2t/87Ozv/x8fH//v7+////////////////////////////8vLy/8zMzP+ysrL/r6+v/5NsTv98NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP97NgD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP97NQD/ezUA/3s1AP98NgD/fjoF/4JCD/+JTh7/lGA4/6uHa//Gtaj/29fU/+Tk5f/k5eX/5ubl/+fn5//p6ej/6urq/+zs7P/t7e3/7+7u//Dx8P/y8vL/8/Pz//X09P/29vb/+Pj4//n5+f////////////7+/v/9/f3//Pv7//r6+v/4+Pj/9/f3//X19v/09PT/8vPz//Hx8f/v8O//7u7u/+3t7P/r6+v/6unp/+jo6P/n5+f/5eXl/+Pj5P/i4uL/4OHh/9/f3//e3d7/3Nzc/9vb2//Z2dn/2NfY/9bW1v/V1dX/09PT/9HS0v/Q0ND/z8/P/87Ozf/Dw87/Q0Pt/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//Xl7X/7S0s/+ysrL/sbCw/6+vr/+trq7/rKys/6urq/+qqqr/qKio/6enp/+mpqb/pKSl/6Ojo/+ioaH/qKio/+Xl5f/////////////////6+vr/sLCx/5mZmf+bm5r/mpqa/5qamv+ampr/mpub/5ubm/+bnJv/nJyc/52dnf+enp7/np+e/5+gn/+goaD/oaGh/6Ojo/+0tLT/29vb//n5+f////////////////////////////v7+//c3d3/sqqk/4ZPJP97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcB/4JEE/+TZED/oH9k/6aJc/+ojHb/qY12/6mNd/+rjnn/q495/6yQev+tkXv/rpJ8/6+Tff+wlH7/sJV+/7GWgP+zmYT/uKCO/8Gtnv/MwLf/2NbT/97f3//h4uP/4uLj/+Pj4//k5OT/5ubm/+fn5//p6en/6uvq/+zs7P/t7e3/7+/v//Dw8P/y8vL/9PP0//X19f/29vb/9/j4//n5+f////////////7+///9/f3//Pz7//r6+v/5+fn/9/f3//b29v/09PT/8vPz//Hx8f/w8PD/7u7u/+3t7P/r6+v/6urp/+jo6P/n5+f/5eXl/+Tk5P/i4uP/4eHh/9/f3//e3t7/3Nzc/9vb2//a2tn/2NjY/9bX1v/V1dX/09TT/9LS0v/R0NH/z8/P/87Ozf/Pzsz/kZDZ/wsL+/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8YGPX/lZbB/7a2s/+zsrL/sbGx/7Cwr/+urq7/ra2t/6yrq/+qqqr/qamp/6ioqP+np6f/paam/6WkpP+joqL/qamp/+fn5//////////////////5+fn/sbGx/5ubm/+cnJz/nJyc/5ybnP+cnJz/nJyc/5ycnP+dnZz/nZ2d/56env+fn5//oKCg/6ChoP+hoaH/oqOi/6SkpP+kpKT/qamp/8TExP/s7Oz//v7+////////////////////////////1ce8/4BADf98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/j143/7Chlf++u7n/w8PD/8bHyP/Hycr/ycrL/8rMzf/Mzc//zs7Q/8/Q0f/Q0tP/0tPV/9PV1v/V1tf/1tjZ/9jZ2//Z29z/2tzd/9zc3v/c3d7/3t7d/9/f3//g4OD/4uHi/+Pj4//l5OT/5ubm/+jo6P/p6en/6+vr/+zs7P/t7e3/7+/v//Hx8f/y8vL/8/T0//X19f/29vf/+Pj4//r6+f/////////////+///+/f3//Pz8//r6+v/5+fn/9/j3//b29v/09PX/8/Pz//Hx8f/w8PD/7u/u/+3t7f/s6+v/6urq/+jp6f/n5+f/5eXl/+Tk5P/j4+P/4eHh/9/f4P/e3t7/3d3c/9vb2//a2tr/2djY/9fX1//V1tX/1NTU/9PS0v/R0dH/0M/P/87Ozv/Ozsz/vr7O/zs77/8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//9OTt//s7O3/7W1tP+zs7P/srKy/7CwsP+vr6//rq6t/6ys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r/+trq7/ra2t/6ysrP+qq6r/qqqp/6moqf+np6f/sLCw/+zs7P/////////////////29vb/tLS0/6Ghof+ioqL/oqKi/6Kiov+ioqL/oqKi/6Kio/+ioqP/o6Oj/6Sjo/+kpKT/paWl/6ampf+mpqb/p6en/6ioqP+pqan/qqqq/6urq/+srKz/ra2t/6+vrv+vr6//v7+//+zs7P//////9O/q/51pQf96NAD/fDcA/3w3AP98NwD/fDcA/3s2AP+JUSX/ubCq/8PDxP/Dw8P/xcXE/8bHxv/IyMf/ycnJ/8rKyv/MzMz/zc7N/8/Pz//Q0ND/0tLR/9PT0//U1NT/1tbW/9fX1//Z2dn/2tra/9zc3P/d3d3/39/f/+Dg4f/h4uL/4+Pj/+Xl5P/m5ub/5+fn/+np6f/q6ur/7Ozs/+3t7f/v7+//8PDw//Hy8v/z8/P/9PX1//b29v/4+Pf/+fn5//v6+v////////////////////7//f39//v8+//6+vr/+fj4//f39//29fb/9PT0//Pz8v/x8fH/8PDw/+7u7v/t7O3/6+vr/+rq6v/o6Oj/5+fn/+Xl5v/k5OT/4uPj/+Hh4f/g4N//3t7e/93d3P/b29v/2tra/9jY2P/X19f/1tXV/9TU1P/S09P/0dHR/9DQ0P/Pzs7/zc3N/83Ny/+qq9L/Hx/2/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//woK+/+Dg83/urq4/7e3t/+2trb/tbW1/7SztP+zsrL/sbGx/7CwsP+vr6//rq6u/62srf+srKv/q6ur/6qqqv+oqKj/srKy/+3t7f/////////////////19fX/tLS0/6Ojo/+jo6T/o6Oj/6Ojo/+jpKP/o6Oj/6SkpP+kpKT/pKSk/6Wlpf+mpab/pqam/6enp/+oqKj/qKio/6mpqf+qqqr/q6ur/6ysrP+tra3/rq6u/7Cwr/+xsbH/sbGx/8LCwf/x8fH//////7OLbP97NQD/fDcA/3w3AP98NwD/fDcA/3w3AP9+OgX/po14/8PExP/ExMT/xsbG/8fHx//IyMj/ysrK/8vLy//NzM3/zs7O/8/Qz//R0dH/0tLS/9PT1P/V1dX/1tbW/9jY2P/Z2dn/29vb/9zc3P/d3t3/39/f/+Dh4f/i4uL/4+Pj/+Xk5f/m5ub/6Ojo/+rp6f/r6+v/7Ozs/+7t7v/v7+//8PHw//Ly8v/z9PP/9fX1//f39//4+Pj/+vn6//v7+////////////////////////f39//z8/P/7+vr/+fn5//f39//29vb/9PT0//Pz8//x8fL/8PDw/+7v7//t7e3/7Ozr/+rq6v/p6On/5+fn/+bm5v/k5OT/4+Pj/+Hi4f/g4OD/397e/93d3f/c29z/2tra/9nZ2f/Y19j/1tbW/9TV1f/T09P/0dLS/9DQ0P/Pz8//zs3O/8zMzP/Kysv/YmLk/wAA//8AAP//AAD//wAA//8AAP//AAD//wAA//8AAP//AAD//wkJ/P9/f8//u7u5/7i4uP+3t7f/tba2/7S1tf+ztLP/srKy/7Gxsf+wsLD/r6+v/66urv+tra3/rKys/6urq/+pqan/s7Oz/+3t7f/////////////////09fT/tbW1/6SkpP+lpaX/pKWl/6Wlpf+lpaX/paWl/6Wlpf+lpab/pqam/6ampv+np6f/p6en/6ioqP+pqan/qqqp/6qrqv+rq6v/rKys/62trf+urq7/r6+v/7Gxsf+ysrL/s7Oz/7Szs//MzMz/+/v8/9fCsf+CQQ3/fDYA/3w3AP98NwD/fDcA/3w3AP97NgD/iFEk/7eso//Gxsf/xsbG/8jHx//Jycj/ysrK/8zMzP/Nzc3/zs7P/9DQ0P/R0dH/0tPT/9TU1P/W1dX/19fX/9jY2P/a2tr/29vb/93c3f/e3t7/4N/f/+Hh4f/i4uL/5OTk/+Xl5f/m5+b/6Ojo/+rp6v/r6+v/7ezs/+7u7v/v8O//8fHx//Lz8v/09PT/9fX1//f39//4+Pj/+vr6//v7+////////////////////////v39//z8/P/7+vv/+fn5//j49//29vb/9PX1//Pz8//y8vL/8PHx/+/v7//u7e7/7Ozs/+vr6v/p6en/6Ofo/+bm5v/l5eX/4+Pj/+Li4v/g4OH/39/f/97e3v/c3Nz/29rb/9rZ2f/Y2Nj/19bX/9XV1f/T1NT/0tLS/9HR0f/Qz9D/zs7O/83Nzf/Ozsv/qqrS/yEh9v8AAP//AAD//wAA//8BAf//AgL//wAA//8AAP//AAD//wkJ/P9/f9D/vLy6/7m5uf+4uLj/t7a3/7a1tf+0tbT/s7Oz/7Kysv+xsbH/sLCw/6+vr/+urq7/ra2t/6ysrP+qqqr/s7Oz/+3t7f/////////////////09PT/tra2/6ampv+np6b/pqam/6amp/+mpqb/pqem/6enpv+np6f/p6en/6ioqP+oqKj/qamp/6qpqf+qqqr/q6ur/6ysrP+tra3/ra6u/66vr/+vsK//sbGw/7Kxsv+zsrP/tLS0/7W1tf+4uLj/4uPj//bx7f+ea0T/ezUA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/5BfOP+7sar/x8jI/8jIyP/Jysn/y8vL/8zMzP/Ozc7/z8/P/9DQ0P/S0tL/09PT/9XV1f/W1tb/2NfX/9nZ2f/a2tr/3Nzc/93d3f/e3t7/4ODg/+Hh4f/j4+P/5OTk/+bl5v/n5+f/6enp/+rq6v/r7Ov/7e3t/+/v7v/w8PD/8fHx//Pz8//09PT/9fb1//f39//5+Pn/+vr6//v7+////////////////////////v7+//38/P/7+/v/+vr5//j4+P/39/f/9fX1//T08//y8vL/8fHx/+/w7//u7u7/7e3s/+vr6//q6er/6Ojo/+fm5//l5eX/5OTj/+Li4//h4eH/3+Dg/97e3v/d3d3/29vb/9ra2v/Z2Nn/19fX/9bW1v/U1NT/09PT/9HR0f/Q0ND/z8/P/83Nzf/MzMz/ysvL/25u4f8EBP7/AAD//x4e//+Dg///nZ3//2Fh/v8YGP//AAD//wkJ/P+BgdD/vb26/7q6uv+4ubn/t7i4/7a3tv+1tbX/tLS0/7Ozs/+ysrL/sbGx/7CwsP+vr6//rq6u/62trf+srKz/tLS0/+zs7f/////////////////19fX/t7e3/6enp/+oqKj/qKio/6ioqP+oqKj/qKio/6ioqP+oqaj/qamp/6mqqf+qqqr/qqqq/6urq/+rq6z/rKys/62trf+urq7/r6+v/6+wsP+wsbH/srKx/7Oys/+0s7T/tbW1/7a2tv+2trb/ycnJ//r7+//Ruab/gkAN/3s2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3Af+QXzj/u7Gp/8rKy//Kysr/y8vL/83Nzf/Ozs7/0M/Q/9HR0f/S0tL/1NPU/9XV1f/X1tb/2NjY/9rZ2f/b29v/3Nzc/97e3v/f39//4ODg/+Li4v/j4+P/5OXl/+bm5v/o6Oj/6enp/+rr6v/s7Oz/7u3t/+/v7//w8PD/8vLy//Pz8//19PX/9vb2//j49//5+fn/+/r6//z8/P///////////////////////v7+//39/f/7/Pv/+vr6//j5+P/39/f/9vb2//T09P/z8/P/8fHx/+/w8P/u7+7/7e3t/+vr6//q6ur/6ejp/+fn5//m5eb/5OTk/+Pj4//i4eL/4ODg/97e3//d3d3/3Nzc/9va2//Z2dn/2NjX/9bW1v/V1dX/09TU/9LS0v/R0dH/z8/P/87Ozv/Nzc3/zMzL/7i3z/81NfD/CQn//5mZ/v/+/v////////f3///Cwv7/WVn//xkZ+/+Hh87/vr67/7u7u/+5urr/uLm5/7e4t/+2trb/tbW1/7S0tP+zs7P/srKy/7Gxsf+wsLD/sK+v/6+vr/+tra3/tbW1/+zs7P/////////////////29vb/ubm5/6ioqP+qqar/qamp/6mpqf+pqan/qamp/6mqqv+qqqr/qqqq/6uqqv+rq6v/rKyr/6ysrP+tra3/ra6u/66urv+vr6//sLCw/7Gxsf+ysrL/s7Oz/7S0tP+1tbX/tra2/7e3t/+3uLf/vr6+/+3t7f/59fP/qHtY/3s1AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/j1w0/7uvpv/LzM3/zMzM/87Nzv/Pz8//0dDQ/9LR0v/T09P/1NTV/9bW1f/X19f/2NjY/9ra2v/b29v/3N3d/97e3v/g3+D/4eHh/+Li4v/k5OP/5eXl/+fm5//o6Oj/6unq/+vr6//s7Oz/7u7u/+/v7//w8fD/8vLy//P08//19fX/9/f3//j4+P/5+fn/+/v7//z8/P////////////////////////7+//39/f/8/Pz/+vr6//n5+f/39/f/9vb2//T09f/z8/P/8vLx//Dw8P/v7+//7e3t/+zs7P/r6uv/6enp/+jo6P/m5ub/5eXl/+Pj4//i4uL/4eDh/9/f3//e3t7/3Nzc/9vb2//a2tr/2NjY/9fX1//V1tb/1NTU/9LT0//R0dL/0NDQ/8/Pz//Nzc3/zMzM/8zMyv+Tk9f/QkL4/9zc////////////////////////8vL//7i4+/+5udb/v7++/7u7u/+6u7v/urq6/7i4uP+3t7j/tra2/7W1tf+0tLT/s7Oz/7Oys/+xsbL/sLGx/7CwsP+urq//tbW2/+vr6//////////////////39/f/uru7/6qqqv+rq6v/q6ur/6urqv+rq6v/q6ur/6urq/+rq6v/q6ys/6ysrP+srKz/ra2t/66urf+urq7/r6+v/6+wsP+wsbH/sbGx/7Kysv+zs7P/tLS0/7W1tf+2trb/t7e3/7i4uP+5ubn/urq5/+Pj4///////5djN/5FXKf97NQD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDYA/4xWK/+4qJv/zc3N/87Pz//Qz8//0dHR/9LS0v/U1NT/1dXV/9bW1v/Y2Nj/2dnZ/9va2//c3Nz/3d3d/97e3v/g4OD/4eLi/+Pj4//k5OT/5ubm/+fn5//p6Oj/6urq/+vr7P/t7e3/7u7u//Dw8P/x8fH/8/Pz//T09P/19vX/9/f3//n4+P/6+vr/+/v7//39/P////////////////////////////79/f/8/Pz/+/v7//r5+f/4+Pj/9vb3//X19f/z9PT/8vLy//Hx8f/w7+//7u7u/+3s7P/r6+v/6unp/+jo6P/n5uf/5eXm/+Tk5P/i4+P/4eHh/+Dg3//f3t7/3d3d/9zc3P/a2tv/2dnZ/9fX1//W1tb/1dXV/9PT1P/S0tL/0dHR/8/Pz//Ozs7/zc3N/8zMy//Ix8r/mprd/9nZ+//////////////////////////////////6+vn/4+Pj/8jIyP+8vLz/urq6/7m5uv+4uLn/t7e4/7a3tv+1tbb/tLS0/7S0s/+zs7L/srKy/7Gxsf+wsLD/tra2/+rq6v/////////////////5+fn/vb29/6yrq/+srK3/rKys/6ysrP+sraz/rKyt/62srf+tra3/ra2t/66trf+urq7/r66u/6+vr/+vsK//sLCw/7Gxsf+ysrL/srKy/7Ozs/+0tLT/tbW1/7a2tv+3t7f/uLi4/7m5uf+6urr/uru6/9/g3////////////8+3o/+EQxD/ezYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP+HTR7/s52M/87Nzf/R0dH/0tHS/9PT0//U1NT/1dbV/9fX1//Y2Nj/2tra/9vb2//c3Nz/3t7e/9/f3//h4OH/4uLi/+Pj5P/l5eX/5ubm/+jo5//p6en/6urq/+zs7P/t7e3/7+/u//Dw8P/x8vH/8/Pz//T09P/29vX/9/f3//n5+f/6+vr//Pz7//39/f////////////////////////////7+/v/8/f3/+/v7//r6+v/4+Pj/9/f3//X29v/09fT/8vPz//Hx8f/w8PD/7+7v/+3t7f/r6+z/6urq/+jp6f/n5+f/5ubm/+Xk5P/j4+P/4uLi/+Dg4P/f39//3t7e/9zc3P/b29v/2dna/9jY2P/X19f/1tXV/9TU1P/T09P/0dHR/9DQ0P/Pz8//zs7O/83MzP/Ly8v/xsbL/8fH3//w8Pr//////////////////////////////////v7+//X19f/d3d3/xcXF/7q6uv+4ubn/uLi4/7e4uP+3t7f/tra2/7W1tf+0tLT/s7Oz/7Kysv+xsbH/t7a2/+np6f/////////////////7+/v/wMDA/62trf+urq7/rq6t/66urv+urq7/rq6u/66urv+urq7/r6+u/6+vr/+vr6//sLCw/7CwsP+xsbH/srGx/7Kysv+zs7P/tLS0/7S1tf+1tbX/tra2/7e3t/+4uLj/ubm5/7q6uv+7u7v/vLy8/+Tk5P////////////v59/+8mn7/gD0I/3s2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NgD/hEYV/6yOdv/Nysj/09PU/9PT1P/V1dX/1tbW/9jY2P/Z2dn/2tra/9zc3P/d3d3/3t7e/+Dg4P/h4eH/4+Li/+Tk5P/l5eX/5+fm/+jo6P/q6er/6+vr/+zt7P/u7u7/7+/v//Hx8f/y8vL/8/Pz//X19f/29vb/+Pj4//n5+f/7+/r//Pz8//79/f////////////////////////////7//v/9/f3//Pz8//r6+v/5+fn/9/f3//b29v/19fX/8/Pz//Ly8v/w8PD/7+/v/+7t7v/s7Oz/6+vr/+np6f/o6Oj/5ufn/+Xl5f/k5OT/4uLj/+Hh4f/f4OD/3t7e/93d3f/c3Nz/2tra/9jZ2f/X19f/1tbW/9XV1f/T09T/0tLS/9HR0f/Q0ND/zs/P/83Nzf/MzMz/y8vK/8jIyv/R0db/7+/u//39/f/////////////////////////////////+/v7/9PT0/+Hh4f/Nzc3/v8DA/7i4uP+3t7f/t7a3/7a2tv+1tbX/tbS0/7S0tP+zs7P/t7e3/+jo6P/////////////////9/f3/wsLC/66urv+vsLD/r6+v/6+vr/+vr6//r7Cv/6+wr/+wsLD/sLCw/7CxsP+wsbH/sbGx/7Kysv+ysrL/s7Oz/7Szs/+0tLT/tbW1/7a2tv+3t7b/uLe4/7i4uP+6ubn/urq6/7u7vP+8vLz/w8PD//Dw8P/////////////////38/D/roZm/3w4Av98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/389Cv+edVT/x7+4/9XW1v/W1tb/19fX/9jY2P/a2dr/29vb/9zc3P/e3t3/39/f/+Dg4f/i4uL/4+Pj/+Xl5f/m5ub/5+fn/+np6f/q6ur/6+vr/+3t7f/u7+7/8PDw//Hx8f/z8vL/9PT0//X29f/39/f/+Pj4//r6+v/7+/v//f39//7+/v////////////////////////////7//v/+/v7//Pz8//v7+//5+fn/+Pj4//f29v/19fX/9PT0//Ly8v/x8fH/7+/w/+7u7v/t7e3/6+vr/+nq6v/o6en/5+fn/+bm5f/k5OX/4+Pj/+Hi4v/g4eD/39/f/93d3f/c3Nz/29vb/9nZ2v/Y2Nj/1tfW/9XV1f/U1NT/09PT/9HS0v/Q0dH/z8/P/87Ozf/Nzc3/zMzL/8rKyv/Jycj/y8zM/93d3f/y8vL//f39///////////////////////////////////////8/Pz/7u7u/93d3f/Kysr/vb29/7i4uP+2tbb/trW2/7W1tf+0tLT/t7e3/+fn5//////////////////+/v7/xsbG/7CwsP+xsbH/sbGx/7Gxsf+xsbH/sbGx/7Gxsf+xsbH/srGx/7Kysv+ysrL/s7Oz/7Ozs/+0tLT/tLS1/7W1tf+1trX/tra2/7e3t/+4uLj/ubm5/7q6uf+7u7r/vLy8/7y8vP++vb7/2tra//39/f//////////////////////3dfS/5drSf99OQP/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP98NgH/kl41/7+uof/V1dT/2NjZ/9nZ2f/a2tr/3Nvc/93d3f/e3t7/4ODg/+Hh4v/i4uL/5OTk/+Xl5f/m5uf/6Ojo/+np6f/q6+v/7Ozs/+3u7f/v7+//8PDw//Ly8f/z8/P/9PX1//b29v/39/f/+fj5//r6+v/7/Pz//f39///+/v/////////////////////////////////+/v7//f39//v7+//6+vr/+Pj4//f39//29vb/9PT0//Pz8//x8vH/8PDw/+/v7//t7u3/7Ozs/+rq6v/p6en/5+jo/+bm5v/l5eX/5OPk/+Li4v/h4eH/4ODg/97e3//d3d3/3Nzc/9ra2v/Z2dn/2NjX/9bW1v/V1dX/1NTU/9LT0v/R0tH/0NDQ/8/Pz//Nzs7/zM3M/8vLy//Kysr/yMnJ/8fIx//Mzcz/3d3d//Hx8f/9/f3///////////////////////////////////////7+/v/6+vr/7u7u/9zc3P/MzMz/vr6+/7e3t/+1tbX/t7e2/+bm5v/////////////////+/v7/y8vL/7Kysf+ysrL/srKy/7Kysv+ysrL/srKz/7Ozsv+zsrP/s7Oz/7Ozs/+0tLT/tLS0/7W1tP+1tbX/tba2/7a2tv+3t7f/t7e4/7i4uP+5ubn/urq6/7u7u/+7u7v/vLy8/8DAv//Y2Nj/+fn5///////////////////////8/Pz/19fY/7+5tf+YbUv/fTkD/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/4ZJGP+ri3H/0MrG/9vc3P/b3Nz/3Nzc/97e3v/f39//4ODh/+Li4v/j4+P/5OXk/+bm5v/n5+f/6Ojo/+rq6v/r6+v/7O3t/+7u7v/v7/D/8fHx//Ly8v/09PT/9fX1//b29v/4+Pj/+vn5//v7+//8/Pz//f79/////////////////////////////////////////v7//f39//z8/P/6+/v/+fn5//f3+P/29vb/9fT1//Pz8//y8vL/8fDw/+/v7//u7u7/7e3s/+vr6//q6un/6ejo/+fn5//m5uX/5OTk/+Pj4//h4eL/4ODh/9/f3//e3t7/3dzd/9vb2//a2tr/2NjY/9fX1//W1tb/1dTU/9PT0//S0tL/0dHR/9DQ0P/Oz87/zc3O/8zMzP/Ly8v/ysrK/8jIyP/Hx8f/xsbG/8vLy//Y2Nj/7Ozs//n5+f/////////////////////////////////////////////////6+vv/8fHx/+Li4v/Q0dD/xcXE/+no6f/////////////////+/v7/0NDQ/7Ozs/+0tLT/tLS0/7S0tP+0tLT/tLS0/7S0tP+0tLT/tbW0/7S1tf+1tbX/tba1/7a2tv+2t7b/t7e3/7i4uP+4uLj/ubm5/7m5uf+6urr/urq7/7y8vP/CwsL/z8/P/+jo6P/7+/v////////////////////////////t7e3/y8vL/8jJyf/Dvbn/nHNS/347Bv98NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP99OgX/lWM7/8Gvof/a2Nf/3t/f/9/e3//g3+D/4eHh/+Li4v/k5OT/5eXl/+bm5//o6Oj/6enp/+rr6//s7Oz/7e3u/+7v7v/w8PD/8fHx//Pz8//09PT/9vX2//f39//4+fj/+vr5//v7+//8/P3//v7+/////////////////////////////////////////////v7+//z9/P/7+/v/+vr6//j4+P/39/f/9fX1//T09P/z8/P/8fHx//Dw8P/u7u//7e3t/+zr6//q6ur/6enp/+fn5//m5ub/5eXl/+Tj5P/i4uL/4eHh/+Dg3//f3t7/3d3d/9zc3P/b2tr/2dnZ/9jY2P/X19f/1tbW/9TV1P/T09P/0tLS/9DQ0P/Pz8//zs7O/83Nzf/MzMz/y8vL/8rJyf/JyMj/yMfH/8bGxv/ExMX/xsbG/9HR0v/h4eH/8/Pz//z8/P/////////////////////////////////////////////////+/v7/9/f3//r6+v//////////////////////2dnZ/7q6uv+4uLj/t7a3/7W1tv+0tLX/tLS0/7S0tP+0tLX/tbW1/7W1tf+1trX/tra2/7a2tv+2t7b/t7e3/7i4uf+6u7v/vb29/8DAwP/FxcX/0tLS/+Hh4f/u7u7/+/v7//////////////////////////////////b29v/T1NP/yMjI/8nJyf/LzMz/x8PA/6OAZP+APwz/ezYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezUA/4RFFP+lfl//zcG4/97e3f/h4uL/4uLi/+Pj4//k5OX/5ubm/+fn5//o6Oj/6urq/+vr6//t7e3/7u7u/+/w7//x8PH/8vLy//Tz8//19fX/9vb2//f39//5+fn/+vr6//z8/P/9/f3///7//////////////////////////////////////////////v7+//39/f/8/Pv/+vr6//n5+f/3+Pj/9vb2//X19P/z8/P/8vLy//Dx8f/v7+//7u7u/+zs7P/r6+v/6urq/+jo6P/n5+f/5ubm/+Tk5P/j4+P/4uHi/+Dg4P/f39//3t7e/9zc3f/b3Nv/2tra/9nZ2f/X2Nj/1tbW/9XV1f/U1NT/09PT/9LR0f/Q0ND/z8/P/87Ozv/Nzc3/zMzM/8rLy//Kycr/ycjI/8fHyP/Gxsf/xcXF/8PExP/DxMT/yMjI/9bV1f/m5uX/9fX0//7+/v//////////////////////////////////////////////////////////////////////9/f3/+vr7P/l5eX/39/f/9ra2v/V1dX/0tLS/9DQ0P/Ozs7/zc3N/8zMzP/MzMz/zs7O/8/Pz//R0dH/1NTU/9ra2v/g4OD/6Ojn//Hx8f/4+Pj//Pz8////////////////////////////////////////////9vb2/9fX1//IyMj/ycnJ/8rKyv/Ly8v/zc3N/8vIx/+sj3j/hEYV/3s1AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP98NwL/iU4g/62Kb//QxLv/4uHg/+Xm5//m5uf/5+fm/+jo6P/p6en/6+rq/+zs7P/t7e3/7+/u//Dw8P/x8fH/8/Lz//T09P/19vb/+Pj5//r6/P/7/P7//f7///39/v/+/v7///////////////////////////////////////////////////////39/v/8/Pz/+/v7//n5+f/4+Pj/9/b3//X19f/09PT/8vPy//Hx8f/w8PD/7u7u/+3t7f/s7Oz/6uvq/+np6f/o6Oj/5ufn/+Xl5f/j5OT/4uPj/+Hh4f/g4OD/39/f/93d3v/c3Nz/29vb/9rZ2v/Z2Nj/19fX/9bW1v/V1dX/1NTT/9PS0v/R0dH/0NDQ/8/Pz//Ozs7/zc3N/8zMzP/Ly8v/ysrJ/8nIyP/Hx8f/x8fH/8XFxv/FxMT/xMPD/8LCwv/Dw8L/ycrJ/9TV1f/l5eX/8/Pz//v7+/////////////////////////////////////////////////////////////////////////////////////////////79/f/8/Pz/+/v7//v7+//7+/v//Pz8//z8/P/9/f3///////////////////////////////////////////////////////////////////////z8/P/s7Oz/0tLS/8jIyP/Jycn/ysrK/8vLy//MzMz/zc3N/8/Pz//Pzs7/t6OT/4xUKP98NgH/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezYA/3w4Av+KTyD/qIJj/8u6rf/f29j/6Onq/+rq6v/r6+v/7Ozs/+3t7f/u7u7/7+/v//Hx8f/y8vL/9PX0//b39//29vb/7ebh/+LWzP/ez8P/4tXK//fz8f////////////////////////////////////////////////////////////7+/v/9/f3/+/v7//r6+v/5+fn/9/f3//b29v/19PT/8/Pz//Lx8v/x8PH/7+/v/+7u7v/s7O3/6+vr/+nq6v/o6On/5+fn/+bm5v/k5OX/4+Pj/+Li4v/h4eH/4ODf/97e3v/d3d3/29zc/9rb2v/Z2dn/2NjY/9bX1//W1db/1dTV/9TT0//S0tL/0dHR/9DQz//Pz8//zs3O/83NzP/MzMz/y8vL/8rKyv/Jycj/yMjH/8fHxv/GxsX/xcXF/8TExP/Dw8P/wsLB/8HBwf/BwcH/xsbG/9LS0v/f397/7u7t//j4+P/9/f3////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/7u7u/9ra2v/Kysr/x8jI/8nJyf/Ky8r/y8vL/8zMzP/Nzs3/z87O/8/P0P/R0dH/0tPT/8O3rf+YakX/fToF/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP97NQD/ezYA/4NDEP+baUP/tpd+/9LEuP/h3Nj/6OXj/+zr6//w8PH/8vP0//Lz8//v7uz/6OHb/9C7qv+yjG7/mmY8/4lLGv+APgr/hUYT/7WPcP/49PH////////////////////////////////////////////////////////////9/f3//Pz8//v7+//5+fn/+Pj4//f29//19fX/9PT0//Py8v/x8fH/8PDw/+7v7v/t7e3/7Ozs/+rr6//p6en/6Ojo/+fn5v/l5eX/5OTk/+Pj4//h4uL/4OHg/9/f3//e3t7/3N3d/9vb3P/a2tr/2dnZ/9jY2P/W1tf/1tbW/9XU1P/T09P/0tLS/9HR0f/Qz9D/z8/P/87Ozv/Nzc3/zMzM/8rLyv/Kysr/ycnJ/8jIyP/Hx8f/xsbG/8XFxf/ExMT/w8TD/8PDw//CwsL/wcHB/8DAv//AwMD/w8PD/8rJyv/W1tb/4uLi/+3t7f/29vb//f39//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/6+vr/8PDw/+Tk5P/U1dT/ysrK/8fHx//IyMj/ycnJ/8rKyv/Ly8v/zMzM/83Nzf/Oz8//z9DQ/9DQ0f/S0tH/09PT/9XV1v/OycX/qYht/4NEEv97NQD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w2AP96NAD/fTkE/4RFEv+SWy//pHhV/7KOcv+7nIP/v6KM/7ucgv+rgmD/kVgs/4JADP97NgH/ejQA/3s2AP98NwD/ezYA/4NBDv/Vv6/////////////////////////////////////////////////////////////+/v7//f39//v7+//6+vr/+fj5//f39//29vb/9PT0//Pz8//y8vL/8PHw/+/v7//u7u7/7O3t/+vr6//q6ur/6enp/+jo5//m5ub/5eXl/+Tj5P/i4+L/4eHh/+Dg4P/f39//3t3e/9zc3P/b29v/2tra/9nZ2f/Y2Nj/1tfW/9XV1f/U1NT/09PT/9LS0v/R0dH/0NDQ/8/Pz//Ozs7/zc3N/8zMy//Ly8v/ysrK/8nJyf/IyMj/x8fH/8bHxv/Gxcb/xcXF/8TExP/Dw8P/w8PD/8LCwv/BwcL/wMHA/8DAwP+/v7//v7+//8PDw//IyMn/z8/P/9jY2P/g4OD/6enp/+/v7//z8/P/9fb1//j4+P/6+vr/+/v7//39/f/+/v7//v7+//////////////////7+/v/9/f3//Pz8//r6+v/4+Pj/9fX1//Ly8v/s7Oz/4+Pj/9nY2f/Q0ND/ysrK/8XGxv/Gxsb/x8fI/8nJyP/Kysn/y8vK/8vMzP/NzMz/zs3N/87Ozv/Pz8//0NDR/9HR0f/S0tP/1NTU/9XV1f/X19f/1tTT/7yomf+SXjX/fTgE/3s2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP97NgD/ezUA/3s1AP96NAD/ejQA/3o0AP97NQD/ezYA/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3s2AP+5lHj//////////////////////////////////////////////////////////////////f39//z8/P/7+vv/+fn5//j4+P/39/f/9fX1//T09P/z8/P/8fLx//Dw8P/v7+//7e3t/+zs7P/r6+v/6urp/+no6P/n5+f/5ubm/+Tl5f/j4+P/4uLi/+Hh4f/g4OD/3t7e/93e3f/c3Nz/29vb/9ra2v/Z2dn/19fX/9bW1v/V1dX/1NTU/9PT0//S0tL/0dHR/9DQ0P/Pz8//zs7O/83Nzf/MzMz/y8vL/8vKyv/Kycn/ycjJ/8jIyP/Hx8f/xsbH/8XGxv/FxcX/xMTE/8TDw//Dw8P/wsLC/8LCwv/BwcH/wcHB/8DAwP+/v7//v7+//7+/v/+/v7//v7+//8HBwf/ExMT/ycnI/8zNzP/Pz8//0tLS/9TU1P/V1dX/1tfW/9fX1//Y2Nj/2NfY/9fX1//W1tb/1NTU/9HS0v/Pz87/y8vL/8bGxv/FxMT/xMTE/8TFxf/FxcX/xsbG/8fHx//IyMj/ycnJ/8rKyv/Ly8v/zMzL/83NzP/Ozs3/zs7P/9DQ0P/R0dD/0tHS/9PS0v/U1NT/1dXV/9bW1v/X19f/2djZ/9rb2//QyMP/qINn/4RFE/97NQD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3ozAP+zimv//////////////////////////////////////////////////////////////////v7+//z9/f/7+/z/+vr6//n5+P/39/j/9vb2//T19f/z9PT/8vLy//Dx8f/v7/D/7u7u/+3t7f/s7Oz/6urq/+np6f/o6Oj/5ufn/+Xm5f/k5OT/4+Pj/+Li4v/g4eH/39/f/97e3v/d3d3/3Nzc/9vb2//Z2tr/2djY/9jX1//W1tf/1dXV/9TU1P/T09P/0tLS/9HR0f/Q0ND/z8/P/87Ozv/Nzc3/zM3M/8zLzP/Ly8v/ysrK/8nJyf/IyMj/x8fH/8fHx//Gxsb/xcXF/8XFxf/ExMT/xMTE/8PDw//Dw8P/wsLC/8LBwv/BwcH/wcHB/8DBwf/AwMD/wMDA/8DAwP/AwMD/v7+//7/Av/+/v7//v7+//7+/v/+/v7//v7+//8C/wP+/v8D/wMDA/8DAwP/BwcH/wcHB/8LCwv/Dw8P/w8TD/8TFxP/FxcX/xsbG/8fGxv/Hx8f/yMjI/8nJyP/Kysn/ysrK/8vLy//MzMz/zc3N/87Ozv/Pz8//0NDQ/9HR0P/S0dH/09LT/9TU1P/V1dX/1tbW/9fX1//Y2Nj/2dnZ/9ra2v/c3N3/2tnY/8Kvof+YZ0D/fjsG/3s1AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP+7mHz///////////////////////////////////////////////////////////////////////39/f/8/Pz/+/r7//n5+f/4+Pj/9/f3//X29f/09PT/8/Pz//Hx8v/w8PD/7+/v/+7t7v/t7O3/6+vr/+rq6v/p6en/5+jo/+bm5v/l5eX/5OTj/+Lj4//h4uH/4OHg/9/f3//e3t7/3d3d/9zc3P/b29v/2dnZ/9jY2P/X19f/1tbW/9XV1f/U1NX/09PT/9LS0v/R0dH/0NDQ/8/P0P/Ozs7/zs7O/83Nzf/MzMz/y8vL/8rKyv/Kysr/ycnJ/8jIyP/Hx8f/x8fH/8bHxv/Fxsb/xcXF/8XExP/ExMT/xMTD/8TDw//Dw8P/wsPC/8LCwv/CwsL/wsLC/8LBwf/BwcH/wcLB/8HCwf/BwsH/wcHB/8HCwv/CwsL/wsLC/8LCwv/Dw8L/w8PD/8PDw//Dw8P/xMTE/8XExf/FxcX/xsbF/8bGxv/Gxsf/x8fH/8jIyP/JyMn/ycnJ/8rKyv/Ly8v/zMzM/83MzP/Nzc3/zs7P/8/Pz//Q0ND/0dHR/9LS0v/T09P/1NPU/9XV1f/W1tb/19fX/9jY2P/Z2dn/2tra/9vb2//d3Nz/3t7e/+Dg4f/Y08//tpmC/45WKf99OAL/ezYA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDYA/4JADf/VwK////////////////////////////////////////////////////////////////////////7+/v/9/f3/+/v8//r6+v/5+fn/+Pj3//b29v/19fX/9PT0//Ly8v/x8fH/8PDw/+/v7v/u7e3/7Ozs/+vr6//q6er/6Ojp/+fn5//m5ub/5eXl/+Tj4//i4uP/4eHh/+Dg4P/f39//3t7e/93d3P/b3Nv/29va/9rZ2f/Z2dn/19jY/9fW1v/V1db/1NTU/9PU0//S09L/0dLR/9HR0f/Q0ND/z8/P/87Ozv/Nzc3/zMzM/8zLy//Ly8v/ysrK/8rKyf/Jycn/yMjI/8fIx//Hx8f/xsfG/8bGxv/Fxcb/xcXF/8XFxf/ExMT/xMTE/8TExP/ExMT/xMPD/8PDw//Dw8P/w8PD/8PDw//Dw8P/w8PD/8PDw//Dw8P/w8PD/8PExP/ExMT/xMTE/8TExP/FxcX/xcXF/8bGxv/Gxsb/x8fH/8fHx//IyMj/yMjJ/8nJyf/Kysr/y8rK/8vLy//MzMz/zc3N/87Ozf/Pzs//z8/P/9DQ0P/R0dH/0tLS/9PT0//U1NT/1dXV/9bW1v/X19f/2NjY/9nZ2f/a2tr/29vb/9zc3P/e3t3/397e/+Dg4P/i4uP/4+Pk/9XLw/+vjHH/ik4f/3w3Av97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/ezUA/6BuRv/17+z////////////////////////////////////////////////////////////////////////+///+/f7//Pz8//v7+//6+vr/+Pj4//f39//29vb/9PX1//Pz8//y8vL/8PDx/+/v7//u7u7/7e3t/+zs7P/r6+v/6enp/+jo6P/n5+b/5uXl/+Xk5P/k4+P/4uLi/+Hh4f/g4OD/3t/f/97e3v/c3Nz/3Nzc/9vb2v/Z2dn/2NjY/9jX1//W19f/1tXV/9XV1P/U1NP/09PT/9LS0v/R0dH/0NDQ/8/Pz//Pzs7/zs7O/83Nzf/MzMz/y8vM/8vLy//Kysr/ycnJ/8nJyf/JyMj/yMjI/8fIyP/Hx8f/xsbH/8bGxv/Gxsb/xcbF/8XFxf/FxcX/xcXF/8XFxf/ExMT/xMTE/8TExP/FxMX/xcTF/8TFxP/FxcT/xcXF/8XFxf/FxcX/xcbF/8bGxv/Hxsf/x8fH/8fHx//Hx8j/yMjI/8nJyf/Jycn/ysrK/8rKyv/Ly8v/zMzM/8zNzf/Nzc3/zs7O/8/Pz//Q0ND/0NDQ/9LR0v/S09L/09PT/9TU1P/V1dX/1tbW/9fX1//Y2Nj/2dnZ/9ra2v/b29v/3Nzc/93d3f/e3t7/39/f/+Dh4f/i4uL/4+Pj/+Xl5v/k4+P/08e9/62Hav+LTyD/fDcB/3s1AP97NgD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP96NAD/jVIj/97NwP/////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/6+vv/+fn5//j4+P/29vb/9fX1//T09P/z8/P/8fLx//Dw8P/v7+//7u7u/+zt7f/r7Ov/6urq/+np6f/o6Oj/5+bn/+Xl5v/k5eX/4+Pj/+Li4v/h4eH/4N/g/9/f3//e3t7/3d3c/9zc2//b2tr/2drZ/9jY2P/X2Nj/19fW/9bW1v/V1dX/1NTU/9PT0//S0tL/0dHR/9HR0f/Q0ND/z8/P/87Ozv/Nzc7/zc3M/8zMzP/LzMz/y8vL/8rKyv/Kysr/ycnJ/8nJyf/JyMj/yMjI/8jIyP/Hx8f/x8fH/8fHx//Gxsf/x8fG/8bGxv/Gxsb/xsbG/8bGxv/Gxsb/xsbG/8bGxv/Hxsb/x8bG/8fGxv/Hx8f/x8fH/8jHx//IyMj/yMjI/8nJyP/Jycn/ysrK/8rKyv/Ky8v/y8zL/8zMzP/MzMz/zc3N/87Ozv/Pzs//0M/Q/9DQ0P/R0dH/0tLS/9PT0//T09T/1NTU/9XV1f/W1tb/19jX/9jY2P/Z2dn/2tra/9vb2//c3Nz/3t7e/97f3//f4N//4eDg/+Li4f/j4+P/5OTk/+Xl5f/n5+b/6Onp/+fm5v/Xy8P/t5d9/5ZhN/+ERBD/ezYB/3s1AP97NgD/ezYA/3w2AP98NwD/fDcA/3w3AP98NwD/fDcA/3w3AP98NgD/ezUA/3w3Av+WXzP/2ca2//7+/v///////////////////////////////////////////////////////////////////////////////////////f3+//z8/f/7+/v/+vr6//n4+f/39/j/9vb2//X19f/08/T/8vLy//Hx8f/w8PD/7+/u/+3u7v/s7Oz/6+vr/+rq6v/p6en/6Ojo/+bm5v/l5eX/5OXl/+Pj4//i4uL/4eHh/9/g4P/f39//3t7e/93d3f/c3Nz/29rb/9ra2f/Z2dn/2NjY/9fX1//W1tb/1dXV/9TU1P/T09P/09LT/9LS0v/R0dH/0NDQ/9DQ0P/Pz8//zs7O/83Nzv/Nzc3/zczM/8zMzP/Ly8v/y8vL/8rKyv/Kysr/ysrK/8nJyf/Iycn/yMjJ/8jIyP/IyMj/yMjI/8jIyP/IyMf/yMjI/8jHyP/Ix8f/yMjI/8jIyP/IyMj/yMjI/8jIyP/IyMj/yMjJ/8nJyf/Jysn/ysrK/8rKyv/Lysr/y8vL/8zLy//MzMz/zc3N/83Nzv/Ozs7/z8/P/8/Pz//Q0ND/0dHR/9LR0v/S0tL/09PT/9TU1P/V1dX/1tbW/9fW1//X19f/2NnY/9nZ2v/a2tr/29vc/9zc3P/d3t3/3t/e/+Dg4P/h4eH/4uHi/+Pj4//k5OT/5eXl/+bm5v/n5+f/6ejo/+rq6v/s7e3/7e3t/+Xg3P/Pva7/t5V6/55uR/+LTyD/hEQQ/4A+Cf99OQP/ezYA/3o0AP95MwD/ezUA/346BP+DQg7/k1su/72af//s4tv///////////////////////////////////////////////////////////////////////////////////////////////////7+//39/f/8/Pz/+/v7//r5+v/5+Pj/9/f3//b19v/09PX/8/Pz//Ly8v/x8fH/8O/w/+7u7//t7e3/7Ozs/+vr6//q6ur/6enp/+jo5//m5+b/5ebm/+Tk5P/j4+P/4uLi/+Hh4f/g4OD/39/f/97e3v/d3d3/3Nzc/9vb2//a2tr/2dnZ/9jY2P/X19f/19fW/9XV1v/V1dX/1NTU/9PT0//S09P/0tLS/9HR0f/Q0ND/0M/P/8/Oz//Ozs//zs7O/83Nzf/Nzcz/zMzM/8zMzP/Ly8v/y8vL/8rLy//Kysr/ysrK/8rKyv/Kycn/ycnJ/8nJyf/Jycn/ycnJ/8nJyf/Jycn/ycnJ/8nJyf/Jycn/ycnJ/8rJyv/Kysr/ysrK/8rKyv/Ly8v/y8vL/8zLy//MzMz/zMzM/83Nzf/Ozs7/zs7O/8/Oz//Pz8//0NDQ/9HR0P/R0dH/0tLS/9PT0//U09P/1NTU/9XV1f/W1tb/19fX/9jY2P/Y2Nj/2drZ/9ra2//c3Nz/3dzc/97d3f/e3t7/39/f/+Hh4P/i4eL/4+Lj/+Tk5P/l5eX/5ubm/+fn5//o6Oj/6enp/+vr6//s7Ov/7e3t/+7u7v/x8vP/8O/w/+vo5f/l3df/18e6/8mwnP++noX/tZF0/7GJav+wiGj/tpBz/8Kjiv/YxbX/8erk//38+/////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/8/f3/+/z8//v6+v/5+fn/+Pj4//f39v/19fX/9PT0//Pz8//y8vL/8fDw/+/v7//u7u7/7e3t/+zs7P/r6+v/6unq/+no6P/n5+f/5ubm/+Xl5f/k5OT/4+Pj/+Li4v/h4eH/4ODg/9/f3//e3t7/3d3d/9zc3P/b29v/2tra/9na2f/Z2dj/2NjY/9fW1//W1tb/1dXV/9TU1P/U1NT/09PT/9LS0v/S0tH/0dHR/9HQ0P/Q0ND/z8/P/8/Pz//Ozs7/zs7O/83Nzf/Nzc3/zMzM/8zMzP/LzMz/y8zL/8vLy//Ly8v/y8vL/8vLyv/Ly8v/y8vK/8vKyv/Lysr/y8vL/8vLy//Ly8v/y8vL/8vLy//Ly8v/y8zL/8zMzP/MzMz/zczM/83Nzf/Nzs3/zs7O/8/Ozv/Pz8//z8/P/9DQ0P/Q0ND/0dLR/9LS0v/T09P/09PT/9TU1P/V1NX/1tbW/9fW1v/X19f/2NjY/9nZ2f/a2tr/29va/9zc2//d3d3/3d7e/9/e3//g3+D/4eHh/+Li4f/j4+L/5OTk/+Xl5f/m5ub/5+fn/+jo6P/p6en/6urq/+vr7P/s7O3/7u7u/+/v7//w8PD/8vHx//Pz8//09fX/9vb3//f4+P/5+vr/+vv8//v9/f/9/v7//v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+///9/f7//Pz8//v7+//6+vr/+fn5//f39//29vb/9fX1//T09P/z8/P/8fLx//Dw8P/v7+//7u7u/+3t7f/s7Oz/6+rr/+rp6f/o6ej/5+fn/+bm5v/l5eX/5OTk/+Pj4//i4uL/4eHh/+Dg4P/f39//3t7f/93d3f/c3Nz/3Nvb/9vb2//a2tn/2dnZ/9jY2P/X19f/1tbX/9bW1v/V1dX/1NTU/9TU0//T09P/0tLS/9HS0v/R0dH/0dHR/9DQ0P/Qz9D/z8/P/8/Pz//Ozs7/zs7O/83Ozv/Nzc3/zc3N/83Nzf/MzMz/zMzM/8zMzP/MzMz/zMzM/8zMzP/MzMz/zczM/8zMzP/MzMz/zczM/83Nzf/Nzc3/zc3N/83Nzf/Ozs7/zs7O/87Pzv/Pz8//z9DP/9DQ0P/Q0ND/0dHR/9LS0f/S0tL/0tPT/9PT0//U1NT/1dXV/9XW1f/W1tb/19fX/9jY1//Z2dj/2tnZ/9ra2v/b29v/3Nzc/93d3f/e3t7/39/f/+Dg4P/h4eH/4uLi/+Pj4//k5OT/5eXl/+bm5v/n5+f/6Ojo/+np6f/r6ur/6+vr/+zs7f/t7e7/7+/v//Dw8P/x8fH/8vLy//Tz8//19fT/9vb2//f39//4+Pj/+fn5//v7+//8/Pz//f39//7+/v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+vv/+fr6//j4+P/39/f/9vb2//X19f/09PT/8/Lz//Hx8v/w8PD/7+/v/+7u7v/t7e3/6+zs/+vr6v/p6un/6Ono/+fn6P/m5uf/5ebl/+Tk5P/j5OP/4+Li/+Hh4f/g4OD/39/f/97e3v/d3t3/3d3d/9zc2//b29v/2tra/9nZ2f/Z2Nj/19jY/9fX1//W1tb/1tbV/9XV1f/U1NT/1NPU/9PT0//S0tL/0tLS/9LS0f/R0dH/0NDQ/9DQ0P/Pz9D/z8/P/8/Pz//Pz8//zs7O/87Ozv/Ozs7/zc7O/87Ozv/Ozs7/zc3N/83Nzf/Ozc7/zs3N/87Ozf/Ozc7/zs7O/87Ozv/Ozs7/z87P/8/Pz//Pz8//0NDQ/9DQ0P/Q0ND/0dHR/9HR0f/S0tH/0tLS/9PT0//T09P/1NTU/9XV1f/W1dX/1tbW/9fX1//Y2Nf/2NjY/9nZ2f/a2tr/29vb/9vb2//c3Nz/3d3d/97e3v/f39//4ODg/+Hh4f/i4uL/4+Pj/+Tk5P/l5eX/5ubm/+fn5//o6Oj/6enp/+rq6v/r6+v/7Ozs/+3t7v/u7+7/8PDv//Hx8f/y8vL/8/Pz//X09P/29vb/9/f3//j4+P/5+fn/+vr6//z8/P/9/f3//v7+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+vr6//n5+f/4+Pj/9/f3//b29v/09fX/8/Pz//Ly8v/x8fH/8PDw/+/v7//u7u7/7e3t/+zs7P/r6+v/6enq/+no6P/n6Oj/5ufm/+Xl5f/k5OT/4+Pj/+Pi4v/i4eL/4ODh/+Dg3//f39//3t7e/93d3f/c3Nz/3Nvc/9rb2//a2tr/2dnZ/9jY2P/X2Nj/19fX/9bW1v/W1db/1dXV/9TU1P/U1NT/09PT/9PT0//S09L/0tLS/9LR0f/R0dH/0dHQ/9DR0P/Q0ND/0NDQ/9DQz//Qz9D/z8/P/8/Qz//Pz8//z8/P/8/Pz//Pz8//z8/P/8/Qz//Pz8//z8/Q/9DQ0P/Q0ND/0NDQ/9DR0P/R0dH/0dHR/9HR0f/S0tL/0tLS/9PT0//T09P/09TT/9TU1f/V1dX/1dbV/9bW1v/X19b/19fX/9jY2P/Z2dn/2dna/9ra2v/b29v/3Nzc/93d3f/e3t3/3t/e/9/f4P/g4OD/4eHh/+Li4v/j4+P/5OTk/+Xl5f/m5ub/5+fn/+jo6P/p6en/6urq/+vr6//s7Oz/7e7t/+7v7v/v8O//8fHx//Ly8v/z8/P/9PT0//X19f/29vf/9/f3//n5+f/6+vr/+/v7//z9/P/+/v7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/fz/+/v7//r6+v/5+fn/+Pj4//f29//29fX/9PT0//Pz8//y8vL/8fHx//Dw8P/v7+//7u7u/+3t7f/s7Ov/6+rq/+np6v/o6en/5+fo/+bm5//l5eX/5eXk/+Pk4//j4+P/4uLi/+Hh4f/g4OD/39/f/97e3//d3d7/3d3d/9zc3P/b29v/2tva/9ra2f/Z2dn/2NjY/9fY2P/X19f/1tbX/9bW1v/V1dX/1dXV/9TV1f/U1NT/09PT/9PT0//T09P/09LS/9LS0v/S0tL/0dLS/9HR0f/R0dH/0dHR/9HR0f/R0NH/0dHQ/9DR0f/Q0dH/0dHQ/9HR0f/R0dH/0dHR/9HR0f/R0dH/0dLS/9LS0v/S0tL/0tPT/9PT0//U1NP/1NTU/9TU1P/V1NT/1dXV/9bW1v/W19b/19fX/9fX1//Y2Nj/2dnZ/9na2f/a2tr/29vb/9vb3P/c3Nz/3d3d/97e3v/f39//4ODg/+Dg4f/h4eH/4+Pj/+Tj4//k5OT/5eXl/+bm5v/n5+f/6Ojo/+np6f/q6ur/6+vr/+zs7P/t7e3/7+/v//Dv7//x8PH/8vLy//Pz8//09PT/9fX1//b29v/39/j/+fn4//r6+v/7+/v//Pz8//39/f/+/v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v3//Pz8//v7+//6+vr/+fn4//f39//29vb/9fX1//T09P/z8/P/8vLy//Hx8f/w8PD/7+/v/+7u7v/t7ez/7Ozs/+rr6//q6ur/6enp/+jo6P/n5+b/5ubm/+Xl5f/k5OT/4+Pj/+Li4v/h4eH/4eDg/+Df4P/f39//3t7e/93d3f/c3Nz/3Nzc/9vb2//a2tv/2tna/9nZ2f/Y2Nn/2NfY/9fX1//X19f/1tbW/9bW1v/V1dX/1dXV/9TU1P/U1NT/1NTT/9TU0//T09P/09PT/9PT0//S09P/0tLS/9LS0v/S0tL/0tLS/9LS0v/S0tL/0tLS/9LS0v/S0tL/0tLS/9LT0v/T09P/09PT/9PT0//T1NT/1NTU/9TU1P/V1dX/1dXV/9XV1f/W1tb/19bW/9fX1//X2Nf/2NjY/9nY2f/Z2dn/2tra/9vb2//b29z/3Nzc/93d3P/d3d3/3t7e/9/f3//g4OD/4eHh/+Li4v/j4+P/5OTj/+Tl5P/l5eX/5ubn/+fn5//o6ej/6enp/+vq6v/r6+v/7Ozs/+3t7f/u7u7/7+/w//Hw8P/y8fL/8/Pz//T09P/19fX/9vb2//f39//4+Pj/+vr6//r7+//8/Pz//f39//7+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+/v/+vr6//n5+P/3+Pf/9vb2//X19f/09PT/8/Pz//Ly8v/x8fH/8PDw/+/v7//u7u7/7ezt/+zs7P/r6+v/6unq/+no6f/o6Oj/5+fn/+bm5v/l5eX/5OTl/+Pj4//i4+L/4uLi/+Hh4f/g4OD/39/f/97e3v/e3t7/3d3d/9zc3P/c3Nz/29vb/9ra2v/a2tr/2dnZ/9nZ2P/Y2Nj/2NjY/9fX1//W19f/1tbW/9bW1f/V1dX/1dXV/9XV1f/V1NX/1dTU/9TU1P/U1NT/1NTU/9TU1P/U1NT/09TT/9PU0//T1NT/09TU/9TT1P/U1NT/1NTU/9TU1P/U1NT/1NTU/9XU1f/V1dX/1dbW/9XW1v/W1tb/19fW/9fX1//Y19f/2NjY/9jZ2P/Z2dn/2dnZ/9ra2v/b29v/29vb/9zc3P/d3d3/3t3d/97e3v/f39//4N/f/+Dg4P/h4eH/4uLi/+Pj4//k5OT/5eXl/+bm5v/n5+f/6Ofn/+jo6P/p6en/6urq/+zs6//s7O3/7e7t/+7v7//w7+//8fDx//Hy8f/y8vP/9PT0//X19f/29vb/9/f3//j4+P/6+fn/+/v7//v8/P/9/f3//v7+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/v6//n6+v/4+fn/+Pf4//b29//19fb/9PT0//Pz8//y8vL/8fHx//Dw8P/v7+//7u7u/+3t7f/s7Oz/6+vr/+rq6v/p6en/6Ojo/+fn5//m5ub/5eXm/+Xk5f/k5OT/4+Pj/+Li4v/h4eH/4eHh/+Dg4P/f39//3t7e/97e3v/d3d3/3Nzc/9zc3P/b29v/29vb/9ra2v/Z2tn/2dnZ/9nZ2P/Y2Nj/2NjY/9fX1//X19f/19fX/9bX1//W1tb/1tbW/9bW1v/W1dX/1dXW/9XV1f/V1dX/1dXV/9XV1f/V1tX/1dXV/9XV1f/V1dX/1tXV/9bV1f/W1tb/1tbW/9bW1v/W1tb/19fX/9fX1//Y2Nf/2NjY/9nY2P/Z2dn/2dnZ/9ra2v/a29v/29vb/9vc3P/c3Nz/3d3d/93e3f/e3t7/39/f/9/f3//g4OD/4eHh/+Li4f/j4+L/4+Tj/+Tl5P/l5eX/5ubm/+fn5//o6Oj/6enp/+rp6v/r6ur/7Ozs/+zt7P/t7u3/7u/u//Dw8P/x8fD/8vHy//Py8//09PP/9fX1//b29v/39/f/+Pj4//n5+f/7+vr/+/z7//z8/f/+/v7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v7+//6+fr/+Pn5//f3+P/29vb/9fX1//T09P/z8/P/8vLy//Hx8f/w8PD/7+/v/+7u7v/t7e3/7Ozs/+vr6//q6ur/6enp/+jp6P/o6Oj/5ufn/+bm5v/l5eX/5OTk/+Pj4//j4uP/4uLi/+Hh4f/g4OD/4N/g/9/f3//e3t7/3t7d/93d3f/d3N3/3Nzc/9zc2//b29v/2trb/9ra2v/a2dn/2dnZ/9nZ2f/Y2Nj/2NjY/9jY2P/Y2Nj/19fX/9fX1//X19f/1tfX/9bW1//X19f/1tbX/9bX1v/W19b/19fW/9fX1v/X19f/19fX/9fX1//X19f/2NfX/9jY2P/Y2Nj/2NjY/9nZ2P/Z2dn/2dnZ/9ra2v/a2tr/29vb/9vb2//b3Nz/3Nzc/93d3f/d3d7/3t7e/9/f3//f39//4ODg/+Hh4f/i4uH/4uLi/+Pj4//k5OT/5OXl/+bl5v/m5ub/5+fn/+jo6P/p6en/6urq/+vr6v/s7Ov/7e3t/+3t7v/u7+//7/Dw//Hx8f/y8vL/8/Lz//T09P/19fX/9vb2//f39//4+Pj/+fn5//r6+v/7+/z//Pz9//79/v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/6+vv/+fn5//j4+P/49/f/9vf2//X19f/09PT/8/Pz//Ly8v/x8fH/8PDw/+/v7//u7u7/7e3t/+zs7P/s6+v/6uvr/+rq6v/p6en/6Ojo/+fn5//m5ub/5eXl/+Xl5P/k5OT/4+Pj/+Lj4v/i4uL/4eHh/+Dh4f/f4OD/39/f/9/e3v/e3t7/3d7d/93d3f/c3Nz/3Nzc/9vb2//b29v/29vb/9vb2//a2tr/2trZ/9nZ2f/Z2dn/2dnZ/9nY2P/Y2dj/2NjZ/9jY2P/Y2Nj/2NjY/9jY2P/Y2Nj/2NjY/9jY2P/Y2Nn/2djZ/9nZ2P/Z2dn/2dnZ/9nZ2f/Z2tn/2tra/9ra2v/a2tv/29vb/9vc2//c3Nz/3Nzc/93c3f/d3d3/3t7d/9/e3v/f39//4N/g/+Dg4P/g4eH/4eHh/+Li4v/j4+P/5OPk/+Tk5f/l5eX/5ubm/+fn5//o5+j/6Ono/+np6f/q6ur/6+vr/+zs7P/t7e3/7u7u/+/v7//w8PD/8fHw//Ly8v/z8/P/9PT0//X19f/29vb/9/f3//j4+P/5+fn/+vv6//v7+//8/Pz//f39//7+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/P/8/Pv/+/r6//r6+f/5+Pj/9/j3//b29v/19fX/9fT0//Pz8//y8vL/8vHx//Hw8f/v7+//7+7u/+7t7v/t7e3/7Ozs/+vr6//q6ur/6enp/+jo6P/o5+j/5+fn/+bm5v/l5eX/5eXl/+Tk4//j4+P/4uLj/+Lh4v/h4eH/4eHg/+Dg4P/f39//39/f/97f3v/e3t7/3t3d/93d3f/c3dz/3Nzc/9zc3P/b3Nv/29zb/9vb2//b2tv/2tra/9ra2v/a2tr/2tra/9ra2v/a2tr/2dra/9ra2v/a2tr/2tra/9ra2v/a2tr/2tra/9ra2v/b2tr/29rb/9vb2//b29v/29vb/9vc3P/c3Nz/3dzd/93d3f/d3d3/3t7d/97e3v/e3t7/39/f/+Dg4P/g4eD/4eHh/+Li4f/i4uL/4+Pj/+Tk4//k5OT/5eXl/+bm5v/m5ub/5+fn/+jo6P/p6en/6urq/+vq6//s6+z/7ezs/+3t7f/u7u7/7+/v//Dw8P/x8fH/8vLy//Pz8//09PT/9fX1//b29v/39/f/+Pj4//n5+f/6+vr/+/v7//z8/P/+/f3//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/f/9/fz/+/z7//v6+//6+fr/+Pj5//j49//29vb/9vb1//T19P/08/P/8/Py//Ly8v/w8PD/8PDv/+/v7//u7u7/7e3t/+zs7P/r6+v/6uvq/+rq6f/p6en/6Ojo/+fn5//m5+f/5ubm/+Xl5f/k5eT/5OTk/+Pj4//i4uL/4uLi/+Hh4f/h4eH/4ODg/+Dg4P/f39//39/e/97e3v/e3t7/3t7e/93d3f/d3d3/3N3c/9zc3P/c3Nz/3Nzc/9zc3P/c29z/29vb/9vb2//b29v/29vb/9vb2//b29v/29vb/9vb2//b29v/29vb/9vb2//c3Nz/3Nzc/9zc3P/c3d3/3d3d/93d3f/e3d3/3t7e/97e3v/f3t//39/f/+Df4P/g4OD/4eHg/+Hh4f/h4uL/4uLi/+Pj4//k4+P/5OTk/+Xl5f/m5eb/5ubm/+fn5//n6Oj/6ejp/+np6f/q6ur/6+vr/+zs7P/t7ez/7e3u/+/u7v/w7+//8PDw//Hx8f/y8vL/8/Pz//T09P/19fX/9vb2//f39//4+Pj/+fn5//r6+v/7+/v//Pz9//39/f/+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v/+/v7//Pz9//z7+//6+vr/+fn6//n5+f/4+Pj/9vf2//b29v/19fT/9PTz//Lz8//y8vL/8fHx//Dw8P/v7+//7u7u/+7t7f/t7e3/7Ozs/+vr6//q6ur/6enp/+np6f/o6Oj/5+fn/+bn5v/m5ub/5eXl/+Tk5f/k5OT/4+Pj/+Pj4//i4uL/4uLi/+Hh4f/h4eH/4ODg/+Dg4P/f4N//39/f/9/f3//e39//3t7e/97e3v/e3t7/3d3e/93d3f/d3d3/3dzd/93c3f/d3N3/3d3d/93d3f/d3d3/3N3d/93d3f/d3d3/3d3d/93d3f/d3d3/3d3d/97d3v/e3t7/3t7e/9/f3//f39//39/f/+Df4P/g4OD/4ODg/+Hh4f/i4uL/4uLi/+Pj4v/j4+P/5OPj/+Tk5P/l5eX/5ebl/+bm5v/n5+f/6Ojo/+jo6P/p6en/6urq/+vr6//s6+v/7Ozs/+3t7f/u7u7/7u/v//Dw8P/x8PH/8vHx//Ly8v/z8/T/9PT0//X19f/29vb/+Pf3//j4+P/5+fn/+vr6//v7+//8/Pz//f7+//7+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/r7//r6+v/5+fj/+Pf4//f39//29vb/9fX1//T09P/z8/P/8vLy//Hx8f/w8PD/7+/v/+/u7v/u7e7/7e3t/+zs7P/s6+z/6+vr/+rq6v/p6en/6ejo/+jo6P/n5+f/5ubm/+bm5v/l5eX/5eXl/+Tk5P/k5OT/4+Pj/+Pi4//i4uL/4uLh/+Hh4f/h4eH/4eHh/+Dg4P/g4OD/3+Df/9/f3//f39//39/f/97f3//e3t7/3t/e/97e3v/e3t7/3t/e/97e3v/e3t7/3t7e/97e3//e3t7/397e/9/e3//f39//39/f/+Df3//g39//4ODg/+Dg4P/h4OD/4eHh/+Hh4f/h4eL/4uLi/+Pi4v/j4+P/5OPj/+Tk5P/k5OX/5eXl/+bl5f/m5ub/5+fn/+jo5//o6Oj/6enp/+np6v/q6+r/6+vr/+zs7P/t7ez/7u7t/+7u7v/v7+//8PDw//Hx8f/y8vL/8/Pz//T08//19fT/9vb1//f39v/39/f/+Pj4//n5+f/6+vr/+/v7//38/P/9/f3//v/+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+//7+/v/9/f3//Pv8//v7+//6+vr/+fn5//j4+P/39/f/9vb2//X19f/09PT/8/Pz//Ly8v/y8fH/8fDx//Dw8P/v7+//7u7u/+7t7f/t7e3/7Ozs/+vr6//r6ur/6urq/+np6f/o6Oj/6Ojo/+fn5//m5uf/5ubm/+Xl5v/l5eX/5OXl/+Tk5P/j4+T/4+Pj/+Pi4//j4uL/4uLi/+Li4v/h4eH/4eHh/+Hh4f/h4OD/4ODg/+Dg4P/g3+D/4ODg/+Dg4P/g4OD/4ODg/+Dg4P/g4OD/4ODg/+Dg4P/g4OD/4ODg/+Dg4P/g4OD/4OHh/+Hh4f/h4eD/4eHh/+Hh4f/i4uL/4uLi/+Lj4v/j4+P/4+Pk/+Tk5P/k5OT/5eXl/+Xl5v/m5ub/5ubm/+fn5//o6Oj/6Ojo/+np6f/q6er/6urq/+rr6//s7Oz/7Ozt/+3t7f/u7u7/7+/v//Dv7//w8fD/8fHx//Ly8v/z8/P/9PT0//X19f/29vb/9vf3//j3+P/4+Pn/+fr6//v7+v/7/Pv//P38//39/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z8/P/7+/v/+vr6//n5+f/4+Pj/9/f3//b29v/19fX/9PT0//P09P/z8/P/8vLy//Hx8f/w8PD/7/Dv/+/v7//u7u7/7e7t/+3s7P/s7Oz/6+vr/+rq6//q6ur/6enp/+np6f/o6Oj/6Ojo/+fn5//m5+f/5ubm/+Xl5f/l5eX/5eTl/+Tk5P/k5OT/5OPk/+Pj4//j4+P/4uLj/+Li4//i4uL/4uLi/+Li4f/h4eL/4eHi/+Hh4f/h4eH/4eHh/+Hh4f/h4eH/4eHh/+Hh4f/h4eH/4eHh/+Lh4f/i4uL/4uLi/+Li4v/i4uP/4uPj/+Pj4//j4+P/5OTj/+Tk5P/k5OT/5eXl/+Xl5f/m5ub/5ubm/+fm5//n5+f/6Ojo/+jp6P/p6en/6enp/+rq6v/r6+v/7Ozs/+zs7P/t7e3/7u7u/+7u7//v7+//8PDw//Hx8f/y8fL/8vLy//Pz8//09PT/9fX1//b29v/39/f/+Pj4//n5+f/6+vr/+/v7//z8/P/8/fz//f79//7//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//39/f/8/Pz/+/v7//r6+v/5+fn/+Pj5//f4+P/39/b/9vX2//X19f/09PT/8/Tz//Ly8v/y8vH/8fHx//Dw8P/v7/D/7+7v/+7u7v/t7e3/7ezs/+zs7P/r6+v/6+vr/+rq6v/p6en/6enp/+jo6P/o6Oj/5+fn/+fn5//n5ub/5ubm/+bm5f/l5eX/5eXl/+Xl5P/k5eT/5OTk/+Tk5P/j5OT/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j5OP/5OTk/+Tk5P/k5OT/5OTk/+Tk5P/l5OX/5eXl/+bl5f/m5ub/5+bm/+fn5//n5+f/6Ofo/+jo6P/o6en/6enq/+rq6v/q6ur/6+vr/+zs7P/s7O3/7e3t/+7u7v/u7u7/7+/v//Dw8P/w8fH/8fHx//Ly8v/z8/P/9PT0//T19f/19fX/9vb2//f39//4+Pj/+fn5//r6+v/7+/v//Pz7//39/f/+/v7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//fz8//v7+//6+/r/+vr6//n5+f/4+Pj/9/f3//b29v/19fX/9fX0//T09P/z8/P/8vLy//Hx8f/x8fH/8PDw/+/v7//u7+//7u7u/+3t7v/s7e3/7Ozs/+vr7P/r6+v/6urq/+rp6v/p6er/6enp/+np6P/o6Oj/5+fn/+fn5//m5uf/5ubm/+bm5v/m5eb/5uXl/+Xl5f/l5eX/5eXl/+Tl5P/k5OT/5OTk/+Tk5P/k5OT/5OTk/+Tk5P/k5OT/5OTk/+Tk5P/k5OT/5OXk/+Tl5P/l5eX/5eXl/+Xl5f/l5eb/5ebl/+bm5v/m5ub/5+bn/+fn5//n5+f/6Ojo/+jo6P/p6en/6enp/+np6f/q6ur/6uvr/+vr6//s7Oz/7O3t/+3t7f/t7e7/7u7u/+/v7//w8PD/8PDw//Hx8f/y8vL/8/Lz//Pz8//09PT/9fX1//X29v/39vf/9/f4//j4+P/5+fn/+vr6//v7+//8/Pz//f39//7+/v/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//39/f/8/Pz/+/v7//r6+v/5+fn/+Pj4//j39//39/b/9vX2//X19f/09PT/8/Tz//Pz8//y8vL/8fHx//Dx8P/w8PD/7+/v/+/v7//u7u7/7e3t/+3t7f/s7ez/6+zs/+vr6//r6+v/6urr/+rq6v/p6en/6enp/+jp6f/o6Oj/6Ojo/+jo6P/n5+f/5+fn/+bm5//n5uf/5ubm/+bm5v/m5ub/5ubm/+bm5v/m5ub/5uXm/+bl5v/l5ub/5ebm/+bm5v/m5ub/5ubm/+bm5v/m5ub/5+bn/+fn5v/n5+f/5+fn/+fo6P/n6Of/6Ojo/+jo6P/o6en/6enp/+rp6v/q6ur/6+vq/+vr6//r7Ov/7Ozs/+zs7f/t7e3/7e7u/+7u7v/v7+//8O/w//Dw8P/x8fH/8fLx//Py8v/z8/P/9PT0//X19f/19fX/9vb2//f39//4+Pj/+fn5//n5+v/7+/r//Pv7//z8/P/9/f3//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//Pz8//v7+//6+vv/+fr6//n5+f/4+Pj/9/f3//b29v/29vX/9fX0//T09P/z8/P/8vPz//Ly8v/x8fH/8fHw//Dw8P/v7+//7+/v/+7u7v/u7u7/7e3t/+zs7f/s7Oz/7Ozs/+vr6//r6+v/6uvr/+rq6v/q6ur/6enp/+np6f/p6en/6ejp/+jo6P/o6Oj/6Ojo/+fo6P/o6Of/6Ojn/+jn5//o5+f/5+fn/+fn5//n5+f/5+fn/+fn6P/n5+j/5+fo/+fn6P/o6Oj/6Ojo/+jo6P/o6ej/6enp/+np6f/p6en/6unq/+rq6v/q6ur/6+rr/+vr6//r7Ov/7Ozs/+3s7P/t7e3/7e3u/+7u7v/u7u//7+/v//Dw8P/w8fD/8fHx//Ly8v/z8vL/8/Pz//P09P/09fT/9fX1//b29v/39/f/9/j4//j4+P/5+fn/+vr6//v7+//8/Pv//fz8//39/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f79//z8/f/7/Pz/+/v7//r6+v/5+fn/+Pj4//f49//39/f/9vb2//X19f/19fX/9PT0//Pz8//y8/P/8vLy//Hx8f/x8PH/8PDw//Dw7//v7+//7+7v/+7u7v/u7u3/7e3t/+3t7f/s7Oz/7Ozs/+vr6//r6+v/6+vr/+vq6//q6ur/6urq/+rq6v/q6un/6enp/+np6f/p6en/6eno/+np6f/p6ej/6enp/+np6f/o6en/6ejp/+np6f/p6en/6enp/+np6f/p6en/6unp/+rp6v/q6ur/6urq/+rq6v/r6uv/6+vr/+vr6//s6+z/7Ozs/+3s7P/t7e3/7e3t/+7u7v/u7u//7+/v/+/w7//w8PD/8PDx//Hx8f/y8fH/8/Ly//Pz8//09PT/9PT0//X19f/19vX/9vf2//f39//4+Pj/+fn5//r5+v/7+vr/+/v7//z8/P/9/f3//v7+///+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7///39/v/9/f3//Pz8//v7+//6+vr/+fr6//n5+f/4+Pj/9/f3//f39//29vb/9fX1//X19f/09PT/8/Pz//Pz8//y8vL/8fHy//Hx8f/w8PD/8PDw/+/v7//v7+//7+/u/+7u7v/u7u7/7e3t/+3t7f/s7ez/7ezs/+zs7P/s7Ov/6+zr/+vr6//r6+v/6+vr/+vr6//r6+v/6+rq/+rq6v/q6ur/6+rq/+rq6v/q6ur/6urq/+rq6v/q6ur/6urq/+rq6v/r6+v/6+vr/+vr6//r6+v/7Ozs/+zs7P/s7Oz/7O3s/+3t7f/t7e3/7e3t/+7u7v/u7+7/7+/v/+/v7//w7+//8PDw//Hx8f/x8vL/8vLy//Lz8v/z8/P/9PT0//X09f/19fX/9vb2//b29v/39/f/+Pj4//n5+f/6+vn/+vr6//v7+//8/Pz//P38//7+/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//f39//z9/f/8/Pz/+/v7//r6+v/5+vn/+fn4//j4+P/39/f/9/f3//b29v/19fb/9fX1//T09P/z9PT/8/Pz//Ly8v/y8vL/8fHx//Hx8f/x8PD/8PDw//Dw7//v7+//7+/v/+7v7v/u7u7/7u7u/+3t7f/t7e3/7e3t/+3t7f/s7Oz/7ezs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozs/+zs7P/s7Oz/7Ozs/+zs7f/t7e3/7e3t/+7t7f/u7u7/7u7u/+7u7v/v7+//7+/v/+/v8P/w8PD/8PHw//Hx8f/x8fH/8vLy//Ly8v/z8/P/8/Pz//T09P/09fT/9fX1//b29v/39/b/9/f3//j4+P/4+Pj/+fn5//r6+v/7+/v/+/z7//z8/P/9/f3//v7+/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v/+//7+/v/9/f3//Pz8//v7/P/7+/v/+vr6//n5+f/5+fn/+Pj4//j49//39/f/9vb2//b19f/19fX/9PT0//T09P/08/P/8/Pz//Ly8v/y8vL/8fHy//Hx8f/w8fH/8PDw//Dw8P/w8O//7+/v/+/v7//u7u//7u7v/+7u7v/u7u7/7u7u/+7u7f/u7u3/7u3t/+3t7f/t7e3/7e3t/+3t7f/t7e3/7e3t/+3t7f/t7u3/7e7t/+3u7f/u7u3/7u7u/+7u7v/u7u7/7+/v/+/v7//v7+//7+/v//Dw8P/w8PD/8PDw//Hx8f/x8fH/8fLy//Ly8v/z8vP/8/Pz//T08//09PT/9fX0//X19f/29vb/9vb2//f39//4+Pj/+fj4//n5+f/5+vr/+vr7//v7+//8/Pz//f39//39/f/+/v7////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//v79//39/f/8/Pz//Pv7//v6+//6+vr/+fn5//n5+f/4+Pj/+Pj3//f39//39vb/9vb2//X19f/19fX/9PT0//T09P/z8/P/8/Py//Lz8//y8vL/8vHy//Hx8v/x8fH/8PDx//Dw8P/w8PD/8PDw//Dw8P/w7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//8O/w//Dv8P/w7/D/8PDw//Dw8P/x8PD/8fHx//Hx8f/x8fL/8vLy//Ly8//y8/P/8/Pz//T09P/09PT/9fT0//X19f/29vb/9vb2//f39//39/f/+Pj4//j4+P/5+fn/+vr6//v7+v/7+/v//Pz8//z8/P/9/f3//v7+//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/9/f3//f39//z8/P/7/Pz/+/v7//r6+v/6+fn/+fn5//j4+P/4+Pf/+Pf3//f39//29vb/9vb2//b19f/19fX/9PT0//T09P/z8/P/8/Pz//Pz8//y8vP/8vLy//Ly8v/y8vH/8fHy//Hx8f/x8fH/8fHx//Hx8f/w8fD/8PHw//Hx8P/w8fD/8PDw//Dw8P/w8fD/8PDw//Hw8P/x8PD/8PHx//Hx8f/x8fH/8fHx//Hx8f/x8fL/8vLy//Ly8v/y8vL/8vLy//Lz8//z8/P/8/P0//T09P/09PT/9fX0//X19f/29vb/9vb2//f29//39/f/+Pf4//j4+P/4+fn/+fn5//r6+v/7+vr/+/v7//z8/P/9/f3//f39//7+/v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//7+/f/9/f3//Pz8//z7+//7+/v/+vr6//r6+v/5+fn/+fj4//j4+P/3+Pj/9/f3//b29//29vb/9vb2//X19f/19fX/9fX0//T09P/09PT/9PP0//Pz8//z8/P/8/Pz//Pz8//y8vL/8vLy//Ly8v/y8vL/8vLy//Ly8v/y8vL/8vLy//Ly8v/x8vL/8vLy//Ly8v/y8vL/8vLy//Ly8v/y8vL/8vLy//Pz8v/z8/P/8/Pz//Pz8//z8/P/9PT0//T09P/19PT/9fX1//X19f/29fX/9vb2//f39//39/f/9/f3//j4+P/4+fj/+fn5//n6+v/6+vr/+/v7//v7+//8/Pz//fz8//39/f/+/v7///7+///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+/v7//v7+//39/f/8/Pz//Pz8//v7+//7+/v/+vr6//n5+f/5+fn/+fj5//j4+P/4+Pf/9/f3//f39//29vb/9vb2//X29v/19fX/9fX1//X19f/09fX/9PX0//T09P/09PT/9PT0//T09P/z8/P/8/Tz//P08//z8/T/8/Pz//Pz8//z9PP/8/Pz//Pz8//08/T/8/P0//T08//09PP/9PT0//T09P/19fT/9fX0//X19f/19fX/9fX1//X19f/29vb/9vb2//f39//39/f/+Pj3//j4+P/4+Pn/+fn4//n5+f/6+vn/+vr6//v7+//7+/z//Pz8//39/f/9/f3//v7+//7+/v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+/v/+/v7//f39//38/f/8/Pz//Pz8//v7+//6+vr/+vr6//r6+v/5+fn/+fn5//j4+P/4+Pj/+Pj3//f49//39/f/9/f3//b29//29vf/9vb2//b29v/19vX/9fb1//X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/19fX/9fX1//X19f/29vb/9vb2//b29v/29/b/9/f3//f39//3+Pf/+Pj4//j4+P/5+Pn/+fn5//r5+v/6+vr/+vr6//v7+//7+/v/+/z8//z8/P/9/f3//f39//7+/v////7//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v/+//7+/v/9/f3//f39//38/P/8/Pz/+/v7//v7+//7+/r/+vr6//r6+v/5+fr/+fn5//n5+f/4+Pj/+Pj4//j4+P/49/j/9/f3//f39//39/f/9/f3//f39v/39/f/9/b2//b29v/29vb/9vb2//b29v/29vb/9vb2//b29v/29/f/9/f2//f39v/39/f/9/f3//f39//39/f/+Pf3//j4+P/4+Pj/+Pj4//j4+f/5+fn/+fn5//r5+v/6+vr/+vr6//v7+//7+/v//Pv8//z8/P/8/f3//f39//3+/v/+/v7//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7///7+/v/9/v3//f39//38/P/8/Pz//Pz8//v7+//7+vv/+/r6//r6+v/6+vr/+vr6//n6+f/5+fn/+fj5//n4+f/4+fn/+Pn4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj4//j4+P/4+Pj/+Pj3//j4+P/4+Pj/+Pj4//j4+P/4+fj/+Pj4//j4+P/5+fn/+fn5//n5+f/6+vr/+vr6//r6+v/6+/r/+/v7//v7+//7+/v//Pz8//z8/P/8/f3//f39//3+/v/+/v7//v///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+//7+/v/+/v7//f39//39/f/8/P3//Pz8//z8/P/7+/v/+/v7//v7+//6+vv/+vr6//r6+v/6+vr/+vr6//r6+v/6+vr/+fr6//n6+v/5+fr/+fn5//n5+f/5+fn/+fn5//r5+v/6+fr/+fr5//r6+v/6+vr/+vr6//r6+v/7+vr/+/v6//v7+//7+/v/+/v7//z7/P/8/Pz//Pz8//39/f/9/f3//f39//7+/v/+/v7//v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+//7+/v/+/f7//f3+//39/f/9/f3//fz9//z8/P/8/Pz//Pz8//z7/P/7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+vv/+/v6//v7+v/7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7/P/8+/v//Pz8//z8/P/8/Pz//f38//39/f/9/f3//v3+//7+/v/+//7//v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7+///+/v///v7+//7+/v/9/f7//f79//39/f/9/f3//f39//39/f/9/fz//P38//z8/f/8/Pz//fz8//38/P/9/Pz//fz8//z8/P/8/fz//f39//39/f/9/f3//f39//39/f/9/f3//v79//7+/v/+/v7//v7+//7//v////7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7////+//7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+//7+/v/+/v7//v7+/////v////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="""
		icondata= base64.b64decode(icon)
		## The temp file is icon.ico
		tempFile= "icon.ico"
		iconfile= open(tempFile,"wb")
		## Extract the icon
		iconfile.write(icondata)
		iconfile.close()
		self.root.wm_iconbitmap(tempFile)
		## Delete the tempfile
		os.remove(tempFile)


		back = Frame(master=self.root,bg=COLOR_BACKGROUND)
		back.pack_propagate(0) #Don't allow the widgets inside to determine the frame's width / height
		back.pack(fill=BOTH, expand=YES) #Expand the frame to fill the root window

		log_label = Label(back,text="Output Log:",foreground="white",background=COLOR_BACKGROUND,anchor="w")
		log_label.pack(side=TOP, fill=X)

		self.log=scrollTxtArea(back)

		#loadimage = ImageTk.PhotoImage(Image.open("UISprite.png"))  # PIL solution

		lower = Frame(master=self.root, bg=COLOR_BACKGROUND)
		lower.pack(side=BOTTOM, fill=X) #Expand the frame to fill the root window

		selectionType = Frame(master=lower, bg=COLOR_BACKGROUND)
		selectionType.pack(side=TOP, fill=X) #Expand the frame to fill the root window

		# Create a Tkinter variable - https://pythonspot.com/tk-dropdown-example/
		self.tkvar = StringVar(self.root)
		self.choices = [
			'Avatar',
			'Prop',
			#'Scene'
		]

		self.blendScripts = [
			blenderscript_avatar,
			blenderscript_prop,
			blenderscript_scene
		]
		self.choicesInfo = [
			"Select the .blend file containing a .mhx2 model to create AnimPrep avatar project files.",
			"Select the .blend file containing a prop model to create AnimPrep prop project files.",
			"Select the .blend file containing a scene model to create AnimPrep scene project files."
		]

		self.tkvar.set('Avatar') # set the default option

		self.popupMenu = OptionMenu(selectionType, self.tkvar, *self.choices)
		self.popupMenu.config(width=5, bg=COLOR_BACKGROUND, fg="white")
		self.popupMenu["highlightthickness"]=0
		self.popupMenu.grid(row=0, column=0, sticky=W, padx=5)

		self.button_label = Label(selectionType, height=2,foreground="white",background=COLOR_BACKGROUND,anchor="center")
		self.button_label.grid(row=0, column=1)
		self.change_dropdown(False) #initialize the text for the button_label



		self.selectbutton = Button(lower, text="SELECT MODEL", background=COLOR_GREEN, foreground="white", command=self.browse_file, font = ('times', 12, 'bold'))
		self.selectbutton.pack()

		separator = Frame(master=lower, height=2, bd=1, relief=SUNKEN)
		separator.pack(fill=X, padx=5, pady=10)

		browser = Frame(master=lower, bg=COLOR_BACKGROUND)
		browser.pack(side=BOTTOM, fill=X) #Expand the frame to fill the root window

		blender_label = Label(browser,text="Blender Path:",foreground="white",background=COLOR_BACKGROUND,anchor="w")
		blender_label.grid(row=0, column=0)

		self.e_blender = Entry(browser)
		self.e_blender.grid(row=0, column=1, sticky=W+E, pady=5)

		browser.grid_columnconfigure(1, weight=1)

		b = Button(browser, text="BROWSE", command=self.browse_blender, font = ('times', 7))
		b.grid(row=0, column=2, padx=5)

		self.load_pickle()

		self.is_override = False
		if (self.check_argparser()):
			self.LogMessage("Argparser has arguments: %s " % str(sys.argv))
			self.LogMessage("Initializing the commands that were supplied via command line arguments.", "notice")

			ASSETTYPE_IDX = 1
			MODELPATH_IDX = 2
			BLENDPATH_IDX = 3

			if self.choices.__contains__(sys.argv[ASSETTYPE_IDX].capitalize()):
				self.tkvar.set(sys.argv[ASSETTYPE_IDX].capitalize())

				self.change_dropdown(False) #initialize the text for the button_label

				self.root.modelpath = sys.argv[MODELPATH_IDX]

				self.e_blender.delete('0', END)
				self.e_blender.insert(INSERT, sys.argv[BLENDPATH_IDX])

				self.root.update()
				if self.check_blender_valid():
					self.selectbutton.configure(state=DISABLED)
					self.popupMenu.configure(state=DISABLED)

					self.is_override = True
					self.load_file()
				else:
					self.LogMessage("The arg parser had arguments but the Blender application path was incorrect! What is %s?" % (sys.argv[BLENDPATH_IDX]), 'warning')
			else:
				self.LogMessage("The arg parser had arguments but the format was incorrect! What is %s?" % (sys.argv[ASSETTYPE_IDX]), 'warning')

		self.tkvar.trace('w', self.change_dropdown)# link function to change dropdown, do this late so it will not generate a message incase we made changes from command line arguments

		self.root.mainloop()


	def check_argparser(self):
		return sys.argv.__len__() > 1

	def get_blendscript(self):
		idx = self.get_dropdown_idx() #the selection type index (is it avatar, prop, scene..)
		if idx is not None: #this should never be None
			return self.blendScripts[idx]
		return ''


	def get_dropdown_idx(self):
		if self.choices.__contains__(self.tkvar.get()):
			return self.choices.index(self.tkvar.get())
		return None

	def change_dropdown(self, verbose=True, *args): # on change dropdown value
		idx = self.get_dropdown_idx()
		if idx is not None:
			self.button_label['text'] = self.choicesInfo[idx]
		if verbose:
			self.log.clear()
			self.LogMessage("User changed type to: \"%s\"." % self.tkvar.get(), 'grayed')

	def LogMessage(self, message, tag=None): #tag may be ['error','warning','notice'] or None
		if self.start_time is -1:
			self.log.insert(message, tag)
		else:
			self.log.insert( r'{:1.8f}'.format(time.time()- self.start_time) + r" - " + str(message), tag)

		self.log.insert( "\n\n")
		self.log.yview_pickplace("end") #move scroll bar to bottom
		self.root.update_idletasks()

	def get_prefs_name (self):
		basename_extension=os.path.basename(__file__)
		basename=os.path.splitext(basename_extension)[0]

		return "%s.prefs" % basename

	def load_pickle (self):
		if os.path.isfile(self.get_prefs_name()):
			self.pickle_data = pickle.load(open(self.get_prefs_name(), "rb"))
		self.e_blender.delete('0', END)
		self.e_blender.insert(INSERT, self.pickle_data['blenderpath'])

	def save_pickle (self):
		self.load_pickle()
		if hasattr(self.root, 'modelpath') and self.root.modelpath:
			idx = self.get_dropdown_idx() #the selection type index (is it avatar, prop, scene..)
			key = 'browsefile_'+str(idx) #a key which changes based on the model type selection dropdown
			if idx is not None: #this snould never be None
				self.pickle_data[key] = os.path.dirname(self.root.modelpath)

		if hasattr(self.root, 'apppath') and self.root.apppath:
			self.pickle_data['browseapp'] = os.path.dirname(self.root.apppath)
			self.pickle_data['blenderpath'] = self.root.apppath

		pickle.dump(self.pickle_data, open(self.get_prefs_name(), "wb"))

	def check_blender_valid(self):
		if not os.path.isfile(self.e_blender.get()):
			self.LogMessage("ERROR! Blender Executable Not Found At: " +  self.e_blender.get(), 'error')
			self.LogMessage("Please browse and locate the Blender.exe executable.", 'notice')
			return False
		else:
			self.LogMessage("%s exists!" % os.path.basename(self.e_blender.get()))
		return True

	def browse_file(self):
		self.start_time = -1

		self.log.clear()

		if not self.check_blender_valid():
			return

		browsefile = "/"
		idx = self.get_dropdown_idx() #the selection type index (is it avatar, prop, scene..)
		key = 'browsefile_'+str(idx) #a key which changes based on the model type selection dropdown
		if idx is not None and key in self.pickle_data: #this snould never be None, only load if the key exists
			browsefile = self.pickle_data[key]

		self.root.modelpath = tkFileDialog.askopenfilename(initialdir=browsefile, title="Select .blend Model", filetypes=(("blender files", "*.blend"), ("all files", "*.*")))
		if not self.root.modelpath: #Empty strings are "falsy"
			self.log.clear()

			self.LogMessage("User pressed \"cancel\".", 'grayed')
			return

		self.save_pickle()

		self.load_file()

	def load_file(self):

		self.start_time = time.time()

		self.LogMessage( "START PROCESSING FILE: " + self.root.modelpath)

		self.selectbutton.configure(state=DISABLED)
		self.popupMenu.configure(state=DISABLED)

		success = False
		try:
			ProcessModelFile(self, self.root.modelpath, self.e_blender.get(), self.LogMessage)
			#ProcessCharacterFile(self.root.modelpath, self.e_blender.get(), self.LogMessage)
			success = True
		except Exception as e:
			tb = traceback.format_exc()
			self.LogMessage( "ERROR! " + str(e), 'error')
			self.LogMessage( tb, 'traceback')
			self.LogMessage( "Failed to create project files for this %s ." % (self.tkvar.get().lower()), 'grayed')

		finally:
			if (self.is_override):
				if success:
					self.root.destroy() #done creating the files, so close!!
					return

			self.selectbutton.configure(state=NORMAL)
			self.popupMenu.configure(state=NORMAL)

	def browse_blender(self):

		self.root.apppath = tkFileDialog.askopenfilename(initialdir=self.pickle_data['browseapp'],title="Browse Blender Path",filetypes=(("Application","*.exe"),("all files","*.*")))
		if not self.root.apppath: #Empty strings are "falsy"
			return

		self.save_pickle()

		self.e_blender.delete('0', END)

		self.e_blender.insert(INSERT, self.root.apppath)




if __name__ == "__main__": #is main instance, build the gui
	t = Interface()

