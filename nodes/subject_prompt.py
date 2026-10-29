"""
YingceSubjectPrompt：按上传图主体类型（人像 / 商品·物体 / 通用兜底）
选择对应的去水印效果图 prompt 文案，供 Qwen Image Edit 编码节点直接使用。

设计要点：
- 纯 CPU、零新增 pip 依赖（仅用 ComfyUI 环境自带的 cv2 + numpy）
- 人脸检测用 OpenCV YuNet（FaceDetectorYN），模型文件放在
  models/facedetect/face_detection_yunet_2023mar.onnx
- 模型文件缺失或检测异常时，一律回落 generic 措辞，绝不影响出图
- 检测结果与所选措辞写入日志，便于排查
"""

import os
import cv2
import numpy as np
import folder_paths


# YuNet onnx 模型搜索路径（按优先级）
_YUNET_CANDIDATES = [
    os.path.join(folder_paths.models_dir, "facedetect", "face_detection_yunet_2023mar.onnx"),
    os.path.join(folder_paths.models_dir, "face_detection_yunet_2023mar.onnx"),
]

_detector_cache = {}


def _get_detector(input_w, input_h):
    """按输入分辨率构造/复用 YuNet 检测器；模型缺失返回 None。"""
    model_path = next((p for p in _YUNET_CANDIDATES if os.path.isfile(p)), None)
    if not model_path:
        return None
    key = (model_path, input_w, input_h)
    if key not in _detector_cache:
        try:
            _detector_cache[key] = cv2.FaceDetectorYN.create(
                model_path, "", (input_w, input_h), score_threshold=0.6
            )
        except Exception:
            _detector_cache[key] = None
    return _detector_cache[key]


def _has_face(image_tensor):
    """
    ComfyUI IMAGE tensor (B,H,W,C, float 0-1) → 是否检测到人脸。
    两次尝试：原分辨率 + 放大到 >=640（小脸召回），任一命中即算人像。
    """
    try:
        frame = image_tensor[0].cpu().numpy()
        bgr = np.clip(frame * 255.0, 0, 255).astype(np.uint8)[:, :, ::-1].copy()
        h, w = bgr.shape[:2]
        for scale in (1.0, max(1.0, 640.0 / min(h, w))):
            img = bgr if scale == 1.0 else cv2.resize(
                bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR
            )
            ih, iw = img.shape[:2]
            det = _get_detector(iw, ih)
            if det is None:
                return False
            det.setInputSize((iw, ih))
            _, faces = det.detect(img)
            if faces is not None and len(faces) > 0:
                return True
    except Exception:
        pass
    return False


class YingceSubjectPrompt:
    """按主体类型输出对应 prompt 文案：人脸→person，否则→product，留空→generic。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "prompt_person": ("STRING", {"multiline": True, "default": ""}),
                "prompt_product": ("STRING", {"multiline": True, "default": ""}),
                "prompt_generic": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "subject_type")
    FUNCTION = "pick"
    CATEGORY = "Yingce/prompt"

    def pick(self, image, prompt_person="", prompt_product="", prompt_generic=""):
        has_face = _has_face(image)
        subject = "person" if has_face else "product"
        text = (prompt_person if has_face else prompt_product).strip()
        if not text:
            text = prompt_generic.strip()
            if text:
                subject = "generic"
        print(f"[YingceSubjectPrompt] face={has_face} → subject={subject}")
        return (text, subject)
