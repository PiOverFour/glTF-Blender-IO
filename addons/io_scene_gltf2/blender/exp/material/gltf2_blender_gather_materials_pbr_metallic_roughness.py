# Copyright 2018-2021 The glTF-Blender-IO authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import bpy

from ....io.com import gltf2_io
from ....io.exp.gltf2_io_user_extensions import export_user_extensions
from ..gltf2_blender_gather_cache import cached
from .gltf2_blender_search_node_tree import get_vertex_color_info
from .gltf2_blender_gather_texture_info import gather_texture_info
from .gltf2_blender_search_node_tree import \
    get_socket_from_gltf_material_node, \
    has_image_node_from_socket, \
    get_const_from_default_value_socket, \
    get_socket, \
    get_factor_from_socket

@cached
def gather_material_pbr_metallic_roughness(blender_material, orm_texture, export_settings):
    if not __filter_pbr_material(blender_material, export_settings):
        return None, {}, {'color': None, 'alpha': None, 'color_type': None, 'alpha_type': None}, {}

    uvmap_infos = {}
    udim_infos = {}

    base_color_texture, uvmap_info, udim_info_bc, _ = __gather_base_color_texture(blender_material, export_settings)
    uvmap_infos.update(uvmap_info)
    udim_infos.update(udim_info_bc)
    metallic_roughness_texture, uvmap_info, udim_info_mr, _ = __gather_metallic_roughness_texture(blender_material, orm_texture, export_settings)
    uvmap_infos.update(uvmap_info)
    udim_infos.update(udim_info_mr)

    base_color_factor, vc_info = __gather_base_color_factor(blender_material, export_settings)

    material = gltf2_io.MaterialPBRMetallicRoughness(
        base_color_factor=base_color_factor,
        base_color_texture=base_color_texture,
        extensions=__gather_extensions(blender_material, export_settings),
        extras=__gather_extras(blender_material, export_settings),
        metallic_factor=__gather_metallic_factor(blender_material, export_settings),
        metallic_roughness_texture=metallic_roughness_texture,
        roughness_factor=__gather_roughness_factor(blender_material, export_settings)
    )

    export_user_extensions('gather_material_pbr_metallic_roughness_hook', export_settings, material, blender_material, orm_texture)

    return material, uvmap_infos, vc_info, udim_infos


def __filter_pbr_material(blender_material, export_settings):
    return True


def __gather_base_color_factor(blender_material, export_settings):
    if not blender_material.use_nodes:
        return [*blender_material.diffuse_color[:3], 1.0], {"color": None, "alpha": None, "color_type": None, "alpha_type": None}

    rgb, alpha = None, None

    alpha_socket = get_socket(blender_material, "Alpha")
    if isinstance(alpha_socket.socket, bpy.types.NodeSocket):
        if export_settings['gltf_image_format'] != "NONE":
            alpha = get_factor_from_socket(alpha_socket, kind='VALUE')
        else:
            alpha = get_const_from_default_value_socket(alpha_socket, kind='VALUE')

    base_color_socket = get_socket(blender_material, "Base Color")
    if base_color_socket.socket is None:
        base_color_socket = get_socket(blender_material, "BaseColor")
    if base_color_socket is None:
        base_color_socket = get_socket_from_gltf_material_node(blender_material, "BaseColorFactor")
    if isinstance(base_color_socket.socket, bpy.types.NodeSocket):
        if export_settings['gltf_image_format'] != "NONE":
            rgb = get_factor_from_socket(base_color_socket, kind='RGB')
        else:
            rgb = get_const_from_default_value_socket(base_color_socket, kind='RGB')

    if rgb is None: rgb = [1.0, 1.0, 1.0]
    if alpha is None: alpha = 1.0

    # Need to clamp between 0.0 and 1.0: Blender color can be outside this range
    rgb = [max(min(c, 1.0), 0.0) for c in rgb]

    rgba = [*rgb, alpha]

    vc_info = get_vertex_color_info(base_color_socket, alpha_socket, export_settings)

    if rgba == [1, 1, 1, 1]: return None, vc_info
    return rgba, vc_info


def __gather_base_color_texture(blender_material, export_settings):
    base_color_socket = get_socket(blender_material, "Base Color")
    if base_color_socket.socket is None:
        base_color_socket = get_socket(blender_material, "BaseColor")
    if base_color_socket is None:
        base_color_socket = get_socket_from_gltf_material_node(blender_material, "BaseColor")

    alpha_socket = get_socket(blender_material, "Alpha")

    # keep sockets that have some texture : color and/or alpha
    inputs = tuple(
        socket for socket in [base_color_socket, alpha_socket]
        if socket.socket is not None and has_image_node_from_socket(socket, export_settings)
    )
    if not inputs:
        return None, {}, {}, None

    tex, uvmap_info, udim_info, factor = gather_texture_info(inputs[0], inputs, (), export_settings)
    return tex, {'baseColorTexture': uvmap_info}, {'baseColorTexture': udim_info} if len(udim_info.keys()) > 0 else {}, factor


def __gather_extensions(blender_material, export_settings):
    return None


def __gather_extras(blender_material, export_settings):
    return None


def __gather_metallic_factor(blender_material, export_settings):
    if not blender_material.use_nodes:
        return blender_material.metallic

    metallic_socket = get_socket(blender_material, "Metallic")
    if metallic_socket is None:
        metallic_socket = get_socket_from_gltf_material_node(blender_material, "MetallicFactor")
    if isinstance(metallic_socket.socket, bpy.types.NodeSocket):
        fac = get_factor_from_socket(metallic_socket, kind='VALUE')
        return fac if fac != 1 else None
    return None


def __gather_metallic_roughness_texture(blender_material, orm_texture, export_settings):
    metallic_socket = get_socket(blender_material, "Metallic")
    roughness_socket = get_socket(blender_material, "Roughness")

    hasMetal = metallic_socket.socket is not None and has_image_node_from_socket(metallic_socket, export_settings)
    hasRough = roughness_socket.socket is not None and has_image_node_from_socket(roughness_socket, export_settings)

    default_sockets = ()
    # Warning: for default socket, do not use NodeSocket object, because it will break cache
    # Using directlty the Blender socket object
    if not hasMetal and not hasRough:
        metallic_roughness = get_socket_from_gltf_material_node(blender_material, "MetallicRoughness")
        if metallic_roughness is None or not has_image_node_from_socket(metallic_roughness, export_settings):
            return None, {}, {}, None
    elif not hasMetal:
        texture_input = (roughness_socket,)
        default_sockets = (metallic_socket.socket,)
    elif not hasRough:
        texture_input = (metallic_socket,)
        default_sockets = (roughness_socket.socket,)
    else:
        texture_input = (metallic_socket, roughness_socket)
        default_sockets = ()

    tex, uvmap_info, udim_info, factor = gather_texture_info(
        texture_input[0],
        orm_texture or texture_input,
        default_sockets,
        export_settings,
    )

    return tex, {'metallicRoughnessTexture': uvmap_info}, {'metallicRoughnessTexture' : udim_info} if len(udim_info.keys()) > 0 else {}, factor

def __gather_roughness_factor(blender_material, export_settings):
    if not blender_material.use_nodes:
        return blender_material.roughness

    roughness_socket = get_socket(blender_material, "Roughness")
    if roughness_socket is None:
        roughness_socket = get_socket_from_gltf_material_node(blender_material, "RoughnessFactor")
    if isinstance(roughness_socket.socket, bpy.types.NodeSocket):
        fac = get_factor_from_socket(roughness_socket, kind='VALUE')
        return fac if fac != 1 else None
    return None

def get_default_pbr_for_emissive_node():
    return gltf2_io.MaterialPBRMetallicRoughness(
        base_color_factor=[0.0,0.0,0.0,1.0],
        base_color_texture=None,
        extensions=None,
        extras=None,
        metallic_factor=None,
        metallic_roughness_texture=None,
        roughness_factor=None
    )
