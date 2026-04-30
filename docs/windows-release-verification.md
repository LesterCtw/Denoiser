# Windows Release Verification

這份 checklist 用來驗證第一版 Denoiser MVS 是否能作為 folder-style Windows release 使用。
這是刻意保留的人工作業，因為最終 acceptance criteria 需要在真實 Windows 10/11 machine 上驗證。

## 目標

FA engineer 可以收到一個 release folder，在 offline 狀態執行 `Denoiser.exe`，還原一張小型
supported image，並取得預期 output；end user 不需要安裝 Python、`uv` 或 `pip`。

## 已知限制

- Build verification 必須在 Windows 10 或 Windows 11 上執行。
- Build machine 可以使用 Python 和 `pip`。
- End-user smoke test 只能使用 release folder。
- 不需要敏感的公司 FA image data。請使用 synthetic 或安全的 non-sensitive 2D grayscale image。
- 第一版不要求在單次 model inference call 中途 cancel。

## Build Machine Prerequisites

- Windows 10 或 Windows 11。
- 與 `pyproject.toml` 相容的 Python。
- 可連網安裝 build dependencies。
- 此 repository 的 fresh checkout 或下載副本。

## Build Steps

在 PowerShell 執行：

```powershell
cd path\to\Denoiser
.\scripts\build_windows.ps1
```

預期結果：

- `dist\Denoiser\Denoiser.exe` 存在。
- Script 完成且沒有 errors。

## Release Folder Inspection

檢查 `dist\Denoiser`。

Pass criteria：

- `Denoiser.exe` 存在。
- Release folder 包含 PyInstaller 產生的 runtime dependency files。
- Release folder 包含以下 model files：
  - `models\sfr_hrstem.onnx`
  - `models\sfr_lrstem.onnx`
  - `models\sfr_hrsem.onnx`
  - `models\sfr_lrsem.onnx`
- Release folder 包含 license notices：
  - `licenses\THIRD_PARTY_NOTICES.md`
  - `licenses\tk_r_em_LICENSE.txt`

## End-User Launch Test

如果可行，使用乾淨的 Windows 10/11 user environment。

步驟：

1. 只複製 `dist\Denoiser` folder 到測試位置。
2. 中斷網路或關閉 Wi-Fi。
3. 這個 user test 不要安裝 Python、`uv` 或 `pip`。
4. 執行 `Denoiser.exe`。

Pass criteria：

- App launches，不要求 Python、`uv`、`pip` 或 internet access。
- Main window 開啟。
- UI 保持可讀，並符合既有 clean desktop direction。

## Single Restore Smoke Test

使用一張 longest side 不超過 `1536 px` 的 small 2D grayscale image。

步驟：

1. 在 Single mode 點擊 `Open Image`。
2. 選擇 smoke-test image。
3. 選擇一個 mode，例如 `HRSTEM`。
4. 點擊 `Restore`。

Pass criteria：

- App 顯示 successful save。
- Output 出現在 input 旁邊正確的 mode folder，例如 `denoised_HRSTEM`。
- Output file 可用標準 image viewer 或 inspection tool 開啟。
- Restore 過程不需要 network access。
- Before/after compare view 在 restore 後更新。

## Offline Retest

在 machine 沒有 network connection 時，重複 launch 和 Single restore smoke test。

Pass criteria：

- Launch 仍可正常運作。
- Restore 仍可正常運作。
- 沒有嘗試下載 model 或 dependency。

## Failure Notes

任何 failure 都請記錄：

- Windows version。
- Build machine 使用的 Python version。
- 失敗的 exact command。
- Error message 或 screenshot。
- Failure 發生在 build、launch 或 restore 哪個階段。
- Machine 當時是 online 或 offline。

## Verification Record Template

```markdown
## Windows Release Verification Record

- Date:
- Tester:
- Windows version:
- Build machine Python version:
- Commit:
- Release folder path:

### Results

- Build script created `Denoiser.exe`: pass/fail
- Runtime dependencies included: pass/fail
- Four ONNX models included: pass/fail
- License notices included: pass/fail
- Launch without Python/uv/pip for end user: pass/fail
- Small Single restore smoke test: pass/fail
- Offline launch and restore: pass/fail
- README updated with verified status: pass/fail

### Notes

-
```
