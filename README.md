# 原神副本扫描器 · GenshinRewardScanner

面向原神副本奖励横排与圣遗物详情的 Windows 本地识别工具。支持整趟扫描、单卡识别和横排拼图，将识别结果及图片整理到 Excel，并提供任务记录与产出空间管理。

## AI 制作说明

本项目原创程序代码由 AI 编写、修改和调试，主要使用 OpenAI Codex；界面布局曾使用 DeepSeek Harness 辅助。DrMoMing 负责提出需求、实际测试和项目决策，未参与程序代码编写。第三方代码、模型和素材仍归其各自作者，不属于本项目 AI 制作声明的范围。

##功能界面展示

<img width="1375" height="1000" alt="image" src="https://github.com/user-attachments/assets/008ff304-4573-4235-8b92-348443b9ec81" />

<img width="1375" height="1000" alt="image" src="https://github.com/user-attachments/assets/0ee74848-bc54-4f55-920d-325320981c82" />

<img width="1375" height="1000" alt="image" src="https://github.com/user-attachments/assets/90d77cc6-6c46-49cd-a9ea-189ccdef8c91" />

悬浮窗展示：

<img width="1375" height="1000" alt="image" src="https://github.com/user-attachments/assets/e588ca40-887a-4b07-a448-cecf1cf9ab9b" />


## 项目与许可

本项目为 **源码可见 / source-available、非商业许可软件**，不以“开源软件”自称。

本项目有权授权的原创部分采用未经修改的 **PolyForm Noncommercial License 1.0.0**，见 [LICENSE](LICENSE)；适用边界见 [许可适用范围](docs/licensing/许可适用范围.md)。未经另行授权，不得倒卖本项目原创软件，或用于协议未许可的商业用途、付费代处理及商业服务。本说明是许可摘要，以协议原文为准。目前不提供商业授权。

第三方组件、模型及游戏素材不因此改用非商业许可；各自原许可和版权声明独立适用，详见 [第三方许可与来源](docs/licensing/第三方许可与来源.md)。

项目主页与发布来源：https://github.com/DrMoMing/GenshinRewardScanner

目前暂不接受外部代码贡献或 Pull Request，可通过 Issues 反馈问题。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)

本项目为非官方工具，与原神及其权利人无隶属或背书关系。相关游戏名称、画面、字体和素材的权利归各自权利人所有。

## 使用与构建

Windows x64。日常使用请下载GitHub Releases中的安装包，识别和写表均在本机进行。整趟扫描、单卡识别、横排拼图及快捷键说明见[使用说明](使用说明.txt)。

源码结构：`src/`为生产Python模块，`native/`为桌面与浮窗源码，`Assets/`为识别所需资源，`third_party/`为第三方原始许可和对应源码，`packaging/`与`tools/`为构建入口。

[独立构建说明](docs/构建说明.md) · [详情布局与识别资源](docs/资源与识别规则.md)

配套构建支持包随Release提供，包含可替换的原生依赖；个人工作簿、日志、完整截图与个人运行缓存不随源码发布。
