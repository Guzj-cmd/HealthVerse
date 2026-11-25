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

分类门槛与端到端覆盖率分别报告。分类指标达标时写入
`classifier_status: classifier_passed`；没有原始视频逐帧检测清单时，覆盖率必须为
`pose_coverage_not_evaluated`，端到端状态必须为
`end_to_end_not_evaluated`，不能用已成功提取的 landmark 行反推覆盖率。
`export_model.py` 只允许导出端到端状态达标的模型。外部评估还会拒绝与训练/验证受试者重复的数据。阈值是本项目的部署门槛，不等同于医疗有效性。

特征除归一化关键点与关节角外，还实现了 EduSense 风格的关键点对单位方向与尺度归一化距离；候选模型包含其使用的 MLP 思路。测试报告把人体检测覆盖率与“已检测帧上的分类指标”分开，避免忽略漏检帧。

```powershell
python evaluate.py --model runs/posture/model.joblib --data data/external-test.jsonl
python export_model.py --run runs/posture --output runs/healthverse-pose-model.zip
```

每次训练会生成：`model.joblib`、`metrics.json`、`confusion_matrix.csv`、`training_history.json`、`splits.csv` 和 `model_card.md`。

## 按受试者的稳健性分析

对已有独立测试运行计算 95% 置信区间时，必须以 `subject_id` 为聚类单位重采样，禁止把高度相关的视频帧当作独立样本。下面的命令还会在全部受试者上执行 5 折 GroupKFold，报告每折指标及最差未见受试者组，并写入新的输出目录，拒绝覆盖已有结果：

```powershell
python robustness_analysis.py `
  --upper-data data/multiposture-upper.jsonl --upper-run runs/upper-v2-subject3 `
  --lower-data data/multiposture-lower.jsonl --lower-run runs/lower-v1-subject3 `
  --config config-subject3.json --output runs/robustness-v1 `
  --bootstrap-repeats 2000 --cv-folds 5 --seed 20261125
```

输出包括 `robustness.json`、`cluster_bootstrap_ci.csv`、`groupkfold_folds.csv` 和 `ROBUSTNESS.md`。MultiPosture 输入是已成功提取的 landmark 表，因此 pose coverage 固定报告为 N/A；本分析只评价“关键点可用条件下”的分类器。

## 工程测试与 benchmark 的区别

```powershell
$env:PYTHONPATH = "."
python -m unittest discover -s tests -v
```

单元测试只检查特征、分组切分和阈值逻辑，不能作为准确率证据。只有使用注明来源、许可、标签和独立测试分区的真实数据运行 `train.py` 后，输出指标才可报告为 benchmark 结果。

## CHI / IMWUT 方法实验

`train_chi_inspired.py` 使用 EduSense 的尺度归一化关键点对方向/距离特征，并在开发受试者上用 5 折 GroupKFold 比较固定候选。胜者确定后才对冻结的 3 名测试受试者评一次：

```powershell
python train_chi_inspired.py `
  --data data/multiposture-upper.jsonl `
  --config config-subject3.json `
  --output runs/chi-inspired-v1
```

论文训练方法与 CHI 反馈机制的边界见 `CHI_METHODS.md`。100% 只是优化目标；禁止根据冻结测试集反复调参，也禁止用帧级随机切分制造虚高结果。

## BEHAVE 人体—物体关系辅助模型

`train_behave_relation.py` 从 BEHAVE 官方 30fps SMPL/物体注册参数中抽取坐具接触、倚桌和显示器交互三类。它排除身份形状参数 `betas`，每段序列最多均匀取 48 帧，并按 `SubXX` 做留一参与者评估：

```powershell
python train_behave_relation.py --config datasets/behave-relation.json
```

输出保存在 `runs/behave-relation-v1/`。原始数据不进入 Git；`model.joblib` 也保持本地，直至 BEHAVE 数据所有者明确允许衍生权重再分发。该模型依赖 SMPL/物体拟合变换，是关系头实验，不是原始摄像头端到端模型，也不是健康诊断模型。

第二轮使用嵌套评估比较基线与因果时序窗口特征：

```powershell
python train_behave_relation_v2.py --config datasets/behave-relation-v2.json
```

每个外层参与者完全冻结，候选只在其余参与者的 3 折 GroupCV 中选择，外层只评一次。V2 的 macro-F1 提升到 0.9482，但最弱类召回从 0.8810 降到 0.8631；根据预先声明的“双指标都必须提升”规则，V2 不替换 V1。完整内层消融保存在 `runs/behave-relation-v2/ablation_summary.csv`。

## Edinburgh Office 跨场景情境实验

`train_office_context.py` 使用 20 天真实办公室真值框训练空房、站/走、坐、交谈四类辅助头。评估采用嵌套的“整位参与者 + 整间办公室留一”，候选选择不能看到外层测试办公室：

```powershell
python train_office_context.py `
  --gt-dir ../ccfa-workfiles/datasets/healthverse-expansion/cache/edinburgh-office/GT `
  --output runs/edinburgh-office-context-v1
```

本轮结果为 **REJECTED**：Accuracy 0.5814、Macro-F1 0.6050、坐姿 Recall 0.2128，未达到 Accuracy ≥ 0.80、Macro-F1 ≥ 0.80、每类 Recall ≥ 0.50。脚本在门槛失败时不会生成 `model.joblib`；该模型未接入网页。337 个跌倒正例全部来自同一参与者/办公室，因此排除在四类正式指标之外，也不能宣称已经验证跌倒检测。结论是检测框几何本身不足以跨办公室泛化，下一轮必须加入图像、人体姿态或场景标定证据。

## COUCH MoCap 标签审计

`audit_couch_mocap.py` 直接读取官方 ZIP，不解包或重新分发数据。它检查归档哈希、485 个 NPZ 的数组结构、六个被试覆盖和源区间边界，并在缺少明确目标时阻止训练：

```powershell
python audit_couch_mocap.py `
  --archive ../ccfa-workfiles/datasets/healthverse-expansion/cache/couch/mocap_npz.zip `
  --config datasets/couch-mocap.json `
  --out-dir runs/couch-mocap-audit-v1
```

当前归档没有 `contact_type`、`hand_contact`、`label` 或 `target` 数组，也没有覆盖六个被试的官方序列标签清单。因此不从文件名、关节距离或 `start_idx/end_idx` 推导手接触/健康标签；计划的六被试 LOSO 运行 0 折，输出只有审计指标与报告，没有模型权重。

## Charades 真实家庭关系实验

`train_charades_relation.py` 直接流式读取 Charades 官方 RGB two-stream VGG-16 fc7 归档，不解压或提交近两百万个源特征文件。它按论文的稀疏 RGB 基线思路，每秒取约一个真实观测，形成每视频 mean+max 特征，并识别坐椅、桌面关系、笔记本交互、沙发/地面/床接触和坐站转换七个可观察关系：

```powershell
python train_charades_relation.py `
  --cache-dir ..\..\..\ccfa-workfiles\charades\cache
```

官方训练/测试为 214/53 名参与者且身份交集为零。三个 `alpha` 候选和七个阈值只在训练参与者的 4 折 GroupKFold 中选择，官方测试只评一次。本轮 official-test macro-mAP 为 0.3634、macro-F1 为 0.4562；虽然 AP 门槛通过，但七类 Recall 均低于预先声明的 0.50，结果判为 **REJECTED**，不会接入网页。`model.joblib` 与逐视频预测受许可约束，默认保留在本地忽略目录。

## 浏览器模型导出与一致性验证

通过的 sklearn HGB / RandomForest 会被转换为纯 JSON 树结构，网页在本地计算 456 维特征并执行同一模型。120 个冻结测试样本的 Python 与 JavaScript 预测标签必须完全一致，概率绝对误差小于 `1e-5`：

```powershell
python browser-export/export_browser_models.py `
  --upper-run runs/upper-v2-subject3 --lower-run runs/chi-inspired-v1-lower-final `
  --output ../src/main/webapp/assets/models/posture-classifiers-v1.json

python browser-export/make_parity_fixture.py `
  --machine-learning-root . --data data/multiposture-upper.jsonl `
  --upper-run runs/upper-v2-subject3 --lower-run runs/chi-inspired-v1-lower-final `
  --output browser-export/test-fixtures/parity-120.json

node browser-export/test_model_parity.mjs
```

## 跨场景、跨参与者关系泛化

`scene-generalization/` 保存目标 3 的冻结评估与复现脚本。它只使用 Charades 官方训练分区；每折同时留出一个住宅场景，并从训练源场景移除所有出现在该目标场景中的参与者。源场景专家的权重仅由其他源场景确定，目标标签不参与权重选择。

通过候选的 aggregate macro-mAP 为 `0.3695`，相对冻结基线 `0.2614` 提升 `0.1080`；五个目标场景均超过预声明的 `0.25` 门槛，参与者交集均为零。该模块是关系识别泛化证据，不是健康结局或建议模型，也不替代正在训练的原始 RGB 端到端分支。
