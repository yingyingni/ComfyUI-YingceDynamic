"""
ComfyUI-YingceDynamic 自定义节点包
提供动态控制 PlanV2 链路的封装节点，利用 ComfyUI 懒加载机制实现按需执行。

节点列表：
- DynamicPlanV2AudioChain: 动态音频引用链路（1-N 个音频，按 count 选择执行）
- DynamicPlanV2ImageChain: 动态图片引用链路（1-N 张图片，按 count 选择执行）
- DynamicLoadImageBatch: 动态加载多张图片（按 count 选择执行）
- DynamicLoadAudioBatch: 动态加载多个音频（按 count 选择执行）
- SanitizeAudio: 清洗音频波形中的 NaN/Inf，防止 AAC 编码崩溃
- YingceExportMesh: TRIMESH 导出并在 ui.images 登记（Hy3D 白模/贴图产物回传）
- YingceRegisterFile3D: FILE_3D_GLB 写盘并在 ui.images 登记（核心 3D 节点产物回传）
"""

from .nodes.dynamic_planv2_chains import (
    DynamicPlanV2AudioChain,
    DynamicPlanV2ImageChain,
)
from .nodes.dynamic_loaders import (
    DynamicLoadImageBatch,
    DynamicLoadAudioBatch,
)
from .nodes.sanitize_audio import SanitizeAudio
from .nodes.subject_prompt import YingceSubjectPrompt
from .nodes.export_mesh import YingceExportMesh
from .nodes.register_file3d import YingceRegisterFile3D

NODE_CLASS_MAPPINGS = {
    "DynamicPlanV2AudioChain": DynamicPlanV2AudioChain,
    "DynamicPlanV2ImageChain": DynamicPlanV2ImageChain,
    "DynamicLoadImageBatch": DynamicLoadImageBatch,
    "DynamicLoadAudioBatch": DynamicLoadAudioBatch,
    "SanitizeAudio": SanitizeAudio,
    "YingceSubjectPrompt": YingceSubjectPrompt,
    "YingceExportMesh": YingceExportMesh,
    "YingceRegisterFile3D": YingceRegisterFile3D,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DynamicPlanV2AudioChain": "Dynamic PlanV2 Audio Chain (Yingce)",
    "DynamicPlanV2ImageChain": "Dynamic PlanV2 Image Chain (Yingce)",
    "DynamicLoadImageBatch": "Dynamic Load Image Batch (Yingce)",
    "DynamicLoadAudioBatch": "Dynamic Load Audio Batch (Yingce)",
    "SanitizeAudio": "Sanitize Audio (Yingce)",
    "YingceSubjectPrompt": "Subject-aware Prompt (Yingce)",
    "YingceExportMesh": "Export 3D Mesh to output (Yingce)",
    "YingceRegisterFile3D": "Register 3D File to output (Yingce)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
