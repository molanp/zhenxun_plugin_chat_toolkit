# zhenxun_plugin_chat_toolkit

由于 [AI全家桶](https://github.com/molanp/zhenxun_plugin_zhipu_toolkit) 插件不能自定义路由使用中转站模型，遂拆分出此插件。

本插件仅支持被动聊天。无生图，伪人等功能。

## 🕹️ 关于模型选择

本插件默认您选择的模型为多模态模型，且支持 `openai` 调用格式

本插件默认使用开发群内群友的中转站(`https://api.mengluo.work`)，如需自定义，你可以在配置中更改

## ⚠️ 注意事项

请确保您已正确配置真寻的ai模块

下面是正确配置的一部分

```yaml
PROVIDERS:
  - name: mengluo
    api_key: sk-TodayiSthUrsDAyKfcVivomEFifty
    api_base: https://api.mengluo.work/
    api_type: openai
    models:
      - model_name: grok-4.5
```

## ✨ 功能

- [x] AI上下文对话
- [x] 用户分组上下文
- [x] 支持多模态
- [x] 调用工具
- [x] 图像理解
- [x] 发/删说说
- [x] 发语音
- [x] 点赞

## 🚀 安装

对 Bot 发送`添加插件 chat_toolkit`即可安装

## ⚠️ 注意事项

1. 本插件已包含真寻AI插件默认的`hello`功能，使用本插件前请先**卸载**真寻的AI插件
2. 请删除`zhenxun/builtin_plugins/nickname.py`这个插件，**否则可能会与本插件冲突**
3. Prompt请在 `/data/chat_toolkit/prompt.txt`中设置
4. **请勿安装多个ai插件**

## 🎉 使用

| 命令 |   参数   |   范围    |               说明                |
| :--: | :------: | :-------: | :-------------------------------: |
| `-`  | `prompt` | 私聊/群聊 | 上下文对话，需要@Bot或叫Bot的名字 |

## ⚙️ 配置

|          配置项           |  必填  |                               默认值                               |                               说明                               |
| :-----------------------: | :----: | :----------------------------------------------------------------: | :--------------------------------------------------------------: |
|        `PROVIDER`         | **是** |                                 -                                  |                用于对话的语言模型，包含name/model                |
|     `VISION_PROVIDER`     | **否** |                                 -                                  | 图于图像识别的语言模型，若未指定则默认使用 PROVIDER 中指定的模型 |
| `MAX_TOOL_CALLS_PER_TURN` | **否** |                                `3`                                 |       单次对话中允许的最大工具迭代次数，0 表示禁用工具调用       |
|     `CONTEXT_WINDOW`      | **否** |                                `10`                                |      上下文窗口大小，即提供给大模型的消息总数，默认值为 20       |
|     `MEMORY_ENABLED`      | **否** |                               `True`                               |                         是否启用记忆功能                         |
|    `MEMORY_MAX_WINDOW`    | **否** |                                `20`                                |     记忆窗口大小，即在对话中最多注入的记忆条数，默认值为 20      |
| `MEMORY_MAX_SCOPE_COUNT`  | **否** |                                `50`                                |        对于每个对话场景，最多允许的记忆条数，默认值为 50         |
|   `FACE_SEND_FREQUENCY`   | **否** |                                `20`                                |               触发对话后发送表情包的概率（百分比）               |
|        `BLOCK_TIP`        | **否** |               `咱的脑回路是加密的，偷看要收硬币哦！`               |                     用户触发安全策略时的提示                     |
|       `MAX_TOKENS`        | **否** |                               `4096`                               |                      单次对话最大 token 数                       |
|    `MAX_FORWARD_DEPTH`    | **否** | 若上下文中包含合并转发消息，则最多展开的层数，默认值为 0，即不展开 |

### 关于 `MAX_TOKENS`

`max_tokens` 用于限制模型单次调用生成的最大 token 数量，建议设置不小于 1024。`token` 是文本的基本单位，通常 1 个 `token` 约等于 0.75 个英文单词或 1.5 个中文字符。设置合适的 `max_tokens` 可以控制响应长度和成本，避免过长的输出。如果模型在达到 `max_tokens` 限制前完成回答，会自然结束；如果达到限制，输出可能被截断。

- 作用: 防止生成过长文本，控制 API 调用成本。
- 注意: `max_tokens` 限制的是生成内容的长度，不包括输入。

最佳实践:

- 根据应用场景合理设置 max_tokens。如果需要简短回答，可设为较小的值（如 50）。

## 感谢

- [bl-chat-plugin](https://github.com/Cat-bl/bl-chat-plugin)
- [plugin-chatsalt](https://github.com/fraqjs/plugin-chatsalt)
- [zhenxun_plugin_zhipu_toolkit](https://github.com/molanp/zhenxun_plugin_zhipu_toolkit)
