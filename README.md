# dont-push (WIP)

这个项目的名称叫 “别催了，在写了".

作为研究生，有时候自己会有一些事情要处理，但是导师又会催着写论文，所以就有了这个项目。该项目可以实现对 Overleaf 上的论文自动修改，并通过
Websocket 实时检测文档中是否有人上线、下线及编辑。当检测到特定成员上线时，程序可以推送通知消息。当用户闲时，程序可以 “改上两笔”，保证最后修改时间较新。
等导师周末打开论文平台、看到你的论文两分钟前刚刚被修改时，他就会满意地想：嗯，这个学生真是勤奋啊。

> [!WARNING]
> 本项目不能完成你的论文。 

希望你能够通过这个项目，合理地规划自己的时间，不要被导师的催促所左右，也不要因为自己的事情而耽误了论文的进度。

## 功能

- [x] 获取 Overleaf 中的项目列表
- [x] 通过 Websocket 实时检测上线、下线及编辑行为
- [x] 文档修改
- [ ] 上线通知
- [ ] 自动保存到 Git  

