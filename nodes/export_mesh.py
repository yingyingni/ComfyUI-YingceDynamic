"""
3D 模型导出节点（白模贴图链路产物输出）

背景：Hunyuan3D-2.1 的 Hy3D21ExportMesh/Hy3DInPaint 只返回 STRING 路径，
不会向 ComfyUI history 写入 ui 记录，导致 proxy daemon 的
_collect_local_images 收集不到 .glb 产物（"幽灵文件"）。

本节点将 TRIMESH 导出到 output 目录，并按 ComfyUI 标准在
ui.images 中登记 {filename, subfolder, type=output}——daemon 会把它
当普通文件走 process_and_upload（.glb 自动 octet-stream，缩略图
失败回退原文件），后端/前端即可获得可访问的产物 URL。

注意：TRIMESH 由 Hy3D 系列节点产出（trimesh.Trimesh），贴图已内嵌
到网格材质，导出 glb 时纹理随包写入。
"""

import logging
import os
from pathlib import Path

import folder_paths

logger = logging.getLogger("ComfyUI-YingceDynamic")


class YingceExportMesh:
    """导出 TRIMESH 为 glb/obj 并在 ui.images 登记，供 daemon 收集上传"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trimesh": ("TRIMESH",),
                "filename_prefix": ("STRING", {"default": "3D/YingceTex"}),
                "file_format": (["glb", "obj", "ply"], {"default": "glb"}),
            },
        }

    RETURN_TYPES = ("STRING", "TRIMESH")
    RETURN_NAMES = ("file_path", "trimesh")
    FUNCTION = "export"
    CATEGORY = "YingceAI/Dynamic"
    OUTPUT_NODE = True

    def export(self, trimesh, filename_prefix, file_format):
        output_dir = folder_paths.get_output_directory()
        full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, output_dir
        )
        full_folder = Path(full_folder)
        full_folder.mkdir(parents=True, exist_ok=True)

        out_name = f"{filename}_{counter:05}_.{file_format}"
        out_path = full_folder / out_name

        # trimesh.Trimesh.export：glb 会把已烘焙的 PBR 材质一并打包
        trimesh.export(str(out_path), file_type=file_format)
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"YingceExportMesh 导出失败或为空: {out_path}")

        logger.info(
            "YingceExportMesh: 已导出 %s (%d bytes)",
            out_path, out_path.stat().st_size,
        )

        relative = str(Path(subfolder) / out_name) if subfolder else out_name
        ui_entry = {
            "filename": out_name,
            "subfolder": subfolder,
            "type": "output",
        }
        # result 给下游节点用（trimesh 透传便于再接 Hy3D21ExportMesh 等）；
        # ui.images 供 daemon 收集上传
        return {"ui": {"images": [ui_entry]}, "result": (relative, trimesh)}
