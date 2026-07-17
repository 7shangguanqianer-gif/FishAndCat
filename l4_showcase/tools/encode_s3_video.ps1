[CmdletBinding()]
param(
    [string]$FramesDirectory = 'F:\abb_wh_work\l4_showcase\out\_frames_s3_0714_final_v2',
    [string]$OutputPath = '',
    [string]$Ffmpeg = 'D:\py\Python3\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Ffmpeg -PathType Leaf)) {
    throw "FFmpeg not found: $Ffmpeg"
}
if (-not (Test-Path -LiteralPath $FramesDirectory -PathType Container)) {
    throw "Frames directory not found: $FramesDirectory"
}

$frames = @(Get-ChildItem -LiteralPath $FramesDirectory -Filter 'frame_*.jpg' -File | Sort-Object Name)
$captureMarker = Join-Path $FramesDirectory '.capture_in_progress'
$manifestPath = Join-Path $FramesDirectory 'capture_manifest.json'
if (Test-Path -LiteralPath $captureMarker -PathType Leaf) {
    throw "Capture is incomplete: $captureMarker"
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Capture manifest not found: $manifestPath"
}
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.mode -ne 'full' -or $manifest.frameCount -ne 960 -or @($manifest.errors).Count -ne 0 -or @($manifest.badResponses).Count -ne 0) {
    throw "Capture manifest is not a clean 960-frame full run: $manifestPath"
}
if ($manifest.selfHosted -ne $true -or $manifest.fps -ne 30 -or $manifest.durationSeconds -ne 32 -or
    @($manifest.outputPixels).Count -ne 2 -or $manifest.outputPixels[0] -ne 1920 -or $manifest.outputPixels[1] -ne 1080) {
    throw "Capture manifest does not match the production self-hosted 1080p30/32s specification: $manifestPath"
}
if ($frames.Count -ne 960) {
    throw "Expected 960 frames, found $($frames.Count): $FramesDirectory"
}
for ($i = 0; $i -lt 960; $i++) {
    $expectedName = 'frame_{0:D6}.jpg' -f $i
    if ($frames[$i].Name -ne $expectedName) {
        throw "Frame sequence mismatch at index $i; expected $expectedName, found $($frames[$i].Name)"
    }
}
if ([string]::IsNullOrWhiteSpace([string]$manifest.source) -or -not (Test-Path -LiteralPath $manifest.source -PathType Leaf)) {
    throw "Manifest source not found: $($manifest.source)"
}
$liveSourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifest.source).Hash
if ($liveSourceHash -ne [string]$manifest.sourceSha256) {
    throw "Manifest source hash does not match the live source: $($manifest.source)"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $outputName = 'S3_' + (-join @(0x4E09, 0x7EF4, 0x4F5C, 0x4E1A, 0x8F68, 0x8FF9 | ForEach-Object { [char]$_ })) + '_1080p_0714.mp4'
    $OutputPath = Join-Path 'F:\abb_wh_work\l4_showcase\out' $outputName
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    throw "Output directory not found: $outputDirectory"
}

$pattern = Join-Path $FramesDirectory 'frame_%06d.jpg'
$tempPath = Join-Path $outputDirectory (([IO.Path]::GetFileNameWithoutExtension($OutputPath)) + '.encoding.tmp.mp4')
$videoFilter = 'scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709'
$title = (-join @(0x667A, 0x50A8, 0x4F18, 0x63A7 | ForEach-Object { [char]$_ })) + ' ' + [char]0x00B7 + ' S3 ' + (-join @(0x4E09, 0x7EF4, 0x4F5C, 0x4E1A, 0x8F68, 0x8FF9, 0x56DE, 0x653E | ForEach-Object { [char]$_ }))

$encodeArgs = @(
    '-y', '-hide_banner', '-loglevel', 'warning',
    '-framerate', '30', '-i', $pattern,
    '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
    '-t', '32', '-map', '0:v:0', '-map', '1:a:0',
    '-vf', $videoFilter,
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
    '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-r', '30', '-g', '15', '-keyint_min', '15', '-sc_threshold', '0', '-bf', '2', '-flags', '+cgop', '-tag:v', 'avc1',
    '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
    '-movflags', '+faststart', '-metadata', "title=$title",
    $tempPath
)

& $Ffmpeg @encodeArgs
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg encode failed with exit code $LASTEXITCODE"
}

& $Ffmpeg -v error -i $tempPath -f null -
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg full decode failed with exit code $LASTEXITCODE; final file was not replaced"
}

Move-Item -Force -LiteralPath $tempPath -Destination $OutputPath
$item = Get-Item -LiteralPath $OutputPath
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath

[pscustomobject]@{
    Path = $item.FullName
    Frames = $frames.Count
    Bytes = $item.Length
    SHA256 = $hash.Hash
    DecodeExit = 0
}
