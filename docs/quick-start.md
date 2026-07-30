# 快速开始

这份流程面向 Windows 和 Android 真机。第一次使用、换演出或更新大麦 App 后，都先做演练。

## 1. 安装

下载 ZIP 并解压，双击根目录 `setup.bat`。如果提示找不到 Python，安装 Python 3.10-3.13，并勾选“Add Python to PATH”。

## 2. 连接手机

1. 打开手机开发者选项和 USB 调试。
2. 数据线连接电脑，在手机弹窗中允许 USB 调试。
3. 只有一台手机时，配置 `serial` 保持 `null`。
4. 多台手机时双击 `check-device.bat`，把状态为 `device` 的序列号填入配置。

## 3. 复制配置

根据页面类型二选一：

- 页面开售后还要选场次/票档：复制 `config/rehearsal.jsonc.example` 为 `config/rehearsal.jsonc`。
- 预约已经锁定场次/票档：复制 `config/preselected-rehearsal.jsonc.example` 为 `config/preselected-rehearsal.jsonc`。

打开配置，至少填写 `keyword`、`city`、`date`、`users` 和 `sell_start_time`。额外选择型还要填写 `session_index`、`price_index`。

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
