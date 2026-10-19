# 通用时间窗与覆盖核对（v1.1 / capture 0.7.0）

先按教程填写 settings.json 并运行 scripts/configure.py。所有示例从工具包目录运行；不包含固定用户、邮箱、项目白名单或本机路径。

## 显式窗口：起点包含、终点排除

```sh
python3 capture/bin/chatgpt-sync window \
  --start 2026-10-18T06:00:00-07:00 \
  --end 2026-10-19T06:00:00-07:00 \
  --timezone America/Vancouver \
  --output runtime/daily/example-unique-run
```

等价入口为 `python3 capture/bin/chatgpt-window prepare` 加相同参数。任意分钟、同日、跨午夜、跨多日均可；不需要手工导出两天并拼接。两端必须带UTC偏移或Z，不接受无时区时间；可用不同偏移表示同一时区在夏令时前后的时间。

`--timezone` 指定 IANA 时区，用于显示时间和核对所涉自然日；缺省使用采集配置时区。输入偏移表示实际瞬间，将先转换到选定时区，不直接按输入日期字符串拼接。

## 每日边界

在 settings.json 设置 `"diary_boundary": "06:00"`，重新运行 configure.py，并将新生成的 runtime/instructions/daily-task.md 更新到实际定时任务。默认00:00保持旧版行为。只改任务里描述的时间、不换导出命令，会重新引入风险。

```sh
python3 capture/bin/chatgpt-window prepare \
  --date 2026-10-18 --boundary 06:00 --timezone America/Vancouver \
  --output runtime/daily/daily-example-unique-run
```

该命令从当地该日06:00到下一日06:00，不固定为24小时。若选择的边界在夏令时切换时重复或不存在，命令退出2，改用带明确偏移的 --start/--end。不能同时指定 --date 和 --start/--end。旧本地任务可用 aster-diary 兼容入口：只有该入口的 --date 默认06:00，仍可显式指定其他分界。

## 三层状态与投递检查

prepare 输出 messages.jsonl、messages.md、manifest.json、coverage.json。目录必须全新，避免覆盖历史来源。

1. **采集状态**：最近一次同步是否成功且白名单一致，仅表示已观察库存的采集结果。
2. **导出覆盖**：实际窗口结束前的快照、有效消息时间、源文件哈希、原始消息ID集合与按所有所涉自然日合并的ID集合一致。不是用总数相同代替集合核对。
3. **叙事去向**：逐消息读完后，在 coverage.json 中只填写 status、section、note。状态可用 summarized / quoted / alternative_recorded；section 是正文中的完整Markdown标题行；note 是该条消息的具体处理说明。其余身份字段，包括 occurrences，必须保留。不能只添加对话标题或虚报已读。

```sh
python3 capture/bin/chatgpt-window verify \
  --bundle runtime/daily/example-unique-run \
  --diary /absolute/path/to/diary.md
```

发送或发布前须检查退出0且本次 verification.json 的 publication_ready=true，再完成实际语义审阅和授权核验。机器不会发送邮件，也不能自动证明正文准确。所有错误返回2，旧verification成功会先失效；来源更新后新建bundle重跑。空窗口可以是合法结果，但缺失文件、错误或partial绝不能被当作合法空集。

## 重复、分支与局限

按对话ID/原始消息ID建立集合。同ID同内容去重，occurrences保留全部原节点、父节点、分支、树顺序；内容冲突中止，不静默采用其中一个版本。替代分支保留，不作为最终成功结果冒充主线。源数据始终只读。

`day` 仍是自然日接口，次日自然日未结束可合法返回partial；不能因此判断已经结束的跨日窗口缺数据。本通用入口只判断实际请求窗口，不依赖某个自然日导出命令的退出状态，也不会在失败后继续宣称完整。

已删除、无法访问或从未列入观测目录的聊天及附件二进制仍不保证覆盖。消息映射和标题检查不能代替阅读用户纠正、双方回应及未决事项。公开仓库与下载包不得包含使用后产生的settings.json、runtime/、capture/data/或capture/state/。

## 升级现有安装

备份现有程序和任务文本，保留自己的配置、原始data/、state/与旧日记。替换 capture/bin 下 chatgpt-sync、chatgpt-window、aster-diary 及新版测试；不要用示例config.json覆盖真实白名单。更新settings中的分界并重新生成指令，再更新实际执行的任务。旧bundle保留为历史来源，新入口对旧格式不会冒充已验证，重新建立新目录即可。
