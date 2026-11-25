# 联邦训练迭代记录

所有数字均来自真实 MultiPosture 受试者关键点；每名 `subject_id` 是一个客户端。三轮实验都使用同一受试者分组，因此 v2/v3 属于看到前一轮测试结果后的探索性改进，不能替代新的外部参与者确认测试。

| 迭代 | 修改 | Accuracy | Macro-F1 | 最低类别 Recall | 结果 |
|---|---|---:|---:|---:|---|
| fed-v1 | 35 轮 FedAvg，2 local epochs，无类别平衡 | 0.9238 | 0.8988 | TLB 0.4943 | failed |
| fed-v2-balanced | 客户端类别平衡，60 轮，96 hidden | 0.9255 | 0.9142 | TLB 0.6782 | failed |
| fed-v3-longer | 120 轮，128 hidden，更小学习率 | 0.9271 | 0.9117 | TLB 0.7126 | exploratory passed |

集中式 v3 baseline 的 Macro-F1 为 0.9460；联邦模型低 0.0343，体现了隐私训练的实际性能代价。v3 上传参数更新累计 90,350,400 bytes，原始图像、视频和 landmarks 上传量为 0。

`exploratory passed` 只表示达到了本项目预注册的数值门槛（Accuracy >= 0.85、Macro-F1 >= 0.80、每类 Recall >= 0.70）。由于同一测试分区在前两轮已被查看，部署前必须再用完全未参与迭代的新参与者数据确认。

