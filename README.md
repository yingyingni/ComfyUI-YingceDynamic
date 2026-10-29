# ComfyUI-YingceDynamic

ComfyUI custom node pack by [Yingce](https://github.com/yingyingni) — dynamic PlanV2 chain loaders, batch media loaders, audio sanitize, subject-aware prompt, and 3D file/mesh output registration.

## Nodes

| Node | Display Name | Purpose |
|---|---|---|
| `DynamicPlanV2AudioChain` | Dynamic PlanV2 Audio Chain | Lazily-assembled audio chain for PlanV2 pipelines |
| `DynamicPlanV2ImageChain` | Dynamic PlanV2 Image Chain | Lazily-assembled image chain for PlanV2 pipelines |
| `DynamicLoadImageBatch` | Dynamic Load Image Batch | Batch image loading with lazy evaluation |
| `DynamicLoadAudioBatch` | Dynamic Load Audio Batch | Batch audio loading with lazy evaluation |
| `SanitizeAudio` | Sanitize Audio | Audio preprocessing/sanitization |
| `YingceSubjectPrompt` | Subject-aware Prompt | Prompt helper that injects subject context |
| `YingceExportMesh` | Export 3D Mesh to output | Writes TRIMESH objects to the output dir and registers them so platforms can collect the file |
| `YingceRegisterFile3D` | Register 3D File to output | Writes FILE_3D* objects (e.g. from `MeshToFile3D` in TRELLIS.2 pipelines) to the output dir and registers under `ui.images` |

## Why `YingceRegisterFile3D`?

Core `Save3DAdvanced`/`MeshToFile3D` writes the `.glb` into the output folder but only registers it under the `ui["3d"]` key in history. Daemons/collectors that only scan `images/videos/gifs/audio` never see the file — the "ghost file" problem. This node writes the file **and** registers `{filename, subfolder, type=output}` under `ui.images`, so any standard output collector picks up the `.glb` as a normal artifact.

## Install

```
cd ComfyUI/custom_nodes
git clone https://github.com/yingyingni/ComfyUI-YingceDynamic.git
pip install -r ComfyUI-YingceDynamic/requirements.txt
```

Restart ComfyUI.

## License

Apache-2.0
