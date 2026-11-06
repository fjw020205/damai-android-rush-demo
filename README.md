# 大麦 Android 抢票控制台

这是我受朋友所托，探索大麦手机 App 专属购票时整理的小工具。搜到的一些开源项目更像临场搜索、识别和导航的完整流程，操作复杂，也不适合开售临界时使用；这个项目把任务收窄为：用户提前登录大麦并停在目标演出详情页，控制台只负责在设定时间启动已经演练过的购票路径。

普通用户只需要使用本地控制台：查看手机状态、填写页面上的少量信息、先演练，再决定是否正式提交。

它不需要复制配置文件、不需要寻找变量名，也不需要打开终端。验证码、短信验证、排队和付款仍由用户在手机上完成；正式按钮只提交订单，不自动付款。

## 普通用户只走这条路

1. 在 GitHub 页面点击 **Code → Download ZIP**，解压到电脑上的固定文件夹。
2. 双击 `setup.bat`，第一次安装运行环境。
3. 连接 Android 手机，打开开发者选项和 USB 调试，并在手机授权弹窗中点“允许”。
4. 双击 `start-console.bat`，浏览器会打开控制台。
5. 在页面选择模式，填写开售时间和必要的顺序信息。
6. 点击“保存并启动演练”，确认手机上的场次、票档和观演人正确。
7. 提前启动正式任务，看到“正式任务状态：已准备就绪”后等待开售。

## 页面怎么选模式

| 大麦页面情况 | 控制台模式 |
| --- | --- |
| 预约时已经锁定场次和票档 | 预约连点型 |
| 开售后还要选择场次或票档 | 额外选择型 |

额外选择型需要填写场次和票档的页面顺序，按横向从左到右数，第一项是 `1`。预约连点型需要分别演练 T0、T0+10ms、T0+20ms，选出当前手机最稳定的一档。

## 先看状态，再点按钮

- **虚拟环境：已就绪**、**ADB：已连接**：电脑和手机准备好了。
- **演练是否就绪：可以开始**：现在可以点演练。
- **正式任务状态：程序未就绪**：已填正式时间，但正式任务还没有提前启动，继续等待会来不及。
- **正式任务状态：已准备就绪**：正式任务已经在等待开售，可以保持手机前台不动。

如果手机没有显示，先解锁手机、允许 USB 调试授权，再刷新页面。

## 重要边界

项目只支持 Windows、Android 真机和大麦 App，不支持网页端或模拟器。它不能保证库存、排队资格或最终购票结果，也不会自动处理验证码和支付。

## 本地启动与使用（不需要别人帮忙）

### 1. 准备

- Windows 电脑、Android 手机、USB 数据线
- 手机打开开发者选项和 **USB 调试**，插线后弹窗选“始终允许”
- 电脑上确认设备：

```powershell
adb devices
```

显示 `device` 才可用；`unauthorized` 说明手机上还没点允许。

### 2. 启动控制台

双击项目根目录的 **`start-console.bat`**，会：

1. 启动一个黑色服务窗口（运行期间不要关）
2. 自动打开浏览器 `http://127.0.0.1:8765/`

浏览器没自动打开就手动访问这个地址。

### 3. 页面操作

1. 选模式：开售后还要选场次/票档 → **额外选择型**；预约时已锁定 → **预约连点型**
2. 填开售时间（北京时间），留空表示立即演练
3. 填场次顺序、票档顺序（从 `1` 开始，按页面从左到右数）
4. 观演人：默认“已预选”；取消勾选后填写姓名，确认页会按姓名勾选
5. 点 **保存并启动演练**，确认手机上的场次、票档、观演人正确
6. 正式使用前勾选底部确认框，再点 **保存并正式提交**

### 4. 停止

- 关掉黑色服务窗口，控制台即停止
- 手机按返回退出确认页

### 5. 命令行方式（可选）

```powershell
cd C:\Users\vini vidi vici\Desktop\damai-android-rush-demo

# 演练（不提交）
.\.venv\Scripts\python.exe -m mobile.damai_app --config config\rehearsal.jsonc

# 正式（会提交订单，不付款）
.\.venv\Scripts\python.exe -m mobile.damai_app --config config\formal.jsonc
```

### 6. 候补监控

也可以直接在控制台底部 **「候补监控」** 填写目标日期、目标价、场次顺序、票档顺序，勾选是否自动导航/自动提交，点 **「保存候补设置」**，它会写入 `config/waitlist.jsonc`。

命令行方式：

```powershell
copy config\waitlist.jsonc.example config\waitlist.jsonc
notepad config\waitlist.jsonc
```

至少改这几项：

```jsonc
"target_date": "2026-11-21",
"target_price": 688,
"auto_navigate": true,
"auto_submit": false,
"session_index": 2,
"price_index": 6
```

运行：

```powershell
.\.venv\Scripts\python.exe -m mobile.waitlist_watch --config config\waitlist.jsonc
```

- 手机先停在票档页
- 每 3 秒“返回详情 → 重新进票档页”刷新（页面不支持下拉刷新）
- 命中目标日期/价格后自动走到确认页，弹 Windows 通知
- 默认 `auto_submit=false`：停在确认页，**不会提交订单**
- `Ctrl+C` 停止

#### 自动提交（可选，默认关闭）

默认不会提交。需要自动提交时，把配置改成：

```jsonc
"auto_submit": true
```

保存后重新运行：

```powershell
.\.venv\Scripts\python.exe -m mobile.waitlist_watch --config config\waitlist.jsonc
```

开启后的行为：

1. 命中可购买 → 自动进确认页
2. 点一次「立即提交」，生成待支付订单
3. 无论成功失败，**立即停止监控**，不会重试提交
4. 弹通知：已提交，请手动付款

风险：

- 会生成真实订单，锁库存，超时自动取消
- 不付款也会留下订单记录，频繁操作可能被风控/限购
- 提交前请确认日期、价格、场次、观演人
- 平台条款风险由使用者自行承担

详细说明见 [docs/waitlist.md](docs/waitlist.md)。

### 7. 常用检查

```powershell
check-locator.bat          # 定位自检
check-locator.bat scan     # 扫描当前页面控件
check-locator.bat learn    # 校准当前机型
```

## 文档

- [新手使用说明](docs/user-guide.md)：按控制台页面一步一步操作
- [USB 调试说明](docs/android-usb-debugging.md)：开发者选项、授权和连接排查
- [技术说明](docs/technical-notes.md)：两种模式、时间方案和实现边界
- [故障排查](docs/troubleshooting.md)：手机、页面和运行异常
- [多机型控件定位](docs/locator.md)：新增的语义定位层、设备校准和自检
- [候补监控](docs/waitlist.md)：只读轮询、重进刷新、本地通知和自动导航

## 多机型定位（新增）

项目原先依赖演练时缓存的坐标，换手机或改字体后容易失效。`mobile/locator.py` 补了一层语义定位：先用页面指纹确认页面，再按 `resource-id` → 文本 → 内容描述 → 校准比例的顺序找控件，找不到就报错而不是盲点。

开抢前可以先自检当前手机和页面：

```bat
check-locator.bat
```

需要校准时执行一次（比例文件保存在 `profiles/`，不会上传 GitHub）：

```bat
check-locator.bat learn
```

详细说明见 [docs/locator.md](docs/locator.md)。


熟悉脚本的用户仍可使用项目中的直接入口，但普通使用不需要接触它们。

本项目基于 [currycan/HaTickets](https://github.com/currycan/HaTickets) 的 Android 移动端实现整理，原始许可见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
