<#
.SYNOPSIS
    Project structure normalization: check or fix.
.DESCRIPTION
    Checks 6 standards (root dirs, .agents, output, .memory, .history, .temp/input).
    --Check : report PASS/FAIL/WARN only.
    --Fix   : report then fix (create missing, move extras to .temp).
#>

param(
    [switch]$Check,
    [switch]$Fix
)

$ErrorActionPreference = "Continue"
$wn = Split-Path -Parent $MyInvocation.MyCommand.Path
while ($wn -and -not (Test-Path (Join-Path $wn ".history"))) {
    $p = Split-Path $wn -Parent
    if ($p -eq $wn) { $wn = $null; break }
    $wn = $p
}
if (-not $wn) { Write-Host "ERROR: Workspace root not found"; exit 1 }

$workspaceSpec = $null
$specPath = Join-Path $wn ".system\standards\workspace-spec.json"
if (Test-Path $specPath) {
    try {
        $workspaceSpec = Get-Content $specPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Write-Host "WARN: workspace-spec.json could not be parsed; using built-in fallback standards"
        $workspaceSpec = $null
    }
}

$issues = 0; $warnings = 0; $passes = 0
$fixLog = @()
$snapshottedProjects = @{}

function cnp($n, $b) { return [System.Text.Encoding]::UTF8.GetString($b) }

$S_mulu      = cnp 0 (@(0xE7,0x9B,0xAE,0xE5,0xBD,0x95))
$S_ver_log   = cnp 0 (@(0xE7,0x89,0x88,0xE6,0x9C,0xAC,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_conv      = cnp 0 (@(0xE5,0xAF,0xB9,0xE8,0xAF,0x9D,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_sys_rec   = cnp 0 (@(0xE7,0xB3,0xBB,0xE7,0xBB,0x9F,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_knowledge = cnp 0 (@(0xE7,0x9F,0xA5,0xE8,0xAF,0x86,0xE6,0x8F,0x90,0xE7,0x82,0xBC))
$S_map        = cnp 0 (@(0xE5,0x85,0xA8,0xE5,0xB1,0x80,0xE7,0x9F,0xA5,0xE8,0xAF,0x86,0xE5,0x9C,0xB0,0xE5,0x9B,0xBE))
$S_rule_chg   = cnp 0 (@(0xE8,0xA7,0x84,0xE5,0x88,0x99,0xE5,0x8F,0x98,0xE6,0x9B,0xB4,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_skill_chg  = cnp 0 (@(0xE6,0x8A,0x80,0xE8,0x83,0xBD,0xE5,0x8F,0x98,0xE6,0x9B,0xB4,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_script_gov = cnp 0 (@(0xE8,0x84,0x9A,0xE6,0x9C,0xAC,0xE6,0xB2,0xBB,0xE7,0x90,0x86,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_lessons    = cnp 0 (@(0xE6,0x95,0x99,0xE8,0xAE,0xAD,0xE5,0xBA,0x93))
$S_index      = cnp 0 (@(0xE7,0xB4,0xA2,0xE5,0xBC,0x95))
$S_anomaly    = cnp 0 (@(0xE8,0xA7,0x84,0xE8,0x8C,0x83,0xE5,0x8C,0x96,0xE5,0xBC,0x82,0xE5,0xB8,0xB8))
$S_migration  = cnp 0 (@(0xE8,0xA7,0x84,0xE8,0x8C,0x83,0xE5,0x8C,0x96,0xE8,0xBF,0x81,0xE7,0xA7,0xBB))

$projectSubFolderSpecs = @(
    @{ Prefix = "01"; Title = "问题答疑"; Stem = "01_问题答疑" },
    @{ Prefix = "02"; Title = "课题研究"; Stem = "02_课题研究" },
    @{ Prefix = "03"; Title = "代码程序"; Stem = "03_代码程序" }
)

function move-extra($src, $dstRel) {
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $base = Join-Path $wn ".temp\$($S_anomaly)_$ts"
    $target = Join-Path $base $dstRel
    $pDir = Split-Path $target -Parent
    if (-not (Test-Path $pDir)) { New-Item -ItemType Directory -Path $pDir -Force | Out-Null }
    if (Test-Path $src) {
        Move-Item $src $target -Force
        $script:fixLog += "Moved: $src -> $target"
        Write-Host "  [FIXED] Moved to $($target.Substring($wn.Length+1))"
    }
}

function archive-migrated($src, $dstRel) {
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $base = Join-Path $wn ".temp\$($S_migration)_$ts"
    $target = Join-Path $base $dstRel
    $pDir = Split-Path $target -Parent
    if (-not (Test-Path $pDir)) { New-Item -ItemType Directory -Path $pDir -Force | Out-Null }
    if (Test-Path $src) {
        Move-Item $src $target -Force
        $script:fixLog += "Migrated archive: $src -> $target"
        Write-Host "  [FIXED] Archived migrated source to $($target.Substring($wn.Length+1))"
    }
}

function Read-Utf8Text($path) {
    return [System.IO.File]::ReadAllText($path, [System.Text.UTF8Encoding]::new($false))
}

function Get-TextFilesForGetContentEncodingCheck {
    $files = @()
    foreach ($rel in @("AGENTS.md", "CLAUDE.md")) {
        $p = Join-Path $wn $rel
        if (Test-Path -LiteralPath $p) { $files += (Get-Item -LiteralPath $p) }
    }

    foreach ($rel in @(".agents\rules", ".agents\skills", ".system\standards")) {
        $p = Join-Path $wn $rel
        if (Test-Path -LiteralPath $p) {
            $files += @(Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Extension -in @(".md", ".json", ".yaml", ".yml", ".ps1") })
        }
    }

    $outputRoot = Join-Path $wn "output"
    if (Test-Path -LiteralPath $outputRoot) {
        $coreProjects = @(Get-ChildItem -LiteralPath $outputRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^00_系统治理(_v\d+\.\d+\.\d+)?$' })
        foreach ($project in $coreProjects) {
            $codeDirs = @(Get-ChildItem -LiteralPath $project.FullName -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^03_代码程序(_v\d+\.\d+\.\d+)?$' })
            foreach ($codeDir in $codeDirs) {
                $templatesDir = Join-Path $codeDir.FullName "src\templates"
                if (Test-Path -LiteralPath $templatesDir) {
                    $files += @(Get-ChildItem -LiteralPath $templatesDir -Recurse -File -ErrorAction SilentlyContinue |
                        Where-Object { $_.Extension -in @(".md", ".json", ".yaml", ".yml", ".ps1") })
                }
            }
        }
    }

    return @($files | Sort-Object FullName -Unique)
}

function Get-GetContentWithoutEncodingIssues {
    $problems = @()
    foreach ($file in (Get-TextFilesForGetContentEncodingCheck)) {
        try {
            $lines = @(Get-Content -LiteralPath $file.FullName -Encoding UTF8)
        } catch {
            continue
        }
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $line = $lines[$i]
            $trimmed = $line.Trim()
            if ($trimmed -match '^(#|>|-|\||description:)') { continue }
            if ($trimmed -match '^(Write-Host|Write-Output)\b') { continue }
            if ($line -match '(^|[\s=\(@{;&|])Get-Content(\s|$)' -and $line -notmatch '-Encoding\b') {
                $rel = $file.FullName.Substring($wn.Length + 1)
                $problems += "${rel}:$($i + 1): $trimmed"
            }
        }
    }
    return $problems
}

function Get-FrontmatterValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ($content -notmatch "(?s)^---\s*\r?\n(?<fm>.*?)\r?\n---") { return $null }
    $frontmatter = $Matches["fm"]
    $pattern = "(?m)^$([regex]::Escape($Key)):\s*(?<value>.+?)\s*$"
    if ($frontmatter -match $pattern) {
        return $Matches["value"].Trim().Trim('"').Trim("'")
    }
    return $null
}

function Get-YamlScalarValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $pattern = "(?m)^\s*$([regex]::Escape($Key)):\s*(?<value>.+?)\s*$"
    if ($content -match $pattern) {
        return $Matches["value"].Trim().Trim('"').Trim("'")
    }
    return $null
}

function Get-SkillNamingContractProblems {
    param([string[]]$RegisteredSkills)

    $result = [ordered]@{
        BadFolderNames = @()
        MissingSkillMd = @()
        MissingYamlName = @()
        BadYamlName = @()
        MissingDescription = @()
        LongDescription = @()
        MissingOpenAiYaml = @()
        MissingDisplayName = @()
        BadDisplayName = @()
        MissingShortDescription = @()
        RegisteredMissingFolder = @()
        UnregisteredFolder = @()
    }

    $skillsDir = Join-Path $wn ".agents\skills"
    if (-not (Test-Path -LiteralPath $skillsDir)) { return $result }

    $skillNamePattern = '^[A-Z]\d{2}_[^\\/:*?"<>|]+$'
    $existingSkills = @(Get-ChildItem -LiteralPath $skillsDir -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name)
    $existingNames = @($existingSkills | ForEach-Object { $_.Name })

    foreach ($skill in $RegisteredSkills) {
        if ($existingNames -notcontains $skill) {
            $result.RegisteredMissingFolder += $skill
        }
    }

    foreach ($dir in $existingSkills) {
        $folderName = $dir.Name
        if ($folderName -notmatch $skillNamePattern) {
            $result.BadFolderNames += $folderName
        }
        if ($RegisteredSkills -notcontains $folderName) {
            $result.UnregisteredFolder += $folderName
        }

        $skillMd = Join-Path $dir.FullName "SKILL.md"
        if (-not (Test-Path -LiteralPath $skillMd)) {
            $result.MissingSkillMd += $folderName
            continue
        }

        $yamlName = Get-FrontmatterValue -Path $skillMd -Key "name"
        if ([string]::IsNullOrWhiteSpace($yamlName)) {
            $result.MissingYamlName += $folderName
        } elseif ($yamlName -ne $folderName) {
            $result.BadYamlName += "$folderName -> $yamlName"
        } elseif ($yamlName -notmatch $skillNamePattern) {
            $result.BadYamlName += "$folderName -> $yamlName"
        }

        $description = Get-FrontmatterValue -Path $skillMd -Key "description"
        if ([string]::IsNullOrWhiteSpace($description)) {
            $result.MissingDescription += $folderName
        } elseif ($description.Length -gt 100) {
            $result.LongDescription += "$folderName ($($description.Length))"
        }

        $openAiYaml = Join-Path $dir.FullName "agents\openai.yaml"
        if (-not (Test-Path -LiteralPath $openAiYaml)) {
            $result.MissingOpenAiYaml += $folderName
        } else {
            $displayName = Get-YamlScalarValue -Path $openAiYaml -Key "display_name"
            if ([string]::IsNullOrWhiteSpace($displayName)) {
                $result.MissingDisplayName += $folderName
            } elseif ($displayName -notmatch "^$([regex]::Escape($folderName))_v\d+\.\d+\.\d+$") {
                $result.BadDisplayName += "$folderName -> $displayName"
            }
            $shortDescription = Get-YamlScalarValue -Path $openAiYaml -Key "short_description"
            if ([string]::IsNullOrWhiteSpace($shortDescription)) {
                $result.MissingShortDescription += $folderName
            }
        }
    }

    return $result
}

function Write-Utf8BomText($path, $content) {
    [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($true))
}

function Get-SystemRecordSpecs() {
    return @(
        @{ Name = "$($S_rule_chg).md";   Title = "Rule 变更";  Desc = "Rule 文件的增删改历史" },
        @{ Name = "$($S_skill_chg).md";  Title = "Skill 变更"; Desc = "Skill 文件的增删改历史" },
        @{ Name = "$($S_script_gov).md"; Title = "脚本治理";   Desc = "脚本 bug、编码、编译、封装与修复过程" },
        @{ Name = "$($S_lessons).md";    Title = "教训库";     Desc = "跨领域教训、根因分析与纠偏规则" },
        @{ Name = "$($S_index).md";      Title = "索引";       Desc = "系统治理记录的索引入口" }
    )
}

function Ensure-SystemRecordFile($path, $title, $desc) {
    if (Test-Path $path) { return $false }
    $content = "# 系统记录 · $title`r`n`r`n> $desc，按时间追加。`r`n`r`n---`r`n"
    Write-Utf8BomText $path $content
    return $true
}

function Split-LegacySystemRecordBlocks($text) {
    $trimmed = if ($null -eq $text) { "" } else { $text.Trim() }
    if (-not $trimmed) { return @() }

    $matches = [regex]::Matches($trimmed, '(?ms)^##\s+\d{4}-\d{2}-\d{2}.*?(?=^##\s+\d{4}-\d{2}-\d{2}|\z)')
    if ($matches.Count -gt 0) {
        return @($matches | ForEach-Object { $_.Value.Trim() })
    }
    return @($trimmed)
}

function Get-LegacySystemRecordTargets($block) {
    $targets = @()
    if ($block -match '(?i)(rule|rules|规则|\.agents[\\/]+rules|direction-rules|filename-rules|memory-rules|version-control-rules)') {
        $targets += "$($S_rule_chg).md"
    }
    if ($block -match '(?i)(skill|skills|技能|\.agents[\\/]+skills|创建技能|子项目管理|安装技能|框架体检|版本控制备份|记忆管理|项目规范化|课题研究)') {
        $targets += "$($S_skill_chg).md"
    }
    if ($block -match '(?i)(script|脚本|\.ps1|\.py|\.exe|exe|编码|乱码|BOM|编译|打包|封装|dist|src|初始化工作区|normalize|backup|new_project|framework-check)') {
        $targets += "$($S_script_gov).md"
    }
    if ($block -match '(?i)(教训|根因|纠偏|踩坑|禁止|必须|以后|原则|经验|风险)') {
        $targets += "$($S_lessons).md"
    }
    if ($targets.Count -eq 0) {
        $targets += "$($S_lessons).md"
    }
    return @($targets | Select-Object -Unique)
}

function Append-LegacyBlockToTarget($targetPath, $block) {
    $cleanBlock = if ($null -eq $block) { "" } else { $block.Trim() }
    if (-not $cleanBlock) { return $false }

    $existing = if (Test-Path $targetPath) { Read-Utf8Text $targetPath } else { "" }
    if ($existing.Contains($cleanBlock)) { return $false }

    $entry = "`r`n<!-- migrated-from: rules-skills.md -->`r`n$cleanBlock`r`n`r`n---`r`n"
    [System.IO.File]::AppendAllText($targetPath, $entry, [System.Text.UTF8Encoding]::new($false))
    return $true
}

function Count-SystemRecordEntries($path) {
    if (-not (Test-Path $path)) { return 0 }
    $text = Read-Utf8Text $path
    return ([regex]::Matches($text, '(?m)^##\s+\d{4}-\d{2}-\d{2}')).Count
}

function Update-SystemRecordIndex($memSys) {
    $specs = Get-SystemRecordSpecs
    $content = "# 系统记录 · $S_index`r`n`r`n"
    $content += "> 系统治理记录的索引入口。详细记录按关注点拆分，正文不写入本文件。`r`n`r`n"
    $content += "- Rule 变更 → [$($S_rule_chg).md]($($S_rule_chg).md)（$(Count-SystemRecordEntries (Join-Path $memSys "$($S_rule_chg).md")) 条）`r`n"
    $content += "- Skill 变更 → [$($S_skill_chg).md]($($S_skill_chg).md)（$(Count-SystemRecordEntries (Join-Path $memSys "$($S_skill_chg).md")) 条）`r`n"
    $content += "- 脚本治理 → [$($S_script_gov).md]($($S_script_gov).md)（$(Count-SystemRecordEntries (Join-Path $memSys "$($S_script_gov).md")) 条）`r`n"
    $content += "- 教训库 → [$($S_lessons).md]($($S_lessons).md)（$(Count-SystemRecordEntries (Join-Path $memSys "$($S_lessons).md")) 条）`r`n`r`n"
    $content += "---`r`n`r`n> 新记录按分类追加到对应文件；旧 `rules-skills.md` 只能作为迁移源，迁移后归档。`r`n"
    Write-Utf8BomText (Join-Path $memSys "$($S_index).md") $content
}

function Migrate-LegacySystemRecord($legacyPath, $memSys) {
    $legacyText = Read-Utf8Text $legacyPath
    $blocks = Split-LegacySystemRecordBlocks $legacyText
    $appended = 0

    foreach ($spec in (Get-SystemRecordSpecs)) {
        Ensure-SystemRecordFile (Join-Path $memSys $spec.Name) $spec.Title $spec.Desc | Out-Null
    }

    foreach ($block in $blocks) {
        foreach ($targetName in (Get-LegacySystemRecordTargets $block)) {
            $targetPath = Join-Path $memSys $targetName
            if (Append-LegacyBlockToTarget $targetPath $block) {
                $appended++
            }
        }
    }

    Update-SystemRecordIndex $memSys
    archive-migrated $legacyPath ".memory/$($S_sys_rec)/rules-skills.md"
    Write-Host "  [FIXED] Migrated legacy rules-skills.md into classified system records ($appended appended entries)"
}

function Has-Mojibake($text) {
    if ($null -eq $text) { return $false }
    return ($text -match '[鐗璁椤杩椋宸浣绠妫鏌鍏鐭绯荤粺]')
}

function Get-ProjectTopic($folderName) {
    if ($folderName -match '^\d{2}_(.+)_v\d+\.\d+\.\d+$') { return $Matches[1] }
    if ($folderName -match '^\d{2}_(.+)$') { return $Matches[1] }
    return $folderName
}

function Get-MemoryVersion($text) {
    if ($text -match '<!--\s*memory-version:\s*(\d+)\.(\d+)\.(\d+)\s*-->') {
        return @{
            Text = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
            Major = [int]$Matches[1]
            Minor = [int]$Matches[2]
            Patch = [int]$Matches[3]
        }
    }
    return @{
        Text = "1.0.0"
        Major = 1
        Minor = 0
        Patch = 0
    }
}

function Ensure-ProjectSnapshot($projectDir) {
    $name = Split-Path $projectDir -Leaf
    if ($script:snapshottedProjects.ContainsKey($name)) { return }
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $histOut = Join-Path $wn ".history\output"
    if (-not (Test-Path $histOut)) { New-Item -ItemType Directory -Path $histOut -Force | Out-Null }
    $snapshot = Join-Path $histOut "${name}_$ts"
    Copy-Item -LiteralPath $projectDir -Destination $snapshot -Recurse -Force
    $script:snapshottedProjects[$name] = $snapshot
    $script:fixLog += "Snapshot: $projectDir -> $snapshot"
    Write-Host "  [FIXED] Snapshot before project normalization: $($snapshot.Substring($wn.Length+1))"
}

function Get-ProjectRootContentFiles($projectDir) {
    $fixed = @("$S_mulu.md", "$S_ver_log.md")
    return @(Get-ChildItem -LiteralPath $projectDir -File -ErrorAction SilentlyContinue |
        Where-Object { $fixed -notcontains $_.Name } |
        Sort-Object CreationTime, Name)
}

function Get-ProjectRootPayloadFiles($projectDir) {
    $fixed = @("$S_mulu.md", "$S_ver_log.md")
    return @(Get-ChildItem -LiteralPath $projectDir -File -ErrorAction SilentlyContinue |
        Where-Object { $fixed -notcontains $_.Name } |
        Sort-Object Name)
}

function Get-SubFolderContentFiles($subDir) {
    if (-not (Test-Path -LiteralPath $subDir)) { return @() }
    return @(Get-ChildItem -LiteralPath $subDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne ".gitkeep" } |
        Sort-Object CreationTime, Name)
}

function Get-ProjectSubFolderMatches($projectDir, $spec) {
    $legacyPattern = "^$([regex]::Escape($spec.Stem))_v\d+\.\d+\.\d+$"
    return @(Get-ChildItem -LiteralPath $projectDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $spec.Stem -or $_.Name -match $legacyPattern } |
        Sort-Object @{ Expression = { if ($_.Name -eq $spec.Stem) { 0 } else { 1 } } }, Name)
}

function Get-ProjectSubFolderVersion($folderName, $spec) {
    $pattern = "^$([regex]::Escape($spec.Stem))_v(\d+\.\d+\.\d+)$"
    if ($folderName -match $pattern) { return $Matches[1] }
    return ""
}

function Get-SubFolderPayloadItems($subDir) {
    if (-not (Test-Path -LiteralPath $subDir)) { return @() }
    return @(Get-ChildItem -LiteralPath $subDir -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne ".gitkeep" } |
        Sort-Object PSIsContainer, CreationTime, Name)
}

function Get-ExpectedSubFolderVersion($subDir) {
    $folderName = Split-Path $subDir -Leaf
    if ($folderName -match '^03_代码程序_v') {
        $items = Get-SubFolderPayloadItems $subDir
        if ($items.Count -eq 0) { return "0.0.0" }
    } else {
        $files = Get-SubFolderContentFiles $subDir
        if ($files.Count -eq 0) { return "0.0.0" }
    }
    if ($folderName -match '_v(\d+\.\d+\.\d+)$' -and $Matches[1] -ne "0.0.0") {
        return $Matches[1]
    }
    return "1.0.0"
}

function Get-ExpectedSubFolderName($spec, $version) {
    return $spec.Stem
}

function Test-StructuredProject($projectDir) {
    $rootPayloadFiles = Get-ProjectRootPayloadFiles $projectDir
    $rootPayloadDirs = @(Get-ChildItem -LiteralPath $projectDir -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $dirName = $_.Name
            -not ($projectSubFolderSpecs | Where-Object {
                $dirName -eq $_.Stem -or $dirName -match "^$([regex]::Escape($_.Stem))_v\d+\.\d+\.\d+$"
            })
        })
    $subFolderCount = 0
    foreach ($spec in $projectSubFolderSpecs) {
        $subFolderCount += (Get-ProjectSubFolderMatches $projectDir $spec).Count
    }
    return ($subFolderCount -gt 0 -or ($rootPayloadFiles.Count -eq 0 -and $rootPayloadDirs.Count -eq 0))
}

function Ensure-StructuredSubFolders($projectDir) {
    foreach ($spec in $projectSubFolderSpecs) {
        $matches = Get-ProjectSubFolderMatches $projectDir $spec
        if ($matches.Count -eq 0) {
            $newName = Get-ExpectedSubFolderName $spec "0.0.0"
            $newPath = Join-Path $projectDir $newName
            New-Item -ItemType Directory -Path $newPath -Force | Out-Null
            Write-Host "  [FIXED] Created sub-folder: $((Split-Path $projectDir -Leaf))/$newName"
            continue
        }

        $primary = $matches[0]
        $expectedVersion = Get-ExpectedSubFolderVersion $primary.FullName
        $expectedName = Get-ExpectedSubFolderName $spec $expectedVersion
        if ($primary.Name -ne $expectedName) {
            $target = Join-Path $projectDir $expectedName
            if (-not (Test-Path -LiteralPath $target)) {
                Rename-Item -LiteralPath $primary.FullName -NewName $expectedName -Force
                Write-Host "  [FIXED] Renamed sub-folder: $($primary.Name) -> $expectedName"
            } else {
                Write-Host "  [WARN] Cannot rename $($primary.Name); target exists: $expectedName"
                $script:warnings++
            }
        }
    }
}

function Get-SubFolderSpecByPrefix($prefix) {
    return ($projectSubFolderSpecs | Where-Object { $_.Prefix -eq $prefix } | Select-Object -First 1)
}

function Get-ProjectSubFolderByPrefix($projectDir, $prefix) {
    $spec = Get-SubFolderSpecByPrefix $prefix
    if ($null -eq $spec) { return $null }
    $matches = Get-ProjectSubFolderMatches $projectDir $spec
    if ($matches.Count -gt 0) { return $matches[0] }
    return $null
}

function Get-TargetSubFolderSpecForRootFile($file) {
    $codeExts = @(".ps1", ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".bat", ".cmd", ".sh", ".sql", ".ipynb")
    $ext = $file.Extension.ToLowerInvariant()
    if ($codeExts -contains $ext) { return (Get-SubFolderSpecByPrefix "03") }

    if ($file.Name -match '(问题|答疑|问答|提问|回答|FAQ|faq|Q&A)') {
        return (Get-SubFolderSpecByPrefix "01")
    }

    return (Get-SubFolderSpecByPrefix "02")
}

function Get-NextContentNumber($targetDir) {
    $nums = @(Get-SubFolderContentFiles $targetDir | ForEach-Object {
        if ($_.Name -match '^(\d{2})_') { [int]$Matches[1] }
    })
    if ($nums.Count -eq 0) { return 1 }
    return (($nums | Sort-Object -Descending | Select-Object -First 1) + 1)
}

function Ensure-VersionedContentFileName($fileName) {
    return $fileName
}

function Get-NormalizedContentFileName($file, $targetDir, $targetSpec) {
    $candidate = $file.Name
    if ($targetSpec.Prefix -ne "03") {
        $candidate = Ensure-VersionedContentFileName $candidate
    }
    $candidatePath = Join-Path $targetDir $candidate
    if ($candidate -match '^\d{2}_' -and -not (Test-Path -LiteralPath $candidatePath)) {
        return $candidate
    }

    $ext = [System.IO.Path]::GetExtension($candidate)
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($candidate)
    $stem = $stem -replace '^\d{2}_', ''
    if ($targetSpec.Prefix -ne "03") {
        $stem = $stem -replace '_v\d+\.\d+\.\d+$', ''
    }
    if ([string]::IsNullOrWhiteSpace($stem)) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    }

    $next = Get-NextContentNumber $targetDir
    do {
        $newName = ("{0:D2}_" -f $next) + $stem
        $newName += $ext
        $newPath = Join-Path $targetDir $newName
        $next++
    } while (Test-Path -LiteralPath $newPath)
    return $newName
}

function Move-RootPayloadFilesToSubFolders($projectDir) {
    $files = Get-ProjectRootContentFiles $projectDir
    $moved = 0
    foreach ($f in $files) {
        $spec = Get-TargetSubFolderSpecForRootFile $f
        if ($null -eq $spec) { continue }
        $targetSubDir = Get-ProjectSubFolderByPrefix $projectDir $spec.Prefix
        if ($null -eq $targetSubDir) {
            $newPath = Join-Path $projectDir (Get-ExpectedSubFolderName $spec "0.0.0")
            New-Item -ItemType Directory -Path $newPath -Force | Out-Null
            $targetSubDir = Get-Item -LiteralPath $newPath
        }

        $newName = Get-NormalizedContentFileName $f $targetSubDir.FullName $spec
        $newPath = Join-Path $targetSubDir.FullName $newName
        Move-Item -LiteralPath $f.FullName -Destination $newPath -Force
        Write-Host "  [FIXED] Moved root content: $($f.Name) -> $($targetSubDir.Name)/$newName"
        $moved++
    }
    return $moved
}

function Build-LegacyCatalogContent($projectDir) {
    $topic = Get-ProjectTopic (Split-Path $projectDir -Leaf)
    $rows = @()
    $files = Get-ProjectRootContentFiles $projectDir
    foreach ($f in $files) {
        $num = ""
        if ($f.Name -match '^(\d{2})_') { $num = $Matches[1] }
        $created = Get-Date $f.CreationTime -Format "yyyy-MM-dd"
        $modified = Get-Date $f.LastWriteTime -Format "yyyy-MM-dd"
        $rows += "| $num | [$($f.Name)](./$($f.Name)) | | $created | $modified |"
    }
    $content = "# $S_mulu · $topic`r`n`r`n> 本子项目内所有内容文件的索引。`r`n`r`n"
    $content += "| # | 文件 | 说明 | 首次落盘 | 最近更新 |`r`n|---|------|------|---------|---------|`r`n"
    if ($rows.Count -gt 0) { $content += ($rows -join "`r`n") + "`r`n" }
    else { $content += "| 待新增文件后填写 | | | | |`r`n" }
    return $content
}

function Build-StructuredCatalogContent($projectDir) {
    $topic = Get-ProjectTopic (Split-Path $projectDir -Leaf)
    $content = "# $S_mulu · $topic`r`n`r`n> 本子项目内所有内容文件的索引，按三个子文件夹分节列出。`r`n`r`n---`r`n"

    foreach ($spec in $projectSubFolderSpecs) {
        $matches = Get-ProjectSubFolderMatches $projectDir $spec
        $subDir = if ($matches.Count -gt 0) { $matches[0] } else { $null }
        $content += "`r`n## $($spec.Stem)`r`n`r`n"
        $content += "| # | 文件 | 说明 | 首次落盘 | 最近更新 |`r`n|---|------|------|---------|---------|`r`n"

        if ($null -eq $subDir) {
            $content += "| 待新增文件后填写 | | | | |`r`n`r`n---`r`n"
            continue
        }

        $rows = @()
        foreach ($f in (Get-SubFolderContentFiles $subDir.FullName)) {
            $num = ""
            if ($f.Name -match '^(\d{2})_') { $num = $Matches[1] }
            $created = Get-Date $f.CreationTime -Format "yyyy-MM-dd"
            $modified = Get-Date $f.LastWriteTime -Format "yyyy-MM-dd"
            $rel = "./$($subDir.Name)/$($f.Name)"
            $rows += "| $num | [$($f.Name)]($rel) | | $created | $modified |"
        }

        if ($rows.Count -gt 0) { $content += ($rows -join "`r`n") + "`r`n" }
        else { $content += "| 待新增文件后填写 | | | | |`r`n" }
        $content += "`r`n---`r`n"
    }

    return $content
}

function Build-CatalogContent($projectDir) {
    return (Build-StructuredCatalogContent $projectDir)
}

function Ensure-VersionRecord($projectDir) {
    $topic = Get-ProjectTopic (Split-Path $projectDir -Leaf)
    $path = Join-Path $projectDir "$S_ver_log.md"
    if (Test-Path $path) { return }
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $content = "# $S_ver_log · $topic`r`n`r`n> 记录子项目的版本变更历史。`r`n`r`n---`r`n`r`n"
    $content += "## 规范化补建 ($now)`r`n`r`n**变更类型**：PATCH`r`n**变更描述**：老项目迁移时补建版本记录。`r`n`r`n---`r`n"
    Write-Utf8BomText $path $content
    Write-Host "  [FIXED] Created: $((Join-Path (Split-Path $projectDir -Leaf) "$S_ver_log.md"))"
}

function Normalize-ProjectInternals($projectDir) {
    Ensure-ProjectSnapshot $projectDir

    Ensure-StructuredSubFolders $projectDir
    $moved = Move-RootPayloadFilesToSubFolders $projectDir
    if ($moved -gt 0) {
        Ensure-StructuredSubFolders $projectDir
    }
    $catalogPath = Join-Path $projectDir "$S_mulu.md"
    Write-Utf8BomText $catalogPath (Build-CatalogContent $projectDir)
    Write-Host "  [FIXED] Updated structured catalog: $((Join-Path (Split-Path $projectDir -Leaf) "$S_mulu.md"))"
    Ensure-VersionRecord $projectDir
}

function Repair-GlobalKnowledgeMap($mapPath, $outputDirs) {
    $oldText = if (Test-Path $mapPath) { Read-Utf8Text $mapPath } else { "" }
    $oldVersion = Get-MemoryVersion $oldText
    if (Test-Path $mapPath) {
        $histDir = Join-Path $wn ".history\.memory\$S_map"
        if (-not (Test-Path $histDir)) { New-Item -ItemType Directory -Path $histDir -Force | Out-Null }
        Copy-Item -LiteralPath $mapPath -Destination (Join-Path $histDir "$($S_map)_v$($oldVersion.Text).md") -Force
    }

    $rowInfo = @{}
    foreach ($line in ($oldText -split "`r?`n")) {
        if ($line -match '^\|') {
            $cells = @($line.Trim('|') -split '\|' | ForEach-Object { $_.Trim() })
            if ($cells.Count -ge 5 -and $cells[1] -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$' -and -not (Has-Mojibake $line)) {
                $rowInfo[$cells[1]] = @{ Date = $cells[2]; Status = $cells[3]; Core = $cells[4] }
            }
        }
    }

    $newVersion = "$($oldVersion.Major).$($oldVersion.Minor + 1).0"
    $content = "<!-- memory-version: $newVersion -->`r`n# $S_map`r`n`r`n"
    $content += "> 所有研究子项目的总索引，新建子项目时自动更新。`r`n`r`n"
    $content += "| 话题 | 子项目文件夹 | 创建时间 | 状态 | 核心结论（一句话） |`r`n"
    $content += "|------|------------|---------|------|----------------|`r`n"
    foreach ($d in ($outputDirs | Sort-Object Name)) {
        $topic = Get-ProjectTopic $d.Name
        if ($rowInfo.ContainsKey($d.Name)) {
            $created = $rowInfo[$d.Name].Date
            $status = $rowInfo[$d.Name].Status
            $core = $rowInfo[$d.Name].Core
        } else {
            $created = Get-Date $d.CreationTime -Format "yyyy-MM-dd"
            $status = "进行中"
            $core = "-"
        }
        $content += "| $topic | $($d.Name) | $created | $status | $core |`r`n"
    }
    Write-Utf8BomText $mapPath $content
    Write-Host "  [FIXED] Rebuilt: .memory/$($S_map).md"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Project Normalization"
Write-Host "  Workspace: $wn"
Write-Host "  Mode: $(if($Fix){'Fix'}else{'Check'})"
Write-Host "========================================"
Write-Host ""

# ========== Check 1: Root directories ==========
Write-Host "--- 1. Root Directories ---"
$rootDirs = if ($workspaceSpec) { @($workspaceSpec.rootDirectories) } else { @(".agents", ".history", ".memory", ".system", ".temp", "input", "output") }
$missingRoot = @()
foreach ($d in $rootDirs) {
    $p = Join-Path $wn $d
    if (-not (Test-Path $p)) { $missingRoot += $d }
}
if ($missingRoot.Count -eq 0) {
    Write-Host "  [PASS] All $($rootDirs.Count) root directories exist"
    $passes++
} else {
    foreach ($m in $missingRoot) {
        Write-Host "  [FAIL] Missing: $m/"
        $issues++
    }
    if ($Fix) {
        foreach ($m in $missingRoot) {
            $p = Join-Path $wn $m
            New-Item -ItemType Directory -Path $p -Force | Out-Null
            Write-Host "  [FIXED] Created: $m/"
        }
    }
}

# ========== Check 2: .agents/ ==========
Write-Host ""
Write-Host "--- 2. .agents/ Structure ---"
$agents = Join-Path $wn ".agents"
if (Test-Path $agents) {
    $requiredSkills = if ($workspaceSpec) { @($workspaceSpec.overwriteLayer.skills) } else { @("A01_创建技能","B04_子项目管理","A02_安装技能","B01_框架体检","B02_版本控制备份","B03_记忆管理","B06_项目规范化","B05_课题研究") }
    $registeredSkills = if ($workspaceSpec -and $workspaceSpec.skillsManagement -and $workspaceSpec.skillsManagement.registeredSkills) { @($workspaceSpec.skillsManagement.registeredSkills) } else { $requiredSkills }
    $skillsDir = Join-Path $agents "skills"
    $rulesDir = Join-Path $agents "rules"
    $requiredRules = if ($workspaceSpec) { @($workspaceSpec.overwriteLayer.rules) } else { @("direction-rules.md","filename-rules.md","memory-rules.md","version-control-rules.md") }

    if (-not (Test-Path $rulesDir)) {
        Write-Host "  [FAIL] Missing: .agents/rules/"
        $issues++
        if ($Fix) { New-Item -ItemType Directory -Path $rulesDir -Force | Out-Null; Write-Host "  [FIXED] Created: .agents/rules/" }
    } else {
        foreach ($r in $requiredRules) {
            $rp = Join-Path $rulesDir $r
            if (-not (Test-Path $rp)) {
                Write-Host "  [FAIL] Missing rule: rules/$r"
                $issues++
            } else { Write-Host "  [PASS] rules/$r"; $passes++ }
        }
    }

    if (-not (Test-Path $skillsDir)) {
        Write-Host "  [FAIL] Missing: .agents/skills/"
        $issues++
        if ($Fix) { New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null; Write-Host "  [FIXED] Created: .agents/skills/" }
    } else {
        $existingSkills = Get-ChildItem $skillsDir -Directory | ForEach-Object { $_.Name }
        foreach ($s in $requiredSkills) {
            if ($existingSkills -notcontains $s) {
                Write-Host "  [FAIL] Missing skill: skills/$s/"
                $issues++
                if ($Fix) {
                    Write-Host "  [NEEDS TEMPLATE] Cannot synthesize skills/$s/. Run the latest init EXE first, then run normalization again."
                }
            } else { Write-Host "  [PASS] skills/$s/"; $passes++ }
        }
        # Check extra skills
        foreach ($es in $existingSkills) {
            if ($registeredSkills -notcontains $es) {
                Write-Host "  [WARN] Extra skill: skills/$es/"
                $warnings++
                if ($Fix) { move-extra (Join-Path $skillsDir $es) ".agents/skills/$es" }
            }
        }
        # SKILL.md in each
        foreach ($s in $existingSkills) {
            $sp = Join-Path $skillsDir "$s\SKILL.md"
            if ((Test-Path (Join-Path $skillsDir $s)) -and -not (Test-Path $sp)) {
                Write-Host "  [WARN] No SKILL.md in: skills/$s/"
                $warnings++
            }
        }

        $skillNamingProblems = Get-SkillNamingContractProblems -RegisteredSkills $registeredSkills
        foreach ($item in $skillNamingProblems.BadFolderNames) { Write-Host "  [FAIL] Bad Skill folder name: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingSkillMd) { Write-Host "  [FAIL] Missing SKILL.md: skills/$item/"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingYamlName) { Write-Host "  [FAIL] Missing YAML name: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.BadYamlName) { Write-Host "  [FAIL] YAML name must equal folder name: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingDescription) { Write-Host "  [FAIL] Missing YAML description: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.LongDescription) { Write-Host "  [FAIL] YAML description exceeds 100 chars: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingOpenAiYaml) { Write-Host "  [FAIL] Missing agents/openai.yaml: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingDisplayName) { Write-Host "  [FAIL] Missing OpenAI display_name: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.BadDisplayName) { Write-Host "  [FAIL] OpenAI display_name must equal folder name plus version: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.MissingShortDescription) { Write-Host "  [FAIL] Missing OpenAI short_description: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.RegisteredMissingFolder) { Write-Host "  [FAIL] Registered Skill missing folder: $item"; $issues++ }
        foreach ($item in $skillNamingProblems.UnregisteredFolder) { Write-Host "  [FAIL] Skill folder not registered: $item"; $issues++ }
        if ($skillNamingProblems.BadFolderNames.Count -eq 0 -and
            $skillNamingProblems.MissingSkillMd.Count -eq 0 -and
            $skillNamingProblems.MissingYamlName.Count -eq 0 -and
            $skillNamingProblems.BadYamlName.Count -eq 0 -and
            $skillNamingProblems.MissingDescription.Count -eq 0 -and
            $skillNamingProblems.LongDescription.Count -eq 0 -and
            $skillNamingProblems.MissingOpenAiYaml.Count -eq 0 -and
            $skillNamingProblems.MissingDisplayName.Count -eq 0 -and
            $skillNamingProblems.BadDisplayName.Count -eq 0 -and
            $skillNamingProblems.MissingShortDescription.Count -eq 0 -and
            $skillNamingProblems.RegisteredMissingFolder.Count -eq 0 -and
            $skillNamingProblems.UnregisteredFolder.Count -eq 0) {
            Write-Host "  [PASS] Skill naming contract"
            $passes++
        } elseif ($Fix) {
            Write-Host "  [NEEDS MANUAL] Skill naming contract issues require explicit rename/register edits."
        }
    }
} else {
    Write-Host "  [FAIL] .agents/ missing (covered by check #1)"
    $issues++
}

# ========== Check 2b: .claude/ ========== 
Write-Host ""
Write-Host "--- 2b. .claude Integration ---"
if ($workspaceSpec -and $workspaceSpec.claudeIntegration) {
    $claudeSpec = $workspaceSpec.claudeIntegration
    $registeredSkillsForClaude = if ($workspaceSpec.skillsManagement -and $workspaceSpec.skillsManagement.registeredSkills) {
        @($workspaceSpec.skillsManagement.registeredSkills)
    } elseif ($workspaceSpec.overwriteLayer -and $workspaceSpec.overwriteLayer.skills) {
        @($workspaceSpec.overwriteLayer.skills)
    } else {
        @()
    }

    $guideRel = [string]$claudeSpec.guideFile
    $localConfigRel = [string]$claudeSpec.localConfigFile
    $settingsRel = [string]$claudeSpec.settingsFile
    $cmdDirRel = [string]$claudeSpec.commandsDirectory
    $cmdTemplate = [string]$claudeSpec.commandTemplate
    if ([string]::IsNullOrWhiteSpace($cmdTemplate)) {
        $cmdTemplate = "请读取并执行 .agents/skills/{skill}/SKILL.md"
    }

    $cmdDir = Join-Path $wn ($cmdDirRel -replace '/', '\')
    if (-not (Test-Path $cmdDir)) {
        Write-Host "  [FAIL] Missing: $cmdDirRel/"
        $issues++
        if ($Fix) {
            New-Item -ItemType Directory -Path $cmdDir -Force | Out-Null
            Write-Host "  [FIXED] Created: $cmdDirRel/"
        }
    } else {
        Write-Host "  [PASS] $cmdDirRel/"
        $passes++
    }

    foreach ($rel in @($guideRel, $localConfigRel, $settingsRel)) {
        if ([string]::IsNullOrWhiteSpace($rel)) { continue }
        $p = Join-Path $wn ($rel -replace '/', '\')
        if (-not (Test-Path $p)) {
            Write-Host "  [FAIL] Missing: $rel"
            $issues++
            if ($Fix) {
                $parent = Split-Path $p -Parent
                if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
                if ($rel -eq $localConfigRel) {
                    [System.IO.File]::WriteAllText($p, "{`r`n  `"env`": {},`r`n  `"hasCompletedOnboarding`": true`r`n}`r`n", [System.Text.UTF8Encoding]::new($false))
                    Write-Host "  [FIXED] Created private placeholder: $rel"
                } elseif ($rel -eq $settingsRel) {
                    [System.IO.File]::WriteAllText($p, "{`r`n  `"permissions`": {`r`n    `"allow`": []`r`n  }`r`n}`r`n", [System.Text.UTF8Encoding]::new($false))
                    Write-Host "  [FIXED] Created local settings placeholder: $rel"
                } else {
                    Write-Host "  [NEEDS SOURCE] $rel is a managed Claude guide and cannot be synthesized by normalization."
                }
            }
        } else {
            Write-Host "  [PASS] $rel"
            $passes++
        }
    }

    if (Test-Path $cmdDir) {
        $missingCommands = @()
        $badCommands = @()
        foreach ($skill in $registeredSkillsForClaude) {
            $cmdPath = Join-Path $cmdDir "$skill.md"
            $expected = $cmdTemplate.Replace("{skill}", $skill)
            if (-not (Test-Path $cmdPath)) {
                $missingCommands += $skill
                if ($Fix) {
                    [System.IO.File]::WriteAllText($cmdPath, $expected + "`r`n", [System.Text.UTF8Encoding]::new($false))
                    Write-Host "  [FIXED] Created Claude command: $skill.md"
                }
                continue
            }
            $actual = (Get-Content $cmdPath -Raw -Encoding UTF8).Trim()
            if ($actual -ne $expected) {
                $badCommands += $skill
                if ($Fix) {
                    [System.IO.File]::WriteAllText($cmdPath, $expected + "`r`n", [System.Text.UTF8Encoding]::new($false))
                    Write-Host "  [FIXED] Rewrote Claude command: $skill.md"
                }
            }
        }
        if (-not $Fix) {
            foreach ($m in $missingCommands) { Write-Host "  [FAIL] Missing Claude command: $m.md"; $issues++ }
            foreach ($b in $badCommands) { Write-Host "  [FAIL] Bad Claude command body: $b.md"; $issues++ }
        }

        $existingCommands = @(Get-ChildItem $cmdDir -Filter "*.md" -File -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
        $expectedCommands = @($registeredSkillsForClaude | ForEach-Object { "$_.md" })
        $extraCommands = $existingCommands | Where-Object { $_ -notin $expectedCommands }
        foreach ($e in $extraCommands) {
            Write-Host "  [WARN] Extra Claude command: $e"
            $warnings++
            if ($Fix) { move-extra (Join-Path $cmdDir $e) "$cmdDirRel/$e" }
        }

        if ($missingCommands.Count -eq 0 -and $badCommands.Count -eq 0) {
            Write-Host "  [PASS] Claude commands match registered skills ($($registeredSkillsForClaude.Count))"
            $passes++
        }
    }
} else {
    Write-Host "  [WARN] No claudeIntegration block in workspace-spec.json"
    $warnings++
}
# ========== Check 3: output/ ==========

Write-Host ""
Write-Host "--- 3. output/ Structure ---"
$out = Join-Path $wn "output"
if (Test-Path $out) {
    $outItems = Get-ChildItem $out -ErrorAction SilentlyContinue
    $outFiles = @($outItems | Where-Object { -not $_.PSIsContainer })
    $outDirs = @($outItems | Where-Object { $_.PSIsContainer })

    if ($outFiles.Count -gt 0) {
        foreach ($f in $outFiles) {
            Write-Host "  [FAIL] Loose file in output/: $($f.Name)"
            $issues++
            if ($Fix) { move-extra $f.FullName "output/$($f.Name)" }
        }
    }

    foreach ($d in $outDirs) {
        if ($d.Name -notmatch '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$') {
            Write-Host "  [FAIL] Bad naming: $($d.Name)"
            $issues++
            if ($Fix) { move-extra $d.FullName "output/$($d.Name)" }
        } else { Write-Host "  [PASS] $($d.Name)"; $passes++ }
    }

    Write-Host ""
    Write-Host "--- 3b. output/ Project Internals ---"
    foreach ($d in $outDirs | Where-Object { $_.Name -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$' }) {
        $catalogPath = Join-Path $d.FullName "$S_mulu.md"
        $versionPath = Join-Path $d.FullName "$S_ver_log.md"
        $rootContentFiles = Get-ProjectRootContentFiles $d.FullName
        $isStructured = Test-StructuredProject $d.FullName
        $needsProjectFix = $false

        if (-not (Test-Path $catalogPath)) {
            Write-Host "  [FAIL] Missing $S_mulu.md: $($d.Name)"
            $issues++
            $needsProjectFix = $true
        }
        if (-not (Test-Path $versionPath)) {
            Write-Host "  [FAIL] Missing $S_ver_log.md: $($d.Name)"
            $issues++
            $needsProjectFix = $true
        }

        if ($isStructured) {
            $catalogText = if (Test-Path $catalogPath) { Read-Utf8Text $catalogPath } else { "" }
            foreach ($spec in $projectSubFolderSpecs) {
                $matches = Get-ProjectSubFolderMatches $d.FullName $spec
                if ($matches.Count -eq 0) {
                    Write-Host "  [FAIL] Missing sub-folder $($spec.Stem): $($d.Name)"
                    $issues++
                    $needsProjectFix = $true
                    continue
                }
                if ($matches.Count -gt 1) {
                    Write-Host "  [WARN] Duplicate sub-folder $($spec.Stem): $($d.Name)"
                    $warnings++
                }

                $primary = $matches[0]
                $actualVersion = Get-ProjectSubFolderVersion $primary.Name $spec
                $expectedVersion = Get-ExpectedSubFolderVersion $primary.FullName
                if ($actualVersion -and $actualVersion -ne $expectedVersion) {
                    Write-Host "  [WARN] Sub-folder version should be v${expectedVersion}: $($d.Name)/$($primary.Name)"
                    $warnings++
                    $needsProjectFix = $true
                }

                if ($catalogText -notmatch "##\s+$([regex]::Escape($spec.Stem))") {
                    Write-Host "  [WARN] $S_mulu.md missing section: $($spec.Stem) in $($d.Name)"
                    $warnings++
                    $needsProjectFix = $true
                }

                if ($spec.Prefix -ne "03") {
                    $unnumbered = @(Get-SubFolderContentFiles $primary.FullName |
                        Where-Object { $_.Name -notmatch '^\d{2}_' })
                    if ($unnumbered.Count -gt 0) {
                        Write-Host "  [WARN] Unnumbered files in $($d.Name)/$($primary.Name): $($unnumbered.Count)"
                        $warnings++
                    }

                }
            }

            if ($rootContentFiles.Count -gt 0) {
                Write-Host "  [WARN] Legacy root content remains outside sub-folders in $($d.Name): $($rootContentFiles.Count)"
                $warnings++
            }
        } else {
            $unnumbered = @($rootContentFiles | Where-Object { $_.Name -notmatch '^\d{2}_' })
            if ($unnumbered.Count -gt 0) {
                Write-Host "  [WARN] Unnumbered legacy content files in $($d.Name): $($unnumbered.Count)"
                $warnings++
                $needsProjectFix = $true
            }
        }

        if (-not $needsProjectFix) {
            Write-Host "  [PASS] $($d.Name) internals"
            $passes++
        } elseif ($Fix) {
            Normalize-ProjectInternals $d.FullName
        }
    }
    # 3c. Core subproject 00_系统治理
    Write-Host ""
    Write-Host "--- 3c. Core Subproject (00_系统治理) ---"
    $coreMatches = @(Get-ChildItem $out -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^00_系统治理(_v\d+\.\d+\.\d+)?$' })
    if ($coreMatches.Count -eq 0) {
        Write-Host "  [FAIL] Core subproject 00_系统治理 not found in output/"
        $issues++
        if ($Fix) {
            $coreDir = Join-Path $out "00_系统治理"
            New-Item -ItemType Directory -Path (Join-Path $coreDir "01_问题答疑") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $coreDir "02_课题研究") -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $coreDir "03_代码程序") -Force | Out-Null
            $now = Get-Date -Format "yyyy-MM-dd"
            $catalogContent = "# $S_mulu · 系统治理`r`n`r`n> 核心骨架子项目，用于记录工作区治理决策、规则变更、Skill 升级等系统性内容。`r`n`r`n---`r`n`r`n## 01_问题答疑`r`n`r`n| # | 文件 | 说明 | 首次落盘 | 最近更新 |`r`n|---|------|------|---------|---------|`r`n`r`n## 02_课题研究`r`n`r`n| # | 文件 | 说明 | 首次落盘 | 最近更新 |`r`n|---|------|------|---------|---------|`r`n`r`n## 03_代码程序`r`n`r`n| # | 文件 | 说明 | 首次落盘 | 最近更新 |`r`n|---|------|------|---------|---------|`r`n"
            Write-Utf8BomText (Join-Path $coreDir "$S_mulu.md") $catalogContent
            $verContent = "# $S_ver_log · 系统治理`r`n`r`n> 核心骨架子项目的版本变更历史。`r`n`r`n---`r`n`r`n## v1.0.0 ($now)`r`n`r`n**变更类型**：MAJOR`r`n**变更描述**：由项目规范化 --Fix 自动创建核心骨架子项目。`r`n`r`n---`r`n"
            Write-Utf8BomText (Join-Path $coreDir "$S_ver_log.md") $verContent
            Write-Host "  [FIXED] Created core subproject: output/00_系统治理"
        }
    } else {
        Write-Host "  [PASS] Core subproject: $($coreMatches[0].Name)"
        $passes++
    }
} else {
    Write-Host "  [FAIL] output/ missing (covered by check #1)"
    $issues++
}

# ========== Check 4: .memory/ ==========
Write-Host ""
Write-Host "--- 4. .memory/ Structure ---"
$mem = Join-Path $wn ".memory"
if (Test-Path $mem) {
    $memConv = Join-Path $mem $S_conv
    $memSys  = Join-Path $mem $S_sys_rec
    $memKnow = Join-Path $mem $S_knowledge
    $memMap  = Join-Path $mem "$($S_map).md"

    # Subdirs
    @($memConv, $memSys, $memKnow) | ForEach-Object {
        if (-not (Test-Path $_)) {
            Write-Host "  [FAIL] Missing: .memory/$(Split-Path $_ -Leaf)/"
            $issues++
            if ($Fix) { New-Item -ItemType Directory -Path $_ -Force | Out-Null; Write-Host "  [FIXED] Created: .memory/$(Split-Path $_ -Leaf)/" }
        } else { Write-Host "  [PASS] .memory/$(Split-Path $_ -Leaf)/"; $passes++ }
    }

    if (-not (Test-Path $memMap)) {
        Write-Host "  [FAIL] Missing: .memory/$($S_map).md"
        $issues++
        if ($Fix -and (Test-Path (Join-Path $wn "output"))) {
            $outputDirsForMap = @(Get-ChildItem (Join-Path $wn "output") -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$' })
            Repair-GlobalKnowledgeMap $memMap $outputDirsForMap
        }
    } else { Write-Host "  [PASS] .memory/$($S_map).md"; $passes++ }

    if (Test-Path $memMap) {
        $mapText = Read-Utf8Text $memMap
        $outputDirsForMap = @(Get-ChildItem (Join-Path $wn "output") -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$' })
        $mapProjects = @()
        foreach ($line in ($mapText -split "`r?`n")) {
            $cells = @($line.Trim('|') -split '\|' | ForEach-Object { $_.Trim() })
            if ($cells.Count -ge 5 -and $cells[1] -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$') {
                $mapProjects += $cells[1]
            }
        }
        $outputNames = @($outputDirsForMap | ForEach-Object { $_.Name })
        $mapIsBad = Has-Mojibake $mapText
        $missingInMap = @($outputNames | Where-Object { $_ -notin $mapProjects })
        $extraInMap = @($mapProjects | Where-Object { $_ -notin $outputNames })

        if ($mapIsBad) {
            Write-Host "  [FAIL] $($S_map).md appears to contain mojibake"
            $issues++
        }
        foreach ($m in $missingInMap) {
            Write-Host "  [WARN] output/ not in $($S_map): $m"
            $warnings++
        }
        foreach ($m in $extraInMap) {
            Write-Host "  [WARN] $($S_map) not in output/: $m"
            $warnings++
        }
        if (($mapIsBad -or $missingInMap.Count -gt 0 -or $extraInMap.Count -gt 0) -and $Fix) {
            Repair-GlobalKnowledgeMap $memMap $outputDirsForMap
        } elseif (-not $mapIsBad -and $missingInMap.Count -eq 0 -and $extraInMap.Count -eq 0) {
            Write-Host "  [PASS] $($S_map).md matches output/"
            $passes++
        }
    }

    # System records fixed files
    if (Test-Path $memSys) {
        $sysSpecs = Get-SystemRecordSpecs
        $sysFiles = @($sysSpecs | ForEach-Object { $_.Name })
        $createdSystemRecord = $false
        foreach ($spec in $sysSpecs) {
            $recordPath = Join-Path $memSys $spec.Name
            if (-not (Test-Path $recordPath)) {
                Write-Host "  [WARN] Missing system record: $($spec.Name)"
                $warnings++
                if ($Fix) {
                    if (Ensure-SystemRecordFile $recordPath $spec.Title $spec.Desc) {
                        $createdSystemRecord = $true
                        Write-Host "  [FIXED] Created system record: $($spec.Name)"
                    }
                }
            }
        }

        $legacySys = Join-Path $memSys "rules-skills.md"
        if (Test-Path $legacySys) {
            Write-Host "  [WARN] Legacy aggregate system record needs migration: rules-skills.md"
            $warnings++
            if ($Fix) { Migrate-LegacySystemRecord $legacySys $memSys }
        } elseif ($Fix -and $createdSystemRecord) {
            Update-SystemRecordIndex $memSys
        }

        $extraSys = Get-ChildItem $memSys -File | Where-Object { $sysFiles -notcontains $_.Name -and $_.Name -ne "rules-skills.md" }
        foreach ($es in $extraSys) {
            Write-Host "  [WARN] Extra system record: $($es.Name)"
            $warnings++
            if ($Fix) { move-extra $es.FullName ".memory/$($S_sys_rec)/$($es.Name)" }
        }
    }

    # Knowledge: no _v* copies
    if (Test-Path $memKnow) {
        $vCopies = Get-ChildItem $memKnow -Recurse -File | Where-Object { $_.Name -match '_v\d+\.\d+\.\d+\.[^.]+$' }
        foreach ($vc in $vCopies) {
            Write-Host "  [FAIL] _v* copy in knowledge: $($vc.Name)"
            $issues++
            if ($Fix) { move-extra $vc.FullName ".memory/$($S_knowledge)/$($vc.Name)" }
        }
    }

    # Knowledge: no subdirs
    if (Test-Path $memKnow) {
        $extraKnow = Get-ChildItem $memKnow -Directory
        foreach ($ek in $extraKnow) {
            Write-Host "  [WARN] Extra dir in knowledge: $($ek.Name)/"
            $warnings++
            if ($Fix) { move-extra $ek.FullName ".memory/$($S_knowledge)/$($ek.Name)" }
        }
    }

    # Extra dirs in .memory/
    $memDirs = Get-ChildItem $mem -Directory | ForEach-Object { $_.Name }
    $allowedDirs = if ($workspaceSpec) { @($workspaceSpec.memoryCleanRules.allowedDirs) } else { @($S_conv, $S_sys_rec, $S_knowledge) }
    foreach ($md in $memDirs) {
        if ($allowedDirs -notcontains $md) {
            Write-Host "  [WARN] Extra dir in .memory/: $md/"
            $warnings++
            if ($Fix) { move-extra (Join-Path $mem $md) ".memory/$md" }
        }
    }
} else {
    Write-Host "  [FAIL] .memory/ missing (covered by check #1)"
    $issues++
}

# ========== Check 5: .history/ ==========
Write-Host ""
Write-Host "--- 5. .history/ Structure ---"
$hist = Join-Path $wn ".history"
if (Test-Path $hist) {
    $histDirs = Get-ChildItem $hist -Directory | ForEach-Object { $_.Name }
    $allowedHist = @(".agents", ".claude", ".memory", "output", ".system")
    foreach ($h in $histDirs) {
        if ($allowedHist -notcontains $h) {
            Write-Host "  [WARN] Extra dir in .history/: $h/"
            $warnings++
            if ($Fix) { move-extra (Join-Path $hist $h) ".history/$h" }
        } else { Write-Host "  [PASS] .history/$h/"; $passes++ }
    }
    foreach ($ah in $allowedHist) {
        if ($histDirs -notcontains $ah) {
            Write-Host "  [WARN] Missing: .history/$ah/"
            $warnings++
            if ($Fix) { New-Item -ItemType Directory -Path (Join-Path $hist $ah) -Force | Out-Null; Write-Host "  [FIXED] Created: .history/$ah/" }
        }
    }

    $histSystem = Join-Path $hist ".system"
    $histSystemStandards = Join-Path $histSystem "standards"
    foreach ($hp in @($histSystem, $histSystemStandards)) {
        if (-not (Test-Path $hp)) {
            $rel = $hp.Substring($wn.Length + 1)
            Write-Host "  [WARN] Missing: $rel/"
            $warnings++
            if ($Fix) {
                New-Item -ItemType Directory -Path $hp -Force | Out-Null
                Write-Host "  [FIXED] Created: $rel/"
            }
        }
    }

    # .history/.agents/ structure
    $histAgents = Join-Path $hist ".agents"
    if (Test-Path $histAgents) {
        $haDirs = Get-ChildItem $histAgents -Directory | ForEach-Object { $_.Name }
        $allowedHA = @("rules", "skills")
        foreach ($h in $haDirs) {
            if ($allowedHA -notcontains $h) {
                Write-Host "  [WARN] Extra in .history/.agents/: $h/"
                $warnings++
                if ($Fix) { move-extra (Join-Path $histAgents $h) ".history/.agents/$h" }
            }
        }

        # Check skills/ for timestamp-less folders
        $histSkills = Join-Path $histAgents "skills"
        if (Test-Path $histSkills) {
            $hsDirs = Get-ChildItem $histSkills -Directory
            foreach ($hs in $hsDirs) {
                if ($hs.Name -notmatch '_\d{14}$') {
                    Write-Host "  [WARN] No timestamp in .history skill: $($hs.Name)"
                    $warnings++
                    if ($Fix) {
                        $ts = Get-Date -Format "yyyyMMddHHmmss"
                        $newName = $hs.Name + "_$ts"
                        $newPath = Join-Path $histSkills $newName
                        Rename-Item $hs.FullName $newName -Force
                        Write-Host "  [FIXED] Renamed: $($hs.Name) -> $newName"
                    }
                }
            }
        }

        # Check rules/ naming
        $histRules = Join-Path $histAgents "rules"
        if (Test-Path $histRules) {
            $hrFiles = Get-ChildItem $histRules -File
            foreach ($hr in $hrFiles) {
                if ($hr.Name -match '_20\d{10,14}\.md$') { continue }  # ok: with timestamp
                if ($hr.Name -in @("direction-rules.md","filename-rules.md","memory-rules.md","version-control-rules.md")) {
                    Write-Host "  [PASS] rules/$($hr.Name)"; $passes++
                } else {
                    Write-Host "  [WARN] Odd rule file: $($hr.Name)"
                    $warnings++
                }
            }
        }
    }

    # .history/output/ naming
    $histOut = Join-Path $hist "output"
    if (Test-Path $histOut) {
        $hoDirs = Get-ChildItem $histOut -Directory
        foreach ($ho in $hoDirs) {
            if ($ho.Name -notmatch '_\d{14}$') {
                Write-Host "  [WARN] No timestamp in output history: $($ho.Name)"
                $warnings++
            }
        }
    }
} else {
    Write-Host "  [FAIL] .history/ missing (covered by check #1)"
    $issues++
}

# ========== Check 6: .system/standards/ ==========
Write-Host ""
Write-Host "--- 6. .system/standards/ ---"
$systemRoot = Join-Path $wn ".system"
$standardsDir = Join-Path $systemRoot "standards"
$standardFiles = if ($workspaceSpec -and $workspaceSpec.requiredLayer -and $workspaceSpec.requiredLayer.systemCore -and $workspaceSpec.requiredLayer.systemCore.files) {
    @($workspaceSpec.requiredLayer.systemCore.files | ForEach-Object { Split-Path ($_ -replace '/', '\') -Leaf })
} elseif ($workspaceSpec -and $workspaceSpec.overwriteLayer -and $workspaceSpec.overwriteLayer.standards) {
    @($workspaceSpec.overwriteLayer.standards)
} else {
    @("workspace-spec.json", "工作区骨架规格.md", "工作区命名规范.md", "Skills管理标准.md")
}
if (-not (Test-Path $standardsDir)) {
    Write-Host "  [FAIL] Missing: .system/standards/"
    $issues++
    if ($Fix) {
        New-Item -ItemType Directory -Path $standardsDir -Force | Out-Null
        Write-Host "  [FIXED] Created: .system/standards/"
    }
} else {
    Write-Host "  [PASS] .system/standards/"
    $passes++
}
foreach ($sf in $standardFiles) {
    $sfPath = Join-Path $standardsDir $sf
    if (-not (Test-Path $sfPath)) {
        Write-Host "  [FAIL] Missing standard file: .system/standards/$sf"
        $issues++
        if ($Fix) {
            Write-Host "  [NEEDS SOURCE] Standard file content is SSOT and cannot be synthesized by normalization."
        }
    } else {
        Write-Host "  [PASS] .system/standards/$sf"
        $passes++
    }
}

# ========== Check 6b: Get-Content encoding ==========
Write-Host ""
Write-Host "--- 6b. Get-Content Encoding ---"
$getContentEncodingProblems = @(Get-GetContentWithoutEncodingIssues)
if ($getContentEncodingProblems.Count -eq 0) {
    Write-Host "  [PASS] Get-Content text reads declare -Encoding UTF8"
    $passes++
} else {
    foreach ($p in $getContentEncodingProblems) {
        Write-Host "  [WARN] Get-Content without -Encoding: $p"
        $warnings++
    }
    if ($Fix) {
        Write-Host "  [NEEDS REVIEW] Add -Encoding UTF8 manually where the command reads project UTF-8 text."
    }
}
# ========== Check 7: .temp/ and input/ ==========
Write-Host ""
Write-Host "--- 7. .temp/ and input/ ---"
$temp = Join-Path $wn ".temp"
$inp  = Join-Path $wn "input"
if (Test-Path $temp) { Write-Host "  [PASS] .temp/ exists"; $passes++ }
else { Write-Host "  [FAIL] Missing .temp/"; $issues++; if ($Fix) { New-Item -ItemType Directory -Path $temp -Force | Out-Null; Write-Host "  [FIXED] Created .temp/" } }
if (Test-Path $inp) { Write-Host "  [PASS] input/ exists"; $passes++ }
else { Write-Host "  [FAIL] Missing input/"; $issues++; if ($Fix) { New-Item -ItemType Directory -Path $inp -Force | Out-Null; Write-Host "  [FIXED] Created input/" } }

Write-Host ""
Write-Host "========================================"
Write-Host "  Passed : $passes  |  Failed : $issues  |  Warnings: $warnings"
Write-Host "========================================"

if ($Fix -and $fixLog.Count -gt 0) {
    Write-Host ""
    Write-Host "--- Fix Summary ---"
    foreach ($fl in $fixLog) { Write-Host "  $fl" }
}

if ($issues -gt 0) { exit 1 } else { exit 0 }
