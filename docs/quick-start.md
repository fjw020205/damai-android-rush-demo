# 快速开始

这份示例假定你使用 Windows 和 Android 真机。请在开抢前先完成一次演练，不要第一次就运行正式入口。

## 1. 下载与安装

克隆仓库或下载 ZIP 并解压，然后双击根目录的 `setup.bat`。它会创建 `.venv` 并安装 Python 依赖。

如果 `setup.bat` 提示找不到 Python，请安装 Python 3.10-3.13，并在安装器中勾选“Add Python to PATH”。

## 2. 连接手机

1. 在手机设置中打开开发者选项和 USB 调试。
2. 用数据线连接电脑，在手机弹窗里允许该电脑的 USB 调试授权。
3. 只有一台已授权手机时，配置的 `serial` 保持 `null`，启动器会自动识别。
4. 连接多台手机时，双击 `check-device.bat`。输出中状态必须是 `device`，把对应序列号填到配置的 `serial` 字段。

## 3. 创建演练配置

在资源管理器中复制：

```text
config/rehearsal.jsonc.example
```

重命名为：

```text
config/rehearsal.jsonc
```

填写演出、场次和票档参数。先看 [配置说明](configuration.md)，尤其是 `session_index` 和 `price_index`。

## 4. 首次演练

在大麦 App 手动完成登录，打开目标演出详情页并保持前台。双击根目录的 `start.bat`。

成功演练的标准是：脚本按配置进入购票页，选择正确的场次、票档和前 N 位观演人，停在“立即提交”之前。结果写入 `logs/rehearsal-result.json`，该文件不会提交到 GitHub。

如果场次或票档不对，先退出订单页，改配置后再次演练。不要直接启动正式模式。

## 5. 正式模式

正式开抢前，将演练配置复制为 `config/formal.jsonc`，唯一必须不同的字段是：

```json
"if_commit_order": true
```

提前手动停在目标详情页。开抢时双击 `start-formal.bat`。它和演练共用同一极速路径，确认页会点击“立即提交”；支付、验证码和任何二次验证由你在手机上手动完成。

## VS Code

不需要使用终端。可直接双击三个批处理文件：

- `setup.bat`：仅首次安装或依赖损坏时使用。
- `check-device.bat`：可选，多台手机时查看设备序列号。
- `start.bat`：演练。
- `start-formal.bat`：正式提交。
