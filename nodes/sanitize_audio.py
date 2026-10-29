"""
音频清洗节点

背景：H3 工作流（尤其无音频参考条件时）采样出的 audio latent 经
VAEDecodeAudio 解码后可能含 NaN/Inf，CreateVideo 将坏波形 mux 进
AAC 音轨时 avcodec_send_frame() 直接抛错，导致整个 prompt 在
最后一步保存阶段失败（8 分钟采样白费）。

本节点插在 VAEDecodeAudio 与 CreateVideo 之间：
- 波形含 NaN/Inf → torch.nan_to_num 清洗为 0（静音片段）
- 整段全坏 → 输出静音轨，保证视频正常产出
- 正常音频 → 原样透传，零开销
"""

import logging

import torch

logger = logging.getLogger("ComfyUI-YingceDynamic")


class SanitizeAudio:
    """清洗 AUDIO 波形中的 NaN/Inf，防止下游 AAC 编码崩溃"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "sanitize"
    CATEGORY = "YingceAI/Dynamic"

    def sanitize(self, audio):
        waveform = None
        if isinstance(audio, dict):
            waveform = audio.get("waveform")
        elif hasattr(audio, "waveform"):
            waveform = audio.waveform

        if waveform is None or not torch.is_tensor(waveform):
            logger.warning("SanitizeAudio: 未找到 waveform，原样透传")
            return (audio,)

        bad_mask = ~torch.isfinite(waveform)
        bad_count = int(bad_mask.sum().item())
        if bad_count == 0:
            return (audio,)

        total = waveform.numel()
        ratio = bad_count / total if total else 0
        logger.warning(
            "SanitizeAudio: 检测到 %d/%d (%.2f%%) NaN/Inf 采样，清洗为静音",
            bad_count, total, ratio * 100,
        )

        clean = torch.nan_to_num(waveform, nan=0.0, posinf=0.0, neginf=0.0)

        if isinstance(audio, dict):
            audio = {**audio, "waveform": clean}
        else:
            try:
                audio.waveform = clean
            except Exception:
                audio = {"waveform": clean,
                         "sample_rate": getattr(audio, "sample_rate", 44100)}

        if ratio > 0.5:
            logger.error(
                "SanitizeAudio: 超过半数采样损坏(%.2f%%)，输出近似静音轨",
                ratio * 100,
            )
        return (audio,)
