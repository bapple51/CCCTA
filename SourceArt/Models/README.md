# Source Models

Authoring-source 3D models for CCCTA_DefenceUE5. These are the editable
originals — Unreal never reads from here at runtime. The imported assets live
in `/Game/Meshes/<Category>/`.

All files are Blockbench 5.1.6 glTF exports. Geometry buffers and textures are
embedded as base64 data URIs, so each `.gltf` is fully self-contained — there
are no sidecar `.bin` or `.png` files to keep next to it.

## Layout

| Source | Imported asset | Size (cm) | Tris |
|---|---|---|---|
| `Buildings/SM_BuildingWall.gltf` | `/Game/Meshes/Buildings/SM_BuildingWall` | 62.5 x 43.75 x 115.6 | 132 |
| `Buildings/SM_BuildingWallWindowless.gltf` | `/Game/Meshes/Buildings/SM_BuildingWallWindowless` | 62.5 x 43.75 x 115.6 | 36 |
| `Buildings/SM_BuildingCorner.gltf` | `/Game/Meshes/Buildings/SM_BuildingCorner` | 62.5 x 62.5 x 115.6 | 240 |
| `Roads/SM_Roundabout.gltf` | `/Game/Meshes/Roads/SM_Roundabout` | 93.75 x 98.6 x 12.5 | 80 |
| `Tiles/SM_TileGreen.gltf` | `/Game/Meshes/Tiles/SM_TileGreen` | 50 x 50 x 6.25 | 12 |
| `Tiles/SM_TileBlue.gltf` | `/Game/Meshes/Tiles/SM_TileBlue` | 50 x 50 x 6.25 | 12 |
| `Tiles/SM_TileRoofRed.gltf` | `/Game/Meshes/Tiles/SM_TileRoofRed` | 50 x 50 x 6.25 | 12 |

Every mesh has its origin at the centre of its footprint with the geometry
sitting on `Z = 0`, so actors drop straight onto the ground plane.

## Import pipeline

Unreal's own glTF importer (Interchange) works via drag-and-drop, but the
editor's scripting/MCP import path only accepts `fbx` and `obj`. To keep
imports scriptable, `Tools/gltf2obj.py` converts glTF to OBJ first:

    <UE>/Engine/Binaries/ThirdParty/Python3/Win64/python.exe Tools/gltf2obj.py \
        SourceArt/Models/Tiles/SM_TileGreen.gltf \
        SourceArt/Models/_Converted/Tiles SM_TileGreen

It bakes the node hierarchy flat and converts coordinate systems — glTF is
Y-up right-handed in metres, Unreal is Z-up left-handed in centimetres — which
also mirrors the geometry, so triangle winding is reversed to keep normals
facing outwards. Embedded textures are written out as `<Name>_T*.png` and
referenced from a generated `.mtl`. Material names are made unique per model
(`M_TileGreen` rather than the exporter's `mat0`), because they land in the
content browser as-is and would otherwise collide between models.

Output goes to `_Converted/`, which is gitignored — it is regenerable.

## Texture settings

These are 16x16 pixel-art atlases. Unreal's import defaults (bilinear filter,
DXT compression, mipmaps) smooth them out, and because a whole model shares one
tiny atlas, mipmapping also bleeds neighbouring faces into each other. Every
imported texture is set to:

    Filter               TF_Nearest       crisp texel edges
    MipGenSettings       TMGS_NoMipmaps   no cross-face bleeding on a 16px atlas
    CompressionSettings  TC_EditorIcon    uncompressed RGBA, no block artifacts

Reimporting a texture resets these to the defaults, so reapply them afterwards.

## Adding a model

1. Export from Blockbench as glTF into the matching category folder.
2. Name it `SM_<PascalCase>.gltf` — the same name the Unreal asset will carry.
3. Run `Tools/gltf2obj.py` on it, import the resulting `.obj`, then apply the
   texture settings above.
4. Add a row to the table.

## Renamed from the original download

    buildingwall.gltf            -> Buildings/SM_BuildingWall.gltf
    buildingwallwindowless.gltf  -> Buildings/SM_BuildingWallWindowless.gltf
    cornerbuildVFinall.gltf      -> Buildings/SM_BuildingCorner.gltf
    roundabout.gltf              -> Roads/SM_Roundabout.gltf
    Tile green.gltf              -> Tiles/SM_TileGreen.gltf
    tile_blue.gltf               -> Tiles/SM_TileBlue.gltf
    tiles_red.gltf               -> Tiles/SM_TileRoofRed.gltf
