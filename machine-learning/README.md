# HealthVerse 姿态模型训练与测试

本目录不是页面演示数据，而是一套可复现的模型训练、独立测试和导出管线。输入是 MediaPipe 的 33 个人体关键点；模型预测项目定义的姿态类别，例如 `upright`、`forward_head`、`lean_left`。类别必须来自具有授权和标注说明的数据集，或由参与者知情同意后采集。

## 数据格式

推荐 JSONL，每行一个样本：

```json
{"sample_id":"p01-0001","subject_id":"p01","label":"upright","source":"session-01","landmarks":[{"x":0.5,"y":0.2,"z":-0.1,"visibility":0.99}]}
```

`landmarks` 必须包含 33 点。CSV 也受支持，元数据列为 `sample_id,subject_id,label,source`，关键点列为 `x0,y0,z0,v0` 到 `x32,y32,z32,v32`。

## 采集真实数据

```powershell
python capture_dataset.py --source 0 --subject-id p01 --label upright --output data/posture.jsonl
python capture_dataset.py --source session.mp4 --subject-id p02 --label forward_head --output data/posture.jsonl
```

相邻视频帧高度相关，不能把帧随机拆到训练集和测试集。训练脚本按 `subject_id` 分组切分，任何受试者只会进入一个分区。

## 训练与独立测试

```powershell
python -m pip install -r requirements.txt
python train.py --data data/posture.jsonl --dataset-manifest data/posture.capture-metrics.json --config config.json --output runs/posture
```

脚本比较 Logistic Regression、Random Forest 和 Histogram Gradient Boosting，以验证集 Macro-F1 选择模型，然后只在未参与选择的测试集上判定达标。默认门槛：

- Accuracy ≥ 0.85
- Macro-F1 ≥ 0.80
- 每个类别 Recall ≥ 0.70
- 测试集至少包含 3 名从未参与开发的受试者
- 每个测试类别至少 30 个样本
- 关键点检测覆盖率 ≥ 0.90（在丢弃未检测帧之前统计）

所有条件必须同时满足，`metrics.json` 才会写入 `status: passed`。未提供 pose coverage 清单时也不能通过。`export_model.py` 会拒绝导出未达标模型。外部评估还会拒绝与训练/验证受试者重复的数据。阈值是本项目的部署门槛，不等同于医疗有效性。

特征除归一化关键点与关节角外，还实现了 EduSense 风格的关键点对单位方向与尺度归一化距离；候选模型包含其使用的 MLP 思路。测试报告把人体检测覆盖率与“已检测帧上的分类指标”分开，避免忽略漏检帧。

```powershell
python evaluate.py --model runs/posture/model.joblib --data data/external-test.jsonl
python export_model.py --run runs/posture --output runs/healthverse-pose-model.zip
```

每次训练会生成：`model.joblib`、`metrics.json`、`confusion_matrix.csv`、`training_history.json`、`splits.csv` 和 `model_card.md`。

## 工程测试与 benchmark 的区别

```powershell
$env:PYTHONPATH = "."
python -m unittest discover -s tests -v
```

单元测试只检查特征、分组切分和阈值逻辑，不能作为准确率证据。只有使用注明来源、许可、标签和独立测试分区的真实数据运行 `train.py` 后，输出指标才可报告为 benchmark 结果。
