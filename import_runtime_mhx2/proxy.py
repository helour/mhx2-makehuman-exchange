# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Authors:             Thomas Larsson
#  Script copyright (C) Thomas Larsson 2014
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import *
from mathutils import Vector
from .error import *
from .utils import *
from .hm8 import *


# ---------------------------------------------------------------------
#   Add proxy
# ---------------------------------------------------------------------

def addProxy(filepath, mhHuman):
    from .load_json import loadJsonRelative
    mhGeo = loadJsonRelative(filepath)
    mhProxy = mhGeo["proxy"]
    return proxyToGeometry(mhHuman, mhProxy, mhGeo)


def proxyToGeometry(mhHuman, mhProxy, mhGeo):
    from .shapekeys import getScale
    pxyGeo = mhGeo
    pxyGeo["human"] = False
    pxyGeo["name"] = ("%s:%s" % (mhHuman["name"].split(":")[0], mhProxy["name"]))
    pxyGeo["offset"] = mhHuman["offset"]
    pxyGeo["material"] = mhHuman["material"]
    pxyGeo["scale"] = mhHuman["scale"]
    mhMesh = pxyGeo["seed_mesh"] = pxyGeo["mesh"] = mhGeo["mesh"]
    pxyGeo["sscale"] = {
        "x" : mhProxy["x_scale"],
        "y" : mhProxy["y_scale"],
        "z" : mhProxy["z_scale"]
    }
    scale = getScale(None, pxyGeo["sscale"], mhHuman)

    hverts = [Vector(co) for co in mhHuman["seed_mesh"]["vertices"]]
    pverts = []
    for vnums,weights,offset in mhProxy["fitting"]:
        pco = (weights[0]*hverts[vnums[0]] +
               weights[1]*hverts[vnums[1]] +
               weights[2]*hverts[vnums[2]])
        pverts.append(Vector([pco[n]+scale[n]*offset[n] for n in range(3)]))
    mhMesh["vertices"] = pverts

    return pxyGeo,scale

# ---------------------------------------------------------------------
#   Vertex groups
# ---------------------------------------------------------------------

def proxifyVertexGroups(mhProxy, vgrps):
    mhFitting = mhProxy["fitting"]
    ngrps = {}
    for gname,ogrp in vgrps.items():
        grp0 = dict([(vn,0.0) for vn in range(NTotalVerts)])
        for vn,w in ogrp:
            grp0[vn] = w

        grp1 = []
        for pvn,pdata in enumerate(mhFitting):
            vnums,weights,_offsets = pdata
            grp1 += [(pvn, weights[n]*grp0[vn]) for n,vn in enumerate(vnums)]
        grp1.sort()

        ngrp = []
        if len(grp1) > 0:
            vn0 = grp1[0][0]
            wsum = 0.0
            for vn,w in grp1:
                if vn == vn0:
                    wsum += w
                else:
                    if wsum > 1e-4:
                        ngrp.append((vn0,wsum))
                    vn0 = vn
                    wsum = w
            if wsum > 1e-4:
                ngrp.append((vn0,wsum))
            if len(ngrp) > 0:
                ngrps[gname] = ngrp
    return ngrps


def proxifyMask(mhProxy, vnums):
    vgrps = { "Mask" : [(vn,1.0) for vn in vnums] }
    ngrps = proxifyVertexGroups(mhProxy, vgrps)
    if "Mask" in ngrps.keys():
        pvnums = [pvn for (pvn,w) in ngrps["Mask"] if w > 0.9]
    else:
        pvnums = []
    return pvnums

# ---------------------------------------------------------------------
#   Targets
# ---------------------------------------------------------------------

def proxifyTargets(mhProxy, targets):
    mhFitting = mhProxy["fitting"]
    ntrgs = {}
    for tname,otrg in targets.items():
        trg0 = dict([(vn,Vector()) for vn in range(NTotalVerts)])
        for vn,delta in otrg:
            trg0[vn] = Vector(delta)

        trg1 = []
        for pvn,pdata in enumerate(mhFitting):
            vnums,weights,_offsets = pdata
            trg1 += [(pvn, weights[n]*trg0[vn]) for n,vn in enumerate(vnums)]
        trg1.sort()

        ntrg = []
        if len(trg1) > 0:
            vn0 = trg1[0][0]
            dsum = Vector()
            for vn,delta in trg1:
                if vn == vn0:
                    dsum += delta
                else:
                    if dsum.length > 1e-3:
                        ntrg.append((vn0,dsum))
                    vn0 = vn
                    dsum = delta
            if dsum > 1e-4:
                ntrg.append((vn0,dsum))
            if len(ntrg) > 0:
                ntrgs[tname] = ntrg
    return ntrgs



# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------

def draw(self, context):
    hairlist = []
    folder = os.path.join(os.path.dirname(__file__), "data", "hm8", "hair")
    for file in os.listdir(folder):
        fname,ext = os.path.splitext(file)
        if ext == ".mhc2":
            hairlist.append(file, fname, fname)
    if hairlist:
        return EnumProperty(
            items = hairlist,
            name = "Hair",
            description = "Hair",
            default = hairlist[0])


def addHair(ob, filepath):
    from .load_json import loadJson
    print(ob)
    struct = loadJson(filepath)
    psys = ob.particle_systems.active
    if psys is not None:
        bpy.ops.object.particle_system_remove()
    bpy.ops.object.particle_system_add()

    psys = ob.particle_systems.active
    pstruct = struct["particles"]
    print(psys)
    for key,value in pstruct.items():
        if key not in ["settings", "vertices"]:
            try:
                setattr(psys, key, value)
            except AttributeError:
                print("***", key,value)
                pass

    pset = psys.settings
    print(pset)
    for key,value in pstruct["settings"].items():
        if key[0] != "_":
            try:
                setattr(pset, key, value)
            except AttributeError:
                print("  ***", key,value)

    nhairs = int(len(pstruct["vertices"])/pset.hair_step)
    print("NH", nhairs)
    pset.count = nhairs
    bpy.ops.object.mode_set(mode='PARTICLE_EDIT')

    verts = pstruct["vertices"]
    idx = 0
    m = n = 0
    print(list(psys.particles))
    for hair in psys.particles:
        print(len(hair.hair_keys))
        for v in hair.hair_keys:
            print(v.co, verts[idx])
            v.co = verts[idx]
            co = psys.co_hair(ob, m, n)
            #print(v.co, co)
            idx += 1
            n += 1
        m += 1

    m = n = 0
    for hair in psys.particles:
        print(len(hair.hair_keys))
        for v in hair.hair_keys:
            co = psys.co_hair(ob, m, n)
            print(v.co, co)
            n += 1
        m += 1

    bpy.ops.object.mode_set(mode='OBJECT')



class VIEW3D_OT_AddHairButton(bpy.types.Operator, ImportHelper):
    bl_idname = "mhx2.add_hair"
    bl_label = "Add Hair (.mhc2)"
    bl_description = "Add Hair"
    bl_options = {'UNDO'}

    filename_ext = ".mhc2"
    filter_glob = StringProperty(default="*.mhc2", options={'HIDDEN'})
    filepath = StringProperty(name="File Path", description="Filepath used for loading the hair file", maxlen=1024, default="")

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH')

    def execute(self, context):
        try:
            addHair(context.object, self.properties.filepath)
        except MHXError:
            handleMHXError(context)
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

print("Hair loaded")