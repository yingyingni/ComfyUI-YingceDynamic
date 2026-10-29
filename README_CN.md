# ComfyUI-YingceDynamic

影策 ComfyUI 自定义节点包——PlanV2 动态链路加载、批量媒体加载、音频净化、主体提示词、3D 文件/网格产物登记输出。

## 节点

| 节点 | 显示名 | 用途 |
|---|---|---|
| `DynamicPlanV2AudioChain` | Dynamic PlanV2 Audio Chain | PlanV2 音频链路懒加载封装 |
| `DynamicPlanV2ImageChain` | Dynamic PlanV2 Image Chain | PlanV2 图像链路懒加载封装 |
| `DynamicLoadImageBatch` | Dynamic Load Image Batch | 批量图像加载（按需执行） |
| `DynamicLoadAudioBatch` | Dynamic Load Audio Batch | 批量音频加载（按需执行） |
| `SanitizeAudio` | Sanitize Audio | 音频预处理/净化 |
| `YingceSubjectPrompt` | Subject-aware Prompt | 主体感知提示词注入 |
| `YingceExportMesh` | Export 3D Mesh to output | 把 TRIMESH 对象写出到 output 并登记，平台可收集 |
| `YingceRegisterFile3D` | Register 3D File to output | 把 FILE_3D*（如 TRELLIS.2 的 MeshToFile3D 产出）写出到 output 并登记到 `ui.images` |

## 为什么需要 `YingceRegisterFile3D`？

核心 `Save3DAdvanced`/`MeshToFile3D` 把 `.glb` 写进 output 后只在 history 的 `ui["3d"]` 键下登记；只收 `images/videos/gifs/audio` 的采集器拿不到——"幽灵文件"问题。本节点额外按 `ui.images` 登记 `{filename, subfolder, type=output}`，任何标准产物收集器都能收到 `.glb`。

## 安装

```
cd ComfyUI/custom_nodes
git clone https://github.com/yingyingni/ComfyUI-YingceDynamic.git
pip install -r ComfyUI-YingceDynamic/requirements.txt
```

重启 ComfyUI。

## License

Apache-2.0
