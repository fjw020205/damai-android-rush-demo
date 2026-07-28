# Damai Android Rush Demo

一个面向 Android 真机的最小大麦 App 自动化示例。它只保留一条已验证的路径：从演出详情页进入购票面板，按配置选择场次和票档，选择前 N 位观演人，并在确认页停止或提交订单。

不支持网页端、桌面端或模拟器。支付始终由用户在手机上手动完成。

## 使用前

- Windows 10/11、Python 3.10-3.13、Android 手机和 USB 数据线。
- 手机已登录大麦，开发者选项和 USB 调试已打开。
- 已在 App 中添加好要使用的观演人。
- 使用者应自行遵守平台规则、服务条款和适用法律；不要用于倒票或规避平台限制。

## 最短路径

1. 在 GitHub 下载或克隆仓库后，双击 `setup.bat` 创建环境。
2. 用数据线连接手机，在手机弹窗中允许 USB 调试；若只连接一台手机，模板中的 `serial: null` 无需修改。
3. 复制 `config/rehearsal.jsonc.example` 为 `config/rehearsal.jsonc`，填写真实参数。
4. 先双击 `start.bat` 做演练。它会走到确认页，但不会点击“立即提交”。
5. 确认场次、票档和观演人顺序正确后，复制并填写 `config/formal.jsonc`，再双击 `start-formal.bat`。它会提交订单，但不会支付。

VS Code 中按 `Ctrl+Shift+B` 运行演练；正式模式通过“Tasks: Run Task”选择“正式手机购票”。

详细步骤见 [快速开始](docs/quick-start.md)。

## 两种入口

| 文件 | 行为 |
| --- | --- |
| `start.bat` | 演练模式：进入确认页、选择观演人、停在“立即提交”前。 |
| `start-formal.bat` | 正式模式：与演练走同一极速路径，确认页点击“立即提交”，随后验证订单结果。 |
| `check-device.bat` | 可选：显示已连接手机；仅多设备时需要把序列号填入配置。 |

两者共用 `rush_mode=true` 的快速路径。不要把正式模式当作付款自动化，它只提交订单。

## 配置重点

- `session_index`：场次卡片从上到下、从 `0` 开始编号。没有场次选择页时填 `null`。
- `price_index`：票档卡片从上到下、从 `0` 开始编号。新版页面的价格文字可能不可读取，因此必须先用演练确认序号。
- `users`：需要选择的观演人数。当前最小示例按确认页复选框顺序选择前 N 位，不按姓名搜索。
- `skip_quantity_adjustment`：预约已经锁定数量时设为 `true`，脚本不再点数量加号。
- `skip_attendee_selection`：App 已经完成观演人预选时设为 `true`；默认 `false`，按顺序选择前 N 位。
- `auto_navigate`：建议保持 `false`，开抢前由你手动停在正确的演出详情页，减少不确定步骤。

完整字段说明见 [配置说明](docs/configuration.md)。

## 文档

- [快速开始](docs/quick-start.md)
- [配置说明](docs/configuration.md)
- [正式抢票前准备](docs/pre-sale-checklist.md)
- [故障排查](docs/troubleshooting.md)

## 来源与许可

此项目基于 [currycan/HaTickets](https://github.com/currycan/HaTickets) 的 Android 移动端实现整理，只保留 UIAutomator2 的最小路径。保留的原始代码遵循 Apache License 2.0，详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
