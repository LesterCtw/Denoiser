# Denoiser

專案狀態：第一版 Minimum Viable Solution（MVS）的產品範圍已定義。
這份 README 是目前專案狀態的 source of truth。

Denoiser 是一個簡單的 Windows desktop tool，讓 FA engineer 使用
`tk_r_em` ONNX models 還原 grayscale SEM/STEM images。

## 目前設定

- GitHub repo：`LesterCtw/Denoiser`
- Issue tracker：GitHub Issues
- Agent instructions：`AGENTS.md`
- Domain context：`CONTEXT.md`
- Architecture decisions：`docs/adr/`
- App icon：`assets/icons/denoiser_icon.png` 是 imagegen source artwork，
  `assets/icons/denoiser_icon.ico` 是 Windows build/runtime icon，
  `assets/icons/denoiser_icon.icns` 是 macOS local native-window icon；使用深色圓角
  icon style，僅保留置中的產品首字母，不放底部 wordmark。
- Windows build/package guide：`docs/windows-build-and-package.md`
- Pre-commit hooks：Husky 會執行 lint-staged Prettier 和 `uv run pytest`。

## Local development launch

在 macOS 或開發機上，可以直接用 `uv` 啟動目前的 NiceGUI native-window app：

```bash
uv sync
uv run denoiser
```

這個方式用來做 local development smoke test。正式 end-user release 仍以 Windows
PyInstaller packaged `Denoiser.exe` 為準。

Local dev icon behavior：

- Windows packaged release 使用 `assets/icons/denoiser_icon.ico` 作為 `Denoiser.exe` 和
  native window icon。
- macOS `uv run denoiser` 會把 `assets/icons/denoiser_icon.icns` 傳給 pywebview native
  app icon。macOS menu bar 在未封裝的 Python process 中仍可能顯示 `python3`；這是
  development launch 的限制，不代表 Windows release icon 沒有設定。

Initial ADRs 已補上，用來記錄第一版 MVS 的基礎架構決策：

- `docs/adr/0001-use-pyside6-for-windows-desktop-ui.md`
- `docs/adr/0002-bundle-onnx-models-for-offline-cpu-runtime.md`
- `docs/adr/0003-use-minimal-local-onnx-wrapper-instead-of-upstream-tk-r-em-runtime.md`
- `docs/adr/0004-use-nicegui-native-window-for-desktop-ui.md`

ADR 0004 supersedes ADR 0001。Implemented frontend 現在是 NiceGUI native
window，使用 standard Windows title bar，並以 repo `DESIGN.md` 作為 visual
source of truth。專案不再保留 PySide6 fallback，避免長期維護兩套 public frontend
stacks。Windows release path 仍維持 PyInstaller。

## 目前實作狀態

已實作：

- `src/denoiser` package layout 的專案骨架。
- NiceGUI native-window inspector frontend：啟動為 NiceGUI native window，
  顯示 Linear-style dark shell、left control rail、right work area、Single/Batch
  workflow switch、四個 denoising mode buttons、primary action area 和 pinned left
  status area；restore/batch processing 時，左下角 status text 和 animated progress
  bar 會填滿左側欄位可用寬度。
  NiceGUI restore parity 已完成。
- NiceGUI Single image selection and raw-only preview：Single mode 會透過
  NiceGUI native file dialog 選擇 image，執行 Single image inspection，顯示
  left-rail loading/selected/error status、overwrite warning、large-image warning，以及
  會填滿右側可用工作區高度的 fit-to-window raw-only preview。選圖後切換 denoising
  mode 時，UI overwrite target 會同步更新到新的 mode folder；restore 後若改選不同
  denoising mode，preview 會回到 raw-only view，避免沿用上一個 mode 的 comparison。
- NiceGUI Single restore and before/after comparison：Single mode 會使用現有
  Denoiser Single restore workflow 執行 Restore，自動寫入既有 output path，
  顯示 processing/saved/error status，restore 中停用衝突 controls，成功後顯示
  raw/restored before/after comparison、50% 初始 divider、click-to-jump 和 drag
  interaction。Single preview area 不顯示右側 heading，且 preview frame 會填滿右側可用高度。
- NiceGUI Batch folder selection and restore run：Batch mode 會透過 NiceGUI
  native folder dialog 選擇 folder，使用現有 Batch restore workflow 執行
  non-recursive restore run，顯示 progress、dense restored/skipped/failed per-file rows，
  active run 的 Cancel action、cancelled per-file rows，以及 final
  restored/failed/skipped/cancelled summary。
- NiceGUI 3 native folder selection compatibility：Batch `Add Folder` 使用
  pywebview folder `create_file_dialog` API，避免 NiceGUI `WindowProxy` 沒有
  `create_folder_dialog` 時 crash。
- App/window icon assets 已放在 `assets/icons/`，runtime 和 Windows build script 會使用同一個
  `.ico` icon。
- Runtime resource paths 已支援 source tree 和 PyInstaller frozen app；Windows
  onedir release 中的 bundled `assets`、`models`、`licenses` 會從 `_internal`
  讀取。
- 四個必要 ONNX model files 已放在 `models/`。
- Third-party notices 和 upstream `tk_r_em` GPL license copy。
- 支援 whole-image 和 patch-based inference 的最小 CPU ONNX inference wrapper。
- 使用 bundled ONNX models 的 Single-image restore workflow。
- Single mode UI：image selection、mode buttons、Restore、自動儲存、
  animated processing indicator、success/failure 狀態。
- Batch mode UI：folder selection、共用 mode buttons、Start Batch、progress、
  animated processing indicator、可捲動的 per-file status list。
- Batch mode status row rendering 已集中在 dedicated presentation module，讓 per-file
  status label、detail text、badge object names 的規則有單一維護位置。
- Single preview encoding/rendering 已集中在 dedicated presentation module，讓 raw preview
  與 before/after comparison 的 HTML contract 不再散落在 NiceGUI shell。
- Native file/folder selection 和 ONNX session factory 已有明確 seam，test adapters
  可替換 NiceGUI/pywebview dialogs 與 ONNX Runtime session。
- Batch cancellation between files、per-file failure isolation，以及 final
  restored/failed/skipped/cancelled summary counts。
- Batch mode 會在 restore workflow 建立前拒絕 selected `denoised_*` folder，
  避免把已輸出的 folder 當成新的 Batch input。
- Single mode preview：選圖後顯示 raw-only preview；restore 後顯示 raw/restored
  before/after compare view、50% 初始 divider、drag interaction、click-to-jump
  interaction；restore 後切換到不同 denoising mode 會清掉 comparison，回到 raw-only
  preview。
- Single mode image selection：使用 Single image inspection module 在 background
  thread 執行 preview inspection，讓 UI 可以先顯示 loading/status，不必等 image
  load 和 large-image 判斷完成。
- 第一版支援格式的 image I/O boundary。
- TIFF single-2D validation 已集中在 image I/O boundary，同一組 multi-page/stack-like
  rejection rules 同時服務 image dimensions inspection 和 full image loading。
- 使用獨立 output path rules module 管理 `denoised_MODE` folders、output suffix、
  overwrite target，以及 `denoised_*` input rejection。
- Output dtype/range preparation：clip 到原圖 min/max，避免 automatic contrast
  stretching。
- Large-image patch-based restore path，預設 `patch_size=512`、`stride=256`、
  `batch_size=2`，並在 Single mode 顯示處理可能需要數分鐘的 warning。
- Conservative metadata preservation：TIFF 保留 safe standard metadata，PNG 保留
  safe text metadata；unsupported metadata 會保守跳過，DM3/DM4 不承諾完整 metadata parity。
- Windows build script 會明確包含 RosettaSciIO DM3/DM4 reader 的 lazy-loaded
  `rsciio.utils._distributed` module，以及 RosettaSciIO dependency 中可能不會被 app
  直接 import 的 `pint`、`yaml`，避免 PyInstaller frozen app 讀取 `.dm3` / `.dm4`
  時漏掉 runtime dependency。
- Windows release dependency flow 已改為 NiceGUI native window stack：release build
  安裝 `nicegui` 和 `pywebview`，不再要求 PySide6 作為 dependency。Build script
  也會用 `--collect-data nicegui` 包含 NiceGUI frontend package data。
- Windows build script 支援 `.\scripts\build_windows.ps1 -Console` diagnostic build；
  如果 packaged `Denoiser.exe` 啟動後立刻關閉，可以用 console build 從 PowerShell
  執行 exe，取得 startup traceback。正式 release 預設仍使用無 console 的
  `--windowed` build。
- 提供 `scripts/check_dm3_pyinstaller_imports.py` 作為 DM3/DM4 PyInstaller import-chain
  probe；它會建立一個最小 frozen executable 並執行，確認 RosettaSciIO DM reader 的必要
  imports 在 frozen app 中可載入。
- Focused tests：app icon resource path、model mapping、missing model handling、whole-image inference、
  patch-based inference、Single restore workflow、Batch restore workflow、
  Batch presentation mapping、Single preview presentation mapping、
  NiceGUI Single UI restore behavior、Single restore processing status transition、
  NiceGUI Single/Batch processing state behavior、
  readable Single/Batch status output、full-width left-rail processing status layout、
  NiceGUI Batch UI progress/status behavior、
  unclipped Batch per-file status rows、
  Single image inspection behavior、output naming、Batch restore runner orchestration、
  NiceGUI before/after comparison state and rendering contract、Single mode-change
  overwrite target synchronization、Single restore-after mode-change raw preview reset、
  denoised-folder rejection、Batch selected denoised-folder blocking、
  unsupported-input rejection、multi-page TIFF rejection、Windows build script
  RosettaSciIO hidden import guard、batch cancellation、
  batch failure isolation、JPEG-to-TIFF output、PNG/TIFF output preservation、
  Batch result row state formatting、RGB/RGBA-to-grayscale conversion、overwrite behavior、
  uint16 TIFF clipping、
  conservative TIFF/PNG metadata preservation。

尚未實作：

- Windows release build verification。

## 第一版 MVS 範圍

- Desktop frontend direction：NiceGUI native window
- Target platform：Windows 10/11 laptop PCs
- Runtime：CPU only
- Distribution：folder-style Windows release，包含 `Denoiser.exe`
- App icon：使用 `assets/icons/denoiser_icon.ico`
- Offline use：必要；bundled ONNX models 會 commit 到此 repo 並一起打包進 release
- Product name / brand：`Denoiser`
- UI language：English
- Development dependency manager：`uv`
- Windows build/deployment dependency install path：`pip install`
- Release build platform：在 Windows 上建立 Windows release

## Engine integration

Denoiser 會使用最小本地 engine wrapper，實作必要的 `tk_r_em` inference behavior，
而不是在 runtime 依賴完整 upstream package。

第一版只包含四個必要 ONNX models：

- `sfr_hrstem`
- `sfr_lrstem`
- `sfr_hrsem`
- `sfr_lrsem`

完整的 `tk_r_em` Streamlit app、tutorials、sample datasets、TEM models 不屬於
runtime app。

因為 `tk_r_em` 是 GPL-3.0-only，Denoiser 必須在 source 和 release package 中保留
相關 license 與 attribution notices。

四個必要 ONNX model files 會追蹤在此 repository，因此 developer clone repo 後可以
不另外下載 model 也能建立 release。

## Windows build and packaging

Windows build target：

- Windows 10/11
- Python 3.12.8 64-bit
- PowerShell
- Standard `pip install` flow
- Source code 可用 GitHub ZIP download；公司環境不需要 `git`

完整建置與打包步驟記錄在
`docs/windows-build-and-package.md`。

預期 package flow：

1. Developer 在 Windows machine 下載 GitHub source ZIP，或在可用時 clone 此 repository。
2. Developer 確認 `assets\icons\denoiser_icon.ico` 存在。
3. Developer 使用 Python 3.12.8 建立 `.venv`。
4. Developer 使用逐一 `pip install` commands 安裝 dependencies，方便定位公司網路或
   package install failure。
5. Developer 執行 `.\scripts\build_windows.ps1`。
6. Build script 產生 folder-style release，內含帶有 app icon 的 `Denoiser.exe`、
   `_internal` runtime folder、dependencies、licenses、bundled model files、
   bundled icon asset。
7. 如果 exe 啟動後立刻關閉，Developer 執行
   `.\scripts\build_windows.ps1 -Console` 產生 diagnostic console build，然後從
   PowerShell 執行 `.\dist\Denoiser\Denoiser.exe` 讀取 traceback。
8. Developer 將 `dist\Denoiser` 壓縮成 release zip。
9. FA engineers 只收到 release folder 或 zip，並執行 `Denoiser.exe`。

End users 不需要 Python、`uv` 或 `pip`。

Windows release 的人工驗證步驟記錄在
`docs/windows-release-verification.md`。

Build script 會額外傳入 `--hidden-import rsciio.utils._distributed`、`--hidden-import pint`
和 `--hidden-import yaml`。原因是 RosettaSciIO 的 DM3/DM4 reader 會透過 lazy import 使用
部分 module；一般 Python 執行可以正常載入，但 PyInstaller frozen app 需要明確指定，
否則 `.dm3` / `.dm4` 讀取可能在 runtime 失敗。

若要在 build machine 上先檢查 DM3/DM4 reader 的 frozen import chain：

```powershell
python .\scripts\check_dm3_pyinstaller_imports.py
```

## Repository layout

```text
Denoiser/
  pyproject.toml
  uv.lock
  requirements.txt
  README.md
  CONTEXT.md
  DESIGN.md
  licenses/
    THIRD_PARTY_NOTICES.md
    tk_r_em_LICENSE.txt
  assets/
    icons/
      denoiser_icon.png
      denoiser_icon.icns
      denoiser_icon.ico
  models/
    sfr_hrsem.onnx
    sfr_hrstem.onnx
    sfr_lrsem.onnx
    sfr_lrstem.onnx
  scripts/
    build_windows.ps1
  docs/
    adr/
      0001-use-pyside6-for-windows-desktop-ui.md
      0002-bundle-onnx-models-for-offline-cpu-runtime.md
      0003-use-minimal-local-onnx-wrapper-instead-of-upstream-tk-r-em-runtime.md
      0004-use-nicegui-native-window-for-desktop-ui.md
    windows-build-and-package.md
    windows-release-verification.md
  src/
    denoiser/
      __init__.py
      __main__.py
      app.py
      app_icon.py
      batch_presentation.py
      engine.py
      image_io.py
      models.py
      nicegui_shell.py
      output_paths.py
      preview_presentation.py
      single_image_inspection.py
      workflow.py
  tests/
    test_app_entrypoint.py
    test_app_icon.py
    test_batch_presentation.py
    test_batch_workflow.py
    test_documentation_contract.py
    test_engine.py
    test_image_io.py
    test_nicegui_shell.py
    test_output_paths.py
    test_preview_presentation.py
    test_single_image_inspection.py
    test_single_workflow.py
    test_windows_build_script.py
```

## Denoising modes

第一版只包含 SEM 和 STEM modes。TEM 會刻意排除。

| UI label | tk_r_em model tag | Output folder     |
| -------- | ----------------- | ----------------- |
| `HRSTEM` | `sfr_hrstem`      | `denoised_HRSTEM` |
| `LRSTEM` | `sfr_lrstem`      | `denoised_LRSTEM` |
| `HRSEM`  | `sfr_hrsem`       | `denoised_HRSEM`  |
| `LRSEM`  | `sfr_lrsem`       | `denoised_LRSEM`  |

UI 會把這四個 modes 顯示為 buttons，而不是 dropdown。

## Workflow

App 有兩個 modes，使用 buttons 切換：

- `Single`
  - 開啟一張 image。
  - 選擇一個 denoising mode。
  - 點擊 `Restore`。
  - 結果會自動儲存。
  - 右側顯示 fit-to-window before/after slider。
- `Batch`
  - 使用 `Add Folder` 選擇一個 folder。
  - 只掃描 selected folder 內的 files；不掃描 subfolders。
  - 選擇一個 denoising mode。
  - 點擊 `Start Batch`。
  - 右側顯示 progress 和可橫向捲動的 per-file status list。

Layout：

- 左側：controls、file/folder selection、mode buttons、primary action，以及底部 status/warnings；
  restore 或 batch 執行中會在底部 status area 顯示 animated progress bar。
- 右側：
  - Single mode：選圖後顯示 raw-only preview；restore 後顯示 before/after
    comparison，不顯示額外 heading。
  - Batch mode：右側 heading 顯示 `Batch Restore`，下方顯示 progress 和 dense
    per-file list；清單會填滿 Preview 高度，先往下排列，滿高後換到下一個
    column，檔案很多時只往橫向捲動；不顯示 image preview。

## Image comparison behavior

- Preview 一律把整張 image fit 到可用的右側區域。
- 第一版不包含 zoom、pan、crop、rotate、brightness、contrast、histogram 或
  image-editing tools。
- 選圖後的 raw-only preview 不顯示 before/after slider。
- Restore 後的 before/after slider 從 50% 開始。
- Comparison 左側顯示 raw image，右側顯示 restored image。
- Divider/handle 使用低白邊重量、高對比的 visual treatment，讓它在 dark、
  light、mid-gray grayscale 區域仍可辨識。
- 拖曳 divider 會移動 comparison position，且位置會限制在實際 fit-to-window image
  area，不會跑到 preview frame 的空白 padding。
- 點擊 image 任意位置會讓 slider 跳到該位置。
- Preview display normalization 只允許用於螢幕顯示，不得影響 saved output files。

## Input and output formats

第一版 input formats：

- `.tif`
- `.tiff`
- `.png`
- `.jpg`
- `.jpeg`
- `.dm3`
- `.dm4`

第一版刻意排除的 formats：

- `.ser`
- `.emd`
- `.bmp`
- `.mrc`
- `.raw`

Output rules：

| Input            | Output              |
| ---------------- | ------------------- |
| `.tif` / `.tiff` | Same extension      |
| `.png`           | `.png`              |
| `.jpg` / `.jpeg` | `.tif`              |
| `.dm3` / `.dm4`  | 32-bit float `.tif` |

一般 image formats 的 output 應盡可能保留原始 bit depth。Model processing 內部可使用
`float32`，但 saved output 不得使用 automatic contrast stretching、histogram
equalization 或 min/max rescaling。如果 model output 超出原圖實際 value range，儲存前
會 clip 到原圖 min/max。

RGB/RGBA inputs 可接受，但會轉成 grayscale 供 model processing。Alpha channels 不會保留。

Metadata 應在安全可行時保留。對無法安全寫回的 formats，尤其 `.dm3` 和 `.dm4`，
output 會寫成 TIFF；只有在安全時，才把可用 metadata 帶入 TIFF metadata 或相鄰 sidecar。

MVS metadata policy 採保守策略：盡可能保留 safe standard metadata，但絕不為了強迫
metadata round-tripping 而冒著 corrupt output image 的風險。完整 `.dm3` / `.dm4`
metadata parity 不是第一版需求。

第一版會拒絕 multi-page TIFF 和 stack-like data。每個 input file 只支援一張 single
2D image。

## Saving behavior

Single 和 Batch 使用相同的 saving concept：

- Output 寫入原始 image 旁邊、對應 mode 的 subfolder。
- Output filename 保持相同，除非 output format 改變。
- Existing files 會被 overwrite。
- Original raw files 不會複製到 output folder。

Examples：

- `D:\caseA\wafer01.tif` with `HRSTEM` ->
  `D:\caseA\denoised_HRSTEM\wafer01.tif`
- `D:\caseA\wafer01.jpg` with `HRSEM` ->
  `D:\caseA\denoised_HRSEM\wafer01.tif`

如果 output filenames collision，後產生的 output 會 overwrite 前一個 output。
UI 應清楚顯示 overwrite behavior。

App 必須拒絕位於任何 `denoised_*` folder 裡的 input，避免不小心再次 denoise 已處理過的
output。

## Processing behavior

App 應自動選擇 inference strategy：

- Longest image side `<= 1536 px`：whole-image inference
- Longest image side `> 1536 px`：patch-based inference
- Windows CPU laptops 的 patch-based settings：
  - `patch_size=512`
  - `stride=256`
  - `batch_size=2`

Large images 不會只因尺寸被 blocked，但 UI 應警告 processing 可能需要數分鐘。

Single 和 Batch restore processing 期間，左側會顯示 animated indeterminate
processing indicator。這個 indicator 只代表 app 正在處理，不代表百分比或剩餘時間。

Cancellation：

- Single mode：沒有 cancel button；processing 時 controls 會 disabled。
- Batch mode：支援在 files 之間 cancel。Current file 會先完成，接著 batch 停止。

## Batch behavior

- Batch mode 只支援 `Add Folder`。
- Selected folder 會 non-recursively scan。
- Unsupported files 會 skipped，並顯示在 on-screen status list。
- On-screen status list 會依 Preview 視窗高度自動分欄，避免檔案多時往下垂直捲動。
- Unexpected per-file restore failures 會回報為 failed，不會停止後續仍可安全處理的 files。
- Cancelling batch 會把 remaining files 標成 cancelled，並保留已寫出的 outputs。
- Final batch status 會 summary restored、failed、skipped、cancelled counts。
- 第一版不產生 CSV log。
- 如果 selected folder name 以 `denoised_` 開頭，batch processing 會被 blocked。

## Design direction

UI 應遵循 repo `DESIGN.md`，這是目前 frontend visual direction 的 source of truth。

Implemented frontend 是 NiceGUI native window，並保留 standard Windows title bar。
專案維持 no PySide6 fallback。

對這個 desktop tool 的實務解讀：

- Fixed dark UI，讓 image inspection 時周邊 chrome 保持低干擾。
- Minimal chrome。
- Blue 作為 main action color。
- Controls 在適當處使用 rounded style。
- 避免會干擾 image inspection 的 decorative effects。

## Known constraints and trade-offs

- `tk_r_em` 採 GPL-3.0-only，因此第一目標是 internal company use。
- App 使用 local minimal engine wrapper，而不是完整 upstream `tk_r_em` package，讓 desktop
  release 更小且更容易控制。
- `tk_r_em` 適用於 2D grayscale EM-style images。第一版不支援 stacks、multi-page TIFF、
  3D volume 或 4D STEM data。
- 有些 microscope-native formats 在可用 IO libraries 中是 read-only，因此 `.dm3` 和
  `.dm4` 會 export as TIFF。
- CPU-only inference 比 GPU inference 慢，但對第一版 Windows laptop release 來說更簡單、
  更可靠。
- 不包含 image adjustment tools，避免改變工程影像判讀。

## Test data strategy

Development machine 上沒有真實公司 FA image data。第一版 validation 使用 synthetic images
和任何可安全使用、不暴露公司資料的 upstream sample data。等未來有具代表性且不敏感的資料後，
再加入 real FA image regression cases。
