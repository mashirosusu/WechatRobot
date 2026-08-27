# WechatRobot

将白名单用户在白名单微信群中发送的 `@机器人 话术` 转发为原生 `@所有人` 消息。

## 风险警告

本项目依赖非官方 PC 微信 Hook 工具 WeChatFerry，仅用于学习和自有测试环境。它可能因微信升级失效，也存在账号限制或封禁风险。请使用专用测试账号；本项目不能绕过微信原生群权限。

## 环境

- Windows 10/11
- Python 3.10
- PC 微信 3.9.12.51
- WeChatFerry 39.5.2.0

版本需要严格匹配。建议关闭 PC 微信自动升级，并先在非重要账号和测试群中验收。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[runtime]"
Copy-Item config.example.json config.json
```

编辑 `config.json`，填入允许使用的群 `roomid` 和触发人的 `wxid`。不要提交真实配置；`config.json` 已加入 `.gitignore`。

配置项：

- `allowed_rooms`：允许触发机器人的群 `roomid` 列表，值必须以 `@chatroom` 结尾。
- `allowed_senders`：允许触发的微信用户 `wxid` 列表。
- `cooldown_seconds`：同一用户在同一群再次触发前的冷却秒数，范围为 0–3600。
- `log_level`：`DEBUG`、`INFO`、`WARNING`、`ERROR` 或 `CRITICAL`。

## 启动

先登录指定版本的 PC 微信，再运行：

```powershell
wechat-robot --config config.json
```

按 `Ctrl+C` 停止机器人并清理 WeChatFerry 连接。

## 行为

只有同时满足群白名单、发送者白名单、真实 @ 机器人、文本消息和冷却限制的消息才会发送。机器人必须位于消息开头；成功消息格式为：

```text
@所有人
原话术
```

发送失败不会进入冷却期。机器人自己发送的消息会被忽略，避免循环触发。

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 人工验收

在测试群给机器人账号群管理员权限并确认客户端原生允许该账号选择 `@所有人`。使用白名单账号发送 `@机器人 测试通知`，确认群里只出现一条原生全员提醒；再验证非白名单账号、非白名单群和冷却期重复请求均不会发送。

## 开源调研结论

本项目采用 [WeChatFerry](https://github.com/lich0821/WeChatFerry) 的 Python API。其消息接收、群内昵称查询和 `send_text(..., aters="notify@all")` 能覆盖本项目核心流程。WeChatFerry 属于非官方方案，稳定性、兼容性和账号风险均由使用者自行评估。

## License

[MIT](LICENSE)
