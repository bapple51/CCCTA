"""Convert a self-contained glTF (embedded base64 buffers/images) to OBJ+MTL+PNG
in Unreal space: Y-up right-handed metres -> Z-up left-handed centimetres."""
import base64, json, os, struct, sys

CT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2),
      5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
SCALE = 100.0  # glTF metres -> Unreal centimetres


def data_uri_bytes(uri):
    if not uri.startswith('data:'):
        raise SystemExit('external resource not supported: ' + uri[:40])
    return base64.b64decode(uri.split(',', 1)[1])


def read_accessor(g, buffers, idx):
    acc = g['accessors'][idx]
    n = NCOMP[acc['type']]
    fmt, size = CT[acc['componentType']]
    if 'bufferView' not in acc:
        return [(0,) * n] * acc['count']
    bv = g['bufferViews'][acc['bufferView']]
    buf = buffers[bv['buffer']]
    base = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    stride = bv.get('byteStride') or size * n
    out = []
    for i in range(acc['count']):
        out.append(struct.unpack_from('<' + fmt * n, buf, base + i * stride))
    return out


def mat_mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
            for r in range(4) for c in range(4)]


def trs_matrix(node):
    if 'matrix' in node:  # glTF stores matrices column-major
        m = node['matrix']
        return [m[c * 4 + r] for r in range(4) for c in range(4)]
    t = node.get('translation', [0, 0, 0])
    r = node.get('rotation', [0, 0, 0, 1])
    s = node.get('scale', [1, 1, 1])
    x, y, z, w = r
    rot = [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0,
           2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0,
           2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0,
           0, 0, 0, 1]
    scl = [s[0], 0, 0, 0, 0, s[1], 0, 0, 0, 0, s[2], 0, 0, 0, 0, 1]
    trn = [1, 0, 0, t[0], 0, 1, 0, t[1], 0, 0, 1, t[2], 0, 0, 0, 1]
    return mat_mul(trn, mat_mul(rot, scl))


def xform_point(m, p):
    return tuple(m[r * 4] * p[0] + m[r * 4 + 1] * p[1] +
                 m[r * 4 + 2] * p[2] + m[r * 4 + 3] for r in range(3))


def xform_dir(m, v):
    return tuple(m[r * 4] * v[0] + m[r * 4 + 1] * v[1] +
                 m[r * 4 + 2] * v[2] for r in range(3))


def to_unreal_pos(p):
    # gltf +X right, +Y up, -Z forward  ->  ue +X forward, +Y right, +Z up
    return (-p[2] * SCALE, p[0] * SCALE, p[1] * SCALE)


def to_unreal_dir(v):
    return (-v[2], v[0], v[1])


def mat_name(base_name, gi, count):
    """Material names land in the content browser as-is, so keep them unique
    per model: M_SM_TileGreen -> M_TileGreen, and only suffix when there are
    several material groups in the one file."""
    stem = base_name[3:] if base_name.startswith('SM_') else base_name
    return 'M_%s' % stem if count == 1 else 'M_%s_%d' % (stem, gi)


def convert(src, out_dir, base_name):
    g = json.load(open(src, encoding='utf-8'))
    buffers = [data_uri_bytes(b['uri']) for b in g.get('buffers', [])]

    os.makedirs(out_dir, exist_ok=True)
    images = g.get('images', [])
    img_files = {}
    for i, img in enumerate(images):
        fn = base_name + ('_T%d.png' % i if len(images) > 1 else '_T.png')
        with open(os.path.join(out_dir, fn), 'wb') as fh:
            fh.write(data_uri_bytes(img['uri']))
        img_files[i] = fn

    def mat_texture(mi):
        try:
            pbr = g['materials'][mi]['pbrMetallicRoughness']
            ti = pbr['baseColorTexture']['index']
            return img_files.get(g['textures'][ti]['source'])
        except (KeyError, IndexError, TypeError):
            return None

    verts, uvs, norms, groups = [], [], [], {}

    def walk(node_idx, parent):
        node = g['nodes'][node_idx]
        world = mat_mul(parent, trs_matrix(node))
        if 'mesh' in node:
            for prim in g['meshes'][node['mesh']]['primitives']:
                if prim.get('mode', 4) != 4:
                    continue  # triangles only
                attrs = prim['attributes']
                pos = read_accessor(g, buffers, attrs['POSITION'])
                nrm = read_accessor(g, buffers, attrs['NORMAL']) if 'NORMAL' in attrs else None
                tex = read_accessor(g, buffers, attrs['TEXCOORD_0']) if 'TEXCOORD_0' in attrs else None
                idx = ([i[0] for i in read_accessor(g, buffers, prim['indices'])]
                       if 'indices' in prim else list(range(len(pos))))

                v0 = len(verts) + 1  # OBJ indices are 1-based
                for p in pos:
                    verts.append(to_unreal_pos(xform_point(world, p)))
                if tex:
                    for t in tex:
                        uvs.append((t[0], 1.0 - t[1]))  # glTF UV origin is top-left
                if nrm:
                    for n in nrm:
                        norms.append(to_unreal_dir(xform_dir(world, n)))

                key = mat_texture(prim['material']) if 'material' in prim else None
                faces = groups.setdefault(key, [])
                for i in range(0, len(idx) - 2, 3):
                    a, b, c = idx[i] + v0, idx[i + 1] + v0, idx[i + 2] + v0
                    # the RH->LH mirror flips winding; reverse it so normals face out
                    faces.append((a, c, b))
        for child in node.get('children', []):
            walk(child, world)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    scene = g.get('scenes', [{}])[g.get('scene', 0)]
    for root in scene.get('nodes', range(len(g.get('nodes', [])))):
        walk(root, ident)

    obj_path = os.path.join(out_dir, base_name + '.obj')
    mtl_name = base_name + '.mtl'
    has_uv, has_n = bool(uvs), bool(norms)
    with open(obj_path, 'w', encoding='utf-8') as f:
        f.write('# converted from %s (Unreal space: Z-up, cm)\n' % os.path.basename(src))
        f.write('mtllib %s\n' % mtl_name)
        for v in verts:
            f.write('v %.6f %.6f %.6f\n' % v)
        for t in uvs:
            f.write('vt %.6f %.6f\n' % t)
        for n in norms:
            f.write('vn %.6f %.6f %.6f\n' % n)
        for gi, (tex, faces) in enumerate(groups.items()):
            f.write('g %s_%d\n' % (base_name, gi))
            f.write('usemtl %s\n' % mat_name(base_name, gi, len(groups)))
            for a, b, c in faces:
                if has_uv and has_n:
                    f.write('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a, a, a, b, b, b, c, c, c))
                elif has_uv:
                    f.write('f %d/%d %d/%d %d/%d\n' % (a, a, b, b, c, c))
                else:
                    f.write('f %d %d %d\n' % (a, b, c))

    with open(os.path.join(out_dir, mtl_name), 'w', encoding='utf-8') as f:
        for gi, tex in enumerate(groups):
            f.write('newmtl %s\n' % mat_name(base_name, gi, len(groups)))
            f.write('Kd 1.000 1.000 1.000\n')
            if tex:
                f.write('map_Kd %s\n' % tex)
            f.write('\n')

    tris = sum(len(v) for v in groups.values())
    textures = sorted(set(t for t in groups if t))
    print('%-30s verts=%-6d tris=%-6d groups=%d tex=%s'
          % (base_name, len(verts), tris, len(groups), ','.join(textures) or 'none'))
    return obj_path


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
