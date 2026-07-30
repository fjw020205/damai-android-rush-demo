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

1. 在 GitHub 点 **Code → Download ZIP**，解压到固定目录。
2. 双击 `setup.bat`，等待安装完成。
3. 打开手机的开发者选项和 USB 调试，再用数据线连接电脑。
4. 手机上出现授权弹窗时点允许；只有一台手机时 `serial` 保持 `null`。

开发者选项在不同品牌里藏得不一样，没搜到不代表手机不支持。先看[安卓开发者选项和 USB 调试说明](docs/android-usb-debugging.md)。

## 配置

先复制对应模板，再把副本另存为不带 `.example` 的文件名：

- 额外选择型：`config/rehearsal.jsonc.example` → `config/rehearsal.jsonc`；正式时再复制为 `config/formal.jsonc`。
- 连点型：`config/preselected-rehearsal.jsonc.example` → `config/preselected-rehearsal.jsonc`；正式时再复制为 `config/preselected-formal.jsonc`。

`.example` 只是模板标记，不是特殊语法。模板会上传到 GitHub，真实配置会被 `.gitignore` 排除，避免设备号和个人信息被提交；启动脚本也只读取不带 `.example` 的真实配置。

配置只记三件事：

- 两种模式都只需要改 `sell_start_time`。
- 额外选择型再改 `session_index`、`price_index`，按页面横向从左到右数，第一项是 `1`。
- 多台手机才改 `serial`；如果 App 没有预选观演人，才把 `skip_attendee_selection` 改为 `false` 并填写 `users`。

其他字段保持模板原样。连点型保持 `preselected_sku: true`；正式模板已经把 `if_commit_order` 设为 `true`，不要在演练模板里改它。

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
