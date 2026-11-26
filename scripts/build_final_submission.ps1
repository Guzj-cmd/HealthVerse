[CmdletBinding()]
param(
    [string]$DestinationBase = 'D:\CodexData\HealthVerse\deliverables-final'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$destinationBaseFull = [System.IO.Path]::GetFullPath($DestinationBase)
$buildRoot = Join-Path $destinationBaseFull 'HealthVerse_最终提交文件夹'
$zipPath = Join-Path $destinationBaseFull 'HealthVerse_最终提交文件夹_2026-11-26.zip'
$sourceArchive = Join-Path $destinationBaseFull '__healthverse_source.zip'

if (-not $destinationBaseFull.StartsWith('D:\CodexData\HealthVerse\deliverables-final', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "DestinationBase must stay under D:\CodexData\HealthVerse\deliverables-final"
}
if (Test-Path -LiteralPath $buildRoot) {
    throw "Build directory already exists: $buildRoot"
}
if (Test-Path -LiteralPath $zipPath) {
    throw "Submission ZIP already exists: $zipPath"
}

New-Item -ItemType Directory -Force -Path $destinationBaseFull | Out-Null
$directories = @(
    $buildRoot,
    (Join-Path $buildRoot '01_课程作业报告'),
    (Join-Path $buildRoot '02_模型与影像来源'),
    (Join-Path $buildRoot '03_演示视频与截图\截图'),
    (Join-Path $buildRoot '04_测试结果\模型证据'),
    (Join-Path $buildRoot '05_改进前后对照\改进前后截图'),
    (Join-Path $buildRoot '06_使用与提交说明')
)
New-Item -ItemType Directory -Force -Path $directories | Out-Null

Push-Location $repoRoot
try {
    git archive --format=zip --prefix=HealthVerse/ -o $sourceArchive HEAD
    if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $buildRoot
} finally {
    Pop-Location
}
Remove-Item -LiteralPath $sourceArchive

Copy-Item -LiteralPath (Join-Path $repoRoot 'output\pdf\HealthVerse_课程作业报告_最终版.pdf') -Destination (Join-Path $buildRoot '01_课程作业报告')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\00_提交清单与课程要求对应.txt') -Destination (Join-Path $buildRoot 'HealthVerse_提交清单与课程要求对应.txt')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\02_模型与数据来源说明.md') -Destination (Join-Path $buildRoot '02_模型与影像来源\HealthVerse_模型与数据来源说明.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\03_演示影像说明.md') -Destination (Join-Path $buildRoot '03_演示视频与截图\HealthVerse_演示影像说明.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\04_测试与评估报告.md') -Destination (Join-Path $buildRoot '04_测试结果\HealthVerse_测试与评估报告.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\04_构建与回归测试.txt') -Destination (Join-Path $buildRoot '04_测试结果\HealthVerse_构建与回归测试.txt')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\05_改进前后对照.md') -Destination (Join-Path $buildRoot '05_改进前后对照\HealthVerse_改进前后对照.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\submission\06_运行与提交说明.txt') -Destination (Join-Path $buildRoot '06_使用与提交说明\HealthVerse_运行与提交说明.txt')

Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\before-static-prototype.jpg') -Destination (Join-Path $buildRoot '03_演示视频与截图\截图\01_修改前_静态原型.jpg')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\after-live-video.png') -Destination (Join-Path $buildRoot '03_演示视频与截图\截图\02_修改后_真实视频推理.png')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\after-privacy-federated.png') -Destination (Join-Path $buildRoot '03_演示视频与截图\截图\03_修改后_隐私联邦状态.png')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\before-static-prototype.jpg') -Destination (Join-Path $buildRoot '05_改进前后对照\改进前后截图\01_修改前_静态原型.jpg')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\after-live-video.png') -Destination (Join-Path $buildRoot '05_改进前后对照\改进前后截图\02_修改后_真实视频推理.png')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\screenshots\after-privacy-federated.png') -Destination (Join-Path $buildRoot '05_改进前后对照\改进前后截图\03_修改后_隐私联邦状态.png')

Copy-Item -LiteralPath (Join-Path $repoRoot 'machine-learning\datasets.registry.json') -Destination (Join-Path $buildRoot '02_模型与影像来源')
Copy-Item -LiteralPath (Join-Path $repoRoot 'machine-learning\CHI_METHODS.md') -Destination (Join-Path $buildRoot '02_模型与影像来源')

$evidenceFiles = @(
    'machine-learning\runs\upper-v2-subject3\metrics.json',
    'machine-learning\runs\upper-v2-subject3\model_card.md',
    'machine-learning\runs\upper-v2-subject3\confusion_matrix.csv',
    'machine-learning\runs\chi-inspired-v1-lower-final\metrics.json',
    'machine-learning\runs\chi-inspired-v1-lower-final\model_card.md',
    'machine-learning\runs\chi-inspired-v1-lower-final\confusion_matrix.csv',
    'machine-learning\runs\chi-inspired-v1\ITERATION_HISTORY.md',
    'machine-learning\runs\behave-relation-v1\metrics.json',
    'machine-learning\runs\behave-relation-v1\model_card.md',
    'machine-learning\runs\behave-relation-v2\metrics.json',
    'machine-learning\runs\charades-relation-v1\metrics.json',
    'machine-learning\runs\charades-relation-v1\MODEL_CARD.md',
    'machine-learning\runs\edinburgh-office-context-v1\metrics.json',
    'machine-learning\runs\edinburgh-office-context-v1\model_card.md',
    'machine-learning\agent-policy\artifacts\evidence-gate-v1\metrics.json',
    'machine-learning\agent-policy\artifacts\evidence-gate-v1\model_card.md',
    'machine-learning\agent-policy\iteration_history.md',
    'machine-learning\federated\runs\secure-aggregation-v1\metrics.json',
    'machine-learning\federated\runs\secure-aggregation-v1\model_card.md',
    'machine-learning\federated\runs\dp-output-perturbation-v1\metrics.json',
    'machine-learning\federated\runs\dp-output-perturbation-v1\model_card.md',
    'machine-learning\federated\runs\iteration_history.md',
    'machine-learning\scene-generalization\artifacts\scene-specialist-v1\metrics.json',
    'machine-learning\scene-generalization\artifacts\scene-specialist-v1\model_card.md'
)
foreach ($relative in $evidenceFiles) {
    $source = Join-Path $repoRoot $relative
    if (-not (Test-Path -LiteralPath $source)) { throw "Missing evidence file: $relative" }
    $safeName = ($relative -replace '[\\/]', '__')
    Copy-Item -LiteralPath $source -Destination (Join-Path $buildRoot "04_测试结果\模型证据\$safeName")
}

Copy-Item -LiteralPath (Join-Path $repoRoot 'README.md') -Destination (Join-Path $buildRoot '06_使用与提交说明\HealthVerse_README.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'SUBMISSION_GUIDE.md') -Destination (Join-Path $buildRoot '06_使用与提交说明\HealthVerse_源码提交说明.md')
Copy-Item -LiteralPath (Join-Path $repoRoot 'IMPLEMENTATION_STATUS.md') -Destination (Join-Path $buildRoot '06_使用与提交说明\HealthVerse_实现与迭代记录.md')

$sourceCommit = (git -C $repoRoot rev-parse HEAD).Trim()
[System.IO.File]::WriteAllLines(
    (Join-Path $buildRoot '06_使用与提交说明\HealthVerse_源码提交.txt'),
    @("GitHub: https://github.com/Guzj-cmd/HealthVerse", "Commit: $sourceCommit"),
    [System.Text.UTF8Encoding]::new($false)
)

$warSource = Join-Path $repoRoot 'target\HealthVerse_Submission.war'
if (-not (Test-Path -LiteralPath $warSource)) { throw "Missing WAR: run Maven package first" }
$warTargetDirectory = Join-Path $buildRoot 'HealthVerse\target'
New-Item -ItemType Directory -Force -Path $warTargetDirectory | Out-Null
Copy-Item -LiteralPath $warSource -Destination $warTargetDirectory

$hashLines = Get-ChildItem -LiteralPath $buildRoot -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($buildRoot.Length + 1)
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        "$hash  $relative"
    }
[System.IO.File]::WriteAllLines((Join-Path $buildRoot 'SHA256SUMS.txt'), $hashLines, [System.Text.UTF8Encoding]::new($false))

Compress-Archive -LiteralPath $buildRoot -DestinationPath $zipPath -CompressionLevel Optimal

$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
[pscustomobject]@{
    Folder = $buildRoot
    Zip = $zipPath
    Files = (Get-ChildItem -LiteralPath $buildRoot -Recurse -File).Count
    ZipBytes = (Get-Item -LiteralPath $zipPath).Length
    ZipSha256 = $zipHash
}
