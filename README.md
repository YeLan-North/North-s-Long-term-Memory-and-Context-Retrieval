# North's Long-term Memory and Context Retrieval

一套可复现的聊天历史保存、细节日记、分层档案与本地语义检索方案。公开材料已去个人化，不包含原用户的真实对话、邮箱、项目 ID、角色档案、凭据或数据库。

## 开始使用

- [完整中文教程](memory-reproduction-kit-v1.0/长期记忆与历史保存复现教程.md)
- [离线复现文件包 ZIP](dist/memory-reproduction-kit-v1.0.zip)（打开后选择 Download raw file）
- [源文件与配置模板](memory-reproduction-kit-v1.0/)
- [验证记录与限制](memory-reproduction-kit-v1.0/VALIDATION.md)
- [外部依赖来源与固定版本](memory-reproduction-kit-v1.0/dependency-sources.json)

文件包内也有可离线打开的 `memory-guide.html` 网页版教程。

## 流程

指定项目的对话采集 → 原始 JSON 与阅读副本 → 每日细节日记 → 每周手动分层归档 → OpenViking 本地索引 → 聊天时检索原文与上下文。

本地采集与嵌入不要求购买模型 API；日记生成使用自己的助手宿主能力。每日任务需有本机文件访问与工具执行能力，普通云端提醒无法读取 Mac 上的目录。自动钩子与定时触发需要分别验收，不能以安装成功推断全部自动化已生效。

## 复现包 v1.0

包含修改后的项目采集源码、配置生成脚本、官方导出转换工具、CPU 嵌入构建脚本、插件准备工具、原文分片与索引工具、日记/邮件/周归档/记忆读取模板，以及测试和来源说明。

请从干净包开始，填写自己的 `settings.json`。使用后产生的 `runtime/`、`settings.json`、`capture/data/`、`capture/state/` 属于私有数据，不要重新公开上传。

## 来源与许可

采集组件基于 [benthamite/chatgpt-sync](https://github.com/benthamite/chatgpt-sync)，保留原 MIT 许可证；新增通用材料采用 MIT。OpenViking、官方插件、模型及第三方依赖通过教程中的原始链接另行下载。

详见 [NOTICE](memory-reproduction-kit-v1.0/NOTICE.md) 和 [LICENSE](memory-reproduction-kit-v1.0/LICENSE)。
