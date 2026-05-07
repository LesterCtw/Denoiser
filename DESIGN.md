---
version: alpha
name: Denoiser Desktop
description: "A fixed dark desktop inspection interface for restoring grayscale SEM/STEM images. The product should feel quiet, technical, and low-distraction: left-side controls, a large image work area, clear status feedback, and no marketing-page chrome."

colors:
  primary: "#5e6ad2"
  on-primary: "#ffffff"
  primary-hover: "#7883e6"
  primary-focus: "#5e69d1"
  ink: "#f7f8f8"
  ink-muted: "#d0d6e0"
  ink-subtle: "#8a8f98"
  ink-tertiary: "#62666d"
  canvas: "#010102"
  surface-1: "#0f1011"
  surface-2: "#141516"
  surface-3: "#18191a"
  hairline: "#23252a"
  hairline-strong: "#34343a"
  semantic-success: "#27a644"
  semantic-warning: "#c9a227"
  semantic-error: "#d94f4f"

typography:
  shell-title:
    fontFamily: Inter, SF Pro Display, Segoe UI, sans-serif
    fontSize: 21px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0
  section-label:
    fontFamily: Inter, SF Pro Display, Segoe UI, sans-serif
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0
  button:
    fontFamily: Inter, SF Pro Display, Segoe UI, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0
  work-title:
    fontFamily: Inter, SF Pro Display, Segoe UI, sans-serif
    fontSize: 26px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0
  status:
    fontFamily: Inter, SF Pro Display, Segoe UI, sans-serif
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0

layout:
  app-window:
    defaultSize: 1280x820
    titleBar: standard
    fullscreen: false
    frameless: false
  control-rail:
    width: 304px
    padding: 22px
    placement: left
  work-area:
    placement: right
    padding: 26px 28px 28px
  preview-frame:
    borderRadius: 8px
    border: 1px solid "{colors.hairline}"
  button-radius: 8px
---

## Purpose

`DESIGN.md` 是 Denoiser frontend 的 visual source of truth。它描述的是
Windows desktop inspection tool，不是 marketing site、landing page 或 web dashboard。

目標使用者是 FA engineer。UI 應該讓使用者快速選圖、選 denoising mode、restore，
並檢查 raw/restored difference。介面要安靜、清楚、低干擾。

## Product Shape

- App 是 NiceGUI native window，保留 standard Windows title bar。
- 第一版固定走 dark UI，避免 image inspection 時周邊 chrome 太亮。
- App 主體分成 left control rail 和 right work area。
- Left rail 放 workflow switch、file/folder selection、mode buttons、primary action、
  status、warnings 和 processing indicator。
- Right work area 在 Single mode 顯示 raw preview 或 before/after comparison。
- Right work area 在 Batch mode 顯示 progress 和 per-file result list，不顯示 image preview。

## Visual Principles

- Keep chrome quiet：不要加入 decorative gradients、hero sections、marketing cards、
  large illustrations 或多餘說明文字。
- Prioritize inspection：preview frame 是主要工作區，尺寸要穩定，圖片要 fit-to-window。
- Make status obvious：processing、saved、failed、skipped、cancelled 狀態要容易掃描。
- Keep controls predictable：mode 用 buttons，不用 dropdown；Batch cancel 只在 active run
  期間出現。
- Use blue sparingly：`primary` 只用於 primary action、selected state、focus 或 warning emphasis。

## Color Usage

- `canvas`：整體 app background 和右側 work area。
- `surface-1`：left control rail、preview placeholder、Batch list container。
- `surface-2`：secondary buttons、idle mode buttons、idle workflow buttons。
- `surface-3`：selected workflow/mode button background、progress track。
- `primary`：Restore button、selected border、progress indicator、important warning text。
- `ink`：主要標題和重要文字。
- `ink-muted`：status、metadata、detail text。
- `ink-subtle`：empty state 或低優先級文字。

## Typography

使用 `Inter, SF Pro Display, Segoe UI, sans-serif`。所有 app text 的
`letter-spacing` 保持 `0`，避免小尺寸 desktop UI 變得難讀。

- Product title：21px / 600。
- Work title：26px / 600，只在 Batch work area 顯示 `Batch Restore`。
- Buttons：14px / 500。
- Status、warnings、Batch details：12px 到 13px。

## Components

### Workflow Switch

- 位置：left rail 上方。
- 選項：`Single`、`Batch`。
- 形式：two-button segmented control。
- Processing 期間 disabled，避免 workflow state 在 restore 中被切換。

### Path Actions

- Single mode 使用 `Open Image`。
- Batch mode 使用 `Add Folder`。
- Buttons 使用 secondary style。
- Native file/folder dialog detail 由 NiceGUI / pywebview adapter 負責。

### Mode Buttons

- 四個 vertical buttons：`HRSTEM`、`LRSTEM`、`HRSEM`、`LRSEM`。
- Selected mode 使用 `surface-3` background 和 `primary` border。
- 不使用 dropdown，因為四個選項固定且需要快速切換。

### Primary Action

- Label：`Restore`。
- 使用 `primary` background。
- Single restore 和 Batch restore 共用同一個 primary action concept。
- Batch active run 時改顯示 `Cancel` secondary action。

### Status Area

- 固定在 left rail 底部。
- Processing 時顯示 indeterminate progress bar。
- Status text 可以換行，避免長 output path 撐破 control rail。
- Warning text 使用 `primary`，但不要加入 additional alert panels。

### Single Preview

- 選圖後顯示 raw-only preview。
- Restore 後顯示 raw/restored before-after comparison。
- Comparison 初始 divider 為 50%。
- Raw image 在左側，restored image 在右側。
- Divider 可 drag，也可 click-to-jump。
- Preview normalization 只可用於螢幕顯示，不得影響 saved output。

### Batch Results

- 顯示 progress，例如 `3 of 10 files`。
- Per-file rows 要 dense、可橫向捲動，避免長清單把畫面往下推。
- 只顯示 image inputs 的 rows；一般 `.txt`、`.csv`、`.json` 這類非影像檔案不用顯示。
- Status labels 使用 `Restored`、`Skipped`、`Failed`、`Cancelled`。

## Responsive Scope

第一版 target 是 Windows 10/11 laptop desktop app，不設計 mobile layout。

目前 native window default size 是 `1280x820`。Layout 應在這個尺寸附近保持穩定：

- Left rail 固定寬度。
- Work area 填滿剩餘空間。
- Preview frame 不因圖片、status 或 button text 改變而跳動。

## Do

- 使用 dark, low-distraction shell。
- 保持 controls 和 status 集中在 left rail。
- 保持 image preview area 最大化。
- 使用穩定尺寸，避免 restore 前後 layout shift。
- 用簡短 English UI labels，符合第一版 UI language scope。

## Don't

- 不要把 app 做成 landing page。
- 不要加入 top nav、pricing cards、footer、testimonial、customer logo marquee。
- 不要加入 decorative gradients、orbs、spotlight cards 或 marketing screenshots。
- 不要新增 light mode，除非產品 scope 明確改變。
- 不要加入 image adjustment tools，第一版不支援 brightness、contrast、histogram、
  zoom、pan、crop、rotate。
