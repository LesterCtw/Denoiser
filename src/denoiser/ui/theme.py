"""Shared stylesheet for the PySide6 UI."""

from __future__ import annotations


def main_window_stylesheet() -> str:
    return """
    QMainWindow {
        background: #111214;
        color: #f2f3f5;
        font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
        font-size: 14px;
    }

    #Sidebar {
        background: #181a1f;
        border-right: 1px solid #2c3038;
    }

    #PreviewArea {
        background: #101114;
    }

    #Title {
        color: #f6f7f9;
        font-size: 28px;
        font-weight: 600;
    }

    #SectionLabel {
        color: #aeb4be;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }

    #StatusCard {
        border: 1px solid #303641;
        border-radius: 8px;
        background: #12151a;
    }

    #StatusTitle {
        color: #f2f4f8;
        font-size: 15px;
        font-weight: 650;
    }

    #StatusDetails {
        color: #c9d0db;
        font-size: 13px;
        font-weight: 500;
        line-height: 135%;
    }

    #ProcessingIndicator {
        min-height: 6px;
        max-height: 6px;
        border: none;
        border-radius: 3px;
        background: #2c3038;
    }

    #ProcessingIndicator::chunk {
        border-radius: 3px;
        background: #2f80ed;
    }

    QPushButton {
        min-height: 36px;
        padding: 8px 14px;
        border: 1px solid #3a3f49;
        border-radius: 8px;
        background: #23262d;
        color: #eef1f5;
    }

    QPushButton:hover {
        border-color: #596170;
        background: #2a2e36;
    }

    QPushButton:checked {
        border-color: #2f80ed;
        color: #ffffff;
        background: #1d3f6e;
    }

    QPushButton:disabled {
        border-color: #2b2f36;
        background: #1b1d22;
        color: #737b87;
    }

    #PrimaryButton {
        border: none;
        border-radius: 18px;
        background: #2f80ed;
        color: #ffffff;
        font-weight: 600;
    }

    #PrimaryButton:hover {
        background: #4a90f3;
    }

    #PrimaryButton:disabled {
        background: #24415f;
        color: #8fa7c5;
    }

    #CompareView {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #15171b;
        color: #aeb4be;
    }

    #BatchPanel {
        background: #15171b;
    }

    #BatchProgress {
        color: #f2f3f5;
        font-size: 20px;
        font-weight: 600;
    }

    #BatchList {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #111318;
        color: #e4e7ec;
        font-size: 15px;
        padding: 8px;
    }

    #BatchList::item {
        border: none;
        margin: 0 0 8px 0;
        padding: 0;
    }

    #BatchResultItem {
        border: 1px solid #2a303a;
        border-radius: 8px;
        background: #151820;
    }

    #BatchFileName {
        color: #f1f4f8;
        font-size: 15px;
        font-weight: 650;
    }

    #BatchFileDetail {
        color: #aeb7c4;
        font-size: 13px;
        font-weight: 500;
    }

    #BatchStatusRestored,
    #BatchStatusSkipped,
    #BatchStatusFailed,
    #BatchStatusCancelled {
        min-width: 76px;
        min-height: 24px;
        padding: 4px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: 650;
    }

    #BatchStatusRestored {
        color: #d8f5e3;
        background: #1d5b38;
    }

    #BatchStatusSkipped {
        color: #d8dde6;
        background: #38404d;
    }

    #BatchStatusFailed {
        color: #ffe0e0;
        background: #743030;
    }

    #BatchStatusCancelled {
        color: #ffe8bd;
        background: #6b4b18;
    }
    """
