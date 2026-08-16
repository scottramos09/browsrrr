import codecs
import winreg

UA = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{CEBFF5CD-ACE2-4F4F-9148-9957BA434F14}\Count"
FU = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage"


def dump(key_path: str, label: str, decode: bool) -> None:
    print(f"--- {label}: {key_path}")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
    except OSError as error:
        print("  OPEN FAILED:", error)
        return
    names = []
    index = 0
    while True:
        try:
            name, _data, _typ = winreg.EnumValue(key, index)
        except OSError:
            break
        index += 1
        names.append(name)
    winreg.CloseKey(key)

    shown = [codecs.decode(n, "rot13") if decode else n for n in names]
    print(f"  total values: {len(names)}")
    print("  paint matches:", [d for d in shown if "paint" in d.lower()][:10])
    print("  sample:", shown[:12])


dump(UA, "UserAssist", decode=True)
for sub in ("AppSwitched", "AppLaunch", "AppBadgeUpdated"):
    dump(f"{FU}\\{sub}", f"FeatureUsage\\{sub}", decode=False)

from browsrrr.app_catalog import scan_recent_apps

entries = scan_recent_apps()
print("--- scan_recent_apps total:", len(entries))
print("paint in scan:", [e.path for e in entries if "paint" in e.name.lower()])
print("top 10:", [e.name for e in entries[:10]])