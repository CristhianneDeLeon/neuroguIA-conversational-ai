# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import html
import os
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------------------------------------
# PATH SETUP
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import initialize_database, load_env_file
from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from memory.profile_manager import ProfileManager


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
DEFAULT_DB_PATH = str(PROJECT_ROOT / "neuroguia.db")
DEFAULT_ENV_PATH = str(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="neuroguIA",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------
# ESTILOS UI
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --ng-bg: #fbf6f1;
        --ng-surface: #ffffff;
        --ng-surface-soft: #fdf9f5;
        --ng-border: #eadfd4;
        --ng-border-soft: #f2e9e0;
        --ng-primary: #b86e54;
        --ng-primary-soft: #f7ebe5;
        --ng-primary-soft-2: #fdf5f0;
        --ng-text: #2f241f;
        --ng-subtext: #73655d;
        --ng-shadow-sm: 0 10px 24px rgba(110, 71, 53, 0.06);
        --ng-shadow-md: 0 18px 40px rgba(110, 71, 53, 0.08);
    }

    html, body, [class*="css"] {
        font-family: "Manrope", "Aptos", "Segoe UI", sans-serif;
        color: var(--ng-text);
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(203, 146, 116, 0.12), transparent 28%),
            radial-gradient(circle at top right, rgba(241, 217, 201, 0.28), transparent 22%),
            linear-gradient(180deg, #fffdfa 0%, var(--ng-bg) 100%);
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
    }

    div[data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0 !important;
        position: fixed !important;
    }

    #MainMenu, footer {
        visibility: hidden !important;
    }

    .block-container {
        max-width: 1240px;
        padding-top: 0.9rem;
        padding-bottom: 1.85rem;
    }

    .ng-page {
        max-width: 1160px;
        margin: 0 auto;
    }

    .ng-layout-grid {
        margin-top: 0.2rem;
    }

    .ng-card,
    .ng-side-card,
    .ng-quick-card,
    .ng-panel,
    .ng-panel-secondary,
    .ng-conversation-card,
    .ng-composer-shell {
        background: var(--ng-surface);
        border: 1px solid var(--ng-border);
        box-shadow: var(--ng-shadow-sm);
    }

    .ng-side-card,
    .ng-quick-card {
        border-radius: 24px;
        padding: 1rem;
        height: fit-content;
    }

    .ng-side-card {
        background: linear-gradient(180deg, #ffffff 0%, #fdf8f4 100%);
        padding: 0.95rem 0.95rem 0.9rem 0.95rem;
    }

    .ng-logo-full {
        margin-bottom: 0.8rem;
    }

    .ng-logo-full-image {
        width: 160px;
        max-width: 100%;
        display: block;
    }

    .ng-logo-wordmark {
        font-size: 1.45rem;
        font-weight: 800;
        color: var(--ng-text);
        letter-spacing: -0.03em;
        margin-bottom: 0.12rem;
    }

    .ng-sidebar-title {
        margin: 0;
        font-size: 1.02rem;
        font-weight: 780;
        color: var(--ng-text);
        line-height: 1.25;
    }

    .ng-sidebar-summary {
        margin: 0 0 0.72rem 0;
        display: flex;
        flex-direction: column;
        gap: 0.36rem;
    }

    .ng-sidebar-summary p {
        margin: 0;
        padding: 0.52rem 0.68rem;
        border-radius: 14px;
        background: var(--ng-primary-soft-2);
        border: 1px solid #ece4fb;
        color: var(--ng-subtext);
        font-size: 0.85rem;
        line-height: 1.4;
    }

    .ng-side-note {
        margin: 0 0 0.72rem 0;
        color: var(--ng-subtext);
        font-size: 0.85rem;
        line-height: 1.5;
    }

    .ng-header {
        padding: 0 0 0.95rem 0;
        text-align: center;
    }

    .ng-header-inner {
        max-width: 920px;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        border: 1px solid var(--ng-border-soft);
        border-radius: 28px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(253, 247, 242, 0.96) 100%);
        padding: 1rem 1.15rem 1.05rem 1.15rem;
        box-shadow: var(--ng-shadow-md);
    }

    .ng-brand-line {
        display: inline-flex;
        align-items: center;
        gap: 0.62rem;
        justify-content: center;
        margin-bottom: 0.42rem;
    }

    .ng-brand-logo {
        width: 42px;
        height: 42px;
        border-radius: 13px;
        overflow: hidden;
        background: var(--ng-primary-soft);
        border: 1px solid var(--ng-border);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .ng-brand-logo img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .ng-brand-fallback {
        font-size: 1.2rem;
        line-height: 1;
    }

    .ng-brand-title {
        margin: 0;
        font-size: 1.46rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.05;
        color: var(--ng-text);
    }

    .ng-sidebar-title-row {
        display: flex;
        align-items: center;
        gap: 0.48rem;
        margin-bottom: 0.45rem;
    }

    .ng-side-title-icon,
    .ng-section-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.1rem;
        height: 1.1rem;
        color: var(--ng-primary);
        line-height: 1;
        flex: 0 0 auto;
    }

    .ng-header-subtitle,
    .ng-header-line {
        margin: 0;
        color: var(--ng-subtext);
        max-width: 760px;
        font-size: 0.92rem;
        line-height: 1.6;
    }

    .ng-header-subtitle + .ng-header-subtitle,
    .ng-header-line + .ng-header-line {
        margin-top: 0.28rem;
    }

    .ng-top-grid {
        margin-top: 0.4rem;
        margin-bottom: 1.2rem;
    }

    .ng-panel {
        border-radius: 20px;
        padding: 1.08rem 1.12rem 1.05rem 1.12rem;
    }

    .ng-panel-secondary {
        background: linear-gradient(180deg, #ffffff 0%, #fdf8f5 100%);
        border: 1px solid var(--ng-border-soft);
        border-radius: 20px;
        padding: 1.08rem 1.02rem 1.05rem 1.02rem;
        display: flex;
        flex-direction: column;
        gap: 0.82rem;
        min-height: 100%;
    }

    .ng-panel-title {
        margin: 0;
        font-size: 1.01rem;
        font-weight: 750;
        color: var(--ng-text);
    }

    .ng-panel-title-row {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin-bottom: 0.8rem;
    }

    .ng-panel-icon {
        font-size: 1rem;
        line-height: 1;
    }

    .ng-context-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.36rem 0.72rem;
        border-radius: 999px;
        background: var(--ng-primary-soft);
        border: 1px solid var(--ng-border);
        color: var(--ng-primary);
        font-size: 0.79rem;
        font-weight: 650;
        margin-bottom: 0.7rem;
    }

    .ng-context-summary {
        min-height: 144px;
        border: 1px solid var(--ng-border-soft);
        border-radius: 16px;
        background: linear-gradient(180deg, #ffffff 0%, #fdf8f5 100%);
        padding: 1rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.62rem;
        position: relative;
        overflow: hidden;
    }

    .ng-context-summary p {
        margin: 0;
        color: var(--ng-subtext);
        font-size: 0.9rem;
        line-height: 1.55;
        padding: 0.55rem 0.72rem;
        border-radius: 14px;
        background: var(--ng-primary-soft-2);
        border: 1px solid #f1e5db;
    }

    .ng-context-summary p + p {
        margin-top: 0;
    }

    .ng-context-summary:empty::before,
    .ng-context-summary:empty::after {
        content: "";
        display: block;
        height: 12px;
        border-radius: 999px;
        background: linear-gradient(
            90deg,
            rgba(184, 110, 84, 0.08),
            rgba(184, 110, 84, 0.18),
            rgba(184, 110, 84, 0.08)
        );
    }

    .ng-context-summary:empty::before {
        width: 62%;
        margin: 0 auto 0.8rem auto;
    }

    .ng-context-summary:empty::after {
        width: 78%;
        margin: 0 auto;
    }

    .ng-conversation-block {
        margin-top: 0;
    }

    .ng-section-title {
        margin: 0;
        font-size: 1.02rem;
        font-weight: 750;
        color: var(--ng-text);
    }

    .ng-section-title-row {
        display: flex;
        align-items: center;
        gap: 0.42rem;
        margin-bottom: 0.42rem;
    }

    .ng-conversation-card {
        background: linear-gradient(180deg, #ffffff 0%, #fdf9f6 100%);
        border: 1px solid #eadfd4;
        border-radius: 26px;
        padding: 0.88rem 0.96rem;
        box-shadow: var(--ng-shadow-md), inset 0 1px 0 rgba(255, 255, 255, 0.88);
    }

    .ng-conversation-card-empty {
        min-height: 188px;
    }

    .ng-chat-empty,
    .ng-empty-state {
        color: var(--ng-subtext);
        max-width: 620px;
        font-size: 0.95rem;
        line-height: 1.68;
        padding: 0.82rem 0.92rem;
        margin: 0;
        background: linear-gradient(180deg, #fefbf8 0%, #fbf4ee 100%);
        border: 1px dashed #e7d5c8;
        border-radius: 20px;
    }

    .ng-message {
        max-width: 80%;
        border-radius: 19px;
        padding: 0.7rem 0.86rem;
        margin-bottom: 0.42rem;
        border: 1px solid var(--ng-border-soft);
        font-size: 0.95rem;
        line-height: 1.65;
        box-shadow: 0 1px 0 rgba(110, 71, 53, 0.04);
        white-space: pre-wrap;
        word-break: break-word;
    }

    .ng-message:last-child {
        margin-bottom: 0;
    }

    .ng-message-user {
        margin-left: auto;
        background: #f8efe8;
    }

    .ng-message-assistant {
        margin-right: auto;
        background: #fffdfb;
    }

    .ng-message-role {
        display: block;
        margin-bottom: 0.16rem;
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--ng-subtext);
    }

    .ng-composer-wrap {
        margin-top: 0.82rem;
        margin-bottom: 0;
    }

    .ng-composer-shell {
        background: linear-gradient(180deg, #ffffff 0%, #fdf8f4 100%);
        border-radius: 24px;
        padding: 0.4rem;
    }

    div[data-testid="stForm"] {
        border: 0 !important;
        background: transparent !important;
        padding: 0 !important;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    textarea {
        background: var(--ng-surface) !important;
        border: 1px solid var(--ng-border) !important;
        border-radius: 20px !important;
        box-shadow: none !important;
    }

    div[data-baseweb="input"] input,
    textarea {
        color: var(--ng-text) !important;
        font-size: 0.97rem !important;
    }

    .ng-composer-wrap div[data-baseweb="input"] > div {
        background: transparent !important;
        border: 0 !important;
        border-radius: 18px !important;
        min-height: 52px !important;
    }

    .ng-composer-wrap div[data-baseweb="input"] input {
        font-size: 0.98rem !important;
        padding-left: 0.28rem !important;
    }

    .stButton > button,
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 18px !important;
        border: 1px solid #e6d6c9 !important;
        background: linear-gradient(180deg, #fffaf6 0%, #f7ece4 100%) !important;
        color: var(--ng-text) !important;
        font-weight: 650 !important;
        min-height: 50px !important;
        padding: 0.72rem 1rem !important;
        box-shadow: none !important;
    }

    .ng-composer-wrap div[data-testid="stFormSubmitButton"] button {
        min-height: 52px !important;
        min-width: 112px !important;
        white-space: nowrap !important;
        padding: 0.72rem 0.95rem !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        border-color: #d9b9a9 !important;
        color: var(--ng-primary) !important;
    }

    .ng-quick-wrap {
        margin-top: 0.18rem;
    }

    .ng-quick-card {
        padding: 0.92rem 0.9rem 0.86rem 0.9rem;
    }

    .ng-quick-title {
        margin: 0;
        font-size: 0.98rem;
        font-weight: 750;
        color: var(--ng-text);
    }

    .ng-quick-subtitle {
        margin: 0.28rem 0 0.76rem 0;
        color: var(--ng-subtext);
        font-size: 0.86rem;
        line-height: 1.48;
        max-width: none;
    }

    .ng-quick-button {
        height: 100%;
        margin-top: 0.42rem;
    }

    .ng-quick-button .stButton {
        height: 100%;
    }

    .ng-quick-button .stButton > button {
        width: 100%;
        background: #fff8f3 !important;
        min-height: 46px !important;
        display: flex !important;
        align-items: center;
        justify-content: center;
        text-align: center;
        line-height: 1.28;
        padding: 0.52rem 0.7rem !important;
        font-size: 0.9rem !important;
    }

    .ng-section-block {
        padding: 0;
        margin-top: 0.52rem;
    }

    .ng-card {
        background: linear-gradient(180deg, #ffffff 0%, #fdf8f4 100%);
        border: 1px solid var(--ng-border-soft);
        border-radius: 16px;
        padding: 0.66rem;
        margin-bottom: 0.4rem;
    }

    .ng-soft-note {
        margin: 0;
        color: var(--ng-subtext);
        font-size: 0.84rem;
        line-height: 1.48;
    }

    div[data-testid="stExpander"] {
        border: 0 !important;
        background: transparent !important;
        margin: 0 !important;
    }

    div[data-testid="stExpander"] details {
        border: 0 !important;
        background: transparent !important;
    }

    div[data-testid="stExpander"] summary {
        border: 1px solid var(--ng-border) !important;
        border-radius: 16px !important;
        background: var(--ng-primary-soft-2) !important;
        padding: 0.55rem 0.82rem !important;
        font-weight: 650 !important;
        font-size: 0.88rem !important;
        color: var(--ng-text) !important;
    }

    div[data-testid="stExpander"] summary:hover {
        color: var(--ng-primary) !important;
    }

    .ng-side-card div[data-testid="stExpander"] summary {
        background: #fdf8f4 !important;
        border-color: #efe2d6 !important;
    }

    .ng-side-card div[data-testid="stExpanderDetails"] {
        background: rgba(184, 110, 84, 0.04);
        border: 1px solid #f4e8de;
        border-radius: 16px;
        padding: 0.32rem 0.5rem 0.12rem 0.5rem;
        margin-top: 0.38rem;
    }

    .ng-side-card label,
    .ng-side-card .stCaption {
        font-size: 0.84rem !important;
    }

    .ng-side-card div[data-baseweb="select"] > div,
    .ng-side-card div[data-baseweb="input"] > div,
    .ng-side-card textarea {
        min-height: 42px !important;
        border-radius: 14px !important;
    }

    .ng-side-card textarea {
        min-height: 88px !important;
    }

    .ng-side-card div[data-testid="stFormSubmitButton"] button {
        min-height: 40px !important;
        padding: 0.55rem 0.8rem !important;
        font-size: 0.86rem !important;
        background: #fff8f3 !important;
    }

    .stCaption {
        color: var(--ng-subtext) !important;
    }

    @media (max-width: 900px) {
        .block-container {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }

        .ng-conversation-card {
            min-height: 0;
        }

        .ng-conversation-card-empty {
            min-height: 176px;
        }

        .ng-message {
            max-width: 100%;
        }
    }

    /* =========================================================
       RESPONSIVE NEUROGUIA - celular, tablet, laptop y PC
       Mantiene columnas laterales cómodas y evita cajas estrechas.
       ========================================================= */

    .block-container {
        width: 100% !important;
        max-width: 1760px !important;
        padding-left: clamp(0.65rem, 1.6vw, 1.7rem) !important;
        padding-right: clamp(0.65rem, 1.6vw, 1.7rem) !important;
    }

    .ng-page {
        width: 100% !important;
        max-width: 1680px !important;
    }

    .ng-layout-grid {
        width: 100% !important;
    }

    .ng-side-card,
    .ng-quick-card,
    .ng-panel-secondary {
        width: 100% !important;
        min-width: 0 !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }

    .ng-side-card textarea,
    .ng-side-card input,
    .ng-side-card .stTextArea,
    .ng-side-card .stTextInput,
    .ng-side-card .stSelectbox,
    .ng-quick-card .stButton,
    .ng-quick-card button {
        width: 100% !important;
        min-width: 100% !important;
    }

    .ng-side-card div[data-baseweb="select"],
    .ng-side-card div[data-baseweb="select"] > div,
    .ng-side-card div[data-baseweb="input"],
    .ng-side-card div[data-baseweb="input"] > div,
    .ng-side-card textarea {
        width: 100% !important;
        min-width: 100% !important;
    }

    .ng-side-card div[data-baseweb="select"] span {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.25 !important;
    }

    .ng-composer-wrap,
    .ng-composer-shell,
    .ng-conversation-card {
        width: 100% !important;
    }

    .ng-message {
        max-width: 94% !important;
    }

    .ng-quick-button .stButton > button {
        min-height: 54px !important;
        font-size: 0.95rem !important;
        white-space: normal !important;
        line-height: 1.25 !important;
    }

    /* PC grande */
    @media (min-width: 1441px) {
        .block-container {
            max-width: 1760px !important;
        }

        .ng-page {
            max-width: 1680px !important;
        }

        .ng-side-card,
        .ng-quick-card {
            padding-left: 1.35rem !important;
            padding-right: 1.35rem !important;
        }
    }

    /* Laptop */
    @media (min-width: 1025px) and (max-width: 1440px) {
        .block-container {
            max-width: 1380px !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        .ng-page {
            max-width: 1340px !important;
        }

        .ng-side-card,
        .ng-quick-card {
            padding-left: 1.05rem !important;
            padding-right: 1.05rem !important;
        }

        .ng-sidebar-title,
        .ng-section-title,
        .ng-quick-title {
            font-size: 0.98rem !important;
        }

        .ng-side-card label,
        .ng-side-card .stCaption {
            font-size: 0.83rem !important;
        }
    }

    /* Tablet: las columnas de Streamlit se apilan o se vuelven cómodas */
    @media (min-width: 701px) and (max-width: 1024px) {
        .block-container {
            max-width: 980px !important;
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
        }

        .ng-page {
            max-width: 960px !important;
        }

        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        .ng-side-card,
        .ng-quick-card,
        .ng-conversation-card,
        .ng-composer-shell {
            margin-bottom: 0.85rem !important;
        }

        .ng-message {
            max-width: 96% !important;
        }

        .ng-header-inner {
            padding: 0.95rem !important;
        }
    }

    /* Celular */
    @media (max-width: 700px) {
        .block-container {
            max-width: 100% !important;
            padding-left: 0.55rem !important;
            padding-right: 0.55rem !important;
            padding-top: 0.45rem !important;
        }

        .ng-page {
            max-width: 100% !important;
        }

        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        .ng-header {
            padding-bottom: 0.55rem !important;
        }

        .ng-header-inner {
            border-radius: 20px !important;
            padding: 0.8rem 0.72rem !important;
        }

        .ng-brand-title {
            font-size: 1.25rem !important;
        }

        .ng-header-subtitle {
            font-size: 0.82rem !important;
            line-height: 1.45 !important;
        }

        .ng-side-card,
        .ng-quick-card,
        .ng-conversation-card,
        .ng-composer-shell {
            border-radius: 18px !important;
            padding: 0.78rem !important;
            margin-bottom: 0.72rem !important;
        }

        .ng-message {
            max-width: 100% !important;
            font-size: 0.9rem !important;
            line-height: 1.5 !important;
            padding: 0.62rem 0.7rem !important;
        }

        .ng-composer-wrap div[data-baseweb="input"] input {
            font-size: 0.94rem !important;
        }

        .ng-composer-wrap div[data-testid="stFormSubmitButton"] button {
            min-width: 100% !important;
            min-height: 48px !important;
        }

        .stButton > button,
        div[data-testid="stFormSubmitButton"] button,
        div[data-testid="stDownloadButton"] button {
            width: 100% !important;
            min-height: 46px !important;
            padding: 0.62rem 0.75rem !important;
            white-space: normal !important;
        }

        textarea {
            min-height: 96px !important;
        }

        .ng-side-card div[data-testid="stExpanderDetails"] {
            padding: 0.32rem 0.35rem 0.12rem 0.35rem !important;
        }
    }


    .ng-profile-actions-note {
        margin: 0.48rem 0 0.28rem 0;
        padding: 0.58rem 0.68rem;
        border-radius: 14px;
        background: #fff8f3;
        border: 1px solid #efe2d6;
        color: var(--ng-subtext);
        font-size: 0.82rem;
        line-height: 1.42;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# BOOTSTRAP
# ---------------------------------------------------------
STREAMLIT_SECRET_ENV_KEYS = (
    "OPENAI_API_KEY",
    "USE_OPENAI_LLM",
    "OPENAI_MODEL",
    "OPENAI_TIMEOUT_SECONDS",
    "DEBUG_MODE",
    "DATABASE_URL",
    "DB_BACKEND",
)


def _get_streamlit_secret_value(key: str) -> Optional[Any]:
    try:
        secrets = st.secrets
    except Exception:
        return None

    try:
        if key in secrets:
            return secrets[key]
    except Exception:
        pass

    nested_candidates = {
        key,
        key.lower(),
        key.replace("OPENAI_", "").lower(),
    }
    for section_name in ("openai", "OPENAI", "llm", "LLM", "debug", "DEBUG"):
        try:
            section = secrets.get(section_name)
        except Exception:
            section = None
        if not hasattr(section, "get"):
            continue
        for candidate in nested_candidates:
            try:
                value = section.get(candidate)
            except Exception:
                value = None
            if value not in {None, ""}:
                return value
    return None


def _has_streamlit_secret_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def sync_streamlit_secrets_to_env() -> Dict[str, Any]:
    synced: List[str] = []
    present: Dict[str, bool] = {}
    for key in STREAMLIT_SECRET_ENV_KEYS:
        value = _get_streamlit_secret_value(key)
        present[key] = _has_streamlit_secret_value(value)
        if not present[key]:
            continue
        os.environ[key] = str(value).strip()
        synced.append(key)
    return {
        "synced_keys": synced,
        "present": present,
        "has_openai_api_key": bool(str(os.getenv("OPENAI_API_KEY", "") or "").strip()),
        "use_openai_llm_raw": str(os.getenv("USE_OPENAI_LLM", "") or "").strip(),
        "openai_model": str(os.getenv("OPENAI_MODEL", "") or "").strip(),
    }


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = str(os.getenv(name, "") or "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "y", "on", "si", "sí", "enabled"}


def derive_database_backend(default: str = "sqlite") -> str:
    """Resolve the active database backend for Streamlit.

    In Streamlit Cloud, DATABASE_URL can exist even if DB_BACKEND was not
    explicitly set. When DATABASE_URL is present, PostgreSQL/Supabase must be
    used for profiles, families, memory and messages.
    """
    raw_backend = str(os.getenv("DB_BACKEND", "") or "").strip().lower()
    database_url = str(os.getenv("DATABASE_URL", "") or "").strip()

    if raw_backend:
        return raw_backend
    if database_url:
        os.environ["DB_BACKEND"] = "postgres"
        return "postgres"
    return default


def bootstrap_environment(env_path: str) -> None:
    load_env_file(env_path)
    st.session_state["streamlit_secrets_sync"] = sync_streamlit_secrets_to_env()
    # Si existe DATABASE_URL, toda la app debe trabajar sobre Supabase/PostgreSQL.
    # Esto evita que familias/perfiles se creen en SQLite local mientras
    # ng_messages se guarda en Supabase.
    derive_database_backend()


def bootstrap_database(db_backend: str, db_path: str) -> None:
    if db_backend == "sqlite":
        initialize_database(db_path=db_path)


def get_profile_manager(db_path: str) -> ProfileManager:
    backend = st.session_state.get("db_backend") or derive_database_backend()
    return ProfileManager(db_path=db_path, backend=backend)


def get_orchestrator(db_path: str) -> NeuroGuiaOrchestratorV2:
    return NeuroGuiaOrchestratorV2(db_path=db_path)


def safe_close(obj: Any) -> None:
    if obj is None:
        return
    try:
        obj.close()
    except Exception:
        pass


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------
def init_session_state() -> None:
    st.session_state.setdefault("env_path", DEFAULT_ENV_PATH)
    st.session_state.setdefault("db_path", DEFAULT_DB_PATH)
    st.session_state.setdefault("db_backend", derive_database_backend())
    st.session_state.setdefault("session_scope_id", uuid.uuid4().hex)
    st.session_state.setdefault("selected_family_id", None)
    st.session_state.setdefault("selected_profile_id", None)
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("auto_store_system_response", False)
    st.session_state.setdefault("auto_store_curated_llm_response", True)
    st.session_state.setdefault("show_response_debug", env_flag("DEBUG_MODE", False))
    st.session_state.setdefault(
        "use_llm_stub",
        False,
    )
    st.session_state.setdefault("session_id", uuid.uuid4().hex)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def load_units_and_profiles(db_path: str) -> Dict[str, Any]:
    pm = get_profile_manager(db_path)
    try:
        units = pm.list_units(limit=200)
        unit_profiles: Dict[str, List[Dict[str, Any]]] = {}
        for unit in units:
            family_id = unit["family_id"]
            unit_profiles[family_id] = pm.list_profiles(family_id=family_id)
        return {
            "units": units,
            "unit_profiles": unit_profiles,
        }
    finally:
        safe_close(pm)


def format_unit_label(unit: Dict[str, Any]) -> str:
    alias = unit.get("caregiver_alias") or "Sin nombre"
    unit_type = unit.get("unit_type") or "individual"
    family_id = str(unit.get("family_id", ""))[:8]
    kind = "Familia o caso" if unit_type == "family" else "Caso individual"
    return f"{alias} · {kind} · {family_id}"


def format_profile_label(profile: Dict[str, Any]) -> str:
    alias = profile.get("alias") or "Sin nombre"
    role = profile.get("role") or "sin rol"
    age = profile.get("age")
    conds = profile.get("conditions", []) or []
    cond_text = ", ".join(conds[:2]) if conds else "sin condiciones"
    age_text = f"{age} años" if age is not None else "edad no indicada"
    return f"{alias} · {role} · {age_text} · {cond_text}"


def _split_csv(text: str) -> List[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def _find_icon_logo() -> Optional[Path]:
    candidates = [
        PROJECT_ROOT / "logo_icon.png",
        PROJECT_ROOT / "icon_logo.png",
        PROJECT_ROOT / "assets" / "logo_icon.png",
        PROJECT_ROOT / "assets" / "icon_logo.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_full_logo() -> Optional[Path]:
    candidates = [
        PROJECT_ROOT / "logo_full.png",
        PROJECT_ROOT / "neuroguia_logo_full.png",
        PROJECT_ROOT / "logo_horizontal.png",
        PROJECT_ROOT / "assets" / "logo_full.png",
        PROJECT_ROOT / "assets" / "neuroguia_logo_full.png",
        PROJECT_ROOT / "assets" / "logo_horizontal.png",
        PROJECT_ROOT / "assets" / "logo_complete.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _image_to_data_uri(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.exists():
        return None
    suffix = path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _escape_html_text(text: Any) -> str:
    return html.escape(str(text or "")).replace("\n", "<br>")


def build_history_hint() -> List[Dict[str, Any]]:
    return [
        {
            "user": item.get("user", ""),
            "assistant": item.get("assistant", ""),
        }
        for item in st.session_state.chat_history[-6:]
    ]


def build_conversation_export(history: List[Dict[str, Any]]) -> str:
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "neuroGuIA - conversacion",
        f"Fecha: {exported_at}",
        "",
    ]

    for index, item in enumerate(history or [], start=1):
        user_text = str(item.get("user") or "").strip()
        assistant_text = str(item.get("assistant") or "").strip()
        lines.append(f"Turno {index}")
        lines.append(f"Usuario: {user_text}")
        lines.append(f"neuroGuIA: {assistant_text}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def conversation_export_filename() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"neuroguia_conversacion_{stamp}.txt"


def clear_visible_conversation() -> None:
    st.session_state.chat_history = []
    st.session_state.last_result = None


def restart_temporary_session() -> None:
    clear_visible_conversation()
    st.session_state.session_scope_id = uuid.uuid4().hex
    st.session_state.selected_family_id = None
    st.session_state.selected_profile_id = None
    st.session_state.pop("selected_family_main", None)
    st.session_state.pop("selected_profile_main", None)


def get_context_badge_text() -> str:
    if st.session_state.selected_family_id or st.session_state.selected_profile_id:
        return "Contexto activo"
    return "Sin contexto activo"


def get_context_summary_text(
    units: List[Dict[str, Any]],
    unit_profiles: Dict[str, List[Dict[str, Any]]],
) -> List[str]:
    if not st.session_state.selected_family_id:
        return []

    lines: List[str] = []
    selected_unit = next(
        (unit for unit in units if unit.get("family_id") == st.session_state.selected_family_id),
        None,
    )
    if selected_unit:
        alias = selected_unit.get("caregiver_alias") or "Caso seleccionado"
        lines.append(alias)

    if st.session_state.selected_profile_id:
        for profile in unit_profiles.get(st.session_state.selected_family_id, []):
            if profile.get("profile_id") == st.session_state.selected_profile_id:
                lines.append(profile.get("alias") or "Perfil seleccionado")
                break

    return lines


# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
def render_shell_start() -> None:
    st.markdown('<div class="ng-page">', unsafe_allow_html=True)


def render_shell_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_app_header(show_full_logo: bool = True) -> None:
    del show_full_logo
    icon_logo_uri = _image_to_data_uri(_find_icon_logo())
    logo_html = (
        f'<img src="{icon_logo_uri}" alt="Logo de neuroguIA" />'
        if icon_logo_uri
        else '<span class="ng-brand-fallback" aria-hidden="true">🧠</span>'
    )
    st.markdown(
        f"""
        <section class="ng-header" aria-label="Cabecera de neuroGuIA">
            <div class="ng-header-inner">
                <div class="ng-brand-line">
                    <div class="ng-brand-logo">{logo_html}</div>
                    <p class="ng-brand-title">neuroguIA</p>
                </div>
                <p class="ng-header-subtitle">Un espacio de apoyo cálido, claro y adaptativo para acompañarte paso a paso.</p>
                <p class="ng-header-subtitle">Acompanamiento inteligente y humano para momentos difíciles, organización, prevención y apoyo emocional.</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    return

    icon_logo = _find_icon_logo()
    st.markdown('<div class="ng-header"><div class="ng-header-inner">', unsafe_allow_html=True)
    st.markdown('<div class="ng-brand-line">', unsafe_allow_html=True)

    if icon_logo:
        st.markdown('<div class="ng-brand-logo">', unsafe_allow_html=True)
        st.image(str(icon_logo), width=32)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="ng-brand-logo"><span style="font-weight:800;color:#8167d8;">nG</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<p class="ng-brand-title">neuroguIA</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="ng-header-line">Un espacio de apoyo cálido, claro y adaptativo para acompañarte paso a paso.</p>
        <p class="ng-header-line">Acompañamiento inteligente y humano para momentos difíciles, organización, prevención y apoyo emocional.</p>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div></div>', unsafe_allow_html=True)


def render_compact_context_bar(
    units: List[Dict[str, Any]],
    unit_profiles: Dict[str, List[Dict[str, Any]]],
) -> None:
    summary_lines = get_context_summary_text(units, unit_profiles)

    st.markdown('<div class="ng-top-grid">', unsafe_allow_html=True)
    col1, col2 = st.columns([1.55, 0.95], gap="medium")

    with col1:
        st.markdown('<div class="ng-panel">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="ng-panel-title-row">
                <span class="ng-panel-icon">💬</span>
                <p class="ng-panel-title">Hablar con neuroguIA</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="ng-context-badge">{get_context_badge_text()}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("> Perfil y contexto", expanded=False):
            render_context_selector(units, unit_profiles, section_key="main")
            create_unit_ui(st.session_state.db_path, embedded=True)
            create_profile_ui(st.session_state.db_path, units, embedded=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="ng-panel-secondary">', unsafe_allow_html=True)
        st.markdown('<p class="ng-panel-title">Perfiles y contexto</p>', unsafe_allow_html=True)
        if summary_lines:
            summary_html = "".join(f"<p>{_escape_html_text(line)}</p>" for line in summary_lines)
            st.markdown(f'<div class="ng-context-summary">{summary_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ng-context-summary"></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def render_context_sidebar(
    units: List[Dict[str, Any]],
    unit_profiles: Dict[str, List[Dict[str, Any]]],
) -> None:
    summary_lines = get_context_summary_text(units, unit_profiles)
    full_logo_uri = _image_to_data_uri(_find_full_logo())

    st.markdown('<div class="ng-card ng-side-card">', unsafe_allow_html=True)
    if full_logo_uri:
        st.markdown(
            f'<div class="ng-logo-full"><img class="ng-logo-full-image" src="{full_logo_uri}" alt="Logo completo de neuroguIA" /></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="ng-logo-full"><div class="ng-logo-wordmark">neuroGuIA</div></div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="ng-sidebar-title-row">
            <span class="ng-side-title-icon">💬</span>
            <p class="ng-sidebar-title">Hablar con neuroguIA</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="ng-context-badge">{get_context_badge_text()}</div>',
        unsafe_allow_html=True,
    )

    if summary_lines:
        summary_html = "".join(f"<p>{_escape_html_text(line)}</p>" for line in summary_lines)
        st.markdown(f'<div class="ng-sidebar-summary">{summary_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="ng-side-note">Usa este espacio para abrir o crear un perfil cuando quieras conservar contexto.</p>',
            unsafe_allow_html=True,
        )

    with st.expander("> Perfil y contexto", expanded=False):
        render_context_selector(units, unit_profiles, section_key="main")

        st.markdown(
            '<p class="ng-profile-actions-note">Los formularios de captura permanecen ocultos para mantener limpio el panel. Actívalos solo cuando necesites crear un nuevo caso o perfil.</p>',
            unsafe_allow_html=True,
        )

        show_create_unit = st.toggle(
            "Crear nuevo caso o familia",
            value=False,
            key="show_create_unit_main",
            help="Activa esta opción solo cuando quieras registrar un nuevo contexto familiar o individual.",
        )
        if show_create_unit:
            create_unit_ui(st.session_state.db_path, embedded=True)

        show_create_profile = st.toggle(
            "Crear nuevo perfil individual",
            value=False,
            key="show_create_profile_main",
            help="Activa esta opción después de seleccionar o crear el caso donde se guardará el perfil.",
        )
        if show_create_profile:
            create_profile_ui(st.session_state.db_path, units, embedded=True)

    st.markdown("</div>", unsafe_allow_html=True)
    return

    summary_lines = get_context_summary_text(units, unit_profiles)
    full_logo = _find_full_logo()

    st.markdown('<div class="ng-side-card">', unsafe_allow_html=True)
    st.markdown('<div class="ng-logo-full">', unsafe_allow_html=True)
    if full_logo:
        st.image(str(full_logo), width=160)
    else:
        st.markdown('<div class="ng-logo-wordmark">neuroGuIA</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="ng-sidebar-title-row">
            <span class="ng-side-title-icon">💬</span>
            <p class="ng-sidebar-title">Hablar con neuroguIA</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="ng-context-badge">{get_context_badge_text()}</div>',
        unsafe_allow_html=True,
    )

    if summary_lines:
        summary_html = "".join(f"<p>{line}</p>" for line in summary_lines)
        st.markdown(f'<div class="ng-sidebar-summary">{summary_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="ng-side-note">Usa este espacio para abrir o crear un perfil cuando quieras conservar contexto.</p>',
            unsafe_allow_html=True,
        )

    with st.expander("> Perfil y contexto", expanded=False):
        render_context_selector(units, unit_profiles, section_key="main")
        create_unit_ui(st.session_state.db_path, embedded=True)
        create_profile_ui(st.session_state.db_path, units, embedded=True)

    st.markdown('</div>', unsafe_allow_html=True)


def render_chat_history() -> None:
    history = st.session_state.chat_history
    card_class = "ng-card ng-conversation-card ng-conversation-card-empty" if not history else "ng-card ng-conversation-card"
    html_parts = [
        '<div class="ng-conversation-block">',
        '<div class="ng-section-title-row"><span class="ng-section-icon">🗨️</span><p class="ng-section-title">Conversacion</p></div>',
        f'<div class="{card_class}">',
    ]

    if not history:
        html_parts.append(
            '<div class="ng-chat-empty">Aqui aparecera la conversacion. Cuando quieras, cuentame que esta pasando y lo vemos poco a poco.</div>'
        )
    else:
        for item in history:
            user_text = _escape_html_text(item.get("user", ""))
            assistant_text = _escape_html_text(item.get("assistant", ""))
            html_parts.append(
                f'<div class="ng-message ng-message-user"><span class="ng-message-role">Tu</span>{user_text}</div>'
            )
            html_parts.append(
                f'<div class="ng-message ng-message-assistant"><span class="ng-message-role">neuroGuIA</span>{assistant_text}</div>'
            )

    html_parts.append("</div></div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    st.download_button(
        "Descargar conversación",
        data=build_conversation_export(history),
        file_name=conversation_export_filename(),
        mime="text/plain",
        key="download_conversation_main",
        disabled=not bool(history),
        use_container_width=True,
    )
    return

    st.markdown('<div class="ng-conversation-block">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ng-section-title-row">
            <span class="ng-section-icon">🗨️</span>
            <p class="ng-section-title">Conversacion</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    card_class = "ng-card ng-conversation-card ng-conversation-card-empty" if not history else "ng-card ng-conversation-card"
    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    if not history:
        st.markdown(
            """
            <div class="ng-chat-empty">
                Aqui aparecera la conversacion. Cuando quieras, cuentame que esta pasando y lo vemos poco a poco.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    for item in history:
        user_text = _escape_html_text(item.get("user", ""))
        assistant_text = _escape_html_text(item.get("assistant", ""))

        st.markdown(
            f"""
            <div class="ng-message ng-message-user">
                <span class="ng-message-role">Tu</span>
                {user_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="ng-message ng-message-assistant">
                <span class="ng-message-role">neuroguIA</span>
                {assistant_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div></div>", unsafe_allow_html=True)
    return

    st.markdown('<div class="ng-conversation-block">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ng-section-title-row">
            <span class="ng-section-icon">🗨️</span>
            <p class="ng-section-title">Conversación</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    card_class = "ng-conversation-card ng-conversation-card-empty" if not history else "ng-conversation-card"
    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    if not history:
        st.markdown(
            """
            <div class="ng-empty-state">
                Aquí aparecerá la conversación. Cuando quieras, cuéntame qué está pasando y lo vemos poco a poco...
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('</div></div>', unsafe_allow_html=True)
        return

    for item in history:
        user_text = item.get("user", "")
        assistant_text = item.get("assistant", "")

        st.markdown(
            f"""
            <div class="ng-message ng-message-user">
                <span class="ng-message-role">Tú</span>
                {user_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="ng-message ng-message-assistant">
                <span class="ng-message-role">neuroGuIA</span>
                {assistant_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('</div></div>', unsafe_allow_html=True)


def render_main_input() -> Optional[str]:
    st.markdown('<div class="ng-composer-wrap"><div class="ng-card ng-composer-shell">', unsafe_allow_html=True)
    with st.form("main_input_form", clear_on_submit=True):
        col1, col2 = st.columns([9.6, 1.8], gap="small")
        with col1:
            user_message = st.text_input(
                "Mensaje",
                value="",
                placeholder="Escribe tu mensaje aquí...",
                label_visibility="collapsed",
            )
        with col2:
            submitted = st.form_submit_button("Enviar", use_container_width=True)
    st.markdown('</div></div>', unsafe_allow_html=True)
    if submitted and user_message.strip():
        return user_message.strip()
    return None


def render_quick_help() -> None:
    st.markdown('<div class="ng-quick-wrap"><div class="ng-card ng-quick-card">', unsafe_allow_html=True)
    st.markdown('<p class="ng-quick-title">Acceso rapido</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ng-quick-subtitle">Si no sabes como empezar, puedes usar una de estas opciones.</p>',
        unsafe_allow_html=True,
    )

    row1 = st.columns(3, gap="small")
    row2 = st.columns(2, gap="small")

    with row1[0]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("😰 Me siento muy ansiosa/o", key="quick_anxiety"):
            process_user_message("😰 Me siento muy ansiosa/o y no se como calmarme")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with row1[1]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("😫 Esta ocurriendo una crisis", key="quick_crisis"):
            process_user_message("😫 Esta ocurriendo una crisis y necesito ayuda para manejarla")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with row1[2]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("🥱 Hay problemas de sue\u00f1o", key="quick_sleep"):
            process_user_message("🥱 Hay problemas de sueño y eso está afectando mucho")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with row2[0]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("📚 No puedo organizarme", key="quick_organize"):
            process_user_message("📚 No puedo organizarme ni empezar lo que tengo pendiente")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with row2[1]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("🧼 Limpiar conversacion", key="quick_clear"):
            clear_visible_conversation()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    return

    st.markdown('<div class="ng-quick-wrap"><div class="ng-quick-card">', unsafe_allow_html=True)
    st.markdown('<p class="ng-quick-title">Acceso rápido</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ng-quick-subtitle">Si no sabes cómo empezar, puedes usar una de estas opciones.</p>',
        unsafe_allow_html=True,
    )

    row1 = st.columns(3, gap="small")
    row2 = st.columns(3, gap="small")

    with row1[0]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("😰 Me siento muy ansiosa/o", key="quick_anxiety"):
            process_user_message("😰 Me siento muy ansiosa/o y no sé cómo calmarme")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with row1[1]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("😫 Está ocurriendo una crisis", key="quick_crisis"):
            process_user_message("😫 Está ocurriendo una crisis y necesito ayuda para manejarla")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with row1[2]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("🥱 Hay problemas de sueño", key="quick_sleep"):
            process_user_message("🥱 Hay problemas de sueño y eso está afectando mucho")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with row2[0]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("📚 No puedo organizarme", key="quick_organize"):
            process_user_message("📚 No puedo organizarme ni empezar lo que tengo pendiente")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with row2[1]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("🧼 Limpiar conversación", key="quick_clear"):
            st.session_state.chat_history = []
            st.session_state.last_result = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with row2[2]:
        st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
        if st.button("Empezar de nuevo", key="quick_restart"):
            st.session_state.chat_history = []
            st.session_state.last_result = None
            st.session_state.selected_profile_id = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


def render_quick_help_sidebar() -> None:
    st.markdown('<div class="ng-quick-wrap"><div class="ng-card ng-quick-card">', unsafe_allow_html=True)
    st.markdown('<p class="ng-quick-title">Acceso rapido</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ng-quick-subtitle">Si no sabes como empezar, puedes usar una de estas opciones.</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("😰 Me siento muy ansiosa/o", key="quick_anxiety_sidebar", use_container_width=True):
        process_user_message("😰 Me siento muy ansiosa/o y no se como calmarme")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("😫 Esta ocurriendo una crisis", key="quick_crisis_sidebar", use_container_width=True):
        process_user_message("😫 Esta ocurriendo una crisis y necesito ayuda para manejarla")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("🥱 Hay problemas de sue\u00f1o", key="quick_sleep_sidebar", use_container_width=True):
        process_user_message("🥱 Hay problemas de sueño y eso está afectando mucho")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("📚 No puedo organizarme", key="quick_organize_sidebar", use_container_width=True):
        process_user_message("📚 No puedo organizarme ni empezar lo que tengo pendiente")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("🧼 Limpiar conversacion", key="quick_clear_sidebar", use_container_width=True):
        clear_visible_conversation()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    return

    st.markdown('<div class="ng-quick-wrap"><div class="ng-quick-card">', unsafe_allow_html=True)
    st.markdown('<p class="ng-quick-title">Acceso rápido</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ng-quick-subtitle">Si no sabes cómo empezar, puedes usar una de estas opciones.</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("😰 Me siento muy ansiosa/o", key="quick_anxiety_sidebar", use_container_width=True):
        process_user_message("😰 Me siento muy ansiosa/o y no sé cómo calmarme")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("😫 Está ocurriendo una crisis", key="quick_crisis_sidebar", use_container_width=True):
        process_user_message("😫 Está ocurriendo una crisis y necesito ayuda para manejarla")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("🥱 Hay problemas de sueño", key="quick_sleep_sidebar", use_container_width=True):
        process_user_message("🥱 Hay problemas de sueño y eso está afectando mucho")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("📚 No puedo organizarme", key="quick_organize_sidebar", use_container_width=True):
        process_user_message("📚 No puedo organizarme ni empezar lo que tengo pendiente")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("🧼 Limpiar conversación", key="quick_clear_sidebar", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_result = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="ng-quick-button">', unsafe_allow_html=True)
    if st.button("Empezar de nuevo", key="quick_restart_sidebar", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_result = None
        st.session_state.selected_profile_id = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)

def render_response_debug_metadata() -> None:
    result = st.session_state.last_result if isinstance(st.session_state.last_result, dict) else {}
    show_debug = False
    if not show_debug or not result:
        return

    response_package = result.get("response_package", {}) or {}
    response_metadata = response_package.get("response_metadata", {}) or {}
    conversation_control = result.get("conversation_control", {}) or {}
    secrets_sync = st.session_state.get("streamlit_secrets_sync", {}) or {}
    debug_payload = {
        "response_source": response_package.get("response_source") or response_metadata.get("response_source"),
        "llm_writer_requested": response_package.get("llm_writer_requested") or response_metadata.get("llm_writer_requested"),
        "llm_writer_used": response_package.get("llm_writer_used") or response_metadata.get("llm_writer_used"),
        "llm_provider": response_package.get("llm_provider") or response_metadata.get("llm_provider"),
        "llm_block_reason": response_package.get("llm_block_reason") or response_metadata.get("llm_block_reason"),
        "llm_curator_status": response_package.get("llm_curator_status") or response_metadata.get("llm_curator_status"),
        "llm_writer_notes": response_metadata.get("llm_writer_notes"),
        "model_used": response_package.get("model_used") or response_metadata.get("model_used"),
        "route_id": response_metadata.get("route_id"),
        "support_subject": response_metadata.get("support_subject"),
        "support_mode": response_metadata.get("support_mode"),
        "openai_writer_status": response_metadata.get("openai_writer_status"),
        "streamlit_secrets_sync": {
            "synced_keys": secrets_sync.get("synced_keys", []),
            "has_openai_api_key": bool(secrets_sync.get("has_openai_api_key")),
            "use_openai_llm_raw": secrets_sync.get("use_openai_llm_raw"),
            "openai_model": secrets_sync.get("openai_model"),
        },
        "conversation_control": {
            "response_source": conversation_control.get("response_source"),
            "llm_writer_requested": conversation_control.get("llm_writer_requested"),
            "llm_writer_used": conversation_control.get("llm_writer_used"),
            "llm_provider": conversation_control.get("llm_provider"),
            "llm_block_reason": conversation_control.get("llm_block_reason"),
            "llm_curator_status": conversation_control.get("llm_curator_status"),
            "model_used": conversation_control.get("model_used"),
        },
    }
    with st.expander("Metadata interna", expanded=False):
        st.json(debug_payload)


def render_context_selector(
    units: List[Dict[str, Any]],
    unit_profiles: Dict[str, List[Dict[str, Any]]],
    section_key: str,
) -> None:
    st.markdown('<div class="ng-section-block"><div class="ng-card">', unsafe_allow_html=True)
    st.markdown('<p class="ng-section-title">Contexto guardado</p>', unsafe_allow_html=True)

    if not units:
        st.markdown(
            '<p class="ng-soft-note">Aún no hay un caso o familia guardado. Si lo necesitas, puedes crearlo en esta misma sección.</p>',
            unsafe_allow_html=True,
        )
        st.session_state.selected_family_id = None
        st.session_state.selected_profile_id = None
        st.markdown('</div></div>', unsafe_allow_html=True)
        return

    unit_labels = {format_unit_label(u): u["family_id"] for u in units}
    unit_options = ["—"] + list(unit_labels.keys())

    current_unit_label = "—"
    if st.session_state.selected_family_id:
        for label, fid in unit_labels.items():
            if fid == st.session_state.selected_family_id:
                current_unit_label = label
                break

    selected_unit_label = st.selectbox(
        "Selecciona el caso o familia que quieres usar",
        unit_options,
        index=unit_options.index(current_unit_label) if current_unit_label in unit_options else 0,
        key=f"selected_family_{section_key}",
    )

    if selected_unit_label != "—":
        st.session_state.selected_family_id = unit_labels[selected_unit_label]
    else:
        st.session_state.selected_family_id = None
        st.session_state.selected_profile_id = None

    selected_profiles = []
    if st.session_state.selected_family_id:
        selected_profiles = unit_profiles.get(st.session_state.selected_family_id, [])

    if selected_profiles:
        profile_labels = {format_profile_label(p): p["profile_id"] for p in selected_profiles}
        profile_options = ["—"] + list(profile_labels.keys())

        current_profile_label = "—"
        if st.session_state.selected_profile_id:
            for label, pid in profile_labels.items():
                if pid == st.session_state.selected_profile_id:
                    current_profile_label = label
                    break

        selected_profile_label = st.selectbox(
            "Selecciona a la persona",
            profile_options,
            index=profile_options.index(current_profile_label) if current_profile_label in profile_options else 0,
            key=f"selected_profile_{section_key}",
        )

        if selected_profile_label != "—":
            st.session_state.selected_profile_id = profile_labels[selected_profile_label]
        else:
            st.session_state.selected_profile_id = None
    else:
        st.session_state.selected_profile_id = None
        st.caption("Este caso todavía no tiene perfiles guardados.")

    st.markdown('</div></div>', unsafe_allow_html=True)


# ---------------------------------------------------------
# CRUD
# ---------------------------------------------------------
def create_unit_ui(db_path: str, embedded: bool = False) -> None:
    """Render a clearer family/case capture form.

    The goal is to reduce cognitive load: only the essential context is shown
    first, and the extra details remain optional. Internally we keep the same
    database fields used by ng_families so the rest of the app does not break.
    """
    container = st.container() if embedded else st.expander("➕ Crear caso o familia", expanded=False)

    with container:
        if embedded:
            st.markdown('<div class="ng-section-block"><div class="ng-card">', unsafe_allow_html=True)
            st.markdown('<p class="ng-section-title">Crear un caso o familia</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="ng-soft-note">Guarda solo el contexto necesario para que neuroguIA pueda acompañar con más continuidad. Puedes completar los detalles poco a poco.</p>',
                unsafe_allow_html=True,
            )

        with st.form("create_unit_form", clear_on_submit=True):
            st.markdown("**1. Datos básicos del caso**")
            unit_type_label = st.radio(
                "¿Qué tipo de contexto quieres guardar?",
                ["Familia o red de cuidado", "Caso individual"],
                index=0,
                horizontal=False,
                help="Usa 'Familia o red de cuidado' cuando varias personas participan en el acompañamiento. Usa 'Caso individual' cuando la persona usuaria se acompaña a sí misma.",
            )
            unit_type = "family" if unit_type_label == "Familia o red de cuidado" else "individual"

            caregiver_alias = st.text_input(
                "Nombre del caso o familia",
                placeholder="Ejemplo: Familia Daniel, Caso Ana, Grupo de apoyo escolar",
                help="Este nombre aparecerá en el selector de contexto. No uses datos sensibles si prefieres mantener anonimato.",
            )

            st.markdown("**2. Situación principal**")
            context_notes = st.text_area(
                "¿Qué situación quieres que neuroguIA tenga presente?",
                placeholder="Ejemplo: Hay dificultades con sueño, saturación sensorial y organización escolar. La familia busca estrategias breves y respetuosas.",
                height=110,
                help="Describe el contexto general en palabras simples. No tiene que ser perfecto; basta con lo que ayude a entender el caso.",
            )

            with st.expander("Detalles opcionales del contexto", expanded=False):
                support_network = st.text_area(
                    "Red de apoyo",
                    placeholder="Ejemplo: mamá, papá, abuela, docente de apoyo, terapeuta externo, amistades cercanas.",
                    height=82,
                    help="Personas o instituciones que pueden apoyar cuando hay sobrecarga, crisis o necesidad de seguimiento.",
                )
                environmental_factors = st.text_area(
                    "Factores del entorno",
                    placeholder="Ejemplo: ruido escolar, cambios de rutina, pantallas por la noche, transporte, discusiones familiares.",
                    height=82,
                    help="Elementos del ambiente que pueden influir en el bienestar o conducta.",
                )
                global_history = st.text_area(
                    "Notas importantes de historia o seguimiento",
                    placeholder="Ejemplo: suele mejorar con anticipación visual; empeora cuando se le presiona; se busca evitar lenguaje clínico o juicios.",
                    height=92,
                    help="Información que conviene recordar en futuras conversaciones.",
                )

            submitted = st.form_submit_button("Guardar caso o familia")

            if submitted:
                if not caregiver_alias.strip():
                    st.warning("Agrega un nombre o alias para identificar este caso.")
                    return

                pm = get_profile_manager(db_path)
                try:
                    family_id = pm.create_unit(
                        unit_type=unit_type,
                        caregiver_alias=caregiver_alias.strip() or None,
                        context_notes=context_notes.strip() or None,
                        support_network=support_network.strip() or None,
                        environmental_factors=environmental_factors.strip() or None,
                        global_history=global_history.strip() or None,
                    )
                    st.session_state.selected_family_id = family_id
                    st.session_state.selected_profile_id = None
                    st.success("Caso guardado correctamente. Ahora puedes crear o seleccionar un perfil individual.")
                    st.rerun()
                finally:
                    safe_close(pm)

        if embedded:
            st.markdown('</div></div>', unsafe_allow_html=True)


def create_profile_ui(db_path: str, available_units: List[Dict[str, Any]], embedded: bool = False) -> None:
    """Render a clearer individual profile capture form.

    Essential fields are grouped first. Technical fields are kept as optional
    details so the UI is easier to understand for caregivers and families.
    """
    container = st.container() if embedded else st.expander("👤 Crear perfil individual", expanded=False)

    with container:
        if embedded:
            st.markdown('<div class="ng-section-block"><div class="ng-card">', unsafe_allow_html=True)
            st.markdown('<p class="ng-section-title">Crear un perfil individual</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="ng-soft-note">Crea un perfil para una persona concreta. Así neuroguIA puede responder con mayor cuidado según sus detonantes, señales y apoyos útiles.</p>',
                unsafe_allow_html=True,
            )

        if not available_units:
            if embedded:
                st.markdown(
                    '<p class="ng-soft-note">Primero guarda un caso o familia para poder crear un perfil individual.</p>',
                    unsafe_allow_html=True,
                )
                st.markdown('</div></div>', unsafe_allow_html=True)
            else:
                st.warning("Primero crea una familia o caso.")
            return

        unit_options = {format_unit_label(u): u["family_id"] for u in available_units}
        unit_labels = list(unit_options.keys())
        default_unit_index = 0
        if st.session_state.get("selected_family_id"):
            for idx, label in enumerate(unit_labels):
                if unit_options[label] == st.session_state.selected_family_id:
                    default_unit_index = idx
                    break

        with st.form("create_profile_form", clear_on_submit=True):
            st.markdown("**1. ¿De quién es este perfil?**")
            unit_label = st.selectbox(
                "Caso o familia donde se guardará",
                unit_labels,
                index=default_unit_index,
                help="El perfil quedará conectado con este caso o familia.",
            )
            alias = st.text_input(
                "Nombre o alias de la persona",
                placeholder="Ejemplo: Daniel, Dani, Persona A",
                help="Puedes usar un alias para proteger la identidad.",
            )
            col_age, col_role = st.columns([0.9, 1.25])
            with col_age:
                age_text = st.text_input(
                    "Edad",
                    placeholder="Ej. 15",
                    help="Déjalo vacío si no quieres registrarla.",
                )
            with col_role:
                role = st.selectbox(
                    "Rol o relación",
                    [
                        "hijo",
                        "hija",
                        "adolescente",
                        "adulto",
                        "madre",
                        "padre",
                        "cuidador",
                        "cuidadora",
                        "estudiante",
                        "usuario_individual",
                        "otro",
                    ],
                    help="Ayuda a adaptar el lenguaje de las respuestas.",
                )

            st.markdown("**2. Información esencial para acompañar mejor**")
            conditions = st.text_area(
                "Características principales",
                placeholder="Ejemplo: autismo, TDAH, alta sensibilidad sensorial, ansiedad escolar, dificultad para cambios de rutina.",
                height=82,
                help="Escribe palabras o frases cortas. No necesitas usar términos clínicos si no los tienes claros.",
            )
            triggers = st.text_area(
                "Lo que suele detonar malestar o saturación",
                placeholder="Ejemplo: ruido, luces fuertes, presión por terminar rápido, cambios inesperados, muchas instrucciones juntas.",
                height=82,
            )
            early_signs = st.text_area(
                "Señales tempranas de que algo no va bien",
                placeholder="Ejemplo: se tapa los oídos, se queda callado, camina de un lado a otro, llora, se irrita, se bloquea.",
                height=82,
            )
            helpful_strategies = st.text_area(
                "Lo que normalmente ayuda",
                placeholder="Ejemplo: hablar bajo, dar tiempo, bajar estímulos, usar una lista corta, respirar, salir a un lugar tranquilo.",
                height=82,
            )
            harmful_strategies = st.text_area(
                "Lo que NO ayuda o puede empeorar",
                placeholder="Ejemplo: regaños, insistir demasiado, tocar sin avisar, hacer muchas preguntas, minimizar lo que siente.",
                height=82,
            )

            with st.expander("Detalles avanzados, si los conoces", expanded=False):
                strengths = st.text_area(
                    "Fortalezas e intereses",
                    placeholder="Ejemplo: memoria visual, gusto por animales, dibujo, videojuegos, música, buena observación.",
                    height=76,
                )
                sensory_needs = st.text_area(
                    "Necesidades sensoriales",
                    placeholder="Ejemplo: audífonos, luz baja, presión profunda, pausas de movimiento, ropa cómoda.",
                    height=76,
                )
                emotional_needs = st.text_area(
                    "Necesidades emocionales",
                    placeholder="Ejemplo: validación breve, tono tranquilo, instrucciones claras, sentir control, anticipación.",
                    height=76,
                )
                autonomy_level = st.text_input(
                    "Nivel de autonomía",
                    placeholder="Ejemplo: requiere apoyo para iniciar tareas, pero puede continuar con una guía breve.",
                )
                sleep_profile = st.text_input(
                    "Sueño y descanso",
                    placeholder="Ejemplo: tarda en dormir, despierta durante la noche, le afectan las pantallas.",
                )
                school_profile = st.text_input(
                    "Escuela o trabajo",
                    placeholder="Ejemplo: se satura en salones ruidosos, requiere instrucciones por pasos.",
                )
                executive_profile = st.text_input(
                    "Organización y función ejecutiva",
                    placeholder="Ejemplo: le cuesta iniciar, priorizar, estimar tiempos o terminar tareas largas.",
                )
                evolution_notes = st.text_area(
                    "Observaciones de seguimiento",
                    placeholder="Ejemplo: ha mejorado con rutinas visuales; conviene evitar preguntas largas cuando está saturado.",
                    height=92,
                )

            submitted = st.form_submit_button("Guardar perfil individual")

            if submitted:
                if not alias.strip():
                    st.warning("Agrega un nombre o alias para identificar este perfil.")
                    return

                parsed_age: Optional[int] = None
                if age_text.strip():
                    try:
                        parsed_age = int(age_text.strip())
                    except ValueError:
                        st.warning("La edad debe ser un número. Puedes dejarla vacía si no quieres registrarla.")
                        return

                pm = get_profile_manager(db_path)
                try:
                    profile_id = pm.create_profile(
                        family_id=unit_options[unit_label],
                        alias=alias.strip() or None,
                        age=parsed_age,
                        role=role or None,
                        conditions=_split_csv(conditions.replace("\n", ",")),
                        strengths=_split_csv(strengths.replace("\n", ",")),
                        triggers=_split_csv(triggers.replace("\n", ",")),
                        early_signs=_split_csv(early_signs.replace("\n", ",")),
                        helpful_strategies=_split_csv(helpful_strategies.replace("\n", ",")),
                        harmful_strategies=_split_csv(harmful_strategies.replace("\n", ",")),
                        sensory_needs=_split_csv(sensory_needs.replace("\n", ",")),
                        emotional_needs=_split_csv(emotional_needs.replace("\n", ",")),
                        autonomy_level=autonomy_level.strip() or None,
                        sleep_profile=sleep_profile.strip() or None,
                        school_profile=school_profile.strip() or None,
                        executive_profile=executive_profile.strip() or None,
                        evolution_notes=evolution_notes.strip() or None,
                    )
                    st.session_state.selected_family_id = unit_options[unit_label]
                    st.session_state.selected_profile_id = profile_id
                    st.success("Perfil guardado correctamente. Ya quedó seleccionado como contexto activo.")
                    st.rerun()
                finally:
                    safe_close(pm)

        if embedded:
            st.markdown('</div></div>', unsafe_allow_html=True)


def resolve_active_context_for_chat() -> Dict[str, Any]:
    """Resolve the selected family/profile immediately before sending a turn.

    This keeps Streamlit's visual selection, the orchestrator and Supabase logs
    aligned. It also protects against reruns where the selector looks active
    but the backend receives None.
    """
    selected_family_id = st.session_state.get("selected_family_id")
    selected_profile_id = st.session_state.get("selected_profile_id")

    active_profile: Optional[Dict[str, Any]] = None
    active_unit: Optional[Dict[str, Any]] = None

    pm = get_profile_manager(st.session_state.db_path)
    try:
        if selected_profile_id:
            active_profile = pm.get_profile(selected_profile_id)
            if active_profile:
                selected_profile_id = active_profile.get("profile_id") or selected_profile_id
                selected_family_id = selected_family_id or active_profile.get("family_id")

        if selected_family_id:
            active_unit = pm.get_unit(selected_family_id)

        if selected_family_id and not active_profile:
            profiles = pm.list_profiles(family_id=selected_family_id, only_active=True)
            if len(profiles) == 1:
                active_profile = profiles[0]
                selected_profile_id = active_profile.get("profile_id")
    finally:
        safe_close(pm)

    st.session_state.selected_family_id = selected_family_id
    st.session_state.selected_profile_id = selected_profile_id

    return {
        "family_id": selected_family_id,
        "profile_id": selected_profile_id,
        "active_profile": active_profile,
        "active_unit": active_unit,
    }


def build_profile_context_payload(active_context: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact profile/unit payload for the orchestrator."""
    profile = active_context.get("active_profile") or {}
    unit = active_context.get("active_unit") or {}

    if not profile and not unit:
        return {}

    return {
        "active_family_id": active_context.get("family_id"),
        "active_profile_id": active_context.get("profile_id"),

        "active_profile": {
            "profile_id": profile.get("profile_id"),
            "family_id": profile.get("family_id"),
            "alias": profile.get("alias"),
            "age": profile.get("age"),
            "role": profile.get("role"),

            # ---------------------------------------------------------
            # ADAPTIVE COMMUNICATION CONTEXT
            # ---------------------------------------------------------
            "communication_style": (
                "Habla de forma cálida, sencilla, breve y apropiada para una niña o adolescente. "
                "Evita lenguaje clínico, adulto o demasiado técnico."
                if (profile.get("age") or 0) < 18
                else "Habla de forma empática y clara para una persona adulta."
            ),

            "developmental_stage": (
                "niña/adolescente"
                if (profile.get("age") or 0) < 18
                else "adulto"
            ),

            "conditions": profile.get("conditions") or [],
            "strengths": profile.get("strengths") or [],
            "triggers": profile.get("triggers") or [],
            "early_signs": profile.get("early_signs") or [],
            "helpful_strategies": profile.get("helpful_strategies") or [],
            "harmful_strategies": profile.get("harmful_strategies") or [],
            "sensory_needs": profile.get("sensory_needs") or [],
            "emotional_needs": profile.get("emotional_needs") or [],
            "autonomy_level": profile.get("autonomy_level"),
            "sleep_profile": profile.get("sleep_profile"),
            "school_profile": profile.get("school_profile"),
            "executive_profile": profile.get("executive_profile"),
            "evolution_notes": profile.get("evolution_notes"),
        },

        "active_unit": {
            "family_id": unit.get("family_id"),
            "unit_type": unit.get("unit_type"),
            "caregiver_alias": unit.get("caregiver_alias"),
            "context_notes": unit.get("context_notes"),
            "support_network": unit.get("support_network"),
            "environmental_factors": unit.get("environmental_factors"),
            "global_history": unit.get("global_history"),
        },
    }




# ---------------------------------------------------------
# SUPABASE COMPATIBILITY + MESSAGE LOGGING
# ---------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_message_db_engine():
    """Return a reusable SQLAlchemy engine for Supabase/PostgreSQL message logging."""
    database_url = str(os.getenv("DATABASE_URL", "") or "").strip()
    if not database_url:
        return None
    return create_engine(database_url, pool_pre_ping=True)


def _run_postgres_statement(sql: str) -> None:
    """Execute a PostgreSQL statement only when DATABASE_URL is available."""
    engine = get_message_db_engine()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text(sql))


def ensure_supabase_compatibility_views() -> None:
    """Create bridge views for legacy names used by internal memory modules."""
    if derive_database_backend() != "postgres":
        return

    bridge_views = {
        "response_memory": "ng_response_memory",
        "user_context_memory": "ng_user_context_memory",
        "routines": "ng_routines",
        "learned_patterns": "ng_learned_patterns",
        "case_memory": "ng_case_memory",
        "families": "ng_families",
        "profiles": "ng_profiles",
    }

    for legacy_name, canonical_name in bridge_views.items():
        try:
            _run_postgres_statement(
                f"""
                create or replace view public.{legacy_name} as
                select * from public.{canonical_name};
                """
            )
        except Exception as exc:
            # No bloqueamos la app: si el puente ya existe como tabla real o
            # Supabase rechaza DDL temporalmente, el flujo principal puede seguir.
            st.session_state["supabase_bridge_warning"] = str(exc)


def save_message_to_db(
    session_id: str,
    user_role: str,
    message: str,
    detected_category: Optional[str] = None,
    emotional_state: Optional[str] = None,
    profile_id: Optional[str] = None,
    family_id: Optional[str] = None,
) -> None:
    """Persist a user or assistant message in public.ng_messages."""
    engine = get_message_db_engine()
    if engine is None:
        st.session_state["db_message_log_error"] = "DATABASE_URL no está configurada."
        return

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    insert into public.ng_messages
                    (
                        session_id,
                        user_role,
                        message,
                        detected_category,
                        emotional_state,
                        profile_id,
                        family_id
                    )
                    values
                    (
                        :session_id,
                        :user_role,
                        :message,
                        :detected_category,
                        :emotional_state,
                        :profile_id,
                        :family_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                    "user_role": user_role,
                    "message": message,
                    "detected_category": detected_category,
                    "emotional_state": emotional_state,
                    "profile_id": profile_id,
                    "family_id": family_id,
                },
            )
        st.session_state.pop("db_message_log_error", None)
    except Exception as exc:
        st.session_state["db_message_log_error"] = str(exc)
        raise


# ---------------------------------------------------------
# CHAT ACTION
# ---------------------------------------------------------
def process_user_message(user_message: str) -> None:
    """Process one user message, render it locally, and persist both turns.

    The selected profile/family is resolved immediately before the orchestrator
    call. This prevents Streamlit reruns from showing "Contexto activo" while
    the backend receives NULL IDs.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        return

    active_context = resolve_active_context_for_chat()
    active_family_id = active_context.get("family_id")
    active_profile_id = active_context.get("profile_id")
    active_profile = active_context.get("active_profile") or {}
    profile_context_payload = build_profile_context_payload(active_context)

    previous_conversation_frame = {}
    if isinstance(st.session_state.last_result, dict):
        previous_conversation_frame = st.session_state.last_result.get("conversation_frame") or {}

    orch = get_orchestrator(st.session_state.db_path)
    try:
        result = orch.process_message(
            message=user_message,
            family_id=active_family_id,
            profile_id=active_profile_id,
            profile_alias=active_profile.get("alias"),
            extra_context={
                "session_scope_id": st.session_state.session_scope_id,
                "conversation_frame": previous_conversation_frame,
                "selected_family_id": active_family_id,
                "selected_profile_id": active_profile_id,
                "profile_context": profile_context_payload,
                "active_profile": profile_context_payload.get("active_profile", {}),
                "active_unit": profile_context_payload.get("active_unit", {}),
            },
            chat_history=build_history_hint(),
            auto_save_case=True,
            auto_store_system_response=st.session_state.auto_store_system_response,
            auto_store_curated_llm_response=st.session_state.auto_store_curated_llm_response,
            use_llm_stub=st.session_state.use_llm_stub,
        )

        response_package = result.get("response_package", {}) or {}
        response_metadata = response_package.get("response_metadata", {}) or {}
        assistant_text = (
            response_package.get("response")
            or response_package.get("text")
            or "No se pudo construir una respuesta en este momento."
        )

        st.session_state.chat_history.append(
            {
                "user": user_message,
                "assistant": assistant_text,
            }
        )

        session_id = st.session_state.get("session_id") or str(uuid.uuid4())
        st.session_state.session_id = session_id

        result_active_profile = result.get("active_profile") or {}
        result_unit_context = result.get("unit_context") or {}
        effective_profile_id = (
            result.get("profile_id")
            or result_active_profile.get("profile_id")
            or active_profile_id
            or st.session_state.get("selected_profile_id")
        )
        effective_family_id = (
            result.get("family_id")
            or result_active_profile.get("family_id")
            or result_unit_context.get("family_id")
            or active_family_id
            or st.session_state.get("selected_family_id")
        )

        detected_category = (
            result.get("detected_category")
            or result.get("category")
            or response_metadata.get("detected_category")
            or response_metadata.get("route_id")
        )
        emotional_state = (
            result.get("emotional_state")
            or result.get("primary_state")
            or response_metadata.get("primary_state")
            or response_metadata.get("support_mode")
        )

        save_message_to_db(
            session_id=session_id,
            user_role="user",
            message=user_message,
            detected_category=detected_category,
            emotional_state=emotional_state,
            profile_id=effective_profile_id,
            family_id=effective_family_id,
        )

        save_message_to_db(
            session_id=session_id,
            user_role="assistant",
            message=assistant_text,
            detected_category=detected_category,
            emotional_state=emotional_state,
            profile_id=effective_profile_id,
            family_id=effective_family_id,
        )

        st.session_state.last_result = result
    finally:
        safe_close(orch)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main() -> None:
    bootstrap_environment(DEFAULT_ENV_PATH)
    init_session_state()
    bootstrap_database(st.session_state.db_backend, st.session_state.db_path)
    ensure_supabase_compatibility_views()

    data = load_units_and_profiles(st.session_state.db_path)
    units = data["units"]
    unit_profiles = data["unit_profiles"]

    render_shell_start()
    render_app_header(show_full_logo=False)
    user_message = None
    st.markdown('<div class="ng-layout-grid">', unsafe_allow_html=True)
    col_left, col_center, col_right = st.columns([1.85, 3.7, 1.85], gap="large")

    with col_left:
        render_context_sidebar(units, unit_profiles)

    with col_center:
        render_chat_history()
        user_message = render_main_input()

    with col_right:
        render_quick_help_sidebar()
        render_response_debug_metadata()
        if st.session_state.get("db_message_log_error"):
            st.error(f"Error guardando mensajes: {st.session_state['db_message_log_error']}")
        if st.session_state.get("supabase_bridge_warning") and env_flag("DEBUG_MODE", False):
            st.warning(f"Aviso puente Supabase: {st.session_state['supabase_bridge_warning']}")

    st.markdown('</div>', unsafe_allow_html=True)

    if user_message and user_message.strip():
        process_user_message(user_message)
        st.rerun()

    render_shell_end()


if __name__ == "__main__":
    main()
