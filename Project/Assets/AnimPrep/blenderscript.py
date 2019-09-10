#This file is pushed into a headless subprocess of the user's .blend via command line args, this automatically export .fbx file and material infos json

# !/usr/bin/env python2.7
import bpy, json, os, re


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
	for slot in m.texture_slots:

		if slot is not None and hasattr(slot.texture, 'image'):
			print(slot.texture)
			filename = slot.texture.image.filepath  # the filename and extension of the image, strip dir info
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
	# iterate over all bones of the active object

	for bone in armature.pose.bones:
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

bpy.ops.file.unpack_all(method='WRITE_LOCAL')

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

    for n in bpy.data.images:
        if n.name=='TMP_BAKING':
            n.user_clear()
            bpy.data.images.remove(n)


    if mode == "ALPHA" and tex.texture.type=='IMAGE':
        sizeX=tex.texture.image.size[0]
        sizeY=tex.texture.image.size[1]
    else:
        sizeX=600
        sizeY=600
    bpy.ops.image.new(name="TMP_BAKING", width=sizeX, height=sizeY, color=(0.0, 0.0, 0.0, 1.0), alpha=True, uv_test_grid=False, float=False)
    bpy.data.screens['UV Editing'].areas[1].spaces[0].image = bpy.data.images["TMP_BAKING"]
    sc.render.engine='BLENDER_RENDER'
    img = bpy.data.images["TMP_BAKING"]
    img=bpy.data.images.get("TMP_BAKING")
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
    bpy.data.images.remove(img)
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

                                img=bpy.data.images.load(tex.texture.name + "_PTEXT.jpg")
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
print ('This will convert the Blender Internal shaders for all materials to a default node setup for cycles and EEVEE engine.\n')
print ('Author Info:')
for key in bl_info.keys():
	print(key, ':', bl_info[key])

AutoNode()
AutoNodeOff()
print("\nMaterial Nodes Created Successfully!")

bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print("\nSaved Done!")