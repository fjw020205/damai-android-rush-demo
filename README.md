# 大麦 Android 抢票最小示例

这是我受朋友委托，对“大麦手机 App 专属购票”做的一个实操型探索项目。

公开项目里有些代码更像完整流程点击器，临近开售时还要搜索、识别和导航，速度和稳定性都不适合临界操作。本项目把流程收窄为：用户提前登录大麦并停在目标演出详情页，脚本只负责按设定时间进入购票流程。

仅支持 Windows + Android 真机 + 大麦 App，不支持网页端、模拟器或自动支付。验证码、短信验证、排队和支付必须由用户在手机上完成。

## 先选脚本类型

| 类型 | 适用情况 | 开售后动作 | 入口 |
| --- | --- | --- | --- |
| 连点型 | 预约阶段已经锁定场次和票档，开售后直接出现购买按钮 | 不识别场次和票价，直接快速连点 | `start-preselected.bat` |
| 额外选择型 | 预约没有包含场次、票档，开售后还要选择 | 按顺序点击 `session_index` 和 `price_index`，再进入确认页 | `start.bat` |

手机端页面会刻意减少可供代码读取的购票状态信息，脚本无法稳定、及时地捕捉“预约”变成“购票”的变化。因此连点型准备了 T0、T0+10ms、T0+20ms 三个时间方案：它们分别代表开售时立即点击、稍等 10 毫秒、稍等 20 毫秒。当前版本先提供这三档用于演练，后续版本会继续实验并确认更合适的间隔参数；你只需要按手机实际表现选择能稳定进入购票页的一档即可。

额外选择型不按金额或场次文字做识别，而是按页面上的卡片顺序点击。请从左到右横着数，第一张填 `1`，第二张填 `2`；如果页面换行，就先数上一行，再数下一行。这样少一次文字读取，速度更快，但每个演出都必须先演练确认顺序。

## 下载和安装

1. 在 GitHub 点 **Code → Download ZIP**，解压到一个固定目录。
2. 双击根目录 `setup.bat`，它会创建 `.venv` 并安装依赖。
3. 手机打开开发者选项和 USB 调试，用数据线连接电脑，在手机上允许 USB 调试授权。
4. 一台手机时配置里的 `serial` 保持 `null`；多台手机时先双击 `check-device.bat`，把状态为 `device` 的序列号填入配置。

## 配置

先复制对应模板，去掉 `.example` 后再编辑：

- 额外选择型：`config/rehearsal.jsonc.example` → `config/rehearsal.jsonc`；正式时再复制为 `config/formal.jsonc`。
- 连点型：`config/preselected-rehearsal.jsonc.example` → `config/preselected-rehearsal.jsonc`；正式时再复制为 `config/preselected-formal.jsonc`。

通常只改这些字段：

- `keyword`、`city`、`date`：填写目标演出页面上的信息。
- `users`：填写已在大麦 App 中保存的观演人；人数等于列表长度。
- `session_index`：额外选择型的场次顺序，从左到右横向数，第一项是 `1`；没有场次页填 `null`。
- `price_index`：额外选择型的票档顺序，从左到右横向数，第一项是 `1`；它不是票面金额。
- `sell_start_time`：定时开抢时间，使用 `2026-08-16T10:18:00+08:00` 这种格式；不定时可填 `null`。
- `skip_attendee_selection`：预约页已经预选观演人时设为 `true`。
- `skip_quantity_adjustment`：预约已经锁定数量时设为 `true`。
- `if_commit_order`：演练为 `false`，正式为 `true`。

连点型还要保持 `preselected_sku: true`。它会跳过场次和票档选择；`session_index`、`price_index` 仅为兼容配置保留，不参与开售后的点击。

## 演练和正式运行

每次新演出、新手机或大麦版本变化，都先演练：

- 额外选择型：双击 `start.bat`，脚本会选场次、票档和观演人，停在“立即提交”前。
- 连点型：分别双击 `start-preselected.bat`、`start-preselected-t10.bat`、`start-preselected-t20.bat`，比较哪一个能稳定进入确认页。

演练确认路径和顺序无误后：

- 额外选择型双击 `start-formal.bat`。
- 连点型把演练配置复制为 `config/preselected-formal.jsonc`，确认 `if_commit_order: true` 和 `cta_first_tap_delay_ms` 后双击 `start-preselected-formal.bat`。

正式入口只会提交订单，不会自动付款。启动前把大麦 App 停在目标演出详情页，手机保持解锁和前台，不要在开售临界时手动触碰屏幕。

## 文档

- [快速开始](docs/quick-start.md)
- [配置说明](docs/configuration.md)
- [正式开抢前准备](docs/pre-sale-checklist.md)
- [故障排查](docs/troubleshooting.md)

本项目基于 [currycan/HaTickets](https://github.com/currycan/HaTickets) 的 Android 移动端实现整理，原始许可见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
