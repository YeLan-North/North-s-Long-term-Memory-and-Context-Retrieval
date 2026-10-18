# 来源、许可与去个人化范围

- `capture/bin`、`capture/extension`和`capture/tests`为基于 benthamite/chatgpt-sync 的修改版，原 MIT 许可证见 `capture/LICENSE`。其中包含原作与本项目改动，不能整体标作从零原创。
- `scripts/`、`templates/`、`tests/test_toolkit.py`与教程为本次整理编写的通用复现材料，按 MIT 许可提供，见 `LICENSE`。
- OpenViking、官方插件、Python依赖、模型和编译源码均不随本包分发。下载地址、版本和参考校验值见 `dependency-sources.json`；下载后保留各自许可证。
- Chrome扩展manifest中的`key`是上游公开公钥，用于稳定扩展ID，不是账号私钥或登录令牌。
- 此包采用明确允许列表构建，不包含真实对话、日记、角色关系档案、邮箱地址、项目ID、Library文件ID、个人目录、浏览器状态、令牌、向量库或运行日志。示例资料全部是合成资料。
- 安装后填写的 `settings.json`、`runtime/`、`capture/config.json`、`capture/data/`、`capture/state/` 是用户自己的私有内容。不要把使用后的整个安装目录直接当公开模板重新打包。
- 去个人化以本次材料为范围，不保证用户日后放入的文字已匿名；分享前应重新审查。
