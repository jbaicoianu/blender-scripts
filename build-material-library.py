import bpy
import os
import re
import math

'''
Automatically builds a material library .blend file from a directory of textures images.

Sets up materials for both Blender Internal and Cycles.  Supports diffuse, specular, normal,
and emission maps.

Also generates a simple preview scene showing off all of your materials.


Directory structure should be as follows:
 * mytextures/
   * metal01/
     * metal01-diffuse.png
     * metal01-normal.png
     * metal01-specular.png
   * metal02/
     * metal02-diffuse.png
     * metal02-normal.png
     * metal02-specular.png
   * glass01/
     * glass01-diffuse.png
     * glass01-normal.png
     * glass01-specular.png
'''

texturepath = '//textures'
filepath = '/home/bai/scratch/models/textures'

def list_materials():
    # get texture names, without the path info
    files = [x[0].replace(filepath, '').replace('/','') for x in os.walk(filepath)]
    # strip blanks
    files = [f for f in files if f.strip()]
    files.sort()
    return files

def get_material_groups():
    materials = list_materials()
    groups = {}
    
    for mat in materials:
        m = re.match(r"^(\w+?)(\d+)$", mat)
        groupname = 'misc'
        if (m):
            groupname = m.group(1)
            groupnum = m.group(2)

        if groupname not in groups:
            groups[groupname] = []

        groups[groupname].append(mat)
    return groups

def create_previews():
    groups = get_material_groups()

    print(groups)

    rowspacing = -4
    colspacing = 20

    col = 0
    groupnames = list(groups.keys())
    groupnames.sort()
    for groupname in groupnames:
        row = 0
        for matname in groups[groupname]:
            material = create_material(matname)

            bpy.ops.mesh.primitive_cube_add(location=(col * colspacing, 0, row * rowspacing))
            box = bpy.context.object
            box.name = matname + '-box' 
            box.data.materials.append(material)
            bpy.ops.object.editmode_toggle()
            bpy.ops.uv.cube_project()
            bpy.ops.object.editmode_toggle()

            bpy.ops.object.text_add(location=(2, 0, -0.5), rotation=(math.pi / 2, 0, 0))
            text = bpy.context.object
            text.parent = box
            text.data.body = matname
            text.data.extrude = 0.1
            text.data.materials.append(material)
            text.name = matname + '-label' 

            bpy.ops.transform.resize(value=(2,2,2))

            bpy.ops.object.convert(target='MESH')
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action='TOGGLE')
            bpy.ops.uv.cube_project()
            bpy.ops.object.editmode_toggle()

            row = row + 1
        col = col + 1

def get_material_imagefiles(matname):
    files = [os.path.splitext(x)[0] for x in os.listdir(filepath + '/' + matname + '/')]
    uniq = set()
    return [x.replace(matname + '-', '') for x in files if not (x in uniq or uniq.add(x))]

def create_material(matname):
    material = bpy.data.materials.new(matname)

    imagefiles = get_material_imagefiles(matname)
    images = create_material_images(material, imagefiles);

    textures_internal = init_material_textures_internal(material, images);
    textures_cycles = init_material_textures_cycles(material, images);

    return material

def get_texture_path(matname, textype):
    texext = 'png' # FIXME - should be jpg for diffuse and specular
    imgpath = '%s/%s/%s-%s.%s' % (filepath, matname, matname, textype, texext)
    return imgpath

def create_material_images(material, imagefiles):
    images = {}
    for textype in imagefiles:
        texname = material.name + '-' + textype
        imgpath = get_texture_path(material.name, textype)
        #texture = bpy.data.textures.new(texname, type='IMAGE')
        #texture.image = bpy.data.images.load(imgpath)
        #textures[textype] = texture
        images[textype] = bpy.data.images.load(imgpath)
    return images

def init_material_textures_internal(material, images):
    #blender internal material setup
    slot = 0

    material.use_nodes = False
    material.specular_intensity = 0

    # FIXME - we should only set this if we detect that the image has an alpha channel
    material.use_transparency = True
    material.alpha = 0

    for textype in images.keys():
        texname = material.name + '-' + textype
        texture = bpy.data.textures.new(texname, type='IMAGE')
        texture.image = images[textype]
        matslot = material.texture_slots.create(slot) 
        init_material_slot(matslot, textype, texture)
        slot = slot + 1

def init_material_textures_cycles(material, images):
    # cycles setup
    textures = {}

    material.use_nodes = True

    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    # common nodes
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = grid_pos(6, 1)
    diffuse = nodes.new(type='ShaderNodeBsdfDiffuse')
    diffuse.location = grid_pos(3, 0.5)
    uvmap = nodes.new(type='ShaderNodeUVMap')
    uvmap.uv_map = "UVMap"
    uvmap.location = grid_pos(0, 1)

    # common links
    #links.new(diffuse.outputs['BSDF'], output.inputs['Surface'])

    normalmap = False

    # FIXME - should default to False, and only enable if the diffuse texture has alpha
    transparent = True

    diffuseteximg = False
    normalteximg = False
    specularteximg = False

    # Cycles material
    if 'diffuse' in images:
        diffuseteximg = nodes.new(type='ShaderNodeTexImage')
        diffuseteximg.image = images['diffuse']
        diffuseteximg.location = grid_pos(1,0)
        diffuseteximg.width = 250
        links.new(uvmap.outputs['UV'], diffuseteximg.inputs['Vector'])
        links.new(diffuseteximg.outputs['Color'], diffuse.inputs['Color'])
    if 'normal' in images:
        normalteximg = nodes.new(type='ShaderNodeTexImage')
        normalteximg.image = images['normal']
        normalteximg.location = grid_pos(1,1)
        normalteximg.width = 250
        normalmap = nodes.new(type='ShaderNodeNormalMap')
        normalmap.location = grid_pos(2, 1)
        normalmap.uv_map = "UVMap"
        links.new(uvmap.outputs['UV'], normalteximg.inputs['Vector'])
        links.new(normalteximg.outputs['Color'], normalmap.inputs['Color'])
        links.new(normalmap.outputs['Normal'], diffuse.inputs['Normal'])
    if 'specular' in images:
        specularteximg = nodes.new(type='ShaderNodeTexImage')
        specularteximg.image = images['specular']
        specularteximg.location = grid_pos(1,2)
        specularteximg.width = 250
        addnode = nodes.new(type='ShaderNodeAddShader')
        glossy = nodes.new(type='ShaderNodeBsdfGlossy')
        glossy.location = grid_pos(3, 1.5)
        addnode.location = grid_pos(4, 1)
        links.new(uvmap.outputs['UV'], specularteximg.inputs['Vector'])
        links.new(specularteximg.outputs['Color'], glossy.inputs['Color'])
        links.new(diffuse.outputs['BSDF'], addnode.inputs[0])
        links.new(glossy.outputs['BSDF'], addnode.inputs[1])
        links.new(addnode.outputs['Shader'], output.inputs['Surface'])
        if normalmap:
            links.new(normalmap.outputs['Normal'], glossy.inputs['Normal'])
    if 'emissive' in images:
        emissionteximg = nodes.new(type='ShaderNodeTexImage')
        emissionteximg.image = images['emissive']
        emissionteximg.location = grid_pos(1,3)
        emissionteximg.width = 250
        oldaddnode = addnode
        addnode = nodes.new(type='ShaderNodeAddShader')
        emissionnode = nodes.new(type='ShaderNodeEmission')
        emissionnode.location = grid_pos(3, 2)
        addnode.location = grid_pos(5, 1.5)
        links.new(uvmap.outputs['UV'], emissionteximg.inputs['Vector'])
        links.new(emissionteximg.outputs['Color'], emissionnode.inputs['Color'])
        links.new(oldaddnode.outputs['Shader'], addnode.inputs[0])
        links.new(emissionnode.outputs['Emission'], addnode.inputs[1])
        links.new(addnode.outputs['Shader'], output.inputs['Surface'])

    if transparent:
        transnode = nodes.new(type='ShaderNodeBsdfTransparent')
        transnode.location = grid_pos(3,0)
        mixnode = nodes.new(type='ShaderNodeMixShader')
        mixnode.location = grid_pos(5,0.5)
        links.new(diffuseteximg.outputs['Alpha'], mixnode.inputs[0])
        links.new(transnode.outputs['BSDF'], mixnode.inputs[1])
        links.new(addnode.outputs['Shader'], mixnode.inputs[2])
        links.new(mixnode.outputs['Shader'], output.inputs['Surface'])
            
    material.use_nodes = True
    

def grid_pos(x, y):
    colsize = 250
    rowsize = -400

    return (x * colsize, y * rowsize)
    
def fix_node_images(material):
    images = []
    if material.use_nodes:
        nodes = material.node_tree.nodes
        for node in nodes:
            if type(node) == bpy.types.ShaderNodeTexImage:
                try:
                    nam = node.image.name
                    images.append(nam)
                except:
                    print('No texture assigned to this node, no problem though')
    return images

def get_node_images(material):
    images = []
    if material.node_tree:
        nodes = material.node_tree.nodes
        for node in nodes:
            if type(node) == bpy.types.ShaderNodeTexImage:
                try:
                    nam = node.image.name
                    print(nam)
                    if nam.find('-') == -1:
                        node.image.name = material.name + '-diffuse'
                        node.image.filepath = texturepath + '/' + material.name + '/' + material.name + '-diffuse.jpg'
                    nam = node.image.name
                    images.append(nam)
                except:
                    print('No texture assigned to this node, no problem though')
    return images

def init_material_slot(slot, textype, texture):
    slot.texture_coords = 'UV'
    slot.uv_layer = 'UVMap'
    slot.use = True
    slot.texture = texture

    if textype == 'diffuse':
        slot.use_map_color_diffuse = True
        slot.use_map_alpha = True 
        slot.use_map_color_emission = True 
        slot.use_map_alpha = True 
        slot.use_map_color_spec = False 
        slot.use_map_specular = False 
        slot.use_map_normal = False 
        slot.texture.use_alpha = True
    elif textype == 'normal':
        slot.use_map_color_diffuse = False 
        slot.use_map_alpha = False 
        slot.use_map_color_emission = False 
        slot.use_map_color_spec = False 
        slot.use_map_specular = False 
        slot.use_map_normal = True 
        slot.texture.use_alpha = False
        slot.texture.use_normal_map = True 
    elif textype == 'specular':
        slot.use_map_color_diffuse = False 
        slot.use_map_alpha = False 
        slot.use_map_color_emission = False 
        slot.use_map_color_spec = False 
        slot.use_map_specular = True 
        slot.use_map_normal = False 
        slot.texture.use_alpha = False
    elif textype == 'emissive':
        slot.use_map_color_diffuse = False 
        slot.use_map_alpha = False 
        slot.use_map_color_emission = True 
        slot.use_map_color_spec = False 
        slot.use_map_specular = False 
        slot.use_map_normal = False 
        slot.blend_type = "ADD"
        slot.texture.use_alpha = False
    
    return slot

def fix_material(material):
    images = get_node_images(material)
    extdefault = 'png'
    exts = { 'diffuse': 'jpg', 'specular': 'jpg' }

    material.use_nodes = False
    slot = 0
    for imgname in images:
        texname = os.path.splitext(imgname)[0]
        parts = texname.split('-')
        try:
            textype = parts[1]
        except IndexError:
            textype = 'diffuse'

        texture = None

        texname = material.name + '-' + textype
        
        if texname in bpy.data.textures:
            texture = bpy.data.textures[texname]
        else:
            texture = bpy.data.textures.new(texname, type='IMAGE')

        print("Texture type: %s" % (texture.type))
        img = texture.image
        texext = exts.get(textype, extdefault)
        imgpath = '%s/%s/%s.%s' % (texturepath, material.name, texname, texext);
        if img:
            if img.filepath != imgpath:
                img.filepath = imgpath
        else:
            img = bpy.data.images.load(imgpath)
        img.reload()
        texture.image = img
        #texname = material.name + '-' + textypes[i]

        if (texture != None):
            matslot = material.texture_slots.create(slot) 
            init_material_slot(matslot, textype, texture)
            slot = slot + 1

        #if material.texture_slots[i] != None and material.texture_slots[i].name == matname + '-' + mattypes[i]:
        #    print('all good with %s %s' % (matname, mattypes[i]))
        #else:
        #    print('%s %s needs fixing' % (matname, mattypes[i]))
    
print('===================')

#for material in bpy.data.materials:
#    fix_material(material)

create_previews()
