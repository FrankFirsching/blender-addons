# ##### BEGIN GPL LICENSE BLOCK #####
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

# <pep8 compliant>


class ElementSpec:
    __slots__ = (
        "name",
        "count",
        "properties",
    )

    def __init__(self, name, count):
        self.name = name
        self.count = count
        self.properties = []

    def load(self, format, stream):
        if format == b'ascii':
            stream = stream.readline().split()
        return [x.load(format, stream) for x in self.properties]

    def index(self, name):
        for i, p in enumerate(self.properties):
            if p.name == name:
                return i
        return -1


class PropertySpec:
    __slots__ = (
        "name",
        "list_type",
        "numeric_type",
    )

    def __init__(self, name, list_type, numeric_type):
        self.name = name
        self.list_type = list_type
        self.numeric_type = numeric_type

    def is_custom_property(self):
        return self.name not in (b'x',b'y',b'z',b's',b't',b'red',b'green',b'blue',b'alpha')

    def read_format(self, format, count, num_type, stream):
        import struct

        if format == b'ascii':
            if num_type == 's':
                ans = []
                for i in range(count):
                    s = stream[i]
                    if not (len(s) >= 2 and s.startswith(b'"') and s.endswith(b'"')):
                        print("Invalid string", s)
                        print("Note: ply_import.py does not handle whitespace in strings")
                        return None
                    ans.append(s[1:-1])
                stream[:count] = []
                return ans
            if num_type == 'f' or num_type == 'd':
                mapper = float
            else:
                mapper = int
            ans = [mapper(x) for x in stream[:count]]
            stream[:count] = []
            return ans
        else:
            if num_type == 's':
                ans = []
                for i in range(count):
                    fmt = format + 'i'
                    data = stream.read(struct.calcsize(fmt))
                    length = struct.unpack(fmt, data)[0]
                    fmt = '%s%is' % (format, length)
                    data = stream.read(struct.calcsize(fmt))
                    s = struct.unpack(fmt, data)[0]
                    ans.append(s[:-1])  # strip the NULL
                return ans
            else:
                fmt = '%s%i%s' % (format, count, num_type)
                data = stream.read(struct.calcsize(fmt))
                return struct.unpack(fmt, data)

    def load(self, format, stream):
        if self.list_type is not None:
            count = int(self.read_format(format, 1, self.list_type, stream)[0])
            return self.read_format(format, count, self.numeric_type, stream)
        else:
            return self.read_format(format, 1, self.numeric_type, stream)[0]


class ObjectSpec:
    __slots__ = ("specs",)

    def __init__(self):
        # A list of element_specs
        self.specs = []

    def load(self, format, stream):
        return dict([(i.name, [i.load(format, stream) for j in range(i.count)]) for i in self.specs])

        # Longhand for above LC
        """
        answer = {}
        for i in self.specs:
            answer[i.name] = []
            for j in range(i.count):
                if not j % 100 and meshtools.show_progress:
                    Blender.Window.DrawProgressBar(float(j) / i.count, 'Loading ' + i.name)
                answer[i.name].append(i.load(format, stream))
        return answer
        """


def read(filepath):
    import re

    format = b''
    texture = b''
    version = b'1.0'
    format_specs = {
        b'binary_little_endian': '<',
        b'binary_big_endian': '>',
        b'ascii': b'ascii',
    }
    type_specs = {
        b'char': 'b',
        b'uchar': 'B',
        b'int8': 'b',
        b'uint8': 'B',
        b'int16': 'h',
        b'uint16': 'H',
        b'short': 'h',
        b'ushort': 'H',
        b'int': 'i',
        b'int32': 'i',
        b'uint': 'I',
        b'uint32': 'I',
        b'float': 'f',
        b'float32': 'f',
        b'float64': 'd',
        b'double': 'd',
        b'string': 's',
    }
    obj_spec = ObjectSpec()
    invalid_ply = (None, None, None)

    with open(filepath, 'rb') as plyf:
        signature = plyf.readline()

        if not signature.startswith(b'ply'):
            print("Signature line was invalid")
            return invalid_ply

        valid_header = False
        for line in plyf:
            tokens = re.split(br'[ \r\n]+', line)

            if len(tokens) == 0:
                continue
            if tokens[0] == b'end_header':
                valid_header = True
                break
            elif tokens[0] == b'comment':
                if len(tokens) < 2:
                    continue
                elif tokens[1] == b'TextureFile':
                    if len(tokens) < 4:
                        print("Invalid texture line")
                    else:
                        texture = tokens[2]
                continue

            elif tokens[0] == b'obj_info':
                continue
            elif tokens[0] == b'format':
                if len(tokens) < 3:
                    print("Invalid format line")
                    return invalid_ply
                if tokens[1] not in format_specs:
                    print("Unknown format", tokens[1])
                    return invalid_ply
                try:
                    version_test = float(tokens[2])
                except Exception as ex:
                    print("Unknown version", ex)
                    version_test = None
                if version_test != float(version):
                    print("Unknown version", tokens[2])
                    return invalid_ply
                del version_test
                format = tokens[1]
            elif tokens[0] == b'element':
                if len(tokens) < 3:
                    print("Invalid element line")
                    return invalid_ply
                obj_spec.specs.append(ElementSpec(tokens[1], int(tokens[2])))
            elif tokens[0] == b'property':
                if not len(obj_spec.specs):
                    print("Property without element")
                    return invalid_ply
                if tokens[1] == b'list':
                    obj_spec.specs[-1].properties.append(PropertySpec(tokens[4], type_specs[tokens[2]], type_specs[tokens[3]]))
                else:
                    obj_spec.specs[-1].properties.append(PropertySpec(tokens[2], None, type_specs[tokens[1]]))
        if not valid_header:
            print("Invalid header ('end_header' line not found!)")
            return invalid_ply

        obj = obj_spec.load(format_specs[format], plyf)

    return obj_spec, obj, texture

def color_factor(properties_type):
    return {
        'f': 1.0,
        'd': 1.0,
        'b': 1.0/128.0,
        'B': 1.0/255.0,
        'h': 1.0/32767.0,
        'H': 1.0/65535.0,
        'i': 1.0/2147483647.0,
        'I': 1.0/4294967295.0
        }.get(properties_type, 1.0)

def load_ply_mesh(obj_spec, obj, texture, ply_name, import_custom_vertex_colors):
    import bpy

    # XXX28: use texture
    if obj is None:
        print("Invalid file")
        return

    uvindices = None
    colindices = {}
    colmultiply = {}

    # TODO import normals
    # noindices = None

    for el in obj_spec.specs:
        if el.name == b'vertex':
            vindices_x, vindices_y, vindices_z = el.index(b'x'), el.index(b'y'), el.index(b'z')
            # noindices = (el.index('nx'), el.index('ny'), el.index('nz'))
            # if -1 in noindices: noindices = None
            uvindices = (el.index(b's'), el.index(b't'))
            if -1 in uvindices:
                uvindices = None
            # ignore alpha if not present
            rgb_idx = el.index(b'red'), el.index(b'green'), el.index(b'blue')
            if all(idx>-1 for idx in rgb_idx):
                if el.index(b'alpha') == -1:
                    colindices['Col'] = rgb_idx
                else:
                    colindices['Col'] = rgb_idx+(el.index(b'alpha'),)
            elif any(idx > -1 for idx in rgb_idx):
                print("Warning: At least one obligatory color channel is missing, ignoring vertex colors.")

            if import_custom_vertex_colors:
                for idx,p in enumerate(el.properties):
                    group_name = p.name.decode("utf-8")
                    if p.is_custom_property() and group_name[-1].isdigit():
                        base_name = group_name[0:-1]
                        digit = int(group_name[-1])
                        cindices = []
                        if base_name in colindices:
                            cindices = colindices[base_name]
                        else:
                            colindices[base_name] = cindices
                        # Resize the list to accomodate at least digit elements
                        cindices.extend([None]*(digit-len(cindices)))
                        # counting is 1-based for the color names
                        cindices[digit-1] = idx
            
            # Filter out the colindices, that still have None in them
            colindices = {k:v for k,v in colindices.items() if not any(idx==None for idx in v)}
            for name in colindices:
                colmultiply[name] = [color_factor(el.properties[i].numeric_type) for i in colindices[name] ]

        elif el.name == b'face':
            findex = el.index(b'vertex_indices')
        elif el.name == b'tristrips':
            trindex = el.index(b'vertex_indices')
        elif el.name == b'edge':
            eindex1, eindex2 = el.index(b'vertex1'), el.index(b'vertex2')

    mesh_faces = []
    mesh_uvs = []
    mesh_colors = {k:[] for k in colindices.keys()}

    def add_face(vertices, indices, uvindices, colindices, colmultiply):
        mesh_faces.append(indices)
        if uvindices:
            mesh_uvs.extend([(vertices[index][uvindices[0]], vertices[index][uvindices[1]]) for index in indices])
        for name in colindices:
            cindices = colindices[name]
            cmultiply = colmultiply[name]
            m_colors = mesh_colors[name]
            if len(cindices) == 3:
                m_colors.extend([
                    (
                       vertices[index][cindices[0]] * cmultiply[0],
                       vertices[index][cindices[1]] * cmultiply[1],
                       vertices[index][cindices[2]] * cmultiply[2],
                       1.0
                    )
                    for index in indices
                ])
            elif len(cindices) == 4:
                m_colors.extend([
                    (
                       vertices[index][cindices[0]] * cmultiply[0],
                       vertices[index][cindices[1]] * cmultiply[1],
                       vertices[index][cindices[2]] * cmultiply[2],
                       vertices[index][cindices[3]] * cmultiply[3],
                    )
                    for index in indices
                ])

    if uvindices or colindices:
        # If we have Cols or UVs then we need to check the face order.
        add_face_simple = add_face

        # EVIL EEKADOODLE - face order annoyance.
        def add_face(vertices, indices, uvindices, colindices, colmultiply):
            if len(indices) == 4:
                if indices[2] == 0 or indices[3] == 0:
                    indices = indices[2], indices[3], indices[0], indices[1]
            elif len(indices) == 3:
                if indices[2] == 0:
                    indices = indices[1], indices[2], indices[0]

            add_face_simple(vertices, indices, uvindices, colindices, colmultiply)

    verts = obj[b'vertex']

    if b'face' in obj:
        for f in obj[b'face']:
            ind = f[findex]
            add_face(verts, ind, uvindices, colindices, colmultiply)

    if b'tristrips' in obj:
        for t in obj[b'tristrips']:
            ind = t[trindex]
            len_ind = len(ind)
            for j in range(len_ind - 2):
                add_face(verts, (ind[j], ind[j + 1], ind[j + 2]), uvindices, colindices, colmultiply)

    mesh = bpy.data.meshes.new(name=ply_name)

    mesh.vertices.add(len(obj[b'vertex']))

    mesh.vertices.foreach_set("co", [a for v in obj[b'vertex'] for a in (v[vindices_x], v[vindices_y], v[vindices_z])])

    if b'edge' in obj:
        mesh.edges.add(len(obj[b'edge']))
        mesh.edges.foreach_set("vertices", [a for e in obj[b'edge'] for a in (e[eindex1], e[eindex2])])

    if mesh_faces:
        loops_vert_idx = []
        faces_loop_start = []
        faces_loop_total = []
        lidx = 0
        for f in mesh_faces:
            nbr_vidx = len(f)
            loops_vert_idx.extend(f)
            faces_loop_start.append(lidx)
            faces_loop_total.append(nbr_vidx)
            lidx += nbr_vidx

        mesh.loops.add(len(loops_vert_idx))
        mesh.polygons.add(len(mesh_faces))

        mesh.loops.foreach_set("vertex_index", loops_vert_idx)
        mesh.polygons.foreach_set("loop_start", faces_loop_start)
        mesh.polygons.foreach_set("loop_total", faces_loop_total)

        if uvindices:
            uv_layer = mesh.uv_layers.new()
            for i, uv in enumerate(uv_layer.data):
                uv.uv = mesh_uvs[i]

        for name in colindices:
            vcol_lay = mesh.vertex_colors.new(name=name)
            m_colors = mesh_colors[name]
            for i, col in enumerate(vcol_lay.data):
                col.color[0] = m_colors[i][0]
                col.color[1] = m_colors[i][1]
                col.color[2] = m_colors[i][2]
                col.color[3] = m_colors[i][3]

    mesh.update()
    mesh.validate()

    if texture and uvindices:
        pass
        # TODO add support for using texture.

        # import os
        # import sys
        # from bpy_extras.image_utils import load_image

        # encoding = sys.getfilesystemencoding()
        # encoded_texture = texture.decode(encoding=encoding)
        # name = bpy.path.display_name_from_filepath(texture)
        # image = load_image(encoded_texture, os.path.dirname(filepath), recursive=True, place_holder=True)

        # if image:
        #     texture = bpy.data.textures.new(name=name, type='IMAGE')
        #     texture.image = image

        #     material = bpy.data.materials.new(name=name)
        #     material.use_shadeless = True

        #     mtex = material.texture_slots.add()
        #     mtex.texture = texture
        #     mtex.texture_coords = 'UV'
        #     mtex.use_map_color_diffuse = True

        #     mesh.materials.append(material)
        #     for face in mesh.uv_textures[0].data:
        #         face.image = image

    return mesh

def load_ply_object(obj_spec, obj_def, texture, ply_name, mesh, normalize_vertex_groups):
    import bpy
    obj = bpy.data.objects.new(ply_name, mesh)

    vertex_groups = {}
    for el in obj_spec.specs:
        if el.name == b'vertex':
            for idx,p in enumerate(el.properties):
                group_name = p.name.decode("utf-8")
                if p.is_custom_property() and not group_name[-1].isdigit():
                    if p.numeric_type == 'f':
                        obj.vertex_groups.new(name=group_name)
                        vertex_groups[group_name] = idx
                    else:
                        print("Warning: Unsupported vertex group", p.name, "of type", p.numeric_type)

    vertices = obj_def[b'vertex']
    for group_name,idx in vertex_groups.items():
        group = obj.vertex_groups[group_name]
        if normalize_vertex_groups:
            v_min=min(vertices, key=lambda k:k[idx])[idx]
            v_max=max(vertices, key=lambda k:k[idx])[idx]
            # We don't have a foreach_set on the vertex group, so we have to set them one by one
            for v_idx,v in enumerate(vertices):
                weight = (v[idx]-v_min)/(v_max-v_min)
                if weight>0:
                    group.add([v_idx], weight, "REPLACE")
        else:
            # We don't have a foreach_set on the vertex group, so we have to set them one by one
            for v_idx,v in enumerate(vertices):
                weight = v[idx]
                if weight>0:
                    group.add([v_idx], weight, "REPLACE")

    return obj

def load_ply(filepath, import_vertex_groups, normalize_vertex_groups, import_custom_vertex_colors):
    import time
    import bpy

    t = time.time()
    ply_name = bpy.path.display_name_from_filepath(filepath)

    obj_spec, obj_def, texture = read(filepath)

    mesh = load_ply_mesh(obj_spec, obj_def, texture, ply_name, import_custom_vertex_colors)
    if not mesh:
        return {'CANCELLED'}

    if import_vertex_groups:
        obj = load_ply_object(obj_spec, obj_def, texture, ply_name, mesh, normalize_vertex_groups)
    else:
        obj = bpy.data.objects.new(ply_name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    print("\nSuccessfully imported %r in %.3f sec" % (filepath, time.time() - t))
    return {'FINISHED'}


def load(operator, context, filepath="", import_vertex_groups=True, normalize_vertex_groups=False, import_custom_vertex_colors=True):
    return load_ply(filepath, import_vertex_groups, normalize_vertex_groups, import_custom_vertex_colors)
