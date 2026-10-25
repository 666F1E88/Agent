# models/ 目录说明

这里放**语音识别（ASR）模型**，`models/whisper-base/` 是 TaskMate 默认使用的
[faster-whisper base](https://huggingface.co/Systran/faster-whisper-base)（Whisper base 的 CTranslate2 版本）。

## 为什么不进 Git 仓库

| 文件 | 大小 | 说明 |
|---|---|---|
| `whisper-base/model.bin` | **138 MB** | 权重文件，超过 GitHub 单文件 100MB 上限，`git push` 会被直接拒绝 |
| `whisper-base/tokenizer.json` | 2.1 MB | 分词器 |
| `whisper-base/vocabulary.txt` | 0.4 MB | 词表 |
| `whisper-base/config.json` | 2.3 KB | 模型配置 |

因此 `.gitignore` 里已排除 `models/whisper-*/` 与 `*.bin`，**只保留本说明文件入库**。

## 换台机器怎么拿回来

```bash
python scripts/fetch_asr_model.py             # 默认 base（~145MB，推荐）
python scripts/fetch_asr_model.py --size tiny # ~75MB，更快但准确率略低
```

脚本默认走国内可用的 HF 镜像（hf-mirror），支持失败自动重试；
想换源：加 `--endpoint https://huggingface.co` 或设环境变量 `HF_ENDPOINT`。

## 不用语音功能可以完全跳过

`faster-whisper` 是可选依赖。不装、不下载模型，TaskMate 的聊天 + 任务管理主流程照常可用，
UI 会提示「语音识别组件未安装」并隐藏语音入口——语音只是加分项，不拖垮主流程。

## 许可

模型来自 Systran/faster-whisper-base，沿用 Whisper 系列的 MIT 许可；用于课程/学习用途无限制。
