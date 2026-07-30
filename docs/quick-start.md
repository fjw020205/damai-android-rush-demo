# 快速开始

这份流程面向 Windows 和 Android 真机。第一次使用、换演出或更新大麦 App 后，都先做演练。

## 1. 安装

下载 ZIP 并解压，双击根目录 `setup.bat`。如果提示找不到 Python，安装 Python 3.10-3.13，并勾选“Add Python to PATH”。

## 2. 连接手机

先看[安卓开发者选项和 USB 调试说明](android-usb-debugging.md)，再打开 USB 调试并连接数据线。手机弹出授权时点允许；只有一台手机时 `serial` 保持 `null`，多台手机才需要用 `check-device.bat` 选择序列号。

## 3. 复制配置

根据页面类型二选一，把模板复制成启动脚本要求的文件名：

- 页面开售后还要选场次/票档：复制 `config/rehearsal.jsonc.example` 为 `config/rehearsal.jsonc`。
- 预约已经锁定场次/票档：复制 `config/preselected-rehearsal.jsonc.example` 为 `config/preselected-rehearsal.jsonc`。

`.example` 只是公开模板的后缀。真实配置不提交 GitHub，启动脚本也不会直接读取模板，避免把占位内容当成真实配置运行。

打开配置。两种模式只改 `sell_start_time`；额外选择型再改 `session_index`、`price_index`。默认已按预约场景跳过观演人操作，只有 App 没有预选观演人时才填写 `users`。

## 4. 做演练

先登录大麦 App，手动打开目标演出详情页并保持前台。

- 额外选择型双击 `start.bat`。它会选择配置的场次、票档和观演人，停在“立即提交”前。
- 连点型依次试 `start-preselected.bat`、`start-preselected-t10.bat`、`start-preselected-t20.bat`。它们分别在 T0、T0+10ms、T0+20ms 发送第一击，均不提交订单。

结果会写入 `logs/`，该目录不会上传 GitHub。演练必须确认最终场次、票档和观演人正确。

## 5. 正式运行

先复制正式模板：

- 额外选择型：`config/rehearsal.jsonc` → `config/formal.jsonc`，将 `if_commit_order` 改为 `true`。
- 连点型：`config/preselected-rehearsal.jsonc` → `config/preselected-formal.jsonc`，将 `if_commit_order` 改为 `true`。

开售前把 App 停在详情页：

- 额外选择型双击 `start-formal.bat`。
- 连点型双击 `start-preselected-formal.bat`。

正式入口会点击“立即提交”，不会支付。支付、验证码、短信和排队提示由用户手动处理。

## VS Code

不需要终端。资源管理器中双击 `.bat` 即可；也可以在 VS Code 里打开项目后，用“Tasks: Run Task”启动已有入口。
