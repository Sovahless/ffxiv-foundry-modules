param(
    [string]$Module = "",
    [ValidateSet("", "patch", "minor", "major")]
    [string]$Bump = "",
    [switch]$PrepareOnly
)

$pyArgs = @("publish_github.py")
if ($Module) { $pyArgs += @("--module", $Module) }
if ($Bump) { $pyArgs += @("--bump", $Bump) }
if ($PrepareOnly) { $pyArgs += "--prepare-only" } else { $pyArgs += "--publish" }

python @pyArgs
