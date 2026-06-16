# Dagens Ord — Obsidian 每日丹麦语插件

[English](README.md)

基于 Anki 丹麦语频率词库（DDO Danish Frequency Deck）的 Obsidian 插件，界面参考「每日一词」卡片风格，提供英文/中文释义、例句以及发音音频。

![Dagens Ord 插件截图](docs/screenshot.png)

> **翻译：** 全部 4442 个词均含英文和中文词义释义，且每个词的例句都配有英文和中文翻译。

## 功能

- 每日自动轮换单词（基于日期确定性选取）
- 词库导航（← →）、收藏、掌握标记
- 「今日」按钮跳回当天单词
- **单词发音**：来自 Anki 词库的丹麦语 MP3
- **例句发音**：通过本地 `edge-tts` 生成
- **按需下载音频**：发布包不再内置音频；首次使用时插件会自检本地音频，并提示从 GitHub 下载
- **CEFR 筛选**：在设置中单独开关 A1–C2 难度等级
- 深色主题，适配 Obsidian 默认暗色界面
- 学习进度本地保存

## 安装

1. 从最新 [release](https://github.com/kouge0510/obsidian-dagens-ord/releases) 下载 `main.js`、`manifest.json`、`styles.css`，放入 `.obsidian/plugins/dagens-ord/`
2. 在 Obsidian 设置 → 第三方插件 中启用 **Dagens Ord**
3. 首次打开视图时，插件会检查音频并提示你下载（见下方）

## 发音音频

为了让发布包保持精简，音频文件**不再内置**，而是托管在本仓库的 [`audio/` 目录](https://github.com/kouge0510/obsidian-dagens-ord/tree/main/audio)，按需下载。

- **打开时自检**：每次点击左侧功能区图标（或运行「打开每日丹麦语」）时，插件会把本地音频与远端文件清单比对。只要有缺失，就弹出英文下载提示；若文件齐全，则静默打开。
- **带进度条下载**：同意后会显示下载进度条，且只下载缺失的文件（已下载的会跳过，支持断点续传）。
- **手动下载**：也可在 设置 → **Pronunciation audio** → *Download / Re-download* 启动，或通过命令「下载发音音频 / Download pronunciation audio」。
- 下载需要联网。若无法访问 GitHub，插件会退回到「本地是否已有音频」的判断，离线时不会反复打扰。

## 使用

- 点击左侧功能区 ![languages](docs/ribbon-icon.png) 图标，或命令面板搜索「打开每日丹麦语」
- 单词播放按钮：播放丹麦语发音
- 例句播放按钮：播放本地生成的例句音频（通过上面的步骤下载得到）

## 开发者须知

### 批量生成例句语音（本地 edge-tts）

先确认本机已安装并可运行 `edge-tts`：

```bash
edge-tts --voice da-DK-ChristelNeural --text "Godmorgen, hvordan har du det?" --write-media "audio/test_da.mp3"
```

然后在插件目录运行：

```bash
python3 scripts/edge-tts-examples.py --jobs 4 --retries 3
```

脚本默认读取 `data/deck.json` 全量词库，给所有有例句的词生成 `audio/generated/ex-<word-id>.mp3`。已存在的音频会自动跳过，支持断点续传；如需重新生成，添加 `--overwrite`。默认并发数是 `--jobs 4`，如果网络稳定可以调到 `--jobs 8` 或更高。若遇到 `NoAudioReceived`，优先降低 `--jobs` 或提高 `--retries`。

### 导入中文词义

从中文 Anki `.apkg` 回填单词级中文释义到 `data/deck.json`：

```bash
npm run extract:zh
npm run build
```

脚本会写入 `translationZh` 和 `translationsZh`。插件会在单词下方显示英文和中文释义，例句区域会同时显示丹麦语原句及其英文、中文翻译。

### 开发

```bash
npm install
npm run extract   # 从 .apkg 重新导出词库
npm run build     # 构建 main.js（会把 data/deck.json 打包进去）
```

> 注意：`data/deck.json` 在构建时会被打包进 `main.js`。修改词库后必须重新构建（或推送 tag 让 CI 重新构建），插件中才会生效。

### 词库来源

`DDO_Danish_Frequency_Deck_English.apkg` — `data/deck.json` 当前包含 4442 个丹麦语高频词，全部带例句（共 13,097 条唯一丹麦语例句）。插件默认使用全量 4442 个词作为每日学习范围，也可在设置里调小或按 CEFR 等级筛选。

## 致谢

本插件的灵感来源于 [ankidkdeck v2.0](https://github.com/iskoldt-X/ankidkdeck/releases/tag/v2.0)（[iskoldt-X/ankidkdeck](https://github.com/iskoldt-X/ankidkdeck)）。

感谢 [Yifan Huang](https://github.com/Ploverrrr) 提供的帮助。
