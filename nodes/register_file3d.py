"""
FILE_3D_GLB 产物登记节点（TRELLIS.2 等核心 3D 链路产物输出）

背景：ComfyUI 核心 Save3DAdvanced 把 FILE_3D 写进 output 后只在
history 的 ui["3d"] 键下登记，而 proxy daemon 的
_collect_local_images 只收 images/videos/gifs/audio 四键，
导致 .glb 产物对平台不可见（"幽灵文件"）。

本节点将 FILE_3D*（MeshToFile3D / Load3D 等产出，内存 BytesIO 或磁盘路径）
写入 output 目录，并按 ComfyUI 标准在 ui.images 中登记
{filename, subfolder, type=output}——daemon 会把它当普通文件走
process_and_upload（.glb 自动 octet-stream），后端/前端即可获得
可访问的产物 URL。与 YingceExportMesh 同一模式，差异仅在输入类型：
TRIMESH（Hy3D trimesh 对象） vs FILE_3D_GLB（核心 3D 节点对象）。
"""

import logging
import shutil
from pathlib import Path

import folder_paths

logger = logging.getLogger("ComfyUI-YingceDynamic")


class YingceRegisterFile3D:
    """把 FILE_3D* 写入 output 并在 ui.images 登记，供 daemon 收集上传"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # 与核心 SaveGLB/Save3DAdvanced 同口径的多类型列表：
                # 具体类型 (FILE_3D_GLB) 与通用类型 (FILE_3D) 都可连
                "model_3d": ("FILE_3D_GLB,FILE_3D_GLTF,FILE_3D_OBJ,FILE_3D_FBX,FILE_3D_STL,FILE_3D_USDZ,FILE_3D",),
                "filename_prefix": ("STRING", {"default": "3d/Yingce3D"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_path",)
    FUNCTION = "register"
    CATEGORY = "YingceAI/Dynamic"
    OUTPUT_NODE = True

    def register(self, model_3d, filename_prefix):
        output_dir = folder_paths.get_output_directory()
        full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, output_dir
        )
        full_folder = Path(full_folder)
        full_folder.mkdir(parents=True, exist_ok=True)

        file_format = getattr(model_3d, "format", "") or "glb"
        out_name = f"{filename}_{counter:05}_.{file_format}"
        out_path = full_folder / out_name

        # File3D 双后端：is_disk_backed=True 时 get_source() 返回路径字符串，
        # 否则 get_data() 读内存字节流（MeshToFile3D 产物即后者）
        source = model_3d.get_source()
        if isinstance(source, str):
            shutil.copyfile(source, out_path)
        else:
            data = model_3d.get_data()
            out_path.write_bytes(data.read())

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"YingceRegisterFile3D 写出失败或为空: {out_path}")

        logger.info(
            "YingceRegisterFile3D: 已写出 %s (%d bytes)",
            out_path, out_path.stat().st_size,
        )

        relative = str(Path(subfolder) / out_name) if subfolder else out_name
        ui_entry = {
            "filename": out_name,
            "subfolder": subfolder,
            "type": "output",
        }
        return {"ui": {"images": [ui_entry]}, "result": (relative,)}
