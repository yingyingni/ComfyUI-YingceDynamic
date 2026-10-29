"""
动态加载器节点

封装 LoadImage / LoadAudio 的批量加载，根据 count 参数决定加载多少个文件。
未使用的加载分支不会被执行（lazy 机制）。

核心原理：
1. 所有文件路径输入标记为 lazy: True（也支持转为链接输入）
2. check_lazy_status 根据 count 只请求需要的输入
3. 节点内部循环调用已注册的加载节点
4. 返回列表供下游使用（OUTPUT_IS_LIST）

音频加载顺序：
- 优先内置 LoadAudio（V3 节点，从 input 目录读取文件名）
- 失败回退 VHS_LoadAudio（支持路径 / URL）
"""

import logging

logger = logging.getLogger("ComfyUI-YingceDynamic")

MAX_LOAD_COUNT = 8


class DynamicLoadImageBatch:
    """动态加载多张图片

    根据 image_count 加载 1-N 张图片，返回 IMAGE 列表。
    未使用的路径不会触发文件加载。

    输入：
    - image_count: 要加载的图片数量 0-8
    - image1 ~ image8: 图片文件名（lazy: True）

    输出：
    - images: IMAGE 列表（OUTPUT_IS_LIST = True）
    - count: 实际加载的图片数量
    """

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, MAX_LOAD_COUNT + 1):
            optional[f"image{i}"] = ("STRING", {"lazy": True, "default": ""})
        return {
            "required": {
                "image_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": MAX_LOAD_COUNT,
                        "step": 1,
                        "tooltip": "要加载的图片数量",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "load_images"
    CATEGORY = "YingceAI/Dynamic"

    def check_lazy_status(self, image_count, **kwargs):
        """只请求需要加载的图片路径"""
        needed = []
        effective_count = min(image_count, MAX_LOAD_COUNT)
        for i in range(1, effective_count + 1):
            key = f"image{i}"
            if key in kwargs and kwargs[key] is None:
                needed.append(key)
        return needed

    def load_images(self, image_count, **kwargs):
        """加载多张图片"""
        load_image_cls = None
        try:
            import nodes as comfy_nodes
            load_image_cls = getattr(comfy_nodes, "LoadImage", None)
            if load_image_cls is None:
                load_image_cls = comfy_nodes.NODE_CLASS_MAPPINGS.get("LoadImage")
        except Exception:
            load_image_cls = None

        if load_image_cls is None:
            # fallback: 直接用 PIL 加载
            return self._load_with_pil(image_count, **kwargs)

        load_image_node = load_image_cls()
        images = []
        effective_count = min(image_count, MAX_LOAD_COUNT)

        for i in range(1, effective_count + 1):
            image_name = kwargs.get(f"image{i}", "")
            if not image_name:
                logger.warning("image %d 路径为空，跳过", i)
                continue

            try:
                result = load_image_node.load_image(image=image_name)
                if result and len(result) > 0:
                    images.append(result[0])
                    logger.info("DynamicLoadImageBatch: 加载 image %d = %s", i, image_name)
            except Exception as e:
                logger.error("加载 image %d (%s) 失败: %s", i, image_name, e)
                raise

        actual_count = len(images)
        logger.info("DynamicLoadImageBatch: 共加载 %d 张图片", actual_count)
        return (images, actual_count)

    def _load_with_pil(self, image_count, **kwargs):
        """PIL fallback 加载方式（按 ComfyUI input 目录解析文件名）"""
        import torch
        import numpy as np
        from PIL import Image
        import folder_paths

        images = []
        effective_count = min(image_count, MAX_LOAD_COUNT)

        for i in range(1, effective_count + 1):
            image_name = kwargs.get(f"image{i}", "")
            if not image_name:
                continue

            try:
                image_path = folder_paths.get_annotated_filepath(image_name)
                img = Image.open(image_path).convert("RGB")
                img_array = np.array(img).astype(np.float32) / 255.0
                img_tensor = torch.from_numpy(img_array).unsqueeze(0)
                images.append(img_tensor)
                logger.info("DynamicLoadImageBatch (PIL): 加载 image %d = %s", i, image_name)
            except Exception as e:
                logger.error("PIL 加载 image %d (%s) 失败: %s", i, image_name, e)
                raise

        actual_count = len(images)
        return (images, actual_count)


class DynamicLoadAudioBatch:
    """动态加载多个音频

    根据 audio_count 加载 1-N 个音频文件，返回 AUDIO 列表。
    未使用的路径不会触发文件加载。

    输入：
    - audio_count: 要加载的音频数量 0-8
    - audio1 ~ audio8: 音频文件名或路径（lazy: True）

    输出：
    - audios: AUDIO 列表（OUTPUT_IS_LIST = True）
    - count: 实际加载的音频数量
    """

    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(1, MAX_LOAD_COUNT + 1):
            optional[f"audio{i}"] = ("STRING", {"lazy": True, "default": ""})
        return {
            "required": {
                "audio_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": MAX_LOAD_COUNT,
                        "step": 1,
                        "tooltip": "要加载的音频数量",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("AUDIO", "INT")
    RETURN_NAMES = ("audios", "count")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "load_audios"
    CATEGORY = "YingceAI/Dynamic"

    def check_lazy_status(self, audio_count, **kwargs):
        """只请求需要加载的音频路径"""
        needed = []
        effective_count = min(audio_count, MAX_LOAD_COUNT)
        for i in range(1, effective_count + 1):
            key = f"audio{i}"
            if key in kwargs and kwargs[key] is None:
                needed.append(key)
        return needed

    @staticmethod
    def _load_one_audio(audio_name):
        """加载单个音频：优先内置 LoadAudio，失败回退 VHS_LoadAudio

        - 内置 LoadAudio（comfy_extras/nodes_audio.py，V3 IO.ComfyNode）：
          cls.execute(audio=文件名) -> IO.NodeOutput，按 input 目录解析
        - VHS_LoadAudio（ComfyUI-VideoHelperSuite）：
          inst.load_audio(audio_file=路径) -> (audio, duration)，支持路径/URL
        """
        import nodes as comfy_nodes

        errors = []

        builtin_cls = comfy_nodes.NODE_CLASS_MAPPINGS.get("LoadAudio")
        if builtin_cls is not None:
            try:
                res = builtin_cls.execute(audio=audio_name)
                # V3 NodeOutput 有 result 属性；老版本直接返回 tuple
                payload = getattr(res, "result", res)
                audio = payload[0] if isinstance(payload, (tuple, list)) else payload
                if audio is not None:
                    return audio
            except Exception as e:
                errors.append(f"内置 LoadAudio: {e}")

        vhs_cls = comfy_nodes.NODE_CLASS_MAPPINGS.get("VHS_LoadAudio")
        if vhs_cls is not None:
            try:
                res = vhs_cls().load_audio(audio_file=audio_name)
                if res and len(res) > 0 and res[0] is not None:
                    return res[0]
            except Exception as e:
                errors.append(f"VHS_LoadAudio: {e}")

        detail = "; ".join(errors) if errors else "未找到 LoadAudio / VHS_LoadAudio 节点"
        raise RuntimeError(f"加载音频 '{audio_name}' 失败: {detail}")

    def load_audios(self, audio_count, **kwargs):
        """加载多个音频"""
        audios = []
        effective_count = min(audio_count, MAX_LOAD_COUNT)

        for i in range(1, effective_count + 1):
            audio_name = kwargs.get(f"audio{i}", "")
            if not audio_name:
                logger.warning("audio %d 路径为空，跳过", i)
                continue

            audio = self._load_one_audio(audio_name)
            audios.append(audio)
            logger.info("DynamicLoadAudioBatch: 加载 audio %d = %s", i, audio_name)

        actual_count = len(audios)
        logger.info("DynamicLoadAudioBatch: 共加载 %d 个音频", actual_count)
        return (audios, actual_count)
