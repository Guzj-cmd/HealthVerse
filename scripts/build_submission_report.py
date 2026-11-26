#!/usr/bin/env python3
"""Build the evidence-grounded HealthVerse course report PDF."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "HealthVerse_课程作业报告_最终版.pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("HV-CN", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("HV-CN-Bold", str(FONT_BOLD)))


def metric(value: float) -> str:
    return f"{value:.4f}"


def add_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#96B8D5"))
    canvas.setLineWidth(0.8)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont("HV-CN", 8)
    canvas.setFillColor(colors.HexColor("#52616B"))
    canvas.drawString(18 * mm, 9 * mm, "HealthVerse · 真实证据约束的人机协同健康空间")
    canvas.drawRightString(width - 18 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def image(path: Path, width: float) -> Image:
    item = Image(str(path))
    ratio = item.imageHeight / item.imageWidth
    item.drawWidth = width
    item.drawHeight = width * ratio
    return item


def build() -> Path:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    upper = read_json("machine-learning/runs/upper-v2-subject3/metrics.json")
    lower = read_json("machine-learning/runs/chi-inspired-v1-lower-final/metrics.json")
    behave = read_json("machine-learning/runs/behave-relation-v1/metrics.json")
    agent = read_json("machine-learning/agent-policy/artifacts/evidence-gate-v1/metrics.json")
    charades = read_json("machine-learning/runs/charades-relation-v1/metrics.json")
    office = read_json("machine-learning/runs/edinburgh-office-context-v1/metrics.json")
    federated = read_json("machine-learning/federated/runs/secure-aggregation-v1/metrics.json")
    scene = read_json("machine-learning/scene-generalization/artifacts/scene-specialist-v1/metrics.json")

    palette = {
        "blue": colors.HexColor("#DCECF8"),
        "blue_line": colors.HexColor("#7CA9C9"),
        "pink": colors.HexColor("#F7E1E7"),
        "green": colors.HexColor("#E5F2D9"),
        "yellow": colors.HexColor("#FFF0BF"),
        "ink": colors.HexColor("#1C2328"),
        "muted": colors.HexColor("#52616B"),
        "accent": colors.HexColor("#27866B"),
    }

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "CoverTitle", fontName="HV-CN-Bold", fontSize=27, leading=36,
        textColor=palette["ink"], alignment=TA_CENTER, spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "CoverSub", fontName="HV-CN", fontSize=12, leading=19,
        textColor=palette["muted"], alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "H1CN", fontName="HV-CN-Bold", fontSize=19, leading=27,
        textColor=palette["ink"], spaceBefore=5, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "H2CN", fontName="HV-CN-Bold", fontSize=13, leading=20,
        textColor=palette["accent"], spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "BodyCN", fontName="HV-CN", fontSize=9.6, leading=16,
        textColor=palette["ink"], alignment=TA_LEFT, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "SmallCN", fontName="HV-CN", fontSize=8, leading=12,
        textColor=palette["muted"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        "TableCellCN", fontName="HV-CN", fontSize=7.8, leading=11,
        textColor=palette["ink"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        "TableHeadCN", fontName="HV-CN-Bold", fontSize=8, leading=11,
        textColor=palette["ink"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        "CalloutCN", fontName="HV-CN", fontSize=9.4, leading=15,
        textColor=palette["ink"], leftIndent=10, rightIndent=10,
        borderColor=palette["blue_line"], borderWidth=1, borderPadding=9,
        backColor=palette["blue"], spaceBefore=6, spaceAfter=9,
    ))

    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=16 * mm,
        title="HealthVerse 课程作业报告",
        author="HealthVerse 项目组",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates(PageTemplate(id="report", frames=frame, onPage=add_page))

    story = []
    story.extend([
        Spacer(1, 28 * mm),
        Paragraph("HealthVerse", styles["CoverTitle"]),
        Paragraph("真实证据约束的人机协同健康空间", styles["CoverTitle"]),
        Spacer(1, 5 * mm),
        Paragraph("课程设计最终报告 · 2026-11-26", styles["CoverSub"]),
        Spacer(1, 12 * mm),
        image(ROOT / "docs/screenshots/after-live-video.png", 158 * mm),
        Spacer(1, 7 * mm),
        Paragraph(
            "核心原则：先观察，再推断，再求证；所有空间调整可撤销，所有个性化记忆由用户确认。",
            styles["CalloutCN"],
        ),
        PageBreak(),
    ])

    story.extend([
        Paragraph("1. 设计动机与需求", styles["H1CN"]),
        Paragraph(
            "学习、办公和居家活动中的健康问题，往往不是单一姿态造成，而是人体、物体、任务、时间和个人限制共同作用的结果。传统姿态提醒容易把短暂动作误判为风险，也常在不知道任务目的时打断用户。HealthVerse 因此把问题重新定义为“可观察证据驱动的空间协同”：系统先理解当前情境，再提出低打扰、可纠正、可撤销的建议，并通过短时自我实验验证是否适合当前用户。",
            styles["BodyCN"],
        ),
        Paragraph("从需求出发的八项能力", styles["H2CN"]),
    ])
    needs = [
        ["01", "真实输入", "摄像头或本地视频，不使用预填演示结论"],
        ["02", "人体与环境", "33 点姿态、目标检测、人与物体二维关系"],
        ["03", "时序行为", "按真实帧时间累计，避免单帧误报"],
        ["04", "证据约束 Agent", "未知事实标未知，不生成厘米、深度或医疗诊断"],
        ["05", "空间协同", "比较方案、保留约束、用户确认后执行"],
        ["06", "个人验证", "3 分钟基线 + 6 分钟方案 + 主观评分"],
        ["07", "校准与记忆", "只保存派生量和已确认结果，可停用、删除、导出"],
        ["08", "隐私联邦", "原始画面本地处理，联网状态真实可核验"],
    ]
    t = Table(needs, colWidths=[13 * mm, 28 * mm, 116 * mm], repeatRows=0)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 0), (0, -1), palette["green"]),
        ("BACKGROUND", (1, 0), (1, -1), palette["blue"]),
        ("GRID", (0, 0), (-1, -1), 0.7, palette["ink"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([t, Spacer(1, 4 * mm)])
    story.append(Paragraph(
        "边界：本项目是课程与研究原型，不是医疗器械。单目视频不能提供真实厘米或深度；短时变化不能证明长期健康效果。",
        styles["CalloutCN"],
    ))

    story.extend([
        PageBreak(),
        Paragraph("2. 人机交互理论落地", styles["H1CN"]),
        Paragraph(
            "课程内容被落实为具体交互机制，而不是只写在说明页中：概念模型用 Observe → Infer → Confirm 表达 Agent 状态；直接操纵用于方案参数；反馈与前馈显示“当前证据”和“下一步会发生什么”；撤销、纠正、删除与隐私开关保障用户控制；短时实验把系统建议转化为可验证假设。",
            styles["BodyCN"],
        ),
        Paragraph("论文方法与本项目实现", styles["H2CN"]),
    ])
    papers_raw = [
        ["工作", "采用的方法", "HealthVerse 落地"],
        ["EduSense · IMWUT 2019", "尺度归一化关键点对方向/距离", "456 维姿态特征、受试者隔离训练"],
        ["Posture Feedback Review · CHI 2024", "任务、环境、隐私与偏好共同决定反馈", "不把“始终挺直”设为唯一目标"],
        ["Slow Robots · CHI 2019", "低打扰、缓慢介入", "证据稳定后才建议，且不自动改变环境"],
        ["PosProjector · CHI 2026", "持续异常后的渐进反馈", "高置信非中性姿态持续 5 秒才进入建议态"],
    ]
    papers = [
        [Paragraph(value, styles["TableHeadCN"]) for value in papers_raw[0]],
        *[
            [Paragraph(value, styles["TableCellCN"]) for value in row]
            for row in papers_raw[1:]
        ],
    ]
    t = Table(papers, colWidths=[46 * mm, 57 * mm, 60 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "HV-CN-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.1),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (-1, 0), palette["pink"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["blue"]]),
        ("GRID", (0, 0), (-1, -1), 0.65, palette["ink"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([t, Spacer(1, 4 * mm)])
    story.extend([
        Paragraph("3. 系统架构与数据流", styles["H1CN"]),
        Paragraph(
            "浏览器端负责视频解码、MediaPipe Pose、EfficientDet、姿态模型推理、二维空间关系与时序累计；Servlet 后端只接收结构化证据和用户消息，并可连接远端 Agent。校准、实验和个人记忆默认保存在浏览器 localStorage。联邦客户端只上传参数更新；网页通过 /api/health 读取协调器白名单状态，不暴露密钥与端点。",
            styles["BodyCN"],
        ),
    ])
    arch = [
        ["真实摄像头/视频", "→", "本地视觉模型", "→", "结构化证据"],
        ["结构化证据 + 用户目标", "→", "证据约束 Agent", "→", "可撤销方案"],
        ["基线/方案时序 + 评分", "→", "证据门槛", "→", "确认后个人记忆"],
        ["本地参数更新", "→", "联邦协调器", "→", "真实运行状态"],
    ]
    t = Table(arch, colWidths=[44 * mm, 9 * mm, 48 * mm, 9 * mm, 53 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (0, -1), palette["blue"]),
        ("BACKGROUND", (2, 0), (2, -1), palette["green"]),
        ("BACKGROUND", (4, 0), (4, -1), palette["yellow"]),
        ("BOX", (0, 0), (-1, -1), 0.8, palette["ink"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA5AC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t)

    story.extend([
        PageBreak(),
        Paragraph("4. 真实模型训练与冻结评估", styles["H1CN"]),
        Paragraph(
            "训练遵循“参与者隔离、开发集选择、冻结测试一次”的协议。相邻帧不会随机分入训练与测试两侧。100% 是优化方向，不是预设结果；未达门槛的分支保留真实失败记录且不接入网页。",
            styles["BodyCN"],
        ),
    ])
    rows = [
        ["能力 / 数据", "协议", "Accuracy", "Macro-F1 / mAP", "结论"],
        ["上身姿态 · MultiPosture", "3 名未见受试者", metric(upper["test"]["accuracy"]), metric(upper["test"]["macro_f1"]), "接入网页"],
        ["下身姿态 · MultiPosture", "3 名未见受试者", metric(lower["test"]["accuracy"]), metric(lower["test"]["macro_f1"]), "接入网页"],
        ["人-物关系 · BEHAVE v1", "7 人 LOSO", metric(behave["aggregate_loso"]["accuracy"]), metric(behave["aggregate_loso"]["macro_f1"]), "研究关系头通过"],
        ["Agent 安全门 · BEHAVE", "7 人 LOSO", metric(agent["accuracy"]), metric(agent["macro_f1"]), "仅拒绝/求证门"],
        ["家庭关系 · Charades", "214/53 人官方分离", "-", metric(charades["official_test_evaluated_once"]["macro_f1"]), "拒绝接入"],
        ["办公室情境 · Edinburgh", "人+办公室双留出", metric(office["accuracy"]), metric(office["macro_f1"]), "拒绝接入"],
        ["安全聚合模型 · BEHAVE", "同机 7 进程", metric(federated["frozen_evaluation"]["accuracy"]), metric(federated["frozen_evaluation"]["macro_f1"]), "协议通过/效用未达门"],
        ["跨场景关系 · Charades", "5 个场景+身份隔离", "-", metric(scene["aggregate"]["macro_map_supported"]), "泛化门通过"],
    ]
    t = Table(rows, colWidths=[43 * mm, 40 * mm, 25 * mm, 33 * mm, 30 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "HV-CN-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (-1, 0), palette["blue"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FA")]),
        ("GRID", (0, 0), (-1, -1), 0.6, palette["ink"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (3, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([t, Spacer(1, 4 * mm)])
    story.append(Paragraph(
        "指标解释：姿态分类数字仅评价“关键点已成功提取”的样本，不等同于摄像头端到端覆盖率；Agent 的 1.0 教师一致性分支也不等同于医疗正确性。",
        styles["CalloutCN"],
    ))
    story.extend([
        Paragraph("失败驱动迭代", styles["H2CN"]),
        Paragraph(
            "Charades 官方测试七类召回均低于预设 0.50，Edinburgh 坐姿召回只有 0.2128，差分隐私输出扰动 Macro-F1 只有 0.2469；这些分支被明确标记 REJECTED，未接入产品。BEHAVE v2 的 Macro-F1 虽提高到 0.9482，但最弱类召回下降，因“双指标均提升”替换规则而保留 v1。",
            styles["BodyCN"],
        ),
    ])

    story.extend([
        PageBreak(),
        Paragraph("5. 网页闭环实现", styles["H1CN"]),
        image(ROOT / "docs/screenshots/after-live-video.png", 166 * mm),
        Spacer(1, 3 * mm),
        Paragraph(
            "真实 Charades 视频导入后，页面显示 33 点姿态骨架、本地训练分类结果、模型置信度、时序证据与 Agent 求证。EfficientDet 与空间推理只在获得检测框时建立人-物关系；未观察到的对象不会被写入建议。",
            styles["BodyCN"],
        ),
        Paragraph("短时实验与记忆门槛", styles["H2CN"]),
        Paragraph(
            "实验被拆为 3 分钟原布局基线与 6 分钟候选方案，两段各自记录独立时序快照。每段至少需要 5 秒有效姿态证据；证据不足时仍可保存审计记录，但 evidenceStatus=insufficient，且不会进入个性化偏好记忆。",
            styles["BodyCN"],
        ),
        Paragraph("个人校准", styles["H2CN"]),
        Paragraph(
            "用户从真实视频或摄像头采集三次关键点后，系统只保存肩宽、左右触达和躯干长度等归一化派生量，以及样本数量与来源标识；不保存原始视频或逐帧 landmark 序列。",
            styles["BodyCN"],
        ),
    ])

    story.extend([
        PageBreak(),
        Paragraph("6. 隐私、联邦与真实性边界", styles["H1CN"]),
        image(ROOT / "docs/screenshots/after-privacy-federated.png", 145 * mm),
        Spacer(1, 3 * mm),
        Paragraph(
            "隐私面板区分“加入意愿”和“已上传更新”。网页读取真实协调器状态：本次网络轮次由 MultiPosture subject-1 与 subject-2 的真实数据客户端产生，协调器完成一轮聚合；因为两客户端来自同一物理机，匿名设备指纹仍为 1，界面保持“尚未验证多设备轮次”，不会把多进程冒充为多设备。",
            styles["BodyCN"],
        ),
        Paragraph("当前可证明 / 尚不能证明", styles["H2CN"]),
    ])
    boundary = [
        ["可以证明", "不能据此宣称"],
        ["真实网络客户端、参数裁剪、HMAC/TLS 配置、状态探针", "已完成两台物理设备的生产验证"],
        ["同机独立进程的 X25519 成对掩码可抵消", "当前网页默认协调器一定看不到单个更新"],
        ["原始画面在浏览器会话中处理", "浏览器库、操作系统或用户导出绝对零风险"],
        ["用户可关闭实验保存、个性化和联邦意愿", "勾选意愿就等于已经训练或上传"],
    ]
    t = Table(boundary, colWidths=[82 * mm, 82 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "HV-CN-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (0, 0), palette["green"]),
        ("BACKGROUND", (1, 0), (1, 0), palette["pink"]),
        ("GRID", (0, 0), (-1, -1), 0.65, palette["ink"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.extend([
        PageBreak(),
        Paragraph("7. 迭代记录与前后对照", styles["H1CN"]),
        Paragraph("修改前：静态原型", styles["H2CN"]),
        image(ROOT / "docs/screenshots/before-static-prototype.jpg", 142 * mm),
        Paragraph(
            "早期页面已具备手绘论文图风格，但存在固定姿态、固定记忆、固定分析数字和演示性建议，无法证明摄像头、模型、实验或联邦能力。",
            styles["BodyCN"],
        ),
        Paragraph("修改后：真实运行闭环", styles["H2CN"]),
        image(ROOT / "docs/screenshots/after-live-video.png", 142 * mm),
        Paragraph(
            "最终版本用摄像头/视频、浏览器姿态模型、物体检测、二维关系、真实帧时间、证据门槛、用户评分和真实协调器状态替换固定演示数据。视觉仍保留手绘边框、不同线型与浅蓝/粉/绿论文图配色。",
            styles["BodyCN"],
        ),
    ])

    story.extend([
        PageBreak(),
        Paragraph("8. 验证结果与复现方式", styles["H1CN"]),
    ])
    tests = [
        ["检查", "结果"],
        ["Java/JUnit", "4/4 通过：Agent 证据约束 2 项，联邦状态白名单 2 项"],
        ["Python 联邦", "8/8 通过：裁剪、聚合、同机不冒充多设备、安全掩码等"],
        ["JavaScript 空间推理", "11/11 断言通过"],
        ["Maven WAR", "clean package 成功，生成 target/HealthVerse_Submission.war"],
        ["浏览器真实视频", "MediaPipe 33 点、姿态模型、时序状态与 Agent 面板可见"],
        ["证据不足实验", "实验记录为 insufficient，memories 保持空数组"],
        ["Agent 远端不可用", "降级到已测试本地证据回退，不臆测未观察对象"],
    ]
    t = Table(tests, colWidths=[48 * mm, 116 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "HV-CN-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "HV-CN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 0), (-1, 0), palette["blue"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["green"]]),
        ("GRID", (0, 0), (-1, -1), 0.65, palette["ink"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([t, Spacer(1, 5 * mm)])
    story.append(Paragraph(
        "复现命令：.\\mvnw.cmd clean package；node machine-learning/browser-export/test_spatial_inference.mjs；python -m unittest discover -s machine-learning/federated/tests -v。完整训练脚本、分割清单、混淆矩阵、模型卡和迭代历史均随源码提交。",
        styles["CalloutCN"],
    ))
    story.extend([
        Paragraph("9. 结论", styles["H1CN"]),
        Paragraph(
            "HealthVerse 已从静态网页原型转变为可运行的横向功能闭环：真实视觉输入驱动人体与环境感知，时序证据约束 Agent，空间方案通过短时实验验证，结果经用户确认后进入可控记忆，联邦状态按真实设备证据呈现。项目同时保留未达门槛的失败实验和部署边界，避免以演示数据、数据泄漏或模拟多设备替代真实证据。",
            styles["BodyCN"],
        ),
        Paragraph("主要参考", styles["H2CN"]),
        Paragraph(
            "[1] Krauter et al. Sitting Posture Recognition and Feedback: A Literature Review. CHI 2024. DOI: 10.1145/3613904.3642657<br/>"
            "[2] Shin et al. Slow Robots for Unobtrusive Posture Correction. CHI 2019. DOI: 10.1145/3290605.3300843<br/>"
            "[3] Ahuja et al. EduSense: Practical Classroom Sensing at Scale. IMWUT 2019. DOI: 10.1145/3351229<br/>"
            "[4] MultiPosture v1. Zenodo DOI: 10.5281/zenodo.14230872<br/>"
            "[5] MediaPipe Pose Landmarker Web documentation.",
            styles["SmallCN"],
        ),
    ])

    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build())
