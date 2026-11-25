# HealthVerse 联邦学习

本目录包含两条可运行路径，状态严格分开：

- `train_federated.py`：在一台计算机上把每个真实 `subject_id` 当作客户端，实际执行 FedAvg；结果只能标记为 `local_federated_test`。
- `coordinator.py` + `client.py`：可在不同设备上联网运行。只有同一轮确实收到至少两个不同设备指纹的更新后，协调器才会标记 `multi_device_federated_run`。

两条路径都只上传模型更新和样本计数，不上传图像、视频、关键点或特征。数据采用真实 MultiPosture 受试者关键点；没有规则或合成样本。

## 单机真实数据 FedAvg

```powershell
python train_federated.py `
  --data ..\data\multiposture-upper.jsonl `
  --config config.json `
  --output runs\fed-v1
```

训练、验证、测试按未见受试者划分。输出包括每轮指标、客户端参与记录、上传字节数、集中式基线和最差测试客户端。该实验验证算法与隐私边界，但不能证明真实网络部署已经完成。

## 多设备运行

协调器：

```powershell
$env:HV_FED_SECRET = "请替换为随机长密钥"
python coordinator.py --host 0.0.0.0 --port 8787 --secret $env:HV_FED_SECRET `
  --tls-cert server.crt --tls-key server.key --min-clients 2
```

每台设备只指定自己的本地受试者数据：

```powershell
python client.py --server https://coordinator.example:8787 --secret $env:HV_FED_SECRET `
  --data ..\data\local-private.jsonl --subject-id anonymous-device-subject
```

请求体使用 HMAC-SHA256 签名；每轮 token 绑定轮次与匿名 client id，过期 token 会被拒绝。生产环境还必须启用 TLS、使用不同于示例的密钥，并限制协调器网络访问。

客户端退出与撤回后续参与：

```powershell
python client.py --server https://coordinator.example:8787 --secret $env:HV_FED_SECRET `
  --withdraw-client-id CLIENT_ID
```

撤回会删除注册和未聚合更新。已经聚合进模型的影响无法从普通 FedAvg 中逐样本删除；如课程演示需要机器遗忘，必须从撤回前检查点重新训练，不能声称即时删除。

## 隐私边界

- 客户端和服务端都会做 update norm clipping。
- 默认未启用高斯噪声，因此不构成差分隐私保证，`epsilon=not_applicable`。
- HMAC/TLS 保护鉴权与传输，但不等于 secure aggregation；当前协调器可见单个客户端更新。
- 匿名设备指纹由主机标识经 HMAC 派生，原始硬件标识不会上传。
- 两个本机进程具有相同设备指纹，集成测试确认它们不会被误报为多设备部署。

## X25519/HKDF 安全聚合实验

`secure_aggregation.py` 实现成对掩码原语；`run_behave_secure_aggregation.py` 对七个真实 BEHAVE 参与者分区启动七个独立进程。每个进程生成临时 X25519 密钥，通过 HKDF-SHA256 派生成对、异号的随机掩码。协调器只接收公钥和带掩码更新。

冻结实验（`runs/secure-aggregation-v1/metrics.json`）中，安全聚合与独立明文审计的最大绝对误差为 `4.996e-15`，预测完全一致；序列隔离评估 Accuracy `0.8069`、Macro-F1 `0.6934`。这证明本次协议路径的掩码抵消与服务端负载边界，**不等于真实多设备部署**：七个客户端仍在同一台电脑上，且尚无掉线恢复、恶意客户端防护或 TLS。安全聚合也不提供差分隐私。

复现实验需要本地 BEHAVE 数据缓存；临时客户端特征只写入系统临时目录并在运行结束后删除：

```powershell
python run_behave_secure_aggregation.py --output runs\secure-aggregation-local
```

## 正式 DP 机制的失败结果

`runs/dp-output-perturbation-v1/metrics.json` 保存另一条正式隐私会计尝试的汇总结果：强凸 L2 softmax ERM 的高斯输出扰动，`epsilon=6`、`delta=1e-5`。它具有样本级、可信管理者中心 DP 会计，但 Macro-F1 仅 `0.2469`，未达到 `0.65` 门槛，因此被拒绝。它不是参与者级 DP，也不是联邦安全聚合，不能作为隐私目标已经完成的证据。

## 测试

```powershell
python -m unittest discover -s tests -v
```

