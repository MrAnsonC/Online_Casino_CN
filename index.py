import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
del _install_secure_json, _account_root, _AccountPath, _account_sys

import ctypes
import importlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Dependency bootstrap (Windows)
# ---------------------------------------------------------------------------
# Python import name -> pip package name
_REQUIRED_PIP_PACKAGES = {
    "PIL": "Pillow",
    "cryptography": "cryptography",
}
_INSTALL_FLAG = "--install-dependencies-only"
_BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))


def _native_message(title: str, message: str, ask: bool = False) -> bool:
    """Show a Windows message box before Tkinter/third-party imports are loaded."""
    if os.name == "nt":
        flags = 0x00000004 | 0x00000030 if ask else 0x00000000 | 0x00000040
        result = ctypes.windll.user32.MessageBoxW(None, message, title, flags)
        return result == 6 if ask else True  # IDYES = 6

    # Fallback for non-Windows systems.
    print(f"{title}: {message}")
    if ask:
        try:
            return input("Continue? [y/N]: ").strip().lower() in {"y", "yes"}
        except (EOFError, KeyboardInterrupt):
            return False
    return True


def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _missing_pip_packages() -> list[str]:
    return [
        pip_name
        for module_name, pip_name in _REQUIRED_PIP_PACKAGES.items()
        if not _can_import(module_name)
    ]


def _check_tkinter() -> None:
    if _can_import("tkinter"):
        return
    _native_message(
        "缺少图形组件 / 缺少圖形元件 / GUI component missing",
        "【简体中文】找不到 tkinter / Tcl-Tk。tkinter 不能通过本游戏的 pip 依赖安装流程正确安装。请修改或重新安装 Python，并加入 Tcl/Tk and IDLE，然后重新打开游戏。\n\n"
        "【繁體中文】找不到 tkinter / Tcl-Tk。tkinter 無法透過本遊戲的 pip 相依套件安裝流程正確安裝。請修改或重新安裝 Python，並加入 Tcl/Tk and IDLE，然後重新開啟遊戲。\n\n"
        "【British English】tkinter / Tcl-Tk was not found. It cannot be correctly installed through this game's pip dependency process. Modify or reinstall Python with Tcl/Tk and IDLE, then reopen the game.\n\n"
        "【Te Reo Māori】Kāore i kitea te tkinter / Tcl-Tk. Kāore e tika kia tāutatia mā te tukanga pip o tēnei kēmu. Whakarerekētia, tāuta anō rānei i a Python me Tcl/Tk and IDLE, kātahi ka whakatuwhera anō i te kēmu.\n\n"
        "【Esperanto】tkinter / Tcl-Tk ne estis trovita. Ĝi ne povas esti ĝuste instalita per la pip-dependeca procezo de ĉi tiu ludo. Modifu aŭ reinstalu Python kun Tcl/Tk and IDLE, poste remalfermu la ludon.",
    )
    raise SystemExit(1)


def _install_packages_as_current_admin(packages: list[str]) -> int:
    """Run only in the elevated helper process."""
    log_path = os.path.join(_BOOTSTRAP_DIR, "dependency_install.log")
    output_parts: list[str] = []

    try:
        pip_check = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        output_parts.append(pip_check.stdout)
        output_parts.append(pip_check.stderr)

        if pip_check.returncode != 0:
            ensure = subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            output_parts.extend([ensure.stdout, ensure.stderr])
            if ensure.returncode != 0:
                raise RuntimeError("無法啟用 pip。")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                *packages,
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
        output_parts.extend([result.stdout, result.stderr])

        with open(log_path, "w", encoding="utf-8") as log:
            log.write("\n".join(part for part in output_parts if part))

        return result.returncode
    except Exception as exc:
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                log.write("\n".join(part for part in output_parts if part))
                log.write(f"\n\nERROR: {exc!r}\n")
        except OSError:
            pass
        return 1


def _run_elevated_installer(packages: list[str]) -> Optional[bool]:
    """Run the installer elevated. True=success, None=UAC declined, False=other failure."""
    if os.name != "nt":
        _native_message(
            "無法自動安裝",
            "此自動管理員安裝流程只支援 Windows。\n"
            f"缺少：{', '.join(packages)}",
        )
        return False

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("fMask", ctypes.c_ulong),
            ("hwnd", ctypes.c_void_p),
            ("lpVerb", ctypes.c_wchar_p),
            ("lpFile", ctypes.c_wchar_p),
            ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.c_void_p),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_wchar_p),
            ("hkeyClass", ctypes.c_void_p),
            ("dwHotKey", ctypes.c_ulong),
            ("hIconOrMonitor", ctypes.c_void_p),
            ("hProcess", ctypes.c_void_p),
        ]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SW_SHOWNORMAL = 1
    INFINITE = 0xFFFFFFFF

    params = subprocess.list2cmdline([os.path.abspath(__file__), _INSTALL_FLAG])
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = sys.executable
    info.lpParameters = params
    info.lpDirectory = _BOOTSTRAP_DIR
    info.nShow = SW_SHOWNORMAL

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        # ERROR_CANCELLED (1223) means the player clicked No/Cancel on UAC.
        if ctypes.windll.kernel32.GetLastError() == 1223:
            return None
        return False

    if not info.hProcess:
        return False

    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, INFINITE)
    exit_code = ctypes.c_ulong(1)
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return exit_code.value == 0


def _dependency_details(missing: list[str], language: str) -> str:
    """Return descriptions only for packages that are actually missing."""
    descriptions = {
        "sc": {
            "Pillow": "• Pillow（程式中以 PIL 导入）：用于读取、缩放和显示游戏图片资源。",
            "cryptography": "• cryptography：为游戏中的部分组件提供所需的加密功能。",
        },
        "tc": {
            "Pillow": "• Pillow（程式中以 PIL 匯入）：用於讀取、縮放及顯示遊戲圖片資源。",
            "cryptography": "• cryptography：為遊戲中的部分元件提供所需的加密功能。",
        },
        "en": {
            "Pillow": "• Pillow (imported by the program as PIL): used to load, resize and display game image assets.",
            "cryptography": "• cryptography: provides cryptographic functions required by parts of the game.",
        },
        "mi": {
            "Pillow": "• Pillow (ka kawemai hei PIL): hei uta, hei whakarahi, hei whakaiti, hei whakaatu hoki i ngā atahanga o te kēmu.",
            "cryptography": "• cryptography: e whakarato ana i ngā mahi whakamuna e hiahiatia ana e ētahi wāhanga o te kēmu.",
        },
        "eo": {
            "Pillow": "• Pillow (importata de la programo kiel PIL): uzata por ŝargi, regrandigi kaj montri la bildajn rimedojn de la ludo.",
            "cryptography": "• cryptography: provizas ĉifradajn funkciojn bezonatajn de iuj partoj de la ludo.",
        },
    }
    return "\n".join(descriptions[language][pkg] for pkg in missing if pkg in descriptions[language])


def _show_dependency_setup_wizard(missing: list[str]) -> tuple[str, str]:
    """Show language selection followed by four single-language consent pages.

    Returns (choice, language):
        choice = "auto", "manual", or "reject"
        language = sc/tc/en/mi/eo

    No UAC request is made here. UAC is requested only after the player has
    reached page 4 and explicitly selected automatic installation.
    """
    import tkinter as tk
    from tkinter import ttk

    package_text = ", ".join(missing)
    manual_command = f'pip install {" ".join(missing)}'

    languages = {
        "sc": {
            "name": "简体中文",
            "font": "Microsoft YaHei UI",
            "window_title": "游戏运行依赖安装",
            "select_title": "请选择说明语言",
            "select_note": "选择后，后续安装说明只会显示该语言。",
            "exit": "退出游戏",
            "agree": "我知道并同意 →",
            "disagree": "我拒绝",
            "auto": "我知道并同意 — 系统帮我安装",
            "manual": "我知道并同意 — 手动安装",
            "copy": "快速复制命令",
            "copied": "已复制到剪贴板",
            "manual_title": "手动安装",
            "manual_sub": "请复制下方命令自行安装。安装完成后必须重新打开程式。",
            "manual_exit": "关闭游戏",
            "command_label": "安装命令（Windows CMD / PowerShell）",
            "pages": [
                (
                    "第 1 页（共 4 页）：需要安装的 Python 库",
                    "请确认您了解本游戏目前缺少哪些组件。",
                    "检测到本游戏目前缺少以下 Python 第三方库：\n\n"
                    "{details}\n\n"
                    "这里只列出本次实际检测为缺失的库；已经能够正常导入的库不会重复安装。"
                    "这些库不是游戏本体的一部分，但当前游戏功能需要它们才能正常载入。\n\n"
                    "按“我知道并同意”表示您已经看清并理解本次需要安装的库；若您不希望继续，请按“我拒绝”，游戏会立即关闭。"
                ),
                (
                    "第 2 页（共 4 页）：下载与安装方式",
                    "请确认您了解程式将如何取得并安装这些组件。",
                    "如果稍后选择“系统帮我安装”，本程式会使用当前执行游戏的 Python 所附带的 pip，安装本次缺少的库：{packages}。\n\n"
                    "pip 会通过您电脑当前配置的 Python 套件来源下载这些库。一般情况下来源为 Python Package Index（PyPI），但如果您的电脑、公司或学校曾修改 pip 设置，实际来源可能不同。"
                    "pip 也可能一并下载这些库正常运作所必需的相依套件。\n\n"
                    "下载过程需要可用的网络连接，并可能受到代理服务器、防火墙、防毒软件、套件来源或网络状况影响。"
                    "本游戏不会因为此步骤而安装与这些缺失库无关的游戏软件。\n\n"
                    "按“我知道并同意”表示您了解上述下载与安装方式。"
                ),
                (
                    "第 3 页（共 4 页）：管理员权限",
                    "请确认您了解自动安装时为什么会出现 Windows UAC。",
                    "只有在第 4 页选择“系统帮我安装”后，本游戏才会要求 Windows 管理员权限。Windows 会显示用户帐户控制（UAC）视窗，由您决定是否允许。\n\n"
                    "管理员权限用于让当前 Python / pip 有足够权限完成安装。游戏本身不会要求、读取或保存您的 Windows 管理员密码；密码或授权流程由 Windows 自己处理。\n\n"
                    "如果您在 UAC 中按“否”、取消或关闭该视窗，安装不会继续，游戏也会立即关闭。"
                    "如果您不希望游戏请求 UAC，可在第 4 页选择“手动安装”。\n\n"
                    "按“我知道并同意”表示您理解自动安装可能需要管理员权限。"
                ),
                (
                    "第 4 页（共 4 页）：风险、责任与最终选择",
                    "阅读完成后，请选择自动安装、手动安装或拒绝。",
                    "上述 Python 第三方库由各自的发布者提供，并非由本游戏开发者编写或控制。下载、安装和使用第三方组件可能受到网络中断、套件来源变更、防毒或安全软件、权限设置、Python 版本、现有环境冲突，以及第三方软件自身问题的影响。\n\n"
                    "如果当前 Python 环境包含重要项目、资料或特殊配置，建议您在继续前自行备份，或使用独立的 Python 环境。"
                    "无论选择自动或手动安装，您都应在理解用途和风险后再继续。\n\n"
                    "在适用法律允许的范围内，因下载、安装、相容性、环境变更、第三方组件或其使用而产生的系统、环境、资料或其他损失，开发者不承担责任。"
                    "本说明不会排除或限制依法不能排除或限制的权利与责任。\n\n"
                    "选择“系统帮我安装”表示您同意前述四页内容，并允许下一步出现 Windows UAC。"
                    "选择“手动安装”表示您同意前述四页内容，但希望自行执行安装命令。按“我拒绝”则立即关闭游戏，不会启动自动安装。"
                ),
            ],
            "manual_text": (
                "您选择了手动安装。目前仍缺少：{packages}。\n\n"
                "请复制下方命令，并在 Windows 命令提示符（CMD）或 PowerShell 中执行。"
                "这是最常见、最简洁的 pip 安装方式：\n\n"
                "{command}\n\n"
                "您可以单击命令框后按 Ctrl+A、Ctrl+C，或直接按“快速复制命令”。"
                "如果终端显示权限不足，可由您自行决定是否以管理员身份重新打开终端后再执行。\n\n"
                "安装成功后，请关闭本页面，并重新打开 index.py。下一次启动时，程式会再次检查缺失库；如果已经安装完成，就会直接进入游戏。"
            ),
        },
        "tc": {
            "name": "繁體中文",
            "font": "Microsoft JhengHei UI",
            "window_title": "遊戲執行依賴安裝",
            "select_title": "請選擇說明語言",
            "select_note": "選擇後，後續安裝說明只會顯示該語言。",
            "exit": "退出遊戲",
            "agree": "我知道並同意 →",
            "disagree": "我拒絕",
            "auto": "我知道並同意 — 系統幫我安裝",
            "manual": "我知道並同意 — 手動安裝",
            "copy": "快速複製指令",
            "copied": "已複製到剪貼簿",
            "manual_title": "手動安裝",
            "manual_sub": "請複製下方指令自行安裝。安裝完成後必須重新開啟程式。",
            "manual_exit": "關閉遊戲",
            "command_label": "安裝指令（Windows CMD / PowerShell）",
            "pages": [
                (
                    "第 1 頁（共 4 頁）：需要安裝的 Python 函式庫",
                    "請確認您了解本遊戲目前缺少哪些元件。",
                    "偵測到本遊戲目前缺少以下 Python 第三方函式庫：\n\n"
                    "{details}\n\n"
                    "這裡只列出本次實際偵測為缺失的函式庫；已經能正常匯入的函式庫不會重複安裝。"
                    "這些函式庫不是遊戲本體的一部分，但目前的遊戲功能需要它們才能正常載入。\n\n"
                    "按「我知道並同意」表示您已看清並理解本次需要安裝的函式庫；若您不希望繼續，請按「我拒絕」，遊戲會立即關閉。"
                ),
                (
                    "第 2 頁（共 4 頁）：下載與安裝方式",
                    "請確認您了解程式將如何取得並安裝這些元件。",
                    "如果稍後選擇「系統幫我安裝」，本程式會使用目前執行遊戲的 Python 所附帶的 pip，安裝本次缺少的函式庫：{packages}。\n\n"
                    "pip 會透過您電腦目前設定的 Python 套件來源下載這些函式庫。一般情況下來源為 Python Package Index（PyPI），但如果您的電腦、公司或學校曾修改 pip 設定，實際來源可能不同。"
                    "pip 亦可能一併下載這些函式庫正常運作所必需的相依套件。\n\n"
                    "下載過程需要可用的網路連線，並可能受到 Proxy、防火牆、防毒軟體、套件來源或網路狀況影響。"
                    "本遊戲不會因為此步驟而安裝與這些缺失函式庫無關的遊戲軟體。\n\n"
                    "按「我知道並同意」表示您了解上述下載與安裝方式。"
                ),
                (
                    "第 3 頁（共 4 頁）：系統管理員權限",
                    "請確認您了解自動安裝時為甚麼會出現 Windows UAC。",
                    "只有在第 4 頁選擇「系統幫我安裝」後，本遊戲才會要求 Windows 系統管理員權限。Windows 會顯示使用者帳戶控制（UAC）視窗，由您決定是否允許。\n\n"
                    "系統管理員權限用於讓目前的 Python / pip 有足夠權限完成安裝。遊戲本身不會要求、讀取或儲存您的 Windows 系統管理員密碼；密碼或授權流程由 Windows 自己處理。\n\n"
                    "如果您在 UAC 中按「否」、取消或關閉該視窗，安裝不會繼續，遊戲也會立即關閉。"
                    "如果您不希望遊戲要求 UAC，可在第 4 頁選擇「手動安裝」。\n\n"
                    "按「我知道並同意」表示您理解自動安裝可能需要系統管理員權限。"
                ),
                (
                    "第 4 頁（共 4 頁）：風險、責任與最終選擇",
                    "閱讀完成後，請選擇自動安裝、手動安裝或拒絕。",
                    "上述 Python 第三方函式庫由各自的發佈者提供，並非由本遊戲開發者編寫或控制。下載、安裝及使用第三方元件可能受到網路中斷、套件來源變更、防毒或安全軟體、權限設定、Python 版本、既有環境衝突，以及第三方軟體本身問題的影響。\n\n"
                    "如果目前 Python 環境包含重要專案、資料或特殊設定，建議您在繼續前自行備份，或使用獨立的 Python 環境。"
                    "無論選擇自動或手動安裝，您都應在理解用途及風險後再繼續。\n\n"
                    "在適用法律允許的範圍內，因下載、安裝、相容性、環境變更、第三方元件或其使用而產生的系統、環境、資料或其他損失，開發者不承擔責任。"
                    "本說明不會排除或限制依法不能排除或限制的權利與責任。\n\n"
                    "選擇「系統幫我安裝」表示您同意前述四頁內容，並允許下一步出現 Windows UAC。"
                    "選擇「手動安裝」表示您同意前述四頁內容，但希望自行執行安裝指令。按「我拒絕」則立即關閉遊戲，不會啟動自動安裝。"
                ),
            ],
            "manual_text": (
                "您選擇了手動安裝。目前仍缺少：{packages}。\n\n"
                "請複製下方指令，並在 Windows 命令提示字元（CMD）或 PowerShell 中執行。"
                "這是最常見、最簡潔的 pip 安裝方式：\n\n"
                "{command}\n\n"
                "您可以點選指令框後按 Ctrl+A、Ctrl+C，或直接按「快速複製指令」。"
                "如果終端顯示權限不足，可由您自行決定是否以系統管理員身分重新開啟終端後再執行。\n\n"
                "安裝成功後，請關閉本頁面，並重新開啟 index.py。下一次啟動時，程式會再次檢查缺失函式庫；如果已經安裝完成，就會直接進入遊戲。"
            ),
        },
        "en": {
            "name": "British English",
            "font": "Segoe UI",
            "window_title": "Game Dependency Installation",
            "select_title": "Choose your language",
            "select_note": "After you choose, the remaining installation pages will be shown only in that language.",
            "exit": "Exit game",
            "agree": "I UNDERSTAND & AGREE →",
            "disagree": "I DISAGREE",
            "auto": "I UNDERSTAND & AGREE — Install for me",
            "manual": "I UNDERSTAND & AGREE — Manual installation",
            "copy": "Quick copy command",
            "copied": "Copied to clipboard",
            "manual_title": "Manual installation",
            "manual_sub": "Copy and run the command below yourself. Reopen the program after installation.",
            "manual_exit": "Exit game",
            "command_label": "Installation command (Windows CMD / PowerShell)",
            "pages": [
                (
                    "Page 1 of 4: Required Python libraries",
                    "Confirm that you understand which components are currently missing.",
                    "The game has detected that the following third-party Python libraries are currently missing:\n\n"
                    "{details}\n\n"
                    "Only libraries actually found to be missing in this run are listed here; libraries that can already be imported successfully will not be reinstalled. "
                    "These libraries are not part of the game itself, but the current game functions require them in order to load correctly.\n\n"
                    "Selecting “I UNDERSTAND & AGREE” confirms that you have read and understood which libraries need to be installed. If you do not wish to continue, select “I DISAGREE”; the game will close immediately."
                ),
                (
                    "Page 2 of 4: Download and installation method",
                    "Confirm that you understand how these components will be obtained and installed.",
                    "If you later choose “Install for me”, the program will use pip from the Python installation currently running the game to install the missing libraries: {packages}.\n\n"
                    "pip downloads packages through the Python package source currently configured on your computer. This is normally the Python Package Index (PyPI), but the actual source can differ if you, your organisation, or your school has changed pip configuration. "
                    "pip may also download dependency packages required for these libraries to work correctly.\n\n"
                    "A working Internet connection is required. The download can be affected by proxies, firewalls, antivirus/security software, package-source availability, or network conditions. "
                    "This step does not intentionally install unrelated game software.\n\n"
                    "Selecting “I UNDERSTAND & AGREE” confirms that you understand this download and installation method."
                ),
                (
                    "Page 3 of 4: Administrator privileges",
                    "Confirm that you understand why Windows UAC may appear during automatic installation.",
                    "The game will request Windows administrator privileges only if you select “Install for me” on page 4. Windows will display a User Account Control (UAC) prompt and you decide whether to allow it.\n\n"
                    "Administrator privileges are used so that the current Python/pip process has sufficient permission to complete the installation. The game does not ask for, read, or store your Windows administrator password; any password or approval process is handled by Windows itself.\n\n"
                    "If you select No, cancel, or close the UAC prompt, installation will not continue and the game will close immediately. If you do not want the game to request UAC, you may choose “Manual installation” on page 4.\n\n"
                    "Selecting “I UNDERSTAND & AGREE” confirms that you understand that automatic installation may require administrator privileges."
                ),
                (
                    "Page 4 of 4: Risk, responsibility and final choice",
                    "After reading this page, choose automatic installation, manual installation, or decline.",
                    "The third-party Python libraries above are supplied by their respective publishers and are not written or controlled by the game developer. Downloading, installing, and using third-party components can be affected by network interruption, package-source changes, antivirus/security software, permissions, Python versions, existing environment conflicts, or defects in the third-party software itself.\n\n"
                    "If this Python environment contains important projects, data, or custom configuration, consider making your own backup or using an isolated Python environment before continuing. Whether you choose automatic or manual installation, continue only after you understand the purpose and risks.\n\n"
                    "To the extent permitted by applicable law, the developer accepts no responsibility for system, environment, data, or other loss arising from downloading, installation, compatibility, environment changes, third-party components, or their use. Nothing in this notice excludes or limits rights or liabilities that cannot lawfully be excluded or limited.\n\n"
                    "Selecting “Install for me” confirms your agreement with the preceding four pages and allows Windows UAC to be requested next. Selecting “Manual installation” confirms the same agreement but lets you run the installation command yourself. Selecting “I DISAGREE” closes the game immediately and no automatic installation is started."
                ),
            ],
            "manual_text": (
                "You selected manual installation. The following packages are still missing: {packages}.\n\n"
                "Copy the command below and run it in Windows Command Prompt (CMD) or PowerShell. This is the usual, concise pip installation command:\n\n"
                "{command}\n\n"
                "Click the command field and press Ctrl+A then Ctrl+C, or select “Quick copy command”. If the terminal reports insufficient permissions, you may decide whether to reopen the terminal as administrator and run it again.\n\n"
                "After installation succeeds, close this page and reopen index.py. On the next start-up, the program will check the missing libraries again; if they are installed, the game will open normally."
            ),
        },
        "mi": {
            "name": "Te Reo Māori",
            "font": "Segoe UI",
            "window_title": "Tāutanga Whirinakitanga Kēmu",
            "select_title": "Kōwhiria tō reo",
            "select_note": "Ka mutu tō kōwhiri, ka whakaaturia ngā whārangi tāutanga e whai ake nei ki taua reo anake.",
            "exit": "Puta i te kēmu",
            "agree": "KUA MĀRAMA AU, Ā, E WHAKAAE ANA AU →",
            "disagree": "KĀORE AU E WHAKAAE",
            "auto": "E WHAKAAE ANA AU — Tāutahia māku",
            "manual": "E WHAKAAE ANA AU — Tāuta ā-ringa",
            "copy": "Tārua tere i te tono",
            "copied": "Kua tāruatia ki te papatopenga",
            "manual_title": "Tāuta ā-ringa",
            "manual_sub": "Tāruatia, whakahaerehia hoki te tono i raro nei. Me whakatuwhera anō te papatono i muri i te tāutanga.",
            "manual_exit": "Puta i te kēmu",
            "command_label": "Tono tāutanga (Windows CMD / PowerShell)",
            "pages": [
                (
                    "Whārangi 1 o te 4: Ngā whare pukapuka Python e hiahiatia ana",
                    "Whakaū kua mārama koe ko ēhea wāhanga kei te ngaro.",
                    "Kua kitea e te kēmu kāore i te wātea ēnei whare pukapuka Python tuatoru:\n\n"
                    "{details}\n\n"
                    "Ko ngā whare pukapuka kua kitea e ngaro ana i tēnei whakahaerenga anake ka whakarārangitia; kāore e tāuta anōtia ngā mea ka taea kē te kawemai. "
                    "Ehara ēnei whare pukapuka i te kēmu ake, engari e hiahiatia ana kia tika te uta o ētahi āhuatanga o te kēmu.\n\n"
                    "Mā te kōwhiri “KUA MĀRAMA AU, Ā, E WHAKAAE ANA AU” ka whakaū koe kua pānui, kua mārama hoki koe ki ngā whare pukapuka e tika ana kia tāutatia. Ki te kore koe e hiahia ki te haere tonu, kōwhiria “KĀORE AU E WHAKAAE”; ka kati tonu te kēmu."
                ),
                (
                    "Whārangi 2 o te 4: Te tikiake me te tikanga tāuta",
                    "Whakaū kua mārama koe me pēhea te tiki me te tāuta i ēnei wāhanga.",
                    "Ki te kōwhiri koe i muri mai i “Tāutahia māku”, ka whakamahia e te papatono te pip o te Python e whakahaere ana i te kēmu hei tāuta i ngā whare pukapuka e ngaro ana: {packages}.\n\n"
                    "Ka tikiake a pip mā te puna mōkī Python kua whirihorahia i tō rorohiko. Ko Python Package Index (PyPI) te puna noa, engari tērā pea he puna kē mēnā kua whakarerekētia ngā tautuhinga pip e koe, e tō whakahaere, e tō kura rānei. "
                    "Ka taea hoki e pip te tiki i ngā mōkī whirinaki e hiahiatia ana kia mahi tika aua whare pukapuka.\n\n"
                    "Me whai hononga Ipurangi e mahi ana. Ka pā pea ngā takawaenga, ngā pātūahi, ngā pūmanawa wheori/haumarutanga, te wātea o te puna mōkī, me ngā āhuatanga whatunga ki te tikiake. "
                    "Kāore tēnei hipanga e whai kia tāuta i ētahi atu pūmanawa kēmu kāore e hāngai ana ki ngā whare pukapuka e ngaro ana.\n\n"
                    "Mā te kōwhiri “KUA MĀRAMA AU, Ā, E WHAKAAE ANA AU” ka whakaū koe kua mārama ki tēnei tikanga tikiake me te tāuta."
                ),
                (
                    "Whārangi 3 o te 4: Ngā mana kaiwhakahaere",
                    "Whakaū kua mārama koe he aha ka puta ai pea a Windows UAC i te tāutanga aunoa.",
                    "Ka tono te kēmu i ngā mana kaiwhakahaere Windows anake mēnā ka kōwhiri koe i “Tāutahia māku” i te whārangi 4. Ka whakaatu a Windows i te matapihi User Account Control (UAC), ā, māu tonu e whakaae, e whakahē rānei.\n\n"
                    "Ka whakamahia ngā mana kaiwhakahaere kia whai whakaaetanga nui te tukanga Python/pip o nāianei ki te whakaoti i te tāutanga. Kāore te kēmu e tono, e pānui, e rokiroki rānei i tō kupuhipa kaiwhakahaere Windows; mā Windows tonu ngā kupuhipa me te tukanga whakaaetanga e whakahaere.\n\n"
                    "Ki te kōwhiri koe i te Kāo, ki te whakakore, ki te kati rānei i te UAC, kāore te tāutanga e haere tonu, ā, ka kati tonu te kēmu. Ki te kore koe e hiahia kia tono te kēmu i te UAC, kōwhiria te “Tāuta ā-ringa” i te whārangi 4.\n\n"
                    "Mā te kōwhiri “KUA MĀRAMA AU, Ā, E WHAKAAE ANA AU” ka whakaū koe kua mārama ka hiahiatia pea ngā mana kaiwhakahaere mō te tāutanga aunoa."
                ),
                (
                    "Whārangi 4 o te 4: Mōrea, kawenga me te kōwhiringa whakamutunga",
                    "Ka mutu te pānui, kōwhiria te tāuta aunoa, te tāuta ā-ringa, te whakahē rānei.",
                    "Nā ō rātou ake kaiwhakaputa ngā whare pukapuka Python tuatoru i runga ake nei; ehara i te mea nā te kaiwhakawhanake kēmu i tuhi, i whakahaere rānei. Ka pā pea te motunga whatunga, te whakarerekē puna mōkī, ngā pūmanawa wheori/haumarutanga, ngā whakaaetanga, ngā putanga Python, ngā taupatupatu o te taiao o nāianei, me ngā hapa o ngā pūmanawa tuatoru ki te tikiake, te tāuta me te whakamahi.\n\n"
                    "Mēnā he kaupapa hira, he raraunga, he tautuhinga motuhake rānei kei tēnei taiao Python, whakaarohia te hanga tārua, te whakamahi rānei i tētahi taiao Python motuhake i mua i te haere tonu. Haere tonu anake ina mārama koe ki te kaupapa me ngā mōrea.\n\n"
                    "Ki te whānuitanga e whakaaetia ana e te ture e hāngai ana, kāore te kaiwhakawhanake e kawe kawenga mō te ngaronga o te pūnaha, te taiao, te raraunga, me ētahi atu ngaronga e puta mai ana i te tikiake, te tāuta, te hototahitanga, ngā panonitanga taiao, ngā wāhanga tuatoru, te whakamahinga rānei. Kāore tēnei pānui e whakakore, e whakawhāiti rānei i ngā motika, i ngā taunahatanga kāore e āhei te whakakore, te whakawhāiti rānei i raro i te ture.\n\n"
                    "Mā te kōwhiri “Tāutahia māku” ka whakaae koe ki ngā whārangi e whā o mua, ā, ka āhei te tono Windows UAC i muri mai. Mā te kōwhiri “Tāuta ā-ringa” ka whakaae hoki koe, engari māu te tono tāutanga e whakahaere. Mā te kōwhiri “KĀORE AU E WHAKAAE” ka kati tonu te kēmu, ā, kāore he tāutanga aunoa e tīmata."
                ),
            ],
            "manual_text": (
                "Kua kōwhiria e koe te tāuta ā-ringa. Kei te ngaro tonu ēnei mōkī: {packages}.\n\n"
                "Tāruatia te tono i raro nei, ka whakahaere ai ki Windows Command Prompt (CMD), ki PowerShell rānei. Koinei te tono pip māmā, whakamahia whānuitia hoki:\n\n"
                "{command}\n\n"
                "Pāwhiritia te pouaka tono, kātahi ka pēhi Ctrl+A me Ctrl+C, ka kōwhiri rānei i “Tārua tere i te tono”. Ki te kī te kāpeka kāore i rawaka ngā whakaaetanga, māu e whakatau mēnā ka whakatuwhera anō hei kaiwhakahaere.\n\n"
                "Kia angitu te tāutanga, katia tēnei whārangi, kātahi ka whakatuwhera anō i index.py. I te tīmatanga e whai ake nei ka tirohia anō ngā whare pukapuka; mēnā kua tāutatia, ka uru tika ki te kēmu."
            ),
        },
        "eo": {
            "name": "Esperanto",
            "font": "Segoe UI",
            "window_title": "Instalado de Ludaj Dependecoj",
            "select_title": "Elektu vian lingvon",
            "select_note": "Post via elekto, la sekvaj instalaj paĝoj aperos nur en tiu lingvo.",
            "exit": "Eliri el la ludo",
            "agree": "MI KOMPRENAS KAJ KONSENTAS →",
            "disagree": "MI NE KONSENTAS",
            "auto": "MI KONSENTAS — Instalu por mi",
            "manual": "MI KONSENTAS — Mana instalado",
            "copy": "Rapide kopii la komandon",
            "copied": "Kopiita al la tondujo",
            "manual_title": "Mana instalado",
            "manual_sub": "Kopiu kaj mem rulu la suban komandon. Remalfermu la programon post instalado.",
            "manual_exit": "Eliri el la ludo",
            "command_label": "Instala komando (Windows CMD / PowerShell)",
            "pages": [
                (
                    "Paĝo 1 el 4: Bezonataj Python-bibliotekoj",
                    "Konfirmu, ke vi komprenas kiuj komponantoj nun mankas.",
                    "La ludo detektis, ke la jenaj triaj Python-bibliotekoj nun mankas:\n\n"
                    "{details}\n\n"
                    "Ĉi tie aperas nur bibliotekoj efektive trovitaj kiel mankantaj dum ĉi tiu lanĉo; bibliotekoj jam sukcese importeblaj ne estos reinstalitaj. "
                    "Tiuj bibliotekoj ne estas parto de la ludo mem, sed la nunaj ludaj funkcioj bezonas ilin por ĝuste ŝargiĝi.\n\n"
                    "Elektante “MI KOMPRENAS KAJ KONSENTAS” vi konfirmas, ke vi legis kaj komprenis kiuj bibliotekoj devas esti instalitaj. Se vi ne volas daŭrigi, elektu “MI NE KONSENTAS”; la ludo tuj fermiĝos."
                ),
                (
                    "Paĝo 2 el 4: Elŝuta kaj instala metodo",
                    "Konfirmu, ke vi komprenas kiel ĉi tiuj komponantoj estos akiritaj kaj instalitaj.",
                    "Se vi poste elektos “Instalu por mi”, la programo uzos pip de la Python-instalaĵo, kiu nun rulas la ludon, por instali la mankantajn bibliotekojn: {packages}.\n\n"
                    "pip elŝutas pakaĵojn per la Python-pakaĵfonto nun agordita en via komputilo. Kutime tio estas Python Package Index (PyPI), sed la efektiva fonto povas esti alia se vi, via organizo aŭ via lernejo ŝanĝis la pip-agordon. "
                    "pip ankaŭ povas elŝuti dependecajn pakaĵojn necesajn por ĝusta funkciado de tiuj bibliotekoj.\n\n"
                    "Necesas funkcianta interreta konekto. La elŝuto povas esti influita de prokuriloj, fajroŝirmiloj, kontraŭvirusaj aŭ sekurecaj programoj, havebleco de la pakaĵfonto aŭ retaj kondiĉoj. "
                    "Ĉi tiu paŝo ne intence instalas nerilatan ludprogramaron.\n\n"
                    "Elektante “MI KOMPRENAS KAJ KONSENTAS” vi konfirmas, ke vi komprenas ĉi tiun elŝutan kaj instalan metodon."
                ),
                (
                    "Paĝo 3 el 4: Administrantaj rajtoj",
                    "Konfirmu, ke vi komprenas kial Windows UAC povas aperi dum aŭtomata instalado.",
                    "La ludo petos administrantajn rajtojn de Windows nur se vi elektos “Instalu por mi” en paĝo 4. Windows montros peton de User Account Control (UAC), kaj vi mem decidos ĉu permesi ĝin.\n\n"
                    "Administrantaj rajtoj estas uzataj por doni al la nuna Python/pip-procezo sufiĉan permeson por fini la instaladon. La ludo ne petas, legas aŭ konservas vian administrantan pasvorton de Windows; ĉiu pasvorta aŭ aprobprocezo estas pritraktata de Windows mem.\n\n"
                    "Se vi elektos Ne, nuligos aŭ fermos la UAC-peton, la instalado ne daŭros kaj la ludo tuj fermiĝos. Se vi ne volas, ke la ludo petu UAC, elektu “Mana instalado” en paĝo 4.\n\n"
                    "Elektante “MI KOMPRENAS KAJ KONSENTAS” vi konfirmas, ke vi komprenas, ke aŭtomata instalado povas bezoni administrantajn rajtojn."
                ),
                (
                    "Paĝo 4 el 4: Risko, respondeco kaj fina elekto",
                    "Post legado elektu aŭtomatan instaladon, manan instaladon aŭ rifuzu.",
                    "La supraj triaj Python-bibliotekoj estas liverataj de siaj respektivaj eldonantoj kaj ne estas verkitaj aŭ regataj de la ludprogramisto. Elŝutado, instalado kaj uzado de triaj komponantoj povas esti influitaj de retinterrompoj, ŝanĝoj de pakaĵfontoj, kontraŭvirusaj aŭ sekurecaj programoj, permesoj, Python-versioj, konfliktoj en ekzistanta medio aŭ problemoj en la tria programaro mem.\n\n"
                    "Se ĉi tiu Python-medio enhavas gravajn projektojn, datumojn aŭ proprajn agordojn, konsideru fari propran sekurkopion aŭ uzi izolitan Python-medion antaŭ ol daŭrigi. Daŭrigu nur post kiam vi komprenas la celon kaj la riskojn.\n\n"
                    "Laŭ la mezuro permesita de aplikebla juro, la programisto ne respondecas pri perdo de sistemo, medio, datumoj aŭ alia perdo rezultanta el elŝutado, instalado, kongrueco, mediaj ŝanĝoj, triaj komponantoj aŭ ilia uzo. Nenio en ĉi tiu sciigo ekskludas aŭ limigas rajtojn aŭ respondecojn, kiuj laŭleĝe ne povas esti ekskluditaj aŭ limigitaj.\n\n"
                    "Elektante “Instalu por mi” vi konfirmas vian konsenton kun la antaŭaj kvar paĝoj kaj permesas, ke Windows UAC estu petita sekve. Elektante “Mana instalado” vi same konsentas, sed mem rulos la instalan komandon. Elektante “MI NE KONSENTAS” la ludo tuj fermiĝos kaj neniu aŭtomata instalado komenciĝos."
                ),
            ],
            "manual_text": (
                "Vi elektis manan instaladon. La jenaj pakaĵoj ankoraŭ mankas: {packages}.\n\n"
                "Kopiu la suban komandon kaj rulu ĝin en Windows Command Prompt (CMD) aŭ PowerShell. Jen la kutima, konciza pip-instala komando:\n\n"
                "{command}\n\n"
                "Alklaku la komandan kampon kaj premu Ctrl+A, poste Ctrl+C, aŭ elektu “Rapide kopii la komandon”. Se la terminalo raportas nesufiĉajn permesojn, vi povas mem decidi ĉu remalfermi ĝin kiel administranto kaj reprovi.\n\n"
                "Post sukcesa instalado, fermu ĉi tiun paĝon kaj remalfermu index.py. Dum la sekva lanĉo la programo denove kontrolos la mankantajn bibliotekojn; se ili estas instalitaj, la ludo malfermiĝos normale."
            ),
        },
    }

    root = tk.Tk()
    root.title("Language / 语言 / 語言 / Reo / Lingvo")
    root.geometry("920x720")
    root.minsize(780, 620)
    root.configure(bg="#f4f4f4")

    result = {"choice": "reject", "language": "en"}
    selected_language = {"value": None}

    outer = tk.Frame(root, bg="#f4f4f4", padx=28, pady=22)
    outer.pack(fill="both", expand=True)

    heading_var = tk.StringVar()
    subheading_var = tk.StringVar()

    heading_label = tk.Label(
        outer,
        textvariable=heading_var,
        font=("Segoe UI", 18, "bold"),
        bg="#f4f4f4",
        fg="#111111",
        anchor="w",
        justify="left",
    )
    heading_label.pack(fill="x")

    subheading_label = tk.Label(
        outer,
        textvariable=subheading_var,
        font=("Segoe UI", 10),
        bg="#f4f4f4",
        fg="#111111",
        anchor="w",
        justify="left",
        wraplength=830,
    )
    subheading_label.pack(fill="x", pady=(5, 16))

    content_host = tk.Frame(outer, bg="#f4f4f4")
    content_host.pack(fill="both", expand=True)

    content_canvas = tk.Canvas(content_host, bg="#f4f4f4", highlightthickness=0, bd=0)
    content_scrollbar = ttk.Scrollbar(content_host, orient="vertical", command=content_canvas.yview)
    content_canvas.configure(yscrollcommand=content_scrollbar.set)
    content_canvas.pack(side="left", fill="both", expand=True)
    content_scrollbar.pack(side="right", fill="y")

    content = tk.Frame(content_canvas, bg="#f4f4f4")
    content_window = content_canvas.create_window((0, 0), window=content, anchor="nw")

    nav = tk.Frame(outer, bg="#f4f4f4")
    nav.pack(fill="x", pady=(16, 0))

    def clear_frame(frame: tk.Misc) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def refresh_scrollregion(_event=None) -> None:
        content_canvas.configure(scrollregion=content_canvas.bbox("all"))

    def fit_content_width(event) -> None:
        content_canvas.itemconfigure(content_window, width=event.width)

    def wheel(event) -> str:
        if getattr(event, "delta", 0):
            content_canvas.yview_scroll(int(-event.delta / 120), "units")
        elif getattr(event, "num", None) == 4:
            content_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            content_canvas.yview_scroll(1, "units")
        return "break"

    content.bind("<Configure>", refresh_scrollregion)
    content_canvas.bind("<Configure>", fit_content_width)
    root.bind_all("<MouseWheel>", wheel)
    root.bind_all("<Button-4>", wheel)
    root.bind_all("<Button-5>", wheel)

    def close_as(choice: str) -> None:
        result["choice"] = choice
        result["language"] = selected_language["value"] or "en"
        root.destroy()

    def reject() -> None:
        close_as("reject")

    def add_text_panel(text: str, font_name: str) -> None:
        panel = tk.Frame(content, bg="#ffffff", highlightbackground="#bdbdbd", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 10))
        tk.Label(
            panel,
            text=text,
            font=(font_name, 11),
            bg="#ffffff",
            fg="#111111",
            anchor="nw",
            justify="left",
            wraplength=810,
        ).pack(fill="x", padx=18, pady=16)

    def render_language_selection() -> None:
        selected_language["value"] = None
        clear_frame(content)
        clear_frame(nav)
        content_canvas.yview_moveto(0.0)
        root.title("Language / 语言 / 語言 / Reo / Lingvo")
        heading_var.set("请选择语言 / 請選擇語言 / Choose your language / Kōwhiria tō reo / Elektu vian lingvon")
        subheading_var.set("选择后，从第 1 页开始只显示所选语言。 / 選擇後，從第 1 頁開始只顯示所選語言。 / From page 1 onwards, only the selected language will be shown.")

        chooser = tk.Frame(content, bg="#ffffff", highlightbackground="#bdbdbd", highlightthickness=1)
        chooser.pack(fill="x", pady=(0, 10))
        tk.Label(
            chooser,
            text="Language / 语言 / 語言 / Reo / Lingvo",
            font=("Segoe UI", 13, "bold"),
            bg="#ffffff",
            fg="#111111",
        ).pack(pady=(18, 12))

        for code in ("sc", "tc", "en", "mi", "eo"):
            lang = languages[code]
            ttk.Button(
                chooser,
                text=lang["name"],
                command=lambda c=code: render_standard_page(0, c),
                width=34,
            ).pack(pady=6, ipady=5)

        tk.Label(
            chooser,
            text="简体中文  ·  繁體中文  ·  British English  ·  Te Reo Māori  ·  Esperanto",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#111111",
        ).pack(pady=(12, 18))

        ttk.Button(nav, text="Exit / 退出 / Puta / Eliri", command=reject).pack(side="left")

    def render_standard_page(index: int, language: str) -> None:
        selected_language["value"] = language
        lang = languages[language]
        root.title(lang["window_title"])
        clear_frame(content)
        clear_frame(nav)
        content_canvas.yview_moveto(0.0)

        title, subtitle, body = lang["pages"][index]
        heading_var.set(title)
        subheading_var.set(subtitle)
        body = body.format(
            details=_dependency_details(missing, language),
            packages=package_text,
        )
        add_text_panel(body, lang["font"])

        ttk.Button(nav, text=lang["disagree"], command=reject).pack(side="left")
        if index < 3:
            ttk.Button(
                nav,
                text=lang["agree"],
                command=lambda: render_standard_page(index + 1, language),
            ).pack(side="right")
        else:
            ttk.Button(
                nav,
                text=lang["manual"],
                command=lambda: render_manual_page(language),
            ).pack(side="right", padx=(10, 0))
            ttk.Button(
                nav,
                text=lang["auto"],
                command=lambda: close_as("auto"),
            ).pack(side="right")

    copy_status = tk.StringVar(value="")

    def copy_manual_command(language: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(manual_command)
        root.update_idletasks()
        copy_status.set(languages[language]["copied"])

    def render_manual_page(language: str) -> None:
        selected_language["value"] = language
        lang = languages[language]
        root.title(lang["manual_title"])
        clear_frame(content)
        clear_frame(nav)
        content_canvas.yview_moveto(0.0)
        heading_var.set(lang["manual_title"])
        subheading_var.set(lang["manual_sub"])

        body = lang["manual_text"].format(packages=package_text, command=manual_command)
        add_text_panel(body, lang["font"])

        command_frame = tk.Frame(content, bg="#ffffff", highlightbackground="#bdbdbd", highlightthickness=1)
        command_frame.pack(fill="x", pady=(0, 10))
        tk.Label(
            command_frame,
            text=lang["command_label"],
            font=(lang["font"], 10, "bold"),
            bg="#ffffff",
            fg="#111111",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 6))

        command_var = tk.StringVar(value=manual_command)
        command_entry = tk.Entry(
            command_frame,
            textvariable=command_var,
            font=("Consolas", 11),
            relief="solid",
            bd=1,
            readonlybackground="#f8f8f8",
        )
        command_entry.configure(state="readonly")
        command_entry.pack(fill="x", padx=14, pady=(0, 8), ipady=7)

        def select_all_command(_event=None):
            command_entry.selection_range(0, tk.END)
            command_entry.icursor(tk.END)
            command_entry.focus_set()
            return "break"

        def copy_shortcut(_event=None):
            copy_manual_command(language)
            return "break"

        command_entry.bind("<Button-1>", lambda _e: root.after(1, select_all_command))
        command_entry.bind("<Control-a>", select_all_command)
        command_entry.bind("<Control-A>", select_all_command)
        command_entry.bind("<Control-c>", copy_shortcut)
        command_entry.bind("<Control-C>", copy_shortcut)

        copy_status.set("Ctrl+A / Ctrl+C")
        tk.Label(
            command_frame,
            textvariable=copy_status,
            font=(lang["font"], 9),
            bg="#ffffff",
            fg="#111111",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        ttk.Button(
            nav,
            text=lang["manual_exit"],
            command=lambda: close_as("manual"),
        ).pack(side="left")
        ttk.Button(
            nav,
            text=lang["copy"],
            command=lambda: copy_manual_command(language),
        ).pack(side="right")

    render_language_selection()
    root.protocol("WM_DELETE_WINDOW", reject)
    root.mainloop()
    return result["choice"], result["language"]


def _localised_install_message(language: str, kind: str, packages: list[str] | None = None) -> tuple[str, str]:
    package_text = ", ".join(packages or [])
    messages = {
        "sc": {
            "failed": ("安装失败", "无法启动或完成管理员安装程序。游戏将退出。可查看游戏文件夹中的 dependency_install.log。"),
            "incomplete": ("安装未完成", f"安装程序已经结束，但仍无法载入：{package_text}。游戏将退出。"),
        },
        "tc": {
            "failed": ("安裝失敗", "無法啟動或完成管理員安裝程序。遊戲將退出。可查看遊戲資料夾內的 dependency_install.log。"),
            "incomplete": ("安裝未完成", f"安裝程序已經結束，但仍無法載入：{package_text}。遊戲將退出。"),
        },
        "en": {
            "failed": ("Installation failed", "The administrator installation process could not be started or completed. The game will exit. See dependency_install.log in the game folder for details."),
            "incomplete": ("Installation incomplete", f"Installation finished, but the following packages still cannot be loaded: {package_text}. The game will exit."),
        },
        "mi": {
            "failed": ("I rahua te tāutanga", "Kāore i taea te tīmata, te whakaoti rānei i te tukanga tāutanga kaiwhakahaere. Ka kati te kēmu. Tirohia dependency_install.log i te kōpaki kēmu mō ngā taipitopito."),
            "incomplete": ("Kāore i oti te tāutanga", f"Kua mutu te pūtāuta, engari kāore tonu e taea te uta: {package_text}. Ka kati te kēmu."),
        },
        "eo": {
            "failed": ("Instalado malsukcesis", "La administra instala procezo ne povis esti komencita aŭ finita. La ludo fermiĝos. Vidu dependency_install.log en la luddosierujo por detaloj."),
            "incomplete": ("Instalado ne kompletiĝis", f"La instalado finiĝis, sed la jenaj pakaĵoj ankoraŭ ne povas esti ŝargitaj: {package_text}. La ludo fermiĝos."),
        },
    }
    return messages.get(language, messages["en"])[kind]

def _bootstrap_dependencies() -> None:
    # Elevated helper mode: install and exit before loading any game modules.
    if _INSTALL_FLAG in sys.argv:
        missing = _missing_pip_packages()
        if not missing:
            raise SystemExit(0)
        raise SystemExit(_install_packages_as_current_admin(missing))

    _check_tkinter()
    missing = _missing_pip_packages()
    if not missing:
        return

    # Show the four-page information/consent wizard first.  UAC is requested
    # only when the player explicitly chooses the automatic-install route.
    setup_choice, setup_language = _show_dependency_setup_wizard(missing)
    if setup_choice == "reject":
        raise SystemExit(1)
    if setup_choice == "manual":
        # The manual page tells the player to install, then reopen index.py.
        raise SystemExit(0)

    install_result = _run_elevated_installer(missing)
    if install_result is None:
        # Player refused/cancelled Windows UAC: close the game immediately.
        raise SystemExit(1)
    if install_result is False:
        title, message = _localised_install_message(setup_language, "failed")
        _native_message(title, message)
        raise SystemExit(1)

    importlib.invalidate_caches()
    still_missing = _missing_pip_packages()
    if still_missing:
        title, message = _localised_install_message(setup_language, "incomplete", still_missing)
        _native_message(title, message)
        raise SystemExit(1)

    # Installation succeeded. Return silently so the original index.py UI
    # continues loading exactly as it would on a machine with dependencies
    # already installed.
    return


_bootstrap_dependencies()

# Safe to import GUI and third-party modules after dependency bootstrap.
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk
from Casino_Games import casino_games


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "A_Tools/Account/saving_data.json")

WINDOW_BG = "#F7F3EA"
PANEL_BG = "#E6D9F2"
CARD_BG = "#DDF2E5"
CARD_HOVER = "#F6D0D8"
GOLD = "#111111"
TEXT = "#111111"
MUTED = "#111111"
DANGER = "#B84F6A"

LANGUAGE_OPTIONS = {
    "en": "English (default)",
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "mi": "Māori",
    "eo": "Esperanto",
}

# Only widgets owned by this file and the four uploaded hub files are passed
# through this table.  Games imported by those hubs deliberately keep their
# own language and appearance.
_TRANSLATIONS = {
    "en": {
        "游戏中心": "Game Center", "欢迎": "Welcome",
        "请选择下一步以继续使用游戏中心。": "Choose how you would like to continue.",
        "已有账号": "Already registered", "登录账号": "Sign in",
        "第一次使用？": "New here?", "创建新账号": "Create account",
        "体验账号": "Guest account", "账号登录": "Account sign-in",
        "请输入已注册的用户名与密码。": "Enter your registered username and password.",
        "用户名": "Username", "密码": "Password", "还没注册？注册！": "Need an account? Register",
        "← 返回欢迎页": "← Back to welcome", "确认密码": "Confirm password",
        "用户名不可重复，密码需要输入两次确认。": "Choose a unique username and confirm the password.",
        "注册": "Register", "返回": "Back", "我的最爱": "Favorites",
        "尚未收藏游戏。\n可在游戏图片右上角点击 ♡。": "No favorites yet.\nSelect ♡ on a game card to add one.",
        "赌场游戏": "Casino Games", "街机小游戏": "Arcade Games",
        "刮刮乐": "Scratch Cards", "老虎机": "Slot Machines",
        "账号服务": "Account & Settings", "安全登出": "Sign out",
        "← 返回主目录": "← Back to home", "账户管理": "Account management",
        "余额概览": "Balance overview", "充值": "Deposit", "提款": "Withdraw",
        "更改密码": "Change password", "设置": "Settings", "可用余额": "Available balance",
        "余额资料已更新。": "Balance updated.", "当前密码": "Current password",
        "新密码": "New password", "更新密码": "Update password",
        "外观与语言": "Appearance & language",
        "这些选项只影响本次上传的五个界面文件。": "These options affect only the five uploaded interface files.",
        "黑暗模式": "Dark mode", "语言": "Language", "选择语言": "Choose language",
        "赌场游戏中心": "Casino Games", "街机小游戏中心": "Arcade Games",
        "刮刮乐中心": "Scratch Cards", "老虎机中心": "Slot Machines",
        "游戏分类": "Categories", "请选择游戏": "Choose a game",
        "游戏运行中…": "Game running…",
        "扑克": "Poker", "桌面游戏": "Table games", "骰子游戏": "Dice games",
        "轮盘与转盘": "Roulette & wheels", "街机动作": "Arcade action",
        "运气与博弈": "Luck & wagering", "模拟与策略": "Simulation & strategy",
        "经典老虎机": "Classic slots", "特色老虎机": "Featured slots",
        "奖池老虎机": "Jackpot slots",
    },
    "zh_CN": {},
    "zh_TW": {
        "游戏中心": "遊戲中心", "欢迎": "歡迎", "请选择下一步以继续使用游戏中心。": "請選擇下一步以繼續使用遊戲中心。",
        "已有账号": "已有帳號", "登录账号": "登入帳號", "第一次使用？": "第一次使用？",
        "创建新账号": "建立新帳號", "体验账号": "體驗帳號", "账号登录": "帳號登入",
        "请输入已注册的用户名与密码。": "請輸入已註冊的使用者名稱與密碼。", "用户名": "使用者名稱",
        "密码": "密碼", "确认密码": "確認密碼", "注册": "註冊", "返回": "返回",
        "还没注册？注册！": "還沒註冊？立即註冊！", "← 返回欢迎页": "← 返回歡迎頁",
        "我的最爱": "我的最愛", "赌场游戏": "賭場遊戲", "街机小游戏": "街機小遊戲",
        "刮刮乐": "刮刮樂", "老虎机": "老虎機", "账号服务": "帳號與設定",
        "安全登出": "安全登出", "← 返回主目录": "← 返回主目錄", "账户管理": "帳戶管理",
        "余额概览": "餘額概覽", "充值": "儲值", "提款": "提款", "更改密码": "更改密碼",
        "设置": "設定", "可用余额": "可用餘額", "余额资料已更新。": "餘額資料已更新。",
        "尚未收藏游戏。\n可在游戏图片右上角点击 ♡。": "尚未收藏遊戲。\n可在遊戲圖片右上角點擊 ♡。",
        "当前密码": "目前密碼", "新密码": "新密碼", "更新密码": "更新密碼",
        "外观与语言": "外觀與語言", "这些选项只影响本次上传的五个界面文件。": "這些選項只影響本次上傳的五個介面檔案。",
        "黑暗模式": "黑暗模式", "语言": "語言", "选择语言": "選擇語言",
        "赌场游戏中心": "賭場遊戲中心", "街机小游戏中心": "街機小遊戲中心",
        "刮刮乐中心": "刮刮樂中心", "老虎机中心": "老虎機中心", "游戏分类": "遊戲分類",
        "请选择游戏": "請選擇遊戲", "游戏运行中…": "遊戲執行中…",
        "扑克": "撲克", "桌面游戏": "桌面遊戲", "骰子游戏": "骰子遊戲",
        "轮盘与转盘": "輪盤與轉盤", "街机动作": "街機動作", "运气与博弈": "運氣與博弈",
        "模拟与策略": "模擬與策略", "经典老虎机": "經典老虎機", "特色老虎机": "特色老虎機",
        "奖池老虎机": "獎池老虎機",
    },
    "mi": {
        "游戏中心": "Pokapū Kēmu", "欢迎": "Nau mai", "请选择下一步以继续使用游戏中心。": "Kōwhiria te huarahi hei haere tonu.",
        "已有账号": "He pūkete kē tāu", "登录账号": "Takiuru", "第一次使用？": "He kaiwhakamahi hou?",
        "创建新账号": "Waihanga pūkete", "体验账号": "Pūkete manuhiri", "账号登录": "Takiuru pūkete",
        "请输入已注册的用户名与密码。": "Tāurua tō ingoa kaiwhakamahi me tō kupuhipa.", "用户名": "Ingoa kaiwhakamahi",
        "密码": "Kupuhipa", "确认密码": "Whakaū kupuhipa", "注册": "Rēhita", "返回": "Hoki",
        "还没注册？注册！": "Kāore anō kia rēhita? Rēhita", "← 返回欢迎页": "← Hoki ki te nau mai",
        "我的最爱": "Ngā tino pai", "赌场游戏": "Ngā kēmu whare petipeti", "街机小游戏": "Ngā kēmu ā-arcade",
        "刮刮乐": "Kāri waruwaru", "老虎机": "Mīhini moni", "账号服务": "Pūkete me ngā tautuhinga",
        "安全登出": "Takiputa", "← 返回主目录": "← Hoki ki te kāinga", "账户管理": "Whakahaere pūkete",
        "余额概览": "Tirohanga toenga", "充值": "Tāpiri moni", "提款": "Tango moni",
        "更改密码": "Huri kupuhipa", "设置": "Tautuhinga", "可用余额": "Toenga wātea",
        "当前密码": "Kupuhipa o nāianei", "新密码": "Kupuhipa hou",
        "更新密码": "Whakahōu kupuhipa",
        "外观与语言": "Āhua me te reo", "这些选项只影响本次上传的五个界面文件。": "Ka pā ēnei kōwhiringa ki ngā kōnae atanga e rima kua tukuake anake.",
        "余额资料已更新。": "Kua whakahōutia ngā raraunga toenga.",
        "尚未收藏游戏。\n可在游戏图片右上角点击 ♡。": "Kāore anō he kēmu tino pai.\nPāwhiria te ♡ i runga matau o te kāri kēmu.",
        "黑暗模式": "Aratau pōuri", "语言": "Reo", "选择语言": "Kōwhiria te reo",
        "赌场游戏中心": "Kēmu whare petipeti", "街机小游戏中心": "Kēmu ā-arcade",
        "刮刮乐中心": "Kāri waruwaru", "老虎机中心": "Mīhini moni", "游戏分类": "Ngā kāwai",
        "请选择游戏": "Kōwhiria he kēmu", "游戏运行中…": "Kei te haere te kēmu…",
        "扑克": "Poker", "桌面游戏": "Kēmu tēpu", "骰子游戏": "Kēmu mataono",
        "轮盘与转盘": "Roulette me ngā wīra", "街机动作": "Mahi arcade", "运气与博弈": "Waimarie me te petipeti",
        "模拟与策略": "Whakatairite me te rautaki",
    },
    "eo": {
        "游戏中心": "Ludcentro", "欢迎": "Bonvenon", "请选择下一步以继续使用游戏中心。": "Elektu kiel vi volas daŭrigi.",
        "已有账号": "Jam registrita", "登录账号": "Ensaluti", "第一次使用？": "Ĉu nova uzanto?",
        "创建新账号": "Krei konton", "体验账号": "Gasta konto", "账号登录": "Kontensaluto",
        "请输入已注册的用户名与密码。": "Enigu vian registritan uzantnomon kaj pasvorton.", "用户名": "Uzantnomo",
        "密码": "Pasvorto", "确认密码": "Konfirmi pasvorton", "注册": "Registri", "返回": "Reen",
        "还没注册？注册！": "Ĉu sen konto? Registriĝu", "← 返回欢迎页": "← Reen al bonveno",
        "我的最爱": "Ŝatataj", "赌场游戏": "Kazinaj ludoj", "街机小游戏": "Arkadaj ludoj",
        "刮刮乐": "Skrapkartoj", "老虎机": "Monludiloj", "账号服务": "Konto kaj agordoj",
        "安全登出": "Elsaluti", "← 返回主目录": "← Reen al hejmo", "账户管理": "Konta administrado",
        "余额概览": "Saldo", "充值": "Deponi", "提款": "Elpreni", "更改密码": "Ŝanĝi pasvorton",
        "设置": "Agordoj", "可用余额": "Disponebla saldo", "外观与语言": "Aspekto kaj lingvo",
        "当前密码": "Nuna pasvorto", "新密码": "Nova pasvorto",
        "更新密码": "Ĝisdatigi pasvorton",
        "余额资料已更新。": "La saldaj datumoj estas ĝisdatigitaj.",
        "尚未收藏游戏。\n可在游戏图片右上角点击 ♡。": "Ankoraŭ neniu ŝatata ludo.\nAlklaku ♡ supre dekstre de ludkarto.",
        "这些选项只影响本次上传的五个界面文件。": "Ĉi tiuj elektoj influas nur la kvin alŝutitajn interfacajn dosierojn.",
        "黑暗模式": "Malhela reĝimo", "语言": "Lingvo", "选择语言": "Elekti lingvon",
        "赌场游戏中心": "Kazinaj ludoj", "街机小游戏中心": "Arkadaj ludoj",
        "刮刮乐中心": "Skrapkartoj", "老虎机中心": "Monludiloj", "游戏分类": "Kategorioj",
        "请选择游戏": "Elektu ludon", "游戏运行中…": "Ludo funkcias…",
        "扑克": "Pokero", "桌面游戏": "Tabloludoj", "骰子游戏": "Ĵetkubaj ludoj",
        "轮盘与转盘": "Ruleto kaj radoj", "街机动作": "Arkada agado", "运气与博弈": "Ŝanco kaj vetado",
        "模拟与策略": "Simulado kaj strategio",
    },
}

# Display names from the four uploaded hub files.  International casino names
# stay recognisable where a customary Māori/Esperanto title is not established,
# but no simplified-Chinese name is left behind in those language modes.
_GAME_TRANSLATION_ROWS = [
    # Casino categories and games
    ("百家乐", "Baccarat", "百家樂", "Baccarat", "Bakarao"),
    ("黑杰克", "Blackjack", "黑傑克", "Blackjack", "Nigra Joĉjo"),
    ("骰子", "Dice", "骰子", "Mataono", "Ĵetkuboj"),
    ("对决", "Head-to-head", "對決", "Whakataetae", "Duelo"),
    ("轮盘赌", "Roulette", "輪盤賭", "Roulette", "Ruleto"),
    ("地区特色", "Regional Specialties", "地區特色", "Ngā Motuhake ā-Rohe", "Regionaj Specialaĵoj"),
    ("中国", "China", "中國", "Haina", "Ĉinio"),
    ("菲律宾", "Philippines", "菲律賓", "Piripīni", "Filipinoj"),
    ("颜色骰子", "Color Sicbo", "顏色骰子", "Sic Bo Tae", "Kolora Sic Bo"),
    ("乒乓落球", "Ping Pong Drop", "乒乓落球", "Poro Tukituki", "Pingponga Falo"),
    ("三张牌扑克", "Three Card Poker", "三張牌撲克", "Poker Kāri Toru", "Trikarta Pokero"),
    ("三公", "San Gong", "三公", "San Gong", "San Gong"),
    ("视频扑克", "Video Poker", "視訊撲克", "Poker Ataata", "Videopokero"),
    ("加勒比梭哈扑克", "Caribbean Stud Poker", "加勒比梭哈撲克", "Poker Stud Karapīpiana", "Karibia Stud-Pokero"),
    ("月亮梭哈扑克", "Lunar Stud Poker", "月亮梭哈撲克", "Poker Stud Marama", "Luna Stud-Pokero"),
    ("四张牌扑克", "Four Card Poker", "四張牌撲克", "Poker Kāri Whā", "Kvarkarta Pokero"),
    ("赌场扑克", "Casino Hold'em", "賭場撲克", "Hold'em Whare Petipeti", "Kazina Hold'em"),
    ("DJ Wild梭哈扑克", "DJ Wild Stud Poker", "DJ Wild梭哈撲克", "Poker Stud DJ Wild", "DJ Wild Stud-Pokero"),
    ("密西西比梭哈扑克", "Mississippi Stud Poker", "密西西比梭哈撲克", "Poker Stud Misisipi", "Misisipa Stud-Pokero"),
    ("纵横交叉扑克", "Criss Cross Poker", "縱橫交叉撲克", "Poker Whakawhiti", "Kruc-Pokero"),
    ("任逍遥扑克", "Let It Ride Poker", "任逍遙撲克", "Poker Let It Ride", "Let It Ride-Pokero"),
    ("单挑扑克", "Heads Up Hold'em", "單挑撲克", "Hold'em Kanohi-ki-te-kanohi", "Duopa Hold'em"),
    ("迷你终极德州扑克", "Mini Ultimate Texas Hold'em", "迷你終極德州撲克", "Texas Hold'em Whakamutunga Iti", "Mini Ultimate Texas Hold'em"),
    ("终极德州扑克", "Ultimate Texas Hold'em", "終極德州撲克", "Texas Hold'em Whakamutunga", "Ultimate Texas Hold'em"),
    ("终极奥马哈扑克", "Ultimate Omaha", "終極奧馬哈撲克", "Omaha Whakamutunga", "Ultimate Omaha"),
    ("内外注", "In or Out", "內外注", "Ki Roto, Ki Waho rānei", "Ene aŭ Ekstere"),
    ("牌九扑克", "Pai Gow Poker", "牌九撲克", "Poker Pai Gow", "Pai Gow-Pokero"),
    ("王牌五张扑克", "Wild Five Card Poker", "王牌五張撲克", "Poker Kāri Rima Wild", "Sovaĝa Kvinkarta Pokero"),
    ("终极三张牌扑克", "Ultimate Three Card Poker", "終極三張牌撲克", "Poker Kāri Toru Whakamutunga", "Ultimate Trikarta Pokero"),
    ("赌场战争", "Casino War", "賭場戰爭", "Pakanga Whare Petipeti", "Kazina Milito"),
    ("我爱同花", "I Love Suits", "我愛同花", "E Aroha Ana Au ki ngā Momo Kāri", "Mi Amas Samkolorojn"),
    ("特殊百家乐", "Special Baccarat", "特殊百家樂", "Baccarat Motuhake", "Speciala Bakarao"),
    ("龙虎斗", "Dragon Tiger", "龍虎鬥", "Tarakona me te Taika", "Drako kaj Tigro"),
    ("龙虎凤", "Dragon Tiger Phoenix", "龍虎鳳", "Tarakona, Taika me te Manu Ahi", "Drako Tigro Fenikso"),
    ("简单黑杰克", "Easy Blackjack", "簡單黑傑克", "Blackjack Māmā", "Facila Nigra Joĉjo"),
    ("经典黑杰克", "Classic Blackjack", "經典黑傑克", "Blackjack Tauhira", "Klasika Nigra Joĉjo"),
    ("双副牌黑杰克", "Double Deck Blackjack", "雙副牌黑傑克", "Blackjack Pūkei Takirua", "Du-Ferdeka Nigra Joĉjo"),
    ("永6 黑杰克", "Always 6 Blackjack", "永6 黑傑克", "Blackjack Ono Tonu", "Ĉiam-6 Nigra Joĉjo"),
    ("西班牙式黑杰克", "Spanish Blackjack", "西班牙式黑傑克", "Blackjack Pāniora", "Hispana Nigra Joĉjo"),
    ("双向黑杰克", "Breakout Blackjack", "雙向黑傑克", "Blackjack Breakout", "Breakout Nigra Joĉjo"),
    ("免费黑杰克", "Free Blackjack", "免費黑傑克", "Blackjack Koreutu", "Senpaga Nigra Joĉjo"),
    ("免牌加倍黑杰克", "No Card Double Blackjack", "免牌加倍黑傑克", "Blackjack Whakarua Kāri-Kore", "Senkarta Duobla Blackjack"),
    ("倍注黑杰克", "Power Blackjack", "倍注黑傑克", "Blackjack Mana", "Potenca Nigra Joĉjo"),
    ("无限加倍黑杰克", "Unlimited Double Blackjack", "無限加倍黑傑克", "Blackjack Whakarua Mutunga Kore", "Senlima Duobla Nigra Joĉjo"),
    ("豪赢黑杰克", "Multiply Blackjack", "豪贏黑傑克", "Blackjack Whakarea", "Multobliga Nigra Joĉjo"),
    ("闪电黑杰克", "Lightning Blackjack", "閃電黑傑克", "Blackjack Uira", "Fulma Nigra Joĉjo"),
    ("投注叠堆黑杰克", "Bet Stacker Blackjack", "投注疊堆黑傑克", "Blackjack Tāpae Peti", "Vet-Stakiga Nigra Joĉjo"),
    ("骰宝", "Sic Bo", "骰寶", "Sic Bo", "Sic Bo"),
    ("超级骰宝", "Super Sic Bo", "超級骰寶", "Sic Bo Nui", "Supera Sic Bo"),
    ("花旗骰", "Craps", "花旗骰", "Craps", "Krapso"),
    ("骰子百家乐", "Bac Bo", "骰子百家樂", "Bac Bo", "Bac Bo"),
    ("德州扑克双人对决", "Texas Hold'em Duel", "德州撲克雙人對決", "Tauwhāinga Texas Hold'em", "Texas Hold'em-Duelo"),
    ("梭哈扑克双人对决", "Stud Poker Duel", "梭哈撲克雙人對決", "Tauwhāinga Poker Stud", "Stud-Pokera Duelo"),
    ("德州扑克彩票购买", "Texas Hold'em Ticket", "德州撲克彩票購買", "Tīkiti Texas Hold'em", "Texas Hold'em-Bileto"),
    ("美式轮盘", "American Roulette", "美式輪盤", "Roulette Amerikana", "Usona Ruleto"),
    ("欧式轮盘", "European Roulette", "歐式輪盤", "Roulette Ūropi", "Eŭropa Ruleto"),
    ("大六之轮", "Big Six Wheel", "大六之輪", "Wīra Ono Nui", "Granda Ses-Rado"),
    ("温州牌九", "Wenzhou Pai Gow", "溫州牌九", "Pai Gow Wenzhou", "Wenzhou Pai Gow"),
    ("经典牌九", "Classic Pai Gow", "經典牌九", "Pai Gow Tauhira", "Klasika Pai Gow"),
    ("经典翻摊", "Classic Fan Tan", "經典翻攤", "Fan Tan Tauhira", "Klasika Fan Tan"),
    # Scratch cards
    ("验钞机", "Banknote Detector", "驗鈔機", "Kaitiro Moni Pepa", "Monbileta Kontrolilo"),
    ("高尔夫球", "Golf", "高爾夫球", "Korowha", "Golfo"),
    ("过三关", "Three Levels", "過三關", "Ngā Taumata e Toru", "Tri Niveloj"),
    ("叠叠乐", "Stack Up", "疊疊樂", "Tāpae", "Stakado"),
    ("100X 现金大挑战", "100X Cash Challenge", "100X 現金大挑戰", "Wero Moni 100X", "Kontanta Defio 100X"),
    ("1 元 / 特易中奖", "$1 / Very easy to win", "1 元／特易中獎", "$1 / He tino māmā te toa", "$1 / Tre facile gajni"),
    ("每局 1 元", "$1 per game", "每局 1 元", "$1 ia kēmu", "$1 por ludo"),
    ("每局 5 元", "$5 per game", "每局 5 元", "$5 ia kēmu", "$5 por ludo"),
    ("大奖 1,000", "Top prize 1,000", "大獎 1,000", "Tohu nui 1,000", "Ĉefa premio 1,000"),
    ("大奖 10,000", "Top prize 10,000", "大獎 10,000", "Tohu nui 10,000", "Ĉefa premio 10,000"),
    ("大奖 50,000", "Top prize 50,000", "大獎 50,000", "Tohu nui 50,000", "Ĉefa premio 50,000"),
    ("请选择一张刮刮卡", "Choose a scratch card", "請選擇一張刮刮卡", "Kōwhiria he kāri waruwaru", "Elektu skrapkarton"),
    # Slot machines
    ("数字老虎机", "Number Slot Machine", "數字老虎機", "Mīhini Moni Tau", "Nombra Monludilo"),
    ("旋转扑克", "Spin Poker", "旋轉撲克", "Poker Takataka", "Turna Pokero"),
    ("21 BELL老虎机", "21 BELL Slot Machine", "21 BELL老虎機", "Mīhini 21 BELL", "Monludilo 21 BELL"),
    ("21点老虎机", "Blackjack Slot Machine", "21點老虎機", "Mīhini Moni Blackjack", "Nigra-Joĉja Monludilo"),
    ("现金老虎机", "Cash Machine", "現金老虎機", "Mīhini Moni", "Kontanta Monludilo"),
    ("双倍钻石老虎机", "Double Diamond", "雙倍鑽石老虎機", "Taimana Takirua", "Duobla Diamanto"),
    ("最高奖金老虎机", "Top Dollar", "最高獎金老虎機", "Tāra Nui", "Plej Alta Premio"),
    # Small games
    ("小鸡过马路", "Chicken Crossing", "小雞過馬路", "Heihei Whakawhiti Rori", "Kokido Transiras Vojon"),
    ("点球大战", "Penalty Shootout", "點球大戰", "Whana Whiu", "Penalta Konkurso"),
    ("上塔游戏", "Tower Climb", "上塔遊戲", "Piki Pourewa", "Turgrimpado"),
    ("火箭升空", "Rocket Launch", "火箭升空", "Whakarewa Tākirirangi", "Raketlanĉo"),
    ("扫雷", "Minesweeper", "踩地雷", "Kimi Maina", "Minforigilo"),
    ("小钢珠跌落", "Plinko", "小鋼珠跌落", "Plinko", "Plinko"),
    ("幸运数字", "Lucky Number", "幸運數字", "Tau Waimarie", "Bonŝanca Numero"),
    ("猜颜色", "Guess the Colour", "猜顏色", "Matapae Tae", "Divenu la Koloron"),
    ("三杯球", "Three Cups", "三杯球", "Ngā Kapu Toru", "Tri Tasoj"),
    ("猜数字", "Guess the Number", "猜數字", "Matapae Tau", "Divenu la Numeron"),
    ("基诺", "Keno", "基諾", "Keno", "Keno"),
    ("宾果", "Bingo", "賓果", "Bingo", "Bingo"),
    ("打地鼠", "Whack-a-Mole", "打地鼠", "Patua te Kiore Matapo", "Frapu la Talpon"),
    ("剪刀石头布", "Rock Paper Scissors", "剪刀石頭布", "Kutikuti Pepa Kōhatu", "Tondilo Papero Ŝtono"),
    ("红包雨", "Red Packet Rain", "紅包雨", "Ua Kōpaki Whero", "Ruĝ-Paketa Pluvo"),
    ("足球弹珠", "Football Pinball", "足球彈珠", "Pinipōro Whutupōro", "Futbala Pinbalo"),
    ("股市大风云", "Stock Market", "股市大風雲", "Mākete Hea", "Borso"),
    ("扑克足球", "Poker Football", "撲克足球", "Whutupōro Poker", "Pokera Futbalo"),
    ("成交与否", "Deal or No Deal", "成交與否", "Whakaae, Kāo rānei", "Interkonsento aŭ Ne"),
]

for _source, _en, _zh_tw, _mi, _eo in _GAME_TRANSLATION_ROWS:
    _TRANSLATIONS["en"][_source] = _en
    _TRANSLATIONS["zh_TW"][_source] = _zh_tw
    _TRANSLATIONS["mi"][_source] = _mi
    _TRANSLATIONS["eo"][_source] = _eo

_EXTRA_TRANSLATION_ROWS = [
    ("游戏、账户与余额，\n集中在一个清晰的入口。", "Games, accounts and balances,\nall in one clear place.", "遊戲、帳號與餘額，\n集中在一個清晰的入口。", "Ngā kēmu, ngā pūkete me ngā toenga,\nkei te wāhi kotahi.", "Ludoj, kontoj kaj saldoj,\nĉio en unu klara loko."),
    ("桌面游戏与扑克专区", "Table games and poker", "桌面遊戲與撲克專區", "Ngā kēmu tēpu me te poker", "Tabloludoj kaj pokero"),
    ("轻量、快速的休闲游戏", "Quick casual games", "輕量、快速的休閒遊戲", "Ngā kēmu tere, māmā", "Rapidaj neformalaj ludoj"),
    ("选择票券并即时开奖", "Choose a ticket for an instant result", "選擇票券並即時開獎", "Kōwhiria he tīkiti mō te hua inamata", "Elektu bileton por tuja rezulto"),
    ("浏览并进入老虎机游戏", "Browse and open slot games", "瀏覽並進入老虎機遊戲", "Tirotiro ka whakatuwhera kēmu mīhini", "Foliumu kaj malfermu monludilojn"),
    ("余额、充值、提款与密码", "Balance, deposits, withdrawals and password", "餘額、儲值、提款與密碼", "Toenga, moni tāpiri, tango moni me te kupuhipa", "Saldo, deponoj, elprenoj kaj pasvorto"),
    ("保存资料并返回登录页", "Save and return to sign-in", "儲存資料並返回登入頁", "Tiakina ka hoki ki te takiuru", "Konservu kaj revenu al ensaluto"),
    ("创建账号", "Create account", "建立帳號", "Waihanga pūkete", "Krei konton"),
    ("用户名不可重复，密码需要输入两次确认。", "Choose a unique username and enter the password twice.", "使用者名稱不可重複，密碼需要輸入兩次確認。", "Me ahurei te ingoa kaiwhakamahi, ā, tāurua te kupuhipa.", "Elektu unikan uzantnomon kaj enigu la pasvorton dufoje."),
    ("请输入用户名和密码。", "Enter a username and password.", "請輸入使用者名稱和密碼。", "Tāurua te ingoa kaiwhakamahi me te kupuhipa.", "Enigu uzantnomon kaj pasvorton."),
    ("用户名至少需要 3 个字符。", "Username must contain at least 3 characters.", "使用者名稱至少需要 3 個字元。", "Kia 3 neke atu ngā pūāhua o te ingoa kaiwhakamahi.", "La uzantnomo bezonas almenaŭ 3 signojn."),
    ("用户名已存在，请选择其他用户名。", "That username already exists; choose another.", "使用者名稱已存在，請選擇其他名稱。", "Kei te whakamahia taua ingoa; kōwhiria tētahi atu.", "Tiu uzantnomo jam ekzistas; elektu alian."),
    ("密码不能为空。", "Password cannot be empty.", "密碼不能為空。", "Kaua te kupuhipa e noho putua.", "La pasvorto ne povas esti malplena."),
    ("两次输入的密码不一致。", "The passwords do not match.", "兩次輸入的密碼不一致。", "Kāore ngā kupuhipa e ōrite ana.", "La pasvortoj ne kongruas."),
    ("你的账户资料已从本地记录重新载入。", "Your account was reloaded from the local record.", "你的帳戶資料已從本機記錄重新載入。", "Kua uta anō tō pūkete mai i te pūkete paetata.", "Via konto estis reŝargita el la loka registro."),
    ("密码在当前页面完成验证与更新，不会打开弹窗。", "Verify and update the password on this page.", "密碼會在目前頁面完成驗證與更新。", "Manatokohia ka whakahou i te kupuhipa ki tēnei whārangi.", "Kontrolu kaj ĝisdatigu la pasvorton en ĉi tiu paĝo."),
    ("当前密码不正确。", "Current password is incorrect.", "目前密碼不正確。", "Kei te hē te kupuhipa o nāianei.", "La nuna pasvorto estas malĝusta."),
    ("新密码不能为空。", "New password cannot be empty.", "新密碼不能為空。", "Kaua te kupuhipa hou e noho putua.", "La nova pasvorto ne povas esti malplena."),
    ("两次输入的新密码不一致。", "The new passwords do not match.", "兩次輸入的新密碼不一致。", "Kāore ngā kupuhipa hou e ōrite ana.", "La novaj pasvortoj ne kongruas."),
    ("密码已成功更新。", "Password updated.", "密碼已成功更新。", "Kua whakahōutia te kupuhipa.", "Pasvorto ĝisdatigita."),
    ("管理员", "Administrator", "管理員", "Kaiwhakahaere", "Administranto"),
    ("管理密码", "Administrator password", "管理員密碼", "Kupuhipa kaiwhakahaere", "Administra pasvorto"),
    ("充值金额", "Deposit amount", "儲值金額", "Moni tāpiri", "Depona sumo"),
    ("提款金额", "Withdrawal amount", "提款金額", "Moni tango", "Elprena sumo"),
    ("确认充值", "Confirm deposit", "確認儲值", "Whakaū moni tāpiri", "Konfirmi deponon"),
    ("确认提款", "Confirm withdrawal", "確認提款", "Whakaū moni tango", "Konfirmi elprenon"),
    ("管理员账号或密码不正确。", "Administrator username or password is incorrect.", "管理員帳號或密碼不正確。", "Kei te hē te pūkete kaiwhakahaere, te kupuhipa rānei.", "La administra konto aŭ pasvorto estas malĝusta."),
    ("请输入有效金额。", "Enter a valid amount.", "請輸入有效金額。", "Tāurua he moni whaimana.", "Enigu validan sumon."),
    ("金额必须大于 0。", "The amount must be greater than 0.", "金額必須大於 0。", "Me nui ake te moni i te 0.", "La sumo devas esti pli granda ol 0."),
    ("提款金额不能超过当前余额。", "The withdrawal cannot exceed the current balance.", "提款金額不能超過目前餘額。", "Kāore te moni tango e āhei ki te nui ake i te toenga.", "La elpreno ne povas superi la nunan saldon."),
    ("体验账号不会储存收藏。", "Guest accounts do not save favorites.", "體驗帳號不會儲存我的最愛。", "Kāore ngā pūkete manuhiri e tiaki tino pai.", "Gastaj kontoj ne konservas ŝatatajn ludojn."),
    ("我的最爱最多只能储存 8 个游戏。", "Favorites can contain up to 8 games.", "我的最愛最多只能儲存 8 個遊戲。", "E waru rawa ngā kēmu tino pai ka taea te tiaki.", "Ŝatataj povas enhavi maksimume 8 ludojn."),
    ("找不到玩家资料，无法储存收藏。", "Player data was not found; the favorite could not be saved.", "找不到玩家資料，無法儲存我的最愛。", "Kāore i kitea ngā raraunga kaitākaro; kāore i tiakina te tino pai.", "Ludantaj datumoj ne estis trovitaj; la ŝatata ludo ne konserviĝis."),
    ("应用", "Apply", "套用", "Hoatu", "Apliki"),
    ("确定", "OK", "確定", "Whakaū", "Bone"),
    ("请选择老虎机", "Choose a slot machine", "請選擇老虎機", "Kōwhiria he mīhini moni", "Elektu monludilon"),
    ("维护", "Maintenance", "維護", "Tiaki", "Prizorgado"),
    ("提示", "Notice", "提示", "Pānui", "Avizo"),
    ("确认", "Confirm", "確認", "Whakaū", "Konfirmi"),
]

for _source, _en, _zh_tw, _mi, _eo in _EXTRA_TRANSLATION_ROWS:
    _TRANSLATIONS["en"][_source] = _en
    _TRANSLATIONS["zh_TW"][_source] = _zh_tw
    _TRANSLATIONS["mi"][_source] = _mi
    _TRANSLATIONS["eo"][_source] = _eo

_DYNAMIC_PHRASES = {
    "en": {
        "已启动：": "Started: ", "已结束，余额已更新": " finished; balance updated",
        "已关闭": " closed", "已加入我的最爱：": "Added to favorites: ",
        "已从我的最爱移除：": "Removed from favorites: ", "余额": "Balance",
        "维护通知": "Maintenance", "目前正在维护。": " is under maintenance.",
        "启动失败": "Launch failed", "无法打开": "Could not open ",
        "游戏运行出错": "Game error", "请选择游戏": "Choose a game",
        "没有设置对应的程序模块。": " has no program module configured.",
        "请先关闭当前运行中的游戏。": "Close the running game first.",
        "未正常结束：": " did not finish normally: ",
        "账号 ": "Account ", " 已被锁定，请联系管理员。": " is locked; contact an administrator.",
        "登录失败三次，该账号已被锁定。": "Three failed sign-ins; this account is now locked.",
        "用户名或密码错误，还可尝试 ": "Incorrect username or password; attempts remaining: ",
        " 次。": ".", " 已建立，请登录。": " created; please sign in.",
    },
    "zh_TW": {
        "已启动：": "已啟動：", "已结束，余额已更新": "已結束，餘額已更新",
        "已关闭": "已關閉", "已加入我的最爱：": "已加入我的最愛：",
        "已从我的最爱移除：": "已從我的最愛移除：", "余额": "餘額",
        "维护通知": "維護通知", "目前正在维护。": "目前正在維護。",
        "启动失败": "啟動失敗", "无法打开": "無法開啟", "游戏运行出错": "遊戲執行出錯",
        "没有设置对应的程序模块。": "沒有設定對應的程式模組。",
        "请先关闭当前运行中的游戏。": "請先關閉目前執行中的遊戲。",
        "未正常结束：": "未正常結束：",
        "账号 ": "帳號 ", " 已被锁定，请联系管理员。": " 已被鎖定，請聯絡管理員。",
        "登录失败三次，该账号已被锁定。": "登入失敗三次，該帳號已被鎖定。",
        "用户名或密码错误，还可尝试 ": "使用者名稱或密碼錯誤，還可嘗試 ",
        " 次。": " 次。", " 已建立，请登录。": " 已建立，請登入。",
    },
    "mi": {
        "已启动：": "Kua tīmata: ", "已结束，余额已更新": " kua mutu; kua whakahōutia te toenga",
        "已关闭": " kua katia", "已加入我的最爱：": "Kua tāpiritia ki ngā tino pai: ",
        "已从我的最爱移除：": "Kua tangohia i ngā tino pai: ", "余额": "Toenga",
        "维护通知": "Pānui tiaki", "目前正在维护。": " kei te tiakina ināianei.",
        "启动失败": "I rahua te tīmata", "无法打开": "Kāore i taea te whakatuwhera ",
        "游戏运行出错": "Hapa kēmu",
        "没有设置对应的程序模块。": " kāore he kōwae papatono kua whakaritea.",
        "请先关闭当前运行中的游戏。": "Katia te kēmu e haere ana i te tuatahi.",
        "未正常结束：": " kāore i mutu tika: ",
        "账号 ": "Pūkete ", " 已被锁定，请联系管理员。": " kua maukati; whakapā atu ki te kaiwhakahaere.",
        "登录失败三次，该账号已被锁定。": "E toru ngā takiuru rahua; kua maukati te pūkete.",
        "用户名或密码错误，还可尝试 ": "He ingoa, he kupuhipa rānei kei te hē; ngā whakamātau e toe ana: ",
        " 次。": ".", " 已建立，请登录。": " kua hangaia; takiuru mai.",
    },
    "eo": {
        "已启动：": "Lanĉita: ", "已结束，余额已更新": " finiĝis; saldo ĝisdatigita",
        "已关闭": " fermiĝis", "已加入我的最爱：": "Aldonita al ŝatataj: ",
        "已从我的最爱移除：": "Forigita el ŝatataj: ", "余额": "Saldo",
        "维护通知": "Prizorga avizo", "目前正在维护。": " estas nun prizorgata.",
        "启动失败": "Lanĉo malsukcesis", "无法打开": "Ne eblis malfermi ",
        "游戏运行出错": "Luderaro",
        "没有设置对应的程序模块。": " ne havas agorditan programmodulon.",
        "请先关闭当前运行中的游戏。": "Unue fermu la rulantan ludon.",
        "未正常结束：": " ne finiĝis normale: ",
        "账号 ": "Konto ", " 已被锁定，请联系管理员。": " estas ŝlosita; kontaktu administranton.",
        "登录失败三次，该账号已被锁定。": "Tri malsukcesaj ensalutoj; la konto nun estas ŝlosita.",
        "用户名或密码错误，还可尝试 ": "Malĝusta uzantnomo aŭ pasvorto; restantaj provoj: ",
        " 次。": ".", " 已建立，请登录。": " kreita; bonvolu ensaluti.",
    },
}

_DARK_COLOURS = {
    "#F7F3EA": "#15171C", "#FFFFFF": "#20232A", "#FFF9FC": "#292C34",
    "#E6D9F2": "#29243A", "#DDF2E5": "#20352C", "#DFF2E5": "#20352C",
    "#DCEAF7": "#1E3040", "#F6D0D8": "#432630", "#F7BEC9": "#4A2832",
    "#CDEEDD": "#204035", "#E6DFF0": "#302B3A", "#D8D3CE": "#333238",
    "#E7D7B8": "#3A3122", "#FFF8ED": "#343029", "#111111": "#F2F3F5",
    "#777777": "#AEB3BD", "#B84F6A": "#FF8EA6", "#684C9C": "#C4A7FF",
    "#E7E1EC": "#302E36", "#B69ADD": "#766096", "#CEC5D5": "#5A5662",
}


def normalise_language(value) -> str:
    aliases = {"sc": "zh_CN", "tc": "zh_TW", "zh-cn": "zh_CN", "zh-tw": "zh_TW"}
    code = aliases.get(str(value), str(value))
    return code if code in LANGUAGE_OPTIONS else "en"


def preference_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def call_with_supported_kwargs(function: Callable, **kwargs):
    """Call old and new hub entry points without coupling their versions."""
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return function(**kwargs)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD
           for parameter in parameters):
        return function(**kwargs)
    supported = {parameter.name for parameter in parameters}
    return function(**{
        name: value for name, value in kwargs.items() if name in supported
    })


def translate_text(text: str, language: str) -> str:
    language = normalise_language(language)
    if language == "zh_CN":
        return text
    translated = _TRANSLATIONS.get(language, {}).get(text)
    if translated is not None:
        return translated
    if text.startswith("余额  $"):
        labels = {"en": "Balance", "zh_TW": "餘額", "mi": "Toenga", "eo": "Saldo"}
        return f"{labels.get(language, '余额')}  ${text.split('$', 1)[1]}"
    greeting_sets = {
        "en": ("Good morning", "Good morning", "Good afternoon", "Good evening"),
        "zh_TW": ("凌晨好", "早安", "午安", "晚安"),
        "mi": ("Ata mārie", "Ata mārie", "Kia ora i te ahiahi", "Pō mārie"),
        "eo": ("Bonan matenon", "Bonan matenon", "Bonan posttagmezon", "Bonan vesperon"),
    }
    for index, prefix in enumerate(("凌晨好，", "早上好，", "中午好，", "晚上好，")):
        if text.startswith(prefix) and text.endswith("！"):
            name = text[len(prefix):-1]
            if language == "zh_TW":
                return f"{greeting_sets[language][index]}，{name}！"
            return f"{greeting_sets[language][index]}, {name}!"

    if text.startswith("当前余额 $") and text.endswith(" · 此操作需要管理员验证。"):
        amount = text[len("当前余额 "):].split(" · ", 1)[0]
        templates = {
            "en": "Current balance {amount} · Administrator verification is required.",
            "zh_TW": "目前餘額 {amount} · 此操作需要管理員驗證。",
            "mi": "Toenga o nāianei {amount} · Me whakamana e te kaiwhakahaere.",
            "eo": "Nuna saldo {amount} · Administra kontrolo estas bezonata.",
        }
        return templates[language].format(amount=amount)

    if "成功：$" in text and "；当前余额 $" in text and text.endswith("。"):
        operation, remainder = text.split("成功：", 1)
        amount, balance = remainder[:-1].split("；当前余额 ", 1)
        operation = translate_text(operation, language)
        templates = {
            "en": "{operation} successful: {amount}; current balance {balance}.",
            "zh_TW": "{operation}成功：{amount}；目前餘額 {balance}。",
            "mi": "Kua oti te {operation}: {amount}; toenga o nāianei {balance}.",
            "eo": "{operation} sukcesis: {amount}; nuna saldo {balance}.",
        }
        return templates[language].format(
            operation=operation, amount=amount, balance=balance
        )

    result = text
    # Longest names first prevents a short title such as “百家乐” from
    # consuming part of “特殊百家乐”.
    game_names = sorted(
        ((source, _TRANSLATIONS[language][source])
         for source, *_rest in _GAME_TRANSLATION_ROWS),
        key=lambda item: len(item[0]), reverse=True,
    )
    for source, target in game_names:
        result = result.replace(source, target)
    for source, target in sorted(
        _DYNAMIC_PHRASES.get(language, {}).items(),
        key=lambda item: len(item[0]), reverse=True,
    ):
        result = result.replace(source, target)
    return result


def add_paper_art_ribbon(parent: tk.Misc, background: str) -> tk.Canvas:
    """绘制可缩放的层叠纸艺装饰；纯 Canvas，不增加资源依赖。"""
    ribbon = tk.Canvas(
        parent, height=38, bg=background, highlightthickness=0, bd=0
    )
    ribbon.pack(fill="x")

    def redraw(event) -> None:
        width = max(event.width, 1)
        ribbon.delete("paper-art")
        ribbon.create_polygon(
            0, 0, width, 0, width, 16,
            width * .78, 12, width * .58, 21, width * .34, 14, 0, 23,
            fill="#CDB7EB", outline="", tags="paper-art",
        )
        ribbon.create_polygon(
            0, 15, width * .25, 9, width * .49, 25, width * .73, 13,
            width, 22, width, 38, 0, 38,
            fill="#CDEEDD", outline="", tags="paper-art",
        )
        ribbon.create_polygon(
            0, 29, width * .20, 19, width * .42, 31, width * .66, 21,
            width * .84, 30, width, 24, width, 38, 0, 38,
            fill="#F7BEC9", outline="", tags="paper-art",
        )
        ribbon.create_line(
            0, 28, width, 23, fill="#FFFFFF", width=1, dash=(3, 5),
            tags="paper-art",
        )
        ribbon.create_line(
            0, 36, width, 31, fill="#9DB7D0", width=2,
            tags="paper-art",
        )
        suits = (("♠", "#684C9C"), ("♥", "#C76078"),
                 ("♣", "#4E8A72"), ("♦", "#C76078"))
        for index, (suit, colour) in enumerate(suits):
            ribbon.create_text(
                width * (.16 + index * .22), 21 + (index % 2) * 5,
                text=suit, fill=colour, font=("Segoe UI Symbol", 15, "bold"),
                tags="paper-art",
            )
    ribbon.bind("<Configure>", redraw)
    return ribbon

# 与原 charge.py 一致。正式使用时建议改为哈希密码或独立管理员资料。
ADMINS = {
    "admin": "admin123",
}


def load_user_data() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def safe_balance(value) -> float:
    try:
        if value in (None, "None", ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def greeting_for(username: str) -> str:
    hour = datetime.now().hour
    if hour < 6:
        period = "凌晨好"
    elif hour < 12:
        period = "早上好"
    elif hour < 18:
        period = "中午好"
    else:
        period = "晚上好"
    return f"{period}，{username}！"


def user_favorites(user: Optional[dict]) -> list[dict]:
    """Return up to eight unique favorites, persisted by module path only."""
    if not isinstance(user, dict):
        return []
    result = []
    seen = set()
    for item in user.get("favorites", []):
        if not isinstance(item, dict):
            continue
        module_name = str(item.get("module", "")).strip()
        if not module_name or module_name in seen:
            continue
        seen.add(module_name)
        result.append({"module": module_name})
        if len(result) == 8:
            break
    return result


def resolve_favorite(favorite: dict) -> dict:
    """Resolve transient hub/name data from the saved module path."""
    module_name = str(favorite.get("module", "")).strip()
    prefix_to_hub = {
        "Casino_Games.": ("casino", "Casino_Games.casino_games"),
        "Lotto.": ("lotto", "Lotto.lotto"),
        "Slot_Machine.": ("slot", "Slot_Machine.slot_machine"),
        "Small_Games.": ("small", "Small_Games.small_games"),
    }
    hub, hub_module_name = next(
        (value for prefix, value in prefix_to_hub.items()
         if module_name.startswith(prefix)),
        ("", ""),
    )
    display_name = module_name.rsplit(".", 1)[-1].replace("_", " ")
    if hub_module_name:
        try:
            hub_module = importlib.import_module(hub_module_name)
            if hub == "lotto":
                for game in getattr(hub_module, "LOTTO_GAMES", []):
                    if game.get("module") == module_name:
                        display_name = str(game.get("name", display_name))
                        break
            else:
                for games in getattr(hub_module, "GAME_SECTIONS", {}).values():
                    match = next(
                        (name for name, module, _maintenance in games
                         if module == module_name),
                        None,
                    )
                    if match is not None:
                        display_name = str(match)
                        break
        except (ImportError, AttributeError, TypeError, ValueError):
            pass
    return {"module": module_name, "hub": hub, "name": display_name}


class EntryRow(tk.Frame):
    def __init__(self, master, label: str, show: str = ""):
        super().__init__(master, bg=master.cget("bg"))
        self.grid_columnconfigure(0, minsize=210)
        self.grid_columnconfigure(1, weight=1)
        self.label = tk.Label(
            self,
            text=label,
            anchor="e",
            justify="right",
            wraplength=200,
            font=("Microsoft YaHei UI", 11),
            bg=self.cget("bg"),
            fg=TEXT,
        )
        self.label.grid(row=0, column=0, sticky="e", padx=(0, 12))

        self.entry = tk.Entry(
            self,
            show=show,
            font=("Microsoft YaHei UI", 12),
            bg="#FFF9FC",
            fg="#111111",
            insertbackground="#111111",
            relief="flat",
            bd=0,
            highlightbackground="#111111",
            highlightcolor="#111111",
            highlightthickness=1,
        )
        self.entry.grid(row=0, column=1, sticky="ew", ipady=9)



class HomeDashboard(tk.Frame):
    """全新的主页仪表板；不使用旧 MainMenuPage 的分类与滚动逻辑。"""

    def __init__(self, master, username: str, balance: float, actions,
                 favorites, on_favorite, on_remove_favorite):
        tr = master.translate_ui
        colour = master.theme_colour
        page_bg = colour("#F7F3EA")
        panel_bg = colour("#E6D9F2")
        side_bg = colour("#DCEAF7")
        surface = colour("#FFFFFF")
        text_colour = colour("#111111")
        hover_surface = colour("#FFF8ED")
        border = colour("#D6CEDD")
        super().__init__(master, bg=page_bg)
        self._index_owned = True
        self._preferences_ready = True
        self.actions = actions

        self.card_images = []
        header = tk.Frame(self, bg=panel_bg, height=82)
        header.pack(fill="x")
        header.pack_propagate(False)
        title_box = tk.Frame(header, bg=panel_bg)
        title_box.pack(side="left", padx=22, pady=12)
        dashboard_title = tr("游戏中心")
        dashboard_title_size = 20 if len(dashboard_title) > 12 else 23
        tk.Label(title_box, text=dashboard_title,
                 font=("Microsoft YaHei UI", dashboard_title_size, "bold"),
                 wraplength=240, justify="left",
                 bg=panel_bg, fg=text_colour).pack(anchor="w")
        tk.Label(header, text=tr(greeting_for(username)),
                 font=("Microsoft YaHei UI", 11, "bold"),
                 wraplength=240, justify="center",
                 bg=panel_bg, fg=text_colour).place(
                     relx=0.58, rely=0.5, anchor="center"
                 )

        balance_box = tk.Frame(header, bg=surface, padx=18, pady=9,
                               highlightbackground="#BDA8D2", highlightthickness=1)
        balance_box.pack(side="right", padx=25, pady=14)
        tk.Label(balance_box, text=tr(f"余额  ${balance:,.2f}"),
                 font=("Microsoft YaHei UI", 14, "bold"), bg=surface,
                 fg=text_colour).pack()

        add_paper_art_ribbon(self, page_bg)
        body = tk.Frame(self, bg=page_bg)
        body.pack(fill="both", expand=True, padx=30, pady=24)

        intro = tk.Frame(body, bg=side_bg, width=300,
                         highlightbackground="#AFC4D8", highlightthickness=1)
        intro.pack(side="left", fill="y", padx=(0, 7))
        intro.pack_propagate(False)
        tk.Label(intro, text="♠  ♥  ♣  ♦", font=("Segoe UI Symbol", 24, "bold"),
                 bg=side_bg, fg=colour("#684C9C")).pack(anchor="w", padx=24, pady=(32, 7))
        tk.Label(intro, text=tr("我的最爱"), font=("Microsoft YaHei UI", 21, "bold"),
                 bg=side_bg, fg=text_colour).pack(anchor="w", padx=24)
        favorite_list = tk.Frame(intro, bg=side_bg)
        favorite_list.pack(fill="x", padx=16, pady=(7, 0))
        if favorites:
            for favorite in favorites[:8]:
                row = tk.Frame(favorite_list, bg=surface, cursor="hand2",
                               highlightbackground="#AFC4D8", highlightthickness=1)
                row.pack(fill="x", pady=3)
                heart = tk.Button(
                    row, text="♥", font=("Segoe UI Symbol", 13, "bold"),
                    bg=surface, fg="#D43D55", activebackground=surface,
                    activeforeground="#D43D55", relief="flat", bd=0,
                    cursor="hand2", padx=0, pady=0,
                )
                heart.pack(side="left", padx=(10, 7), pady=7)
                name = tk.Label(row, text=tr(favorite["name"]), anchor="w",
                                justify="left", wraplength=210,
                                font=("Microsoft YaHei UI", 9, "bold"),
                                bg=surface, fg=text_colour, cursor="hand2")
                name.pack(side="left", fill="x", expand=True, pady=7)
                for widget in (row, name):
                    widget.bind("<Button-1>",
                                lambda _event, item=favorite: on_favorite(item))

                pending = {"job": None}

                def finish_remove(item=favorite, current_row=row,
                                  state=pending):
                    state["job"] = None
                    if on_remove_favorite(item):
                        try:
                            if current_row.winfo_exists():
                                current_row.destroy()
                        except tk.TclError:
                            pass

                def toggle_remove(current_heart=heart, state=pending,
                                  finish=finish_remove):
                    if state["job"] is not None:
                        self.after_cancel(state["job"])
                        state["job"] = None
                        current_heart.configure(text="♥")
                        return
                    current_heart.configure(text="♡")
                    state["job"] = self.after(5000, finish)

                heart.configure(command=toggle_remove)
        else:
            tk.Label(favorite_list, text=tr("尚未收藏游戏。\n可在游戏图片右上角点击 ♡。"),
                     font=("Microsoft YaHei UI", 10), bg=side_bg, fg=text_colour,
                     justify="left").pack(anchor="w", padx=8, pady=8)
        tk.Frame(intro, bg=colour("#F7BEC9"), height=8).pack(side="bottom", fill="x")

        grid = tk.Frame(body, bg=page_bg)
        grid.pack(side="left", fill="both", expand=True)
        for column in range(2):
            grid.grid_columnconfigure(column, weight=1, uniform="dashboard")
        for row in range(3):
            grid.grid_rowconfigure(row, weight=1, uniform="dashboard")

        for index, action in enumerate(actions):
            title, _subtitle, colour, image_filename, command = action
            row, column = divmod(index, 2)
            card = tk.Frame(grid, bg=surface, cursor="hand2",
                            highlightbackground=border, highlightthickness=1)
            card.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            band = tk.Frame(card, bg=master.theme_colour(colour), height=7)
            band.pack(side="top", fill="x")
            content = tk.Frame(card, bg=surface)
            content.pack(fill="both", expand=True)
            image_path = os.path.join(BASE_DIR, "Picture", image_filename)
            if os.path.isfile(image_path):
                try:
                    picture = Image.open(image_path).convert("RGBA")
                    picture = ImageOps.fit(
                        picture,
                        (300, 105),
                        method=Image.Resampling.LANCZOS,
                        centering=(0.5, 0.5),
                    )
                    photo = ImageTk.PhotoImage(picture)
                    self.card_images.append(photo)
                    image_label = tk.Label(content, image=photo, bg=surface,
                                           bd=0, cursor="hand2")
                    image_label.pack(side="top", pady=(8, 3))
                except (OSError, ValueError, tk.TclError):
                    image_label = None
            else:
                image_label = None
            title_label = tk.Label(
                content, text=tr(title), font=("Microsoft YaHei UI", 13, "bold"),
                bg=surface, fg=text_colour, cursor="hand2",
                wraplength=280, justify="center",
            )
            title_label.pack(side="bottom", pady=(2, 9))

            def activate(_event=None, callback=command):
                callback()

            def recolour(widget, colour_value, accent):
                try:
                    widget.configure(bg=colour_value)
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    if child is not accent:
                        recolour(child, colour_value, accent)

            def enter(_event=None, current=card, accent=band):
                recolour(current, hover_surface, accent)
                current.configure(highlightbackground="#8EAFCB")

            def leave(_event=None, current=card, accent=band):
                recolour(current, surface, accent)
                current.configure(highlightbackground=border)

            event_widgets = [card, content, title_label]
            if image_label is not None:
                event_widgets.append(image_label)
            for widget in event_widgets:
                widget.bind("<Button-1>", activate)
                widget.bind("<Enter>", enter)
                widget.bind("<Leave>", leave)


class GameCenterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"游戏中心")
        self.geometry("1150x750+50+10")
        self.resizable(False, False)
        self.configure(bg=WINDOW_BG)
        self.protocol("WM_DELETE_WINDOW", self.close_application)

        self.users = []
        self.current_user: Optional[dict] = None
        self.username = ""
        self.balance = 0.0
        self.is_guest = False
        self.failed_attempts = {}
        self.language = "en"
        self.dark_mode = False
        self.current_page: Optional[tk.Widget] = None
        self.casino_page = None
        self.game_hub_page = None
        self.bind_class("UploadedDarkGuard", "<Enter>",
                        self._guard_uploaded_hover, add="+")
        self.bind_class("UploadedDarkGuard", "<Leave>",
                        self._guard_uploaded_hover, add="+")
        self.show_welcome_page()

    def _guard_uploaded_hover(self, _event=None):
        # In dark mode the original pages' hover callbacks briefly restore
        # light pastel colours.  This bind tag runs before the widget binding,
        # so those light callbacks never execute and cannot flash.
        if self._effective_dark_mode():
            return "break"
        return None

    def translate_ui(self, text: str) -> str:
        return translate_text(str(text), self._effective_language())

    def _effective_language(self) -> str:
        return self.language

    def _effective_dark_mode(self) -> bool:
        return self.dark_mode

    def theme_colour(self, colour: str) -> str:
        if not self._effective_dark_mode():
            return colour
        return _DARK_COLOURS.get(str(colour).upper(), colour)

    def apply_uploaded_preferences(self, root: Optional[tk.Widget] = None) -> None:
        page = root if root is not None else self.current_page
        if page is None or not page.winfo_exists():
            return
        if root is None and not (
            getattr(page, "_index_owned", False) or
            getattr(page, "_uploaded_scope", False)
        ):
            return

        language = self._effective_language()
        uploaded_scope = bool(getattr(page, "_uploaded_scope", False))

        def visit(widget: tk.Widget) -> None:
            try:
                options = set(widget.keys())
                # The hover guard is needed only by uploaded hub pages. Adding
                # a bind tag to every account widget caused many Tcl round trips
                # and made Account & Settings disproportionately slow on Windows.
                if uploaded_scope:
                    bindtags = widget.bindtags()
                    if "UploadedDarkGuard" not in bindtags:
                        widget.bindtags(("UploadedDarkGuard",) + bindtags)
                if "text" in options:
                    current = str(widget.cget("text"))
                    translated = translate_text(current, language)
                    if translated != current:
                        widget.configure(text=translated)
                if "textvariable" in options:
                    variable_name = str(widget.cget("textvariable"))
                    if variable_name:
                        current = str(widget.getvar(variable_name))
                        translated = translate_text(current, language)
                        if translated != current:
                            widget.setvar(variable_name, translated)
                if isinstance(widget, tk.Canvas):
                    for item_id in widget.find_all():
                        try:
                            current = widget.itemcget(item_id, "text")
                        except tk.TclError:
                            continue
                        if current:
                            translated = translate_text(current, language)
                            if translated != current:
                                widget.itemconfigure(item_id, text=translated)
                if self._effective_dark_mode():
                    updates = {}
                    for option in ("bg", "background", "fg", "foreground",
                                   "activebackground", "activeforeground",
                                   "highlightbackground", "highlightcolor",
                                   "insertbackground", "disabledforeground"):
                        if option not in options:
                            continue
                        value = str(widget.cget(option)).upper()
                        if value in _DARK_COLOURS:
                            updates[option] = _DARK_COLOURS[value]
                    if updates:
                        widget.configure(**updates)
                for child in widget.winfo_children():
                    visit(child)
            except tk.TclError:
                return

        visit(page)
        dark_mode = self._effective_dark_mode()
        self.configure(bg=_DARK_COLOURS["#F7F3EA"] if dark_mode else WINDOW_BG)
        self.title(translate_text("游戏中心", language))

    def replace_page(self, page: tk.Widget) -> None:
        if self.current_page is not None and self.current_page.winfo_exists():
            self.current_page.destroy()
        self.current_page = page
        # Apply the selected appearance before the page becomes visible.
        if not getattr(page, "_preferences_ready", False):
            self.apply_uploaded_preferences()
        self.current_page.pack(fill="both", expand=True)

        # 页面自己的 on_close 决定返回层级：目录页回大厅，
        # 目录内游戏回原目录，从“我的最爱”启动的游戏回大厅。
        page_close = getattr(page, "on_close", None)
        if callable(page_close):
            self.protocol("WM_DELETE_WINDOW", page_close)
        elif self.username and not getattr(page, "_index_owned", False):
            self.protocol("WM_DELETE_WINDOW", self.close_external_page_to_home)
        else:
            self.protocol("WM_DELETE_WINDOW", self.close_application)

    def close_external_page_to_home(self) -> None:
        page = self.current_page
        if page is None:
            return
        balance = safe_balance(getattr(page, "balance", self.balance))
        close_handler = getattr(page, "on_close", None)
        if callable(close_handler):
            try:
                close_handler()
            except (tk.TclError, RuntimeError):
                pass
        self.set_balance(balance)
        self.after_idle(self._ensure_home_after_external_close)

    def _ensure_home_after_external_close(self) -> None:
        if not isinstance(self.current_page, HomeDashboard):
            self.show_main_menu()

    def styled_button(
        self,
        master,
        text,
        command,
        width=18,
        bg=CARD_BG,
        fg=TEXT,
        font_size=12,
    ):
        normal_bg = self.theme_colour(bg)
        normal_fg = self.theme_colour(fg)
        hover_bg = self.theme_colour(CARD_HOVER)
        translated_text = self.translate_ui(text)
        adaptive_width = width
        if self._effective_language() not in {"zh_CN", "zh_TW"}:
            adaptive_width = max(width, min(34, len(translated_text) + 2))
        button = tk.Button(
            master,
            text=translated_text,
            command=command,
            width=adaptive_width,
            font=("Microsoft YaHei UI", font_size, "bold"),
            bg=normal_bg,
            fg=normal_fg,
            activebackground=self.theme_colour("#F7BEC9"),
            activeforeground=self.theme_colour("#111111"),
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=13,
        )
        def set_button_colour(colour):
            button.config(bg=colour)

        button.bind("<Enter>", lambda event: set_button_colour(hover_bg))
        button.bind("<Leave>", lambda event: set_button_colour(normal_bg))
        return button

    def _activate_english_input(self, _event=None) -> None:
        """Select the US-English keyboard layout for authentication fields."""
        if os.name != "nt":
            return
        try:
            user32 = ctypes.windll.user32
            user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
            user32.ActivateKeyboardLayout.argtypes = (
                ctypes.c_void_p, ctypes.c_uint
            )
            user32.PostMessageW.argtypes = (
                ctypes.c_void_p, ctypes.c_uint,
                ctypes.c_size_t, ctypes.c_ssize_t,
            )
            layout = user32.LoadKeyboardLayoutW("00000409", 0x00000001)
            if layout:
                user32.ActivateKeyboardLayout(ctypes.c_void_p(layout), 0)
                user32.PostMessageW(
                    ctypes.c_void_p(self.winfo_id()), 0x0050, 0, layout
                )
        except (AttributeError, OSError, tk.TclError):
            return

    def _use_english_input_for(self, *entries: tk.Entry) -> None:
        for entry in entries:
            entry.bind("<FocusIn>", self._activate_english_input, add="+")
        self.after_idle(self._activate_english_input)

    # ---------------- 欢迎 / 登录 / 注册 ----------------

    def _auth_shell(self, title: str, subtitle: str):
        """新的身份页面骨架：品牌区与表单区并列，不复用旧页头结构。"""
        page = tk.Frame(self, bg="#FFFFFF")
        page._index_owned = True
        brand = tk.Frame(page, bg="#E6D9F2", width=410)
        brand.pack(side="left", fill="y")
        brand.pack_propagate(False)
        tk.Label(brand, text="♠  ♥  ♣  ♦", font=("Segoe UI Symbol", 24, "bold"),
                 bg="#E6D9F2", fg="#684C9C").pack(anchor="w", padx=42, pady=(70, 24))
        tk.Label(brand, text="GAME\nCENTER", font=("Segoe UI", 37, "bold"),
                 bg="#E6D9F2", fg="#111111", justify="left").pack(anchor="w", padx=42)
        tk.Label(brand, text="游戏、账户与余额，\n集中在一个清晰的入口。",
                 font=("Microsoft YaHei UI", 12), bg="#E6D9F2", fg="#111111",
                 justify="left").pack(anchor="w", padx=42, pady=(20, 0))
        tk.Frame(brand, bg="#DCEAF7", height=18).pack(side="bottom", fill="x")
        tk.Frame(brand, bg="#F7BEC9", height=26).pack(side="bottom", fill="x")
        tk.Frame(brand, bg="#CDEEDD", height=34).pack(side="bottom", fill="x")

        right = tk.Frame(page, bg="#FFFFFF")
        right.pack(side="left", fill="both", expand=True)
        panel = tk.Frame(right, bg="#FFFFFF", width=520, height=590)
        panel.pack(expand=True, padx=72, pady=45)
        panel.pack_propagate(False)
        tk.Label(panel, text=title, font=("Microsoft YaHei UI", 25, "bold"),
                 wraplength=500, justify="left",
                 bg="#FFFFFF", fg="#111111").pack(anchor="w")
        tk.Label(panel, text=subtitle, font=("Microsoft YaHei UI", 10),
                 wraplength=500, justify="left",
                 bg="#FFFFFF", fg="#111111").pack(anchor="w", pady=(6, 28))
        return page, panel

    def show_welcome_page(self):
        page, panel = self._auth_shell("欢迎", "请选择下一步以继续使用游戏中心。")
        tk.Label(panel, text="已有账号", font=("Microsoft YaHei UI", 11, "bold"),
                 bg="#FFFFFF", fg="#111111").pack(anchor="w")
        self.styled_button(panel, "登录账号", self.show_login_page,
                           width=28, bg="#DFF2E5").pack(anchor="w", pady=(8, 24))
        tk.Label(panel, text="第一次使用？", font=("Microsoft YaHei UI", 11, "bold"),
                 bg="#FFFFFF", fg="#111111").pack(anchor="w")
        self.styled_button(panel, "创建新账号", self.show_register_page,
                           width=28, bg="#E6D9F2").pack(anchor="w", pady=(8, 12))
        self.styled_button(panel, "体验账号", self.login_temp_account,
                           width=28, bg="#DCEAF7").pack(anchor="w")

        language_box = tk.Frame(page, bg="#FFFFFF")
        language_box.place(relx=0.985, rely=0.975, anchor="se")
        tk.Label(language_box, text="选择语言", font=("Microsoft YaHei UI", 9),
                 bg="#FFFFFF", fg="#111111").pack(side="left", padx=(0, 7))
        selected = tk.StringVar(value=LANGUAGE_OPTIONS[self.language])

        def choose_language(code: str) -> None:
            self.language = normalise_language(code)
            self.show_welcome_page()

        language_codes = {label: code for code, label in LANGUAGE_OPTIONS.items()}
        menu = tk.OptionMenu(
            language_box, selected, *LANGUAGE_OPTIONS.values(),
            command=lambda label: choose_language(language_codes[label]),
        )
        menu.configure(font=("Segoe UI", 9), bg="#FFFFFF", fg="#111111",
                       activebackground="#DCEAF7", relief="flat", bd=0,
                       highlightthickness=1, highlightbackground="#D6CEDD")
        menu["menu"].delete(0, "end")
        for code, label in LANGUAGE_OPTIONS.items():
            menu["menu"].add_command(
                label=label,
                command=lambda value=code, shown=label: (
                    selected.set(shown), choose_language(value)
                ),
            )
        menu.pack(side="left")
        self.replace_page(page)

    def show_login_page(self):
        page, panel = self._auth_shell("账号登录", "请输入已注册的用户名与密码。")

        username_row = EntryRow(panel, "用户名")
        username_row.pack(fill="x", pady=9)
        password_row = EntryRow(panel, "密码", show="*")
        password_row.pack(fill="x", pady=9)

        status_var = tk.StringVar(
            value=self.translate_ui(getattr(self, "pending_auth_notice", ""))
        )
        self.pending_auth_notice = ""
        tk.Label(
            panel,
            textvariable=status_var,
            font=("Microsoft YaHei UI", 10),
            bg="#FFFFFF",
            fg="#B84F6A",
        ).pack(pady=(8, 4))

        buttons = tk.Frame(panel, bg="#FFFFFF")
        buttons.pack(pady=12)

        def submit(event=None):
            username = username_row.entry.get().strip()
            password = password_row.entry.get()
            if not username or not password:
                status_var.set(self.translate_ui("请输入用户名和密码。"))
                return

            self.users = load_user_data()
            matched = next(
                (u for u in self.users if u.get("user_name") == username),
                None,
            )

            if matched and str(matched.get("lock", "False")) == "True":
                status_var.set(self.translate_ui(
                    f"账号 {username} 已被锁定，请联系管理员。"
                ))
                return

            if matched and matched.get("password") == password:
                self.failed_attempts.pop(username, None)
                self.current_user = matched
                self.username = username
                self.balance = safe_balance(matched.get("cash"))
                self.is_guest = False
                self.language = normalise_language(matched.get("language", self.language))
                self.dark_mode = preference_bool(matched.get("dark_mode", False))
                self.show_main_menu()
                return

            attempts = self.failed_attempts.get(username, 0) + 1
            self.failed_attempts[username] = attempts
            remaining = max(0, 3 - attempts)

            if attempts >= 3:
                if matched:
                    matched["lock"] = "True"
                    save_user_data(self.users)
                status_var.set(self.translate_ui("登录失败三次，该账号已被锁定。"))
            else:
                status_var.set(self.translate_ui(
                    f"用户名或密码错误，还可尝试 {remaining} 次。"
                ))
            password_row.entry.delete(0, "end")

        self.styled_button(buttons, "登录账号", submit, width=28).pack()

        tk.Button(panel, text="还没注册？注册！", command=self.show_register_page,
                  font=("Microsoft YaHei UI", 10, "bold"), bg="#FFFFFF",
                  fg="#111111", activebackground="#FFFFFF",
                  activeforeground="#684C9C", relief="flat", bd=0,
                  cursor="hand2").pack(pady=(10, 3))
        tk.Button(panel, text="← 返回欢迎页", command=self.show_welcome_page,
                  font=("Microsoft YaHei UI", 9), bg="#FFFFFF", fg="#111111",
                  activebackground="#FFFFFF", relief="flat", bd=0,
                  cursor="hand2").pack()

        username_row.entry.bind("<Return>", lambda e: password_row.entry.focus_set())
        password_row.entry.bind("<Return>", submit)
        self._use_english_input_for(username_row.entry, password_row.entry)
        username_row.entry.focus_set()

        self.replace_page(page)

    def login_temp_account(self):
        self.users = []
        self.current_user = {
            "user_name": "TEMP_ACCOUNT",
            "cash": "500000.00",
            "favorites": [],
            "language": self.language,
            "dark_mode": self.dark_mode,
        }
        self.username = "TEMP_ACCOUNT"
        self.balance = 500000.0
        self.is_guest = True
        self.show_main_menu()

    def show_register_page(self):
        page, panel = self._auth_shell("创建账号", "用户名不可重复，密码需要输入两次确认。")

        username_row = EntryRow(panel, "用户名")
        username_row.pack(fill="x", pady=7)
        password1_row = EntryRow(panel, "密码", show="*")
        password1_row.pack(fill="x", pady=7)
        password2_row = EntryRow(panel, "确认密码", show="*")
        password2_row.pack(fill="x", pady=7)

        status_var = tk.StringVar()
        tk.Label(
            panel,
            textvariable=status_var,
            font=("Microsoft YaHei UI", 10),
            bg="#FFFFFF",
            fg="#B84F6A",
        ).pack(pady=(7, 2))

        def submit(event=None):
            username = username_row.entry.get().strip()
            password1 = password1_row.entry.get()
            password2 = password2_row.entry.get()

            if len(username) < 3:
                status_var.set(self.translate_ui("用户名至少需要 3 个字符。"))
                return
            if not password1:
                status_var.set(self.translate_ui("密码不能为空。"))
                return
            if password1 != password2:
                status_var.set(self.translate_ui("两次输入的密码不一致。"))
                return

            users = load_user_data()
            if any(u.get("user_name") == username for u in users):
                status_var.set(self.translate_ui("用户名已存在，请选择其他用户名。"))
                return

            users.append(
                {
                    "user_name": username,
                    "password": password1,
                    "cash": "0.00",
                    "lock": "False",
                    "favorites": [],
                    "language": self.language,
                    "dark_mode": self.dark_mode,
                }
            )
            save_user_data(users)
            self.pending_auth_notice = f"账号 {username} 已建立，请登录。"
            self.show_login_page()

        buttons = tk.Frame(panel, bg="#FFFFFF")
        buttons.pack(pady=13)
        self.styled_button(buttons, "注册", submit, width=13).grid(
            row=0, column=0, padx=8
        )
        self.styled_button(
            buttons,
            "返回",
            self.show_welcome_page,
            width=13,
            bg="#E6DFF0",
        ).grid(row=0, column=1, padx=8)

        password2_row.entry.bind("<Return>", submit)
        self._use_english_input_for(
            username_row.entry, password1_row.entry, password2_row.entry
        )
        username_row.entry.focus_set()
        self.replace_page(page)

    # ---------------- 主目录 ----------------

    def show_main_menu(self):
        self.reload_current_user()
        actions = [
            ("赌场游戏", "桌面游戏与扑克专区", "#CDB7EB", "Casino_Games.png", self.open_casino),
            ("街机小游戏", "轻量、快速的休闲游戏", "#CDEEDD", "Small_Games.png", self.open_small_games),
            ("刮刮乐", "选择票券并即时开奖", "#F7BEC9", "Lotto.png", self.open_lotto),
            ("老虎机", "浏览并进入老虎机游戏", "#DCEAF7", "Slot_Machine.png", self.open_slot_machines),
            ("账号服务", "余额、充值、提款与密码", "#E7D7B8", "Account.png", self.show_account_page),
            ("安全登出", "保存资料并返回登录页", "#D8D3CE", "Logout.png", self.logout),
        ]
        favorites = (
            [] if self.is_guest else
            [resolve_favorite(item) for item in user_favorites(self.current_user)]
        )
        page = HomeDashboard(
            self, self.username, self.balance, actions,
            favorites, self.launch_favorite, self.remove_favorite,
        )
        self.replace_page(page)

    def remove_favorite(self, favorite: dict) -> bool:
        """从当前玩家的 JSON 资料删除收藏；体验账号不会写入。"""
        if self.is_guest or not self.username:
            return False
        module_name = str(favorite.get("module", "")).strip()
        if not module_name:
            return False
        users = load_user_data()
        matched = next(
            (user for user in users
             if user.get("user_name") == self.username),
            None,
        )
        if matched is None:
            return False
        before = user_favorites(matched)
        after = [item for item in before if item.get("module") != module_name]
        if len(after) == len(before):
            return False
        matched["favorites"] = after
        save_user_data(users)
        self.users = users
        self.current_user = matched
        return True

    def launch_favorite(self, favorite: dict) -> None:
        """从大厅直接启动收藏游戏；不会先显示对应游戏目录。"""
        favorite = resolve_favorite(favorite)
        hub = favorite.get("hub", "")
        display_name = favorite.get("name", "收藏游戏")
        module_name = favorite.get("module", "")
        if not module_name:
            return
        try:
            hub_names = {
                "casino": "Casino_Games.casino_games",
                "lotto": "Lotto.lotto",
                "slot": "Slot_Machine.slot_machine",
                "small": "Small_Games.small_games",
            }
            hub_module = importlib.import_module(hub_names[hub])
            embedded = getattr(hub_module, "EMBEDDED_GAME_MODULES", set())
            legacy = getattr(hub_module, "LEGACY_PROCESS_MODULES", set())

            if hub == "lotto" or (
                module_name in embedded and module_name not in legacy
            ):
                game_module = importlib.import_module(module_name)
                game_main = getattr(game_module, "main")

                def return_home(final_balance: float) -> None:
                    self.set_balance(float(final_balance))
                    self.show_main_menu()

                kwargs = {
                    "parent": self,
                    "balance": self.balance,
                    "user": self.username,
                    "on_back": return_home,
                    "on_balance_change": self.set_balance,
                }
                close_modules = getattr(hub_module, "CLOSE_RETURNS_TO_CASINO_MODULES", set())
                if module_name in close_modules:
                    kwargs["close_returns_to_parent"] = True
                game_page = game_main(**kwargs)
                if not isinstance(game_page, tk.Widget):
                    raise TypeError("收藏游戏入口必须返回 Tkinter 页面。")
                self.replace_page(game_page)
                if module_name in close_modules:
                    install_close = getattr(
                        game_page, "_install_embedded_close_handler", None
                    )
                    if callable(install_close):
                        install_close()
                return

            # 旧式子进程游戏仍由原目录启动器负责，但目录页不会显示。
            hub_page = call_with_supported_kwargs(
                hub_module.main,
                parent=self,
                balance=self.balance,
                user=self.username,
                on_back=lambda value: (self.set_balance(value), self.show_main_menu()),
                on_balance_change=self.set_balance,
                translator=self.translate_ui,
            )
            if hub == "lotto":
                hub_page.launch_game(display_name, module_name)
            else:
                hub_page.launch_game(display_name, module_name, False)
        except Exception as exc:
            messagebox.showerror(
                "启动失败",
                f"无法打开收藏游戏《{display_name}》：\n\n{type(exc).__name__}: {exc}",
                parent=self,
            )

    def open_casino(self):
        page = call_with_supported_kwargs(
            casino_games.main,
            parent=self,
            balance=self.balance,
            user=self.username,
            on_back=self.return_from_casino,
            on_balance_change=self.set_balance,
            translator=self.translate_ui,
        )
        self.casino_page = page
        self.replace_page(page)

    def return_from_casino(self, balance: float):
        self.set_balance(balance)
        self.casino_page = None
        self.show_main_menu()

    def open_lotto(self):
        self.open_game_hub("Lotto.lotto", "刮刮乐")

    def open_small_games(self):
        self.open_game_hub("Small_Games.small_games", "街机小游戏")

    def open_slot_machines(self):
        self.open_game_hub("Slot_Machine.slot_machine", "老虎机")

    def open_game_hub(self, module_name: str, title: str):
        """延迟加载 GUI 游戏目录，避免可选子游戏影响 index.py 启动。"""
        try:
            module = importlib.import_module(module_name)
            hub_main = getattr(module, "main", None)
            if not callable(hub_main):
                raise AttributeError(f"{module_name} 没有可调用的 main()")

            page = call_with_supported_kwargs(
                hub_main,
                parent=self,
                balance=self.balance,
                user=self.username,
                on_back=self.return_from_game_hub,
                on_balance_change=self.set_balance,
                translator=self.translate_ui,
            )
            if not isinstance(page, tk.Widget):
                raise TypeError(f"{module_name}.main() 必须返回 Tkinter Widget/Frame")

            self.game_hub_page = page
            self.replace_page(page)
        except Exception as exc:
            messagebox.showerror(
                "启动失败",
                f"无法打开{title}：\n\n{type(exc).__name__}: {exc}",
                parent=self,
            )

    def return_from_game_hub(self, balance: float):
        self.set_balance(balance)
        self.game_hub_page = None
        self.show_main_menu()

    # ---------------- 账号服务 ----------------

    def show_account_page(self, initial_action: str = "balance"):
        # The main menu and every balance mutation already keep this state
        # current. Avoid another full JSON read whenever this page is entered
        # or rebuilt after confirming settings.
        page = tk.Frame(self, bg=WINDOW_BG)
        page._index_owned = True
        page.on_close = self.show_main_menu
        header = tk.Frame(page, bg="#E6D9F2", height=82)
        header.pack(fill="x")
        header.pack_propagate(False)
        account_title = self.translate_ui("账号服务")
        account_title_size = 20 if len(account_title) > 10 else 23
        tk.Label(header, text="账号服务",
                 font=("Microsoft YaHei UI", account_title_size, "bold"),
                 wraplength=250, justify="left",
                 bg="#E6D9F2", fg="#111111").pack(side="left", padx=(22, 10))
        self.styled_button(
            header,
            "← 返回主目录",
            self.show_main_menu,
            width=14,
            bg="#FFFFFF",
            font_size=10,
        ).pack(side="left", padx=(0, 22), pady=18)
        tk.Label(header, text=greeting_for(self.username),
                 font=("Microsoft YaHei UI", 11, "bold"),
                 wraplength=220, justify="center",
                 bg="#E6D9F2", fg="#111111").place(
                     relx=0.62, rely=0.5, anchor="center"
                 )
        identity = tk.Frame(header, bg="#FFFFFF", padx=18, pady=9,
                            highlightbackground="#CBBBDD", highlightthickness=1)
        identity.pack(side="right", padx=25, pady=14)
        self.account_balance_var = tk.StringVar(
            value=f"余额  ${self.balance:,.2f}"
        )
        tk.Label(identity, textvariable=self.account_balance_var,
                 font=("Microsoft YaHei UI", 14, "bold"), bg="#FFFFFF",
                 fg="#111111").pack()

        add_paper_art_ribbon(page, WINDOW_BG)
        body = tk.Frame(page, bg=WINDOW_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(16, 24))

        navigation = tk.Frame(body, bg="#DCEAF7", width=230,
                              highlightbackground="#AFC4D8", highlightthickness=1)
        navigation.pack(side="left", fill="y", padx=(0, 18))
        navigation.pack_propagate(False)
        tk.Label(navigation, text="账户管理", font=("Microsoft YaHei UI", 15, "bold"),
                 bg="#DCEAF7", fg="#111111").pack(anchor="w", padx=20, pady=(24, 14))
        services = [
            ("余额概览", self.show_balance, True),
            ("充值", lambda: self.show_money_dialog("charge"), not self.is_guest),
            ("提款", lambda: self.show_money_dialog("withdraw"), not self.is_guest),
            ("更改密码", self.show_password_dialog, not self.is_guest),
            ("设置", self.show_settings, True),
        ]
        for label, command, enabled in services:
            button = tk.Button(navigation, text=label, command=command, anchor="w",
                               justify="left", wraplength=175,
                               font=("Microsoft YaHei UI", 11, "bold"),
                               bg="#DCEAF7", fg="#111111",
                               activebackground="#FFFFFF", activeforeground="#111111",
                               disabledforeground="#777777",
                               state="normal" if enabled else "disabled",
                               relief="flat", bd=0, padx=20, pady=13,
                               cursor="hand2" if enabled else "arrow")
            button.pack(fill="x", padx=8, pady=3)

        work = tk.Frame(body, bg="#FFFFFF", highlightbackground="#D6CEDD",
                        highlightthickness=1)
        work.pack(side="left", fill="both", expand=True)
        self.account_action_host = tk.Frame(work, bg="#FFFFFF")
        self.account_action_host.pack(fill="both", expand=True, padx=32, pady=(28, 16))
        self.account_notice = tk.Label(work, text="", anchor="w",
                                       justify="left", wraplength=730,
                                       font=("Microsoft YaHei UI", 10, "bold"),
                                       bg="#DFF2E5", fg="#111111", padx=16, pady=10)
        self.account_notice.pack(fill="x", padx=32, pady=(0, 24))

        self.replace_page(page)
        if initial_action == "settings":
            self.show_settings()
        else:
            self.show_balance(reload_user=False)

    def show_settings(self):
        if not self._clear_account_action():
            return
        self._account_title("外观与语言", "这些选项只影响本次上传的五个界面文件。")
        form = tk.Frame(self.account_action_host, bg="#FFFFFF")
        form.pack(fill="x", anchor="n")

        dark_value = tk.BooleanVar(value=self.dark_mode)

        tk.Checkbutton(
            form, text="黑暗模式", variable=dark_value,
            font=("Microsoft YaHei UI", 12, "bold"), bg="#FFFFFF", fg="#111111",
            activebackground="#FFFFFF", activeforeground="#111111",
            selectcolor="#FFFFFF", anchor="w", padx=0, pady=10,
        ).pack(fill="x", anchor="w")

        tk.Label(form, text="语言", font=("Microsoft YaHei UI", 12, "bold"),
                 bg="#FFFFFF", fg="#111111").pack(anchor="w", pady=(18, 7))
        language_value = tk.StringVar(value=LANGUAGE_OPTIONS[self.language])

        language_codes = {label: code for code, label in LANGUAGE_OPTIONS.items()}
        language_menu = tk.OptionMenu(
            form, language_value, *LANGUAGE_OPTIONS.values(),
        )
        language_menu.configure(font=("Segoe UI", 11), bg="#DCEAF7", fg="#111111",
                                activebackground="#DDF2E5", relief="flat", bd=0,
                                width=24, anchor="w", padx=12, pady=8)
        language_menu["menu"].delete(0, "end")
        for code, label in LANGUAGE_OPTIONS.items():
            language_menu["menu"].add_command(
                label=label,
                command=lambda shown=label: language_value.set(shown),
            )
        language_menu.pack(anchor="w")

        def confirm_preferences() -> None:
            self.language = normalise_language(
                language_codes.get(language_value.get(), self.language)
            )
            self.dark_mode = bool(dark_value.get())
            self.persist_current_user()
            self.after_idle(lambda: self.show_account_page("settings"))

        self.styled_button(
            form, "确定", confirm_preferences, width=14,
            bg="#DFF2E5", font_size=10,
        ).pack(anchor="w", pady=(22, 0))
        self.apply_uploaded_preferences(self.account_action_host)

    def _clear_account_action(self) -> bool:
        host = getattr(self, "account_action_host", None)
        if host is None or not host.winfo_exists():
            return False
        for widget in host.winfo_children():
            widget.destroy()
        self.account_notice.configure(
            text="", bg=self.theme_colour("#DFF2E5")
        )
        return True

    def _account_message(self, text: str, error: bool = False) -> None:
        notice = getattr(self, "account_notice", None)
        if notice is not None and notice.winfo_exists():
            notice.configure(
                text=self.translate_ui(text),
                bg=self.theme_colour("#F6D0D8" if error else "#DFF2E5"),
            )

    def _account_title(self, title: str, subtitle: str) -> None:
        tk.Label(self.account_action_host, text=self.translate_ui(title),
                 font=("Microsoft YaHei UI", 21, "bold"), bg="#FFFFFF",
                 justify="left", wraplength=720,
                 fg="#111111").pack(anchor="w")
        tk.Label(self.account_action_host, text=self.translate_ui(subtitle),
                 font=("Microsoft YaHei UI", 10), bg="#FFFFFF",
                 justify="left", wraplength=720,
                 fg="#111111").pack(anchor="w", pady=(5, 22))

    def show_balance(self, reload_user: bool = True):
        if reload_user:
            self.reload_current_user()
        if not self._clear_account_action():
            return
        if hasattr(self, "account_balance_var"):
            self.account_balance_var.set(
                self.translate_ui(f"余额  ${self.balance:,.2f}")
            )
        self._account_title("余额概览", "你的账户资料已从本地记录重新载入。")
        card = tk.Frame(self.account_action_host, bg="#DFF2E5", padx=28, pady=25,
                        highlightbackground="#A9CEB9", highlightthickness=1)
        card.pack(fill="x")
        tk.Label(card, text="可用余额", font=("Microsoft YaHei UI", 11),
                 bg="#DFF2E5", fg="#111111").pack(anchor="w")
        tk.Label(card, text=f"${self.balance:,.2f}", font=("Segoe UI", 31, "bold"),
                 bg="#DFF2E5", fg="#111111").pack(anchor="w", pady=(6, 0))
        self._account_message("余额资料已更新。")
        self.apply_uploaded_preferences(self.account_action_host)

    def show_money_dialog(self, operation: str):
        title = "充值" if operation == "charge" else "提款"
        if not self._clear_account_action():
            return
        self._account_title(title, f"当前余额 ${self.balance:,.2f} · 此操作需要管理员验证。")
        form = tk.Frame(self.account_action_host, bg="#FFFFFF")
        form.pack(fill="x", anchor="n")
        amount_row = EntryRow(form, f"{title}金额")
        amount_row.pack(fill="x", pady=7)
        admin_row = EntryRow(form, "管理员")
        admin_row.pack(fill="x", pady=7)
        admin_password = EntryRow(form, "管理密码", show="*")
        admin_password.pack(fill="x", pady=7)

        def submit(event=None):
            if ADMINS.get(admin_row.entry.get().strip()) != admin_password.entry.get():
                self._account_message("管理员账号或密码不正确。", True)
                return
            try:
                amount = round(float(amount_row.entry.get()), 2)
            except ValueError:
                self._account_message("请输入有效金额。", True)
                return
            if amount <= 0:
                self._account_message("金额必须大于 0。", True)
                return
            if operation == "withdraw" and amount > self.balance:
                self._account_message("提款金额不能超过当前余额。", True)
                return
            self.balance += amount if operation == "charge" else -amount
            self.persist_current_user()
            self.account_balance_var.set(
                self.translate_ui(f"余额  ${self.balance:,.2f}")
            )
            self._account_message(f"{title}成功：${amount:,.2f}；当前余额 ${self.balance:,.2f}。")
            amount_row.entry.delete(0, "end")
            admin_password.entry.delete(0, "end")

        self.styled_button(form, f"确认{title}", submit, width=16,
                           bg="#DFF2E5", font_size=11).pack(anchor="w", pady=(16, 0))
        admin_password.entry.bind("<Return>", submit)
        amount_row.entry.focus_set()
        self.apply_uploaded_preferences(self.account_action_host)

    def show_password_dialog(self):
        if not self._clear_account_action():
            return
        self._account_title("更改密码", "密码在当前页面完成验证与更新，不会打开弹窗。")
        form = tk.Frame(self.account_action_host, bg="#FFFFFF")
        form.pack(fill="x", anchor="n")
        old_row = EntryRow(form, "当前密码", show="*")
        old_row.pack(fill="x", pady=7)
        new_row = EntryRow(form, "新密码", show="*")
        new_row.pack(fill="x", pady=7)
        confirm_row = EntryRow(form, "确认密码", show="*")
        confirm_row.pack(fill="x", pady=7)

        def submit(event=None):
            self.reload_current_user()
            if not self.current_user or self.current_user.get("password") != old_row.entry.get():
                self._account_message("当前密码不正确。", True)
                return
            new_password = new_row.entry.get()
            if not new_password:
                self._account_message("新密码不能为空。", True)
                return
            if new_password != confirm_row.entry.get():
                self._account_message("两次输入的新密码不一致。", True)
                return
            self.current_user["password"] = new_password
            self.persist_current_user()
            self._account_message("密码已成功更新。")
            for row in (old_row, new_row, confirm_row):
                row.entry.delete(0, "end")

        self.styled_button(form, "更新密码", submit, width=16,
                           bg="#F6D0D8", font_size=11).pack(anchor="w", pady=(16, 0))
        confirm_row.entry.bind("<Return>", submit)
        old_row.entry.focus_set()
        self.apply_uploaded_preferences(self.account_action_host)

    # ---------------- 数据同步 / 退出 ----------------

    def reload_current_user(self):
        if not self.username or self.is_guest:
            return
        self.users = load_user_data()
        self.current_user = next(
            (u for u in self.users if u.get("user_name") == self.username),
            self.current_user,
        )
        if self.current_user:
            self.balance = safe_balance(self.current_user.get("cash", self.balance))
            self.language = normalise_language(
                self.current_user.get("language", self.language)
            )
            self.dark_mode = preference_bool(
                self.current_user.get("dark_mode", self.dark_mode)
            )

    def persist_current_user(self):
        if not self.username or self.is_guest:
            return
        users = load_user_data()
        matched = next(
            (u for u in users if u.get("user_name") == self.username),
            None,
        )
        if matched is None:
            return

        matched["cash"] = f"{self.balance:.2f}"
        if self.current_user:
            matched["password"] = self.current_user.get(
                "password",
                matched.get("password", ""),
            )
            matched["lock"] = self.current_user.get(
                "lock",
                matched.get("lock", "False"),
            )
            # 收藏可能由游戏目录页直接写入；以刚载入的磁盘资料为准，
            # 避免余额同步时用旧的 current_user 覆盖新收藏。
            matched["favorites"] = user_favorites(matched)
            matched["language"] = normalise_language(self.language)
            matched["dark_mode"] = bool(self.dark_mode)

        save_user_data(users)
        self.users = users
        self.current_user = matched

    def set_balance(self, balance: float):
        self.balance = safe_balance(balance)
        self.persist_current_user()

    def logout(self):
        self.persist_current_user()
        self.current_user = None
        self.username = ""
        self.balance = 0.0
        self.is_guest = False
        self.language = "en"
        self.dark_mode = False
        self.casino_page = None
        self.game_hub_page = None
        self.show_welcome_page()

    def close_application(self):
        if self.casino_page is not None and getattr(self.casino_page, "process", None):
            messagebox.showwarning(
                "游戏运行中",
                "请先关闭独立运行中的赌场游戏。",
                parent=self,
            )
            return
        if self.game_hub_page is not None and getattr(
            self.game_hub_page, "process", None
        ):
            messagebox.showwarning(
                "游戏运行中",
                "请先关闭当前运行中的游戏。",
                parent=self,
            )
            return

        self.persist_current_user()
        self.destroy()


def main():
    app = GameCenterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
