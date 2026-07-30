# 故障排查

## 手机没有显示

换数据线或 USB 口；重新插拔并在手机上允许 USB 调试。如果状态是 `unauthorized`，撤销 USB 调试授权后重新连接。如果状态是 `offline`，先重启手机上的 USB 调试，再运行 `check-device.bat`。

## 启动后提示配置不存在

`.example` 只是模板，不会被入口直接读取。先复制为实际文件：

- `rehearsal.jsonc.example` → `rehearsal.jsonc`
- `formal.jsonc.example` → `formal.jsonc`
- `preselected-rehearsal.jsonc.example` → `preselected-rehearsal.jsonc`
- `preselected-formal.jsonc.example` → `preselected-formal.jsonc`

## 提示配置文件格式错误

JSONC 允许注释，但仍然必须使用双引号和正确逗号。重点检查刚修改的 `sell_start_time`、`session_index`、`price_index` 是否写在正确的行，时间是否类似 `2026-08-16T10:18:00+08:00`。

## 场次或票档选错

这是额外选择型的顺序参数问题。重新进入同一场次，按页面横向从左到右数卡片，第一项是 `1`，换行时再从上一行数到下一行，然后修改 `session_index` 或 `price_index` 并重新演练。不要把 `680`、`980`、`1280` 直接填进 `price_index`。

如果预约已经锁定场次和票档，应改用连点型模板并设置 `preselected_sku: true`，不要让额外选择型在开售后重复找票档。

## 连点型误入预约按钮

先确认 `sell_start_time` 与手机时间一致，且页面确实是预约后详情页。分别演练 T0、T0+10ms、T0+20ms；若页面切换较慢，使用较晚的版本。连点型是按时间信号直接点击，不能保证服务端已经开放库存。

## 提交后没有支付页

提交订单不等于支付成功，可能进入排队、验证码、库存不足或订单待确认状态。先查看手机订单状态，不要重复启动正式入口。

## 小米/HyperOS 点击无效

确认 USB 调试授权没有失效，并用演练验证当前大麦版本。不要在正式开抢前第一次升级大麦、系统或 Python 依赖；升级后先重新演练。
