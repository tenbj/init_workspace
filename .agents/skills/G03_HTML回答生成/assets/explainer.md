---
title: TCP 三次握手
subtitle: 双方交换初始序号，并确认对方已收到
lang: zh
template: sheet
theme: blueprint
---

## A 核心结论
```callout info 为什么需要第三步
第三次报文确认服务端的初始序号。
服务端收到该确认后，进入连接已建立状态。
```

## B 三次报文
```sequence num
客户端 -> 服务端: SYN，seq=x
服务端 -> 客户端: SYN+ACK，seq=y，ack=x+1
客户端 -> 服务端: ACK，seq=x+1，ack=y+1
```

## C 两个初始序号
| 符号 | 含义 | 对端如何确认 |
|---|---|---|
| x | 客户端初始序号 | 第二次报文携带 ack=x+1 |
| y | 服务端初始序号 | 第三次报文携带 ack=y+1 |

## D 服务端状态
```flow LR
LISTEN -> SYN_RECEIVED: 收到 SYN
SYN_RECEIVED -> ESTABLISHED: 收到有效 ACK
```
