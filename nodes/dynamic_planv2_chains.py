"""
DynamicPlanV2 链路节点

封装 MiniMaxH3PlanV2AudioReference / MiniMaxH3PlanV2ImageReference 的链式调用，
利用 ComfyUI 的 check_lazy_status + lazy: True 机制实现按需执行。

核心原理：
1. 所有 audio/image 输入标记为 lazy: True
2. check_lazy_status 根据 count 只请求需要的输入
3. 未被请求的输入分支不会被 ComfyUI 执行
4. 节点内部直接调用 PlanV2 节点的 add_audio/add_image 方法构建链路

兼容性：
- 不修改 PlanV2 插件源码
- 通过 importlib 动态加载 PlanV2 节点类与枚举常量
- PLAN_TYPE 类型字符串与 PlanV2 保持一致
- 枚举值优先从 PlanV2 模块实时读取，失败时使用本地兜底常量
  （兜底值与 plan_v2.py 当前版本逐一核对过，PlanV2 内部做严格枚举校验）
"""

import logging
import importlib

logger = logging.getLogger("ComfyUI-YingceDynamic")

# PlanV2 类型常量（与 ComfyUI-MiniMax-H3-Guide/plan_v2.py 保持一致）
PLAN_TYPE = "MINIMAX_H3_PLAN_V2"

# 最大支持的 audio/image 数量
MAX_AUDIO_REFS = 8
MAX_IMAGE_REFS = 8

# ---- 本地兜底枚举（与 plan_v2.py 常量完全一致，仅作动态加载失败时的备用） ----
UNASSIGNED_CONTENT_TYPE = "Choose visible content type"

_FALLBACK_IMAGE_USES = [
    "Define reusable visible content",
    "Exact first frame",
    "Exact last frame",
    "Concrete keyframe / composition anchor",
    "Storyboard / shot planning",
]

_FALLBACK_CONTENT_TYPES = [
    UNASSIGNED_CONTENT_TYPE,
    "Identity or appearance",
    "Object, prop, clothing, interface, or visual effect",
    "Scene or environment",
    "Visual style",
    "Pose, expression, action, or motion",
]

_FALLBACK_RETENTIONS = [
    "Auto for this relationship",
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "weak_reference",
]

_FALLBACK_AUDIO_USES = [
    "Voice timbre and delivery",
    "Background-music style",
    "Beat or rhythm",
    "Sound-effect texture",
    "Dialogue or lyric content",
    "Audio continuity",
    "Copy complete signal",
    "Copy selected part or layers",
    "Broad audio inspiration",
]


def _planv2_module():
    """动态加载 PlanV2 模块，失败返回 None"""
    try:
        return importlib.import_module(
            "custom_nodes.ComfyUI-MiniMax-H3-Guide.plan_v2"
        )
    except Exception as e:
        logger.warning("PlanV2 模块暂不可用: %s", e)
        return None


def _planv2_enum(attr, fallback, skip_first=False):
    """从 PlanV2 模块读取枚举常量，失败时使用本地兜底值

    skip_first: USES 类列表首项是 "Choose..." 占位符，需跳过
    """
    module = _planv2_module()
    if module is not None:
        values = getattr(module, attr, None)
        if values:
            values = list(values)
            return values[1:] if skip_first else values
    return list(fallback)


def _audio_uses():
    return _planv2_enum("AUDIO_USES", _FALLBACK_AUDIO_USES, skip_first=True)


def _image_uses():
    return _planv2_enum("IMAGE_USES", _FALLBACK_IMAGE_USES, skip_first=True)


def _content_types():
    return _planv2_enum("CONTENT_TYPES", _FALLBACK_CONTENT_TYPES)


def _retentions():
    return _planv2_enum("VISUAL_RETENTIONS", _FALLBACK_RETENTIONS)


def _get_planv2_audio_class():
    """动态获取 MiniMaxH3PlanV2AudioReference 类"""
    module = _planv2_module()
    if module is None:
        raise ImportError("ComfyUI-MiniMax-H3-Guide 插件未安装或无法加载")
    return module.MiniMaxH3PlanV2AudioReference


def _get_planv2_image_class():
    """动态获取 MiniMaxH3PlanV2ImageReference 类"""
    module = _planv2_module()
    if module is None:
        raise ImportError("ComfyUI-MiniMax-H3-Guide 插件未安装或无法加载")
    return module.MiniMaxH3PlanV2ImageReference


def _build_lazy_optional_inputs(type_name: str, max_count: int):
    """构建 lazy optional 输入字典"""
    optional = {}
    for i in range(1, max_count + 1):
        optional[f"input{i}"] = (type_name, {"lazy": True})
    return optional


class DynamicPlanV2AudioChain:
    """动态 PlanV2 音频引用链路

    封装多个 MiniMaxH3PlanV2AudioReference 节点的链式调用。
    根据 audio_count 参数决定执行多少个音频引用分支。
    未被选中的分支（包括 LoadAudio 等上游节点）不会被执行。

    各 audio_use 的必填伴随参数（PlanV2 内部校验）：
    - Voice timbre and delivery / Dialogue or lyric content: target_speaker
    - Dialogue or lyric content: 另需 language + transcript
    - Music/Beat/SFX/Continuity/Broad 类: target_layer_or_event
    - Copy selected part or layers: instructions
    - Copy complete signal: 无额外必填

    输入：
    - h3_plan: 前置 PlanV2 节点输出（required）
    - audio_count: 音频数量 0-8（required）
    - input1 ~ input8: AUDIO 类型输入（optional, lazy: True）
    - 每个 index 配套 audio_use/reference_name/target_speaker/
      language/transcript/target_layer_or_event/instructions/shot_scope

    输出：
    - h3_plan: 链路终点 PLAN_TYPE
    - preview: 各引用摘要
    """

    @classmethod
    def INPUT_TYPES(cls):
        uses = _audio_uses()
        optional = _build_lazy_optional_inputs("AUDIO", MAX_AUDIO_REFS)
        # 每个 index 的默认用途（均为 PlanV2 合法枚举值）
        defaults = [
            "Voice timbre and delivery",
            "Sound-effect texture",
            "Background-music style",
            "Beat or rhythm",
            "Audio continuity",
            "Broad audio inspiration",
            "Copy complete signal",
            "Dialogue or lyric content",
        ]
        for i in range(1, MAX_AUDIO_REFS + 1):
            default_use = defaults[i - 1]
            if default_use not in uses:
                default_use = uses[0]
            optional[f"audio_use{i}"] = (uses, {"default": default_use})
            optional[f"reference_name{i}"] = (
                "STRING",
                {"default": f"audio reference {i}"},
            )
            optional[f"target_speaker{i}"] = (
                "STRING",
                {"default": "", "tooltip": "Voice/Content 用途必填"},
            )
            optional[f"language{i}"] = (
                "STRING",
                {"default": "", "tooltip": "Dialogue or lyric content 必填"},
            )
            optional[f"transcript{i}"] = (
                "STRING",
                {"default": "", "multiline": True},
            )
            optional[f"target_layer_or_event{i}"] = (
                "STRING",
                {"default": "", "tooltip": "Music/Beat/SFX/Continuity/Broad 用途必填"},
            )
            optional[f"instructions{i}"] = (
                "STRING",
                {"default": "", "multiline": True},
            )
            optional[f"shot_scope{i}"] = (
                "STRING",
                {"default": ""},
            )

        return {
            "required": {
                "h3_plan": (
                    PLAN_TYPE,
                    {"tooltip": "Connect the preceding Plan v2 setup node."},
                ),
                "audio_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": MAX_AUDIO_REFS,
                        "step": 1,
                        "tooltip": "实际使用的音频数量。0 表示不添加任何音频引用。",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = (PLAN_TYPE, "STRING")
    RETURN_NAMES = ("h3_plan", "preview")
    FUNCTION = "build_chain"
    CATEGORY = "YingceAI/Dynamic"

    def check_lazy_status(self, h3_plan, audio_count, **kwargs):
        """根据 audio_count 只请求需要的音频输入"""
        needed = []
        effective_count = min(audio_count, MAX_AUDIO_REFS)
        for i in range(1, effective_count + 1):
            key = f"input{i}"
            if key in kwargs and kwargs[key] is None:
                needed.append(key)
        return needed

    def build_chain(self, h3_plan, audio_count, **kwargs):
        """构建音频引用链路"""
        audio_cls = _get_planv2_audio_class()
        audio_node = audio_cls()

        current_plan = h3_plan
        effective_count = min(audio_count, MAX_AUDIO_REFS)
        previews = []

        for i in range(1, effective_count + 1):
            audio = kwargs.get(f"input{i}")
            if audio is None:
                logger.warning("audio %d 为 None，跳过", i)
                continue

            audio_use = kwargs.get(f"audio_use{i}", "Sound-effect texture")
            reference_name = kwargs.get(f"reference_name{i}", f"audio reference {i}")

            try:
                result = audio_node.add_audio(
                    h3_plan=current_plan,
                    audio=audio,
                    audio_use=audio_use,
                    reference_name=reference_name,
                    target_speaker=kwargs.get(f"target_speaker{i}", "") or "",
                    language=kwargs.get(f"language{i}", "") or "",
                    transcript=kwargs.get(f"transcript{i}", "") or "",
                    target_layer_or_event=kwargs.get(f"target_layer_or_event{i}", "") or "",
                    instructions=kwargs.get(f"instructions{i}", "") or "",
                    shot_scope=kwargs.get(f"shot_scope{i}", "") or "",
                )
                current_plan = result[0]
                preview = result[2] if len(result) > 2 else f"Audio {i} added"
                previews.append(preview)
                logger.info("DynamicPlanV2AudioChain: 添加 audio %d (%s)", i, audio_use)
            except Exception as e:
                logger.error("添加 audio %d 失败: %s", i, e)
                raise

        combined_preview = " | ".join(previews) if previews else "No audio references added"
        return (current_plan, combined_preview)


class DynamicPlanV2ImageChain:
    """动态 PlanV2 图片引用链路

    封装多个 MiniMaxH3PlanV2ImageReference 节点的链式调用。
    根据 image_count 参数决定执行多少个图片引用分支。

    各 image_use 的必填伴随参数（PlanV2 内部校验）：
    - Define reusable visible content: content_type(非占位符) + subject_name
    - Concrete keyframe / composition anchor: shot_scope(数值)
    - Exact first/last frame: shot_scope 必须为空
    - 其余用途: content_type 必须保持 "Choose visible content type"，
      subject_name 必须为空
    - attribute_transfer retention: transfer_target_subject 必填

    输入：
    - h3_plan: 前置 PlanV2 节点输出（required）
    - image_count: 图片数量 0-8（required）
    - input1 ~ input8: IMAGE 类型输入（optional, lazy: True）
    - 每个 index 配套 image_use/reference_name/description/
      content_type/subject_name/retention/shot_scope/transfer_target_subject

    输出：
    - h3_plan: 链路终点 PLAN_TYPE
    - preview: 各引用摘要
    """

    @classmethod
    def INPUT_TYPES(cls):
        uses = _image_uses()
        content_types = _content_types()
        retentions = _retentions()
        optional = _build_lazy_optional_inputs("IMAGE", MAX_IMAGE_REFS)
        # 每个 index 的默认用途（均为 PlanV2 合法枚举值）
        defaults = [
            "Define reusable visible content",
            "Storyboard / shot planning",
            "Storyboard / shot planning",
            "Concrete keyframe / composition anchor",
            "Exact first frame",
            "Exact last frame",
            "Storyboard / shot planning",
            "Storyboard / shot planning",
        ]
        for i in range(1, MAX_IMAGE_REFS + 1):
            default_use = defaults[i - 1]
            if default_use not in uses:
                default_use = uses[0]
            optional[f"image_use{i}"] = (uses, {"default": default_use})
            optional[f"reference_name{i}"] = (
                "STRING",
                {"default": f"image reference {i}"},
            )
            optional[f"description{i}"] = (
                "STRING",
                {"default": "", "multiline": True},
            )
            optional[f"content_type{i}"] = (
                content_types,
                {
                    "default": UNASSIGNED_CONTENT_TYPE,
                    "tooltip": "仅 Define reusable visible content 需要选择具体类型",
                },
            )
            optional[f"subject_name{i}"] = (
                "STRING",
                {"default": "", "tooltip": "仅 Define reusable visible content 必填"},
            )
            optional[f"retention{i}"] = (
                retentions,
                {"default": "Auto for this relationship"},
            )
            optional[f"shot_scope{i}"] = (
                "STRING",
                {"default": "", "tooltip": "Keyframe 用途必填(数值)；first/last frame 必须留空"},
            )
            optional[f"transfer_target_subject{i}"] = (
                "STRING",
                {"default": "", "tooltip": "retention 为 attribute_transfer 时必填"},
            )

        return {
            "required": {
                "h3_plan": (
                    PLAN_TYPE,
                    {"tooltip": "Connect the preceding Plan v2 setup node."},
                ),
                "image_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": MAX_IMAGE_REFS,
                        "step": 1,
                        "tooltip": "实际使用的图片数量。0 表示不添加任何图片引用。",
                    },
                ),
            },
            "optional": optional,
        }

    RETURN_TYPES = (PLAN_TYPE, "STRING")
    RETURN_NAMES = ("h3_plan", "preview")
    FUNCTION = "build_chain"
    CATEGORY = "YingceAI/Dynamic"

    def check_lazy_status(self, h3_plan, image_count, **kwargs):
        """根据 image_count 只请求需要的图片输入"""
        needed = []
        effective_count = min(image_count, MAX_IMAGE_REFS)
        for i in range(1, effective_count + 1):
            key = f"input{i}"
            if key in kwargs and kwargs[key] is None:
                needed.append(key)
        return needed

    def build_chain(self, h3_plan, image_count, **kwargs):
        """构建图片引用链路"""
        image_cls = _get_planv2_image_class()
        image_node = image_cls()

        current_plan = h3_plan
        effective_count = min(image_count, MAX_IMAGE_REFS)
        previews = []

        for i in range(1, effective_count + 1):
            image = kwargs.get(f"input{i}")
            if image is None:
                logger.warning("image %d 为 None，跳过", i)
                continue

            image_use = kwargs.get(f"image_use{i}", "Storyboard / shot planning")
            reference_name = kwargs.get(f"reference_name{i}", f"image reference {i}")

            try:
                result = image_node.add_image(
                    h3_plan=current_plan,
                    image=image,
                    image_use=image_use,
                    reference_name=reference_name,
                    description=kwargs.get(f"description{i}", "") or "",
                    content_type=kwargs.get(f"content_type{i}", UNASSIGNED_CONTENT_TYPE)
                    or UNASSIGNED_CONTENT_TYPE,
                    subject_name=kwargs.get(f"subject_name{i}", "") or "",
                    retention=kwargs.get(f"retention{i}", "Auto for this relationship")
                    or "Auto for this relationship",
                    shot_scope=kwargs.get(f"shot_scope{i}", "") or "",
                    transfer_target_subject=kwargs.get(f"transfer_target_subject{i}", "") or "",
                )
                current_plan = result[0]
                preview = result[3] if len(result) > 3 else f"Image {i} added"
                previews.append(preview)
                logger.info("DynamicPlanV2ImageChain: 添加 image %d (%s)", i, image_use)
            except Exception as e:
                logger.error("添加 image %d 失败: %s", i, e)
                raise

        combined_preview = " | ".join(previews) if previews else "No image references added"
        return (current_plan, combined_preview)
