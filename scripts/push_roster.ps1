<#
Copy the lab's roster of names to the rig, so the Control tab offers the
same names PIHTI Log does.

The roster is the names-only file PIHTI Log keeps in the Obsidian vault,
People\operators.json. Names are people, so the file never enters git; the
rig keeps its own copy in ~/.controlunit/, and this script is how that copy
gets there. Run it again whenever the roster changes. It needs ssh and scp
on the PATH and a key the rig accepts.

    scripts\push_roster.ps1                 # vault under Dropbox, rig pi@pihti
    scripts\push_roster.ps1 -Rig pi@10.249.254.21
#>
param(
    [string]$Vault = (Join-Path $env:USERPROFILE "Dropbox\Obsidian\pihti"),
    [string]$Rig = "pi@pihti"
)

$ErrorActionPreference = "Stop"
$roster = Join-Path $Vault "People\operators.json"
if (-not (Test-Path $roster)) {
    Write-Error "No roster at $roster. Give the vault with -Vault."
}
$document = Get-Content $roster -Raw | ConvertFrom-Json
if ($document.schema -ne "pihti-operators/v1") {
    Write-Error "$roster is not a pihti-operators/v1 roster."
}
$count = @($document.operators).Count

ssh $Rig "mkdir -p .controlunit"
if ($LASTEXITCODE -ne 0) { Write-Error "Could not reach $Rig." }
scp $roster "${Rig}:.controlunit/operators.json"
if ($LASTEXITCODE -ne 0) { Write-Error "The copy to $Rig failed." }
Write-Output "Roster of $count names copied to ${Rig}:~/.controlunit/operators.json"
Write-Output "The Control tab reads it within a second; no restart needed."
