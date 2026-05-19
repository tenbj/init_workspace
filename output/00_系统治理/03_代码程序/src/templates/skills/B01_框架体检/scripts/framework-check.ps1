<#
.SYNOPSIS
    Framework health check. Read-only. Reports issues, does not fix them.
.DESCRIPTION
    Loads workspace-spec.json from .system/standards/ as Single Source of Truth.
    Checks: conversation records, .ps1 BOM, .memory cleanliness, knowledge map alignment,
    input/ path, sub-project catalog completeness, file numbering, required skeleton, catalog link format,
    Get-Content -Encoding check, .system history changelog, root README history folder.
#>

param([switch]$Quiet)

$ErrorActionPreference = "Continue"
$workspaceRoot = $PSScriptRoot
while ($workspaceRoot -and -not (Test-Path (Join-Path $workspaceRoot ".history"))) {
    $parent = Split-Path $workspaceRoot -Parent
    if ($parent -eq $workspaceRoot) { $workspaceRoot = $null; break }
    $workspaceRoot = $parent
}

if (-not $workspaceRoot) {
    Write-Host "ERROR: Workspace root not found"
    exit 1
}

# ── Load SSOT spec ─────────────────────────────────────────────────────────────
$specPath = Join-Path $workspaceRoot ".system\standards\workspace-spec.json"
if (-not (Test-Path $specPath)) {
    Write-Host "WARN: workspace-spec.json not found at $specPath — falling back to built-in defaults"
    $spec = $null
} else {
    $spec = Get-Content $specPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

# ── Derive values from spec (with hard-coded fallbacks) ────────────────────────
$requiredSkills = if ($spec) {
    $spec.overwriteLayer.skills
} else {
    @("A01_创建技能","B04_子项目管理","A02_安装技能","B01_框架体检","B02_版本控制备份","B03_记忆管理","B06_项目规范化","B05_课题研究")
}

$registeredSkills = if ($spec -and $spec.skillsManagement -and $spec.skillsManagement.registeredSkills) {
    @($spec.skillsManagement.registeredSkills)
} else {
    @($requiredSkills)
}

$requiredRules = if ($spec) {
    $spec.overwriteLayer.rules
} else {
    @("direction-rules.md","filename-rules.md","memory-rules.md","version-control-rules.md")
}

$bomFiles = if ($spec) {
    $spec.bomCheck.files | ForEach-Object { Join-Path $workspaceRoot $_ }
} else {
    @(
        (Join-Path $workspaceRoot ".agents\skills\B02_版本控制备份\scripts\backup.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B04_子项目管理\scripts\new_project.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B04_子项目管理\scripts\next_number.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B04_子项目管理\scripts\normalize_project.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B01_框架体检\scripts\framework-check.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B06_项目规范化\scripts\normalize.ps1"),
        (Join-Path $workspaceRoot ".agents\skills\B03_记忆管理\scripts\remove.ps1")
    )
}

$systemRecordFiles = if ($spec) {
    $spec.naming.systemRecord.fixedNames
} else {
    @("规则变更记录.md","技能变更记录.md","脚本治理记录.md","教训库.md","索引.md")
}

$allowedMemoryDirs = if ($spec) {
    $spec.memoryCleanRules.allowedDirs
} else {
    @("对话记录","系统记录","知识提炼")
}

$subFolderSpecs = if ($spec) {
    $spec.naming.subfolder.specs | ForEach-Object {
        @{ Prefix = $_.prefix; Title = $_.title; Stem = $_.stem }
    }
} else {
    @(
        @{ Prefix = "01"; Title = "问题答疑"; Stem = "01_问题答疑" },
        @{ Prefix = "02"; Title = "课题研究"; Stem = "02_课题研究" },
        @{ Prefix = "03"; Title = "代码程序"; Stem = "03_代码程序" }
    )
}

$requiredDirs = if ($spec) { $spec.requiredLayer.directories } else { @() }
$requiredFiles = if ($spec -and $spec.requiredLayer -and $spec.requiredLayer.files) {
    @($spec.requiredLayer.files.PSObject.Properties.Name)
} else {
    @()
}

# ── Helper functions ───────────────────────────────────────────────────────────
$issues = 0
$warnings = 0
$passes = 0

function Get-ProjectRootContentFiles($projectDir) {
    return @(Get-ChildItem -LiteralPath $projectDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin @("目录.md", "版本记录.md") -and $_.Name -match '\.(md|html|txt|ps1)$' } |
        Sort-Object CreationTime, Name)
}

function Get-ProjectRootPayloadFiles($projectDir) {
    return @(Get-ChildItem -LiteralPath $projectDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin @("目录.md", "版本记录.md") } |
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

function Test-StructuredProject($projectDir) {
    $rootPayloadFiles = Get-ProjectRootPayloadFiles $projectDir
    $rootPayloadDirs = @(Get-ChildItem -LiteralPath $projectDir -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $dirName = $_.Name
            -not ($subFolderSpecs | Where-Object {
                $dirName -eq $_.Stem -or $dirName -match "^$([regex]::Escape($_.Stem))_v\d+\.\d+\.\d+$"
            })
        })
    $subFolderCount = 0
    foreach ($s in $subFolderSpecs) {
        $subFolderCount += (Get-ProjectSubFolderMatches $projectDir $s).Count
    }
    return ($subFolderCount -gt 0 -or ($rootPayloadFiles.Count -eq 0 -and $rootPayloadDirs.Count -eq 0))
}

function Get-TextFilesForGetContentEncodingCheck {
    $files = @()
    $fileRoots = @("AGENTS.md", "CLAUDE.md")
    foreach ($rel in $fileRoots) {
        $p = Join-Path $workspaceRoot $rel
        if (Test-Path -LiteralPath $p) { $files += (Get-Item -LiteralPath $p) }
    }

    $dirRoots = @(".agents\rules", ".agents\skills", ".system\standards")
    foreach ($rel in $dirRoots) {
        $p = Join-Path $workspaceRoot $rel
        if (Test-Path -LiteralPath $p) {
            $files += @(Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Extension -in @(".md", ".json", ".yaml", ".yml", ".ps1") })
        }
    }

    $outputRoot = Join-Path $workspaceRoot "output"
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
                $rel = $file.FullName.Substring($workspaceRoot.Length + 1)
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

    $skillsDir = Join-Path $workspaceRoot ".agents\skills"
    if (-not (Test-Path -LiteralPath $skillsDir)) { return $result }

    $skillNamePattern = '^[A-Z]\d{2}_[^\\/:*?"<>|]+$'
    $existingSkills = @(Get-ChildItem -LiteralPath $skillsDir -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name)
    $existingNames = @($existingSkills | ForEach-Object { $_.Name })

    foreach ($skill in $registeredSkills) {
        if ($existingNames -notcontains $skill) {
            $result.RegisteredMissingFolder += $skill
        }
    }

    foreach ($dir in $existingSkills) {
        $folderName = $dir.Name
        if ($folderName -notmatch $skillNamePattern) {
            $result.BadFolderNames += $folderName
        }
        if ($registeredSkills -notcontains $folderName) {
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

function Get-HistorySystemSnapshots {
    $systemHistoryRoot = Join-Path $workspaceRoot ".history\.system"
    if (-not (Test-Path -LiteralPath $systemHistoryRoot)) { return @() }
    return @(Get-ChildItem -LiteralPath $systemHistoryRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^.+_\d{14}$' } |
        Sort-Object Name)
}

function Get-MarkdownSection {
    param(
        [string]$Content,
        [string]$Heading
    )

    $escaped = [regex]::Escape($Heading)
    $match = [regex]::Match($Content, "(?ms)^##\s+$escaped\s*`r?`n(?<body>.*?)(?=^##\s+|\z)")
    if ($match.Success) { return $match.Groups["body"].Value }
    return $null
}

function Get-RelativePathUnder {
    param(
        [string]$Path,
        [string]$Root
    )

    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { return "" }
    $prefix = $rootFull + "\"
    if ($pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathFull.Substring($prefix.Length)
    }
    return $pathFull
}

function Get-SystemHistoryLogProblems {
    $result = [ordered]@{
        MissingLog = $false
        MissingEntries = @()
        MissingFiles = @()
        Placeholders = @()
    }

    $snapshots = @(Get-HistorySystemSnapshots)
    if ($snapshots.Count -eq 0) { return $result }

    $logPath = Join-Path $workspaceRoot ".history\.system\更新日志.md"
    if (-not (Test-Path -LiteralPath $logPath)) {
        $result.MissingLog = $true
        return $result
    }

    $content = Get-Content -LiteralPath $logPath -Raw -Encoding UTF8
    foreach ($snapshot in $snapshots) {
        $section = Get-MarkdownSection -Content $content -Heading $snapshot.Name
        if ($null -eq $section) {
            $result.MissingEntries += $snapshot.Name
            continue
        }

        $files = @(Get-ChildItem -LiteralPath $snapshot.FullName -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne ".gitkeep" } |
            Sort-Object FullName)
        foreach ($file in $files) {
            $rel = (Get-RelativePathUnder -Path $file.FullName -Root $snapshot.FullName) -replace '\\', '/'
            if ($section -notmatch [regex]::Escape($rel)) {
                $result.MissingFiles += "$($snapshot.Name): $rel"
            }
        }

        if ($section -match '待填写|待补全|待补充') {
            $result.Placeholders += $snapshot.Name
        }
    }

    return $result
}

function Get-RootHistoryProblems {
    $result = [ordered]@{
        MissingReadmeDir = $false
        LooseReadmeBackups = @()
        BadReadmeBackups = @()
    }

    $readmePath = Join-Path $workspaceRoot "README.md"
    $readmeHistoryDir = Join-Path $workspaceRoot ".history\README"
    if ((Test-Path -LiteralPath $readmePath) -and -not (Test-Path -LiteralPath $readmeHistoryDir)) {
        $result.MissingReadmeDir = $true
    }

    $historyRoot = Join-Path $workspaceRoot ".history"
    if (Test-Path -LiteralPath $historyRoot) {
        $result.LooseReadmeBackups = @(Get-ChildItem -LiteralPath $historyRoot -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^README_\d{14}\.md$' } |
            ForEach-Object { $_.Name })
    }

    if (Test-Path -LiteralPath $readmeHistoryDir) {
        $result.BadReadmeBackups = @(Get-ChildItem -LiteralPath $readmeHistoryDir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne ".gitkeep" -and $_.Name -notmatch '^README_\d{14}\.md$' } |
            ForEach-Object { $_.Name })
    }

    return $result
}
# ══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "========================================"
Write-Host "  Framework Health Check"
Write-Host "  Workspace: $workspaceRoot"
if ($spec) { Write-Host "  Spec: workspace-spec.json v$($spec.version)" }
Write-Host "========================================"
Write-Host ""

# ── Check 0: Required skeleton ──────────────────────────────────────────────
if ($requiredDirs.Count -gt 0) {
    Write-Host "--- 0. Required Skeleton Directories ---"
    $missingDirs = @()
    foreach ($d in $requiredDirs) {
        $p = Join-Path $workspaceRoot ($d -replace '/', '\')
        if (-not (Test-Path $p)) { $missingDirs += $d }
    }
    if ($missingDirs.Count -eq 0) {
        Write-Host "  [PASS] All $($requiredDirs.Count) required directories exist"
        $passes++
    } else {
        foreach ($m in $missingDirs) {
            Write-Host "  [FAIL] Missing: $m/"
            $issues++
        }
    }

    if ($requiredFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "--- 0a. Required Skeleton Files ---"
        $missingFiles = @()
        foreach ($f in $requiredFiles) {
            $p = Join-Path $workspaceRoot ($f -replace '/', '\')
            if (-not (Test-Path $p)) { $missingFiles += $f }
        }
        if ($missingFiles.Count -eq 0) {
            Write-Host "  [PASS] All $($requiredFiles.Count) required files exist"
            $passes++
        } else {
            foreach ($m in $missingFiles) {
                Write-Host "  [FAIL] Missing: $m"
                $issues++
            }
        }
    }

    # Core subproject check
    if ($spec -and $spec.requiredLayer.coreSubproject) {
        Write-Host ""
        Write-Host "--- 0b. Core Subproject (00_系统治理) ---"
        $coreSpec = $spec.requiredLayer.coreSubproject
        $corePattern = "^00_$([regex]::Escape($coreSpec.name))(_v\d+\.\d+\.\d+)?$"
        $coreDirs = @(Get-ChildItem (Join-Path $workspaceRoot "output") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match $corePattern })
        if ($coreDirs.Count -eq 0) {
            Write-Host "  [FAIL] Core subproject not found: output/00_$($coreSpec.name)/"
            $issues++
        } else {
            $coreDir = $coreDirs[0]
            Write-Host "  [PASS] Core subproject: $($coreDir.Name)"
            $passes++
            # Check subfolders
            foreach ($sf in $coreSpec.subfolders) {
                $stem = $sf -replace '_v\d+\.\d+\.\d+$', ''
                $sfMatch = @(Get-ChildItem $coreDir.FullName -Directory |
                    Where-Object { $_.Name -eq $stem -or $_.Name -match "^$([regex]::Escape($stem))_v\d+\.\d+\.\d+$" })
                if ($sfMatch.Count -eq 0) {
                    Write-Host "  [WARN] Core subproject missing subfolder: $stem"
                    $warnings++
                }
            }
            # Check fixed files
            foreach ($ff in $coreSpec.fixedFiles) {
                if (-not (Test-Path (Join-Path $coreDir.FullName $ff))) {
                    Write-Host "  [WARN] Core subproject missing: $ff"
                    $warnings++
                }
            }
            # Check conversation record
            $convRecordName = "$($coreDir.Name).md"
            $convRecordPath = Join-Path $workspaceRoot ".memory\对话记录\$convRecordName"
            if (-not (Test-Path $convRecordPath)) {
                Write-Host "  [WARN] Core subproject conversation record missing: .memory/对话记录/$convRecordName"
                $warnings++
            }
        }
    }

    # .system/standards files
    if ($spec) {
        Write-Host ""
        Write-Host "--- 0c. .system/standards/ ---"
        $systemFiles = @($spec.requiredLayer.systemCore.files)
        if ($systemFiles.Count -eq 0) {
            $systemFiles = @(
                ".system/standards/workspace-spec.json",
                ".system/standards/工作区骨架规格.md",
                ".system/standards/工作区命名规范.md",
                ".system/standards/Skills管理标准.md"
            )
        }
        $missingSystemFiles = @()
        foreach ($sf in $systemFiles) {
            $sfPath = Join-Path $workspaceRoot ($sf -replace '/', '\')
            if (-not (Test-Path $sfPath)) { $missingSystemFiles += $sf }
        }
        if ($missingSystemFiles.Count -eq 0) {
            Write-Host "  [PASS] All $($systemFiles.Count) .system standard files present"
            $passes++
        } else {
            foreach ($sf in $missingSystemFiles) {
                Write-Host "  [FAIL] Missing: $sf"
                $issues++
            }
        }
    }

    # .system history changelog
    Write-Host ""
    Write-Host "--- 0d. .system History Changelog ---"
    $systemHistoryProblems = Get-SystemHistoryLogProblems
    if ($systemHistoryProblems.MissingLog) {
        Write-Host "  [FAIL] Missing: .history/.system/更新日志.md"
        $issues++
    } else {
        foreach ($entry in $systemHistoryProblems.MissingEntries) {
            Write-Host "  [FAIL] .system snapshot missing changelog entry: $entry"
            $issues++
        }
        foreach ($file in $systemHistoryProblems.MissingFiles) {
            Write-Host "  [FAIL] .system changelog missing file row: $file"
            $issues++
        }
        foreach ($placeholder in $systemHistoryProblems.Placeholders) {
            Write-Host "  [WARN] .system changelog entry still has placeholders: $placeholder"
            $warnings++
        }
        if (-not $systemHistoryProblems.MissingLog -and
            $systemHistoryProblems.MissingEntries.Count -eq 0 -and
            $systemHistoryProblems.MissingFiles.Count -eq 0) {
            $snapshotCount = (Get-HistorySystemSnapshots).Count
            Write-Host "  [PASS] .system changelog covers $snapshotCount timestamped snapshots"
            $passes++
        }
    }

    # Root independent file history folders
    Write-Host ""
    Write-Host "--- 0e. Root File History ---"
    $rootHistoryProblems = Get-RootHistoryProblems
    if ($rootHistoryProblems.MissingReadmeDir) {
        Write-Host "  [FAIL] Missing README history dir: .history/README/"
        $issues++
    }
    foreach ($loose in $rootHistoryProblems.LooseReadmeBackups) {
        Write-Host "  [FAIL] Loose README backup in .history root: $loose"
        $issues++
    }
    foreach ($bad in $rootHistoryProblems.BadReadmeBackups) {
        Write-Host "  [FAIL] Bad README backup filename in .history/README/: $bad"
        $issues++
    }
    if (-not $rootHistoryProblems.MissingReadmeDir -and
        $rootHistoryProblems.LooseReadmeBackups.Count -eq 0 -and
        $rootHistoryProblems.BadReadmeBackups.Count -eq 0) {
        Write-Host "  [PASS] README history uses .history/README/"
        $passes++
    }

    # Claude slash commands
    if ($spec -and $spec.claudeIntegration) {
        Write-Host ""
        Write-Host "--- 0f. Claude Integration ---"
        $cmdDirRel = [string]$spec.claudeIntegration.commandsDirectory
        $cmdDir = Join-Path $workspaceRoot ($cmdDirRel -replace '/', '\')
        $cmdTemplate = [string]$spec.claudeIntegration.commandTemplate
        if ([string]::IsNullOrWhiteSpace($cmdTemplate)) {
            $cmdTemplate = "请读取并执行 .agents/skills/{skill}/SKILL.md"
        }
        if (-not (Test-Path $cmdDir)) {
            Write-Host "  [FAIL] Missing: $cmdDirRel/"
            $issues++
        } else {
            $missingCommands = @()
            $badCommands = @()
            foreach ($skill in $registeredSkills) {
                $cmdPath = Join-Path $cmdDir "$skill.md"
                $expected = $cmdTemplate.Replace("{skill}", $skill)
                if (-not (Test-Path $cmdPath)) {
                    $missingCommands += "$skill.md"
                    continue
                }
                $actual = (Get-Content $cmdPath -Raw -Encoding UTF8).Trim()
                if ($actual -ne $expected) { $badCommands += "$skill.md" }
            }
            foreach ($m in $missingCommands) { Write-Host "  [FAIL] Missing Claude command: $m"; $issues++ }
            foreach ($b in $badCommands) { Write-Host "  [FAIL] Bad Claude command body: $b"; $issues++ }

            $existingCommands = @(Get-ChildItem $cmdDir -Filter "*.md" -File -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
            $expectedCommands = @($registeredSkills | ForEach-Object { "$_.md" })
            $extraCommands = $existingCommands | Where-Object { $_ -notin $expectedCommands }
            foreach ($e in $extraCommands) { Write-Host "  [WARN] Extra Claude command: $e"; $warnings++ }

            if ($missingCommands.Count -eq 0 -and $badCommands.Count -eq 0) {
                Write-Host "  [PASS] Claude commands match registered skills ($($registeredSkills.Count))"
                $passes++
            }
        }
    }

    # Skill folder, YAML name, and registry contract
    Write-Host ""
    Write-Host "--- 0g. Skill Naming Contract ---"
    $skillNamingProblems = Get-SkillNamingContractProblems
    foreach ($item in $skillNamingProblems.BadFolderNames) {
        Write-Host "  [FAIL] Bad Skill folder name: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingSkillMd) {
        Write-Host "  [FAIL] Missing SKILL.md: .agents/skills/$item/"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingYamlName) {
        Write-Host "  [FAIL] Missing YAML name: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.BadYamlName) {
        Write-Host "  [FAIL] YAML name must equal folder name: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingDescription) {
        Write-Host "  [FAIL] Missing YAML description: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.LongDescription) {
        Write-Host "  [FAIL] YAML description exceeds 100 chars: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingOpenAiYaml) {
        Write-Host "  [FAIL] Missing agents/openai.yaml: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingDisplayName) {
        Write-Host "  [FAIL] Missing OpenAI display_name: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.BadDisplayName) {
        Write-Host "  [FAIL] OpenAI display_name must equal folder name plus version: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.MissingShortDescription) {
        Write-Host "  [FAIL] Missing OpenAI short_description: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.RegisteredMissingFolder) {
        Write-Host "  [FAIL] Registered Skill missing folder: $item"
        $issues++
    }
    foreach ($item in $skillNamingProblems.UnregisteredFolder) {
        Write-Host "  [FAIL] Skill folder not registered: $item"
        $issues++
    }
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
        Write-Host "  [PASS] Skill folders, YAML names, OpenAI display versions, descriptions, and registry align ($($registeredSkills.Count))"
        $passes++
    }
    Write-Host ""
}

# ── Check 1: Conversation records ────────────────────────────────────────────
Write-Host "--- 1. Conversation Records ---"
$outputDirs = Get-ChildItem (Join-Path $workspaceRoot "output") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$' }
$convDir = Join-Path $workspaceRoot ".memory\对话记录"
$missingConvs = @()
foreach ($dir in $outputDirs) {
    $expected = Join-Path $convDir "$($dir.Name).md"
    if (-not (Test-Path $expected)) { $missingConvs += $dir.Name }
}
if ($missingConvs.Count -eq 0) {
    Write-Host "  [PASS] $($outputDirs.Count)/$($outputDirs.Count) subprojects have conversation records"
    $passes++
} else {
    foreach ($m in $missingConvs) {
        Write-Host "  [FAIL] Missing: $m"
        $issues++
    }
}
$convFiles = Get-ChildItem $convDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d{2}_.+\.md$' }
$outputNames = $outputDirs | ForEach-Object { "$($_.Name).md" }
$orphans = $convFiles | Where-Object { $_.Name -notin $outputNames }
foreach ($o in $orphans) {
    Write-Host "  [WARN] Orphan record: $($o.Name)"
    $warnings++
}

# ── Check 2: .ps1 BOM ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- 2. .ps1 BOM ---"
foreach ($p in $bomFiles) {
    if (-not (Test-Path $p)) {
        Write-Host "  [FAIL] Not found: $($p.Substring($workspaceRoot.Length + 1))"
        $issues++
        continue
    }
    $b = [System.IO.File]::ReadAllBytes($p)
    $rel = $p.Substring($workspaceRoot.Length + 1)
    if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
        Write-Host "  [PASS] BOM OK: $rel"
        $passes++
    } else {
        Write-Host "  [FAIL] No BOM: $rel"
        $issues++
    }
}

# ── Check 3: .memory cleanliness ─────────────────────────────────────────────
Write-Host ""
Write-Host "--- 3. .memory Current Zone ---"
$memRoot = Join-Path $workspaceRoot ".memory"

# No _v* history copies outside 对话记录
$vCopies = Get-ChildItem $memRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '_v\d+\.\d+\.\d+\.[^.]+$' -and
        $_.DirectoryName -notmatch '\\\.history' -and
        $_.DirectoryName -notmatch '\\对话记录'
    }
if ($vCopies.Count -eq 0) {
    Write-Host "  [PASS] No _v* history copies in current zone"
    $passes++
} else {
    foreach ($vc in $vCopies) {
        Write-Host "  [FAIL] History copy: $($vc.FullName.Substring($workspaceRoot.Length + 1))"
        $issues++
    }
}

# No extra dirs in .memory
$memDirs = @(Get-ChildItem $memRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
$unexpectedDirs = $memDirs | Where-Object { $allowedMemoryDirs -notcontains $_ }
foreach ($ud in $unexpectedDirs) {
    Write-Host "  [WARN] Unexpected dir in .memory/: $ud/"
    $warnings++
}

# System record files
$sysRecDir = Join-Path $memRoot "系统记录"
if (Test-Path $sysRecDir) {
    $missingRec = @()
    foreach ($rf in $systemRecordFiles) {
        if (-not (Test-Path (Join-Path $sysRecDir $rf))) { $missingRec += $rf }
    }
    $extraRec = @(Get-ChildItem $sysRecDir -File -ErrorAction SilentlyContinue |
        Where-Object { $systemRecordFiles -notcontains $_.Name -and $_.Name -ne "rules-skills.md" })
    if ($missingRec.Count -eq 0 -and $extraRec.Count -eq 0) {
        Write-Host "  [PASS] 系统记录/ has exactly $($systemRecordFiles.Count) required files"
        $passes++
    } else {
        foreach ($mr in $missingRec) { Write-Host "  [FAIL] Missing system record: $mr"; $issues++ }
        foreach ($er in $extraRec)   { Write-Host "  [WARN] Extra system record: $($er.Name)"; $warnings++ }
    }
    if (Test-Path (Join-Path $sysRecDir "rules-skills.md")) {
        Write-Host "  [WARN] Legacy rules-skills.md still present — needs migration"
        $warnings++
    }
}

# Task progress structure and index consistency
Write-Host ""
Write-Host "--- 3a. Task Progress ---"
$taskProgressRoot = Join-Path $memRoot "任务进度"
$taskProgressIndex = Join-Path $taskProgressRoot "索引.md"
$taskProgressActive = Join-Path $taskProgressRoot "进行中"
$taskProgressDone = Join-Path $taskProgressRoot "已完成"
$taskProgressCanceled = Join-Path $taskProgressRoot "已取消"
$taskProgressRequired = @($taskProgressRoot, $taskProgressIndex, $taskProgressActive, $taskProgressDone, $taskProgressCanceled)
$missingTaskProgress = @()
foreach ($tp in $taskProgressRequired) {
    if (-not (Test-Path -LiteralPath $tp)) {
        $missingTaskProgress += $tp.Substring($workspaceRoot.Length + 1)
    }
}
if ($missingTaskProgress.Count -gt 0) {
    foreach ($m in $missingTaskProgress) {
        Write-Host "  [FAIL] Missing task progress item: $m"
        $issues++
    }
} else {
    $activeTaskFiles = @(Get-ChildItem -LiteralPath $taskProgressActive -Filter "*.md" -File -ErrorAction SilentlyContinue)
    $indexContent = Get-Content -LiteralPath $taskProgressIndex -Raw -Encoding UTF8
    $missingInIndex = @()
    foreach ($taskFile in $activeTaskFiles) {
        if ($indexContent -notmatch [regex]::Escape($taskFile.Name)) {
            $missingInIndex += $taskFile.Name
        }
    }
    foreach ($m in $missingInIndex) {
        Write-Host "  [FAIL] Active task not indexed: $m"
        $issues++
    }

    $linkedActiveFiles = @([regex]::Matches($indexContent, '\]\(([^)]*任务进度/进行中/[^)]+\.md)\)') |
        ForEach-Object { $_.Groups[1].Value })
    $brokenLinks = @()
    foreach ($link in $linkedActiveFiles) {
        $linkPath = Join-Path $workspaceRoot ($link -replace '/', '\')
        if (-not (Test-Path -LiteralPath $linkPath)) {
            $brokenLinks += $link
        }
    }
    foreach ($b in $brokenLinks) {
        Write-Host "  [FAIL] Task index link not found: $b"
        $issues++
    }

    $staleTasks = @()
    foreach ($taskFile in $activeTaskFiles) {
        $content = Get-Content -LiteralPath $taskFile.FullName -Raw -Encoding UTF8
        if ($content -match '(?m)^> status:\s*(ACTIVE|PAUSED|BLOCKED|REVIEW|STALE)\s*$' -and
            $content -match '(?m)^> updated-at:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*$') {
            $updatedAt = [datetime]::ParseExact($Matches[1], "yyyy-MM-dd HH:mm:ss", $null)
            if ($updatedAt -lt (Get-Date).AddDays(-7)) {
                $staleTasks += $taskFile.Name
            }
        }
    }
    foreach ($s in $staleTasks) {
        Write-Host "  [WARN] Task progress may be stale: $s"
        $warnings++
    }

    if ($missingInIndex.Count -eq 0 -and $brokenLinks.Count -eq 0) {
        Write-Host "  [PASS] Task progress index matches active tasks ($($activeTaskFiles.Count))"
        $passes++
    }
}

# ── Check 4: Knowledge map ────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- 4. Knowledge Map ---"
$mapPath = Join-Path $memRoot "全局知识地图.md"
if (-not (Test-Path $mapPath)) {
    Write-Host "  [FAIL] Map not found"
    $issues++
} else {
    $mapContent = Get-Content $mapPath -Raw -Encoding UTF8
    $mapProjects = @()
    foreach ($line in ($mapContent -split "`r?`n")) {
        $cells = @($line.Trim() -split '\|' |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -ne "" })
        if ($cells.Count -ge 5 -and $cells[1] -match '^\d{2}_.+?(_v\d+\.\d+\.\d+)?$') {
            $mapProjects += $cells[1]
        }
    }
    $outputNames = $outputDirs | ForEach-Object { $_.Name }
    $inMapNotOut = $mapProjects | Where-Object { $_ -notin $outputNames }
    $inOutNotMap = $outputNames | Where-Object { $_ -notin $mapProjects }
    if ($inMapNotOut.Count -eq 0 -and $inOutNotMap.Count -eq 0) {
        Write-Host "  [PASS] Map ($($mapProjects.Count)) matches output/ ($($outputDirs.Count))"
        $passes++
    } else {
        foreach ($m in $inMapNotOut) { Write-Host "  [FAIL] In map, not output/: $m"; $issues++ }
        foreach ($o in $inOutNotMap) { Write-Host "  [FAIL] In output/, not map: $o"; $issues++ }
    }
}

# ── Check 5: input/ ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "--- 5. input/ Path ---"
$inputPath = Join-Path $workspaceRoot "input"
if (Test-Path $inputPath) {
    $inputFiles = Get-ChildItem $inputPath -File -ErrorAction SilentlyContinue
    $bad = $inputFiles | Where-Object { $_.Name -match '系统|变更|治理|规则|skill|备份|记忆' }
    if ($bad.Count -gt 0) {
        foreach ($b in $bad) { Write-Host "  [WARN] Possible governance doc in input/: $($b.Name)"; $warnings++ }
    } else {
        Write-Host "  [PASS] input/ clean"
        $passes++
    }
} else {
    Write-Host "  [PASS] No input/"
    $passes++
}

# ── Check 6: Structured sub-project internals ─────────────────────────────────
Write-Host ""
Write-Host "--- 6. Structured Sub-folders ---"
$missingCatalog = @()
$structuredProblems = @()
foreach ($dir in $outputDirs) {
    $catalogPath = Join-Path $dir.FullName "目录.md"
    if (-not (Test-Path $catalogPath)) {
        $missingCatalog += $dir.Name
    }
    if (Test-StructuredProject $dir.FullName) {
        foreach ($s in $subFolderSpecs) {
            $sfMatches = Get-ProjectSubFolderMatches $dir.FullName $s
            if ($sfMatches.Count -eq 0) {
                $structuredProblems += "$($dir.Name): missing $($s.Stem)"
                continue
            }
            if ($sfMatches.Count -gt 1) {
                $structuredProblems += "$($dir.Name): duplicate $($s.Stem)"
            }
            $actualVersion   = Get-ProjectSubFolderVersion $sfMatches[0].Name $s
            $expectedVersion = Get-ExpectedSubFolderVersion $sfMatches[0].FullName
            if ($actualVersion -and $actualVersion -ne $expectedVersion) {
                $structuredProblems += "$($dir.Name)\$($sfMatches[0].Name): expected v$expectedVersion"
            }
        }
    }
}
if ($missingCatalog.Count -eq 0) {
    Write-Host "  [PASS] All $($outputDirs.Count) subprojects have 目录.md"
    $passes++
} else {
    foreach ($m in $missingCatalog) { Write-Host "  [FAIL] Missing 目录.md: $m"; $issues++ }
}
if ($structuredProblems.Count -eq 0) {
    Write-Host "  [PASS] Structured sub-folder checks passed"
    $passes++
} else {
    foreach ($p in $structuredProblems) { Write-Host "  [FAIL] $p"; $issues++ }
}

# ── Check 7: File numbering and internal file version ─────────────────────────
Write-Host ""
Write-Host "--- 7. Internal File Naming ---"
$unnumberedFiles   = @()
foreach ($dir in $outputDirs) {
    if (Test-StructuredProject $dir.FullName) {
        foreach ($s in $subFolderSpecs) {
            $sfMatches = Get-ProjectSubFolderMatches $dir.FullName $s
            if ($sfMatches.Count -eq 0) { continue }
            foreach ($f in (Get-SubFolderContentFiles $sfMatches[0].FullName)) {
                $relPath = "$($dir.Name)\$($sfMatches[0].Name)\$($f.Name)"
                if ($s.Prefix -ne "03" -and $f.Name -notmatch '^\d{2}_') {
                    $unnumberedFiles += $relPath
                }
            }
        }
    } else {
        foreach ($f in (Get-ProjectRootContentFiles $dir.FullName)) {
            if ($f.Name -notmatch '^\d{2}_') {
                $unnumberedFiles += "$($dir.Name)\$($f.Name)"
            }
        }
    }
}
if ($unnumberedFiles.Count -eq 0) {
    Write-Host "  [PASS] Numbered content files look OK"
    $passes++
} else {
    Write-Host "  [WARN] $($unnumberedFiles.Count) files without {NN}_ prefix:"
    foreach ($u in $unnumberedFiles) { Write-Host "     $u" }
    $warnings++
}
Write-Host "  [PASS] 01/02 content file version suffixes are optional"
$passes++

# -- Check 8: Catalog link format ------------------------------------------------
Write-Host ""
Write-Host "--- 8. Catalog Link Format ---"
$catalogProblems = @()
$catalogFileName = ([string][char]0x76EE) + ([string][char]0x5F55) + ".md"
foreach ($dir in $outputDirs) {
    $catalogPath = Join-Path $dir.FullName $catalogFileName
    if (-not (Test-Path -LiteralPath $catalogPath)) { continue }

    $lines = @(Get-Content -LiteralPath $catalogPath -Encoding UTF8)
    $inCheckedSection = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line -match '^\s*##\s+') {
            $inCheckedSection = ($line -match '^\s*##\s+(01_|02_)')
            continue
        }
        if (-not $inCheckedSection) { continue }

        $trimmed = $line.Trim()
        if (-not $trimmed.StartsWith('|')) { continue }

        $cells = @($trimmed.Trim('|').Split('|') | ForEach-Object { $_.Trim() })
        if ($cells.Count -lt 2) { continue }

        $indexCell = $cells[0]
        $fileCell = $cells[1]
        if ([string]::IsNullOrWhiteSpace($fileCell)) { continue }
        if ($indexCell -eq '#' -or $indexCell -match '^-+$') { continue }

        $relCatalog = "$($dir.Name)\$catalogFileName"
        $lineNo = $i + 1
        if ($fileCell -notmatch '^\[(?<label>[^\]]+)\]\((?<href>[^)]+)\)$') {
            $catalogProblems += "${relCatalog}:$lineNo file column is not a Markdown link: $fileCell"
            continue
        }

        $href = $Matches['href'].Trim()
        $hrefNoAnchor = ($href -split '#', 2)[0]
        if ([string]::IsNullOrWhiteSpace($hrefNoAnchor)) {
            $catalogProblems += "${relCatalog}:$lineNo link target is empty: $fileCell"
            continue
        }
        try { $hrefNoAnchor = [System.Uri]::UnescapeDataString($hrefNoAnchor) } catch {}
        $targetPath = Join-Path $dir.FullName ($hrefNoAnchor -replace '/', '\')
        if (-not (Test-Path -LiteralPath $targetPath)) {
            $catalogProblems += "${relCatalog}:$lineNo link target not found: $href"
        }
    }
}
if ($catalogProblems.Count -eq 0) {
    Write-Host "  [PASS] Catalog file columns are Markdown links with existing targets"
    $passes++
} else {
    foreach ($p in $catalogProblems) { Write-Host "  [FAIL] $p"; $issues++ }
}
# -- Check 9: Get-Content encoding ------------------------------------------------
Write-Host ""
Write-Host "--- 9. Get-Content Encoding ---"
$getContentEncodingProblems = @(Get-GetContentWithoutEncodingIssues)
if ($getContentEncodingProblems.Count -eq 0) {
    Write-Host "  [PASS] Get-Content text reads declare -Encoding UTF8"
    $passes++
} else {
    foreach ($p in $getContentEncodingProblems) {
        Write-Host "  [WARN] Get-Content without -Encoding: $p"
        $warnings++
    }
}
Write-Host ""
Write-Host "========================================"
Write-Host "  Passed : $passes  |  Failed : $issues  |  Warnings: $warnings"
Write-Host "========================================"
if ($issues -gt 0) { exit 1 } else { exit 0 }
