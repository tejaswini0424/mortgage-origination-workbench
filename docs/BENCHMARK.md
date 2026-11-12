# Reproducing the generative benchmark

The five-pipeline experiment uses a local vision-language model so fictional mortgage documents stay on the workstation. The rules, layout, and layout-verified methods require English Tesseract for the scanned conditions. The generative methods send the same page images and available OCR to the configured chat-completions endpoint.

The tested model is SmolVLM-256M-Instruct Q8_0 with its Q8_0 image projector, served by the llama.cpp b12318 Windows CPU build. [Model files](https://huggingface.co/ggml-org/SmolVLM-256M-Instruct-GGUF/tree/main) [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

Place the CPU executable and model files in a directory outside source control. From that directory, start the server using the local filenames for the model and projector.

```powershell
.\llama-server.exe -m model.gguf --mmproj mmproj.gguf --alias SmolVLM-256M-Instruct-Q8_0 --host 127.0.0.1 --port 18937 -c 4096 -t 4 -ngl 0
```

From the repository root, run the experiment in a separate terminal.

```powershell
$env:VISION_ENDPOINT = "http://127.0.0.1:18937/v1/chat/completions"
$env:VISION_MODEL = "SmolVLM-256M-Instruct-Q8_0"
$env:VISION_IMAGE_EDGE = "512"
$env:VISION_JSON_SCHEMA = "1"
python -m benchmarks.suite --seed 81 --vision
```

| File | SHA-256 |
| --- | --- |
| Model | `2A31195D3769C0B0FD0A4906201666108834848DB768AF11DE1D2CEF7CD35E65` |
| Projector | `7E943F7C53F0382A6FC41B6EE0C2DEF63BA4FDED9AB8ED039CC9E2AB905E0EDD` |

Vision and vision-plus-verification share the same model response for each fixture. The verified pipeline latency includes the measured model request and its own verification work. The report tracks provider failures separately from pipeline failures. Field accuracy counts exact normalized matches against evaluable ground truth. Unsupported emissions count predictions for fields marked absent or ambiguous. A reported page-evidence match requires a normalized correct value and source text on the expected page.

The benchmark includes four synthetic document types across seven conditions. Results are evidence about these fixtures and this model configuration.

## Measured results for seed 81

The run evaluated five pipelines on the same 28 fixtures. Each pipeline had 69 evaluable fields.

| Pipeline | Correct fields | Unsupported emissions | Processing errors | Provider errors |
| --- | ---: | ---: | ---: | ---: |
| rules | 53/69 | 4 | 0 | 0 |
| layout | 59/69 | 4 | 0 | 0 |
| layout_verified | 59/69 | 0 | 0 | 0 |
| vision | 39/69 | 2 | 0 | 0 |
| verified | 58/69 | 0 | 0 | 0 |

The layout pipelines recovered all 11 split-column fields. The rules pipeline recovered none. On rotated scans the rules pipeline recovered six fields and the layout-verified pipeline recovered one. The generative model by itself recovered 39 fields. Verification increased that to 58 by grounding output in the document layout and abstaining on disagreement.

[Download the full per-condition report](benchmark-seed-81.json).
